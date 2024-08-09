"""mock USBIP server"""

import os
import errno
import json
import platform
import re
import socket
from threading import Thread, Event
from time import time, sleep
from typing import Optional, Any, cast
from enum import EnumType
import glob
import traceback
from pathlib import Path
import logging
import struct

from serial_usbipclient.protocol.usbip_defs import BasicCommands, Direction
from serial_usbipclient.protocol.usb_descriptors import DescriptorType
from serial_usbipclient.protocol.packets import (CommonHeader, OP_REP_DEVLIST_HEADER, OP_REQ_IMPORT, OP_REP_DEV_PATH, OP_REP_IMPORT,
                              HEADER_BASIC, CMD_SUBMIT, CMD_SUBMIT_PREFIX, USBIP_RET_SUBMIT, OP_REP_DEV_INTERFACE, CMD_UNLINK, RET_UNLINK)
from serial_usbipclient.protocol.urb_packets import (UrbSetupPacket, DeviceDescriptor, ConfigurationDescriptor,
                                  URBBase, InterfaceDescriptor, InterfaceAssociation, EndPointDescriptor, HeaderFunctionalDescriptor,
                                  CallManagementFunctionalDescriptor, ACMFunctionalDescriptor, UnionFunctionalDescriptor, StringDescriptor,
                                  URBStandardDeviceRequest, URBCDCRequestType)


logger = logging.getLogger(__name__)


class MockDevice:
    """URB information for a device"""
    def __init__(self, vendor: int, product: int, device: DeviceDescriptor, busnum: int, devnum: int) -> None:
        """setup our instance"""
        self.vendor: int = vendor
        self.product: int = product
        self.busid: bytes = f"{busnum}-{devnum}".encode('utf-8')
        self.busid += b'\0' * (32 - len(self.busid))
        self.device: Optional[DeviceDescriptor] = device
        self.queued_reads: dict[int, CMD_SUBMIT] = {}  # key'd by the sequence # for easy access
        self._attached: bool = False

    def enqueue_read(self, command: CMD_SUBMIT) -> None:
        """enqueue the read command"""
        self.queued_reads[command.seqnum] = command

    def dequeue_read(self, seq: int) -> CMD_SUBMIT:
        """remove the queued read from the queue"""
        if not seq:
            return self.queued_reads.popitem()[1]

        if seq in self.queued_reads:
            cmd_submit: CMD_SUBMIT = self.queued_reads.pop(seq)
            return cmd_submit
        else:
            logger.error(f"{seq=} not in queue! {self.queued_reads=}")

    @property
    def is_attached(self) -> bool:
        """=True, then device is attached"""
        return self._attached

    @property
    def attach(self) -> bool:
        """attach device =True"""
        previous_state: bool = self._attached
        self._attached = True
        return previous_state

    @property
    def detach(self) -> bool:
        """detach device"""
        previous_state: bool = self._attached
        self._attached = False
        return previous_state

    @property
    def busnum(self) -> int:
        """extract the bus number from the busid"""
        busid: str = "".join([chr(item) for item in self.busid if item])
        return int(busid.split('-')[0])

    @property
    def devnum(self) -> int:
        """extract the bus number from the busid"""
        busid: str = "".join([chr(item) for item in self.busid if item])
        return int(busid.split('-')[1])

    def __hash__(self):
        """return the hash of this device"""
        return hash((self.vendor, self.product))

    def __str__(self):
        """display readable version"""
        return f"{self.busnum}-{self.devnum} VID/PID={self.vendor:0x4}:{self.product:0x4}"


