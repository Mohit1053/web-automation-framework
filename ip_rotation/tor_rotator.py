"""
Tor-based IP rotation with SOCKS5 proxy and circuit renewal.

Routes Selenium Chrome through the Tor network and rotates exit nodes
by sending SIGNAL NEWNYM to the Tor control port. Falls back to
restarting the Tor service if the control port is unavailable.

Prerequisites:
    - Tor installed and running (default SOCKS port 9050, control port 9051)
    - ControlPort enabled in torrc with HashedControlPassword

Usage::

    rotator = TorRotator(control_password="your_password")
    options = webdriver.ChromeOptions()
    rotator.setup_tor_proxy(options)
    driver = webdriver.Chrome(options=options)
    ip = rotator.get_current_ip(driver)
    rotator.rotate_circuit()
"""

import json
import logging
import platform
import socket
import subprocess
import time

logger = logging.getLogger(__name__)


class TorRotator:
    """Manage IP rotation through the Tor network.

    Parameters
    ----------
    socks_port : int
        Tor SOCKS5 proxy port (default 9050).
    control_port : int
        Tor control port for NEWNYM signals (default 9051).
    control_password : str
        Password for Tor control port authentication.
    circuit_wait : float
        Seconds to wait after requesting a new circuit.
    """

    def __init__(self, socks_port=9050, control_port=9051,
                 control_password="", circuit_wait=5.0):
        self.socks_port = socks_port
        self.control_port = control_port
        self.control_password = control_password
        self.circuit_wait = circuit_wait

    def setup_tor_proxy(self, driver_options):
        """Configure Chrome options to route traffic through Tor SOCKS5 proxy."""
        driver_options.add_argument(
            f"--proxy-server=socks5://localhost:{self.socks_port}"
        )
        driver_options.add_argument(
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost"
        )
        logger.info("Chrome configured for Tor SOCKS5 on port %d", self.socks_port)

    def rotate_circuit(self):
        """Request a new Tor circuit for a fresh exit IP.

        Tries SIGNAL NEWNYM via control port first, falls back to service restart.

        Returns True if rotation was successful.
        """
        try:
            return self._signal_newnym()
        except Exception as exc:
            logger.warning("NEWNYM failed (%s), trying service restart", exc)
            return self._restart_tor_service()

    def _signal_newnym(self):
        """Send SIGNAL NEWNYM to Tor control port via raw socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        try:
            sock.connect(("127.0.0.1", self.control_port))

            if self.control_password:
                sock.send(f'AUTHENTICATE "{self.control_password}"\r\n'.encode())
            else:
                sock.send(b"AUTHENTICATE\r\n")

            response = sock.recv(1024).decode()
            if "250" not in response:
                raise RuntimeError(f"Tor auth failed: {response.strip()}")

            sock.send(b"SIGNAL NEWNYM\r\n")
            response = sock.recv(1024).decode()
            if "250" not in response:
                raise RuntimeError(f"NEWNYM failed: {response.strip()}")

            logger.info("Circuit rotated via NEWNYM, waiting %.1fs", self.circuit_wait)
            time.sleep(self.circuit_wait)
            return True
        finally:
            sock.close()

    def _restart_tor_service(self):
        """Restart the Tor service (fallback when control port unavailable)."""
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.run(["net", "stop", "tor"], capture_output=True, timeout=30)
                time.sleep(2)
                subprocess.run(["net", "start", "tor"], capture_output=True, timeout=30)
            else:
                subprocess.run(
                    ["systemctl", "restart", "tor"], capture_output=True, timeout=30
                )
            logger.info("Tor service restarted, waiting %.1fs", self.circuit_wait * 2)
            time.sleep(self.circuit_wait * 2)
            return True
        except Exception as exc:
            logger.error("Failed to restart Tor: %s", exc)
            return False

    def verify_tor_connection(self, driver):
        """Check if browser is routing through Tor via check.torproject.org."""
        try:
            driver.get("https://check.torproject.org")
            page_text = driver.find_element("tag name", "body").text
            is_tor = "Congratulations" in page_text
            logger.info("Tor verification: %s", "ACTIVE" if is_tor else "NOT DETECTED")
            return is_tor
        except Exception as exc:
            logger.error("Tor verification failed: %s", exc)
            return False

    def get_current_ip(self, driver):
        """Get current public IP through the browser (not requests).

        Uses the browser to ensure the IP reflects the proxy configuration.
        """
        try:
            driver.get("https://httpbin.org/ip")
            body = driver.find_element("tag name", "body").text
            data = json.loads(body)
            ip = data.get("origin", "unknown")
            logger.info("Current IP (via browser): %s", ip)
            return ip
        except Exception:
            try:
                driver.get("https://api.ipify.org?format=json")
                body = driver.find_element("tag name", "body").text
                return json.loads(body).get("ip", "unknown")
            except Exception as exc:
                logger.error("IP detection failed: %s", exc)
                return "unknown"
