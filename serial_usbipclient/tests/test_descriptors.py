
from common_test_base import CommonTestBase

import serial_usbipclient.protocol.urb_packets as urb


class TestInterfaceDescriptor(CommonTestBase):
    """test the formatting of the interface descriptor"""

    def test_descriptors(self):
        """test the descriptors"""
        descriptors: list[tuple[callable, str, list[str]]] = [
            (urb.InterfaceDescriptor, '<bbbbbbbbb', ['bLength',
                                                     'bDescriptorType',
                                                     'bInterfaceNumber',
                                                     'bAlternateSetting',
                                                     'bNumEndpoints',
                                                     'bInterfaceClass',
                                                     'bInterfaceSubClass',
                                                     'bInterfaceProtocol',
                                                     'iInterface']),
            (urb.ConfigurationDescriptor, '<bbHbbbbb', ['bLength',
                                                        'bDescriptorType',
                                                        'wTotalLength',
                                                        'bNumInterfaces',
                                                        'bConfigurationValue',
                                                        'iConfiguration',
                                                        'bmAttributes',
                                                        'bMaxPower']),
            (urb.InterfaceAssociation, '<bbbbbbbb', ['bLength',
                                                     'bDescriptorType',
                                                     'bFirstInterface',
                                                     'bInterfaceCount',
                                                     'bFunctionClass',
                                                     'bFunctionSubClass',
                                                     'bFunctionProtocol',
                                                     'iFunction']),
            (urb.FunctionalDescriptor, '<bbb', ['bFunctionLength',
                                                'bDescriptorType',
                                                'bDescriptorSubType']),
            (urb.UnionFunctionalDescriptor, '<bbbbb', ['bFunctionLength',
                                                       'bDescriptorType',
                                                       'bDescriptorSubType',
                                                       'bMasterInterface',
                                                       'bSlaveInterface']),
            (urb.ACMFunctionalDescriptor, '<bbbb', ['bFunctionLength',
                                                    'bDescriptorType',
                                                    'bDescriptorSubType',
                                                    'bmCapabilities']),
            (urb.BaseDescriptor, '<bb', ['bLength', 'bDescriptorType']),
            (urb.DeviceDescriptor, '<bbHbbbbHHHbbbb', ['bLength',
                                                       'bDescriptorType',
                                                       'bcdUSB',
                                                       'bDeviceClass',
                                                       'bDeviceSubClass',
                                                       'bDeviceProtocol',
                                                       'bMaxPacketSize',
                                                       'idVendor',
                                                       'idProduct',
                                                       'bcdDevice',
                                                       'iManufacturer',
                                                       'iProduct',
                                                       'iSerial',
                                                       'bNumConfigurations']),
            (urb.HeaderFunctionalDescriptor, '<bbbH', ['bFunctionLength',
                                                       'bDescriptorType',
                                                       'bDescriptorSubType',
                                                       'bcdCDC']),
            (urb.CallManagementFunctionalDescriptor, '<BBBBB', ['bFunctionLength',
                                                                'bDescriptorType',
                                                                'bDescriptorSubType',
                                                                'bmCapabilities',
                                                                'bDataInterface']),
            (urb.EndPointDescriptor, '<bbbbHb', ['bLength',
                                                 'bDescriptorType',
                                                 'bEndpointAddress',
                                                 'bmAttributes',
                                                 'wMaxPacketSize',
                                                 'bInterval']),
            (urb.StringDescriptor, '<bbh', ['bLength',
                                            'bDescriptorType',
                                            'wLanguage']),
        ]

        errors: list[str] = []
        for descriptor_class, fmt, args in descriptors:
            descriptor = descriptor_class()
            descriptor_fmt: str = descriptor.config().endianness.value + "".join([item[1].fmt for item in descriptor.fields()])
            if descriptor_fmt.upper() != fmt.upper():
                errors.append(f"{descriptor.__class__.__name__} {fmt.upper()} does not match {descriptor_fmt.upper()}\n")
            not_found: list[str] = [item for item in args if item not in dir(descriptor)]
            if not_found:
                errors.append(f"{descriptor.__class__.__name__}, not found{not_found}\n")

        self.assertFalse(errors)  # display any discrepancies
