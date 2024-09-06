"""test the mock usbip server for basic behavior"""
import errno
import logging
import os
from socket import AF_INET, SHUT_RDWR, SOCK_STREAM, socket

from common_test_base import CommonTestBase
from mock_usbip import MockUSBDevice, MockUSBIP, ParseLSUSB, USBIPServerClient

from serial_usbipclient.protocol.packets import (CMD_SUBMIT, CMD_UNLINK,
                                                 OP_REQ_IMPORT, CommonHeader)
from serial_usbipclient.protocol.usbip_defs import Direction
from serial_usbipclient.tests.mock_usbip import MockDevice
from serial_usbipclient.usbip_client import USBIPClient

logger = logging.getLogger(__name__)


class TestMockUSBIPServer(CommonTestBase):
    """test the mock USBIP server"""
    def setUp(self):
        """initialize the port"""
        super().setUp()
        self.port += self.get_test_index(name=os.path.join(__file__, str(__class__.__name__), self._testMethodName))

    def test_mock_usbip_server_startup(self):
        """standup a server and check it out"""
        # verify we can start the listening thread and shut it down
        # before any client connects
        server: MockUSBIP = MockUSBIP(host=self.host, port=self.port)
        self.logger.info(f"MockUSBIP @{server.host}:{server.port}")
        server.shutdown()

    def test_mock_usbip_server_connection(self):
        """standup a server and check it out"""
        # verify we can start the listening thread and shut it down
        # before any client connects
        server: MockUSBIP = MockUSBIP(host=self.host, port=self.port)

        client: socket = socket(AF_INET, SOCK_STREAM)
        client.connect((self.host, self.port))
        server.shutdown()
        # shutdown the dangling client connection for clean exit
        try:
            client.shutdown(SHUT_RDWR)
            client.close()
        except OSError:  # safe to ignore
            pass

    def test_mocked_response(self):
        """test against mocked data responses"""
        server: MockUSBIP = MockUSBIP(host=self.host, port=self.port)

        client: USBIPClient = USBIPClient(remote=(self.host, self.port))
        client.connect_server()
        published = client.list_published()
        self.assertTrue(published.paths)
        self.assertEqual(len(published.paths), 4)  # should be 4 paths

        client.shutdown()
        server.shutdown()

    def test_reading_paths(self):
        """test reading the path information from the json file"""
        server: MockUSBIP = MockUSBIP(host=self.host, port=self.port)
        paths: list = server.read_paths()
        self.assertEqual(2, len(paths))


