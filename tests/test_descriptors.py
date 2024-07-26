
from tests.test_base import TestBase
import usb_descriptors


class TestInterfaceDescriptor(TestBase):
    """test the formatting of the interface descriptor"""
    def test_descriptors(self):
        """test the descriptors"""
        descriptors: list[tuple[callable, str, list[str]]] = [
            (usb_descriptors.InterfaceDescriptor, '!bbbbbbbbb', ['bLength',
                                                                 'bDescriptorType',
                                                                 'bInterfaceNumber',
                                                                 'bAlternateSetting',
                                                                 'bNumEndpoints',
                                                                 'bInterfaceClass',
                                                                 'bInterfaceSubClass',
                                                                 'bInterfaceProtocol',
                                                                 'iInterface']),
            (usb_descriptors.ConfigurationDescriptor, '!bbHbbbbb', ['bLength',
                                                                    'bDescriptorType',
                                                                    'wTotalLength',
                                                                    'bNumInterfaces',
                                                                    'bConfigurationValue',
                                                                    'iConfiguration',
                                                                    'bmAttributes',
                                                                    'bMaxPower']),
            (usb_descriptors.InterfaceAssociation, '!bbbbbbbb', ['bLength',
                                                                 'bDescriptorType',
                                                                 'bFirstInterface',
                                                                 'bInterfaceCount',
                                                                 'bFunctionClass',
                                                                 'bFunctionSubClass',
                                                                 'bFunctionProtocol',
                                                                 'iFunction']),
            (usb_descriptors.FunctionalDescriptor, '!bbb', ['bFunctionLength',
                                                            'bDescriptorType',
                                                            'bDescriptorSubType']),
            (usb_descriptors.UnionFunctionalDescriptor, '!bbbbb', ['bFunctionLength',
                                                                   'bDescriptorType',
                                                                   'bDescriptorSubType',
                                                                   'bControllerInterface',
                                                                   'bSubordinateInterface']),
            (usb_descriptors.ACMFunctionalDescriptor, '!bbbb', ['bFunctionLength',
                                                                'bDescriptorType',
                                                                'bDescriptorSubType',
                                                                'bmCapabilities']),
            (usb_descriptors.BaseDescriptor, '<bb', ['bLength', 'bDescriptorType']),
            (usb_descriptors.DeviceDescriptor, '!bbHbbbbHHHbbbb', ['bLength',
                                                                   'bDescriptorType',
                                                                   'bcdUSB',
                                                                   'bDeviceClass',
                                                                   'bDeviceSubClass',
                                                                   'bDevice Protocol',
                                                                   'bMaxPacketSize',
                                                                   'idVendor',
                                                                   'idProduct',
                                                                   'bcdDevice',
                                                                   'iManufacturer',
                                                                   'iProduct',
                                                                   'iSerialNumber',
                                                                   'bNumConfigurations']),
            (usb_descriptors.HeaderFunctionalDescriptor, '!bbbH', ['bFunctionLength',
                                                                   'bDescriptorType',
                                                                   'bDescriptorSubType',
                                                                   'bcdCDC']),
            (usb_descriptors.CallManagementFunctionalDescriptor, '!BBBBB', ['bFunctionLength',
                                                                            'bDescriptorType',
                                                                            'bDescriptorSubType',
                                                                            'bmCapabilities',
                                                                            'bDataInterface']),
            (usb_descriptors.EndPointDescriptor, '!bbbbHb', ['bLength',
                                                             'bDescriptorType',
                                                             'bEndpointAddress',
                                                             'bmAttributes',
                                                             'wMaxPacketSize',
                                                             'bInterval']),
            (usb_descriptors.StringDescriptor, '<bbw', ['bLength',
                                                        'bDescriptorType',
                                                        'wLanguage']),
        ]

        errors: list[str] = []
        for descriptor_class, fmt, args in descriptors:
            descriptor = descriptor_class()
            if descriptor.fmt != fmt:
                errors.append(f"{descriptor.__class__.__name__}, {descriptor.fmt} != {fmt}")
            if descriptor.args != args:
                errors.append(f"{descriptor.__class__.__name__}, {descriptor.args} != {args}")

        self.assertFalse(errors)  # display any discrepancies
