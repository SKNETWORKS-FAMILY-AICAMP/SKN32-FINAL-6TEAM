# -*- coding: utf-8 -*-
"""이 여행의 **사실**을 묻는 말에 사실로 답한다. `[2026-09-28]` (ui 세션 인계 · 사용자 지시)

★왜. 웹 화면의 빠른 질문(「하루 일정 요약」·「일정 상세」·「다음 일정」·「예약 표시」)이 **규정 검색**으로 갔다.
  규정 코퍼스에는 그 답이 없어서(실측 상위 점수 0.42~0.52, 문턱 0.55) 「규정에서 찾지 못했어요」와 제목·시각
  한 줄만 나갔다 — 화면이 스스로 제안한 질문에 되물었다. 이 질문들은 규정이 아니라 **여행 기록**이 답이다.

★답의 재료 — 전부 서버가 가진 값이다. 문장은 틀(템플릿)이 만들고 **모델은 쓰지 않는다**:
    · 일정 항목   제목 · 시각 · 종류 · 장소 이름 · 구 · 저장된 속성(영업시간 · 가격 · 결제)   — `TripStore`
    · 이동        이동 항목의 출발 시각 · 계획 수단 · `eta_min` · 산출 근거(`transfer_basis`, [추정] 표시 그대로)
    · 예약        `booking_id` · `detail.booking`(예약번호) · `detail.reserved`
    · 주소 · 운영시간  관광공사 상세 조회(`detailCommon2` · `detailIntro2`) **원문 그대로** — 해석하지 않는다
  ★값이 없으면 **모른다고 말한다** — 무엇이 없어서 모르는지도 말한다(지어내지 않는다, CLAUDE.md §0).

★무엇을 사실 질문으로 보나 — **규칙**(모델 아님). 화면 버튼 문장이 모델 판단에 흔들리면 안 된다.
  바꾸는 말(바꿔·늦어·되돌려·닫았어요 …)이 섞이면 여기서 받지 않는다 — 신고 경로로 간다.
"""
from __future__ import annotations

import re
import time as _time
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

#: 바꾸는 말 — 이 말이 있으면 사실 질문으로 받지 않는다(신고·재요청 경로)
_CHANGE = ("바꿔", "바꾸", "변경", "늦", "되돌", "취소해", "빼 줘", "빼줘", "빼 주", "닫았", "닫혀", "휴업", "문을 닫",
           "대신", "교체", "옮겨")
#: 돈·규정 말 — 예약 「표시」가 아니라 규정 질문이다
_POLICY = ("위약금", "환불", "환급", "수수료", "취소하면", "취소 하면", "규정", "보상")

KIND_LABEL = {"activity": "활동", "dining": "식사", "lodging": "숙소", "mobility": "이동"}
_WEEKDAY = "월화수목금토일"


def fact_question(message: str) -> str | None:
    """사실 질문의 종류 — `day` · `booking` · `next` · `address` · `hours` · `move` · `detail`. 아니면 None."""
    text = (message or "").strip()
    if not text or any(word in text for word in _CHANGE):
        return None
    # ★순서가 뜻이다 — 화면 버튼 문구(요약 · 다음 일정 · 상세)를 먼저 본다. 일정 **제목**에 「예약」이 든 경우가
    #   있어서(「성수 점심 식사(예약)」) 예약을 먼저 보면 「… 다음 일정을 알려 주세요」가 예약 질문이 된다(시험으로 확인)
    if "요약" in text:
        return "day"
    if any(word in text for word in ("다음 일정", "그 다음", "다음은", "다음 장소")):
        return "next"
    if any(word in text for word in ("상세", "자세히", "자세한")):
        return "detail"
    if any(word in text for word in ("주소", "위치가", "위치 알려", "어디에 있")):
        return "address"
    if any(word in text for word in ("영업시간", "영업 시간", "운영시간", "운영 시간", "몇 시까지", "여는 시간",
                                     "문 여", "휴무일", "쉬는 날", "입장 마감", "관람 시간", "닫는 시간", "몇 시에 닫")):
        return "hours"
    if any(word in text for word in ("이동", "어떻게 가", "얼마나 걸", "몇 분 걸", "출발 시각", "언제 출발",
                                     "몇 시에 출발", "가는 길", "가는 방법")):
        return "move"
    if "예약" in text and not any(word in text for word in _POLICY):
        return "booking"
    if any(word in text for word in ("하루 일정", "오늘 일정", "내일 일정", "일정 알려", "일정 보여", "전체 일정",
                                     "일정이 뭐", "일정 뭐")):
        return "day"
    if any(word in text for word in ("몇 시에", "몇시에", "언제 가", "언제예요", "몇 시예요")):
        return "detail"
    return None


