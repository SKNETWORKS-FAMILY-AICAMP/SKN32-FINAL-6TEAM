# -*- coding: utf-8 -*-
"""고를 때 숙소 가격 재확인 — 화면 고르기(`/proposals/{id}/choose`) 앞에서 한 번. `[2026-10-13]`

왜.
    숙소 · 항공 「다른 후보」는 보류 제안으로 내밀고 고르기는 공용 고르기(`planning/pending.choose`)가 한다. 숙소 팀의 고를 때 재확인
    (`instances/lodging/team._recheck`)은 팀 Case 경로에만 있어 화면 고르기는 보여 줄 때 값 그대로 바꿨다.
    공용 고르기는 DB 를 잠근 채(`FOR UPDATE`) 돈다 — 그 안에서 바깥 검색을 부르지 않으려고 **잠그기 전에** 부른다(`trip_api._choose`).

무엇을.
    마이리얼트립 후보(`myrealtrip:<gid>`)는 상세를 한 번 더 읽는다(키 없는 소스).
    `[2026-10-13]` 구글 호텔 후보(`google:…` · `property_token`)는 SerpApi 상세 1회로 **판매처 최저가끼리** 비교한다(숙소 팀 `_recheck_google` 과 같다).
    SerpApi 는 무료 월 250회 · 하루 8회 예산 안에서만 나간다(`settings.rate_serpapi_*`) — 예산이 차면 「확인 못 함」이다.
    결과 `status`: same(그대로) · changed(바뀜 — 새 값) · gone(그 날짜 객실 없음 · 매진) · unchecked(읽지 못함 · 확인할 길 없음).
    판정과 문장은 숙소 팀 `_recheck` · `_price_note` 와 같다(목록 값과 상세 값이 다른 것은 「가격이 바뀌었다」가 아니라 기준 차이로 적는다).
"""
from __future__ import annotations

from typing import Any


#: 보여 줄 판매처 — ★숙소 팀 `instances/lodging/team.SELLER_NAMES` 와 같아야 한다(시험이 대조한다). 구글 재확인이 같은 판매처끼리 비교하도록
SELLER_NAMES = {"agoda": "아고다", "trip.com": "트립닷컴", "klook": "클룩", "tripbtoz": "트립비토즈", "booking.com": "부킹닷컴",
                "hotels.com": "호텔스닷컴", "expedia": "익스피디아", "expedia.co.kr": "익스피디아"}


def _seller_low(detail: dict[str, Any] | None) -> float | None:
    """구글 호텔 상세의 판매처 중 보여 주는 곳(공식 사이트 · `SELLER_NAMES`)의 가장 싼 1박 값."""
    prices = [row["price_per_night"] for row in (detail or {}).get("sellers") or []
              if isinstance(row.get("price_per_night"), (int, float)) and row["price_per_night"] > 0
              and (row.get("official") or str(row.get("seller") or "").strip().lower() in SELLER_NAMES)]
    return min(prices) if prices else None


def recheck_stay(source: Any, option: dict[str, Any], *, check_in: str, check_out: str, adults: int,
                 google: Any = None, keyword: str | None = None) -> dict[str, Any]:
    """`source` — 마이리얼트립 검색 소스(`stay_detail`), `google` — 구글 호텔 소스(`stay_detail(property_token, keyword, …)`).
    없으면 확인하지 못한 것으로 돌려준다(지어내지 않는다)."""
    before = option.get("price_per_night")
    provider, _, gid = str(option.get("key") or "").partition(":")
    if provider == "google":
        return _recheck_google(google, option, check_in=check_in, check_out=check_out, adults=adults, keyword=keyword)
    if provider != "myrealtrip" or not gid:
        return {"status": "unchecked", "before": before, "now": None, "reason": "no_recheck_tool"}
    if source is None:
        return {"status": "unchecked", "before": before, "now": None, "reason": "source_unavailable"}
    try:
        detail = source.stay_detail(gid=int(gid), check_in=check_in, check_out=check_out, adults=int(adults))
    except (TypeError, ValueError):
        return {"status": "unchecked", "before": before, "now": None, "reason": "bad_option"}
    if not detail or detail.get("cooldown_seconds"):
        return {"status": "unchecked", "before": before, "now": None, "reason": "detail_unreadable"}
    if detail.get("sold_out") or detail.get("no_rooms"):
        return {"status": "gone", "before": before, "now": None}
    now = detail.get("price_per_night")
    if not isinstance(now, (int, float)) or not isinstance(before, (int, float)):
        return {"status": "unchecked", "before": before, "now": now, "reason": "no_price"}
    return {"status": "same" if now == before else "changed", "before": before, "now": now,
            "basis": option.get("price_basis") or "list"}


