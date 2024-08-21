"""test the mock usbip server for basic behavior"""
import logging
import os
from socket import AF_INET, SHUT_RDWR, SOCK_STREAM, socket

from common_test_base import CommonTestBase
from mock_usbip import MockUSBDevice, MockUSBIP, ParseLSUSB

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
        self.assertEqual(len(published.paths), 4)  # should be 4 paths

        client.shutdown()
        server.shutdown()

    def test_reading_paths(self):
        """test reading the path information from the json file"""
        host: str = 'localhost'
        port: int = 3240 + self.get_test_index(name=os.path.join(__file__, str(__class__.__name__), self._testMethodName))
        server: MockUSBIP = MockUSBIP(host=host, port=port, logger=self.logger)
        paths: list = server.read_paths()
        self.assertEqual(2, len(paths))


class TestDeviceConfiguration(CommonTestBase):
    """test setting up our device configuration"""
    def test_lsusb_parsing(self):
        """test parsing the lsusb output file"""
        error: list[str] = []
        lsusb_parsed: ParseLSUSB = ParseLSUSB(self.logger)
        self.assertTrue(lsusb_parsed)
        self.assertTrue(lsusb_parsed.devices)  # we have a device descriptor
        for usb in lsusb_parsed.devices:
            for configuration in usb.device.configurations:
                if configuration.bNumInterfaces != configuration.num_interfaces:
                    error.append(f"[0x{usb.vendor:04x}:0x{usb.product:04x}] Incorrect # interfaces "
                                 f"(expected {configuration.bNumInterfaces} found {len(configuration.interfaces)} "
                                 f"{configuration.descriptor_type.name=}")

        self.assertFalse(error)

    def test_usbip_path(self):
        """test we generate a USBIP path for our devices"""
        parsed_devices: ParseLSUSB = ParseLSUSB(self.logger)
        devices: MockUSBDevice = MockUSBDevice(parsed_devices.devices)
        devices.setup()  # create our USBIP protocol image
        response: bytes = devices.pack()
        print(f"{response.hex()=}")
