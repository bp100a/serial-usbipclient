"""test handling various strange responses from the socket"""
import json
import os
import socket
from socket import AddressFamily, SocketKind
from typing import Optional

from common_test_base import CommonTestBase

from serial_usbipclient import USBConnectionLostError, USBIPConnectionError, USBIPServerTimeoutError, USBIP_Connection
from serial_usbipclient.protocol.packets import OP_REP_DEVLIST_HEADER, BasicCommands, CommonHeader
from serial_usbipclient.socket_wrapper import SocketWrapper
from serial_usbipclient.usbip_client import HardwareID, USBIPClient


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


class GiaErrorSocketWrapper(MockSocketWrapper):
    """raise a gai error on connection"""
    def connect(self, address: tuple[str, int]):
        """raise a socket error"""
        raise socket.gaierror('mock error handling')


class TimeoutErrorSocketWrapper(MockSocketWrapper):
    """raise a timeout error on connection"""
    def connect(self, address: tuple[str, int]):
        """raise a socket error"""
        raise socket.timeout('timeout error handling')


class RecvOSErrorSocketWrapper(MockSocketWrapper):
    """raise an OSError (not a timeout) error on connection"""
    def recv(self, size: int) -> bytes:
        """raise our error"""
        raise OSError('mock error handling')


class URBErrorSocketWrapper(MockSocketWrapper):
    """raise error on URB"""

    def sendall(self, data: bytes) -> None:
        """sending data to the device"""
        super().sendall(data)
        header: CommonHeader = CommonHeader.unpack(data)
        if header.command == BasicCommands.CMD_SUBMIT:
            raise ValueError('fail URB request')


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

    def test_gai_error(self):
        """test handling the gai error"""
        self.client = USBIPClient(remote=(self.host, self.port), socket_class=GiaErrorSocketWrapper)
        with self.assertRaisesRegex(expected_exception=USBIPConnectionError, expected_regex='mock error handling'):
            self.client.connect_server()

    def test_timeout_error(self):
        """test handling the low-level socket timeout error"""
        self.client = USBIPClient(remote=(self.host, self.port), socket_class=TimeoutErrorSocketWrapper)
        with self.assertRaisesRegex(expected_exception=USBIPServerTimeoutError, expected_regex='connection attempt'):
            self.client.connect_server()

    def test_recv_error(self):
        """test handling the low-level socket oserror during recv"""
        self.client = USBIPClient(remote=(self.host, self.port), socket_class=RecvOSErrorSocketWrapper)
        self.client.connect_server()
        with self.assertRaisesRegex(expected_exception=USBConnectionLostError, expected_regex='connection lost'):
            self.client.list_published()  # trigger a read

    def test_restore_connection_no_device(self):
        """test failure modes when restoring a connection"""
        self.client.connect_server()
        published: OP_REP_DEVLIST_HEADER = self.client.list_published()
        no_device: USBIP_Connection = USBIP_Connection(devnum=published.paths[0].devnum, busnum=published.paths[0].busnum)
        with self.assertRaisesRegex(expected_exception=ValueError, expected_regex='no connection to restore'):
            self.client.restore_connection(lost_usb=no_device)

    def test_restore_connection(self):
        """test failure modes when restoring a connection"""
        self.client = USBIPClient(remote=(self.host, self.port), socket_class=URBErrorSocketWrapper)
        self.client.connect_server()
        published: OP_REP_DEVLIST_HEADER = self.client.list_published()
        lost_usb: USBIP_Connection = USBIP_Connection(devnum=published.paths[0].devnum,
                                                      busnum=published.paths[0].busnum,
                                                      seqnum=0,
                                                      device=HardwareID(published.paths[0].idVendor, published.paths[0].idProduct),
                                                      sock=MockSocketWrapper(family=socket.AF_INET, kind=socket.SOCK_STREAM))

        with self.assertRaisesRegex(expected_exception=ValueError, expected_regex='Attach error'):
            self.client.restore_connection(lost_usb=lost_usb)
