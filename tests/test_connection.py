from typing import Optional
from tests.common_test_base import CommonTestBase

from usbip_client import USBIPClient, HardwareID, MBIUSBAttachError, USBIP_Connection
from tests.mock_usbip import MockUSBIP


class TestUSBIPConnection(CommonTestBase):
    """test connections to a USBIP service"""
    def __init__(self, methodName):
        """set up local variables"""
        super().__init__(methodName)
        self.host: str = 'localhost'
        self.port: int = 3244
        self.mock_usbip: Optional[MockUSBIP] = None

    def setUp(self):
        """set up our connection test"""
        super().setUp()
        self.mock_usbip = MockUSBIP(host=self.host, port=self.port, logger=self.logger)

    def tearDown(self):
        """clean up after test"""
        if self.mock_usbip:
            self.mock_usbip.shutdown()
            self.mock_usbip = None

        super().tearDown()

    def test_connection(self):
        """test simple connection"""
        self.skip_on_ci()  # having issues running on GitHub Actions
        client: USBIPClient = USBIPClient(remote=(self.host, self.port), logger=self.logger)
        client.connect_server()
        published = client.list_published()
        self.assertTrue(published.paths)
        vid: int = 0x525
        pid: int = 0xA4A7

        try:
            client.attach(devices=[HardwareID(vid, pid)], published=published)
            connections: list[USBIP_Connection] = client.get_connection(device=HardwareID(vid, pid))
            self.assertEqual(len(connections), 1)  # should be a single connection
        except MBIUSBAttachError as a_error:
            self.logger.error(a_error.detail)
            raise
