"""test packaging"""
from common_test_base import CommonTestBase

from serial_usbipclient.version import get_version


class TestVersion(CommonTestBase):
    """test the version handling"""
    def test_version(self):
        """test reading version from non-package"""
        version_regex: str = r'^(\d+\.)?(\d+\.)?(\*|\d+)$'  # x.y.z
        version: str = get_version('serial-usbipclient')
        self.assertRegex(version, version_regex)

        # if package name doesn't match we expect a warning to be logged
        with self.assertLogs(level='WARNING'):
            get_version('bad-package-name')
