"""full implementation of a python-only client to connect to usbipd servers"""

# Protocol can be found here:
# https://docs.kernel.org/usb/usbip_protocol.html
#
from __future__ import annotations

import errno
import logging
import os
import socket
import struct
from dataclasses import dataclass
from time import perf_counter, time
from typing import Optional, cast
from collections import namedtuple

# wrapper for sockets
from serial_usbipclient.socket_wrapper import SocketWrapper

from .protocol.packets import (CMD_SUBMIT, CMD_UNLINK, HEADER_BASIC,
                               OP_REP_DEV_INTERFACE, OP_REP_DEV_PATH,
                               OP_REP_DEVLIST_HEADER, OP_REP_IMPORT,
                               OP_REQ_DEVLIST, OP_REQ_IMPORT,
                               RET_SUBMIT_PREFIX, RET_UNLINK, CommonHeader)
from .protocol.urb_packets import (ConfigurationDescriptor, DeviceDescriptor,
                                   EndPointDescriptor, GenericDescriptor,
                                   StringDescriptor, UrbSetupPacket)
# enums needed for USBIP and URBs
from .protocol.usb_descriptors import DescriptorType, DeviceInterfaceClass
from .protocol.usbip_defs import (BasicCommands, CDCControl,  # just the basics
                                  Direction, ErrorCodes, Status)
# USBIP & URB packet definitions
from .protocol.usbip_protocol import (URBCDCRequestType, URBSetupRequestType,
                                      URBStandardDeviceRequest,
                                      URBTransferFlags)

LOGGER: logging.Logger = logging.getLogger('serial-usbipclient')
LOGGER.addHandler(logging.NullHandler())  # in case wrapping application hasn't set a default handler

PAYLOAD_TIMEOUT: float = 0.250  # maximum time (seconds) we'll wait for pieces of our payload


@dataclass
class HardwareID:
    """hardware id of device we want to connect to"""

    vid: int = 0
    pid: int = 0

    def __eq__(self, other: object) -> bool:
        """test if two hardware ids are the same"""
        if not isinstance(other, HardwareID):
            raise NotImplementedError
        return self.vid == other.vid and self.pid == other.pid

    def __str__(self) -> str:
        """easy to read representation of hardware id"""
        return f"vid: 0x{self.vid:04x}, pid: 0x{self.pid:04x}"


@dataclass
class USB_Endpoint:  # pylint: disable=invalid-name
    """endpoint for a USB interface"""

    endpoint: Optional[EndPointDescriptor] = None  # host -> USB device

    @property
    def number(self) -> int:
        """return the number for the endpoint"""
        return self.endpoint.number if self.endpoint else 0


class CDCEndpoints:
    """endpoints we need to talk to a CDC device"""
    def __init__(self):
        """initialize"""
        self.control: USB_Endpoint = USB_Endpoint(endpoint=EndPointDescriptor())
        self.input: Optional[USB_Endpoint] = None
        self.output: Optional[USB_Endpoint] = None


class USBIPError(Exception):
    """base for all USBIP errors"""

    def __init__(self, detail: str):
        """our basic exception"""
        self.detail: str = detail

    def __str__(self) -> str:
        """return our details"""
        return self.detail


class USBIPValueError(ValueError):
    """wrapper for issues with a value"""


class USBIPServerTimeoutError(USBIPError):
    """timeout while trying to connect to the usbip server"""


class USBIPConnectionError(USBIPError):
    """connection error while trying to connect to the usbip server"""


class USBIPResponseTimeoutError(USBIPError):
    """timeout while waiting for data from the USBIP"""

    def __init__(self, **kwargs):
        """timed out, aggregate information for diagnostics"""
        self.timeout: float = kwargs.get("timeout", 0.0)
        self.request: Optional[bytes] = kwargs.get("request", None)
        self.size: Optional[int] = kwargs.get("size", None)
        super().__init__(
            detail=f"Timeout error, timeout={self.timeout}, "
            f"request={self.request.hex() if self.request else 'None'}, "  # pylint: disable=inconsistent-quotes
            f"size={self.size}"
        )


class USBConnectionLostError(USBIPError):
    """the connection to the USB device has been lost"""

    USB_DISCONNECT: list[int] = [errno.ENOENT, errno.ENODEV]

    def __init__(self, detail: str, connection: USBIP_Connection | SocketWrapper):
        """details of the connection to assist recovery"""
        self.connection: USBIP_Connection | SocketWrapper = connection
        super().__init__(detail=detail)


class USBAttachError(USBIPError):
    """problem attaching to the device, specifics in the error status"""

    def __init__(self, detail: str, an_errno: int):
        """details of the error"""
        self.errno: int = abs(an_errno)
        detail += (f", {self.errno=}/{errno.errorcode[self.errno]}, "
                   f"{ErrorCodes.readable_errno(self.errno)}")
        super().__init__(detail=detail)


@dataclass
class URBResponse:
    """for storing URB responses"""
    prefix: RET_SUBMIT_PREFIX
    payload: bytes