def _shown_seller_low(option: dict[str, Any]) -> float | None:
    """보여 줄 때 판매처 최저가 — 후보의 `sellers`(보여 준 판매처) 가운데 가장 싼 1박. ★`price_from`(「1박 ○원~」)은 구글 목록가까지 넣은 최저라
    판매처끼리 비교할 기준이 아니다(☆2026-10-13 x600 확인 — 라인 호텔 명동 목록 173,845원 · 판매처 최저 176,766원이 「바뀜」으로 나왔다)."""
    prices = [s.get("price_per_night") for s in option.get("sellers") or [] if isinstance(s.get("price_per_night"), (int, float))]
    return min(prices) if prices else None


def _recheck_google(google: Any, option: dict[str, Any], *, check_in: str, check_out: str, adults: int,
                    keyword: str | None) -> dict[str, Any]:
    before = _shown_seller_low(option)
    if before is None:
        before = option.get("price_from") if option.get("price_from") is not None else option.get("price_per_night")
    token = option.get("property_token")
    if google is None or not hasattr(google, "stay_detail"):
        return {"status": "unchecked", "before": before, "now": None, "reason": "source_unavailable"}
    if not token or not keyword:
        return {"status": "unchecked", "before": before, "now": None, "reason": "no_query"}
    detail = google.stay_detail(property_token=str(token), keyword=str(keyword), check_in=check_in, check_out=check_out,
                                adults=int(adults))
    if not detail:
        return {"status": "unchecked", "before": before, "now": None, "reason": "detail_unreadable"}
    now = _seller_low(detail)
    if now is None or not isinstance(before, (int, float)):
        # 판매처가 없으면 「없어졌다」고 하지 않는다 — 매진인지 표시만 안 된 건지 가를 수 없다(숙소 팀과 같다)
        return {"status": "unchecked", "before": before, "now": None, "reason": "no_price"}
    return {"status": "same" if now == before else "changed", "before": before, "now": now, "basis": "sellers"}


def _won(value: Any) -> str:
    return f"{int(value):,}원" if isinstance(value, (int, float)) else "가격 모름"


def price_note(check: dict[str, Any] | None) -> str:
    """재확인 결과 한 문장(앞에 빈칸) — 변경 알림 끝에 붙인다. 1박 값을 모르면 아무것도 적지 않는다."""
    if not check:
        return ""
    before, now = check.get("before"), check.get("now")
    if check.get("basis") == "sellers":
        if check["status"] == "same":
            return f" 지금도 판매처 최저가 1박 {_won(now)}~ 그대로예요."
        if check["status"] == "changed":
            return f" 보여 드릴 때 1박 {_won(before)}~이던 판매처 최저가가 지금 1박 {_won(now)}~이에요."
    if check["status"] == "changed" and check.get("basis") == "list":
        return f" 목록에서는 1박 {_won(before)}이었는데, 예약 화면 기준으로 지금 1박 {_won(now)}이에요."
    if check["status"] == "changed":
        return f" 보여 드릴 때 1박 {_won(before)}이던 가격이 지금 1박 {_won(now)}이에요."
    if check["status"] == "same":
        return f" 지금 가격도 1박 {_won(now)} 그대로예요."
    if check["status"] == "unchecked" and check.get("reason") != "no_recheck_tool" and before is not None:
        return f" 지금 가격은 다시 확인하지 못했어요(보여 드릴 때 1박 {_won(before)}) — 예약 전에 링크에서 확인해 주세요."
    return ""


def over_price_limit(check: dict[str, Any] | None, option: dict[str, Any]) -> float | None:
    """`[2026-10-27 LB-05 · ST4F-709]` 고를 때 다시 본 1박 값이 고객이 말한 상한(후보의 `price_limit` — 숙소 팀이 싣는다)을 넘으면 그 상한.
    아니면 `None` — 상한을 말하지 않았거나(옛 후보 포함) · 다시 보지 못했거나(`unchecked`) · 객실이 없으면(`gone`, 따로 거절) 비교하지 않는다."""
    limit = option.get("price_limit")
    if not check or check.get("status") not in ("same", "changed") or not isinstance(limit, (int, float)):
        return None
    now = check.get("now")
    return limit if isinstance(now, (int, float)) and now > limit else None


def price_limit_refusal(check: dict[str, Any], limit: float, name: str) -> str:
    """상한을 넘어 바꾸지 않을 때 고객에게 하는 말 — 객실이 없을 때(「…남은 객실이 없어요. 일정은 그대로 두었어요.」)와 같은 꼴."""
    now = (f"지금 판매처 최저가 1박 {_won(check.get('now'))}~" if check.get("basis") == "sellers"
           else f"지금 1박 {_won(check.get('now'))}")
    return (f"{name}은(는) 다시 확인해 보니 {now}이라 말씀하신 1박 {_won(limit)} 이하를 넘어요. 일정은 그대로 두었어요. "
            "다른 후보를 고르시거나 「바꿔 줘」라고 하시면 새로 찾아 드릴게요.")


__all__ = ["over_price_limit", "price_limit_refusal", "price_note", "recheck_stay"]