# ── 대상 찾기 ─────────────────────────────────────────────────────
def _local(moment: datetime) -> datetime:
    return moment.astimezone(KST)


def _hm(moment: datetime | None) -> str:
    return _local(moment).strftime("%H:%M") if moment else "모름"


def _is(text: str) -> str:
    """「…이에요 / …예요」 — 마지막 한글 글자의 받침으로 고른다(괄호·숫자는 건너뛴다)."""
    last = next((ch for ch in reversed(text) if "가" <= ch <= "힣"), None)
    return text + ("이에요" if last is None or (ord(last) - 0xAC00) % 28 else "예요")


def _day_label(day: date) -> str:
    return f"{day.month}월 {day.day}일({_WEEKDAY[day.weekday()]})"


def _asked_day(text: str, now: datetime) -> date | None:
    found = re.search(r"(20\d\d)-(\d{1,2})-(\d{1,2})", text)
    if found:
        return date(*(int(x) for x in found.groups()))
    found = re.search(r"(\d{1,2})월\s*(\d{1,2})일", text)
    if found:
        return date(_local(now).year, int(found.group(1)), int(found.group(2)))
    if "오늘" in text:
        return _local(now).date()
    if "내일" in text:
        return _local(now).date() + timedelta(days=1)
    return None


def _asked_clock(text: str) -> str | None:
    found = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", text)
    return f"{int(found.group(1)):02d}:{found.group(2)}" if found else None


def target(items: list[Any], message: str, now: datetime) -> tuple[date | None, Any | None]:
    """(물은 날, 짚은 일정). ①날짜·시각이 둘 다 맞는 항목 ②날짜 안에서 이름이 겹치는 항목(`mentioned_item`)."""
    from .itinerary_team import mentioned_item

    day = _asked_day(message, now)
    stops = [i for i in items if i.kind != "mobility"]
    pool = [i for i in stops if _local(i.starts_at).date() == day] if day else stops
    clock = _asked_clock(message)
    item = None
    if clock:
        timed = [i for i in pool if _hm(i.starts_at) == clock]
        item = (mentioned_item(timed, message) or timed[0]) if timed else None
    if item is None:
        item = mentioned_item(pool, message)
    if day is None and item is not None:
        day = _local(item.starts_at).date()
    return day, item


# ── 사실 한 줄씩 ──────────────────────────────────────────────────
def booking_fact(item: Any) -> tuple[str, str]:
    """(짧은 값, 설명). ★「기록 없음」은 「예약 안 함」이 아니다 — 우리에게 들어온 예약 정보가 없다는 뜻이다."""
    booking = item.detail.get("booking") or {}
    if item.booking_id or booking:
        number = booking.get("booking_no") if isinstance(booking, dict) else None
        return "있음", f"예약 있음{f' · 예약번호 {number}' if number else ''}"
    if item.detail.get("reserved"):
        return "있음", "예약 있음(일정에 예약으로 표시돼 있어요)"
    return "기록 없음", "예약 기록 없음(받은 예약 정보가 없어요)"


def _stored_hours(place: dict[str, Any], day: date | None = None) -> str | None:
    """저장된 영업시간 — 날짜를 주면 그날 것(요일별 칸이 먼저, `place_hours.hours_on`)."""
    from .place_hours import hours_on

    attributes = place.get("attributes") or {}
    today = hours_on(attributes, day) if day is not None else None
    if today == "closed":
        return f"{_day_label(day)}은 쉬는 날"
    if today is not None:
        text = f"{today.opens:%H:%M}~{today.closes:%H:%M}"
        if today.last_entry:
            text += f" (입장·주문 마감 {today.last_entry:%H:%M})"
        return text
    hours = attributes.get("hours")
    if not (isinstance(hours, (list, tuple)) and len(hours) == 2):
        return None
    text = f"{hours[0]}~{hours[1]}"
    rest = attributes.get("break")
    if isinstance(rest, (list, tuple)) and len(rest) == 2:
        text += f" (쉬는 시간 {rest[0]}~{rest[1]})"
    return text


