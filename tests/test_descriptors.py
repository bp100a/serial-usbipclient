from unittest import TestCase

from usb_descriptors import InterfaceDescriptor


class TestInterfaceDescriptor(TestCase):
    """test the formatting of the interface descriptor"""

    def test_interface_descriptor(self):
        """test the interface descriptor"""
        if_descriptor = InterfaceDescriptor()
        self.assertTrue(if_descriptor.fmt, "should have formatting string!")
        self.assertEqual(if_descriptor.fmt, '!bbbbbbbbb', 'incorrect formatting string')
        self.assertEqual(if_descriptor.args, ['bLength',
                                              'bDescriptorType',
                                              'bInterfaceNumber',
                                              'bAlternateSetting',
                                              'bNumEndpoints',
                                              'bInterfaceClass',
                                              'bInterfaceSubClass',
                                              'bInterfaceProtocol',
                                              'iInterface'], 'incorrect argument list')
