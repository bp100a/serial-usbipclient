"""test the mock usbip server for basic behavior"""

from unittest import TestCase
from socket import socket, AF_INET, SOCK_STREAM
import logging

from mock_usbip import MockUSBIP


logger = logging.getLogger(__name__)


class TestMockUSBIPServer(TestCase):
    """test the mock USBIP server"""
    def test_mock_usbip_server_startup(self):
        """standup a server and check it out"""
        # verify we can start the listening thread and shut it down
        # before any client connects
        server: MockUSBIP = MockUSBIP(host='localhost', port=3241)
        server.shutdown()

    def test_mock_usbip_server_connection(self):
        """standup a server and check it out"""
        # verify we can start the listening thread and shut it down
        # before any client connects
        host: str = 'localhost'
        port: int = 3241
        server: MockUSBIP = MockUSBIP(host=host, port=port)

        client: socket = socket(AF_INET, SOCK_STREAM)
        client.connect((host, port))
        server.shutdown()