def _move_line(move: Any) -> str:
    planner = move.detail.get("planner") or {}
    route = move.detail.get("route_def") or {}
    planned = next((o for o in route.get("options") or [] if o.get("id") == route.get("planned")), None)
    how = planned.get("label") if planned else None
    minutes = (planned or {}).get("eta_min") or planner.get("travel_min")
    parts = [f"{_hm(move.starts_at)} 출발"]
    if how:
        parts.append(how)
    if minutes:
        parts.append(f"약 {minutes}분")
    basis = planner.get("transfer_basis")
    return " · ".join(parts) + (f" ({basis})" if basis else "")


def _move_between(items: list[Any], before: Any, after: Any) -> Any | None:
    moves = [i for i in items if i.kind == "mobility" and before.seq < i.seq < after.seq]
    return moves[0] if moves else None


def _stops(items: list[Any]) -> list[Any]:
    return sorted((i for i in items if i.kind != "mobility"), key=lambda i: (i.starts_at, i.seq))


def _neighbours(items: list[Any], item: Any) -> tuple[Any | None, Any | None]:
    stops = _stops(items)
    index = next((n for n, s in enumerate(stops) if s.item_id == item.item_id), None)
    if index is None:
        return None, None
    return (stops[index - 1] if index > 0 else None), (stops[index + 1] if index + 1 < len(stops) else None)


def _stop_line(item: Any) -> str:
    end = f"~{_hm(item.ends_at)}" if item.ends_at else ""
    return f"{_hm(item.starts_at)}{end} {item.title}({KIND_LABEL.get(item.kind, item.kind)})"


# ── 장소 조회(관광공사 원문) ──────────────────────────────────────
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_SECONDS = 6 * 3600


def look_up_place(place: dict[str, Any] | None, source: Any) -> dict[str, Any]:
    """주소 · 운영시간 · 휴무 **원문**. 못 가져오면 `failed` 에 이유를 적는다(조용히 비우지 않는다)."""
    out: dict[str, Any] = {"address": None, "hours_text": None, "rest_text": None, "phone": None,
                           "source": None, "failed": []}
    attributes = (place or {}).get("attributes") or {}
    content_id = str(attributes.get("source_content_id") or "")
    type_id = str(attributes.get("source_content_type_id") or "")
    if not content_id:
        out["failed"].append("관광공사 식별자가 없는 장소")
        return out
    if source is None or not hasattr(source, "operating"):
        out["failed"].append("관광공사 조회가 연결돼 있지 않음")
        return out
    cached = _CACHE.get(content_id)
    if cached and _time.time() - cached[0] < _CACHE_SECONDS:
        return dict(cached[1])
    out["source"] = "관광공사"
    try:
        common = source.by_content_id(content_id, type_id)
        if common and common.get("address"):
            out["address"] = common["address"]
        else:
            out["failed"].append("주소 조회 결과 없음")
        intro = source.operating(content_id, type_id)
        if intro:
            out["hours_text"], out["rest_text"] = intro.get("usetime_text"), intro.get("restdate_text")
            out["phone"] = intro.get("info_phone")
        else:
            out["failed"].append("운영시간 조회 결과 없음")
    except Exception as exc:                                  # noqa: BLE001 — 조회 실패도 답에 그대로 말한다
        out["failed"].append(f"조회 오류 {type(exc).__name__}")
        return out
    _CACHE[content_id] = (_time.time(), dict(out))
    return out


