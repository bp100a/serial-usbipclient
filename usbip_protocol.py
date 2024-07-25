#
# Mobilion Acorn REST API services
# Copyright (c) 2024 MOBILion Systems, Inc.
# Author: Harry Collins
#
"""full implementation of a python-only client to connect to usbipd servers"""

# Protocol can be found here:
# https://docs.kernel.org/usb/usbip_protocol.html
#
from __future__ import annotations
from enum import IntEnum
from typing import Optional

from usbip_defs import BaseProtocolPacket
from usbip_defs import BasicCommands
from usbip_defs import Direction


class URBTransferFlags(IntEnum):
    """transfer flags from usb.h"""

    URB_SHORT_NOT_OK = 0x0001  # report short reads as errors
    URB_ISO_ASAP = 0x0002  # iso-only; use the first unexpired *slot in the schedule
    URB_NO_TRANSFER_DMA_MAP = 0x0004  # urb->transfer_dma valid on submit
    URB_ZERO_PACKET = 0x0040  # Finish bulk OUT with short packet
    URB_NO_INTERRUPT = 0x0080  # HINT: no non-error interrupt *needed
    URB_FREE_BUFFER = 0x0100  # Free transfer buffer with the URB

    # *The following flags are used internally by usbcore and HCDs
    URB_DIR_IN = 0x0200  # Transfer from device to host
    URB_DIR_OUT = 0
    URB_DIR_MASK = URB_DIR_IN

    URB_DMA_MAP_SINGLE = 0x00010000  # Non-scatter-gather mapping
    URB_DMA_MAP_PAGE = 0x00020000  # HCD-unsupported S-G
    URB_DMA_MAP_SG = 0x00040000  # HCD-supported S-G
    URB_MAP_LOCAL = 0x00080000  # HCD-local-memory mapping
    URB_SETUP_MAP_SINGLE = 0x00100000  # Setup packet DMA mapped
    URB_SETUP_MAP_LOCAL = 0x00200000  # HCD-local setup packet
    URB_DMA_SG_COMBINED = 0x00400000  # S-G entries were combined
    URB_ALIGNED_TEMP_BUFFER = 0x00800000  # Temp buffer was alloc'd


class URBSetupRequestType(IntEnum):
    """define bitfields for the request_type field in the setup"""

    HOST_TO_DEVICE = 0 << 7  # for readability
    DEVICE_TO_HOST = 1 << 7
    TYPE_STANDARD = 0 << 5
    TYPE_CLASS = 1 << 5
    TYPE_VENDOR = 2 << 5
    TYPE_PRODUCT = 3 << 5
    RECIPIENT_DEVICE = 0x0
    RECIPIENT_INTERFACE = 0x1
    RECIPIENT_ENDPOINT = 0x2
    RECIPIENT_OTHER = 0x3


class URBStandardDeviceRequest(IntEnum):
    """device requests"""

    GET_STATUS = 0x0
    CLEAR_FEATURE = 0x1
    SET_FEATURE = 0x3
    SET_ADDRESS = 0x5
    GET_DESCRIPTOR = 0x6
    SET_DESCRIPTOR = 0x7
    GET_CONFIGURATION = 0x8
    SET_CONFIGURATION = 0x9


class URBStandardInterfaceRequest(IntEnum):
    """device requests"""

    GET_STATUS = 0x0
    CLEAR_FEATURE = 0x1
    GET_INTERFACE = 0x0A
    SET_INTERFACE = 0x11


class URBStandardEndpointRequest(IntEnum):
    """device requests"""

    GET_STATUS = 0x0
    CLEAR_FEATURE = 0x1
    SET_FEATURE = 0x3
    SYNCH_FRAME = 0x12


class URBCDCRequestType(IntEnum):
    """request types specific to CDC devices"""

    SET_LINE_CODING = (
        0x20  # Configures baud rate, stop-bits, parity, and numberof-character bits.
    )
    GET_LINE_CODING = 0x21  # Requests current DTE rate, stop-bits, parity, and number-of-character bits.
    SET_CONTROL_LINE_STATE = (
        0x22  # RS232 signal used to tell the DCE device the DTE device is now present.
    )


