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

# Top 50 surnames from the 2015 Statistics Korea population census surname
# table.  A surname by itself is intentionally never enough to identify PII;
# the context patterns below require an honorific or an explicit name-intro.
VERIFIED_SURNAME_CLASS = re.escape("김이박최정강조윤장임한오서신권황안송전홍유고문양손배백허남심노하곽성차주우구민류나진지엄채원천방공현")
NAME_CONTEXT_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(rf"(?<![가-힣])(?P<name>[{VERIFIED_SURNAME_CLASS}][가-힣]{{1,2}})(?=\s*(?:고객님|님|씨)(?:께서|께|은|는|이|가|을|를|의)?(?![가-힣]))"),
    re.compile(rf"(?:(?:성함|이름)은|저는|제가)\s*(?P<name>[{VERIFIED_SURNAME_CLASS}][가-힣]{{1,2}})(?=\s*(?:입니다|이에요|예요|님|씨)(?![가-힣]))"),
)


def detect_person_name_pii(text: str) -> bool:
    """Return whether text contains a verified surname in name context."""
    return any(pattern.search(text) for pattern in NAME_CONTEXT_PATTERNS)

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
    "detect_person_name_pii",
    "TONE_PROFILES",
    "DEFAULT_TONE_PROFILE",
    "decide_tone",
    "CUSTOMER_OPS_POLICY",
]
