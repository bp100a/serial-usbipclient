"""test we can read/write the MockUSBIP device via the usbip client"""
import logging
import os
from typing import Optional

import serial_usbipclient.usbip_client
from common_test_base import CommonTestBase
from mock_usbip import MockUSBIP

from serial_usbipclient.protocol.packets import OP_REP_DEVLIST_HEADER
from serial_usbipclient.usbip_client import HardwareID, USBIP_Connection, USBIPClient, USBConnectionLostError

logger = logging.getLogger(__name__)


class TestReadWrite(CommonTestBase):
    """test reading/writing a mock USBIP device"""
    def __init__(self, methodName):
        """set up local variables"""
        super().__init__(methodName)

        # this is the 8.8 inch Turing smart screen (CPU monitor)
        self.vid: int = 0x525  # Netchip Technology, Inc.
        self.pid: int = 0xA4A7 # Linux-USB Serial Gadget (CDC ACM mode)
        self.hardware_id: HardwareID = HardwareID(vid=self.vid, pid=self.pid)

    def setUp(self):
        """set up our connection test"""
        super().setUp()
        self.port += self.get_test_index(name=os.path.join(__file__, str(__class__.__name__), self._testMethodName))
        self.mock_usbip = MockUSBIP(host=self.host, port=self.port, logger=self.logger)

    def _connect(self) -> USBIP_Connection:
        """connect to the USBIPD server"""
        if self.mock_usbip is None:
            self.mock_usbip: MockUSBIP = MockUSBIP(host=self.host, port=self.port, logger=self.logger)

        self.client = USBIPClient(remote=(self.host, self.port), logger=self.logger)
        self.client.connect_server()
        published: OP_REP_DEVLIST_HEADER = self.client.list_published()
        self.client.attach(devices=[self.hardware_id], published=published)
        connections: list[USBIP_Connection] = self.client.get_connection(device=self.hardware_id)
        return connections[0]

    def test_read_write(self):
        """read data from the faux device and verify it"""
        usb: USBIP_Connection = self._connect()
        test_data: list[bytes] = [b'\01\02\03\04', b'\0x55' * 10, b'\0xaa'*15]
        errors: list[str] = []
        for data in test_data:
            self.client.send(usb=usb, data=data)  # send URB writing data to device
            response: bytes = usb.response_data(size=len(data))  # waits for pending URB response from queued URBs
            if data != response:
                errors.append(f"{data.hex()=} != {response.hex()=}")

        self.assertFalse(errors)  # all data responses should match

    def test_delimited_read(self):
        """test we can read with a delimiter"""
        usb: USBIP_Connection = self._connect()
        test_data: list[bytes] = [b'\01\02\03\04', b'\0x55' * 10, b'\0xaa'*15]
        errors: list[str] = []
        for delimiter in [b'\r\n', b'\n', b'\0']:
            usb.delimiter = delimiter
            for data in test_data:
                data += delimiter
                self.client.send(usb=usb, data=data)  # send URB writing data to device
                response: bytes = usb.response_data(size=0)  # wait for delimiter
                if data != response:
                    errors.append(f"{data.hex()=} != {response.hex()=}")

        self.assertFalse(errors)  # all data responses should match

    def test_readline(self):
        """test we can read delimited strings"""
        usb: USBIP_Connection = self._connect()
        test_data: list[bytes] = [b'string']
        errors: list[str] = []
        for delimiter in [b'\r\n', b'\n', b'\r']:
            usb.delimiter = delimiter
            for data in test_data:
                data += delimiter
                self.client.send(usb=usb, data=data)  # send URB writing data to device
                response: str = USBIPClient.readline(usb)  # wait for delimiter
                if data.strip(delimiter) != response.encode('utf-8'):
                    errors.append(f"{data.hex()=} != {response=}")

        self.assertFalse(errors)  # all data responses should match

    def test_read_timeout(self):
        """test we time out on empty reads"""
        usb: USBIP_Connection = self._connect()
        # with self.assertRaisesRegex(expected_exception=TimeoutError, expected_regex='timeout'):
        #     usb.response_data(size=12)  # shouldn't be any data for us, time out!
        with self.assertRaisesRegex(expected_exception=USBConnectionLostError,
                                    expected_regex='connection lost'):
            usb.response_data(size=12)  # shouldn't be any data for us, time out!

    def test_restore_connection(self):
        """test we can restore lost connections"""
        self.skip_on_ci(reason='not ready for prime time')
        usb: USBIP_Connection = self._connect()
        restored_usb: Optional[USBIP_Connection] = self.client.restore_connection(lost_usb=usb)
        self.assertIsNotNone(restored_usb)