class UrbSetupPacket(BaseProtocolPacket):
    """URB setup packet structure"""

    format: dict = {
        0: ("B", "request_type"),
        1: ("B", "request"),
        2: ("H", "value"),
        4: ("H", "index"),
        6: ("H", "length"),
    }
    fmt: str = ""
    args: list[str] = []
    endianness: str = "<"  # this portion of the URB is little-endian

    def __init__(
        self,
        request_type: int = 0,
        request: int = 0,
        value: int = 0,
        index: int = 0,
        length: int = 0,
    ):
        """initialize the setup packet"""
        self.request_type: int = request_type
        self.request: int = request
        self.value: int = value
        self.index: int = index
        self.length: int = length
        super().__init__()  # just to keep type checker happy

    @property
    def direction(self) -> Direction:
        """the direction of the request"""
        if self.request in [
            URBStandardEndpointRequest.SET_FEATURE.value,
            URBStandardInterfaceRequest.SET_INTERFACE.value,
            URBStandardDeviceRequest.SET_FEATURE.value,
            URBStandardDeviceRequest.SET_CONFIGURATION.value,
            URBStandardDeviceRequest.SET_DESCRIPTOR,
            URBCDCRequestType.SET_LINE_CODING,
        ]:
            return Direction.USBIP_DIR_OUT  # host -> device (WRITE)
        return Direction.USBIP_DIR_IN  # device -> host (READ)


class OP_REQ_DEVLIST(BaseProtocolPacket):
    """Retrieve the list of exported USB devices"""

    def __init__(self):
        """build the outgoing packet structure"""
        super().__init__(command=0x8005, status=0x0000)


class OP_REP_DEVLIST_HEADER(BaseProtocolPacket):
    """response from usbipd service, list of devices"""

    fmt: str = ""
    args: list[str] = []
    format: dict = {8: ("I", "number_exported_devices")}

    def __init__(
        self,
        usbip_version: int = 0,
        command: int = 0,
        status: int = 0,
        number_exported_devices: int = 0,
    ):
        """our device list"""
        self.num_exported_devices: int = number_exported_devices
        self.paths: list[OP_REP_DEV_PATH] = []
        super().__init__(version=usbip_version, command=command, status=status)


class OP_REP_DEV_PATH(BaseProtocolPacket):
    """response from usbipd service, list of devices"""

    fmt: str = ""
    args: list[str] = []
    format: dict = {
        0x0C: (">256s", "path"),
        0x10C: ("32s", "busid"),
        0x12C: ("I", "busnum"),
        0x130: ("I", "devnum"),
        0x134: ("I", "speed"),
        0x138: ("H", "idVendor"),
        0x13A: ("H", "idProduct"),
        0x13C: ("H", "bcdDevice"),
        0x13E: ("B", "bDeviceClass"),
        0x13F: ("B", "bDeviceSubClass"),
        0x140: ("B", "bDeviceProtocol"),
        0x141: ("B", "bConfigurationValue"),
        0x142: ("B", "bNumConfigurations"),
        0x143: ("B", "bNumInterfaces"),
    }

    def __init__(
        self,
        path: bytes = None,
        busid: bytes = None,
        busnum: int = 0,
        devnum: int = 0,
        speed: int = 0,
        idVendor: int = 0,
        idProduct: int = 0,
        bcdDevice: int = 0,
        bDeviceClass: int = 0,
        bDeviceSubClass: int = 0,
        bDeviceProtocol: int = 0,
        bConfigurationValue: int = 0,
        bNumConfigurations: int = 0,
        bNumInterfaces: int = 0,
    ) -> None:
        """our device list"""
        self.path: Optional[bytes] = path
        self.busid: Optional[bytes] = busid
        self.busnum: int = busnum
        self.devnum: int = devnum
        self.speed: int = speed
        self.idVendor: int = idVendor
        self.idProduct: int = idProduct
        self.bcdDevice: int = bcdDevice
        self.bDeviceClass: int = bDeviceClass
        self.bDeviceSubClass: int = bDeviceSubClass
        self.bDeviceProtocol: int = bDeviceProtocol
        self.bConfigurationValue: int = bConfigurationValue
        self.bNumConfigurations: int = bNumConfigurations
        self.bNumInterfaces: int = bNumInterfaces
        self.interfaces: list[OP_REP_DEV_INTERFACE] = []
        super().__init__(command=0x0005, status=0x0)


