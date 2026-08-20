"""Domain vocabulary for the response generation/review team."""
from __future__ import annotations

import re
from typing import Pattern

from app.modules.customer_ops.verification_policy import CUSTOMER_OPS_POLICY


FORBIDDEN_WORDS = frozenset(
    {"guaranteed", "guarantee", "always", "never", "100%", "무조건", "반드시 보장", "절대"}
)

PII_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)"),
    re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
)

TONE_PROFILES = {
    "professional": "Write clearly and politely, with concise and precise customer-facing language.",
    "empathetic": "Acknowledge the customer's inconvenience and explain the next helpful action warmly.",
}

DEFAULT_TONE_PROFILE = "professional"


def decide_tone(sentiment: str | None) -> str:
    """Choose tone deterministically from the classified sentiment."""
    if sentiment == "negative":
        return "empathetic"
    return DEFAULT_TONE_PROFILE


# The verification vocabulary belongs to the customer-operations policy module.
# Keep this alias only as a local import target for callers that need the policy.
__all__ = [
    "FORBIDDEN_WORDS",
    "PII_PATTERNS",
    "TONE_PROFILES",
    "DEFAULT_TONE_PROFILE",
    "decide_tone",
    "CUSTOMER_OPS_POLICY",
]
