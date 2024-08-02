#
# Definitions for USBIP protocol packets
#
import struct
from functools import lru_cache
from dataclasses import dataclass

from datastruct import DataStruct
from datastruct.fields import field, built
from datastruct.utils.config import Endianness, datastruct_config, Config, datastruct_get_config

from usbip_defs import BasicCommands, Direction


class MetaStruct(type):
    """holds class property"""
    @classmethod
    def packet_size(cls):
        """compute the packet size"""
        return 0

    @property
    def size(cls) -> int:
        """compute the static size of the structure"""
        return cls.packet_size()


@dataclass
class BaseStruct(DataStruct, metaclass=MetaStruct):
    """some commonly used methods"""

    @classmethod
    @lru_cache()
    def config(cls) -> Config:
        datastruct_config(endianness=Endianness.NETWORK)
        config = Config(datastruct_get_config())
        config.update(getattr(cls, "_CONFIG", {}))
        return config

    def packet(self) -> bytes:
        """serialize the structure"""
        return self.pack()

    @classmethod
    def new(cls, data: bytes):
        """Create (and return) a new instance based on the binary data"""
        return cls.unpack(data)

    @property
    def size(self) -> int:
        """returns the actual size of the data structure based on configuration"""
        return self.sizeof()

    @classmethod
    def packet_size(cls) -> int:
        """return the size of packets"""
        fmt: str = "".join([item[1].fmt for item in cls.classfields() if isinstance(item[1].fmt, str)])
        return struct.calcsize(fmt)


@dataclass
class URBBase(BaseStruct):
    """make our URBs little-endian"""
    @classmethod
    @lru_cache()
    def config(cls) -> Config:
        datastruct_config(endianness=Endianness.LITTLE)
        config = Config(datastruct_get_config())
        config.update(getattr(cls, "_CONFIG", {}))
        return config


@dataclass
class CommonHeader(BaseStruct):
    """basic USBIP command header"""
    usbip_version: int = field("H", default=0x111)
    command: BasicCommands = field("H", default=0x0)
    status: int = field("I", default=0x0)


@dataclass
class OP_REQ_DEVLIST(CommonHeader):
    """request the device list"""
    def __post_init__(self):
        """ensure command is set properly"""
        if self.command == BasicCommands.UNDEFINED:
            self.command = BasicCommands.REQ_DEVLIST


@dataclass
class OP_REQ_IMPORT(CommonHeader):
    """import an usbipd published device"""
    busid: bytes = field("32s")

    def __post_init__(self):
        """ensure command is set properly"""
        if self.command == BasicCommands.UNDEFINED:
            self.command = BasicCommands.REQ_IMPORT


@dataclass
class OP_REP_IMPORT(CommonHeader):
    """response from an import (attach) request"""
    path: bytes = field("256s", default=b'\0'*256)  # 0x8
    busid: bytes = field("32s", default=b'\0'*32)  # 0x108
    busnum: int = field("i", default=0x0)  # 0x128
    devnum: int = field("i", default=0x0)  # 0x12C
    speed: int = field("i", default=0x0)  # 0x130
    idVendor: int = field("H", default=0x0)  # 0x134
    idProduct: int = field("H", default=0x0)  # 0x136
    bcdDevice: int = field("H", default=0x0)  # 0x138
    bDeviceClass: int = field("B", default=0x0)  # 0x139
    bDeviceSubClass: int = field("B", default=0x0)  # 0x13A
    bDeviceProtocol: int = field("B", default=0x0)  # 0x13B
    bConfigurationValue: int = field("B", default=0x0)  # 0x13C
    bNumConfigurations: int = field("B", default=0x0)  # 0x13D
    bNumInterfaces: int = field("B", default=0x0)  # 0x13E

    def __post_init__(self):
        """ensure command is set property"""
        if self.command == BasicCommands.UNDEFINED:
            self.command = BasicCommands.RET_SUBMIT


@dataclass
class OP_REP_DEV_PATH(BaseStruct):
    """list of device paths"""
    path: bytes = field("256s", default=b'\0'*256)  # 0xC
    busid: bytes = field("32s", default=b'\0'*32)  # 0x10C
    busnum: int = field("I", default=0x0)  # 0x12C
    devnum: int = field("I", default=0x0)  # 0x130
    speed: int = field("I", default=0x0)  # 0x134
    idVendor: int = field("H", default=0x0)  # 0x138
    idProduct: int = field("H", default=0x0)  # 0x13A
    bcdDevice: int = field("H", default=0x0)  # 0x13C
    bDeviceClass: int = field("B", default=0x0)  # 0x13E
    bDeviceSubClass: int = field("B", default=0x0)  # 0x13F
    bDeviceProtocol: int = field("B", default=0x0)  # 0x140
    bConfigurationValue: int = field("B", default=0x0)  # 0x141
    bNumConfigurations: int = field("B", default=0x0)  # 0x142
    bNumInterfaces: int = field("B", default=0x0)  # 0x143

    def __post_init__(self):
        """set up any instance variables"""
        self.interfaces: list[OP_REP_DEV_INTERFACE] = []


