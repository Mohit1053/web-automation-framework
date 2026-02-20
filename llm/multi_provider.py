"""Multi-provider LLM abstraction with failover and cost estimation."""

import hashlib
import itertools
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Container for a single LLM generation result."""

    text: str
    provider: str
    model: str
    estimated_tokens: int = 0
    estimated_cost: float = 0.0
    latency_ms: float = 0.0


class LLMProvider(ABC):
    """Abstract base for LLM providers with automatic API-key rotation."""

    COST_PER_1K_TOKENS: float = 0.0

    def __init__(self, api_keys: Sequence[str], model: str, **kwargs: Any) -> None:
        if not api_keys:
            raise ValueError("At least one API key is required.")
        self.model = model
        self._key_cycle = itertools.cycle(api_keys)
        self._num_keys = len(api_keys)
        self._extra_config = kwargs
        self._configure()

    @abstractmethod
    def _configure(self) -> None:
        """Provider-specific SDK configuration."""

    @abstractmethod
    def _call_api(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Execute a single generation call and return raw text."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def next_key(self) -> str:
        """Return the next API key from the rotation pool."""
        return next(self._key_cycle)

    def estimate_cost(self, text: str) -> float:
        """Approximate cost based on token count heuristic (1 token ~ 4 chars)."""
        approx_tokens = max(1, len(text) // 4)
        return (approx_tokens / 1000.0) * self.COST_PER_1K_TOKENS

    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1024) -> GenerationResult:
        """Generate text with timing and cost estimation."""
        start = time.perf_counter()
        raw = self._call_api(prompt, temperature, max_tokens)
        elapsed = (time.perf_counter() - start) * 1000.0
        approx_tokens = max(1, len(raw) // 4)
        return GenerationResult(
            text=raw,
            provider=self.name,
            model=self.model,
            estimated_tokens=approx_tokens,
            estimated_cost=self.estimate_cost(raw),
            latency_ms=round(elapsed, 2),
        )


class GeminiProvider(LLMProvider):
    """Google Gemini / Generative AI provider."""

    COST_PER_1K_TOKENS = 0.0005

    def _configure(self) -> None:
        try:
            import google.generativeai as genai  # noqa: F401
            self._genai = genai
        except ImportError:
            logger.warning("google-generativeai not installed; Gemini calls will fail.")
            self._genai = None

    def _call_api(self, prompt: str, temperature: float, max_tokens: int) -> str:
        if self._genai is None:
            raise RuntimeError("google-generativeai SDK is not available.")
        self._genai.configure(api_key=self.next_key())
        model = self._genai.GenerativeModel(self.model)
        config = self._genai.types.GenerationConfig(
            temperature=temperature, max_output_tokens=max_tokens
        )
        response = model.generate_content(prompt, generation_config=config)
        return response.text


class OpenAIProvider(LLMProvider):
    """OpenAI ChatCompletion provider."""

    COST_PER_1K_TOKENS = 0.002

    def _configure(self) -> None:
        try:
            import openai  # noqa: F401
            self._openai = openai
        except ImportError:
            logger.warning("openai not installed; OpenAI calls will fail.")
            self._openai = None

    def _call_api(self, prompt: str, temperature: float, max_tokens: int) -> str:
        if self._openai is None:
            raise RuntimeError("openai SDK is not available.")
        client = self._openai.OpenAI(api_key=self.next_key())
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    COST_PER_1K_TOKENS = 0.008

    def _configure(self) -> None:
        try:
            import anthropic  # noqa: F401
            self._anthropic = anthropic
        except ImportError:
            logger.warning("anthropic not installed; Anthropic calls will fail.")
            self._anthropic = None

    def _call_api(self, prompt: str, temperature: float, max_tokens: int) -> str:
        if self._anthropic is None:
            raise RuntimeError("anthropic SDK is not available.")
        client = self._anthropic.Anthropic(api_key=self.next_key())
        message = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text


class MultiProviderLLM:
    """Orchestrator that distributes generation across multiple providers with failover."""

    def __init__(self, providers: Sequence[LLMProvider], max_retries: int = 2) -> None:
        if not providers:
            raise ValueError("At least one provider is required.")
        self.providers = list(providers)
        self.max_retries = max_retries
        self._seen_hashes: set = set()
        self._stats: Dict[str, int] = {"calls": 0, "failures": 0, "deduped": 0}

    @staticmethod
    def _content_hash(text: str) -> str:
        """SHA-256 digest for deduplication."""
        return hashlib.sha256(text.strip().lower().encode()).hexdigest()

    def generate(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 1024
    ) -> Optional[GenerationResult]:
        """Try each provider in order until one succeeds."""
        self._stats["calls"] += 1
        last_error: Optional[Exception] = None
        for provider in self.providers:
            for attempt in range(self.max_retries + 1):
                try:
                    result = provider.generate(prompt, temperature, max_tokens)
                    h = self._content_hash(result.text)
                    if h in self._seen_hashes:
                        self._stats["deduped"] += 1
                        logger.debug(
                            "Duplicate content detected from %s; skipping.",
                            provider.name,
                        )
                        break
                    self._seen_hashes.add(h)
                    return result
                except Exception as exc:
                    last_error = exc
                    wait = 2 ** attempt
                    logger.warning(
                        "Provider %s attempt %d failed: %s. Retrying in %ds.",
                        provider.name,
                        attempt + 1,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
        self._stats["failures"] += 1
        logger.error("All providers exhausted. Last error: %s", last_error)
        return None

    def batch_generate(
        self,
        prompts: Sequence[str],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> List[Optional[GenerationResult]]:
        """Generate results for a batch of prompts sequentially."""
        return [self.generate(p, temperature, max_tokens) for p in prompts]

    def cost_summary(self) -> Dict[str, Any]:
        """Return aggregate cost and call statistics."""
        return {
            "total_calls": self._stats["calls"],
            "failures": self._stats["failures"],
            "deduped": self._stats["deduped"],
            "unique_generations": len(self._seen_hashes),
        }

    def reset(self) -> None:
        """Clear deduplication cache and reset stats."""
        self._seen_hashes.clear()
        self._stats = {"calls": 0, "failures": 0, "deduped": 0}
