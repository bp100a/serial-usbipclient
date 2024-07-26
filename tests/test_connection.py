from tests.common_test_base import CommonTestBase

from usbip_client import USBIPClient


class TestUSBIPConnection(CommonTestBase):
    """test connections to a USBIP service"""
    def test_connection(self):
        """test simple connection"""
        self.skip_on_ci()  # don't run this test on a CI/CD system
        client: USBIPClient = USBIPClient(remote=('192.168.1.32', 3240))
        client.connect_server()
        published = client.list_published()
        self.assertTrue(published.paths)
