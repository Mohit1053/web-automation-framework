"""Form scanning and honeypot detection for web form analysis."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# JavaScript snippet to compute a stable XPath for a DOM element.
XPATH_JS = """
function getXPath(el) {
    if (!el) return '';
    if (el.id) return '//' + el.tagName.toLowerCase() + '[@id="' + el.id + '"]';
    if (el === document.body) return '/html/body';
    var ix = 0;
    var siblings = el.parentNode ? el.parentNode.childNodes : [];
    for (var i = 0; i < siblings.length; i++) {
        var sib = siblings[i];
        if (sib === el) {
            return getXPath(el.parentNode) + '/' + el.tagName.toLowerCase() + '[' + (ix + 1) + ']';
        }
        if (sib.nodeType === 1 && sib.tagName === el.tagName) ix++;
    }
    return '';
}
return getXPath(arguments[0]);
"""

# CSS selectors tried in order to locate form containers.
CONTAINER_SELECTORS: List[str] = [
    "form",
    "[role='form']",
    ".form-container",
    "[data-form]",
    "fieldset",
]


@dataclass
class FieldInfo:
    """Metadata about a single form field."""

    tag: str
    field_type: str
    name: str
    label: str = ""
    xpath: str = ""
    options: List[str] = field(default_factory=list)
    required: bool = False


class FormScanner:
    """Discover and catalogue form fields on a web page."""

    def __init__(self) -> None:
        self._fields: List[FieldInfo] = []
        self._honeypot = HoneypotDetector()

    def scan(self, driver: Any, url: str) -> List[FieldInfo]:
        """
        Navigate to *url* and extract all visible form fields.

        Args:
            driver: Selenium WebDriver instance.
            url: Target page URL.

        Returns:
            List of discovered ``FieldInfo`` objects.
        """
        driver.get(url)
        self._fields = []
        container = self._find_container(driver)
        if container is None:
            logger.warning("No form container found on %s", url)
            return self._fields

        elements = container.find_elements("css selector", "input, select, textarea, button")
        for el in elements:
            if self._honeypot.is_honeypot(driver, el):
                logger.debug("Skipping honeypot element: %s", el.get_attribute("name"))
                continue
            info = FieldInfo(
                tag=el.tag_name,
                field_type=self._identify_type(el),
                name=el.get_attribute("name") or "",
                label=self._find_label(driver, el),
                xpath=self._get_xpath(driver, el),
                options=self._extract_options(el),
                required=el.get_attribute("required") is not None,
            )
            self._fields.append(info)

        logger.info("Scanned %d fields on %s", len(self._fields), url)
        return self._fields

    def export_structure(self, filepath: str) -> None:
        """Serialize discovered fields to a JSON file."""
        data = []
        for f in self._fields:
            data.append({
                "tag": f.tag,
                "type": f.field_type,
                "name": f.name,
                "label": f.label,
                "xpath": f.xpath,
                "options": f.options,
                "required": f.required,
            })
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        logger.info("Exported %d fields to %s", len(data), filepath)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_container(driver: Any) -> Optional[Any]:
        """Try each container selector strategy in order."""
        for selector in CONTAINER_SELECTORS:
            elems = driver.find_elements("css selector", selector)
            if elems:
                return elems[0]
        return None

    @staticmethod
    def _identify_type(element: Any) -> str:
        """Determine the logical field type from element attributes."""
        tag = element.tag_name.lower()
        if tag == "select":
            return "select"
        if tag == "textarea":
            return "textarea"
        if tag == "button":
            return element.get_attribute("type") or "button"
        input_type = (element.get_attribute("type") or "text").lower()
        return input_type

    @staticmethod
    def _extract_options(element: Any) -> List[str]:
        """Return option values for select elements."""
        if element.tag_name.lower() != "select":
            return []
        options = element.find_elements("css selector", "option")
        return [opt.get_attribute("value") or opt.text for opt in options]

    @staticmethod
    def _get_xpath(driver: Any, element: Any) -> str:
        """Compute the XPath of *element* via JavaScript injection."""
        try:
            return driver.execute_script(XPATH_JS, element) or ""
        except Exception:
            return ""

    @staticmethod
    def _find_label(driver: Any, element: Any) -> str:
        """Attempt to find a label associated with the element."""
        elem_id = element.get_attribute("id")
        if elem_id:
            labels = driver.find_elements(
                "css selector", "label[for='{}']".format(elem_id)
            )
            if labels:
                return labels[0].text.strip()
        # Fallback: placeholder or aria-label
        return (
            element.get_attribute("placeholder")
            or element.get_attribute("aria-label")
            or ""
        )


class HoneypotDetector:
    """Detect hidden honeypot fields designed to trap bots."""

    def is_honeypot(self, driver: Any, element: Any) -> bool:
        """
        Check whether an element is a hidden honeypot trap.

        Examines CSS display, visibility, opacity, dimensions,
        aria-hidden, and tabIndex attributes.

        Args:
            driver: Selenium WebDriver instance.
            element: WebElement to inspect.

        Returns:
            True if the element is likely a honeypot.
        """
        try:
            props = driver.execute_script(
                "var cs = window.getComputedStyle(arguments[0]);"
                "return {"
                "  display: cs.display,"
                "  visibility: cs.visibility,"
                "  opacity: cs.opacity,"
                "  width: arguments[0].offsetWidth,"
                "  height: arguments[0].offsetHeight,"
                "  ariaHidden: arguments[0].getAttribute('aria-hidden'),"
                "  tabIndex: arguments[0].getAttribute('tabindex')"
                "};",
                element,
            )
        except Exception:
            return False

        if props.get("display") == "none":
            return True
        if props.get("visibility") == "hidden":
            return True
        if float(props.get("opacity", 1)) == 0:
            return True
        if props.get("width", 1) == 0 and props.get("height", 1) == 0:
            return True
        if props.get("ariaHidden") == "true":
            return True
        if str(props.get("tabIndex", "")) == "-1":
            return True
        return False
