"""
Delay module - Manages request delays to avoid getting blocked.

Two types of delays:
1. Normal delay: Random between DELAY_MIN and DELAY_MAX for every request.
2. Long delay: After every LONG_DELAY_AFTER_COUNT requests, take a longer
   break between LONG_DELAY_MIN and LONG_DELAY_MAX seconds.
"""

import time
import random
from utils.logger import get_logger


class DelayManager:
    """Manages request timing to avoid rate-limiting and blocks."""

    def __init__(self, settings):
        self.delay_min = settings.DELAY_MIN
        self.delay_max = settings.DELAY_MAX
        self.long_delay_min = settings.LONG_DELAY_MIN
        self.long_delay_max = settings.LONG_DELAY_MAX
        self.long_delay_after_count = settings.LONG_DELAY_AFTER_COUNT
        self.request_count = 0
        self.logger = get_logger()

    def wait(self):
        """
        Apply appropriate delay before the next request.
        After every `long_delay_after_count` requests, applies a longer delay.
        """
        self.request_count += 1

        if (
            self.long_delay_after_count > 0
            and self.request_count % self.long_delay_after_count == 0
        ):
            delay = random.uniform(self.long_delay_min, self.long_delay_max)
            self.logger.info(
                f"Long delay triggered after {self.request_count} requests: "
                f"sleeping {delay:.1f}s"
            )
        else:
            delay = random.uniform(self.delay_min, self.delay_max)
            self.logger.debug(f"Request #{self.request_count}: sleeping {delay:.1f}s")

        time.sleep(delay)

    def reset(self):
        """Reset the request counter."""
        self.request_count = 0
