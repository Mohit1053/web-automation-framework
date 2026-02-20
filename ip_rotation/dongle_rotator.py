"""
USB dongle-based IP rotation by cycling mobile hotspot interfaces.

Rotates public IP by toggling Windows network interfaces via netsh,
cycling through multiple USB cellular dongles. Each dongle provides
a different IP from a different mobile carrier.

Windows-only. Requires administrator privileges.

Usage::

    dongles = [
        {"name": "Mobile Broadband 1", "label": "Carrier-A"},
        {"name": "Mobile Broadband 2", "label": "Carrier-B"},
    ]
    rotator = DongleRotator(dongles)
    rotator.rotate()
"""

import json
import logging
import os
import platform
import subprocess
import time
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class DongleRotator:
    """Rotate public IP by cycling through USB mobile hotspot dongles.

    Parameters
    ----------
    dongles : list[dict]
        List of dongle descriptors with "name" (interface name) and
        optional "label" keys.
    switch_wait : float
        Seconds to wait after enabling an interface for connection.
    log_file : str
        Path to JSON log file for recording IP changes.
    """

    IP_API = "https://api.ipify.org?format=json"
    GEO_API = "https://ipapi.co/{}/json/"

    def __init__(self, dongles, switch_wait=15.0, log_file="dongle_rotation.json"):
        if not dongles:
            raise ValueError("At least one dongle descriptor is required")
        if platform.system() != "Windows":
            logger.warning("DongleRotator uses netsh -- designed for Windows")
        self.dongles = dongles
        self.switch_wait = switch_wait
        self.log_file = log_file
        self._index = -1

    @property
    def current_dongle(self):
        """Return the currently active dongle descriptor."""
        if 0 <= self._index < len(self.dongles):
            return self.dongles[self._index]
        return None

    def rotate(self):
        """Switch to next dongle, verify IP, return change record."""
        self._index = (self._index + 1) % len(self.dongles)
        target = self.dongles[self._index]
        label = target.get("label", target["name"])
        logger.info("Rotating to dongle: %s", label)

        # Disable all interfaces
        for d in self.dongles:
            self._toggle(d["name"], enable=False)
        time.sleep(2)

        # Enable target
        self._toggle(target["name"], enable=True)
        logger.info("Waiting %.0fs for %s to connect...", self.switch_wait, label)
        time.sleep(self.switch_wait)

        ip = self.get_public_ip()
        geo = self._get_geo(ip) if ip != "unknown" else {}

        record = {
            "timestamp": datetime.now().isoformat(),
            "dongle": label,
            "ip": ip,
            "city": geo.get("city", ""),
            "country": geo.get("country_code", ""),
            "isp": geo.get("org", ""),
        }
        self._log(record)
        logger.info("New IP via %s: %s (%s)", label, ip, geo.get("city", ""))
        return record

    def get_public_ip(self):
        """Get current public IP address."""
        try:
            return requests.get(self.IP_API, timeout=10).json().get("ip", "unknown")
        except Exception as exc:
            logger.error("IP detection failed: %s", exc)
            return "unknown"

    def verify_country(self, expected="IN"):
        """Check if current IP is from the expected country."""
        ip = self.get_public_ip()
        geo = self._get_geo(ip)
        actual = geo.get("country_code", "")
        match = actual.upper() == expected.upper()
        if not match:
            logger.warning("IP %s is from %s, expected %s", ip, actual, expected)
        return match

    @classmethod
    def discover_interfaces(cls):
        """Auto-detect connected Windows network interfaces via ipconfig."""
        if platform.system() != "Windows":
            return []
        try:
            result = subprocess.run(
                ["ipconfig"], capture_output=True, text=True, timeout=10
            )
            interfaces = []
            adapter = None
            for line in result.stdout.split("\n"):
                line = line.strip()
                if "adapter" in line.lower() and line.endswith(":"):
                    adapter = line.split("adapter")[-1].strip().rstrip(":")
                elif "IPv4 Address" in line and adapter:
                    interfaces.append({"name": adapter, "label": adapter})
                    adapter = None
            return interfaces
        except Exception as exc:
            logger.error("Interface discovery failed: %s", exc)
            return []

    def _toggle(self, name, enable=True):
        action = "enable" if enable else "disable"
        try:
            subprocess.run(
                ["netsh", "interface", "set", "interface", name, action],
                capture_output=True, timeout=15,
            )
        except Exception as exc:
            logger.error("Failed to %s %s: %s", action, name, exc)

    def _get_geo(self, ip):
        try:
            return requests.get(self.GEO_API.format(ip), timeout=10).json()
        except Exception:
            return {}

    def _log(self, record):
        try:
            entries = []
            if os.path.exists(self.log_file):
                with open(self.log_file) as f:
                    entries = json.load(f)
            entries.append(record)
            with open(self.log_file, "w") as f:
                json.dump(entries, f, indent=2)
        except Exception as exc:
            logger.error("Log write failed: %s", exc)
