#
# Copyright (c) 2024 Altai Technologies, LLC
# Author: Harry Collins
#
"""handling of USB/URB descriptors"""

# Protocol can be found here:
# https://docs.kernel.org/usb/usbip_protocol.html
#
from __future__ import annotations
from enum import IntEnum
from typing import Callable, Any, Optional

from usbip_defs import BaseProtocolPacket

# Define h/w structures that don't conform to pylint's defaults
# pylint: disable=too-many-instance-attributes, too-many-arguments, invalid-name


class DescriptorType(IntEnum):
    """types of descriptors"""

    DEVICE_DESCRIPTOR = 0x1
    CONFIGURATION_DESCRIPTOR = 0x2
    STRING_DESCRIPTOR = 0x3
    INTERFACE_DESCRIPTOR = 0x4
    ENDPOINT_DESCRIPTOR = 0x5
    INTERFACE_ASSOCIATION = 0xB  # Gener8 electronics reports this
    CS_INTERFACE = 0x24


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


class BaseDescriptor(BaseProtocolPacket):
    """all descriptors share these properties"""

    format: dict = {
        0: ("b", "bLength"),
        1: ("b", "bDescriptorType"),
    }
    fmt: str = ""
    args: list[str] = []
    endianness: str = "<"  # data is little-endian, and not aligned!

    def __init__(self, length: int = 0, descriptor_type: int = 0):
        """initialize descriptor common elements"""
        super().__init__()  # keep type checker happy
        self.length = length
        self.descriptor_type = descriptor_type


