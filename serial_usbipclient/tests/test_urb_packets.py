"""test generation of URB packets"""
import socket

from common_test_base import CommonTestBase
from mock_usbip import MockUSBIP, USBIPClient

from serial_usbipclient.protocol.packets import RET_SUBMIT_PREFIX
from serial_usbipclient.protocol.urb_packets import (CDCDescriptorSubType,
                                                     ConfigurationDescriptor,
                                                     EndPointDescriptor,
                                                     GenericDescriptor,
                                                     InterfaceDescriptor,
                                                     StringDescriptor, InterfaceAssociation)


class MockUSBIPClient(USBIPClient):
    """fake usbipclient for testing"""
    def __init__(self, busid: bytes):
        """set up local variables"""
        super().__init__(connection=socket.socket(), address=('', 0), size=0)
        self.busid = busid


class TestURBPackets(CommonTestBase):
    """test URB packets"""
    def __init__(self, methodName):
        """set up local variables"""
        super().__init__(methodName)
        self.mock_usbip: MockUSBIP = MockUSBIP(host='', port=0)  # won't launch thread, just the instance

    def test_configuration_descriptor(self):
        """test the generation of the ConfigurationDescriptor"""
        request_config: bytes = bytes.fromhex('0000000100000003000900020000000100000000'
                                              '000002000000004b0000000000000000000000008006000200004b00')
        mock_client: MockUSBIPClient = MockUSBIPClient(busid=b'1-1' + b'\0'*29)
        response: bytes = self.mock_usbip.mock_urb_responses(mock_client, message=request_config)
        self.assertIsNotNone(response)
        RET_SUBMIT_PREFIX.unpack(response)  # verify it's legit

        generic_handler = GenericDescriptor()
        descriptor = generic_handler.packet(data=response[RET_SUBMIT_PREFIX.size:])
        self.assertIsNotNone(descriptor)

    def test_generate_configuration(self):
        """generate the configuration desc"""
        output: str = ''
        busid: bytes = b'1-1' + b'\0' * 29
        for device in self.mock_usbip.usb_devices.devices:
            if device.busid == busid:
                configuration: ConfigurationDescriptor = device.device.configurations[0]
                output += f"\nConfigurationDesc: {configuration.pack().hex()}\n"
                interface_offset: int = 0
                for association in configuration.associations:
                    output += f"  InterfaceAssociation: {association.pack().hex()}\n"
                    for i in range(0, association.bInterfaceCount):
                        interface: InterfaceDescriptor = configuration.interfaces[i + interface_offset]
                        output += f"  Interface: {interface.pack().hex()}\n"
                        for descriptor in interface.descriptors:
                            if not isinstance(descriptor, EndPointDescriptor):
                                output += (f"    {CDCDescriptorSubType(descriptor.bDescriptorSubType).name}: "
                                           f"{descriptor.pack().hex()}\n")
                            else:
                                output += f"    EndPoint: {descriptor.pack().hex()}\n"

                    interface_offset += association.bInterfaceCount
        print(output)

    def test_descriptor_handlers(self):
        """test handling the descriptors"""
        string_desc: bytes = b'\x04\x03\t\x04'  # bLength=4, bDescriptorType=3, wLanguage=0x0904 (supports only english)
        generic_handler: GenericDescriptor = GenericDescriptor()
        descriptor = generic_handler.packet(data=string_desc)
        self.assertTrue(isinstance(descriptor, StringDescriptor))

    def test_endpoint_descriptor_handlers(self):
        """test endpoint descriptors"""
        endpoint_desc: bytes = bytes.fromhex('07058303080020')
        generic_handler: GenericDescriptor = GenericDescriptor()
        descriptor = generic_handler.packet(data=endpoint_desc)
        self.assertTrue(isinstance(descriptor, EndPointDescriptor))
        self.assertEqual(repr(descriptor), "bEndpointAddress=0x83[IN #3], bDescriptorType=ENDPOINT_DESCRIPTOR")

    def test_interface_association_handlers(self):
        """test interface associations"""
        ia_desc: bytes = bytes.fromhex('080b020108065000')
        generic_handler: GenericDescriptor = GenericDescriptor()
        descriptor = generic_handler.packet(data=ia_desc)
        self.assertTrue(isinstance(descriptor, InterfaceAssociation))
