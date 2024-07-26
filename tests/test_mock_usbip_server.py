"""test the mock usbip server for basic behavior"""

from socket import socket, AF_INET, SOCK_STREAM, SHUT_RDWR
import logging

from tests.common_test_base import CommonTestBase
from mock_usbip import MockUSBIP


logger = logging.getLogger(__name__)


class TestMockUSBIPServer(CommonTestBase):
    """test the mock USBIP server"""
    def test_mock_usbip_server_startup(self):
        """standup a server and check it out"""
        # verify we can start the listening thread and shut it down
        # before any client connects
        server: MockUSBIP = MockUSBIP(host='localhost', port=3241, logger=self.logger)
        self.logger.info(f"MockUSBIP @{server.host}:{server.port}")
        server.shutdown()

    def test_mock_usbip_server_connection(self):
        """standup a server and check it out"""
        # verify we can start the listening thread and shut it down
        # before any client connects
        host: str = 'localhost'
        port: int = 3242
        server: MockUSBIP = MockUSBIP(host=host, port=port, logger=self.logger)

        client: socket = socket(AF_INET, SOCK_STREAM)
        client.connect((host, port))
        server.shutdown()
        # shutdown the dangling client connection for clean exit
        client.shutdown(SHUT_RDWR)
        client.close()
