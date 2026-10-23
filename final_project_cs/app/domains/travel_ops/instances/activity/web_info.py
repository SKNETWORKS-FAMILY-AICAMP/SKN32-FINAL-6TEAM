# -*- coding: utf-8 -*-
"""웹 검색(OpenAI)으로 장소 정보를 채울 때의 **입력 · 출력 계약과 검증** — 계산만 한다(LLM · DB 를 부르지 않는다). `[2026-10-19 사용자 결정]`

흐름(2026-10-19 사용자 정리):
    장소 이름 → 활동 원장에 있나?
        있다  → 비어 있는 칸만 웹 검색 (이미 채워진 칸은 패스)
        없다  → 카카오로 **실존만** 확인(응답은 저장하지 않는다) → 있으면 웹 검색(주소 · 운영시간 …) → 주소를 브이월드로 좌표(`geocode.py`)
    웹 값은 별도 표 `activity.ac_place_web_info`(마이그레이션 307)에 출처 · 인용 · 만료와 함께 둔다. 읽을 때 **원장 값이 있으면 그것, 비었을 때만 웹 값**(`effective`).

이 파일이 하는 일:
    `missing_fields`  웹 검색으로 채울 칸(원장이 비었고 웹 값이 없거나 만료된 칸)
    `schema` · `payload`  모델에 보내는 입력 · 받는 출력(Structured Outputs strict)
    `validate`        모델 답을 **검증**해 통과한 것만 `Entry` 로 — 출처 URL 이 실제 검색한 페이지인지 · 인용이 있는지 · 숫자가 인용에 있는지
    `effective`       원장 값과 웹 값 중 쓸 값

★**소개글 · 체험 안내는 다루지 않는다** — 남의 글이라 저장하지 않는다(2026-10-19 사용자 결정 · `fill_tourapi_details.HUMAN_FILLABLE` 도 뺀다).
★모르면 `null` — 지어내지 않는다. 값은 **원문 그대로**(운영시간 문장을 새로 쓰지 않는다). 요일표로 펴는 일은 기존 `read_hours` 가 한다.
★웹 값은 틀릴 수 있다 — 인용(`quote`)과 URL 이 없으면 버리고, 만료(`TTL_DAYS`)가 있다.
★프롬프트는 아직 등록 전이다(`ALLOWED_PROMPT_KEYS` 는 코어 파일) — 호출하는 쪽이 `instructions` 를 넘긴다. 초안은 `docs/activity/` 에 있다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping

from .judge.llm import _normalize_url, _parse_date, _squash
from .place_aliases import key_of

#: 웹 검색으로 채울 수 있는 칸 — `fill_tourapi_details.HUMAN_FILLABLE` 과 같은 범위 + 주소. 소개글 · 체험 안내 · 식별자 · 분류는 없다.
FIELDS = ("address", "business_hours", "closed_days", "reservation_info", "capacity", "age_limit", "fee", "spendtime", "tel", "homepage", "pet")
#: 칸 → 원장 `ac_place` 컬럼 — 원장에 값이 있으면 웹 검색을 하지 않는다. 컬럼이 없는 칸(`homepage` · `pet`)은 원장 값이 없는 것으로 본다.
LEDGER_COLUMN = {"address": "addr1", "business_hours": "usetime_text", "closed_days": "restdate_text",
                 "reservation_info": "reservation_text", "capacity": "capacity_text", "age_limit": "age_limit",
                 "fee": "fee_text", "spendtime": "spend_time", "tel": "info_center"}
#: 웹 값의 유효 기간(일). ★우리가 고른 값 — 운영시간 · 휴무는 바뀌기 쉬워 짧게, 주소 · 전화는 길게. 측정한 값이 아니다.
TTL_DAYS = {"business_hours": 30, "closed_days": 30, "fee": 90, "reservation_info": 90, "capacity": 90, "age_limit": 90,
            "spendtime": 90, "pet": 90, "address": 180, "tel": 180, "homepage": 180, "lat_lng": 365, "name": 365}
#: 숫자 일치를 확인하는 칸 — 값의 숫자는 인용에도 있어야 한다(모델이 숫자를 지어내지 않게)
NUMERIC_FIELDS = ("business_hours", "closed_days", "fee", "tel", "capacity", "age_limit", "spendtime")
VALUE_MAX = 300
QUOTE_MAX = 500
SERVICE_AREA = "서울"

#: 웹 검색을 했지만 쓸 값을 못 찾은 칸의 표시(`source`) — 같은 칸을 매번 다시 검색하지 않게 짧은 만료를 둔다.
NOTHING = "none"
NOTHING_TTL_DAYS = 7                  # ★우리가 고른 값

KIND = "place_info"
PROMPT_KEY = f"activity_judge.{KIND}"


@dataclass(frozen=True)
class Entry:
    """표 `ac_place_web_info` 한 줄."""
    field: str
    value: str
    source: str                      # web · vworld · customer
    quote: str | None = None
    url: str | None = None
    published_at: date | None = None
    expires_at: datetime | None = None


def place_key(content_id: str | None, name: str | None) -> str | None:
    """표의 장소 키 — 원장 장소면 contentid, 아니면 `web:` + 정규화한 고객 이름. 둘 다 없으면 `None`."""
    if content_id:
        return str(content_id)
    key = key_of(name or "")
    return f"web:{key}" if key else None


def _empty(value: Any) -> bool:
    return value is None or not str(value).strip()


def missing_fields(ledger_row: Mapping[str, Any] | None, web: Mapping[str, Entry] | None, now: datetime,
                   *, wanted: Iterable[str] = FIELDS) -> list[str]:
    """웹 검색으로 채울 칸 — **원장 값이 비었고** 웹 값이 없거나 만료된 칸. 이미 채워진 칸은 패스한다."""
    out = []
    for field in wanted:
        column = LEDGER_COLUMN.get(field)
        if column is not None and ledger_row is not None and not _empty(ledger_row.get(column)):
            continue
        entry = (web or {}).get(field)
        if entry is not None and entry.expires_at is not None and entry.expires_at > now:
            continue
        out.append(field)
    return out


def effective(field: str, ledger_value: Any, web: Entry | None, now: datetime) -> tuple[str | None, str | None]:
    """`(값, 출처)` — 원장 값이 있으면 그것(`ledger`), 비었을 때만 만료 전의 웹 값(`web`). 둘 다 없으면 `(None, None)`.
    「못 찾음」 표시(`none`)는 값이 아니다."""
    if not _empty(ledger_value):
        return str(ledger_value).strip(), "ledger"
    if web is not None and web.source != NOTHING and not _empty(web.value) and web.expires_at is not None and web.expires_at > now:
        return web.value, "web"
    return None, None


def not_found_markers(fields: Iterable[str], found: Iterable[str], now: datetime) -> list[Entry]:
    """웹 검색을 했는데 값을 못 얻은 칸마다 「못 찾음」 표시 — 짧은 기간 다시 검색하지 않게. 찾은 칸에는 만들지 않는다."""
    got = set(found)
    return [Entry(field, "", NOTHING, None, None, None, now + timedelta(days=NOTHING_TTL_DAYS)) for field in fields if field not in got]


# ── 모델 입력 · 출력 ─────────────────────────────────────────────

def _item_schema() -> dict[str, Any]:
    return {"type": ["object", "null"], "additionalProperties": False,
            "properties": {"value": {"type": "string"}, "quote": {"type": "string"}, "url": {"type": "string"},
                           "published_at": {"type": ["string", "null"]}},
            "required": ["value", "quote", "url", "published_at"]}


def schema(fields: Iterable[str] = FIELDS) -> dict[str, Any]:
    """Structured Outputs(strict) — 칸마다 `null`(모름) 또는 `{value, quote, url, published_at}`."""
    names = list(fields)
    return {"type": "object", "additionalProperties": False,
            "properties": {name: _item_schema() for name in names}, "required": names}


def payload(place_name: str, fields: Iterable[str], *, address: str | None = None, today: date | None = None) -> dict[str, Any]:
    """모델에게 보낼 입력 — 고객이 쓴 장소 이름 · (알면) 주소 · 찾을 칸 · 오늘. 카카오가 준 값은 넣지 않는다."""
    return {"kind": KIND, "place_name": place_name, "address": address or None, "fields": list(fields),
            "today": (today or date.today()).isoformat()}


# ── 검증 ────────────────────────────────────────────────────────

def _ints(text: str) -> set[int]:
    return {int(d) for d in re.findall(r"\d+", text)}


def validate(output: Any, *, wanted: Iterable[str], sources: Iterable[str], now: datetime,
             max_age_days: int) -> tuple[list[Entry], list[str]]:
    """모델 답을 검증해 `(통과한 Entry 들, 버린 이유들)`. 통과 조건(칸마다):
        · 값 · 인용 · URL 이 있다(길이 상한)  · URL 이 **실제로 검색한 페이지**다(`sources`)  · 게시일이 `max_age_days` 보다 오래되지 않았다(모르면 통과)
        · 숫자 칸은 값의 숫자가 인용에도 있다  · 주소는 서울이다  · 홈페이지는 http(s) · 전화는 숫자 7자리 이상
    """
    dropped: list[str] = []
    if not isinstance(output, dict):
        return [], ["output:not_object"]
    seen = {_normalize_url(u) for u in sources if isinstance(u, str) and u.strip()}
    entries: list[Entry] = []
    for field in wanted:
        item = output.get(field)
        if item is None:
            continue                                                  # 모름 — 지어내지 않는다
        if not isinstance(item, dict):
            dropped.append(f"{field}:not_object")
            continue
        value, quote, url = (str(item.get(k) or "").strip() for k in ("value", "quote", "url"))
        if not value or not quote or not url:
            dropped.append(f"{field}:missing_evidence")
            continue
        if len(value) > VALUE_MAX or len(quote) > QUOTE_MAX:
            dropped.append(f"{field}:too_long")
            continue
        if _normalize_url(url) not in seen:
            dropped.append(f"{field}:url_not_in_sources")             # 검색하지 않은 페이지를 댔다
            continue
        published = _parse_date(item.get("published_at"))
        if published is not None and (now.date() - published).days > max_age_days:
            dropped.append(f"{field}:stale")
            continue
        if field in NUMERIC_FIELDS and not _ints(value) <= _ints(quote):
            dropped.append(f"{field}:value_not_in_quote")             # 값의 숫자가 인용에 없다 — 지어냈을 수 있다
            continue
        if field == "address" and SERVICE_AREA not in value:
            dropped.append("address:out_of_area")
            continue
        if field == "homepage" and not re.match(r"https?://", value):
            dropped.append("homepage:not_url")
            continue
        if field == "tel" and len(re.findall(r"\d", value)) < 7:
            dropped.append("tel:too_short")
            continue
        if _squash(value) not in _squash(quote) and field not in ("reservation_info", "pet", "capacity", "age_limit", "spendtime"):
            # 운영시간 · 휴무 · 요금 · 주소 · 전화 · 홈페이지는 **원문 그대로**다 — 인용 안에 값이 글자 그대로 들어 있어야 한다
            dropped.append(f"{field}:value_not_verbatim")
            continue
        entries.append(Entry(field, value, "web", quote, url, published,
                             now + timedelta(days=TTL_DAYS.get(field, 90))))
    return entries, dropped
