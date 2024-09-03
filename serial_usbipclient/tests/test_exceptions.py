"""test exceptions are properly raised"""

from common_test_base import CommonTestBase
from serial_usbipclient import USBIPClient
from serial_usbipclient.usbip_client import USBIPValueError, USBIP_Connection


class TestExceptions(CommonTestBase):
    """tests exception throwing"""
    def test_endpoint_exceptions(self):
        """test exceptions from endpoints"""
        conn: USBIP_Connection = USBIP_Connection()
        _ = conn.control  # no exception

        # exceptions should be thrown from uninitialized endpoints
        with self.assertRaisesRegex(expected_exception=USBIPValueError, expected_regex='no input endpoint!'):
            _ = conn.input

        with self.assertRaisesRegex(expected_exception=USBIPValueError, expected_regex='no output endpoint!'):
            _ = conn.output

        with self.assertRaisesRegex(expected_exception=USBIPValueError, expected_regex='no endpoint!'):
            _ = conn.pending_reads