class OP_REP_DEV_INTERFACE(BaseProtocolPacket):
    """response from usbipd service, list of interfaces for a specific device"""

    fmt: str = ""
    args: list[str] = []
    format: dict = {
        0x144: ("B", "bInterfaceClass"),
        0x145: ("B", "bInterfaceSubClass"),
        0x146: ("B", "bInterfaceProtocol"),
        0x147: ("B", "_alignment"),
    }

    def __init__(
        self,
        interfaceclass: int = 0,
        interfacesubclass: int = 0,
        interfaceprotocol: int = 0,
        alignment: int = 0,
    ):
        """a device interface"""
        self.bInterfaceClass: int = interfaceclass
        self.bInterfaceSubClass: int = interfacesubclass
        self.bInterfaceProtocol: int = interfaceprotocol
        self._alignment: int = alignment
        super().__init__()


class OP_REQ_IMPORT(BaseProtocolPacket):
    """import an usbipd published device"""

    fmt: str = ""
    args: list[str] = ""
    format: dict = {0x8: ("32s", "busid")}

    def __init__(self, busid: Optional[bytes] = None):
        """create a request"""
        self.busid: Optional[bytes] = busid
        super().__init__(command=0x8003, status=0x0)


class OP_REP_IMPORT(BaseProtocolPacket):
    """response from an import (attach) request"""

    fmt: str = ""
    args: list[str] = ""
    format: dict = {
        0x8: ("256s", "path"),
        0x108: ("32s", "busid"),
        0x128: ("i", "busnum"),
        0x12C: ("i", "devnum"),
        0x130: ("i", "speed"),
        0x134: ("h", "idVendor"),
        0x136: ("h", "idProduct"),
        0x138: ("H", "bcdDevice"),
        0x139: ("B", "bDeviceClass"),
        0x13A: ("B", "bDeviceSubClass"),
        0x13B: ("B", "bDeviceProtocol"),
        0x13C: ("B", "bConfigurationValue"),
        0x13D: ("B", "bNumConfigurations"),
        0x13E: ("B", "bNumInterfaces"),
    }

    def __init__(
        self,
        usbip_version: int = 0,
        command: int = 0,
        status: int = 0,
        path: bytes = None,
        busid: bytes = None,
        busnum: int = 0,
        devnum: int = 0,
        speed: int = 0,
        idVendor: int = 0,
        idProduct: int = 0,
        bcdDevice: int = 0,
        bDeviceClass: int = 0,
        bDeviceSubClass: int = 0,
        bDeviceProtocol: int = 0,
        bConfigurationValue: int = 0,
        bNumConfigurations: int = 0,
        bNumInterfaces: int = 0,
    ) -> None:
        """our device list"""
        self.path: Optional[bytes] = path
        self.busid: Optional[bytes] = busid
        self.busnum: int = busnum
        self.devnum: int = devnum
        self.speed: int = speed
        self.idVendor: int = idVendor
        self.idProduct: int = idProduct
        self.bcdDevice: int = bcdDevice
        self.bDeviceClass: int = bDeviceClass
        self.bDeviceSubClass: int = bDeviceSubClass
        self.bDeviceProtocol: int = bDeviceProtocol
        self.bConfigurationValue: int = bConfigurationValue
        self.bNumConfigurations: int = bNumConfigurations
        self.bNumInterfaces: int = bNumInterfaces
        self.interfaces: list[OP_REP_DEV_INTERFACE] = []
        super().__init__(command=command, status=status, version=usbip_version)


