"""full implementation of a python-only client to connect to usbipd servers"""

# Protocol can be found here:
# https://docs.kernel.org/usb/usbip_protocol.html
#
from __future__ import annotations
from enum import IntEnum


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
    URB_ALIGNED_TEMP_BUFFER = 0x00800000  # Temp buffer was allocated


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
    """endpoint requests"""
    GET_STATUS = 0x0
    CLEAR_FEATURE = 0x1
    SET_FEATURE = 0x3
    SYNCH_FRAME = 0x12


class URBCDCRequestType(IntEnum):
    """request types specific to CDC devices"""
    SET_LINE_CODING = 0x20  # Configures baud rate, stop-bits, parity, and number-of-character bits.
    GET_LINE_CODING = 0x21  # Requests current DTE rate, stop-bits, parity, and number-of-character bits.
    SET_CONTROL_LINE_STATE = 0x22  # RS232 signal used to tell the DCE device the DTE device is now present.