def _clean(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"<br\s*/?>", " / ", str(text), flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip() or None


# ── 답 ───────────────────────────────────────────────────────────
def fact_reply(kind: str, *, message: str, items: list[Any], now: datetime,
               place_source: Any = None) -> tuple[str, dict[str, Any]]:
    """(답, 근거). 근거에는 무엇을 보고 답했는지(`kind` · `item` · `day` · `lookups`)와 **문장을 누가 썼는지**
    (`writer: "template"`)를 싣는다."""
    day, item = target(items, message, now)
    basis: dict[str, Any] = {"kind": kind, "writer": "template", "day": day.isoformat() if day else None,
                             "item": item.title if item else None, "lookups": None}
    stops = _stops(items)
    if not stops:
        return "이 여행에는 아직 일정이 없어요.", basis
    days = sorted({_local(s.starts_at).date() for s in stops})

    if kind == "day":
        day = day or (_local(now).date() if _local(now).date() in days else days[0])
        basis["day"] = day.isoformat()
        return _day_answer(items, day, days), basis
    if kind == "booking":
        if item is not None and not _asked_day(message, now):
            return f"{item.title}({_day_label(_local(item.starts_at).date())} {_hm(item.starts_at)}) — "\
                   f"{booking_fact(item)[1]}.", basis
        day = day or (_local(now).date() if _local(now).date() in days else days[0])
        basis["day"] = day.isoformat()
        return _booking_answer(stops, day, days), basis
    if kind == "next":
        return _next_answer(items, stops, item, now), basis
    if item is None:
        titles = " · ".join(f"{_hm(s.starts_at)} {s.title}" for s in stops[:8])
        return (f"어느 일정을 물으신 건지 찾지 못했어요. 일정 이름이나 시각을 같이 적어 주세요.\n"
                f"이 여행의 일정 — {titles}{' …' if len(stops) > 8 else ''}"), basis
    if kind == "move":
        return _move_answer(items, item), basis
    lookup = look_up_place(item.place, place_source) if item.place else None
    basis["lookups"] = lookup
    if kind == "address":
        return _address_answer(item, lookup), basis
    if kind == "hours":
        return _hours_answer(item, lookup), basis
    return _detail_answer(items, item, lookup), basis


def _day_answer(items: list[Any], day: date, days: list[date]) -> str:
    today = [s for s in _stops(items) if _local(s.starts_at).date() == day]
    if not today:
        return (f"{_day_label(day)}에는 일정이 없어요. 이 여행의 날짜는 "
                f"{_is(' · '.join(_day_label(d) for d in days))}.")
    lines = [f"{_day_label(day)} 일정은 {len(today)}곳이에요."]
    for index, stop in enumerate(today):
        lines.append(f"· {_stop_line(stop)}")
        if index + 1 < len(today):
            move = _move_between(items, stop, today[index + 1])
            if move is not None:
                lines.append(f"   ↳ 이동: {_move_line(move)}")
    return "\n".join(lines)


def _booking_answer(stops: list[Any], day: date, days: list[date]) -> str:
    today = [s for s in stops if _local(s.starts_at).date() == day]
    if not today:
        return (f"{_day_label(day)}에는 일정이 없어요. 이 여행의 날짜는 "
                f"{_is(' · '.join(_day_label(d) for d in days))}.")
    lines = [f"{_day_label(day)} 예약 표시예요."]
    lines += [f"· {_hm(s.starts_at)} {s.title} — {booking_fact(s)[1]}" for s in today]
    if any(booking_fact(s)[0] == "기록 없음" for s in today):
        lines.append("「예약 기록 없음」은 받은 예약 정보가 없다는 뜻이에요. 직접 하신 예약이 있으면 예약번호와 함께 알려 주세요.")
    return "\n".join(lines)


def _next_answer(items: list[Any], stops: list[Any], item: Any | None, now: datetime) -> str:
    if item is not None:
        _, after = _neighbours(items, item)
        head = f"{item.title}({_hm(item.starts_at)}) 다음 일정은"
    else:
        after = next((s for s in stops if s.starts_at >= now), None)
        head = "다음 일정은"
    if after is None:
        return f"{item.title}({_hm(item.starts_at)}) 뒤로는 남은 일정이 없어요." if item else "남은 일정이 없어요."
    line = f"{head} {_day_label(_local(after.starts_at).date())} {_is(_stop_line(after))}."
    move = _move_between(items, item, after) if item is not None else None
    if move is None and item is None:
        before = [i for i in items if i.kind == "mobility" and i.seq < after.seq]
        move = before[-1] if before and _local(before[-1].starts_at).date() == _local(after.starts_at).date() else None
    if move is not None:
        line += f"\n이동: {_move_line(move)}"
    return line


def _move_answer(items: list[Any], item: Any) -> str:
    before, after = _neighbours(items, item)
    lines = [f"{item.title}({_hm(item.starts_at)}) 이동 정보예요."]
    come = _move_between(items, before, item) if before else None
    lines.append(f"· 오는 길: {_move_line(come)}" if come else "· 오는 길: 앞 일정에서 오는 이동 항목이 없어요.")
    go = _move_between(items, item, after) if after else None
    if go:
        lines.append(f"· 다음 일정({after.title} {_hm(after.starts_at)})으로: {_move_line(go)}")
    elif after:
        lines.append(f"· 다음 일정({after.title} {_hm(after.starts_at)})으로 가는 이동 항목은 없어요.")
    return "\n".join(lines)


def _lookup_note(lookup: dict[str, Any] | None) -> str:
    if not lookup or not lookup.get("failed"):
        return ""
    return " — " + ", ".join(lookup["failed"])


def _address_answer(item: Any, lookup: dict[str, Any] | None) -> str:
    place = item.place or {}
    if lookup and lookup.get("address"):
        return f"{place.get('name') or item.title} 주소는 {_is(lookup['address'])}(출처 {lookup['source']})."
    district = place.get("district")
    return (f"{place.get('name') or item.title}의 주소는 모르겠어요{_lookup_note(lookup)}."
            + (f" 저장된 값으로는 {district}에 있어요." if district else ""))


def _hours_answer(item: Any, lookup: dict[str, Any] | None) -> str:
    name = (item.place or {}).get("name") or item.title
    lines = []
    if lookup and (lookup.get("hours_text") or lookup.get("rest_text")):
        if lookup.get("hours_text"):
            lines.append(f"{name} 운영시간(관광공사 안내 원문): {_clean(lookup['hours_text'])}")
        if lookup.get("rest_text"):
            lines.append(f"쉬는 날(원문): {_clean(lookup['rest_text'])}")
    stored = _stored_hours(item.place or {}, _local(item.starts_at).date())
    if stored:
        lines.append(f"{name} 영업시간(저장된 값): {stored}")
    if not lines:
        return f"{name}의 운영시간은 모르겠어요{_lookup_note(lookup)}."
    return "\n".join(lines)


def _detail_answer(items: list[Any], item: Any, lookup: dict[str, Any] | None) -> str:
    place = item.place or {}
    attributes = place.get("attributes") or {}
    end = f"~{_hm(item.ends_at)}" if item.ends_at else ""
    lines = [f"{item.title} 일정이에요 — {_day_label(_local(item.starts_at).date())} {_hm(item.starts_at)}{end}"
             f" · {KIND_LABEL.get(item.kind, item.kind)}"]
    if place:
        where = " · ".join(x for x in (place.get("name"), place.get("district")) if x)
        lines.append(f"· 장소: {where}")
        if lookup and lookup.get("address"):
            lines.append(f"· 주소: {lookup['address']} (출처 {lookup['source']})")
        else:
            lines.append(f"· 주소: 모름{_lookup_note(lookup)}")
        hours = _hours_answer(item, lookup)
        lines += [f"· {line}" for line in hours.splitlines()]
        if attributes.get("price_krw") is not None:
            lines.append(f"· 가격(저장된 값): {int(attributes['price_krw']):,}원")
        if attributes.get("payment"):
            labels = {"card": "카드", "cash": "현금"}
            lines.append(f"· 결제(저장된 값): {', '.join(labels.get(p, p) for p in attributes['payment'])}")
    else:
        lines.append("· 장소: 이 일정에는 장소가 연결돼 있지 않아요.")
    lines.append(f"· 예약: {booking_fact(item)[1]}")
    before, after = _neighbours(items, item)
    come = _move_between(items, before, item) if before else None
    if come:
        lines.append(f"· 오는 길: {_move_line(come)}")
    if after:
        go = _move_between(items, item, after)
        lines.append(f"· 다음 일정: {_day_label(_local(after.starts_at).date())} {_stop_line(after)}"
                     + (f" — 이동 {_move_line(go)}" if go else ""))
    else:
        lines.append("· 다음 일정: 없어요(이 일정이 마지막이에요).")
    return "\n".join(lines)


__all__ = ["KIND_LABEL", "booking_fact", "fact_question", "fact_reply", "look_up_place", "target"]

