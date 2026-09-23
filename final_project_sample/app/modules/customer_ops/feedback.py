"""Inline S-VOC classifier.

The issue-code vocabulary is intentionally small and scenario-oriented:
``post_cancel_charge``, ``payment_failed``, ``billing_other``,
``entitlement_mismatch``, ``login_issue``, ``service_unavailable``,
``technical_other``, and ``other``.  A provider must return all four labels;
there is no silent/default classification path.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from acop_basement.core.settings import get_settings
from acop_basement.presentation.security import masked


class ClassificationFailed(RuntimeError):
    """Raised when the classifier cannot produce a complete classification."""


@dataclass(frozen=True)
class Classification:
    sentiment: str
    intent: str
    issue_code: str
    severity: str


INTENTS = frozenset({"billing", "technical", "other"})
SENTIMENTS = frozenset({"positive", "neutral", "negative"})
SEVERITIES = frozenset({"low", "medium", "high", "critical"})
ISSUE_CODES = frozenset(
    {
        "post_cancel_charge", "payment_failed", "billing_other",
        "entitlement_mismatch", "login_issue", "service_unavailable",
        "technical_other", "other",
    }
)


class LLM(Protocol):
    def __call__(self, text: str) -> dict[str, Any]: ...


def _openai_llm(text: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ClassificationFailed("OpenAI API key is missing")
    try:
        from openai import OpenAI

        response = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            seed=settings.llm_seed,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "Classify customer feedback as JSON with exactly these keys: "
                    "sentiment, intent, issue_code, severity. "
                    "intent is billing|technical|other; sentiment is "
                    "positive|neutral|negative; severity is low|medium|high|critical. "
                    "issue_code must be one of: " + ", ".join(sorted(ISSUE_CODES))
                )},
                {"role": "user", "content": text},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise ClassificationFailed("LLM returned an empty response")
        value = json.loads(content)
        if not isinstance(value, dict):
            raise ClassificationFailed("LLM response is not an object")
        return value
    except ClassificationFailed:
        raise
    except Exception as exc:
        raise ClassificationFailed(f"LLM classification failed: {exc}") from exc


def classify(text: str, llm: LLM | None = None) -> Classification:
    """Classify text through an injectable LLM; incomplete output fails loudly."""
    if not isinstance(text, str) or not text.strip():
        raise ClassificationFailed("feedback text is empty")
    provider: LLM = llm or _openai_llm
    try:
        raw = provider(masked(text))
    except ClassificationFailed:
        raise
    except Exception as exc:
        raise ClassificationFailed(f"classifier provider failed: {exc}") from exc
    if not isinstance(raw, dict):
        raise ClassificationFailed("classifier output is not an object")
    required = ("sentiment", "intent", "issue_code", "severity")
    if any(not isinstance(raw.get(key), str) or not raw[key].strip() for key in required):
        raise ClassificationFailed("classifier output is missing a required label")
    result = Classification(*(raw[key].strip() for key in required))
    if result.intent not in INTENTS or result.sentiment not in SENTIMENTS:
        raise ClassificationFailed("classifier returned an invalid intent or sentiment")
    if result.issue_code not in ISSUE_CODES or result.severity not in SEVERITIES:
        raise ClassificationFailed("classifier returned an invalid issue code or severity")
    return result
