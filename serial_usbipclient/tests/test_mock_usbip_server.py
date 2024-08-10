"""test the mock usbip server for basic behavior"""
import os
from socket import socket, AF_INET, SOCK_STREAM, SHUT_RDWR
import logging

from common_test_base import CommonTestBase
from mock_usbip import MockUSBIP, Parse_lsusb, MockUSBDevice

from serial_usbipclient.usbip_client import USBIPClient

logger = logging.getLogger(__name__)


class TestMockUSBIPServer(CommonTestBase):
    """test the mock USBIP server"""
    def test_mock_usbip_server_startup(self):
        """standup a server and check it out"""
        # verify we can start the listening thread and shut it down
        # before any client connects
        port: int = 3240 + self.get_test_index(name=os.path.join(__file__, str(__class__.__name__), self._testMethodName))
        server: MockUSBIP = MockUSBIP(host='localhost', port=port, logger=self.logger)
        self.logger.info(f"MockUSBIP @{server.host}:{server.port}")
        server.shutdown()

    def test_mock_usbip_server_connection(self):
        """standup a server and check it out"""
        # verify we can start the listening thread and shut it down
        # before any client connects
        host: str = 'localhost'
        port: int = 3240 + self.get_test_index(name=os.path.join(__file__, str(__class__.__name__), self._testMethodName))
        server: MockUSBIP = MockUSBIP(host=host, port=port, logger=self.logger)

        client: socket = socket(AF_INET, SOCK_STREAM)
        client.connect((host, port))
        server.shutdown()
        # shutdown the dangling client connection for clean exit
        try:
            client.shutdown(SHUT_RDWR)
            client.close()
        except OSError:  # safe to ignore
            pass

    def test_mocked_response(self):
        """test against mocked data responses"""
        host: str = 'localhost'
        port: int = 3240 + self.get_test_index(name=os.path.join(__file__, str(__class__.__name__), self._testMethodName))
        server: MockUSBIP = MockUSBIP(host=host, port=port, logger=self.logger)

        client: USBIPClient = USBIPClient(remote=(host, port), logger=self.logger)
        client.connect_server()
        published = client.list_published()
        self.assertTrue(published.paths)
        self.assertEqual(len(published.paths), 2)  # should be 2 paths

        client.shutdown()
        server.shutdown()

    def test_reading_paths(self):
        """test reading the path information from the json file"""
        host: str = 'localhost'
        port: int = 3240 + self.get_test_index(name=os.path.join(__file__, str(__class__.__name__), self._testMethodName))
        server: MockUSBIP = MockUSBIP(host=host, port=port, logger=self.logger)
        paths: list = server.read_paths()


class TestDeviceConfiguration(CommonTestBase):
    """test setting up our device configuration"""
    def test_lsusb_parsing(self):
        """test parsing the lsusb output file"""
        error: list[str] = []
        lsusb_parsed: Parse_lsusb = Parse_lsusb(self.logger)
        self.assertTrue(lsusb_parsed)
        self.assertTrue(lsusb_parsed.devices)  # we have a device descriptor
        for usb in lsusb_parsed.devices:
            for configuration in usb.device.configurations:
                if configuration.bNumInterfaces != len(configuration.interfaces):
                    error.append(f"[0x{usb.vendor:0x4x}:0x{usb.product:0x4x}] Incorrect # interfaces {configuration.descriptor_type.name=}")

        self.assertFalse(error)

    def test_usbip_path(self):
        """test we generate a USBIP path for our devices"""
        parsed_devices: Parse_lsusb = Parse_lsusb(self.logger)
        devices: MockUSBDevice = MockUSBDevice(parsed_devices.devices)
        devices.setup()  # create our USBIP protocol image
        response: bytes = devices.pack()
        print(f"{response.hex()=}")