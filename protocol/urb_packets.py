"""definitions for URB packets"""

from typing import Optional, Any
from dataclasses import dataclass

from datastruct.fields import field

from usbip_defs import Direction
from protocol.packets import URBBase  # URBs are "little-endian"
from usbip_protocol import URBStandardEndpointRequest, URBStandardInterfaceRequest, URBStandardDeviceRequest, URBSetupRequestType, URBCDCRequestType
from usb_descriptors import DescriptorType, DeviceInterfaceClass, CDCDescriptorSubType, EndpointAttributesTransferType


@dataclass
class BaseDescriptor(URBBase):
    """all descriptors share these properties"""
    bLength: int = field("B", default=0x0)
    bDescriptorType: DescriptorType = field("B", default=0x0)

    @property
    def descriptor_type(self) -> DescriptorType:
        """return the descriptor type"""
        return self.bDescriptorType


@dataclass
class DeviceDescriptor(BaseDescriptor):  # https://www.mikecramer.com/qnx/momentics_nc_docs/ddk_en/usb/usbd_device_descriptor.html
    """URB device descriptor"""
    bcdUSB: int = field("H", default=0x0)
    bDeviceClass: int = field("B", default=0x0)
    bDeviceSubClass: int = field("B", default=0x0)
    bDeviceProtocol: int = field("B", default=0x0)
    bMaxPacketSize: int = field("B", default=0x0)
    idVendor: int = field("H", default=0x0)
    idProduct: int = field("H", default=0x0)
    bcdDevice: int = field("H", default=0x0)
    iManufacturer: int = field("B", default=0x0)
    iProduct: int = field("B", default=0x0)
    iSerial: int = field("B", default=0x0)
    bNumConfigurations: int = field("B", default=0x0)

    def __post_init__(self) -> None:
        """set up some instance variables"""
        self.configurations: list[ConfigurationDescriptor] = []


@dataclass
class ConfigurationDescriptor(BaseDescriptor):  # https://www.mikecramer.com/qnx/momentics_nc_docs/ddk_en/usb/usbd_configuration_descriptor.html
    """URB configuration descriptor"""
    wTotalLength: int = field("H", default=0x0)
    bNumInterfaces: int = field("B", default=0x0)
    bConfigurationValue: int = field("B", default=0x0)
    iConfiguration: int = field("B", default=0x0)
    bmAttributes: int = field("B", default=0x0)
    bMaxPower: int = field("B", default=0x0)

    def __post_init__(self) -> None:
        """set up some instance variables"""
        self.interfaces: list[InterfaceDescriptor] = []
        self.associations: list[InterfaceAssociation] = []


@dataclass
class InterfaceDescriptor(BaseDescriptor):  # https://www.mikecramer.com/qnx/momentics_nc_docs/ddk_en/usb/usbd_interface_descriptor.html
    """interface descriptor"""
    bInterfaceNumber: int = field("B", default=0x0)
    bAlternateSetting: int = field("B", default=0x0)
    bNumEndpoints: int = field("B", default=0x0)
    bInterfaceClass: DeviceInterfaceClass = field("B", default=0x0)
    bInterfaceSubClass: int = field("B", default=0x0)
    bInterfaceProtocol: int = field("B", default=0x0)
    iInterface: int = field("B", default=0x0)

    def __post_init__(self) -> None:
        """initialize instance variables"""
        self.descriptors: list[EndPointDescriptor | FunctionalDescriptor] = []

    @property
    def interface_class(self) -> DeviceInterfaceClass:
        """return the interface class"""
        return self.bInterfaceClass


@dataclass
class InterfaceAssociation(BaseDescriptor):
    """interface descriptor"""
    bFirstInterface: int = field("B", default=0x0)
    bInterfaceCount: int = field("B", default=0x0)
    bFunctionClass: int = field("B", default=0x0)
    bFunctionSubClass: int = field("B", default=0x0)
    bFunctionProtocol: int = field("B", default=0x0)
    iFunction: int = field("B", default=0x0)


@dataclass
class FunctionalDescriptor(URBBase):
    """interface descriptor base"""
    bFunctionLength: int = field("B", default=0x0)
    bDescriptorType: DescriptorType = field("B", default=0x0)
    bDescriptorSubType: CDCDescriptorSubType = field("B", default=0x0)


@dataclass
class UnionFunctionalDescriptor(FunctionalDescriptor):
    """interface descriptor base"""
    bMasterInterface: int = field("B", default=0x0)
    bSlaveInterface: int = field("B", default=0x0)

    def __post_init__(self) -> None:
        """initialize our descriptor type"""
        self.bDescriptorType = DescriptorType.CS_INTERFACE
        self.bDescriptorSubType = CDCDescriptorSubType.FeatureUnit
        self.bFunctionLength = self.size


