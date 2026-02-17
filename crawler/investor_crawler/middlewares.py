"""
Scrapy Middlewares - Anti-ban, CAPTCHA avoidance, rotating user agents.
=======================================================================

Middlewares:
  1. RotatingUserAgentMiddleware  - Random realistic browser User-Agent per request
  2. CaptchaDetectionMiddleware   - Detect CAPTCHA pages, retry or skip
  3. LongDelayMiddleware          - Apply long delays after N requests
  4. RandomHeadersMiddleware      - Add realistic browser headers
"""

import random
import logging
from scrapy import signals
from scrapy.http import HtmlResponse
from scrapy.exceptions import IgnoreRequest

logger = logging.getLogger(__name__)


# =============================================================================
# Rotating User Agents
# =============================================================================

# Pool of realistic browser User-Agent strings
USER_AGENT_POOL = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]


class RotatingUserAgentMiddleware:
    """
    Replaces the User-Agent header with a random one from the pool
    on every outgoing request. This makes the crawler appear as
    different browsers to the target site.
    """

    def __init__(self, enabled=True):
        self.enabled = enabled

    @classmethod
    def from_crawler(cls, crawler):
        enabled = crawler.settings.getbool("ROTATING_USER_AGENT", True)
        middleware = cls(enabled=enabled)
        return middleware

    def process_request(self, request, spider):
        if self.enabled:
            ua = random.choice(USER_AGENT_POOL)
            request.headers["User-Agent"] = ua
            logger.debug(f"User-Agent set to: {ua[:50]}...")


# =============================================================================
# CAPTCHA Detection
# =============================================================================

# Common CAPTCHA indicators in page content
CAPTCHA_INDICATORS = [
    "captcha",
    "recaptcha",
    "g-recaptcha",
    "hcaptcha",
    "h-captcha",
    "cf-challenge",           # Cloudflare challenge
    "challenge-platform",     # Cloudflare
    "cf-turnstile",           # Cloudflare Turnstile
    "are you a robot",
    "are you human",
    "verify you are human",
    "bot detection",
    "access denied",
    "blocked",
    "unusual traffic",
    "automated queries",
    "please verify",
    "security check",
    "ddos protection",
    "checking your browser",
    "just a moment",          # Cloudflare "Just a moment..."
    "ray id",                 # Cloudflare Ray ID
]


class CaptchaDetectionMiddleware:
    """
    Inspects response body for CAPTCHA/challenge indicators.
    If detected:
      - Logs a warning
      - If RETRY_ON_CAPTCHA is true, retries the request (up to MAX_RETRIES)
      - Otherwise, marks the response with a flag for the spider to handle
    """

    def __init__(self, captcha_detection=True, retry_on_captcha=True, max_retries=3):
        self.captcha_detection = captcha_detection
        self.retry_on_captcha = retry_on_captcha
        self.max_retries = max_retries

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            captcha_detection=crawler.settings.getbool("CAPTCHA_DETECTION", True),
            retry_on_captcha=crawler.settings.getbool("RETRY_ON_CAPTCHA", True),
            max_retries=crawler.settings.getint("MAX_RETRIES", 3),
        )

    def process_response(self, request, response, spider):
        if not self.captcha_detection:
            return response

        # Only check HTML responses
        if not hasattr(response, "text"):
            return response

        body_lower = response.text[:5000].lower()  # Check first 5KB only

        captcha_found = False
        matched_indicator = ""
        for indicator in CAPTCHA_INDICATORS:
            if indicator in body_lower:
                captcha_found = True
                matched_indicator = indicator
                break

        if not captcha_found:
            return response

        # CAPTCHA detected!
        retry_count = request.meta.get("captcha_retry_count", 0)
        logger.warning(
            f"CAPTCHA/Challenge detected on {request.url} "
            f"(indicator: '{matched_indicator}', retry: {retry_count}/{self.max_retries})"
        )

        if self.retry_on_captcha and retry_count < self.max_retries:
            # Retry with a different User-Agent.
            # The download delay between requests is handled by Scrapy's
            # DOWNLOAD_DELAY + AutoThrottle — no time.sleep() needed.
            retry_request = request.copy()
            retry_request.meta["captcha_retry_count"] = retry_count + 1
            retry_request.meta["download_slot"] = f"captcha_retry_{retry_count}"
            retry_request.headers["User-Agent"] = random.choice(USER_AGENT_POOL)
            retry_request.dont_filter = True
            # Use Scrapy's download_delay meta to add extra delay
            retry_request.meta["download_delay"] = random.uniform(5, 15) * (retry_count + 1)
            logger.info(
                f"CAPTCHA retry #{retry_count + 1} for {request.url} "
                f"(delay: {retry_request.meta['download_delay']:.1f}s)"
            )
            return retry_request

        # Mark response as captcha-blocked for spider to handle
        request.meta["captcha_blocked"] = True
        logger.warning(
            f"CAPTCHA blocked (max retries reached): {request.url}"
        )
        return response


