"""base for all unit tests"""

from os import getenv

from unittest import TestCase


class TestBase(TestCase):
    """base class for common behavior to all unit tests"""
    @staticmethod
    def is_truthy(key: str, default: bool) -> bool:
        """read environment variable, return boolean response"""
        value: str = getenv(key, default=str(default)).upper()
        return value in ['TRUE', '1', '1.0']

    def skip_on_ci(self):
        """skip the test if running on a CI/CD system"""
        if self.CI:
            self.skipTest(reason='incompatible with CI')

    def __init__(self, methodName):
        """need some special variables"""
        self.CI: bool = TestBase.is_truthy('CI', False)
        super().__init__(methodName)