class Parse_lsusb:
    """parse the output of a lsusb command to get a USB device configuration"""
    def __init__(self, logger: logging.Logger):
        """parse the data"""
        self.logger = logger
        self.root: str = os.path.join(os.path.dirname(__file__), '*.lsusb')
        self.devices: list[MockDevice] = []
        for file_path in glob.glob(self.root):
            self.file_path: str = file_path
            basename: str = Path(file_path).stem
            parts: list[str] = basename.split('-')
            busnum: int = int(parts[0])
            devnum: int = int(parts[1])
            device_descriptor: DeviceDescriptor = DeviceDescriptor()
            usb_configuration: list[str] = self.read_file(self.file_path)
            for offset in range(len(usb_configuration)):
                if usb_configuration[offset].startswith('Device Descriptor:'):
                    self.parse_descriptor(usb_configuration, offset, urb=device_descriptor)
                    self.devices.append(MockDevice(device_descriptor.idVendor, device_descriptor.idProduct,
                                                   device=device_descriptor, busnum=busnum, devnum=devnum))
                    break

    @staticmethod
    def read_file(file_path: str) -> list[str]:
        """read in the entire file"""
        usb_config_lines: list[str] = []
        with open(file_path, "r") as usb:
            while line := usb.readline():
                usb_config_lines.append(line.strip())  # remove leading & trailing whitespace
            return usb_config_lines

    @staticmethod
    def from_hex(hex_value: str) -> int:
        """convert hex to integer"""
        return int(hex_value[2:], 16)  # return as an integer

    @staticmethod
    def to_bcd(bcd_value: str) -> int:
        """convert a string to BCD int"""
        # 2.00 -> 0x0200
        hex_value: str = bcd_value.replace('.', '')  # now it's a hex string
        return int(hex_value, 16)  # return as an integer

    def set_attribute(self, urb: URBBase, name: str, value: str):
        """set the attribute to the structure"""
        if name == 'bMaxPacketSize0':  # indicates max packet size for default endpoint
            name = 'bMaxPacketSize'

        if name == 'MaxPower':
            name = 'bMaxPower'
            value = value.replace('mA', '')

        for field in urb.fields():
            if field[0].name == name:
                if '.' in value:  # encoded, BCD
                    value = self.to_bcd(bcd_value=value)
                elif value.startswith('0x'):
                    value = self.from_hex(value)

                if type(field[0].type) == EnumType:
                    value = int(value)
                typed_value = field[0].type(value)
                urb.__setattr__(name, typed_value)
                return
        raise NotImplementedError(f"{name=} was not found on {urb.__class__.__name__}")

    def parse_descriptor(self, usb: list[str], offset: int, urb: URBBase) -> int:
        """parse the device descriptor data"""
        end_offset: int = len(usb) - 1
        while offset < end_offset:
            offset += 1
            section: str = usb[offset]
            if not section.endswith(':'):
                parts: list[str] = re.split(r'\s+', section)
                attribute_name: str = parts[0]
                attribute_value: str = parts[1]
                if attribute_name not in ['Self', 'line', 'Transfer', 'Synch', 'Usage'] and attribute_value not in ['Powered', 'coding', 'Type']:
                    self.set_attribute(urb, attribute_name, attribute_value)
            else:
                if section == 'Configuration Descriptor:':
                    device_desc: DeviceDescriptor = cast(DeviceDescriptor, urb)
                    device_desc.configurations.append(ConfigurationDescriptor())
                    offset = self.parse_descriptor(usb, offset, device_desc.configurations[-1])
                    configuration_response: bytes = device_desc.configurations[-1].pack()
                    for association in device_desc.configurations[-1].associations:
                        configuration_response += association.pack()
                    for interface in device_desc.configurations[-1].interfaces:
                        configuration_response += interface.pack()
                        for descriptor in interface.descriptors:
                            configuration_response += descriptor.pack()
                    if len(configuration_response) != device_desc.configurations[-1].wTotalLength:
                        self.logger.error(f"Parsing lsusb output, mismatch for configuration size "
                                         f"{device_desc.configurations[-1].wTotalLength=} != {len(configuration_response)}")

                elif section == 'Interface Association:':
                    if not isinstance(urb, ConfigurationDescriptor):
                        return offset - 1
                    config_descriptor: ConfigurationDescriptor = cast(ConfigurationDescriptor, urb)
                    config_descriptor.associations.append(InterfaceAssociation())
                    offset = self.parse_descriptor(usb, offset, config_descriptor.associations[-1])
                elif section == 'Interface Descriptor:':
                    if not isinstance(urb, ConfigurationDescriptor):
                        return offset - 1
                    config_descriptor: ConfigurationDescriptor = cast(ConfigurationDescriptor, urb)
                    config_descriptor.interfaces.append(InterfaceDescriptor())
                    offset = self.parse_descriptor(usb, offset, config_descriptor.interfaces[-1])
                elif section == "Endpoint Descriptor:":
                    if not isinstance(urb, InterfaceDescriptor):
                        return offset - 1
                    if_descriptor: InterfaceDescriptor = cast(InterfaceDescriptor, urb)
                    if_descriptor.descriptors.append(EndPointDescriptor())
                    offset = self.parse_descriptor(usb, offset, if_descriptor.descriptors[-1])
                elif section == 'CDC Header:':
                    if not isinstance(urb, InterfaceDescriptor):
                        return offset - 1
                    if_descriptor: InterfaceDescriptor = cast(InterfaceDescriptor, urb)
                    if_descriptor.descriptors.append(HeaderFunctionalDescriptor())
                    offset = self.parse_descriptor(usb, offset, if_descriptor.descriptors[-1])
                elif section == 'CDC Call Management:':
                    if not isinstance(urb, InterfaceDescriptor):
                        return offset - 1
                    if_descriptor: InterfaceDescriptor = cast(InterfaceDescriptor, urb)
                    if_descriptor.descriptors.append(CallManagementFunctionalDescriptor())
                    offset = self.parse_descriptor(usb, offset, if_descriptor.descriptors[-1])
                elif section == 'CDC ACM:':
                    if not isinstance(urb, InterfaceDescriptor):
                        return offset - 1
                    if_descriptor: InterfaceDescriptor = cast(InterfaceDescriptor, urb)
                    if_descriptor.descriptors.append(ACMFunctionalDescriptor())
                    offset = self.parse_descriptor(usb, offset, if_descriptor.descriptors[-1])
                elif section == 'CDC Union:':
                    if not isinstance(urb, InterfaceDescriptor):
                        return offset - 1
                    if_descriptor: InterfaceDescriptor = cast(InterfaceDescriptor, urb)
                    if_descriptor.descriptors.append(UnionFunctionalDescriptor())
                    offset = self.parse_descriptor(usb, offset, if_descriptor.descriptors[-1])

        return offset


