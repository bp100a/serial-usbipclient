"""test generation of URB packets"""
from typing import Optional

from tests.common_test_base import CommonTestBase
from tests.mock_usbip import MockUSBIP
from protocol.urb_packets import (GenericDescriptor, ConfigurationDescriptor, InterfaceDescriptor,
                                  CDCDescriptorSubType, EndPointDescriptor, StringDescriptor)
from protocol.packets import RET_SUBMIT_PREFIX

class TestURBPackets(CommonTestBase):
    """test URB packets"""
    def __init__(self, methodName):
        """set up local variables"""
        super().__init__(methodName)
        self.mock_usbip: MockUSBIP = MockUSBIP(host='', port=0, logger=self.logger)  # won't launch thread, just the instance

    def test_configuration_descriptor(self):
        """test the generation of the ConfigurationDescriptor"""
        request_config: bytes = bytes.fromhex('0000000100000003000900020000000100000000000002000000004b0000000000000000000000008006000200004b00')
        response: bytes = self.mock_usbip.mock_urb_responses(message=request_config, busid=b'1-1' + b'\0'*29)
        self.assertIsNotNone(response)
        header: RET_SUBMIT_PREFIX = RET_SUBMIT_PREFIX.unpack(response)

        generic_handler = GenericDescriptor()
        descriptor = generic_handler.packet(data=response[RET_SUBMIT_PREFIX.size:])
        self.assertIsNotNone(descriptor)

    def test_generate_configuration(self):
        """generate the configuration desc"""
        output: str = ''
        busid: bytes = b'1-1' + b'\0' * 29
        for device in self.mock_usbip.usb_devices.devices:
            if device.busid == busid:
                transfer_buffer: Optional[bytes] = None
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
                                output += f"    {CDCDescriptorSubType(descriptor.bDescriptorSubType).name}: {descriptor.pack().hex()}\n"
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
