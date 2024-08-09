"""test the performance tracking"""
from time import sleep
from math import fsum

from common_test_base import CommonTestBase

from performance_stats import USBStatsManager, USBStats


class TestStats(CommonTestBase):
    """test the performance tracking"""
    def test_context_management(self):
        """test performance stats context management"""
        stats: USBStats = USBStats()

        for _ in range(10):
            with USBStatsManager(stats, 'sleep') as sleep_stats:
                sleep(0.01)

        for _ in range(10):
            with USBStatsManager(stats, 'sleep') as sleep_stats:
                sleep(0.02)

        for _ in range(10):
            with USBStatsManager(stats, 'sleep-longer') as sleep_stats:
                sleep(0.03)

        self.assertEqual(len(stats.raw_data('sleep')), 20)
        self.assertEqual(len(stats.raw_data('sleep-longer')), 10)

        self.assertAlmostEqual(fsum(stats.raw_data('sleep')), (0.01*10 + 0.02*10), delta=0.015)
        self.assertAlmostEqual(fsum(stats.raw_data('sleep-longer')), 0.03*10, delta=0.015)
