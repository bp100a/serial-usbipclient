"""mock USBIP server"""

import os
import errno
import json
import platform
import re
import socket
from threading import Thread, Event
from time import time, sleep
from queue import Queue
import logging
from typing import Optional, Any, cast
from enum import EnumType
import glob
from dataclasses import dataclass

from protocol.packets import (CommonHeader, OP_REP_DEVLIST_HEADER, OP_REQ_IMPORT, OP_REP_DEV_PATH, OP_REP_IMPORT,
                              HEADER_BASIC, CMD_SUBMIT, USBIP_RET_SUBMIT, OP_REP_DEV_INTERFACE)
from usbip_protocol import Direction
from protocol.urb_packets import (UrbSetupPacket, DeviceDescriptor, ConfigurationDescriptor,
                                  URBBase, InterfaceDescriptor, InterfaceAssociation, EndPointDescriptor, HeaderFunctionalDescriptor,
                                  CallManagementFunctionalDescriptor, ACMFunctionalDescriptor, UnionFunctionalDescriptor)
from usbip_defs import BasicCommands
from usb_descriptors import DescriptorType


@dataclass
class MockDevice:
    """URB information for a device"""
    vendor: int = 0
    product: int = 0
    device: Optional[DeviceDescriptor] = None

    def __hash__(self):
        """return the hash of this device"""
        return hash((self.vendor, self.product))


