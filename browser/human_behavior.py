"""
human_behavior -- Simulate realistic human interaction patterns.

Provides HumanBehavior for natural typing, mouse movement, scrolling,
and delay simulation, plus HoneypotDetector for identifying trap fields.
"""

import time
import random
import logging

import numpy as np
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

logger = logging.getLogger(__name__)

class HumanBehavior:
    """Simulate realistic human interaction with web elements."""

    DEFAULT_TYPING_SPEED = 0.10
    DEFAULT_TYPO_RATE = 0.015
    DEFAULT_WPM = 250

    def __init__(self, typing_speed=None, typo_rate=None):
        self.typing_speed = typing_speed or self.DEFAULT_TYPING_SPEED
        self.typo_rate = typo_rate or self.DEFAULT_TYPO_RATE

    def type_like_human(self, element, text):
        """Type text with Gaussian-distributed key delays and typo simulation."""
        element.click()
        time.sleep(random.uniform(0.2, 0.5))
        word_pos = 0
        for i, char in enumerate(text):
            if char == " ":
                word_pos = 0
            else:
                word_pos += 1
            if random.random() < self.typo_rate and i < len(text) - 1 and char.isalpha():
                wrong = random.choice("abcdefghijklmnopqrstuvwxyz")
                element.send_keys(wrong)
                time.sleep(self._char_delay(wrong, word_pos))
                time.sleep(random.uniform(0.15, 0.35))
                element.send_keys(Keys.BACKSPACE)
                time.sleep(random.uniform(0.1, 0.25))
            element.send_keys(char)
            time.sleep(self._char_delay(char, word_pos))
        time.sleep(random.uniform(0.3, 0.9))

    def _char_delay(self, char, word_pos):
        """Calculate delay for a character using Gaussian distribution."""
        delay = self.typing_speed
        if char in ".,\!?;:": delay *= random.uniform(1.5, 2.5)
        elif char == " ": delay *= random.uniform(1.2, 1.8)
        elif char.isupper(): delay *= random.uniform(1.1, 1.4)
        if 2 < word_pos < 8: delay *= random.uniform(0.7, 0.9)
        delay *= np.random.lognormal(0, 0.3)
        if random.random() < 0.05: delay += random.uniform(0.5, 1.5)
        return max(0.04, min(delay, 0.35))

    @staticmethod
    def move_mouse_naturally(driver, element, num_points=20):
        """Move mouse to element along a Bezier curve with jitter."""
        try:
            loc = element.location
            sz = element.size
            x1, y1 = random.randint(100, 800), random.randint(100, 500)
            x4 = loc["x"] + sz["width"] // 2 + random.randint(-10, 10)
            y4 = loc["y"] + sz["height"] // 2 + random.randint(-10, 10)
            overshoot = random.uniform(1.05, 1.15)
            x2 = x1 + (x4 - x1) * random.uniform(0.2, 0.4)
            y2 = y1 + (y4 - y1) * random.uniform(0.2, 0.4)
            x3 = x1 + (x4 - x1) * random.uniform(0.6, 0.8) * overshoot
            y3 = y1 + (y4 - y1) * random.uniform(0.6, 0.8) * overshoot
            t = np.linspace(0, 1, num_points)
            bx = (1-t)**3*x1 + 3*(1-t)**2*t*x2 + 3*(1-t)*t**2*x3 + t**3*x4
            by = (1-t)**3*y1 + 3*(1-t)**2*t*y2 + 3*(1-t)*t**2*y3 + t**3*y4
            bx += np.random.normal(0, 2, num_points)
            by += np.random.normal(0, 2, num_points)
            for ix, (px, py) in enumerate(zip(bx.astype(int), by.astype(int))):
                js = f"document.dispatchEvent(new MouseEvent(\"mousemove\",{{clientX:{px},clientY:{py},bubbles:true}}));"
                driver.execute_script(js)
                if ix < 3 or ix > num_points - 3:
                    time.sleep(random.uniform(0.02, 0.04))
                else:
                    time.sleep(random.uniform(0.008, 0.02))
            time.sleep(random.uniform(0.1, 0.3))
        except Exception:
            logger.debug("Mouse movement failed; skipping.", exc_info=True)

    @staticmethod
    def random_scroll(driver):
        """Perform natural scroll with ease-in-ease-out acceleration."""
        try:
            total = random.randint(150, 400)
            steps = random.randint(8, 15)
            for i in range(steps):
                progress = i / steps
                eased = progress * progress * (3 - 2 * progress)
                step_px = int((total / steps) * (1 + eased * 0.5))
                driver.execute_script(f"window.scrollBy(0, {step_px});")
                time.sleep(random.uniform(0.05, 0.15))
        except Exception:
            pass

    @staticmethod
    def human_delay(min_s=2.0, max_s=5.0):
        """Wait a Gamma-distributed duration between min_s and max_s."""
        base = random.uniform(min_s, max_s)
        delay = np.random.gamma(2.5, base / 2.5)
        delay = max(min_s, min(delay, max_s * 2))
        if random.random() < 0.03: delay += random.uniform(3, 8)
        time.sleep(delay)
        return delay

    @staticmethod
    def simulate_reading(text):
        """Estimate and wait a realistic reading time for text."""
        words = len(text) / 4.5
        speed = random.gauss(250, 50)
        reading_time = (words / max(speed, 50)) * 60
        scan_factor = random.uniform(0.3, 0.6)
        wait = max(2, reading_time * scan_factor)
        time.sleep(wait)
        return wait


class HoneypotDetector:
    """Detect honeypot trap fields in web forms."""

    @staticmethod
    def is_honeypot(driver, element):
        """Return True if element is likely a honeypot trap."""
        try:
            js = """const el=arguments[0]; const s=window.getComputedStyle(el);
            if(s.display==="none"||s.visibility==="hidden"||s.opacity==="0")return false;
            if(parseInt(s.width)===0||parseInt(s.height)===0)return false;
            if(el.getAttribute("aria-hidden")==="true")return false;
            if(el.getAttribute("tabindex")==="-1")return false;
            const r=el.getBoundingClientRect();
            if(r.top<-100||r.left<-100)return false;
            if(r.top>window.innerHeight+100||r.left>window.innerWidth+100)return false;
            return true;"""
            is_visible = driver.execute_script(js, element)
            return not is_visible
        except Exception:
            return True
