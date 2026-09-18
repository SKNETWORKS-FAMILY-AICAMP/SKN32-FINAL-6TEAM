"""Domain-level redaction rules for values persisted by the application."""

from __future__ import annotations

import re

#: ★UUID 는 가리지 않는다(`[2026-09-18]`). UUID 가운데 숫자만 이어진 부분(`…d588-1234-4253-…`)이
#:  전화번호 규칙에 걸려 `…d588-****-4253-…` 으로 **저장됐다.** Case 상태의 `trip_id` 가 이렇게 망가져
#:  Team 이 「여행 일정을 확인하지 못했다」로 사람에게 넘기고, 중복 표식이 다음 조회와 안 맞아 같은
#:  신고를 두 번 처리했다 — UUID 가 무작위라 가끔만 나서 「원인 모름 간헐 실패」로 남아 있었다
#:  (wiki/records/reports/debugs/2026-09-18_1425_UUID가_전화번호로_가려져_Case가_가끔_사람에게_간다.md).
_UUID = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
                   r"[0-9A-Fa-f]{12}(?![0-9A-Fa-f])")


def masked(value: object) -> str:
    """UUID 사이의 조각만 가린다 — UUID 자체는 그대로 둔다."""
    text = str(value)
    ids = _UUID.findall(text)
    if not ids:
        return _mask(text)
    pieces = [_mask(piece) for piece in _UUID.split(text)]
    out = pieces[0]
    for uuid_text, piece in zip(ids, pieces[1:]):
        out += uuid_text + piece
    return out


def _mask(text: str) -> str:
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
