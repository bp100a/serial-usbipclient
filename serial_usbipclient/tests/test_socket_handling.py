"""test handling various strange responses from the socket"""
import os
import json
from typing import cast, Optional
from socket import AddressFamily, SocketKind

from serial_usbipclient.socket_wrapper import SocketWrapper

from common_test_base import CommonTestBase
from serial_usbipclient.usbip_client import USBIPClient, HardwareID
from serial_usbipclient.protocol.packets import OP_REP_DEVLIST_HEADER, BasicCommands, CommonHeader


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


class TestSocketWrapper(CommonTestBase):
    """test injected failures"""
    def __init__(self, methodName):
        """set up local variables"""
        super().__init__(methodName)
        self.client: Optional[USBIPClient] = None

    def setUp(self):
        """initialize for tests"""
        self.client = USBIPClient(remote=(self.host, self.port), socket_class=MockSocketWrapper)

    def tearDown(self):
        """clean up after tests"""
        if self.client:
            self.client.shutdown()

    def test_connection(self):
        """Test connecting to a mocked remote"""
        self.client.connect_server()
        self.assertTrue(isinstance(self.client.usbipd, MockSocketWrapper))
        socket: MockSocketWrapper = cast(MockSocketWrapper, self.client.usbipd)

    def test_list_published(self):
        """test attaching via MockSocketWrapper"""
        self.client.connect_server()
        published: OP_REP_DEVLIST_HEADER = self.client.list_published()
        self.assertEqual(len(published.paths), 2)  # should have 2 paths

    def test_attachment(self):
        """test we can attach to a device"""
        self.client.connect_server()

        with self.assertRaisesRegex(expected_exception=ValueError, expected_regex='Attach error'):
            self.client.attach(devices=[HardwareID(vid=0x525, pid=0xa4a7)])