class MockUSBDevice:
    """wrapper for devices we'll be mocking"""
    def __init__(self, devices: list[MockDevice]):
        """set up the devices we'll be mocking"""
        self.devices: list[MockDevice] = devices
        self.usbip: Optional[OP_REP_DEVLIST_HEADER] = None

    def device(self, busnum: int, devnum: int) -> Optional[MockDevice]:
        """retrieve the USB device associated with this devid"""
        for device in self.devices:
            if device.busnum == busnum and device.devnum == devnum:
                return device
        return None

    def setup(self):
        """create the USBIP device list"""
        usbip_dev_header: OP_REP_DEVLIST_HEADER = OP_REP_DEVLIST_HEADER()
        usbip_dev_header.num_exported_devices = len(self.devices)

        for usb in self.devices:
            root_dev_path: bytes = f"/sys/devices/pci0000.0/0000:00.1d1/usb2/{usb.busnum}-{usb.devnum}".encode('utf-8')
            dev_path: bytes = root_dev_path + (b'\0' * (256 - len(root_dev_path)))
            path: OP_REP_DEV_PATH = OP_REP_DEV_PATH(busid=usb.busid, path=dev_path, busnum=usb.busnum, devnum=usb.devnum,
                                                    idVendor=usb.vendor, idProduct=usb.product,
                                                    bcdDevice=usb.device.bcdDevice, bDeviceClass=usb.device.bDeviceClass,
                                                    bDeviceSubClass=usb.device.bDeviceSubClass, bDeviceProtocol=usb.device.bDeviceProtocol,
                                                    bConfigurationValue=0x0, bNumConfigurations=len(usb.device.configurations),
                                                    bNumInterfaces=sum([len(item.interfaces) for item in usb.device.configurations]),
                                                    )
            usbip_dev_header.paths.append(path)
            for configuration in usb.device.configurations:
                for interface in configuration.interfaces:
                    usbip_interface: OP_REP_DEV_INTERFACE = OP_REP_DEV_INTERFACE(bInterfaceClass=interface.bInterfaceClass,
                                                                                 bInterfaceSubClass=interface.bInterfaceSubClass,
                                                                                 bInterfaceProtocol=interface.bInterfaceProtocol)
                    path.interfaces.append(usbip_interface)

        self.usbip = usbip_dev_header

    def pack(self) -> bytes:  # create the byte representation of the data
        """walk the USBIP representation and create the byte stream"""
        response: bytes = self.usbip.pack()
        for path in self.usbip.paths:
            response += path.pack()
            for interface in path.interfaces:
                response += interface.pack()
        return response


