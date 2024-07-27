from tests.common_test_base import CommonTestBase

from usbip_client import USBIPClient, HardwareID, MBIUSBAttachError


class TestUSBIPConnection(CommonTestBase):
    """test connections to a USBIP service"""
    def test_connection(self):
        """test simple connection"""
        self.skip_on_ci()  # don't run this test on a CI/CD system
        client: USBIPClient = USBIPClient(remote=('192.168.1.32', 3240), logger=self.logger)
        client.connect_server()
        published = client.list_published()
        self.assertTrue(published.paths)
        vid: int = 0x525
        pid: int = 0xA4A7

        try:
            client.attach(devices=[HardwareID(vid, pid)], published=published)
        except MBIUSBAttachError as a_error:
            self.logger.error(a_error.detail)
            raise
