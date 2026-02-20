# Web Automation Framework

> **Production-grade toolkit for browser automation, anti-detection, IP rotation, and AI-powered content generation -- built from real-world deployment experience processing 500K+ form submissions.**

[\![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[\![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Architecture

```
+---------------------------------------------------------------------+
|                    Web Automation Framework                          |
+--------------+--------------+-----------+-----------+--------------+
|              |              |           |           |              |
|  Browser     |  IP          |  LLM      |  Form     |  Data        |
|  Control     |  Rotation    |  Engine   |  Recon    |  Pipeline    |
|              |              |           |           |              |
|  +--------+  |  +--------+  | +-------+ | +-------+ | +----------+|
|  |Stealth |  |  |  Tor   |  | |OpenAI | | |XPath  | | |  Batch   ||
|  |Driver  |  |  |Circuit |  | |Claude | | |  Gen  | | |  Merge   ||
|  +--------+  |  +--------+  | +-------+ | +-------+ | +----------+|
|  |Finger- |  |  |USB     |  | |Persona| | |Honey- | | |Validation||
|  |print   |  |  |Dongles |  | |Engine | | |pot    | | |  Engine  ||
|  |Evasion |  |  +--------+  | |       | | |Detect | | +----------+|
|  +--------+  |  |Router  |  | |       | | |       | | |  Log     ||
|  |Human   |  |  |Reset   |  | |       | | |       | | |  Parser  ||
|  |Behavior|  |  +--------+  | |       | | |       | | |          ||
|  |        |  |  |Proxy   |  | |       | | |       | | |          ||
|  |        |  |  |Pool    |  | |       | | |       | | |          ||
|  +--------+  |  +--------+  | +-------+ | +-------+ | +----------+|
+--------------+--------------+-----------+-----------+--------------+
```
---

## Modules

### 1. Browser Control

Undetectable browser automation built on Selenium and `undetected-chromedriver`.

| Component            | Description                                                       |
| -------------------- | ----------------------------------------------------------------- |
| **Stealth Driver**   | Wraps `undetected-chromedriver` with randomized launch args       |
| **Fingerprint Evasion** | Rotates across **6 surfaces**: User-Agent, viewport, WebGL renderer, canvas noise, timezone, and language headers |
| **Human Behavior**   | Gaussian-distributed mouse movements, variable keystroke delays, random scroll patterns, and idle pauses |

### 2. IP Rotation

Four independent strategies for acquiring fresh IP addresses.

| Strategy          | Mechanism                                                       |
| ----------------- | --------------------------------------------------------------- |
| **Tor Circuits**  | Programmatic `NEWNYM` signals via Stem; waits for unique exit IP |
| **USB Dongles**   | AT-command modem reset (`AT+CFUN=1,1`) to trigger DHCP re-lease |
| **Router Reset**  | Selenium-driven admin-panel login to reboot consumer routers    |
| **Proxy Pool**    | Round-robin or weighted selection from residential proxy lists   |

### 3. LLM Engine

AI-powered content generation with provider abstraction.

| Component            | Description                                                    |
| -------------------- | -------------------------------------------------------------- |
| **Multi-Provider**   | Unified interface for OpenAI, Anthropic Claude, and local Ollama models |
| **Persona Engine**   | Generates demographically coherent identities (name, email, company, bio) and varies writing style per persona |

### 4. Form Recon

Automated form discovery, mapping, and obstacle detection.

| Component            | Description                                                    |
| -------------------- | -------------------------------------------------------------- |
| **XPath Generator**  | Crawls target pages and emits stable XPath/CSS selectors for every input, select, and textarea element |
| **Honeypot Detector**| Identifies hidden fields, off-screen inputs, and CSS `display:none` traps to avoid bot-detection triggers |

### 5. Data Pipeline

Post-submission data handling, validation, and observability.

| Component            | Description                                                    |
| -------------------- | -------------------------------------------------------------- |
| **Batch Merge**      | Consolidates per-worker CSV shards into a single deduplicated dataset |
| **Validation Engine**| Schema checks, email-format verification, and duplicate detection before final export |
| **Log Parser**       | Structured JSON logging with per-submission outcome tracking, error categorization, and retry metrics |
---

## Tech Stack

| Layer          | Technology                                                  |
| -------------- | ----------------------------------------------------------- |
| Language       | Python 3.10+                                                |
| Browser Driver | Selenium 4, undetected-chromedriver                         |
| Network        | Stem (Tor), requests, PySocks                               |
| LLM            | OpenAI API, Anthropic API, Ollama                           |
| Data           | pandas, csvkit                                              |
| Scheduling     | concurrent.futures, APScheduler                             |
| Logging        | structlog, Python logging                                   |
| Config         | pydantic-settings, YAML                                     |

---

## Quick Start

### Installation

```bash
pip install -e ".[dev]"
```

### Basic Usage

```python
from waf.browser import StealthBrowser
from waf.rotation import TorRotator
from waf.llm import LLMEngine

# Launch a stealth browser session
browser = StealthBrowser(headless=True)
driver = browser.launch()

# Rotate IP via Tor before each request
rotator = TorRotator(control_port=9051, password="changeme")
rotator.new_identity()

# Generate form content with AI
llm = LLMEngine(provider="openai", model="gpt-4o-mini")
persona = llm.generate_persona()
message = llm.compose_message(
    context="product inquiry",
    persona=persona,
)

# Navigate and submit
driver.get("https://example.com/contact")
driver.find_element("id", "name").send_keys(persona["name"])
driver.find_element("id", "email").send_keys(persona["email"])
driver.find_element("id", "message").send_keys(message)
driver.find_element("id", "submit").click()

browser.quit()
```
---

## Project Structure

```
waf/
├── README.md
├── pyproject.toml
├── waf/
│   ├── __init__.py
│   ├── browser/
│   │   ├── stealth_driver.py
│   │   ├── fingerprint.py
│   │   └── human_behavior.py
│   ├── rotation/
│   │   ├── tor_rotator.py
│   │   ├── dongle_reset.py
│   │   ├── router_reset.py
│   │   └── proxy_pool.py
│   ├── llm/
│   │   ├── engine.py
│   │   └── persona.py
│   ├── recon/
│   │   ├── xpath_gen.py
│   │   └── honeypot.py
│   └── pipeline/
│       ├── merge.py
│       ├── validate.py
│       └── log_parser.py
├── examples/
│   ├── stealth_browsing.py
│   └── ip_rotation_demo.py
├── tests/
│   └── ...
└── configs/
    └── default.yaml
```

---

## Production Deployment Stats

| Metric                | Value                          |
| --------------------- | ------------------------------ |
| Total Submissions     | 500,000+                       |
| Concurrent Workers    | 15 -- 20                       |
| Success Rate          | 85 -- 90%                      |
| IP Rotation Methods   | 4 (Tor, Dongle, Router, Proxy) |
| LLM Providers Tested  | 3 (OpenAI, Claude, Ollama)     |
| Avg. Submission Time  | 18 -- 25 seconds               |
| Uptime (supervised)   | 48-hour unattended runs        |

---

## Concepts Demonstrated

- **Stealth browser automation** with fingerprint randomization across six distinct surfaces
- **Multi-strategy IP rotation** combining Tor, hardware dongles, router resets, and proxy pools
- **LLM-driven content generation** with persona consistency and style variation
- **Automated form reconnaissance** including honeypot and bot-trap detection
- **Scalable data pipelines** with batch merging, schema validation, and structured logging
- **Concurrent worker orchestration** using Python's `concurrent.futures` thread/process pools
- **Resilient error handling** with exponential backoff, per-submission retry logic, and dead-letter queues

---

## Disclaimer

This framework is provided **for authorized testing, research, and educational purposes only**.
Users are solely responsible for ensuring that their use complies with all applicable laws,
terms of service, and organizational policies. The authors assume no liability for misuse.

---

## License

This project is licensed under the [MIT License](LICENSE).