class MockUSBIP:
    """mock USBIP server"""
    def __init__(self, host: str, port: int, logger: logging.Logger):
        """set up our instance"""
        self.host: str = host
        self.port: int = port
        self.logger: logging.Logger = logger
        self.server_socket: socket.socket | None = None
        self.thread: Thread = Thread(name=f'mock-usbip@{self.host}:{self.port}', target=self.run, daemon=True)
        self.event: Event = Event()
        self._is_windows: bool = platform.system() == 'Windows'
        self._protocol_responses: dict[str, list[str]] = {}
        self._urb_traffic: Optional[bytes] = None
        self.urb_queue: dict[int, Any] = {}  # pending read URBs, queued by seq #
        self.usb_devices: Optional[MockUSBDevice] = None
        self.setup()
        if self.host and self.port:
            self.event.clear()
            self.thread.start()
            start_time: float = time()
            while time() - start_time < 5.0:
                if self.event.is_set():
                    return
                sleep(0.010)  # allow thread time to start

            raise TimeoutError(f"Timed out waiting for USBIP server @{self.host}:{self.port} to start, waited {round(time() - start_time, 2)} seconds")
        else:
            logger.info("[usbip-server] MockUSBIP server not started")

    def setup(self):
        """setup our instance"""
        data_path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'usbip_packets.json')
        with open(file=data_path, mode='r') as recording:
            self._protocol_responses = json.loads(recording.read())

        parser: Parse_lsusb = Parse_lsusb(logger=self.logger)
        self.usb_devices = MockUSBDevice(parser.devices)
        self.usb_devices.setup()  # now we have binary for the USB devices we can emulate

    def shutdown(self):
        """shutdown the USBIP server thread"""
        if self.thread and self.event.is_set():
            self.logger.info("[usbip-server] clear event, wait for thread to recognize exit condition")
            self.event.clear()  # -> 0, thread will exit loop if we aren't blocking on accept()
            if self.server_socket:
                if not self._is_windows:  # in linux-land, need to shut down as well
                    self.server_socket.shutdown(socket.SHUT_RDWR)
                self.server_socket.close()  # if we are waiting for accept(), should unblock

            self.logger.info("[usbip-server] waiting for event to signal (0->1)")
            if self.event.wait(timeout=10.0):
                self.thread.join(timeout=1.0)
                self.thread = None
                return
            raise TimeoutError(f"Timed out waiting for USBIP server to acknowledge shutdown {self.event.is_set()=}")

    def unlink(self, message: bytes) -> bytes:
        """unlink the specified read"""
        cmd_unlink: CMD_UNLINK = CMD_UNLINK.unpack(message)
        busnum, devnum = cmd_unlink.devid >> 16, cmd_unlink.devid & 0xFFFF
        usb: MockDevice = self.usb_devices.device(busnum, devnum)
        unlinked_command: CMD_SUBMIT = usb.dequeue_read(seq=cmd_unlink.unlink_seqnum)
        status: int = ~errno.ECONNRESET if not unlinked_command else 0
        ret_unlink: RET_UNLINK = RET_UNLINK(status=status, seqnum=cmd_unlink.seqnum, devid=cmd_unlink.devid)
        self.logger.info(f"[usbip-server] unlink #{cmd_unlink.unlink_seqnum} for {busnum}-{devnum}")
        return ret_unlink.pack()

    def mock_urb_responses(self, message: bytes, busid: bytes) -> bytes:
        """return URB packets"""
        urb_header: HEADER_BASIC = HEADER_BASIC.unpack(message)
        if urb_header.command == BasicCommands.CMD_UNLINK:  # de-queue a read request
            return self.unlink(message)

        if urb_header.command == BasicCommands.CMD_SUBMIT:
            cmd_submit: CMD_SUBMIT = CMD_SUBMIT.unpack(message)
            if cmd_submit.ep and cmd_submit.direction == Direction.USBIP_DIR_IN:  # a read is being issued
                busnum, devnum = cmd_submit.devid >> 16, cmd_submit.devid & 0xFFFF
                usb: MockDevice = self.usb_devices.device(busnum, devnum)
                usb.enqueue_read(cmd_submit)  # associate this read with the device it's intended
                self.logger.info(f"[usbip-server] queued read #{cmd_submit.seqnum} for {busnum}-{devnum} ({len(usb.queued_reads)} in queue)")
                return bytes()  # there is no response (yet!)
            if cmd_submit.ep and cmd_submit.direction == Direction.USBIP_DIR_OUT:  # write to the device
                busnum, devnum = cmd_submit.devid >> 16, cmd_submit.devid & 0xFFFF
                usb: MockDevice = self.usb_devices.device(busnum, devnum)
                self.logger.info(f"[usbip-server] device write #{cmd_submit.seqnum} for {busnum}-{devnum} ({len(usb.queued_reads)} in queue)")
                ret_submit = USBIP_RET_SUBMIT(status=0, seqnum=cmd_submit.seqnum, transfer_buffer=bytes())
                response: bytes = ret_submit.pack()
                queued_read: CMD_SUBMIT = usb.dequeue_read(seq=0)  # get the first one available
                ret_submit = USBIP_RET_SUBMIT(status=0, seqnum=queued_read.seqnum, transfer_buffer=cmd_submit.transfer_buffer)
                self.logger.info(f"[usbip-server] ")
                return response + ret_submit.pack()  # send the read values back immediately

            urb_setup: UrbSetupPacket = UrbSetupPacket.unpack(cmd_submit.setup)
            self.logger.info(f"[usbip-server] Setup flags: {str(urb_setup)}\n{busid.hex()=}")
            for device in self.usb_devices.devices:
                if device.busid == busid:
                    transfer_buffer: Optional[bytes] = None
                    if urb_setup.descriptor_type == DescriptorType.DEVICE_DESCRIPTOR:
                        transfer_buffer = device.device.pack()
                    elif urb_setup.descriptor_type == DescriptorType.CONFIGURATION_DESCRIPTOR:
                        if urb_setup.request == URBStandardDeviceRequest.GET_DESCRIPTOR:
                            configuration: ConfigurationDescriptor = device.device.configurations[urb_setup.index]
                            transfer_buffer = configuration.pack()
                            interface_idx: int = 0
                            for association in configuration.associations:
                                transfer_buffer += association.pack()
                                for i in range(0, association.bInterfaceCount):
                                    interface: InterfaceDescriptor = configuration.interfaces[i+interface_idx]
                                    transfer_buffer += interface.pack()
                                    for descriptor in interface.descriptors:
                                        transfer_buffer += descriptor.pack()
                                interface_idx += association.bInterfaceCount

                            self.logger.info(f"[usbip-server] {urb_setup.length=}, {len(transfer_buffer)=}")
                            transfer_buffer = transfer_buffer[:urb_setup.length]  # restrict response to length requested
                    elif urb_setup.descriptor_type == DescriptorType.STRING_DESCRIPTOR:
                        transfer_buffer = StringDescriptor(wLanguage=0x409).pack()
                    elif urb_setup.request == URBStandardDeviceRequest.SET_CONFIGURATION:
                        to_enable: DescriptorType = DescriptorType(urb_setup.value & 0xFF)
                        self.logger.info(f"[usbip-server] Setting configuration: {to_enable.name}")
                        transfer_buffer = bytes()
                    elif urb_setup.request == URBCDCRequestType.SET_LINE_CODING:
                        self.logger.info(f"[usbip-server] Setting line coding")
                        transfer_buffer = bytes()
                    elif urb_setup.request == URBCDCRequestType.SET_CONTROL_LINE_STATE:
                        self.logger.info(f"[usbip-server] Setting control line state")
                        transfer_buffer = bytes()

                    if transfer_buffer is not None:
                        ret_submit = USBIP_RET_SUBMIT(status=0, transfer_buffer=transfer_buffer, seqnum=cmd_submit.seqnum)
                        response: bytes = ret_submit.pack()
                        self.logger.info(f"[usbip-server] #{ret_submit.seqnum},{ret_submit.actual_length=}, {len(response)=} {response.hex()=}")
                        return response

            # device not found, return error
            busid: str = self._urb_traffic.strip(b'\0').decode('utf-8') if self._urb_traffic else 'None'
            devices: str = ",".join([device.busid.strip(b'\0').decode('utf-8') for device in self.usb_devices.devices])
            self.logger.warning(f"operation not recognized: {urb_setup.descriptor_type.name=}, {busid=}, {devices=}")
            failure: CommonHeader = CommonHeader(command=BasicCommands.RET_SUBMIT, status=errno.ENODEV)
            self._urb_traffic = None
            return failure.pack()

    def mock_response(self, client: socket.socket, message: bytes) -> None:
        """use the lsusb devices to mock a response"""
        busid: str = self._urb_traffic.strip(b'\0').decode('utf-8') if self._urb_traffic else 'None'
        self.logger.info(f"[usbip-server] {busid=}, {message.hex()=}")
        if self._urb_traffic is not None:  # we have imported a device
            response: bytes = self.mock_urb_responses(message, busid=self._urb_traffic)
            if response:
                client.sendall(response)
                self.logger.info(f"[usbip-server] client.sendall {len(response)=}, {response.hex()=}")

        header: CommonHeader = CommonHeader.unpack(message)
        if header.command == BasicCommands.REQ_DEVLIST:
            response: bytes = self.usb_devices.pack()
            self.logger.info(f"[usbip-server] REP_DEVLIST: {response.hex()=}")
            if response:
                client.sendall(response)
            return
        elif header.command == BasicCommands.REQ_IMPORT:
            req_import: OP_REQ_IMPORT = OP_REQ_IMPORT.unpack(message)
            self.logger.info(f"[usbip-server] REQ_IMPORT {req_import.busid}")
            for path in self.usb_devices.usbip.paths:
                if path.busid == req_import.busid:
                    device: MockDevice = self.usb_devices.device(busnum=path.busnum, devnum=path.devnum)
                    was_already_attached: bool = device.attach  # attach the device (returns previous state
                    if was_already_attached:
                        self.logger.warning(f"Device is already attached! {str(device)}")
                    rep_import: OP_REP_IMPORT = OP_REP_IMPORT(status=0, path=path.path, busid=req_import.busid, busnum=path.busnum,
                                                              devnum=path.devnum, speed=path.speed, idVendor=path.idVendor,
                                                              idProduct=path.idProduct, bcdDevice=path.bcdDevice,
                                                              bDeviceClass=path.bDeviceClass, bDeviceSubClass=path.bDeviceSubClass,
                                                              bDeviceProtocol=path.bDeviceProtocol, bConfigurationValue=path.bConfigurationValue,
                                                              bNumConfigurations=path.bNumConfigurations, bNumInterfaces=path.bNumInterfaces)
                    data: bytes = rep_import.pack()
                    client.sendall(data)
                    self.logger.info(f"OP_REP_IMPORT: {data.hex()}")
                    self._urb_traffic = path.busid
                    return
            return

    def read_message(self, conn: socket.socket) -> bytes:
        """read a single message from the socket"""
        if self._urb_traffic:  # reading URBs
            message = conn.recv(CMD_SUBMIT_PREFIX.size)
            if message:
                try:
                    urb_cmd: CMD_SUBMIT_PREFIX = CMD_SUBMIT_PREFIX.unpack(message)
                except struct.error as s_error:
                    raise ValueError(f"{message.hex()=}") from struct.error
                try:
                    transfer_buffer: bytes = conn.recv(urb_cmd.transfer_buffer_length) \
                        if urb_cmd.transfer_buffer_length  and urb_cmd.direction == Direction.USBIP_DIR_OUT else b''
                    return message + transfer_buffer
                except OSError:
                    self.logger.error(f"Timeout, {BasicCommands(urb_cmd.command).name}, {len(message)=}, {urb_cmd.transfer_buffer_length=}, {message.hex()=}")
                    raise
        else:  # USBIP traffic
            message = conn.recv(CommonHeader.size)  # read the prefix for a USBIP command
            if message:
                usbip_cmd: CommonHeader = CommonHeader.unpack(message)
                if usbip_cmd.command == BasicCommands.REQ_DEVLIST:
                    return message
                elif usbip_cmd.command == BasicCommands.REQ_IMPORT:
                    remaining_size = OP_REQ_IMPORT.size - len(message)
                    remainder = conn.recv(remaining_size)
                    if not remainder:
                        raise ValueError(f"Unexpected lack of response {usbip_cmd.command.name}, expected {remaining_size} bytes")
                    message += remainder
                    return message
                else:
                    raise ValueError(f"Unrecognized command {usbip_cmd.command.name}")

        return b''

    def run(self):
        """standup the server, start listening"""
        self.server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.settimeout(None)  # so our accept() will block

        self.server_socket.listen(1)  # only allow one connection (testing)
        self.event.set()
        self.logger.info("\nmock USBIP server started @%s:%s", self.host, self.port)
        try:
            while self.event.is_set():
                conn, address = self.server_socket.accept()  # accept new connection
                conn.settimeout(None)  # wait for as long as it takes
                self.logger.info(f"[usbip-server] client @{address} connected")
                try:
                    while conn and self.event.is_set():
                        message: bytes = self.read_message(conn)
                        if not message:
                            conn.shutdown(socket.SHUT_RDWR)
                            conn.close()
                            conn = None
                        else:
                            self.mock_response(conn, message)

                    if conn:
                        conn.shutdown(socket.SHUT_RDWR)
                        conn.close()  # close the connection
                except OSError as os_error:
                    failure: str = traceback.format_exc()
                    self.logger.info(f"[usbip-server] client @{address} disconnected from {self.host}:{self.port}, {os_error=}\n{failure=}")
                    if conn:
                        conn.shutdown(socket.SHUT_RDWR)
                        conn.close()
                        conn = None
        except OSError as os_error:
            failure: str = traceback.format_exc()
            self.logger.error(f"[usbip-server] Exception {str(os_error)}\n{failure=}")
        except Exception as bad_error:
            failure: str = traceback.format_exc()
            self.logger.error(f"[usbip-server] Exception = {str(bad_error)}\n{failure=}")
        finally:
            self.event.set()  # indicate we are exiting
            self.logger.info("[usbip-server] server stopped @%s:%s", self.host, self.port)

    def read_paths(self) -> list[OP_REP_DEV_PATH]:
        """read the paths from the JSON file"""
        devlist: bytes = bytes.fromhex("".join([item for item in self._protocol_responses['OP_REP_DEVLIST']]))
        devlist_header: OP_REP_DEVLIST_HEADER = OP_REP_DEVLIST_HEADER.unpack(devlist[:OP_REP_DEVLIST_HEADER.size])
        devices: bytes = devlist[OP_REP_DEVLIST_HEADER.size:]
        paths: list[OP_REP_DEV_PATH] = []
        for device_index in range(0, devlist_header.num_exported_devices):
            path: OP_REP_DEV_PATH = OP_REP_DEV_PATH.unpack(devices)
            paths.append(path)
            devices = devices[OP_REP_DEV_PATH.size:]
            for _ in range(0, path.bNumInterfaces):
                interface: OP_REP_DEV_INTERFACE = OP_REP_DEV_INTERFACE.unpack(devices)
                path.interfaces.append(interface)
                devices = devices[OP_REP_DEV_INTERFACE.size:]

        return paths
