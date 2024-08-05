"""handling of USB/URB descriptors"""

# Protocol can be found here:
# https://docs.kernel.org/usb/usbip_protocol.html
#
from __future__ import annotations
from enum import IntEnum


# Define h/w structures that don't conform to pylint's defaults
# pylint: disable=too-many-instance-attributes, too-many-arguments, invalid-name


class DescriptorType(IntEnum):
    """types of descriptors"""
    INVALID_DESCRIPTOR = 0x0  # not a valid descriptor
    DEVICE_DESCRIPTOR = 0x1
    CONFIGURATION_DESCRIPTOR = 0x2
    STRING_DESCRIPTOR = 0x3
    INTERFACE_DESCRIPTOR = 0x4
    ENDPOINT_DESCRIPTOR = 0x5
    DEVICE_QUALIFIER_DESCRIPTOR_TYPE = 0x6
    OTHER_SPEED_CONFIGURATION_DESCRIPTOR_TYPE = 0x7
    INTERFACE_POWER_DESCRIPTOR_TYPE = 0x8
    OTG_DESCRIPTOR_TYPE = 0x9
    DEBUG_DESCRIPTOR_TYPE = 0xA
    INTERFACE_ASSOCIATION = 0xB  # Gener8 electronics reports this
    BOS_DESCRIPTOR_TYPE = 0xf
    DEVICE_CAPABILITY_DESCRIPTOR_TYPE = 0x10
    CS_INTERFACE = 0x24
    USB_20_HUB = 0x29
    USB_30_HUB = 0x2a
    USB_SUPERSPEED_ENDPOINT_COMPANION_DESCRIPTOR_TYPE = 0x30
    USB_SUPERSPEEDPLUS_ISOCH_ENDPOINT_COMPANION_DESCRIPTOR_TYPE = 0x31


class CDCDescriptorSubType(IntEnum):
    """subtypes of descriptors"""

    EthernetNetworkingFunctionalDescriptor = 0xF
    Header = 0x0
    CallManagement = 0x1
    AbstractControlManagement = 0x2
    FeatureUnit = 0x6


class DeviceInterfaceClass(IntEnum):
    """device and/or interface class"""

    PER_INTERFACE = 0  # for DeviceClass
    AUDIO = 1
    COMM = 2  # communications & cdc control
    HID = 3
    PHYSICAL = 5
    STILL_IMAGE = 6
    PRINTER = 7
    MASS_STORAGE = 8
    HUB = 9
    CDC_DATA = 0x0A
    CSCID = 0x0B  # chip+ smart card
    CONTENT_SEC = 0x0D  # content security
    VIDEO = 0x0E
    WIRELESS_CONTROLLER = 0xE0
    PERSONAL_HEALTHCARE = 0x0F
    AUDIO_VIDEO = 0x10
    BILLBOARD = 0x11
    USB_TYPE_C_BRIDGE = 0x12
    MISC = 0xEF
    APP_SPEC = 0xFE
    VENDOR_SPEC = 0xFF


class FunctionClass(IntEnum):
    """define our function classes"""

    DEVICE = 0  # class information in the Interface Descriptor
    AUDIO = 1
    CDC = 2  # Communications & CDC Control
    HID = 3
    PHYSICAL = 5
    STILL_IMAGE = 6
    PRINTER = 7
    MASS_STORAGE = 8
    CDC_DATA = 0x0A
    CSCID = 0x0B
    CONTENT_SEC = 0x0D
    VIDEO = 0x0E
    WIRELESS_CONTROLLER = 0xE0


class MassStorageFunctionSubClass(IntEnum):
    """define our function subclasses"""

    UFI = 4  # usb floppies
    SCSI = 6


class MassStorageProtocol(IntEnum):
    """protocols for Mass Storage devices"""

    CBI = 0x1


class EndpointAttributesTransferType(IntEnum):
    """bits [0..1] of bmAttributes"""

    CONTROL = 0x0
    ISOCHRONOUS = 0x1
    BULK = 0x2
    INTERRUPT = 0x3


class EndpointAttributesSynchronizationType(IntEnum):
    """bits[3..2] of bmAttributes"""

    NO_SYNCHRONIZATION = 0x0
    ASYNCHRONOUS = 0x1
    ADAPTIVE = 0x2
    SYNCHRONOUS = 0x3


class EndpointAttributesUsageType(IntEnum):
    """bits[5..4] of bmAttributes"""

    DATA_ENDPOINT = 0x0
    FEEDBACK_ENDPOINT = 0x1
    EXPLICIT_FEEDBACK_DATA_ENDPOINT = 0x2
    RESERVED = 0x3
