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
    text = redact_secret_values(text)               # 등록된 바깥 API 키 값(설정) — 이름 규칙은 로그에만 `[2026-10-26]`
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


#: ★`[2026-10-26]` 로그 · 진단 기록 · 예외 문자열에서 **값을 가리는** 쿼리 · 폼 파라미터 이름(소문자로 비교한다). 바깥 API 가 키를 주소에 싣는 이름은
#:  여기 한 곳에만 적는다 — 새 공급자가 다른 이름을 쓰면 이 목록만 늘린다(wiki `quality/invariants.md` INV-CS-SEC-016).
#:  ☆x600 api 컨테이너 로그에 공공데이터 요청 주소가 `serviceKey=…` 째 찍혔다 — `httpx` INFO 줄(`log_redaction.py` 머리말).
SECRET_QUERY_PARAMS = frozenset({
    "servicekey", "key", "apikey", "api_key", "appkey", "app_key", "authkey", "auth_key", "crtfc_key", "certkey",
    "client_secret", "client_key", "consumer_key", "consumer_secret", "secret", "access_token", "refresh_token",
    "id_token", "token", "password", "passwd", "subscription-key", "x-api-key",
})
_NAMES = "|".join(sorted(map(re.escape, SECRET_QUERY_PARAMS), key=len, reverse=True))
#: 주소 · 폼 모양 `name=value` — 값은 `&` · 공백 · 따옴표 · `<>#)` 앞까지(쉼표가 든 값도 통째로 가린다)
_SECRET_PARAM = re.compile(r"(?i)(?<![A-Za-z0-9_\-])(" + _NAMES + r")=([^&\s\"'<>#)]+)")
#: JSON · 사전 글 모양 `"name": "value"` · `'name': 'value'`
_SECRET_JSON = re.compile(r"(?i)([\"'])(" + _NAMES + r")(\1\s*:\s*)([\"'])([^\"']*)(\4)")
#: 이름으로 못 잡는 자리(키가 주소 경로 조각인 공급자)를 위해 설정에 든 **키 값 자체**를 모아 둔다 — `log_redaction.register_secret_values`.
#:  값과 그 URL 인코딩 모양(`quote` · `quote_plus`)을 같이 넣는다. 8자 미만은 넣지 않는다(흔한 낱말까지 가리게 된다).
_SECRET_VALUES: set[str] = set()
SECRET_VALUE_MIN_LENGTH = 8


def add_secret_values(values) -> None:
    """가릴 값을 더한다 — 빈 값 · 짧은 값은 버린다. 원문 · `quote` · `quote_plus` 모양을 함께 넣는다."""
    from urllib.parse import quote, quote_plus

    for value in values or ():
        text = str(value or "").strip()
        if len(text) < SECRET_VALUE_MIN_LENGTH:
            continue
        _SECRET_VALUES.update({text, quote(text, safe=""), quote_plus(text, safe="")})


def redact_secrets(value: object) -> str:
    """로그 · 예외 글 — 비밀 파라미터 값(`serviceKey=…` → `serviceKey=***`, `"serviceKey": "…"`)과 등록된 키 값을 `***` 로 바꾼다. 이름 · 다른 파라미터는 그대로 둔다."""
    text = _SECRET_PARAM.sub(lambda m: m.group(1) + "=***", str(value))
    text = _SECRET_JSON.sub(lambda m: m.group(1) + m.group(2) + m.group(3) + m.group(4) + "***" + m.group(6), text)
    return redact_secret_values(text)


def redact_secret_values(value: object) -> str:
    """등록된 키 값(설정의 `*_key` · `*_secret` · `*_token` …)만 `***` 로 — 이름 규칙은 걸지 않는다(저장값 `mask_json` 이 쓴다:
    고객이 적은 링크의 `?token=` · `?key=` 는 고객 글이라 그대로 둔다)."""
    text = str(value)
    for secret in sorted(_SECRET_VALUES, key=len, reverse=True):
        if secret in text:
            text = text.replace(secret, "***")
    return text