@dataclass
class OP_REP_DEVLIST_HEADER(CommonHeader):
    """header of the device list"""
    num_exported_devices: int = field("I", default=0x0)

    def __post_init__(self):
        """ensure command is set properly"""
        self.paths: list[OP_REP_DEV_PATH] = []
        if self.command == BasicCommands.UNDEFINED:
            self.command = BasicCommands.REP_DEVLIST


@dataclass
class HEADER_BASIC(BaseStruct):
    """basic protocol packet for URB traffic"""
    command: int = field("i", default=BasicCommands.UNDEFINED)  # 0x0, the command being issued or returned
    seqnum: int = field("i", default=0x0)  # 0x04, sequential number that identifies requests & corresponding responses, increment per connection
    devid: int = field("i", default=0x0)  # 0x08, specifies remote USB device, client (request) (busnum << 16) | devnum, for server this shall be 0
    direction: int = field("i", default=0x0)  # 0x0c, 0=USBIP_DIR_OUT, 1=USBIP_DIR_IN, only used by client, for server this shall be 0
    ep: int = field("i", default=0x0)  # 0x10, endpoint number only used by client, for server this shall be 0; for UNLINK, this shall be 0


@dataclass
class CMD_SUBMIT(HEADER_BASIC):
    """submit a URB"""
    transfer_flags: int = field("I", default=0x0)  # 0x14, URB transfer flags
    transfer_buffer_length: int = built("I", lambda ctx: len(ctx.transfer_buffer) if ctx.transfer_buffer else ctx.transfer_buffer_length)  # 0x18
    start_frame: int = field("I", default=0x0)  # 0x1C, =0 if not ISO transfer
    number_of_packets: int = field("I", default=0xFFFFFFFF)  # 0x20, # of ISO packets, default it not ISO
    interval: int = field("i", default=0x0)  # 0x24,  maximum time for the request on the server-side host controller
    setup: bytes = field("8s", default=b'\0\0\0\0\0\0\0\0')  # 0x28, data bytes for USB setup, filled with zeros if not used.
    transfer_buffer: bytes = field(lambda ctx: ctx.transfer_buffer_length)  # 0x30, -> HOST, data we are sending

    @property
    def iso_packet_descriptors(self) -> bytes:
        """return the iso packet descriptor"""
        return self.transfer_buffer if self.number_of_packets != 0xFFFFFFFF else None

    def __post_init__(self):
        """ensure command is set properly"""
        if self.command == BasicCommands.UNDEFINED:
            self.command = BasicCommands.CMD_SUBMIT


@dataclass
class USBIP_RET_SUBMIT(HEADER_BASIC):
    """submit a URB"""
    status: int = field("i", default=0x0)  # 0x14
    actual_length: int = built("i", lambda ctx: len(ctx.transfer_buffer))   # 0x18
    start_frame: int = field("I", default=0xFFFFFFFF)  # 0x1C
    number_of_packets: int = field("i", default=0x0)  # 0x20
    error_count: int = field("i", default=0x0)  # 0x24
    padding: bytes = field("8s", default=b'\0'*8)  # 0x28
    transfer_buffer: bytes = field(lambda ctx: ctx.actual_length if ctx.direction == Direction.USBIP_DIR_OUT else 0)

    def __post_init__(self):
        """ensure command is set properly"""
        if self.command == BasicCommands.UNDEFINED:
            self.command = BasicCommands.RET_SUBMIT


@dataclass
class CMD_UNLINK(HEADER_BASIC):
    """unlink a USB device"""
    unlink_seqnum: int = field("i")  # 0x14, sequence number to unlink
    padding: bytes = field("24s", default=b'\0'*24)  # 0x18, padding defaulted to 0s

    def __post_init__(self):
        """ensure command is set properly"""
        if self.command == BasicCommands.UNDEFINED:
            self.command = BasicCommands.CMD_UNLINK


@dataclass
class RET_UNLINK(HEADER_BASIC):
    """response for an unlink a queued command"""
    status: int = field("i", default=0x0)  # 0x14
    padding: bytes = field("24s", default=b'\0'*24)  # 0x18, padding defaulted to 0s

    def __post_init__(self):
        """ensure command is set properly"""
        if self.command == BasicCommands.UNDEFINED:
            self.command = BasicCommands.RET_UNLINK


@dataclass
class OP_REP_DEV_INTERFACE(BaseStruct):
    """response from usbipd service, list of interfaces for a specific device"""
    bInterfaceClass: int = field("B", default=0)
    bInterfaceSubClass: int = field("B", default=0)
    bInterfaceProtocol: int = field("B", default=0)
    _alignment: int = field("B", default=0)


@dataclass
class RET_SUBMIT_PREFIX(HEADER_BASIC):
    """data from usbipd server"""
    status: int = field("i", default=0x0)  # 0x14
    actual_length: int = field("i", default=0)  # 0x18
    start_frame: int = field("i", default=0x0)  # 0x1C
    number_of_packets: int = field("i", default=0xFFFFFFFF)  # 0x20
    error_count: int = field("i", default=0x0)  # 0x24
    padding: bytes = field("8s", default=b'\0'*8)  # 0x28
