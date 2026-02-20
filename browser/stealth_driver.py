"""Module for Chrome WebDriver configuration."""
import os, uuid, random, shutil, tempfile, logging
from typing import Optional, List, Dict, Any
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

DEVICE_PROFILES = [
    {"gpu": "Intel Inc.", "renderer": "Intel(R) UHD Graphics 620", "screen": [1920, 1080]},
    {"gpu": "Intel Inc.", "renderer": "Intel(R) UHD Graphics 630", "screen": [1920, 1080]},
    {"gpu": "Intel Inc.", "renderer": "Intel(R) HD Graphics 520", "screen": [1366, 768]},
    {"gpu": "Intel Inc.", "renderer": "Intel(R) Iris Xe Graphics", "screen": [1920, 1080]},
    {"gpu": "Intel Inc.", "renderer": "Intel(R) HD Graphics 5500", "screen": [1366, 768]},
    {"gpu": "Intel Inc.", "renderer": "Intel(R) UHD Graphics", "screen": [1536, 864]},
    {"gpu": "AMD", "renderer": "AMD Radeon(TM) Graphics", "screen": [1920, 1080]},
    {"gpu": "AMD", "renderer": "AMD Radeon RX 580 Series", "screen": [2560, 1440]},
    {"gpu": "AMD", "renderer": "AMD Radeon RX 6600", "screen": [1920, 1080]},
    {"gpu": "NVIDIA Corporation", "renderer": "NVIDIA GeForce GTX 1650", "screen": [1920, 1080]},
    {"gpu": "NVIDIA Corporation", "renderer": "NVIDIA GeForce GTX 1660", "screen": [1920, 1080]},
    {"gpu": "NVIDIA Corporation", "renderer": "NVIDIA GeForce RTX 3060", "screen": [2560, 1440]},
    {"gpu": "NVIDIA Corporation", "renderer": "NVIDIA GeForce GTX 1050 Ti", "screen": [1920, 1080]},
    {"gpu": "NVIDIA Corporation", "renderer": "NVIDIA GeForce RTX 3080", "screen": [3840, 2160]},
    {"gpu": "NVIDIA Corporation", "renderer": "NVIDIA GeForce RTX 2060", "screen": [2560, 1440]},
    {"gpu": "Apple Inc.", "renderer": "Apple M1", "screen": [2560, 1600]},
    {"gpu": "Apple Inc.", "renderer": "Apple M1 Pro", "screen": [3024, 1964]},
]

class StealthDriver:
    """Chrome WebDriver wrapper."""
    def __init__(self, headless=False, user_agent=None, extra_arguments=None, window_position="-2400,0"):
        self.headless = headless
        self.user_agent = user_agent
        self.extra_arguments = extra_arguments or []
        self.window_position = window_position
        self._driver = None
        self._profile_dir = None
        self._device_profile = None

    def __enter__(self):
        return self.create_driver()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def create_driver(self):
        """Create and return a configured Chrome WebDriver."""
        options = self._build_options()
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        self._inject_webdriver_suppression(driver)
        self._inject_webgl_spoofing(driver)
        self._driver = driver
        return driver

    def cleanup(self):
        """Quit browser and remove temporary profile directory."""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None
        if self._profile_dir and os.path.isdir(self._profile_dir):
            shutil.rmtree(self._profile_dir, ignore_errors=True)
            self._profile_dir = None

    def _build_options(self):
        """Assemble Chrome options with anti-detection flags."""
        options = Options()
        unique_id = uuid.uuid4().hex[:12]
        self._profile_dir = tempfile.mkdtemp(prefix=f"waf_chrome_{unique_id}_")
        options.add_argument(f"--user-data-dir={self._profile_dir}")
        if self.user_agent is None:
            ua = UserAgent()
            self.user_agent = ua.random
        options.add_argument(f"user-agent={self.user_agent}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        self._device_profile = random.choice(DEVICE_PROFILES)
        w, h = self._device_profile["screen"]
        options.add_argument(f"--window-size={w},{h}")
        options.add_argument(f"--window-position={self.window_position}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        prefs = {"profile.default_content_setting_values.notifications": 2, "credentials_enable_service": False, "profile.password_manager_enabled": False}
        options.add_experimental_option("prefs", prefs)
        if self.headless:
            options.add_argument("--headless=new")
        for arg in self.extra_arguments:
            options.add_argument(arg)
        return options

    def _inject_webdriver_suppression(self, driver):
        """Hide navigator.webdriver via CDP script injection."""
        js = "Object.defineProperty(navigator,\\\"webdriver\\\",{get:()=>undefined});"
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": js})

    def _inject_webgl_spoofing(self, driver):
        """Override WebGL getParameter to return spoofed GPU info."""
        if not self._device_profile:
            return
        gpu = self._device_profile["gpu"]
        renderer = self._device_profile["renderer"]
        script = f"(function(){{var g=WebGLRenderingContext.prototype.getParameter;WebGLRenderingContext.prototype.getParameter=function(p){{if(p===37445)return'{gpu}';if(p===37446)return'{renderer}';return g.apply(this,arguments);}};if(typeof WebGL2RenderingContext\!=='undefined'){{var g2=WebGL2RenderingContext.prototype.getParameter;WebGL2RenderingContext.prototype.getParameter=function(p){{if(p===37445)return'{gpu}';if(p===37446)return'{renderer}';return g2.apply(this,arguments);}};}}}})()"
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