class USBIP_Connection:  # pylint: disable=too-many-instance-attributes, invalid-name
    """a connection to an usbip device we attached to"""
    def __init__(self, busnum: int = 0, devnum: int = 0, seqnum: int = 0,
                 device: Optional[HardwareID] = None, sock: Optional[SocketWrapper] = None):
        """fill in our local variables"""
        self.busnum: int = busnum
        self.devnum: int = devnum
        self.seqnum: int = seqnum  # tracks request/response for all endpoints of device connection
        self.device: Optional[HardwareID] = device
        self.socket: Optional[SocketWrapper] = sock
        self._configuration: Optional[ConfigurationDescriptor] = None
        self._device: Optional[DeviceDescriptor] = None
        self._endpoints: CDCEndpoints = CDCEndpoints()
        self._commands: dict[int, CMD_SUBMIT] = {}  # seqnum/command
        self._responses: dict[int, URBResponse] = {}  # seqnum/(ret/data)
        self._logger: logging.Logger = LOGGER
        self._delimiter: bytes = b'\r\n'

    @property
    def delimiter(self) -> bytes:
        """return the current delimiter"""
        return self._delimiter

    @delimiter.setter
    def delimiter(self, delimiter: bytes) -> None:
        """set the delimiter"""
        self._delimiter = delimiter

    @property
    def endpoint(self) -> CDCEndpoints:
        """return our accessor the endpoint"""
        return self._endpoints

    @property
    def devid(self) -> int:
        """uniquely identifies the device to the usbipd service"""
        return self.busnum << 16 | self.devnum

    @property
    def device_desc(self) -> DeviceDescriptor | None:
        """return the device descriptor"""
        return self._device

    @device_desc.setter
    def device_desc(self, desc: DeviceDescriptor) -> None:
        """set our new device descriptor"""
        self._device = desc

    @property
    def configuration(self) -> ConfigurationDescriptor:
        """configuration of the device"""
        if self._configuration is None:
            raise USBIPValueError("no configuration for device")
        return self._configuration

    @configuration.setter
    def configuration(self, configuration: ConfigurationDescriptor) -> None:
        """set the configuration to the device, locate endpoints"""
        if self._device is None:
            raise USBIPValueError("cannot set configuration if there's no device!")

        if configuration not in self._device.configurations:
            self._device.configurations.append(configuration)
        self._configuration = configuration
        for interface in self._configuration.interfaces:
            if interface.interface_class == DeviceInterfaceClass.CDC_DATA.value:
                for descriptor in interface.descriptors:
                    if descriptor.descriptor_type == DescriptorType.ENDPOINT_DESCRIPTOR.value:
                        endpoint_desc: EndPointDescriptor = cast(EndPointDescriptor, descriptor)
                        if endpoint_desc.is_output:
                            self._endpoints.output = USB_Endpoint(endpoint=endpoint_desc)
                        else:
                            self._endpoints.input = USB_Endpoint(endpoint=endpoint_desc)

    @property
    def control(self) -> USB_Endpoint:
        """the control endpoint"""
        return self.endpoint.control

    @property
    def output(self) -> USB_Endpoint:
        """the control endpoint"""
        if self.endpoint.output is None:
            raise USBIPValueError("no output endpoint!")
        return self.endpoint.output

    @property
    def input(self) -> USB_Endpoint:
        """the control endpoint"""
        if self.endpoint.input is None:
            raise USBIPValueError("no input endpoint!")
        return self.endpoint.input

    @property
    def pending_commands(self) -> list[CMD_SUBMIT]:
        """return any commands to unlink"""
        return [cmd for _, cmd in self._commands.items()]

    @property
    def pending_reads(self) -> int:
        """calculate buffer size available for pending read operations"""
        if self.endpoint.input is None:
            raise USBIPValueError("no endpoint!")
        return len([seqnum for seqnum, cmd in self._commands.items() if cmd.ep == self.endpoint.input.number])

    def sendall(self, data: bytes) -> None:
        """wrapper for socket sendall"""
        if self.socket:
            self.socket.sendall(data)
        else:
            raise USBIPValueError("socket not available!")

    def send_command(self, command: CMD_SUBMIT) -> int:
        """send the command"""
        try:
            self.sendall(command.pack())
            self._commands[command.seqnum] = command
            if command.ep and command.direction == Direction.USBIP_DIR_IN:  # a read is being issued
                self._logger.debug(f"queued read #{command.seqnum}")

            # If this is a *write* to the device, then wait for confirmation
            # it was successful
            if command.ep in [self.output.number, self.control.number] and command.direction == Direction.USBIP_DIR_OUT:
                timeout: float = 5.0  # pretty large for testing
                start_time: float = perf_counter()
                while command.seqnum not in self._responses and perf_counter() - start_time < timeout:
                    self.wait_for_response()

                # if we got a response, then pop it off and return the size of data
                #  the send operation successfully sent
                if command.seqnum in self._responses:
                    response: URBResponse = self._responses.pop(command.seqnum)
                    self._commands.pop(command.seqnum)
                    return response.prefix.actual_length  # how much data was sent
            return 0
        except ConnectionError as connection_error:
            raise USBConnectionLostError(detail="send_command() connection lost", connection=self) from connection_error

    def send_unlink(self, command: CMD_UNLINK) -> bool:
        """send an unlink command"""
        try:
            self._logger.debug(f"UNLINK #{command.unlink_seqnum}")
            self.sendall(command.pack())
            unlink_response: Optional[RET_UNLINK] = self.wait_for_unlink()
            if unlink_response and abs(unlink_response.status) in USBConnectionLostError.USB_DISCONNECT:
                return True
            return False
        except ConnectionError as connection_error:
            raise USBConnectionLostError(detail="connection lost", connection=self) from connection_error

    def readall(self, size: int, timeout: float = PAYLOAD_TIMEOUT) -> bytes:
        """read all the expected data from the socket"""
        return USBIPClient.readall(size, self, timeout)

    def wait_for_unlink(self) -> Optional[RET_UNLINK]:
        """wait for the unlink response"""
        start_time: float = time()
        while time() - start_time < 10.0:  # wade through any residual packets to get the unlink response
            header_data: bytes = USBIPClient.readall(HEADER_BASIC.size, self.socket, timeout=1.0)  # type: ignore[arg-type]
            if not header_data:
                return None
            header: HEADER_BASIC = HEADER_BASIC.new(data=header_data)
            if header.command == BasicCommands.RET_UNLINK:  # unlink command
                unlink_data: bytes = (header_data +
                                      USBIPClient.readall(RET_UNLINK.size - HEADER_BASIC.size, self))  # type: ignore[operator]
                unlink: RET_UNLINK = RET_UNLINK.unpack(unlink_data)
                return unlink
            if header.command == BasicCommands.RET_SUBMIT:  # response for a submit
                self._logger.warning(f"wait_for_unlink() read a RET_SUBMIT {header_data.hex()=}")
                self.wait_for_response(header_data=header_data)
                return None

        raise TimeoutError("timeout waiting for unlink response")

    def _fetch_header(self, header_data: Optional[bytes] = None) -> Optional[HEADER_BASIC]:
        """fetch the header (if required)"""
        if self.endpoint.control is None or self.endpoint.input is None:
            raise USBIPValueError("missing endpoint(s)")

        # get our header data if we don't already have it.
        header_data = self.readall(HEADER_BASIC.size) if header_data is None else header_data  # type: ignore[arg-type]
        if not header_data:
            return None

        return HEADER_BASIC.new(data=header_data)

    def wait_for_response(self, header_data: Optional[bytes] = None) -> bool:
        """wait for response"""
        # we need to check if the command was a CONTROL or INPUT endpoint, which will have
        # an additional set of payload data we need to read in.
        header: Optional[HEADER_BASIC] = self._fetch_header(header_data)
        if header is None or header.command != BasicCommands.RET_SUBMIT:  # this is a return from a submit
            return False  # unrecognized

        # we have a response, check to see if there's any additional data
        expected_size: int = RET_SUBMIT_PREFIX.size - header.size  # type: ignore[arg-type, operator]
        prefix_data: bytes = bytes()
        if expected_size:  # if there's more data, read it in
            prefix_data = self.readall(expected_size)
            if not prefix_data:
                return False  # no additional data, we are done
            prefix_data = header.pack() + prefix_data

        prefix: RET_SUBMIT_PREFIX = RET_SUBMIT_PREFIX.new(data=prefix_data)
        payload: bytes = bytes()

        if prefix.seqnum in self._commands:
            ep: int = self._commands[prefix.seqnum].ep
            if (ep in [self.endpoint.control.number, self.endpoint.input.number] and  # type: ignore[union-attr]
                    self._commands[prefix.seqnum].direction == Direction.USBIP_DIR_IN):
                payload = USBIPClient.readall(prefix.actual_length, self)
            prefix.ep = self._commands[prefix.seqnum].ep  # simplifies correlation with endpoints

        self._responses[prefix.seqnum] = URBResponse(prefix, payload)
        return True

    @property
    def response_sequences(self) -> list[int]:
        """return the sequence #s for responses we have read"""
        if self.endpoint.input is None:
            return []
        return [
            seqnum
            for seqnum, response in self._responses.items()
            if response.prefix.ep == self.endpoint.input.number
        ]

    def response_data(self, timeout: float = PAYLOAD_TIMEOUT, size: int = 0) -> bytes:
        """
        Read device data from the USBIP device
        :param self:
        :type self:
        :param timeout: time in seconds we will wait for the response
        :type timeout: float
        :param size: how many bytes we expect to read, 0 if response terminated
                     by '\r\n' (default delimiter)
        :type size: int
        :return: response from USBIP device
        :rtype: bytes
        """
        # Abstract:
        # ========
        # 1. Read any USBIP packets that have arrived from the device
        #      a) all responses on "queue" indexed by their seqnum & payload
        # 2. aggregate payloads from all USBIP responses
        #      a) remove responses and corresponding commands
        #           i) commands not removed will be "unlinked" when connection terminated
        #      b) once we reach the specified 'size' we are done
        #
        if self.endpoint.input is None:
            raise USBIPValueError("missing input endpoint")

        data: bytes = bytes()
        start_time: float = perf_counter()
        while perf_counter() - start_time < timeout:
            if self.wait_for_response():  # if any responses pending, pull them in
                for seqnum in self.response_sequences:
                    if self._responses[seqnum].payload:
                        data += self._responses[seqnum].payload
                    self._responses.pop(seqnum)
                    self._commands.pop(seqnum)
                    if size and len(data) >= size:
                        return data
                    # if a delimiter is specified, check for it & return what we have
                    if size == 0 and data.endswith(self.delimiter) and self.delimiter:
                        return data

        if data:  # we received a response
            return data

        # further up call stack should add the request packet for diagnostics
        raise USBIPResponseTimeoutError(timeout=timeout, size=size)


