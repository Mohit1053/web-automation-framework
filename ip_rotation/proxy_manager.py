"""
Multi-provider proxy manager with rotating and list-based modes.

Supports rotating proxy services (Smartproxy, Bright Data, Oxylabs) and
fixed proxy lists from dongles or VPNs. Includes per-worker rotation and
IP verification.

Usage::

    # Rotating proxy service
    pm = ProxyManager(mode="rotating", provider="smartproxy",
                      credentials={"user": "u", "password": "p"})

    # Fixed proxy list
    pm = ProxyManager(mode="list", proxy_list=[
        {"host": "1.2.3.4", "port": 8080},
        {"host": "5.6.7.8", "port": 8080},
    ])

    proxy = pm.get_proxy_for_worker(worker_id=0)
    pm.setup_chrome_proxy(chrome_options, proxy)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Provider endpoint templates (use placeholder credentials)
PROVIDER_TEMPLATES = {
    "smartproxy": {
        "host": "gate.smartproxy.com",
        "port": 7000,
        "format": "http://{user}:{password}@gate.smartproxy.com:7000",
    },
    "brightdata": {
        "host": "brd.superproxy.io",
        "port": 22225,
        "format": "http://{user}:{password}@brd.superproxy.io:22225",
    },
    "oxylabs": {
        "host": "pr.oxylabs.io",
        "port": 7777,
        "format": "http://{user}:{password}@pr.oxylabs.io:7777",
    },
}


@dataclass
class ProxyConfig:
    """A single proxy endpoint."""
    host: str
    port: int
    username: str = ""
    password: str = ""
    protocol: str = "http"

    @property
    def url(self):
        if self.username:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"

    def as_requests_proxies(self):
        return {"http": self.url, "https": self.url}


class ProxyManager:
    """Multi-provider proxy manager with rotation.

    Parameters
    ----------
    mode : str
        "rotating" (paid service handles rotation) or "list" (fixed IPs).
    provider : str
        Provider name for rotating mode (smartproxy, brightdata, oxylabs).
    credentials : dict
        Provider credentials with "user" and "password" keys.
    proxy_list : list[dict]
        List of proxy dicts with "host" and "port" for list mode.
    rotate_every : int
        In list mode, rotate after this many requests per worker.
    """

    def __init__(self, mode="rotating", provider=None, credentials=None,
                 proxy_list=None, rotate_every=10):
        self.mode = mode
        self.provider = provider
        self.credentials = credentials or {}
        self.proxy_list = proxy_list or []
        self.rotate_every = rotate_every
        self._worker_counts = {}
        self._worker_indices = {}

    def get_proxy_for_worker(self, worker_id=0):
        """Return a ProxyConfig for the given worker.

        In rotating mode, returns the provider proxy (service handles rotation).
        In list mode, cycles through the proxy list after rotate_every requests.
        """
        if self.mode == "rotating":
            return self._build_rotating_proxy()

        if not self.proxy_list:
            raise ValueError("No proxies in list")

        # Track per-worker request count for rotation
        count = self._worker_counts.get(worker_id, 0)
        idx = self._worker_indices.get(worker_id, worker_id % len(self.proxy_list))

        if count > 0 and count % self.rotate_every == 0:
            idx = (idx + 1) % len(self.proxy_list)
            self._worker_indices[worker_id] = idx
            logger.info("Worker %d rotating to proxy index %d", worker_id, idx)

        self._worker_counts[worker_id] = count + 1

        p = self.proxy_list[idx]
        return ProxyConfig(
            host=p["host"], port=p["port"],
            username=p.get("username", ""), password=p.get("password", ""),
        )

    def setup_chrome_proxy(self, driver_options, proxy):
        """Apply a ProxyConfig to Chrome options.

        Parameters
        ----------
        driver_options : ChromeOptions
            Chrome options to modify.
        proxy : ProxyConfig
            Proxy to apply.
        """
        if proxy.username:
            logger.warning(
                "Chrome --proxy-server does not support auth natively. "
                "Use a proxy extension or unauthenticated proxy."
            )
        driver_options.add_argument(f"--proxy-server={proxy.url}")
        logger.info("Chrome proxy set to %s:%d", proxy.host, proxy.port)

    def verify_proxy_ip(self, proxy=None):
        """Check current IP through the proxy.

        Returns dict with ip, city, country, org keys.
        """
        proxies = proxy.as_requests_proxies() if proxy else None
        try:
            resp = requests.get("https://ipapi.co/json/", proxies=proxies, timeout=15)
            data = resp.json()
            logger.info(
                "Proxy IP: %s (%s, %s)",
                data.get("ip"), data.get("city"), data.get("country_code"),
            )
            return data
        except Exception as exc:
            logger.error("Proxy IP verification failed: %s", exc)
            return {}

    @classmethod
    def from_url_list(cls, urls, rotate_every=10):
        """Create a ProxyManager from a list of proxy URL strings.

        Parameters
        ----------
        urls : list[str]
            Proxy URLs like "http://host:port" or "http://user:pass@host:port".
        rotate_every : int
            Rotate after this many requests per worker.
        """
        proxy_list = []
        for url in urls:
            url = url.replace("http://", "").replace("https://", "")
            username = password = ""
            if "@" in url:
                auth, url = url.rsplit("@", 1)
                username, password = auth.split(":", 1) if ":" in auth else (auth, "")
            host, port = url.split(":", 1) if ":" in url else (url, "8080")
            proxy_list.append({
                "host": host, "port": int(port),
                "username": username, "password": password,
            })
        return cls(mode="list", proxy_list=proxy_list, rotate_every=rotate_every)

    def _build_rotating_proxy(self):
        template = PROVIDER_TEMPLATES.get(self.provider)
        if not template:
            raise ValueError(f"Unknown provider: {self.provider}")
        return ProxyConfig(
            host=template["host"],
            port=template["port"],
            username=self.credentials.get("user", ""),
            password=self.credentials.get("password", ""),
        )
