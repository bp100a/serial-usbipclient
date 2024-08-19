"""test we can read/write the MockUSBIP device via the usbip client"""
import errno
import logging
import os
from typing import Optional

from common_test_base import CommonTestBase
from mock_usbip import MockUSBIP

from serial_usbipclient.protocol.packets import OP_REP_DEVLIST_HEADER
from serial_usbipclient.usbip_client import (HardwareID, USBIP_Connection, USBIPClient,
                                             PAYLOAD_TIMEOUT, USBIPResponseTimeoutError, USBAttachError)

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

    def test_write_string(self):
        """test we can read with a delimiter"""
        usb: USBIP_Connection = self._connect()
        test_data: list[str] = ['test-string\r\n']
        errors: list[str] = []
        for data in test_data:
            self.client.send(usb=usb, data=data)  # send URB writing data to device
            response: bytes = usb.response_data(size=0)  # wait for delimiter
            if data != response.decode('utf-8'):
                errors.append(f"{data.encode('utf-8').hex()=} != {response.hex()=}")

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
        with self.assertRaisesRegex(expected_exception=USBIPResponseTimeoutError,
                                    expected_regex='Timeout error'):
            usb.response_data(size=12)  # shouldn't be any data for us, time out!

    def test_restore_connection(self):
        """test we can restore lost connections"""
        usb: USBIP_Connection = self._connect()
        self.assertEqual(self.client.command_timeout, PAYLOAD_TIMEOUT)
        restored_usb: Optional[USBIP_Connection] = self.client.restore_connection(lost_usb=usb)
        self.assertIsNotNone(restored_usb)

    def test_timeout_error(self):
        """test formatting of the timeout error"""
        error = USBIPResponseTimeoutError(timeout=0.2, request=b'\01\02', size=3)
        self.assertEqual(str(error), 'Timeout error, timeout=0.2, request=0102, size=3')

        error = USBAttachError(detail='a failure', an_errno=errno.EPIPE)
        self.assertEqual(str(error), "a failure, self.errno=32/EPIPE, "
                                     "The pipe type specified in the URB doesn't match the endpoint’s actual type.")

    def test_hardware_id_formatting(self):
        """simple test to get coverage on the HardwareID"""
        hw_id: HardwareID = HardwareID(pid=0x1234, vid=0x4567)
        self.assertEqual(str(hw_id), 'vid: 0x4567, pid: 0x1234')

    def test_unknown_device(self):
        """test handling a pid/vid that isn't being shared"""
        self._connect()  # first connect as usual
        with self.assertRaisesRegex(expected_exception=ValueError, expected_regex='Devices not found'):
            self.client.attach(devices=[HardwareID(pid=0, vid=0)], published=None)

    def test_no_write_response(self):
        """test we can read with a delimiter"""
        usb: USBIP_Connection = self._connect()
        command: str = '{"cmd": "no-write-response"}\r\n'
        with self.assertRaisesRegex(expected_exception=USBIPResponseTimeoutError, expected_regex='Timeout error'):
            self.client.send(usb=usb, data=command)  # send URB writing data to device

    def test_no_read_response(self):
        """test we can read with a delimiter"""
        usb: USBIP_Connection = self._connect()
        command: str = '{"cmd": "no-read-response"}\r\n'
        self.client.send(usb=usb, data=command)  # send URB writing data to device
        with self.assertRaisesRegex(expected_exception=USBIPResponseTimeoutError, expected_regex='Timeout error'):
            usb.response_data(size=len(command))  # there should be no response (suppressed)