class DeviceDescriptor(BaseProtocolPacket):
    """URB device descriptor"""

    format: dict = {
        0: ("b", "bLength"),
        1: ("b", "bDescriptorType"),
        2: ("H", "bcdUSB"),
        4: ("b", "bDeviceClass"),
        5: ("b", "bDeviceSubClass"),
        6: ("b", "bDevice Protocol"),
        7: ("b", "bMaxPacketSize"),
        8: ("H", "idVendor"),
        10: ("H", "idProduct"),
        12: ("H", "bcdDevice"),
        14: ("b", "iManufacturer"),
        15: ("b", "iProduct"),
        16: ("b", "iSerialNumber"),
        17: ("b", "bNumConfigurations"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(
        self,
        length: int = 0,
        descriptor_type: int = 0,
        usb: int = 0,
        device_class: int = 0,
        device_subclass: int = 0,
        device_protocol: int = 0,
        max_packet_size: int = 0,
        vid: int = 0,
        pid: int = 0,
        device: int = 0,
        manufacturer: int = 0,
        product: int = 0,
        serial_number: int = 0,
        num_configurations: int = 0,
    ):
        """initialize the device descriptor packet"""
        super().__init__()  # keep type checker happy
        self.length: int = length
        self.descriptor_type: int = descriptor_type
        self.usb: int = usb
        self.device_class: int = device_class
        self.device_subclass: int = device_subclass
        self.device_protocol: int = device_protocol
        self.max_packet_size: int = max_packet_size
        self.vid: int = vid
        self.pid: int = pid
        self.device: int = device
        self.manufacturer: int = manufacturer
        self.product: int = product
        self.serial_number: int = serial_number
        self.num_configurations: int = num_configurations


class ConfigurationDescriptor(BaseProtocolPacket):
    """URB configuration descriptor"""

    format: dict = {
        0: ("b", "bLength"),
        1: ("b", "bDescriptorType"),
        2: ("H", "wTotalLength"),
        4: ("b", "bNumInterfaces"),
        5: ("b", "bConfigurationValue"),
        6: ("b", "iConfiguration"),
        7: ("b", "bmAttributes"),
        8: ("b", "bMaxPower"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(
        self,
        length: int = 0,
        descriptor_type: int = 0,
        total_length: int = 0,
        num_interfaces: int = 0,
        configuration_value: int = 0,
        configuration: int = 0,
        attributes: int = 0,
        max_power: int = 0,
    ):
        """initialize the configuration descriptor packet"""
        super().__init__()
        self.length: int = length
        self.descriptor_type: int = descriptor_type
        self.total_length: int = total_length
        self.num_interfaces: int = num_interfaces
        self.configuration_value: int = configuration_value
        self.configuration: int = configuration
        self.attributes: int = attributes
        self.max_power: int = max_power
        self.interfaces: list[InterfaceDescriptor] = []


class InterfaceDescriptor(BaseProtocolPacket):
    """interface descriptor"""

    format: dict = {
        0: ("b", "bLength"),
        1: ("b", "bDescriptorType"),
        2: ("b", "bInterfaceNumber"),
        3: ("b", "bAlternateSetting"),
        4: ("b", "bNumEndpoints"),
        5: ("b", "bInterfaceClass"),
        6: ("b", "bInterfaceSubClass"),
        7: ("b", "bInterfaceProtocol"),
        8: ("b", "iInterface"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(
        self,
        length: int = 0,
        descriptor_type: int = 0,
        interface_number: int = 0,
        alternate_setting: int = 0,
        num_endpoints: int = 0,
        interface_class: int = 0,
        interface_subclass: int = 0,
        interface_protocol: int = 0,
        i_interface: int = 0,
    ):
        """initialize interface descriptor"""
        super().__init__()  # keep linter happy
        self.length = length
        self.descriptor_type = descriptor_type
        self.interface_number = interface_number
        self.alternate_setting = alternate_setting
        self.num_endpoints = num_endpoints
        self.interface_class = interface_class
        self.interface_subclass = interface_subclass
        self.interface_protocol = interface_protocol
        self.i_interface = i_interface
        self.descriptors: list[EndPointDescriptor | FunctionalDescriptor] = []


class InterfaceAssociation(BaseProtocolPacket):
    """interface descriptor"""

    format: dict = {
        0: ("b", "bLength"),
        1: ("b", "bDescriptorType"),
        2: ("b", "bFirstInterface"),
        3: ("b", "bInterfaceCount"),
        4: ("b", "bFunctionClass"),
        5: ("b", "bFunctionSubClass"),
        6: ("b", "bFunctionProtocol"),
        7: ("b", "iFunction"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(
        self,
        length: int = 0,
        descriptor_type: int = 0,
        first_interface: int = 0,
        interface_count: int = 0,
        function_class: int = 0,
        function_subclass: int = 0,
        function_protocol: int = 0,
        function: int = 0,
    ):
        """initialize interface descriptor"""
        super().__init__()  # keep linter happy
        self.length = length
        self.descriptor_type = descriptor_type
        self.first_interface = first_interface
        self.interface_count = interface_count
        self.function_class = function_class
        self.function_subclass = function_subclass
        self.function_protocol = function_protocol
        self.function = function


class FunctionalDescriptor(BaseProtocolPacket):
    """interface descriptor base"""

    format: dict = {
        0: ("b", "bFunctionLength"),
        1: ("b", "bDescriptorType"),
        2: ("b", "bDescriptorSubType"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(
        self,
        function_length: int = 0,
        descriptor_type: int = 0,
        descriptor_subtype: int = 0,
    ):
        """initialize the interface descriptor packet"""
        super().__init__()  # keep type checker happy
        self.function_length: int = function_length
        self.descriptor_type: int = descriptor_type
        self.descriptor_subtype: int = descriptor_subtype


class UnionFunctionalDescriptor(FunctionalDescriptor):
    """interface descriptor base"""

    format: dict = {
        0: ("b", "bFunctionLength"),
        1: ("b", "bDescriptorType"),
        2: ("b", "bDescriptorSubType"),
        3: ("b", "bControllerInterface"),
        4: ("b", "bSubordinateInterface"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(
        self,
        function_length: int = 0,
        descriptor_type: int = 0,
        descriptor_subtype: int = 0,  # pylint: disable=too-many-arguments
        controller_interface: int = 0,
        subordinate_interface: int = 0,
    ):
        """initialize the interface descriptor packet"""
        super().__init__()  # keep type checker happy
        self.function_length: int = function_length
        self.descriptor_type: int = descriptor_type
        self.descriptor_subtype: int = descriptor_subtype
        self.controller_interface: int = controller_interface
        self.subordinate_interface: int = subordinate_interface


class ACMFunctionalDescriptor(FunctionalDescriptor):
    """interface descriptor base"""

    format: dict = {
        0: ("b", "bFunctionLength"),
        1: ("b", "bDescriptorType"),
        2: ("b", "bDescriptorSubType"),
        3: ("b", "bmCapabilities"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(
        self,
        function_length: int = 0,
        descriptor_type: int = 0,
        descriptor_subtype: int = 0,
        capabilities: int = 0,
    ):
        """initialize the interface descriptor packet"""
        super().__init__()  # keep type checker happy
        self.function_length: int = function_length
        self.descriptor_type: int = descriptor_type
        self.descriptor_subtype: int = descriptor_subtype
        self.capabilities: int = capabilities


class HeaderFunctionalDescriptor(FunctionalDescriptor):
    """interface descriptor base"""

    format: dict = {
        0: ("b", "bFunctionLength"),
        1: ("b", "bDescriptorType"),
        2: ("b", "bDescriptorSubType"),
        3: ("H", "bcdCDC"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(
        self,
        function_length: int = 0,
        descriptor_type: int = 0,
        descriptor_subtype: int = 0,
        cdc: int = 0,
    ):
        """initialize the interface descriptor packet"""
        super().__init__()  # keep type checker happy
        self.function_length: int = function_length
        self.descriptor_type: int = descriptor_type
        self.descriptor_subtype: int = descriptor_subtype
        self.cdc: int = cdc


class CallManagementFunctionalDescriptor(FunctionalDescriptor):
    """interface descriptor base"""

    format: dict = {
        0: ("B", "bFunctionLength"),
        1: ("B", "bDescriptorType"),
        2: ("B", "bDescriptorSubType"),
        3: ("B", "bmCapabilities"),
        4: ("B", "bDataInterface"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(
        self,
        function_length: int = 0,
        descriptor_type: int = 0,
        descriptor_subtype: int = 0,
        capabilities: int = 0,
        data_interface=0,
    ):
        """initialize the interface descriptor packet"""
        super().__init__()  # keep type checker happy
        self.function_length: int = function_length
        self.descriptor_type: int = descriptor_type
        self.descriptor_subtype: int = descriptor_subtype
        self.capabilities: int = capabilities
        self.data_interface: int = data_interface


class EndPointDescriptor(BaseProtocolPacket):
    """Endpoint descriptor packet"""

    format: dict = {
        0: ("b", "bLength"),
        1: ("b", "bDescriptorType"),
        2: ("b", "bEndpointAddress"),
        3: ("b", "bmAttributes"),
        4: ("H", "wMaxPacketSize"),
        6: ("b", "bInterval"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(
        self,
        length: int = 0,
        descriptor_type: int = 0,
        endpoint_address: int = 0,
        attributes: int = 0,
        max_packet_size: int = 0,
        interval: int = 0,
    ):
        """initialize the endpoint descriptor"""
        super().__init__()
        self.length: int = length
        self.descriptor_type: int = descriptor_type
        self.endpoint_address: int = endpoint_address
        self.bmAttributes: int = attributes
        self.wMaxPacketSize: int = max_packet_size
        self.bInterval: int = interval

    def transfer_type(self) -> EndpointAttributesTransferType:
        """determine the transfer type from the bitfield"""
        return EndpointAttributesTransferType(self.bmAttributes & 0x3)

    @property
    def is_output(self):
        """return the direction"""
        return not bool(self.endpoint_address & 0x80)

    @property
    def number(self) -> int:
        """return the endpoint address"""
        return self.endpoint_address & 0xF


class StringDescriptor(BaseDescriptor):
    """handle string descriptors"""

    format: dict = {
        0: ("b", "bLength"),
        1: ("b", "bDescriptorType"),
        2: ("w", "wLanguage"),
    }
    fmt: str = ""
    args: list[str] = []

    def __init__(self, length: int = 0, descriptor_type: int = 0, language: int = 0):
        """initialize the string descriptor"""
        super().__init__()
        self.length: int = length
        self.descriptor_type: int = descriptor_type
        self.language: int = language

class GenericDescriptor:
    """handle a generic descriptor and return correct type"""

    def __init__(self):
        """initialize all instance data we need"""
        self._handlers: dict[DescriptorType, Callable] = {
            DescriptorType.CONFIGURATION_DESCRIPTOR: self._configuration_handler,
            DescriptorType.ENDPOINT_DESCRIPTOR: self._endpoint_handler,
            DescriptorType.INTERFACE_DESCRIPTOR: self._interface_handler,
            DescriptorType.CS_INTERFACE: self._functional_handler,
            DescriptorType.DEVICE_DESCRIPTOR: self._device_handler,
            DescriptorType.INTERFACE_ASSOCIATION: self._interface_assoc_handler,
        }

    def _configuration_handler(
        self, data: bytes, length: int
    ) -> ConfigurationDescriptor:
        """handle Configuration descriptors"""
        configuration_desc: ConfigurationDescriptor = ConfigurationDescriptor.new(
            data[0:length]
        )
        offset: int = configuration_desc.size
        interface_desc_size: int = InterfaceDescriptor().size
        idx_interface: int = 0
        while idx_interface < configuration_desc.num_interfaces:
            if len(data[offset:]) < BaseDescriptor().size:
                break
            desc_type: DescriptorType = self._descriptor_type(data[offset:])
            if desc_type == DescriptorType.INTERFACE_ASSOCIATION:
                offset += InterfaceAssociation().size
            elif desc_type == DescriptorType.INTERFACE_DESCRIPTOR:
                idx_interface += 1
                if len(data[offset:]) >= interface_desc_size:
                    interface_desc: InterfaceDescriptor = self._interface_handler(
                        data[offset:], length=interface_desc_size
                    )
                    configuration_desc.interfaces.append(interface_desc)
                    offset += interface_desc.size + sum(
                        item.size for item in interface_desc.descriptors
                    )
            elif desc_type == DescriptorType.STRING_DESCRIPTOR:
                base_desc: BaseDescriptor = BaseDescriptor.new(
                    data[offset : offset + BaseDescriptor().size]
                )
                offset += base_desc.length

        return configuration_desc

    @staticmethod
    def _endpoint_handler(data: bytes, length: int) -> EndPointDescriptor:
        """handle endpoint descriptors"""
        endpoint_desc: EndPointDescriptor = EndPointDescriptor.new(data[0:length])
        return endpoint_desc

    @staticmethod
    def _device_handler(data: bytes, length: int) -> DeviceDescriptor:
        """handle device descriptors"""
        device_desc: DeviceDescriptor = DeviceDescriptor.new(data[0:length])
        return device_desc

    @staticmethod
    def _interface_assoc_handler(data: bytes, length: int) -> InterfaceAssociation:
        """handle the interface association descriptor"""
        interface_assoc: InterfaceAssociation = InterfaceAssociation.new(data[0:length])
        return interface_assoc

    @staticmethod
    def _descriptor_type(data: bytes) -> DescriptorType:
        """Determine the descriptor type"""
        try:
            base_desc: BaseDescriptor = BaseDescriptor.new(
                data[: BaseDescriptor().size]
            )
            return DescriptorType(base_desc.descriptor_type)
        except (
            ValueError
        ) as v_error:  # pylint: disable=unused-variable, try-except-raise
            raise

    def _interface_handler(
        self, data: bytes, length
    ) -> InterfaceDescriptor | InterfaceAssociation:
        """handle interface descriptors"""
        interface_desc: InterfaceDescriptor = InterfaceDescriptor.new(data[0:length])
        offset: int = interface_desc.size
        for _ in range(0, interface_desc.num_endpoints):
            endpoint: bool = False
            while not endpoint:
                base_desc: BaseDescriptor = BaseDescriptor.new(
                    data[offset : offset + BaseDescriptor().size]
                )
                descriptor_type: DescriptorType = DescriptorType(
                    base_desc.descriptor_type
                )
                if descriptor_type == DescriptorType.ENDPOINT_DESCRIPTOR:
                    endpoint_desc: EndPointDescriptor = self._endpoint_handler(
                        data[offset:], length=base_desc.length
                    )
                    interface_desc.descriptors.append(endpoint_desc)
                    offset += endpoint_desc.size
                    endpoint = True
                elif descriptor_type == DescriptorType.CS_INTERFACE:
                    functional_desc: FunctionalDescriptor = self._functional_handler(
                        data[offset:], base_desc.length
                    )
                    interface_desc.descriptors.append(functional_desc)
                    offset += base_desc.length

        return interface_desc

    @staticmethod
    def _functional_handler(
        data: bytes, length: int
    ) -> FunctionalDescriptor:  # pylint: disable=unused-argument
        """handle functional descriptors"""
        func_desc: FunctionalDescriptor = FunctionalDescriptor.new(
            data[: FunctionalDescriptor().size]
        )
        if (
            func_desc.descriptor_subtype
            == CDCDescriptorSubType.AbstractControlManagement
        ):
            func_desc = ACMFunctionalDescriptor.new(data[: func_desc.function_length])
        elif (
            func_desc.descriptor_subtype == CDCDescriptorSubType.FeatureUnit
        ):  # union functional descriptor
            func_desc = UnionFunctionalDescriptor.new(data[: func_desc.function_length])
        elif (
            func_desc.descriptor_subtype == CDCDescriptorSubType.Header
        ):  # header functional descriptor
            func_desc = HeaderFunctionalDescriptor.new(
                data[: func_desc.function_length]
            )
        elif (
            func_desc.descriptor_subtype == CDCDescriptorSubType.CallManagement
        ):  # Call Management descriptor
            func_desc = CallManagementFunctionalDescriptor.new(
                data[: func_desc.function_length]
            )
        else:
            pass
        return func_desc

    def _string_handler(self, data: bytes, length: int) -> StringDescriptor:
        """handle string descriptors"""

    def packet(self, data: bytes) -> Any:
        """given a stream of bytes, create appropriate descriptor"""
        descriptor: BaseDescriptor = BaseDescriptor.new(data[0:2])
        descriptor_type = DescriptorType(descriptor.descriptor_type)
        handler: Optional[Callable] = self._handlers.get(descriptor_type, None)
        if handler:
            return handler(data, descriptor.length)
        return None
