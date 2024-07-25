from unittest import TestCase

from usbip_client import USBIPClient


class TestUSBIPConnection(TestCase):
    """test connections to a USBIP service"""
    def test_connection(self):
        """test simple connection"""
        client: USBIPClient = USBIPClient(remote=('192.168.1.32', 3240))
        client.connect_server()
        published = client.list_published()
        self.assertTrue(published.paths)