# =============================================================================
# Long Delay Middleware
# =============================================================================

class LongDelayMiddleware:
    """
    Applies a longer delay after every N requests to mimic human
    browsing patterns and avoid rate-limiting.

    - Normal requests: random delay between DELAY_MIN and DELAY_MAX
    - Every LONG_DELAY_AFTER_COUNT requests: sleep LONG_DELAY_MIN to LONG_DELAY_MAX
    """

    def __init__(self, delay_min, delay_max, long_min, long_max, long_after):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.long_delay_min = long_min
        self.long_delay_max = long_max
        self.long_delay_after_count = long_after
        self.request_count = 0

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            delay_min=crawler.settings.getfloat("DELAY_MIN", 1.0),
            delay_max=crawler.settings.getfloat("DELAY_MAX", 3.0),
            long_min=crawler.settings.getfloat("LONG_DELAY_MIN", 10.0),
            long_max=crawler.settings.getfloat("LONG_DELAY_MAX", 15.0),
            long_after=crawler.settings.getint("LONG_DELAY_AFTER_COUNT", 30),
        )

    def process_request(self, request, spider):
        self.request_count += 1

        if (
            self.long_delay_after_count > 0
            and self.request_count % self.long_delay_after_count == 0
        ):
            # Use Scrapy's download_delay meta to apply the long delay
            # without blocking the Twisted reactor.
            delay = random.uniform(self.long_delay_min, self.long_delay_max)
            request.meta["download_delay"] = delay
            logger.info(
                f"Long delay after {self.request_count} requests: "
                f"{delay:.1f}s (via download_delay meta)"
            )
        # Note: Normal per-request delay is handled by Scrapy's
        # DOWNLOAD_DELAY + RANDOMIZE_DOWNLOAD_DELAY settings


# =============================================================================
# Random Headers Middleware
# =============================================================================

class RandomHeadersMiddleware:
    """
    Adds realistic browser headers to each request to appear more
    like a real browser. Varies Accept-Language and other headers.
    """

    ACCEPT_LANGUAGES = [
        "en-US,en;q=0.9",
        "en-US,en;q=0.8",
        "en-GB,en;q=0.9,en-US;q=0.8",
        "en-US,en;q=0.9,hi;q=0.8",
        "en-IN,en;q=0.9,en-US;q=0.8",
    ]

    ACCEPT_ENCODINGS = [
        "gzip, deflate, br",
        "gzip, deflate",
        "gzip, deflate, br, zstd",
    ]

    def process_request(self, request, spider):
        request.headers.setdefault(
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8",
        )
        request.headers["Accept-Language"] = random.choice(self.ACCEPT_LANGUAGES)
        request.headers["Accept-Encoding"] = random.choice(self.ACCEPT_ENCODINGS)
        request.headers.setdefault("Connection", "keep-alive")
        request.headers.setdefault(
            "Sec-Fetch-Dest", "document"
        )
        request.headers.setdefault("Sec-Fetch-Mode", "navigate")
        request.headers.setdefault("Sec-Fetch-Site", "none")
        request.headers.setdefault("Sec-Fetch-User", "?1")
        request.headers.setdefault("Upgrade-Insecure-Requests", "1")
        request.headers.setdefault("Cache-Control", "max-age=0")
