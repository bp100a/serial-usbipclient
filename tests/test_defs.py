#
# Copyright (c) 2024 Altai Technologies, LLC
# Author: Harry Collins
#

from tests.test_base import TestBase
from usbip_defs import BaseProtocolPacket


class TestDefinitions(TestBase):
    """test base behavior of our definitions"""
    def test_protocol_formatting(self):
        """test the generation of the protocol format string"""
        base_protocol: BaseProtocolPacket = BaseProtocolPacket()
        self.assertTrue(base_protocol.fmt, 'struct formatting string not generated!')
        self.assertEqual(base_protocol.fmt, '!HHI', 'struct formatting string incorrect')
        self.assertEqual(base_protocol.args, ['usbip_version', 'command', 'status'], 'arguments incorrect!')
