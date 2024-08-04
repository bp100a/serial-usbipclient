from typing import Optional
from tests.common_test_base import CommonTestBase
import os

from protocol.packets import OP_REP_DEVLIST_HEADER
from usbip_client import USBIPClient, HardwareID, USBAttachError, USBIP_Connection
from tests.mock_usbip import MockUSBIP


class TestUSBIPConnection(CommonTestBase):
    """test connections to a USBIP service"""
    def __init__(self, methodName):
        """set up local variables"""
        super().__init__(methodName)
        self.host: str = 'localhost'
        self.port: int = 3244
        self.mock_usbip: Optional[MockUSBIP] = None
        self.client: Optional[USBIPClient] = None

        # this is the 8.8 inch Turing smart screen (CPU monitor)
        self.vid: int = 0x525  # Netchip Technology, Inc.
        self.pid: int = 0xA4A7 # Linux-USB Serial Gadget (CDC ACM mode)
        self.hardware_id: HardwareID = HardwareID(vid=self.vid, pid=self.pid)

    def setUp(self):
        """set up our connection test"""
        super().setUp()
        self.port += self.get_test_index(name=os.path.join(__file__, str(__class__.__name__), self._testMethodName))
        self.mock_usbip = MockUSBIP(host=self.host, port=self.port, logger=self.logger)

    def tearDown(self):
        """clean up after test"""
        if self.mock_usbip:
            self.mock_usbip.shutdown()
            self.mock_usbip = None

        super().tearDown()

    def test_connection(self):
        """test simple connection"""
        if not self.CI:
            # run against a "real" USBIPD service when not in the CI environment
            self.port = self.DEFAULT_USBIP_SERVER_PORT

        published: OP_REP_DEVLIST_HEADER = self.connect_server()
        self.assertTrue(published.paths)

        try:
            self.client.attach(devices=[self.hardware_id], published=published)
            connections: list[USBIP_Connection] = self.client.get_connection(device=self.hardware_id)
            self.assertEqual(len(connections), 1)  # should be a single connection
        except USBAttachError as a_error:
            self.logger.error(a_error.detail)
            raise

    def connect_server(self) -> OP_REP_DEVLIST_HEADER:
        """connect to the USBIP server"""
        self.client: USBIPClient = USBIPClient(remote=(self.host, self.port), logger=self.logger)
        self.client.connect_server()
        return self.client.list_published()

    def test_connection_shutdown(self):
        """test shutting down the connection"""
        self.port = self.port + 1
        published: OP_REP_DEVLIST_HEADER = self.connect_server()
        self.assertTrue(published.paths)
        try:
            self.client.attach(devices=[self.hardware_id], published=published)
            connections: list[USBIP_Connection] = self.client.get_connection(device=self.hardware_id)
            self.assertEqual(len(connections), 1)  # should be a single connection
            self.client.shutdown()  # shut it all down
        except USBAttachError as a_error:
            self.logger.error(a_error.detail)
            raise

    def test_queue_urbs(self):
        """test queue urbs to the server"""
        self.skip_on_ci(reason="not yet fully implemented")
        self.port = self.port + 2
        published: OP_REP_DEVLIST_HEADER = self.connect_server()
        self.assertTrue(published.paths)
        try:
            self.client.attach(devices=[self.hardware_id], published=published)
            connections: list[USBIP_Connection] = self.client.get_connection(device=self.hardware_id)
            self.assertEqual(len(connections), 1)  # should be a single connection
            self.client.queue_urbs(usb=connections[0])
            self.client.shutdown()  # shut it all down
        except USBAttachError as a_error:
            self.logger.error(a_error.detail)
            raise
