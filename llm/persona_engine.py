"""Persona engine for generating diverse synthetic user personas."""

import random
from copy import deepcopy
from typing import Any, Dict, List, Optional


# Default dimension definitions
_DEFAULT_DIMENSIONS: Dict[str, Dict[str, Any]] = {
    "age": {
        "values": ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"],
    },
    "gender": {
        "values": ["male", "female", "non-binary"],
    },
    "personality_type": {
        "values": ["analytical", "expressive", "driver", "amiable"],
        "word_range": (40, 200),
        "tone": ["formal", "casual", "enthusiastic", "reserved"],
    },
    "communication_style": {
        "values": ["concise", "verbose", "storytelling", "bullet-point", "conversational"],
    },
    "education_level": {
        "values": ["high-school", "some-college", "bachelors", "masters", "doctorate"],
    },
    "mood": {
        "values": [
            "happy", "neutral", "frustrated", "curious",
            "skeptical", "excited", "indifferent",
        ],
    },
}


class PersonaEngine:
    """Generates diverse synthetic personas by sampling configurable dimensions."""

    def __init__(self, dimensions: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        """
        Initialize with optional custom dimension definitions.

        Args:
            dimensions: Mapping of dimension name to config dict.  Each config
                must contain a ``values`` key with a list of possible values.
                Optional keys include ``word_range`` and ``tone``.
        """
        self._dimensions = deepcopy(dimensions or _DEFAULT_DIMENSIONS)
        self._generated_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_persona(self, attempt: int = 0) -> Dict[str, Any]:
        """
        Generate a random persona by sampling each dimension.

        Args:
            attempt: Retry counter; higher values shift sampling weights
                toward less-common options to increase diversity.

        Returns:
            Dictionary mapping dimension names to sampled values.
        """
        persona: Dict[str, Any] = {}
        for name, config in self._dimensions.items():
            values = config["values"]
            if attempt > 0 and len(values) > 1:
                # Shift probability mass toward later (rarer) options
                weights = [1.0 + attempt * (i / len(values)) for i in range(len(values))]
                chosen = random.choices(values, weights=weights, k=1)[0]
            else:
                chosen = random.choice(values)
            persona[name] = chosen

            # Attach optional metadata
            if "word_range" in config:
                lo, hi = config["word_range"]
                persona[f"{name}_word_target"] = random.randint(lo, hi)
            if "tone" in config:
                persona[f"{name}_tone"] = random.choice(config["tone"])

        self._generated_count += 1
        return persona

    def build_prompt(self, persona: Dict[str, Any], task_template: str) -> str:
        """
        Assemble a full prompt from a persona context block and a task template.

        Args:
            persona: Persona dictionary (as returned by ``generate_persona``).
            task_template: A string that may contain ``{persona_block}`` placeholder.

        Returns:
            Fully assembled prompt string.
        """
        lines = ["[Persona Context]"]
        for key, value in persona.items():
            label = key.replace("_", " ").title()
            lines.append(f"  {label}: {value}")
        persona_block = "\n".join(lines)

        if "{persona_block}" in task_template:
            return task_template.replace("{persona_block}", persona_block)
        return f"{persona_block}\n\n{task_template}"

    def add_dimension(self, name: str, values: List[str], **kwargs: Any) -> None:
        """
        Register a new dimension or overwrite an existing one.

        Args:
            name: Dimension name (e.g. ``"occupation"``).
            values: List of possible values for this dimension.
            **kwargs: Optional extras such as ``word_range`` or ``tone``.
        """
        config: Dict[str, Any] = {"values": list(values)}
        config.update(kwargs)
        self._dimensions[name] = config

    @property
    def stats(self) -> Dict[str, Any]:
        """Return engine statistics."""
        return {
            "dimensions": list(self._dimensions.keys()),
            "dimension_count": len(self._dimensions),
            "total_generated": self._generated_count,
            "cardinality": {
                name: len(cfg["values"]) for name, cfg in self._dimensions.items()
            },
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"PersonaEngine(dimensions={len(self._dimensions)}, "
            f"generated={self._generated_count})"
        )
