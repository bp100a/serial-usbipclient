"""measure performance with a context manager"""

from statistics import mean, median
from time import perf_counter


class USBStats:
    """track stats for the USBIP serial interface"""

    def __init__(self):
        """set up our variables"""
        self._stats: dict[str, list[float]] = {}

    def start_timer(self, name: str):
        """start the timer"""
        if name not in self._stats:
            self._stats[name] = []
        self._stats[name].append(perf_counter())

    def end_timer(self, name: str) -> None:
        """end the timer and store result"""
        self._stats[name][-1] = perf_counter() - self._stats[name][-1]
        if self._stats[name][-1] > 0.050:
            pass

    @staticmethod
    def display_time(elapsed: float) -> str:
        """return the display time in a more readable format"""
        if elapsed > 60.0:
            minutes: int = int(elapsed / 60.0)
            seconds: int = int(elapsed - minutes * 60.0)
            return f"{minutes}m {seconds}s"
        elif elapsed > 1.0:
            return f"{elapsed:.2f} seconds"
        elif elapsed > 0.001:
            return f"{elapsed*1000.0:.2f} ms"
        return f"{elapsed*1000000:.2f} us"

    def __str__(self) -> str:
        """display our states"""
        return "\n".join(
            [
                f"{name} = {len(value)} samples, min/max: "
                f"{self.display_time(min(value))}/"
                f"{self.display_time(max(value))}, "
                f"avg: {self.display_time(mean(value))}, "
                f"median: {self.display_time(median(value))}"
                for name, value in self._stats.items()
            ]
        )

    def raw_data(self, key: str) -> list[float]:
        """return the raw data"""
        return self._stats.get(key, [])


class USBStatsManager:
    """easily time things"""

    def __init__(self, stats: USBStats, name: str):
        """context we'll be tracking"""
        self.stats: USBStats = stats
        self.name = name

    def __enter__(self):
        """start up the timer"""
        self.stats.start_timer(self.name)

    def __exit__(
        self, exc_type, exc_value, traceback
    ):  # pylint: disable=redefined-outer-name
        """stop the timing"""
        self.stats.end_timer(self.name)