class Parse_lsusb:
    """parse the output of a lsusb command to get a USB device configuration"""
    def __init__(self):
        """parse the data"""
        self.root: str = os.path.join(os.path.dirname(__file__), '*.lsusb')
        self.device_descriptors: list[MockDevice] = []
        for file_path in glob.glob(self.root):
            self.file_path: str = file_path
            device_descriptor: DeviceDescriptor = DeviceDescriptor()
            usb_configuration: list[str] = self.read_file(self.file_path)
            for offset in range(len(usb_configuration)):
                if usb_configuration[offset].startswith('Device Descriptor:'):
                    self.parse_descriptor(usb_configuration, offset, urb=device_descriptor)
                    self.device_descriptors.append(MockDevice(device_descriptor.idVendor, device_descriptor.idProduct, device_descriptor))
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

    def setup(self):
        """create the USBIP device list"""
        busnum: int = 1
        devnum: int = 0
        usbip_dev_header: OP_REP_DEVLIST_HEADER = OP_REP_DEVLIST_HEADER()
        usbip_dev_header.num_exported_devices = len(self.devices)

        for usb in self.devices:
            devnum += 1
            devid: bytes = f"{busnum}-{devnum}".encode('utf-8')
            busid: bytes = devid + (b'\0' * (32-len(devid)))
            root_dev_path: bytes = f"/sys/devices/pci0000.0/0000:00.1d1/usb2/{busnum}-{devnum}".encode('utf-8')
            dev_path: bytes = root_dev_path + (b'\0' * (256 - len(root_dev_path)))

            path: OP_REP_DEV_PATH = OP_REP_DEV_PATH(busid=busid, path=dev_path, busnum=busnum, devnum=devnum,
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
        self.queue: Queue = Queue()
        self.server_socket: socket.socket | None = None
        self.thread: Thread = Thread(name=f'mock-usbip@{self.host}:{self.port}', target=self.run, daemon=True)
        self.event: Event = Event()
        self._is_windows: bool = platform.system() == 'Windows'
        self._protocol_responses: dict[str, list[str]] = {}
        self._urb_traffic: bool = False
        self.urb_queue: dict[int, Any] = {}  # pending read URBs, queued by seq #
        self.setup()
        self.event.clear()
        self.thread.start()
        start_time: float = time()
        while time() - start_time < 5.0:
            if self.event.is_set():
                return
            sleep(0.010)  # allow thread time to start

        raise TimeoutError(f"Timed out waiting for USBIP server to start, waited {round(time() - start_time, 2)} seconds")

    def setup(self):
        """setup our instance"""
        data_path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'usbip_packets.json')
        with open(file=data_path, mode='r') as recording:
            self._protocol_responses = json.loads(recording.read())

    def shutdown(self):
        """shutdown the USBIP server thread"""
        if self.thread and self.event.is_set():
            self.logger.info("usbip-server: clear event, wait for thread to recognize exit condition")
            self.event.clear()  # -> 0, thread will exit loop if we aren't blocking on accept()
            if self.server_socket:
                if not self._is_windows:  # in linux-land, need to shut down as well
                    self.server_socket.shutdown(socket.SHUT_RDWR)
                self.server_socket.close()  # if we are waiting for accept(), should unblock

            self.logger.info("usbip-server: waiting for event to signal (0->1)")
            if self.event.wait(timeout=10.0):
                self.thread.join(timeout=1.0)
                self.thread = None
                return
            raise TimeoutError(f"Timed out waiting for USBIP server to acknowledge shutdown")

    def process_message(self, client: socket.socket, message: bytes) -> None:
        """process the message sent"""
        self.logger.info(f"{self._urb_traffic=}, {message.hex()=}")
        if self._urb_traffic:
            urb_header: HEADER_BASIC = HEADER_BASIC.unpack(message)
            if urb_header.command == BasicCommands.CMD_SUBMIT:
                cmd_submit: CMD_SUBMIT = CMD_SUBMIT.unpack(message)
                if cmd_submit.ep and cmd_submit.direction == Direction.USBIP_DIR_IN:  # a read is being issued
                    raise NotImplementedError("TBD, queueing URB packets")

                urb_setup: UrbSetupPacket = UrbSetupPacket.unpack(cmd_submit.setup)
                ret_submit: Optional[USBIP_RET_SUBMIT] = None
                self.logger.info(f"Setup flags: {str(urb_setup)}")
                if urb_setup.value == DescriptorType.DEVICE_DESCRIPTOR << 8:
                    # return descriptor for device
                    ret_submit = USBIP_RET_SUBMIT.unpack(bytes.fromhex(self._protocol_responses['URB_SETUP'][0]))
                elif urb_setup.value == DescriptorType.CONFIGURATION_DESCRIPTOR << 8:
                    ret_submit = USBIP_RET_SUBMIT.unpack(bytes.fromhex(self._protocol_responses['URB_SETUP'][1]))
                elif urb_setup.value == DescriptorType.STRING_DESCRIPTOR << 8:
                    ret_submit = USBIP_RET_SUBMIT.unpack(bytes.fromhex(self._protocol_responses['URB_SETUP'][2]))
                if ret_submit:
                    ret_submit.seqnum = cmd_submit.seqnum
                    response: bytes = ret_submit.pack()
                    self.logger.info(f"{ret_submit.actual_length=}, {response.hex()=}")
                    client.sendall(response)
                    return

                failure: bytes = USBIP_RET_SUBMIT(status=0, direction=0, transfer_buffer=bytes()).pack()
                client.sendall(failure)
        else:
            header: CommonHeader = CommonHeader.unpack(message)
            if header.command == BasicCommands.REQ_DEVLIST:
                # return the device list
                for output in self._protocol_responses['OP_REP_DEVLIST']:
                    data: bytes = bytes.fromhex(output)
                    client.sendall(data)
            elif header.command == BasicCommands.REQ_IMPORT:
                # return specifics for device import (find the busid we are looking for)
                req_import: OP_REQ_IMPORT = OP_REQ_IMPORT.unpack(message)
                for path in self.read_paths():
                    if path.busid == req_import.busid:
                        rep_import: OP_REP_IMPORT = OP_REP_IMPORT(status=0, path=path.path, busid=req_import.busid, busnum=path.busnum,
                                                                  devnum=path.devnum, speed=path.speed, idVendor=path.idVendor,
                                                                  idProduct=path.idProduct, bcdDevice=path.bcdDevice,
                                                                  bDeviceClass=path.bDeviceClass, bDeviceSubClass=path.bDeviceSubClass,
                                                                  bDeviceProtocol=path.bDeviceProtocol, bConfigurationValue=path.bConfigurationValue,
                                                                  bNumConfigurations=path.bNumConfigurations, bNumInterfaces=path.bNumInterfaces)
                        data: bytes = rep_import.pack()
                        client.sendall(data)
                        self.logger.info(f"OP_REP_IMPORT: {data.hex()}")
                        self._urb_traffic = True
                        return
                else:
                    # device not found, return error
                    self.logger.warning(f"busid not found: {req_import.busid.hex()}")
                    failure: CommonHeader = CommonHeader(command=BasicCommands.RET_SUBMIT, status=errno.ENODEV)
                    client.sendall(failure.pack())
                    self._urb_traffic = False

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
            conn: Optional[socket.socket] = None
            while self.event.is_set():
                conn, address = self.server_socket.accept()  # accept new connection
                self.logger.info(f"usbip-server, client @{address} connected")
                try:
                    while conn and self.event.is_set():
                        message: bytes = conn.recv(1024)
                        if not message:
                            conn.shutdown(socket.SHUT_RDWR)
                            conn.close()
                            conn = None
                        else:
                            self.process_message(conn, message)

                    if conn:
                        conn.shutdown(socket.SHUT_RDWR)
                        conn.close()  # close the connection
                except OSError as os_error:
                    self.logger.info(f"usbip-server, client @{address} disconnected: {os_error}")
                    if conn:
                        conn.shutdown(socket.SHUT_RDWR)
                        conn.close()
                        conn = None
        except OSError as os_error:
            pass
        finally:
            self.event.set()  # indicate we are exiting
            self.logger.info("mock USBIP server stopped @%s:%s", self.host, self.port)

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
