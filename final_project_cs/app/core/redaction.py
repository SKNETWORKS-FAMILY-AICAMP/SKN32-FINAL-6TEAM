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


#: ★`[2026-10-26 integ-rm9]` 밖(유료 모델)으로 보내는 글에만 더 거는 전화 규칙 — `masked` 의 3-4-4 하이픈 규칙이 놓치는 모양.
#:  휴대폰 01[016789] 는 구분자 없음 · 공백 · 점 · 가운데 3자리, 국가번호 +82(0 뺀 10 · 2 …), 지역번호 02 · 0[3-6][1-5] · 070 은 구분자 있거나 없거나.
#:  숫자 앞뒤에 다른 숫자가 붙어 있으면(더 긴 번호 · 날짜 · 금액의 일부) 걸지 않는다. 날짜(2026-10-26 · 20261026) · 시각(10:30 · 1030) ·
#:  0 으로 시작하지 않는 예약번호는 자리 수 · 첫 자리가 달라 걸리지 않는다. 앞 3자리(지역번호)와 끝 4자리만 남긴다.
_SEP = r"[ .\-]?"
_OUTBOUND_PHONES = (
    re.compile(r"(?<![\d+])(01[016789])" + _SEP + r"(\d{3,4})" + _SEP + r"(\d{4})(?!\d)"),
    re.compile(r"(?<![\d+])(\+?82)[ .\-]?(0?1[016789])" + _SEP + r"(\d{3,4})" + _SEP + r"(\d{4})(?!\d)"),
    re.compile(r"(?<![\d+])(\+?82)[ .\-]?(0?2|0?[3-6][1-5]|0?70)" + _SEP + r"(\d{3,4})" + _SEP + r"(\d{4})(?!\d)"),
    re.compile(r"(?<![\d+])(02|0[3-6][1-5]|070)" + _SEP + r"(\d{3,4})" + _SEP + r"(\d{4})(?!\d)"),
)


def _hide_middle(match: re.Match[str]) -> str:
    middle = match.lastindex - 1                         # 끝에서 두 번째 묶음이 가운데 번호다(구분자 · 앞자리는 그대로 둔다)
    whole = match.group(0)
    begin, end = match.start(middle) - match.start(), match.end(middle) - match.start()
    return whole[:begin] + "****" + whole[end:]


def _mask_outbound(text: str) -> str:
    for rule in _OUTBOUND_PHONES:
        text = rule.sub(_hide_middle, text)
    return text


def masked_outbound(value: object) -> str:
    """유료 모델로 보내는 글 — `masked` 에 구분자 없는 휴대폰 · 지역번호 · +82 모양을 더 가린다(UUID 는 그대로).
    저장값(`mask_json`)은 바꾸지 않는다. 이름 · 예약번호는 여전히 가리지 못한다(wiki `llm-failover.md` 7-1)."""
    text = masked(value)
    ids = _UUID.findall(text)
    pieces = [_mask_outbound(piece) for piece in _UUID.split(text)]
    out = pieces[0]
    for uuid_text, piece in zip(ids, pieces[1:]):
        out += uuid_text + piece
    return out


def mask_json(value: object) -> object:
    """Recursively redact sensitive string values before persistence."""
    if isinstance(value, dict):
        return {key: mask_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_json(item) for item in value]
    return masked(value) if isinstance(value, str) else value
