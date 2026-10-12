"""Domain-level redaction rules for values persisted by the application."""

from __future__ import annotations

import re


def masked(value: object) -> str:
    text = str(value)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]+\b", "[REDACTED_API_KEY]", text)
    text = re.sub(r"\bpay_[A-Za-z0-9_-]+\b", "[REDACTED_PAYMENT_ID]", text)
    text = re.sub(r"(?<!\d)(\d{3})-(\d{4})-(\d{4})(?!\d)", r"\1-****-\3", text)
    text = re.sub(r"(?<!\d)(\d{4})[ -](\d{4})[ -](\d{4})[ -](\d{4})(?!\d)", r"**** **** **** \4", text)
    text = re.sub(r"\b([^\s@]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", lambda m: m.group(1)[0] + "***@" + m.group(2), text)
    return text


def mask_json(value: object) -> object:
    """Recursively redact sensitive string values before persistence."""
    if isinstance(value, dict):
        return {key: mask_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_json(item) for item in value]
    return masked(value) if isinstance(value, str) else value