class USBIPClient:  # pylint: disable=too-many-public-methods
    """client to connect to usbipd service for devices"""

    # set USBIP protocol high, observed delays long delays before response
    USBIP_TIMEOUT: float = 10.0  # timeout for USBIP protocol overhead (list/attach can run +5 secs)
    READ_BUFFER_SIZE: int = 512  # number of bytes of pending reads to enqueue
    URB_QUEUE_MIN: int = 10
    URB_QUEUE_MAX: int = 50
    SERVER_CONNECT_TIMEOUT: float = 1.0

    def __init__(self, remote: tuple[str, int], command_timeout: float = PAYLOAD_TIMEOUT, socket_class: type = SocketWrapper):
        """establish connection to server for devices"""
        # Note: in docker the host/port will most likely be `host.docker.internal:3420`
        self._host: str = remote[0]
        self._port: int = remote[1]
        self._socket: Optional[SocketWrapper] = None
        self._connections: list[USBIP_Connection] = []  # track our attachments
        self._socket_timeout: Optional[float] = 0.005  # timeout on waiting for a "receive" from the socket (transactions)
        self._command_timeout: float = command_timeout
        self._logger: logging.Logger = LOGGER
        self._socket_class: type = socket_class

    @property
    def command_timeout(self) -> float:
        """return the command timeout (how long we wait for Gener8 responses)"""
        return self._command_timeout

    def disconnect_server(self):
        """disconnect from the usbipd server"""
        if self._socket is not None:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)  # we are done
                self._socket.close()
                self._logger.debug(f"disconnected from {self._host}:{self._port}")
            except OSError:
                pass
            finally:
                self._socket = None

    def connect_server(self) -> None:
        """connect to the remote usbipd server"""
        if self._socket is None:
            try:
                self._socket = self._socket_class(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self.SERVER_CONNECT_TIMEOUT)
                self._socket.connect((self._host, self._port))
                self._socket.settimeout(self._socket_timeout)
                self._logger.debug(f"connected via {self._socket.__class__.__name__} "
                                   f"to {self._host}:{self._port} from {self._socket.getsockname()}")
            except socket.gaierror as gai_error:
                raise USBIPConnectionError(
                    f"connection attempt to {self._host}:{self._port} '{str(gai_error)}'"
                ) from gai_error
            except (socket.timeout, OSError) as timeout_error:
                raise USBIPServerTimeoutError(
                    f"connection attempt to {self._host}:{self._port} timed out "
                    f"after {self.SERVER_CONNECT_TIMEOUT} seconds"
                ) from timeout_error
            finally:
                if self._socket:
                    self._socket.settimeout(self._socket_timeout)  # restore the transaction timeout

    def set_tcp_nodelay(self):
        """set TCP nodelay for the current socket"""
        if self._socket is None:
            raise USBIPValueError("no socket to set options on!")
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    @property
    def usbipd(self) -> SocketWrapper:
        """return the socket connection"""
        self.connect_server()
        if self._socket is None:
            raise USBIPValueError("socket not created!")
        return self._socket

    def _remove_connection(self) -> SocketWrapper:
        """detach the connection"""
        if self._socket is None:
            raise USBIPValueError("no socket to remove")
        socket_connection: SocketWrapper = self._socket
        self._socket = None
        if socket_connection is not None:
            # Connections will be sending lots of small packets, disable Nagle's
            # algorithm so there's no delay, and they are sent immediately to reduce latency
            socket_connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            # Its possible we could be quiet for extended periods of time (say an error)
            # make sure we keep the socket alive otherwise the server will terminate it after 2h11m
            socket_connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        return socket_connection

    def create_connection(self, device: HardwareID, attached: OP_REP_IMPORT) -> USBIP_Connection:
        """create a USBIP device connection for the attached device"""
        conn: USBIP_Connection = USBIP_Connection(busnum=attached.busnum, devnum=attached.devnum,
                                                  device=device, sock=self._remove_connection())
        return conn

    @staticmethod
    def readall(size: int, usb: USBIP_Connection | SocketWrapper, timeout: float = PAYLOAD_TIMEOUT) -> bytes:
        """read all the expected data from the socket"""
        sock: SocketWrapper | None = usb.socket if isinstance(usb, USBIP_Connection) else usb
        if sock is None:
            raise USBIPValueError("no socket to read!")
        try:
            data: bytes = bytes()
            start: float = perf_counter()
            while size > 0:
                try:
                    just_read: bytes = sock.recv(size)
                    if not just_read:  # nothing left in socket
                        return data
                    data += just_read
                    size -= len(just_read)
                except TimeoutError as timeout_error:
                    if perf_counter() - start > timeout:
                        LOGGER.debug(f"Timeout Error, {size=}, {timeout=}, {data.hex()=}")
                        raise timeout_error
            return data
        except ConnectionError as connection_error:
            raise USBConnectionLostError(detail="connection error", connection=usb) from connection_error
        except OSError as os_error:
            if isinstance(os_error, TimeoutError):
                raise USBIPResponseTimeoutError(size=size, timeout=timeout) from os_error
            raise USBConnectionLostError(detail=f"connection lost [{os_error.errno=}, {str(os_error)}",
                                         connection=usb) from os_error

    def list_published(self) -> OP_REP_DEVLIST_HEADER:
        """get list of remote devices"""
        self.connect_server()  # ensure we are connected to the USBIPD server
        request: bytes = OP_REQ_DEVLIST().packet()
        self.usbipd.sendall(request)
        data: bytes = self.readall(OP_REP_DEVLIST_HEADER.size, self.usbipd)  # type: ignore[arg-type]
        response_header: OP_REP_DEVLIST_HEADER = OP_REP_DEVLIST_HEADER.new(data=data)
        for _ in range(0, response_header.num_exported_devices):
            # read a device path
            data = self.readall(OP_REP_DEV_PATH.size, self.usbipd)  # type: ignore[arg-type]
            device_path: OP_REP_DEV_PATH = OP_REP_DEV_PATH.new(data=data)
            response_header.paths.append(device_path)
            for _ in range(0, device_path.bNumInterfaces):
                # read an interface associated with the device
                interface_data: bytes = self.readall(OP_REP_DEV_INTERFACE.size, self.usbipd)  # type: ignore[arg-type]
                interface: OP_REP_DEV_INTERFACE = OP_REP_DEV_INTERFACE.new(data=interface_data)
                device_path.interfaces.append(interface)
        return response_header

    def import_device(self, busid: bytes) -> OP_REP_IMPORT:
        """import the specified device"""
        request: bytes = OP_REQ_IMPORT(busid=busid).packet()
        if self.usbipd is None:
            raise USBIPValueError("no usbipd server connection")
        self.set_tcp_nodelay()

        self.usbipd.sendall(request)
        data: bytes = self.readall(CommonHeader.size, self.usbipd, timeout=self.USBIP_TIMEOUT)  # type: ignore[arg-type]
        base_response: CommonHeader = CommonHeader.new(data=data)
        if base_response.status != Status.SUCCESS:
            raise USBAttachError("Error attaching to device", an_errno=base_response.status)

        more_data: bytes = bytes()
        start_time: float = time()
        while not more_data and time() - start_time < 1.0:
            more_data += self.readall(OP_REP_IMPORT.size - CommonHeader.size, self.usbipd)  # type: ignore[arg-type, operator]

        self._logger.debug(f"OP_REP_IMPORT: {data.hex()}{more_data.hex()}")
        return OP_REP_IMPORT.unpack(data + more_data)

    def send_setup(self, setup: UrbSetupPacket, usb: USBIP_Connection, data: Optional[bytes] = None) -> None:
        """send command to the device"""
        usb.seqnum += 1
        command: CMD_SUBMIT = CMD_SUBMIT(
            seqnum=usb.seqnum,
            devid=usb.devid,
            start_frame=0,
            ep=usb.control.number,
            number_of_packets=0,
            transfer_flags=(
                URBTransferFlags.URB_DIR_IN
                if setup.direction == Direction.USBIP_DIR_IN
                else 0x0
            ),
            transfer_buffer_length=len(data) if data else setup.length,
            interval=0,
            setup=setup.packet(),
            direction=setup.direction,
            transfer_buffer=data if data else bytes(),
        )
        command_data: bytes = command.pack()
        usb.sendall(command_data)
        command_hex_data: str = command_data.hex() if command_data else 'None'
        self._logger.debug(f"send_setup(): {str(setup)}\ncommand_data.hex()={command_hex_data}")

    def request_descriptor(self, setup: UrbSetupPacket, usb: USBIP_Connection) -> (
            DeviceDescriptor | ConfigurationDescriptor | StringDescriptor):
        """request a descriptor"""
        self.send_setup(setup=setup, usb=usb)
        prefix_data: bytes = self.readall(RET_SUBMIT_PREFIX.size, usb, timeout=3.0)  # type: ignore[arg-type]
        self._logger.debug(f"{len(prefix_data)=}, {prefix_data.hex()=}")
        if not prefix_data:
            raise USBConnectionLostError("connection lost while fetching URB descriptor", connection=usb)
        prefix: RET_SUBMIT_PREFIX = RET_SUBMIT_PREFIX.unpack(prefix_data)
        if prefix.status != 0:
            raise USBIPValueError(f"request_descriptor failure! {prefix.status=}, errno='{os.strerror(abs(prefix.status))}'")
        try:
            generic_handler: GenericDescriptor = GenericDescriptor()
            data: bytes = self.readall(prefix.actual_length, usb)
            self._logger.debug(f"{prefix.actual_length=}, {data.hex()=}")
            descriptor = generic_handler.packet(data=data)
            return descriptor
        except Exception as descriptor_error:
            self._logger.error(f"GenericDescriptor() error! {prefix.actual_length=}, {str(descriptor_error)}")
            raise

    def set_line_coding(self, setup: UrbSetupPacket, data: bytes, usb: USBIP_Connection) -> None:
        """set line coding"""
        self.send_setup(setup=setup, usb=usb, data=data)
        prefix_data: bytes = self.readall(RET_SUBMIT_PREFIX.size, usb)  # type: ignore[arg-type]
        prefix: RET_SUBMIT_PREFIX = RET_SUBMIT_PREFIX.new(data=prefix_data)
        if prefix.status != 0:
            raise USBIPValueError(f"set_line_coding failure! {prefix.status=}, errno='{os.strerror(abs(prefix.status))}'")

    def set_line_control_state(self, usb: USBIP_Connection) -> None:
        """set the line control state (DCE/DTE)"""
        setup: UrbSetupPacket = UrbSetupPacket(request_type=URBSetupRequestType.HOST_TO_DEVICE.value
                                                            | URBSetupRequestType.TYPE_CLASS.value
                                                            | URBSetupRequestType.RECIPIENT_INTERFACE.value,
                                               request=URBCDCRequestType.SET_CONTROL_LINE_STATE,
                                               value=(CDCControl.USB_CDC_CTRL_RTS | CDCControl.USB_CDC_CTRL_DTR) << 8,
                                               index=0,
                                               length=0,
                                               )
        self.send_setup(setup=setup, usb=usb)
        prefix_data: bytes = self.readall(RET_SUBMIT_PREFIX.size, usb)  # type: ignore[arg-type]
        prefix: RET_SUBMIT_PREFIX = RET_SUBMIT_PREFIX.unpack(prefix_data)
        if prefix.status != 0:
            raise USBIPValueError(f"set_line_control_state failure! {prefix.status=}, errno='{os.strerror(abs(prefix.status))}'")

    def set_configuration(self, setup: UrbSetupPacket, usb: USBIP_Connection) -> None:
        """set the configuration"""
        self.send_setup(setup=setup, usb=usb)
        prefix_data: bytes = bytes()
        try:
            prefix_data = self.readall(RET_SUBMIT_PREFIX.size, usb)  # type: ignore[arg-type]
            prefix: RET_SUBMIT_PREFIX = RET_SUBMIT_PREFIX.new(data=prefix_data)
            if prefix.status != 0:
                raise USBIPValueError(f"set_descriptor failure! {prefix.status=}, errno='{os.strerror(abs(prefix.status))}'")
        except struct.error as s_error:
            self._logger.error(f"RET_SUBMIT_PREFIX failure on {RET_SUBMIT_PREFIX.size=}, {prefix_data.hex()=}")
            raise s_error

    def setup(self, usb: USBIP_Connection):
        """after we attach to the device, we need to issue some setup"""
        # Send data to the remote USB serial device
        # After we are "attached" we need to interrogate the USB device for its characteristics.
        #
        # 1. USBIP_CMD_SUBMIT(GetDescriptor(type=Device))
        #
        # 2. USBIP_CMD_SUBMIT(GetDescriptor(type=Configuration))
        #     a) ask for the configuration descriptor, request 9 bytes, that will
        #        provide us with the ConfigurationDescriptor from which we can get the
        #        total size.
        #
        # 3. USBIP_CMD_SUBMIT(GetDescriptor(type=Configuration))
        #      a) Now ask for *all* the data and parse out all the
        #         Interfaces/Endpoints/Descriptors
        #
        # 4. USBIP_CMD_SUBMIT(GetDescriptor(type=String))
        #      a) get the string descriptor for completeness
        #
        # 5. USBIP_CMD_SUBMIT(SetConfiguration(value=0x1))
        #      a) enable the usb device
        #
        # 6. USBIP_CMD_SUBMIT(SetLineCoding())
        #      a) setup: 21 20 0000 0000 0700
        #            21 - bmRequestType
        #             0.... ... - device -> host
        #             .01.. ... - Type: Class (0x1)
        #             ...0 0001 - Recipient: Interface (0x01)
        #            20 - RequestType SET_LINE_CODING
        #            0000 - value
        #            0000 - index
        #            0700 - length
        #
        # 7. USBIP_CMD_SUBMIT(SetControlLineState())
        #      a) setup: 21 22 0300 0000 0000
        #            21 - bmRequestType
        #             0.... ... - device -> host
        #             .01.. ... - Type: Class (0x1)
        #             ...0 0001 - Recipient: Interface (0x01)
        #            22 - RequestType SET_LINE_CONTROL_STATE
        #            0003 - value
        #            0000 - index
        #            0700 - length
        setup: UrbSetupPacket = UrbSetupPacket(
            request_type=URBSetupRequestType.DEVICE_TO_HOST.value,
            request=URBStandardDeviceRequest.GET_DESCRIPTOR.value,
            value=DescriptorType.DEVICE_DESCRIPTOR.value << 8,
            length=DeviceDescriptor.size,  # type: ignore[arg-type]
        )
        usb.device_desc = self.request_descriptor(setup=setup, usb=usb)

        # Get the configuration descriptor to find out how many other descriptors we need to read
        setup = UrbSetupPacket(
            request_type=URBSetupRequestType.DEVICE_TO_HOST.value,
            request=URBStandardDeviceRequest.GET_DESCRIPTOR.value,
            value=DescriptorType.CONFIGURATION_DESCRIPTOR.value << 8,
            length=ConfigurationDescriptor.size,  # type: ignore[arg-type]
        )
        config_desc: ConfigurationDescriptor = self.request_descriptor(setup=setup, usb=usb)

        # now that we know the Configuration Descriptor's total length, read it all in:
        #   Configuration Descriptor
        #       - associations
        #       - interfaces
        #           - endpoints, descriptors
        #
        setup = UrbSetupPacket(
            request_type=URBSetupRequestType.DEVICE_TO_HOST.value,
            request=URBStandardDeviceRequest.GET_DESCRIPTOR.value,
            value=DescriptorType.CONFIGURATION_DESCRIPTOR.value << 8,
            length=config_desc.wTotalLength,
        )
        usb.configuration = self.request_descriptor(setup=setup, usb=usb)

        # Now for the string descriptor
        setup = UrbSetupPacket(
            request_type=URBSetupRequestType.DEVICE_TO_HOST.value,
            request=URBStandardDeviceRequest.GET_DESCRIPTOR.value,
            value=DescriptorType.STRING_DESCRIPTOR.value << 8,
            index=0,
            length=0xFF,
        )
        self.request_descriptor(setup=setup, usb=usb)  # StringDesc (not used)

        # "enable" the USB device
        # bytes: '0009010000000000'
        setup = UrbSetupPacket(
            request_type=URBSetupRequestType.HOST_TO_DEVICE.value,
            request=URBStandardDeviceRequest.SET_CONFIGURATION.value,
            value=config_desc.bConfigurationValue,
            index=0,
            length=0x0,
        )
        self.set_configuration(setup=setup, usb=usb)

        line_coding_data: bytes = struct.pack("<IBBB", 9600, 0, 0, 8)
        setup = UrbSetupPacket(
            request_type=URBSetupRequestType.HOST_TO_DEVICE.value
            | URBSetupRequestType.TYPE_CLASS.value
            | URBSetupRequestType.RECIPIENT_INTERFACE.value,
            request=URBCDCRequestType.SET_LINE_CODING.value,
            value=0x0000,
            index=0,
            length=len(line_coding_data),
        )
        self.set_line_coding(setup=setup, data=line_coding_data, usb=usb)
        self.set_line_control_state(usb=usb)

    def attach(self, devices: list[HardwareID], published: Optional[OP_REP_DEVLIST_HEADER] = None) -> None:
        """attach to all instances specified devices"""
        # find the 'busid' for devices we want to attach to
        self.disconnect_server()  # ensure we start with a clean connection
        if published is None:
            published = self.list_published()  # get the list of devices
        self.disconnect_server()  # disconnect the socket
        self._logger.debug("found %s paths published", len(published.paths))
        found: list[HardwareID] = []
        for device in devices:
            for path in published.paths:
                if path.idVendor == device.vid and path.idProduct == device.pid:
                    # attach to this device, the socket connection needs to go with it
                    try:
                        busid: str = path.busid.decode("utf-8").rstrip("\x00")
                        self._logger.debug(f"attaching to {device.vid=:04x}/{device.pid=:04x} at {busid=}")
                        response: OP_REP_IMPORT = self.import_device(busid=path.busid)
                        self._connections.append(self.create_connection(device, response))
                        self.setup(usb=self._connections[-1])  # get configuration & all that
                        found.append(device)
                    except (ValueError, USBConnectionLostError) as attach_error:
                        raise USBIPValueError(
                            f"Attach error for vid:0x{device.vid:04x}, pid:0x{device.pid:04x}, "
                            f"busid={path.busnum}-{path.devnum} @{self._host}:{self._port}"
                        ) from attach_error
        not_found: list[HardwareID] = [item for item in devices if item not in found]
        if not found:
            raise USBIPValueError(f"Devices not found: {not_found=}")

    def get_connection(self, device: HardwareID) -> list[USBIP_Connection]:
        """get the connection we'll need for reading/writing the remote usb port"""
        # there could be multiple devices with the same vid/pid, return all of them, the
        # caller will need to figure out which one they are interested in
        return [item for item in self._connections if item.device == device]

    def queue_urbs(self, usb: USBIP_Connection):
        """queue up URBs"""
        # make sure the input endpoint has pending read commands to accommodate any
        # response data generated by this command
        if usb.pending_reads < self.URB_QUEUE_MIN:
            for _ in range(usb.pending_reads, self.URB_QUEUE_MAX):
                self.read(usb, size=0x1000)  # max expected data

    def send(self, usb: USBIP_Connection, data: bytes | str) -> int:
        """send data to the underlying device"""
        # Use the "OUT" endpoint (host -> device)

        # make sure the input endpoint has pending read commands to accommodate
        # any response data generated by this command
        self.queue_urbs(usb)

        if isinstance(data, str):
            data = data.encode("utf-8")

        # Send data to the remote USB serial device
        usb.seqnum += 1
        command: CMD_SUBMIT = CMD_SUBMIT(
            seqnum=usb.seqnum,
            devid=usb.devid,
            start_frame=0,
            ep=usb.output.number,  # host -> device
            transfer_flags=URBTransferFlags.URB_DIR_OUT,
            transfer_buffer_length=len(data),
            interval=0,
            direction=Direction.USBIP_DIR_OUT,
            transfer_buffer=data,
        )
        return usb.send_command(command)

    @staticmethod
    def read(usb: USBIP_Connection, size: int) -> None:
        """read up to the specified # of bytes from the serial device"""
        usb.seqnum += 1
        command: CMD_SUBMIT = CMD_SUBMIT(seqnum=usb.seqnum,
                                         devid=usb.devid,
                                         start_frame=0,
                                         ep=usb.input.number,  # device -> host
                                         transfer_flags=0,
                                         transfer_buffer_length=size,
                                         interval=0,
                                         direction=Direction.USBIP_DIR_IN,
                                         )
        usb.send_command(command)

    @staticmethod
    def readline(usb: USBIP_Connection) -> str:
        """
        read until a linefeed is encountered, which presumes the data can
        be represented as a string
        """
        response: bytearray = bytearray()
        timeout: float = 0.250  # 250ms
        start_time: float = perf_counter()
        while perf_counter() - start_time < timeout:
            try:
                packet: bytes = usb.response_data(size=0)  # reads until delimiter
                if packet:
                    response.extend(packet)
                    if usb.delimiter in packet:
                        break
            except TimeoutError:
                return ""
        return response.decode("utf-8").strip(usb.delimiter.decode("utf-8"))

    def shutdown_connection(self, usb: USBIP_Connection) -> None:
        """shutdown this connection"""
        # Any commands that are "pending", we need to unlink them
        if usb.pending_commands:
            self._logger.debug(f"unlink for {len(usb.pending_commands)} commands")

        for submit in usb.pending_commands:
            usb.seqnum += 1
            unlink: CMD_UNLINK = CMD_UNLINK(seqnum=usb.seqnum, devid=submit.devid, direction=submit.direction,
                                            ep=submit.ep, unlink_seqnum=submit.seqnum)
            usb.send_unlink(unlink)  # waits for response

        # we are all done, shutdown the socket connection
        if usb.socket:
            usb.socket.shutdown(socket.SHUT_RDWR)  # tell the server we are done
            usb.socket.close()
            usb.socket = None

    def shutdown(self):
        """shutdown all connections"""
        self.disconnect_server()  # cleanup any outstanding connections
        for connection in self._connections:
            self.shutdown_connection(connection)

    def is_device(self, usb: USBIP_Connection, path: OP_REP_DEV_PATH) -> bool:
        """
        Determine if the lost USB connection is in the USBIPD server's published list of
        devices (paths).
        :param usb: usb connection that was "lost"
        :type usb: USBIP device connection context
        :param path: list of USB devices published by the USBIPD server
        :type path:
        :return: =True, lost connection "found" in current path, =False, try another path
        :rtype: bool
        """
        # The connection to the usb device has been lost. Check the path to see if this
        # matches the usb device we are looking to restore

        if usb.device is None:
            raise USBIPValueError("no device specified in connection")

        for current_connection in self._connections:
            if current_connection.busnum == usb.busnum and current_connection.devnum == usb.devnum:
                continue
            if current_connection.busnum == path.busnum and current_connection.devnum == path.devnum:
                return False  # path matches an existing connection

        # if this path is not in use, and it matches our product, then we should connect to it
        return usb.device.vid == path.idVendor and usb.device.pid == path.idProduct

    def restore_connection(self, lost_usb: USBIP_Connection) -> Optional[USBIP_Connection]:
        """A USB connection has been lost, attempt to restore it"""
        # get the list of published devices from the USBIPD server
        if lost_usb is None or lost_usb.device is None:
            raise USBIPValueError("no connection to restore")

        self._logger.debug("restoring connection")
        if lost_usb in self._connections:
            self._connections.remove(lost_usb)

        published: OP_REP_DEVLIST_HEADER = self.list_published()
        self.disconnect_server()  # disconnect the socket
        for path in published.paths:
            if self.is_device(usb=lost_usb, path=path):  # device has returned! we can re-establish a link to it
                try:
                    response: OP_REP_IMPORT = self.import_device(busid=path.busid)
                    usb: USBIP_Connection = self.create_connection(lost_usb.device, response)
                    self.setup(usb=usb)  # get configuration & all that
                    return usb
                except USBAttachError as device_error:
                    if device_error.errno in USBConnectionLostError.USB_DISCONNECT:
                        self._logger.warning("device error on re-attachment, try again...")
                        self.disconnect_server()  # don't re-use this connection
                    return None
                except ValueError as attach_error:
                    raise USBIPValueError(
                        f"Attach error for vid:0x{lost_usb.device.vid:04x}, pid:0x{lost_usb.device.pid:04x}, "
                        f"busid={path.busnum}-{path.devnum} @{self._host}:{self._port}"
                    ) from attach_error
        self._logger.warning(f"timed out restoring connection {lost_usb.devid:04x}")
        return None