@dataclass
class ACMFunctionalDescriptor(FunctionalDescriptor):
    """interface descriptor base"""
    bmCapabilities: int = field("B", default=0x0)

    def __post_init__(self) -> None:
        """initialize our descriptor type"""
        self.bDescriptorType = DescriptorType.CS_INTERFACE
        self.bDescriptorSubType = CDCDescriptorSubType.AbstractControlManagement
        self.bFunctionLength = self.size


@dataclass
class HeaderFunctionalDescriptor(FunctionalDescriptor):
    """interface descriptor base"""
    bcdCDC: int = field("H", default=0x0)

    def __post_init__(self) -> None:
        """initialize our descriptor type"""
        self.bDescriptorType = DescriptorType.CS_INTERFACE
        self.bDescriptorSubType = CDCDescriptorSubType.Header
        self.bFunctionLength = self.size


@dataclass
class CallManagementFunctionalDescriptor(FunctionalDescriptor):
    """interface descriptor base"""
    bmCapabilities: int = field("B", default=0x0)
    bDataInterface: int = field("B", default=0x0)

    def __post_init__(self) -> None:
        """initialize our descriptor type"""
        self.bDescriptorType = DescriptorType.CS_INTERFACE
        self.bDescriptorSubType = CDCDescriptorSubType.CallManagement
        self.bFunctionLength = self.size


@dataclass
class EndPointDescriptor(BaseDescriptor):  # https://www.mikecramer.com/qnx/momentics_nc_docs/ddk_en/usb/usbd_endpoint_descriptor.html
    """Endpoint descriptor packet"""
    bEndpointAddress: int = field("B", default=0x0)
    bmAttributes: int = field("B", default=0x0)
    wMaxPacketSize: int = field("H", default=0x0)
    bInterval: int = field("B", default=0x0)

    def transfer_type(self) -> EndpointAttributesTransferType:
        """determine the transfer type from the bitfield"""
        return EndpointAttributesTransferType(self.bmAttributes & 0x3)

    @property
    def is_output(self):
        """return the direction"""
        return not bool(self.bEndpointAddress & 0x80)

    @property
    def number(self) -> int:
        """return the endpoint address"""
        return self.bEndpointAddress & 0xF

    def __repr__(self):
        """for display purposes"""
        ep_dir: str = "IN" if self.bEndpointAddress & 0x80 else "OUT"
        number: int = self.bEndpointAddress & 0xF
        response: str = f"bEndpointAddress=0x{self.bEndpointAddress:02x}[{ep_dir} #{number}]"
        response += f", bDescriptorType={self.bDescriptorType.name}"
        return response


@dataclass
class StringDescriptor(BaseDescriptor):
    """handle string descriptors"""
    wLanguage: int = field("H", default=0x0)