class HEADER_BASIC(BaseProtocolPacket):
    """basic protocol packet for URB traffic"""

    fmt: str = ""
    args: list[str] = ""
    format: dict[int, tuple[str, str]] = {
        0x0: (">i", "command"),
        0x4: ("i", "seqnum"),
        0x8: ("i", "devid"),
        0xC: ("i", "direction"),
        0x10: ("i", "ep"),
    }

    def __init__(
        self,
        command: int = 0,
        seqnum: int = 0,
        devid: int = 0,
        direction: int = 0,
        ep: int = 0,
    ) -> None:
        """our device list"""
        self.command: int = command
        self.seqnum: int = seqnum
        self.devid: int = devid
        self.direction: int = direction
        self.ep: int = ep
        super().__init__(command=self.command, status=0x0)
        if not HEADER_BASIC.fmt:
            HEADER_BASIC.fmt = "".join(
                [HEADER_BASIC.format[item][0] for item in HEADER_BASIC.format]
            )
            HEADER_BASIC.args = [
                HEADER_BASIC.format[item][1] for item in HEADER_BASIC.format
            ]


class CMD_SUBMIT(HEADER_BASIC):
    """submit command to usbipd server"""

    fmt: str = ""
    args: list[str] = ""
    format: dict[int, tuple[str, str]] = {
        0x14: ("i", "transfer_flags"),
        0x18: ("i", "transfer_buffer_length"),
        0x1C: ("i", "start_frame"),
        0x20: ("I", "number_of_packets"),
        0x24: ("i", "interval"),
        0x28: ("8s", "setup"),
        0x30: ("s", "transfer_buffer"),
        0x31: ("s", "iso_packet_descriptor"),
    }

    def __init__(
        self,
        seqnum: int = 0,
        devid: int = 0,
        direction: int = 0,
        ep: int = 0x4,
        transfer_flags: int = 0,
        transfer_buffer_length: int = 0,  # pylint: disable=unused-argument
        start_frame: int = 0,
        number_of_packets: int = 0xFFFFFFFF,
        interval: int = 0,
        setup: Optional[bytes] = None,
        transfer_buffer: Optional[bytes] = None,
        iso_packet_descriptor: Optional[
            bytes
        ] = None,  # pylint: disable=unused-argument
    ) -> None:
        """create a command to submit"""
        self.transfer_flags: int = transfer_flags
        self.transfer_buffer_length: int = (
            len(transfer_buffer) if transfer_buffer else transfer_buffer_length
        )
        self.start_frame: int = start_frame
        self.number_of_packets: int = number_of_packets
        self.interval: int = interval
        self.setup: Optional[bytes] = setup if setup else bytes(b"\x00" * 8)
        self.transfer_buffer: Optional[bytes] = (
            transfer_buffer if transfer_buffer else bytes()
        )
        self.iso_packet_descriptor: Optional[bytes] = bytes()

        super().__init__(
            command=BasicCommands.CMD_SUBMIT,
            seqnum=seqnum,
            devid=devid,
            direction=direction,
            ep=ep,
        )

        # regenerate so we catch changes to the transfer_buffer
        CMD_SUBMIT.format[0x30] = (
            f"{len(self.transfer_buffer)}s",
            CMD_SUBMIT.format[0x30][1],
        )
        if 0x31 in CMD_SUBMIT.format:
            CMD_SUBMIT.format.pop(0x31)  # ISO transfers not supported
        CMD_SUBMIT.fmt = HEADER_BASIC.fmt + "".join(
            [CMD_SUBMIT.format[item][0] for item in CMD_SUBMIT.format]
        )
        CMD_SUBMIT.args = HEADER_BASIC.args + [
            CMD_SUBMIT.format[item][1] for item in CMD_SUBMIT.format
        ]


