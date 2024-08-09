"""base for all unit tests"""

import sys
from os import getenv
import logging
import os
import re
import json
from typing import Optional

from unittest import TestCase

from tests.mock_usbip import MockUSBIP
from usbip_client import USBIPClient


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
        if self.CI:
            self.skipTest(reason=reason)

    def __init__(self, methodName):
        """need some special variables"""
        self.CI: bool = CommonTestBase.is_truthy('CI', False)
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.mock_usbip: Optional[MockUSBIP] = None
        self.client: Optional[USBIPClient] = None
        self.host: str = 'localhost'
        self.port: int = self.DEFAULT_USBIP_SERVER_PORT  # will be updated by subclasses
        formatter: logging.Formatter = logging.Formatter('%(asctime)s \t%(levelname)s \t%(name)s \t%(message)s')
        if not self.logger.handlers:
            handler: logging.Handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(formatter)
            handler.setLevel(logging.DEBUG)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
        # elif not [item for item in self.logger.root.handlers if type(item) == logging.StreamHandler]:
        #     self.logger.root.setLevel(level=logging.DEBUG)
        #     handler = logging.StreamHandler(sys.stdout)
        #     handler.setFormatter(formatter)
        #     self.logger.root.addHandler(handler)

        super().__init__(methodName)

        if methodName != 'runTest':
            self.logger.info(f"running {methodName}")

        self.runner_instance: str = os.getenv('PYTEST_XDIST_WORKER', '1')
        self.worker_id: int = int(re.findall(r"(\d+)$", self.runner_instance)[0]) if self.runner_instance else 0

    def get_test_index(self, name: str) -> int:
        """get index of test, can be used as offset for port assignments"""
        qualified_name: str = name.replace(os.sep, '.').lower()
        with open(os.path.join(os.path.dirname(__file__), 'list_of_tests.json'), 'r') as tests:
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
