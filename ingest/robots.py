"""robots.txt compliance and per-host throttling."""

from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests


class PoliteClient:
    """HTTP client that obeys robots.txt and waits between requests to the same host."""

    def __init__(self, user_agent: str, min_delay_s: float = 2.0, timeout_s: float = 30.0) -> None:
        self.user_agent = user_agent
        self.min_delay_s = min_delay_s
        self.timeout_s = timeout_s
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last_hit: dict[str, float] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Language": "en-AU,en;q=0.9"})

    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            try:
                self._throttle(parts.netloc)
                resp = self.session.get(f"{host}/robots.txt", timeout=self.timeout_s)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    parser.disallow_all = True  # RFC 9309: treat as "complete disallow"
                else:
                    parser.allow_all = True  # 404 etc: no robots rules
            except requests.RequestException:
                self._robots[host] = None  # unreachable robots.txt → skip host conservatively
                return None
            self._robots[host] = parser
        return self._robots[host]

    def allowed(self, url: str) -> bool:
        """True if robots.txt permits fetching `url` for our user agent."""
        parser = self._robots_for(url)
        return bool(parser and parser.can_fetch(self.user_agent, url))

    def crawl_delay(self, url: str) -> float:
        """Effective delay for the URL's host: max(min_delay_s, robots Crawl-delay)."""
        parser = self._robots_for(url)
        declared = parser.crawl_delay(self.user_agent) if parser else None
        return max(self.min_delay_s, float(declared or 0))

    def _throttle(self, netloc: str, delay: float | None = None) -> None:
        wait = (delay or self.min_delay_s) - (time.monotonic() - self._last_hit.get(netloc, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_hit[netloc] = time.monotonic()

    def get(self, url: str, retries: int = 3) -> requests.Response:
        """GET with throttling and exponential backoff on 429/5xx/network errors."""
        netloc = urlsplit(url).netloc
        delay = self.crawl_delay(url)
        last_exc: Exception | None = None
        for attempt in range(retries):
            self._throttle(netloc, delay)
            try:
                resp = self.session.get(url, timeout=self.timeout_s)
                if resp.status_code not in (429, 500, 502, 503, 504):
                    return resp
                last_exc = RuntimeError(f"HTTP {resp.status_code}")
            except requests.RequestException as exc:
                last_exc = exc
            time.sleep(delay * (2**attempt))
        raise RuntimeError(f"Failed to fetch {url}: {last_exc}")
