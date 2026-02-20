"""
fingerprint_evasion -- Browser fingerprint randomization via CDP scripts.

Provides JavaScript injection scripts that override browser APIs to
produce unique, randomized fingerprints per session. Each method
returns a JS string suitable for CDP Page.addScriptToEvaluateOnNewDocument.
"""

import random
import logging

logger = logging.getLogger(__name__)

class FingerprintEvasion:
    """Browser fingerprint randomization via CDP JavaScript injection."""

    @staticmethod
    def get_canvas_noise():
        """Return JS that adds sub-pixel noise to canvas data."""
        return """
            const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            const noise = () => Math.random() * 0.0001;
            CanvasRenderingContext2D.prototype.getImageData = function() {
                const imageData = origGetImageData.apply(this, arguments);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] += noise();
                    imageData.data[i+1] += noise();
                    imageData.data[i+2] += noise();
                }
                return imageData;
            };
            HTMLCanvasElement.prototype.toDataURL = function() {
                const ctx = this.getContext("2d");
                if (ctx) {
                    const id = ctx.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < id.data.length; i++) id.data[i] += Math.floor(noise() * 10);
                    ctx.putImageData(id, 0, 0);
                }
                return origToDataURL.apply(this, arguments);
            };
        """

    @staticmethod
    def get_audio_context_randomization():
        """Return JS that randomizes AudioContext fingerprint."""
        offset = random.uniform(0.000001, 0.00001)
        return f"""
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (AudioCtx) {{
                const origOsc = AudioCtx.prototype.createOscillator;
                const origComp = AudioCtx.prototype.createDynamicsCompressor;
                AudioCtx.prototype.createOscillator = function() {{
                    const osc = origOsc.apply(this, arguments);
                    const origStart = osc.start;
                    osc.start = function() {{ this.frequency.value += {offset}; return origStart.apply(this, arguments); }};
                    return osc;
                }};
                AudioCtx.prototype.createDynamicsCompressor = function() {{
                    const comp = origComp.apply(this, arguments);
                    if (comp.threshold) comp.threshold.value += Math.random() * 0.1 - 0.05;
                    if (comp.knee) comp.knee.value += Math.random() * 0.1 - 0.05;
                    if (comp.ratio) comp.ratio.value += Math.random() * 0.1 - 0.05;
                    return comp;
                }};
            }}
        """

    @staticmethod
    def get_webgl_shader_randomization():
        """Return JS that randomizes WebGL shader precision values."""
        nf = random.uniform(0.00001, 0.0001)
        return f"""
            const origGetSPF = WebGLRenderingContext.prototype.getShaderPrecisionFormat;
            WebGLRenderingContext.prototype.getShaderPrecisionFormat = function() {{
                const r = origGetSPF.apply(this, arguments);
                if (r) {{ r.precision += Math.floor(Math.random() * 2); r.rangeMin += {nf}; r.rangeMax += {nf}; }}
                return r;
            }};
        """

    @staticmethod
    def get_font_randomization():
        """Return JS that randomizes the detected font list."""
        font_sets = [
            ["Arial", "Helvetica", "Times New Roman", "Courier New", "Verdana", "Georgia", "Comic Sans MS", "Trebuchet MS", "Arial Black", "Impact"],
            ["Arial", "Helvetica", "Times New Roman", "Courier New", "Verdana", "Georgia", "Palatino", "Garamond", "Bookman", "Arial Narrow"],
            ["Arial", "Helvetica", "Times New Roman", "Courier New", "Verdana", "Georgia", "Noto Sans", "Lato", "Roboto", "Open Sans"],
        ]
        selected = random.choice(font_sets)
        fonts_js = ", ".join(["\\\"{}\\\"".format(f) for f in selected])
        return f"""
            const availableFonts = [{fonts_js}];
            Object.defineProperty(Document.prototype, "fonts", {{
                get: () => ({{ entries: () => availableFonts.map(f => [f, f]), values: () => availableFonts, size: availableFonts.length }})
            }});
        """

    @staticmethod
    def get_performance_randomization():
        """Return JS that adds jitter to performance.now()."""
        jitter = random.uniform(0.1, 0.5)
        return f"""
            const origPerfNow = Performance.prototype.now;
            let perfOffset = 0;
            Performance.prototype.now = function() {{
                const result = origPerfNow.apply(this, arguments);
                perfOffset += (Math.random() - 0.5) * {jitter};
                return result + perfOffset;
            }};
        """

    @staticmethod
    def get_battery_randomization():
        """Return JS that spoofs the Battery Status API."""
        level = random.uniform(0.15, 0.95)
        charging = random.choice([True, False])
        charging_js = "true" if charging else "false"
        ct = random.randint(1800, 7200) if charging else "Infinity"
        dt = random.randint(3600, 28800) if not charging else "Infinity"
        return f"""
            if (navigator.getBattery) {{
                navigator.getBattery = function() {{
                    return Promise.resolve({{ level: {level}, charging: {charging_js}, chargingTime: {ct}, dischargingTime: {dt} }});
                }};
            }}
        """

    @classmethod
    def apply_all(cls, driver):
        """Inject all fingerprint randomization scripts into the driver."""
        scripts = [
            cls.get_canvas_noise(),
            cls.get_audio_context_randomization(),
            cls.get_webgl_shader_randomization(),
            cls.get_font_randomization(),
            cls.get_performance_randomization(),
            cls.get_battery_randomization(),
        ]
        combined = "\n".join(scripts)
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": combined})
        logger.info("Applied %d fingerprint randomization scripts", len(scripts))