class RET_SUBMIT_PREFIX(HEADER_BASIC):
    """data from usbipd server"""

    fmt: str = ""
    args: list[str] = ""
    format: dict[int, tuple[str, str]] = {
        0x14: ("i", "status"),
        0x18: ("i", "actual_length"),
        0x1C: ("i", "start_frame"),
        0x20: ("i", "number_of_packets"),
        0x24: ("i", "error_count"),
        0x28: ("8s", "padding"),
    }

    def __init__(
        self,
        command: int = 0,
        seqnum: int = 0,
        devid: int = 0,
        direction: int = 0,
        ep: int = 0,
        status: int = 0,
        actual_length: int = 0,
        start_frame: int = 0,
        number_of_packets: int = 0,
        error_count: int = 0,
        padding: Optional[bytes] = None,
    ) -> None:
        """fixed portion of a submit ret"""
        super().__init__(
            command=command, seqnum=seqnum, devid=devid, direction=direction, ep=ep
        )
        self.status: int = status
        self.actual_length: int = actual_length
        self.start_frame: int = start_frame
        self.number_of_packets: int = number_of_packets
        self.error_count: int = error_count
        self.padding: Optional[bytes] = padding
        self.transfer_buffer: Optional[bytes] = None
        if not RET_SUBMIT_PREFIX.fmt:
            RET_SUBMIT_PREFIX.fmt = HEADER_BASIC.fmt + "".join(
                [RET_SUBMIT_PREFIX.format[item][0] for item in RET_SUBMIT_PREFIX.format]
            )
            RET_SUBMIT_PREFIX.args = HEADER_BASIC.args + [
                RET_SUBMIT_PREFIX.format[item][1] for item in RET_SUBMIT_PREFIX.format
            ]


class RET_SUBMIT_DATA(HEADER_BASIC):
    """read the variable portion of the data"""

    fmt: str = ""
    args: list[str] = ""
    format: dict[int, tuple[str, str]] = {
        0x30: ("s", "transfer_buffer"),
        0x31: ("s", "iso_packet_descriptor"),
    }


class CMD_UNLINK(HEADER_BASIC):
    """unlink a queued command"""

    fmt: str = ""
    args: list[str] = ""
    format: dict[int, tuple[str, str]] = {
        0x14: ("i", "unlink_seqnum"),
        0x18: ("24s", "padding"),
    }

    def __init__(
        self,
        command: int = 0,
        seqnum: int = 0,
        devid: int = 0,
        direction: int = 0,
        ep: int = 0,
        unlink_seqnum: int = 0,
        padding: Optional[bytes] = None,
    ) -> None:  # pylint: disable=unused-argument
        """fixed portion of a submit ret"""
        super().__init__(
            command=BasicCommands.CMD_UNLINK,
            seqnum=seqnum,
            devid=devid,
            direction=direction,
            ep=ep,
        )
        self.unlink_seqnum = unlink_seqnum
        self.padding: bytes = bytes(24)  # initialize with 0s
        if not CMD_UNLINK.fmt:
            CMD_UNLINK.fmt = HEADER_BASIC.fmt + "".join(
                [CMD_UNLINK.format[item][0] for item in CMD_UNLINK.format]
            )
            CMD_UNLINK.args = HEADER_BASIC.args + [
                CMD_UNLINK.format[item][1] for item in CMD_UNLINK.format
            ]


class RET_UNLINK(HEADER_BASIC):
    """response for an unlink a queued command"""

    fmt: str = ""
    args: list[str] = ""
    format: dict[int, tuple[str, str]] = {
        0x14: ("i", "status"),
        0x18: ("24s", "padding"),
    }

    def __init__(
        self,
        command: int = BasicCommands.RET_UNLINK,
        seqnum: int = 0,
        devid: int = 0,
        direction: int = 0,
        ep: int = 0,
        status: int = 0,
        padding: Optional[bytes] = None,
    ) -> None:
        """fixed portion of a submit ret"""
        super().__init__(
            command=command, seqnum=seqnum, devid=devid, direction=direction, ep=ep
        )
        self.status = status
        self.padding: Optional[bytes] = padding
        if not RET_UNLINK.fmt:
            RET_UNLINK.fmt = HEADER_BASIC.fmt + "".join(
                [RET_UNLINK.format[item][0] for item in RET_UNLINK.format]
            )
            RET_UNLINK.args = HEADER_BASIC.args + [
                RET_UNLINK.format[item][1] for item in RET_UNLINK.format
            ]