class GenericDescriptor:
    """handle a generic descriptor and return correct type"""
    def __init__(self):
        """initialize all instance data we need"""
        self._handlers: dict[DescriptorType, callable] = {
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
        configuration_desc: ConfigurationDescriptor = ConfigurationDescriptor.unpack(data)
        offset: int = configuration_desc.size
        interface_desc_size: int = InterfaceDescriptor.size
        idx_interface: int = 0
        while idx_interface < configuration_desc.bNumInterfaces:
            if len(data[offset:]) < BaseDescriptor.size:
                break
            desc_type: DescriptorType = self._descriptor_type(data[offset:])
            if desc_type == DescriptorType.INTERFACE_ASSOCIATION:
                offset += InterfaceAssociation.size
            elif desc_type == DescriptorType.INTERFACE_DESCRIPTOR:
                idx_interface += 1
                if len(data[offset:]) >= interface_desc_size:
                    interface_desc: InterfaceDescriptor = self._interface_handler(data[offset:], length=interface_desc_size)
                    configuration_desc.interfaces.append(interface_desc)
                    offset += interface_desc.size + sum(item.size for item in interface_desc.descriptors)
            elif desc_type == DescriptorType.STRING_DESCRIPTOR:
                base_desc: BaseDescriptor = BaseDescriptor.unpack(data[offset:])
                offset += base_desc.bLength

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
        base_desc: BaseDescriptor = BaseDescriptor.new(data[: BaseDescriptor().size])
        return DescriptorType(base_desc.bDescriptorType)

    def _interface_handler(self, data: bytes, length) -> InterfaceDescriptor | InterfaceAssociation:
        """handle interface descriptors"""
        interface_desc: InterfaceDescriptor = InterfaceDescriptor.unpack(data)
        offset: int = interface_desc.size
        for _ in range(0, interface_desc.bNumEndpoints):
            endpoint: bool = False
            while not endpoint:
                base_desc: BaseDescriptor = BaseDescriptor.unpack(data[offset:])
                descriptor_type: DescriptorType = DescriptorType(base_desc.bDescriptorType)
                if descriptor_type == DescriptorType.ENDPOINT_DESCRIPTOR:
                    endpoint_desc: EndPointDescriptor = self._endpoint_handler(data[offset:], length=base_desc.bLength)
                    interface_desc.descriptors.append(endpoint_desc)
                    offset += endpoint_desc.size
                    endpoint = True
                elif descriptor_type == DescriptorType.CS_INTERFACE:
                    functional_desc: FunctionalDescriptor = self._functional_handler(data[offset:], base_desc.bLength)
                    interface_desc.descriptors.append(functional_desc)
                    offset += base_desc.bLength
                elif descriptor_type == DescriptorType.INVALID_DESCRIPTOR:
                    raise ValueError(f"Interface: invalid descriptor type, {data.hex()=}")

        return interface_desc

    @staticmethod
    def _functional_handler(data: bytes, length: int) -> FunctionalDescriptor:  # pylint: disable=unused-argument
        """handle functional descriptors"""
        func_desc: FunctionalDescriptor = FunctionalDescriptor.unpack(data)
        if func_desc.bDescriptorSubType == CDCDescriptorSubType.AbstractControlManagement:
            func_desc = ACMFunctionalDescriptor.unpack(data)
        elif func_desc.bDescriptorSubType == CDCDescriptorSubType.FeatureUnit:  # union functional descriptor
            func_desc = UnionFunctionalDescriptor.unpack(data)
        elif func_desc.bDescriptorSubType == CDCDescriptorSubType.Header:  # header functional descriptor
            func_desc = HeaderFunctionalDescriptor.unpack(data)
        elif func_desc.bDescriptorSubType == CDCDescriptorSubType.CallManagement:  # Call Management descriptor
            func_desc = CallManagementFunctionalDescriptor.unpack(data)

        return func_desc

    def _string_handler(self, data: bytes, length: int) -> StringDescriptor:
        """handle string descriptors"""

    def packet(self, data: bytes) -> Any:
        """given a stream of bytes, create appropriate descriptor"""
        descriptor: BaseDescriptor = BaseDescriptor.new(data[0:2])
        descriptor_type = DescriptorType(descriptor.bDescriptorType)
        handler: Optional[callable] = self._handlers.get(descriptor_type, None)
        if handler:
            return handler(data, descriptor.bLength)
        return None


@dataclass
class UrbSetupPacket(URBBase):
    """URB setup packet structure"""
    request_type: int = field("B", default=0)
    request: int = field("B", default=0)
    value: int = field("H", default=0)
    index: int = field("H", default=0)
    length: int = field("H", default=0)

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

    @property
    def bRequest(self) -> str:
        """return a string representing the request this setup packet represents"""
        try:
            return URBStandardDeviceRequest(self.request).name
        except ValueError:
            try:
                return URBCDCRequestType(self.request).name
            except ValueError:
                return f"0x{self.request:02x}"

    @property
    def descriptor_type(self) -> DescriptorType:
        """return the descriptor type"""
        if self.bRequest in [URBStandardDeviceRequest.GET_DESCRIPTOR.name, URBStandardDeviceRequest.SET_CONFIGURATION.name]:
            return DescriptorType(self.value >> 8)
        else:
            return DescriptorType.INVALID_DESCRIPTOR

    @property
    def wValue(self) -> str:
        """return a string represent the value that is contextually aware"""
        if self.bRequest == URBStandardDeviceRequest.GET_DESCRIPTOR.name:
            # wValue = Descriptor Type & Index
            descriptor: DescriptorType = DescriptorType((self.value & 0xFF00) >> 8)
            index: int = self.value & 0xFF
            return f"{descriptor.name}:{index}"
        return f'{self.value:04x}'

    @property
    def device_type(self) -> str:
        """return the recipient of the bmRequestType"""
        device_type: int = (self.request_type & 0x70) >> 8
        device_types: dict[int, str] = {0: 'Standard', 1: 'Class', 2: 'Vendor', 3: 'Reserved'}
        return device_types[device_type]

    @property
    def recipient(self) -> str:
        """return the recipient of the bmRequestType"""
        recipient: int = (self.request_type & 0xF) >> 8
        recipients: dict[int, str] =  {0: 'Device', 1: 'Interface', 2: 'Endpoint', 3: 'Other'}
        return recipients[recipient]

    def __str__(self):
        """decode the setup"""
        output: str = "\nSetup=" + self.pack().hex() + "\n"
        output += f"...bmRequestType={self.request_type:02x}" + "\n"
        output += "......Direction=" + URBSetupRequestType(self.request_type & URBSetupRequestType.DEVICE_TO_HOST).name + "\n"
        output += "......Type=" + self.device_type + "\n"
        output += "......Recipient=" + self.recipient + "\n"
        output += f"...bRequest={self.bRequest}\n"
        output += f"...wValue={self.wValue}\n"
        output += f"...wIndex={self.index} (0x{self.index:04x})\n"
        output += f"...wLength={self.length}\n"
        output += f"...Direction={self.direction.name}\n"

        return output