class TestDeviceConfiguration(CommonTestBase):
    """test setting up our device configuration"""
    def setUp(self):
        """initialize the port"""
        super().setUp()
        self.port += self.get_test_index(name=os.path.join(__file__, str(__class__.__name__), self._testMethodName))

    def test_lsusb_parsing(self):
        """test parsing the lsusb output file"""
        error: list[str] = []
        lsusb_parsed: ParseLSUSB = ParseLSUSB()
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
        parsed_devices: ParseLSUSB = ParseLSUSB()
        devices: MockUSBDevice = MockUSBDevice(parsed_devices.devices)
        devices.setup()  # create our USBIP protocol image
        response: bytes = devices.pack()
        print(f"{response.hex()=}")

        self.assertIsNotNone(devices.device(busnum=1, devnum=1))
        self.assertIsNone(devices.device(busnum=0, devnum=0))

    def test_server_timeout(self):
        """test timeout exception on server startup"""
        original_timeout: float = MockUSBIP.STARTUP_TIMEOUT
        MockUSBIP.STARTUP_TIMEOUT = -1.0
        with self.assertRaisesRegex(expected_exception=TimeoutError, expected_regex='Timed out waiting for USBIP server'):
            MockUSBIP(host='localhost', port=3240)
        MockUSBIP.STARTUP_TIMEOUT = original_timeout

    def test_unlink_no_device(self):
        """test if we unlink with an unrecognized device we get error"""
        self.mock_usbip = MockUSBIP(host=self.host, port=self.port)
        with self.assertRaisesRegex(expected_exception=ValueError, expected_regex='busnum=0/devnum=0 not found'):
            self.mock_usbip.unlink(message=CMD_UNLINK(seqnum=2, unlink_seqnum=1, devid=0).pack())

    def test_bad_urb_response(self):
        """test handling of bad URB response packet"""
        self.mock_usbip = MockUSBIP(host=self.host, port=self.port)
        client: USBIPServerClient = USBIPServerClient(connection=socket(), address=(self.host, self.port))
        client.busid = b'\01\02\03\04' + b'\0' * 4
        response: bytes = self.mock_usbip.mock_urb_responses(client=client, message=CMD_SUBMIT(seqnum=2, devid=0).pack())
        failed_response: CommonHeader = CommonHeader.unpack(response)
        self.assertEqual(failed_response.status, errno.ENODEV)

    def test_urb_read_no_device(self):
        """test handling of bad URB response packet"""
        self.mock_usbip = MockUSBIP(host=self.host, port=self.port)
        client: USBIPServerClient = USBIPServerClient(connection=socket(), address=(self.host, self.port))
        client.busid = b'\01\02\03\04' + b'\0' * 4
        with self.assertRaisesRegex(expected_exception=ValueError, expected_regex='busnum=0/devnum=0 not found'):
            self.mock_usbip.mock_urb_responses(client=client, message=CMD_SUBMIT(seqnum=2, devid=0, ep=1, direction=Direction.USBIP_DIR_IN).pack())

        with self.assertRaisesRegex(expected_exception=ValueError, expected_regex='busnum=0/devnum=0 not found'):
            self.mock_usbip.mock_urb_responses(client=client, message=CMD_SUBMIT(seqnum=2, devid=0, ep=1, direction=Direction.USBIP_DIR_OUT).pack())

    def test_bad_mock_response(self):
        """test that mock response returns proper exceptions"""
        self.mock_usbip = MockUSBIP(host=self.host, port=self.port)
        client: USBIPServerClient = USBIPServerClient(connection=socket(), address=(self.host, self.port))
        busid: bytes = b'\01\02\03\04' + b'\0'*28
        client.busid = bytes()
        with self.assertLogs(level='ERROR') as logs:
            self.mock_usbip.usb_devices.usbip = None
            self.mock_usbip.mock_response(client=client, message=OP_REQ_IMPORT(busid=busid).pack())
            self.assertTrue("REQ_IMPORT from unrecognized" in "".join(logs.output))

    def test_bad_mock_response_with_device(self):
        """test that mock response returns proper exceptions"""

        # we need to remove the device we are searching for from the server's list of usb devices
        # but leave it in the paths to generate this error, something that probably can never happen.

        self.mock_usbip = MockUSBIP(host=self.host, port=self.port)
        client: USBIPServerClient = USBIPServerClient(connection=socket(), address=(self.host, self.port))
        busid: bytes = b'1-3\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        client.busid = bytes()
        with self.assertRaisesRegex(expected_exception=ValueError, expected_regex='path.busnum=1/path.devnum=3 path not found!'):
            mock_device: MockDevice = self.mock_usbip.usb_devices.device(busnum=1, devnum=3)
            self.mock_usbip.usb_devices.devices.remove(mock_device)
            self.mock_usbip.mock_response(client=client, message=OP_REQ_IMPORT(busid=busid).pack())

    def test_bad_mock_response_no_device(self):
        """test if no device match found, nothing done"""
        self.mock_usbip = MockUSBIP(host=self.host, port=self.port)
        client: USBIPServerClient = USBIPServerClient(connection=socket(), address=(self.host, self.port))
        busid: bytes = b'1-4\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        client.busid = bytes()
        with self.assertLogs(level='WARNING') as logs:
            self.mock_usbip.mock_response(client=client, message=OP_REQ_IMPORT(busid=busid).pack())
            self.assertTrue("no response" in "".join(logs.output))

    def test_wait_for_response_improper_sockets(self):
        """test if we don't have appropriate sockets, wait fails"""
        self.mock_usbip = MockUSBIP(host=self.host, port=self.port)
        self.mock_usbip.shutdown()  # cleanup the server socket
        with self.assertRaisesRegex(expected_exception=ValueError, expected_regex='neither the wakeup or server socket can be empty'):
            self.mock_usbip.wait_for_message(conn=None)
