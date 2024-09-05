"""base for all unit tests"""

import json
import logging
import os
import re
import sys
from os import getenv
from socket import AddressFamily, SocketKind
from typing import Optional
from unittest import TestCase

from mock_usbip import MockUSBIP

from serial_usbipclient.protocol.packets import BasicCommands, CommonHeader
from serial_usbipclient.usbip_client import SocketWrapper, USBIPClient

LOG_FORMAT: str = '%(asctime)s\t%(levelname)s \t[%(filename)s:%(lineno)d] - %(message)s'
logging.basicConfig(
    force=True,
    level=logging.DEBUG,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(stream=sys.stdout), logging.StreamHandler(stream=sys.stderr)],
)


class CommonTestBase(TestCase):
    """base class for common behavior to all unit tests"""
    DEFAULT_USBIP_SERVER_PORT: int = 3240

    @staticmethod
    def is_truthy(key: str, default: bool) -> bool:
        """read environment variable, return boolean response"""
        value: str = getenv(key, default=str(default)).upper()
        return value in ['TRUE', '1', '1.0']

    def skip_on_ci(self, reason='incompatible with CI'):
        """skip the test if running on a CI/CD system"""
        if self.continuous_integration:
            self.skipTest(reason=reason)

    def __init__(self, methodName):
        """need some special variables"""
        self.continuous_integration: bool = CommonTestBase.is_truthy('CI', False)
        self.mock_usbip: Optional[MockUSBIP] = None
        self.client: Optional[USBIPClient] = None
        self.host: str = 'localhost'
        self.port: int = self.DEFAULT_USBIP_SERVER_PORT  # will be updated by subclasses
        self.logger: logging.Logger = logging.getLogger(__name__)
        super().__init__(methodName)

        if methodName != 'runTest':
            self.logger.info(f"running {methodName}")

        self.runner_instance: str = os.getenv('PYTEST_XDIST_WORKER', '1')
        self.worker_id: int = int(re.findall(r"(\d+)$", self.runner_instance)[0]) if self.runner_instance else 0

    @staticmethod
    def get_test_index(name: str) -> int:
        """get index of test, can be used as offset for port assignments"""
        qualified_name: str = name.replace(os.sep, '.').lower()
        with open(os.path.join(os.path.dirname(__file__), 'list_of_tests.json'), 'r', encoding='utf-8') as tests:
            all_tests: dict = json.load(tests)

        for i in range(len(all_tests)):
            if qualified_name.endswith(all_tests[i]):
                return i + 1

        raise ValueError(f"{name=}, {qualified_name=}, {all_tests=}")

    def tearDown(self):
        """clean up after test"""
        if self.mock_usbip:
            try:
                self.mock_usbip.shutdown()
            except TimeoutError:
                pass
            self.mock_usbip = None

        super().tearDown()


class MockSocketWrapper(SocketWrapper):
    """for injecting and managing a fake connection"""
    def __init__(self, family: AddressFamily, kind: SocketKind):
        """set up local variables"""
        super().__init__(family, kind)
        self._protocol_responses: dict[str, bytes] = {}
        data_path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'usbip_packets.json')
        with open(file=data_path, mode='r', encoding='utf-8') as recording:
            self._protocol_responses = json.loads(recording.read())
        self.send_data: list[bytes] = []  # track commands that were sent
        self.response_data: bytes = bytes()  # buffered responses based on commands sent

    def connect(self, address: tuple[str, int]):
        """mock connection"""
        self._address = address

    def getsockname(self) -> tuple[str, int]:
        """return the socket name"""
        return self._address

    def shutdown(self, how: int) -> None:
        """perform mock shutdown"""
        return

    def sendall(self, data: bytes) -> None:
        """sending data to the device"""
        self.send_data.append(data)
        header: CommonHeader = CommonHeader.unpack(data)
        response_key: str = ''
        if header.command == BasicCommands.REQ_DEVLIST:  # asking for the device list
            response_key = 'OP_REP_DEVLIST'
        elif header.command == BasicCommands.REQ_IMPORT:
            response_key = 'OP_REP_IMPORT'
        if response_key:
            self.response_data += bytes.fromhex("".join([item for item in self._protocol_responses[response_key]]))

    def recv(self, size: int) -> bytes:
        """return data corresponding to last send"""
        if self.response_data:
            if len(self.response_data) < size:
                size = len(self.response_data)
            response: bytes = self.response_data[:size]
            self.response_data = self.response_data[size:]
            return response

        return bytes()
