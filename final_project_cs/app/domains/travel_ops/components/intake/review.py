# -*- coding: utf-8 -*-
"""계획 확인 화면의 **검사 결과** — 장소마다 「장소 · 시간 · 운영시간 · 휴무일」, 장소 사이마다 「경로 · 수단 · 도착」. `[2026-10-02 사용자 지시 — 계획 확인 시나리오 목업]`

★왜. 읽은 일정을 확인 화면에 그냥 늘어놓으면 고객이 「이게 갈 수 있는 일정인가」를 스스로 따져야 했다(2026-10-01 「20분에 강남에서 명동」 사고). 멘토링(2026-10-01)
  「사람이 현장에서 하는 체크(실제 있나 · 이 시간에 되나 · 갈 수 있나)를 다 모아 보여 줘라」 — 서버가 읽은 값마다 이 검사를 **한 번** 하고, 화면은 그 결과를 줄줄이 보인다.

★입력은 읽은 값(`intake_claims` 한 판)뿐이다. 장소 하나 · 구간 하나마다 같은 모양의 **검사 줄** `{row, result, text}` 을 낸다.
    result  ok 통과 · filled 규칙이 채움 · warn 주의 · bad 고쳐야 함 · unknown 아직 모름(모르는 것을 통과로 두지 않는다)
    항목 status  keep 유지 · adjusted 조정(규칙이 채웠거나 고객이 고침) · review 확인 필요
    이동 status  keep · review(다음 일정에 늦게 닿음) · waiting(한쪽 장소가 정해지지 않아 아직 못 잼 — 확인 필요 개수에 안 센다)
★판정은 새로 만들지 않는다. 운영시간 · 휴무 · 겹침은 **등록 판정기**(`itinerary_checks.check_itinerary`)가 하고 — 여기서는 그 위반을 줄로 옮기기만 한다.
  그래서 확인 화면의 「주의」와 등록 때의 거절이 어긋나지 않는다. 운영시간 사실은 DB 에 읽어 둔 것만 쓴다(`intake/hours.py` — 바깥 호출 없음).
  이동은 이동 계산기(시간표) 또는 직선 어림값이다(`intake/moves.py` — 어림이면 그렇게 적는다).
★모르는 값은 모른다(`unknown`)고 적는다 — 「열려 있다」 · 「닿는다」를 지어내지 않는다(루트 `CLAUDE.md` 근거 없는 문장 금지).
★**확인 필요 개수**(`needs`)가 0 이면 `ready` — 화면의 「여행 등록」이 켜진다. 개수는 장소(status review) + 이동(status review)이다.

한 판(revision)의 검사는 판마다 한 번 계산해 `intake_reviews`(마이그레이션 040)에 둔다 — 읽을 때마다 DB · 계산기를 다시 부르지 않고, 같은 판은 늘 같은 값이다.
고치면 새 판이 생기고 그 판의 검사가 새로 계산된다(바뀌지 않은 구간은 앞 판의 값을 재사용한다).
"""
from __future__ import annotations

import json
import time
from copy import deepcopy
from datetime import date, datetime, time as dtime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.itinerary.itinerary_checks import Part, Violation, check_itinerary
from app.domains.travel_ops.components.places.place_hours import DayHours, break_span, hours_on
from .assemble import collect
from .hours import HoursFacts, closed_weekdays, facts_for, week_known_all, weekday_ko
from .moves import Leg, late_text, leg_between
from .terms import category_label
from . import taxi_pricing
from app.domains.travel_ops.components import settings_hook

KST = ZoneInfo("Asia/Seoul")
#: 한 번 계산하는 동안 이동 계산기에 쓰는 시간 상한(초). 넘으면 남은 구간은 어림값으로 낸다(이유가 줄에 적힌다) — 화면이 끝없이 기다리지 않게. ★우리가 고른 값
ENGINE_BUDGET_S = 25.0
SOURCE_LABEL = {"places": "우리 장소 목록", "tour_api": "관광공사", "kakao": "카카오 지도", "customer_pick": "직접 고른 곳",
                "customer": "직접 고른 곳"}
_HOURS_CODES = {"before_opening", "after_closing", "after_last_entry", "break_time", "outside_hours"}
_RANK = {"bad": 4, "warn": 3, "filled": 2, "ok": 1, "unknown": 0}


# ── 말 다듬기 ─────────────────────────────────────────────────────
def _jong(word: str) -> int:
    code = ord(word[-1]) - 0xAC00 if word else -1
    return code % 28 if 0 <= code <= 11171 else 0


def eul(word: str) -> str:
    return word + ("을" if _jong(word) else "를")


def ro(word: str) -> str:
    return word + ("로" if _jong(word) in (0, 8) else "으로")


def gwa(word: str) -> str:
    return word + ("과" if _jong(word) else "와")


def _line(row: str, result: str, text: str) -> dict[str, str]:
    return {"row": row, "result": result, "text": text}


def _worst(parts: list[tuple[str, str]]) -> tuple[str, str]:
    """같은 줄에 여러 말이 모이면 가장 나쁜 결과로, 말은 이어 붙인다."""
    parts = [p for p in parts if p[1]]
    return max((r for r, _ in parts), key=lambda r: _RANK[r]), " · ".join(t for _, t in parts)


#: `[2026-10-13]` 아침 「숙소 → 첫 일정」 이동의 출발 하한 — 계산기는 첫 일정 도착에 맞춰 가장 늦은 출발을 고른다(등록 쪽 `itinerary_changes.STAY_MORNING_FLOOR` 와 같다)
STAY_MORNING_FROM = "06:00"


def _dt(day: str | None, hhmm: str | None) -> datetime | None:
    if not day or not hhmm:
        return None
    try:
        return datetime.combine(date.fromisoformat(day), dtime.fromisoformat(hhmm), tzinfo=KST)
    except ValueError:
        return None


def _hm(moment: datetime) -> str:
    return moment.strftime("%H:%M")


# ── 한 항목의 장소 ───────────────────────────────────────────────
#: 이름 없이 종류 + 지역만 적은 줄의 상태 — 장소 값이 비어 있고 고르는 것은 고객이다(`line_parts.py`)
NAMELESS_STATES = ("needs_choice", "needs_name")


def place_state(row: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """(상태, 장소 값). 상태: found 찾음 · picked_nearest 이름이 여럿이라 가까운 곳을 임시로 고름 · customer 고객이 고름 ·
    none 고객이 「장소 없음」 · unresolved 못 찾음 ·
    ★`[2026-10-03]` needs_choice 이름 없이 종류 + 지역만 적은 줄(「성수 식당」) — 후보에서 고른다 · needs_name 같은 줄인데 **예약이 있다고** 적혀 있다 — 후보 대신 예약한 곳의 이름을 묻는다."""
    claim = (row["claims"] or {}).get("place")
    value = claim["value"] if claim else None
    evidence = (claim or {}).get("evidence") or {}
    if claim and claim["method"] == "customer":
        return ("none", None) if (value is None or evidence.get("none")) else ("customer", value)
    if claim and claim["method"] == "trip" and value is None:
        return "none", None                # ★`[2026-10-13]` 등록한 여행의 「장소 없음」 일정을 다시 연 것(`reopen.py`)
    if evidence.get("method") == "nameless":
        return ("needs_name" if evidence.get("booked") is True else "needs_choice"), None
    if not value or row["place"] is None:
        return "unresolved", None
    if evidence.get("method") == "kakao_nearest":
        return "picked_nearest", value
    return "found", value


def _place_line(row: dict[str, Any], state: str, value: dict[str, Any] | None) -> dict[str, str]:
    claim = (row["claims"] or {}).get("place") or {}
    evidence = claim.get("evidence") or {}
    title = row["title"] or ""
    if state == "none":
        return _line("place", "unknown", "장소 없이 두었어요 · 운영시간과 이동은 확인하지 않아요")
    if state in NAMELESS_STATES:
        parts = evidence.get("parts") or {}
        what = parts.get("label") or "장소"
        area = (parts.get("area") or {}).get("name")
        if parts.get("lodging_meal"):
            # ★`[2026-10-04]` 「호텔 조식」 — 식당이 아니다(후보 · 자동 추천은 숙소에서만 고른다).
            # ★`[2026-10-07 사용자 지적]` 고객에게는 **숙소를 정하는 일정**이라고만 말한다 — 「숙소에서 하는 식사예요」 · 「(식당으로 바꾸지 않아요)」 같은
            #   시스템이 어떻게 읽었는지의 설명은 고객 화면에 띄우지 않는다(「숙소에서 하는 식사가 아니라 그냥 호텔은 숙소를 찾고 있는 거잖아」)
            if state == "needs_name":
                return _line("place", "bad", "예약하신 숙소의 이름이 적혀 있지 않아요 — 이름을 알려 주세요")
            return _line("place", "bad", f"숙소를 정해야 해요 — {area + ' 지역 ' if area else ''}숙소의 이름이 적혀 있지 않아요 · 후보에서 골라 주세요")
        if state == "needs_name":
            return _line("place", "bad", f"예약하신 {what}의 이름이 적혀 있지 않아요 — 이름을 알려 주세요")
        return _line("place", "bad", f"{area + ' 지역 ' if area else ''}{what}의 이름이 적혀 있지 않아요 — 후보에서 골라 주세요")
    if state == "unresolved":
        blocked = evidence.get("blocked") or []
        why = " · 장소 조회가 막혀 있어서 못 찾은 것일 수 있어요" if blocked else ""
        return _line("place", "bad", f"장소를 정하지 못했어요 — 이름을 고치거나 후보에서 골라 주세요{why}")
    name = str(value["name"])
    if state == "picked_nearest":
        return _line("place", "warn", f"이름이 여러 곳이라 가까운 「{name}」으로 임시로 골랐어요 · 다르면 바꿔 주세요")
    source = str(value.get("source") or evidence.get("source") or "")
    label = SOURCE_LABEL.get(source, "장소 정보")
    if state == "customer":
        # ★`[2026-10-03]` 「직접 고른 곳이에요 · 직접 고른 곳」으로 겹쳐 나왔다 — 뒤에는 **어디서 찾았는지**(고른 값의 출처)가 온다
        origin = str(value.get("origin") or (source if source not in ("customer_pick", "customer") else ""))
        found = SOURCE_LABEL.get(origin) if origin not in ("customer_pick", "customer") else None
        return _line("place", "ok", "직접 고른 곳이에요" + (f" · {found}에서 찾았어요" if found else ""))
    tried = [str(t) for t in evidence.get("tried") or []]
    alias = next((t for t in tried if t.startswith("alias:")), None)
    query = evidence.get("query")
    if alias:
        before, _, after = alias[len("alias:"):].partition("→")
        base = f"「{before}」를 「{after}」로 바꿔 찾았어요"
    elif evidence.get("method") == "typo":
        base = f"오타로 보고 「{name}」로 고쳐 찾았어요"
    elif query and query != title:
        if row["kind"] == "dining":
            # 「광장시장 빈대떡」 — 가게 이름이 없어 시장까지만 정했다. 장소는 그곳이면 충분하다(가게를 지어내지 않는다) — 확인을 재촉하지 않는다
            return _line("place", "ok", f"가게 이름이 없어 {ro(name)} 잡았어요")
        base = f"「{title}」 중 「{query}」 부분을 {label} 정보로 찾았어요"
    elif title and name != title:
        base = f"{label} 정보로 「{name}」{'을' if _jong(name) else '를'} 찾았어요"
    else:
        base = f"{label} 정보로 찾았어요"
    if claim.get("needs_review"):
        return _line("place", "warn", base + " · 맞는지 확인해 주세요")
    return _line("place", "ok", base)


def booked_of(row: dict[str, Any], state: str) -> bool | None:
    """이 일정을 예약했다고 적혀 있나(True) · 안 했다고(False) · 말이 없다(None). 이름 없는 줄은 줄 글자의 「예약한」도 읽은 값(`line_parts`)을 쓴다."""
    if state in NAMELESS_STATES:
        return (((row["claims"] or {}).get("place") or {}).get("evidence") or {}).get("booked")
    return row.get("booked")


def nameless_parts(row: dict[str, Any], state: str) -> dict[str, Any] | None:
    """이름 없는 줄이 읽힌 조각 — `{label, kind, content_type, meal, near, area:{name, kind, latitude, longitude, radius_m}|None}`. 그 밖의 줄은 None."""
    if state not in NAMELESS_STATES:
        return None
    return (((row["claims"] or {}).get("place") or {}).get("evidence") or {}).get("parts")


def rereads_of(row: dict[str, Any]) -> list[dict[str, Any]]:
    """사진 · 스캔을 **두 번 다르게 읽은 줄**에서 나온 제목 · 예약번호 — 고객이 아직 안 골랐으면 `[{field, current, other, note}]`. `[2026-10-07 uiux 요청]`

    `other` 는 반쪽 받아쓰기에서 이 값이 무엇으로 읽혔나(`evidence.transcription_differs.other_value`, 못 정하면 None). 화면은 「지금 값 / 다른 읽기」 두 단추를 그리고
    고른 값을 `items[i].<field>` 로 보낸다 — 그러면 그 칸의 값이 고객 것(`method: customer`)이 되어 이 줄이 사라진다. 고객이 이미 고친 칸은 건너뛴다."""
    out = []
    for field in ("title", "booking_no"):
        claim = (row["claims"] or {}).get(field)
        if not claim or claim.get("method") == "customer":
            continue
        differs = (claim.get("evidence") or {}).get("transcription_differs")
        if not differs:
            continue
        current, other = claim.get("value"), differs.get("other_value")
        if other:
            note = f"사진에서 「{current}」 / 「{other}」 두 가지로 읽었어요 · 원본과 맞는 쪽을 골라 주세요"
        else:
            note = f"사진에서 이 줄을 두 가지로 읽었어요 — 「{differs.get('text')}」 / 「{differs.get('other')}」 · 원본과 맞는 쪽을 골라 주세요"
        out.append({"field": field, "current": current, "other": other, "note": note})
    return out


def _with_note(line: dict[str, str] | None, row: str, note: str) -> dict[str, str]:
    """이미 있는 줄에 말을 덧붙이고(가장 나쁜 결과 유지) 없으면 warn 줄을 만든다 — 같은 `row` 가 두 줄로 나가지 않게."""
    if line is None:
        return _line(row, "warn", note)
    result, text = _worst([(line["result"], line["text"]), ("warn", note)])
    return _line(row, result, text)


def _booking_line(booked: bool | None, state: str, kind: str) -> dict[str, str] | None:
    """예약 줄 — ok 예약이 있다(자동으로 안 바꾼다) · warn 예약이 있다는데 장소를 못 정했다 · unknown 식사인데 예약을 모른다. 말이 없는 일반 일정에는 줄이 없다."""
    if booked is True:
        if state in ("found", "customer"):
            return _line("booking", "ok", "예약이 있다고 적혀 있어요 · 예약한 일정은 자동으로 바꾸지 않아요")
        return _line("booking", "warn", "예약이 있다고 적혀 있는데 장소를 정하지 못했어요 · 예약하신 곳의 이름을 알려 주세요")
    if booked is False:
        return _line("booking", "ok", "예약 없이 가는 곳이라고 적혀 있어요")
    if state == "needs_choice" and kind == "dining":
        return _line("booking", "unknown", "예약 여부가 적혀 있지 않아요 · 이미 예약하셨다면 알려 주세요")
    return None


# ── 시간 · 운영시간 · 휴무일 ──────────────────────────────────────
def _polite(note: str) -> str:
    return note[:-1] + "어요" if note.endswith("두었다") else note


def _time_line(row: dict[str, Any], notes: dict[tuple[str, str], str], overlap: str | None,
               order_bad: bool) -> dict[str, str] | None:
    parts: list[tuple[str, str]] = []
    if not row["date"]:
        parts.append(("bad", "날짜를 모르겠어요 — 첫날 날짜를 알려 주세요"))
    if order_bad:
        parts.append(("bad", f"끝나는 시각({row['end']})이 시작({row['start']})보다 빨라요"))
    for field in ("starts_at", "ends_at"):
        note = notes.get((row["source_id"], f"{row['where']}.{field}"))
        if note:
            parts.append(("filled", _polite(note)))
    if overlap:
        parts.append(("warn", overlap))
    if not parts:
        return None
    result, text = _worst(parts)
    return _line("time", result, text)


def _live_reference(act: dict[str, Any]) -> str | None:
    """웹 공지로 확인한 임시휴무가 **판정에 반영되지 않은** 경우의 참고 문장. `[2026-10-15]` 활동 → 코어 전달 4번.

    활동 원장 판정의 `live_status` 칸(`value` · `mode` · `applied`)을 읽는다.
      - `mode: shadow`(정확도를 재는 기간) — 「닫힘」이어도 판정은 그대로다. 그래서 줄의 결과(ok · warn · bad)는 바꾸지 않고 「참고」로만 덧붙인다.
      - `mode: llm` 이고 `applied` — 판정에 반영됐다(휴무 줄이 이미 `웹 공지` 이유로 말한다) → 여기서는 덧붙이지 않는다.
      - 그 밖의 값(열었다 · 모름 · 아직 안 봄) — 보여 줄 근거가 없다. 「열었다」로 풀어 주지도 않는다.
    """
    live = act.get("live_status")
    if not isinstance(live, dict) or live.get("value") != "closed":
        return None
    if live.get("mode") == "llm" and live.get("applied") is True:
        return None
    return "참고 · 웹 공지에는 임시 휴무로 나와요(확인하는 중이라 판단에는 반영하지 않았어요)"


def _hours_lines(row: dict[str, Any], facts: HoursFacts, vios: list[Violation]) -> tuple[dict[str, str], dict[str, str]]:
    """(운영시간 줄, 휴무일 줄). 운영시간 줄에는 화면 문장과 따로 **시작 시각에 열려 있나**(`open_at` ok · bad)를 싣는다 — 알 때만.
    웹 공지 참고(`_live_reference`)는 휴무일 줄 끝에 덧붙인다 — 줄의 결과는 바꾸지 않는다.

    ★`[2026-10-15]` 운영시간 줄의 결과 `warn` 은 「시작 때 이미 닫힘」과 「끝나기 전에 닫음 · 마지막 주문 임박」을 함께 담는다.
      요식 판정 그림자(`instances/dining/shadow.py`)가 이 둘을 가르지 못해 「시작 때 닫힘」을 규칙 ok 로 세었다(정식당 11:30 · 하동관 18:00 · 진진 23:30).
      화면 문장 · 결과는 그대로 두고 비교용 값만 더한다."""
    hours, closed = _hours_and_closed(row, facts, vios)
    opened = _open_at_start(row, facts, vios)
    if opened is not None:
        hours = {**hours, "open_at": opened}
    note = _live_reference(facts.activity or {}) if row["place"] is not None else None
    if note:
        closed = {**closed, "text": f"{closed['text']} · {note}"}
    return hours, closed


def _open_at_start(row: dict[str, Any], facts: HoursFacts, vios: list[Violation]) -> str | None:
    """시작 시각에 열려 있나 — ok · bad · None(모름). 요식 원장의 그 시각 판정이 먼저, 없으면 그날 운영시간 · 입장 마감 · 브레이크로 본다."""
    when = _dt(row["date"], row["start"])
    if when is None or row["place"] is None or not facts.known:
        return None
    codes = {v.code for v in vios}
    today = hours_on(facts.attributes, when.date())
    act = facts.activity or {}
    if today == "closed" or "closed_day" in codes or act.get("closed") is True:
        return "bad"
    if facts.open_at_slot is not None:
        return "ok" if facts.open_at_slot else "bad"
    if not isinstance(today, DayHours):
        return {True: "ok", False: "bad"}.get(act.get("within_hours"))
    start = when.time()
    if today.closes < today.opens:                    # 밤을 넘겨 닫는 곳(17:00–02:00) — 여는 시각 뒤이거나 닫는 시각 전이면 연다
        if today.closes <= start < today.opens:
            return "bad"
    elif start < today.opens or (start >= today.closes and today.closes != dtime(23, 59)):
        return "bad"
    if today.last_entry and start > today.last_entry:
        return "bad"
    rest = break_span(facts.attributes)
    if rest is not None and rest[0] <= start < rest[1]:
        return "bad"
    return "ok"


def _hours_and_closed(row: dict[str, Any], facts: HoursFacts, vios: list[Violation]) -> tuple[dict[str, str], dict[str, str]]:
    """(운영시간 줄, 휴무일 줄) — 화면 문장."""
    when = _dt(row["date"], row["start"])
    if when is None or row["place"] is None:
        why = facts.why_unknown or "장소를 정하면 확인해요"
        return _line("hours", "unknown", why), _line("closed", "unknown", why)
    if not facts.known:
        return (_line("hours", "unknown", facts.why_unknown or "운영시간 정보를 아직 못 찾았어요"),
                _line("closed", "unknown", "휴무 정보가 없어요"))
    day = when.date()
    today = hours_on(facts.attributes, day)
    dow = weekday_ko(day)
    codes = {v.code: v for v in vios}
    # ★`[2026-10-13]` 활동 원장 판정(관광지) — 휴무 원문 · 중간에 닫힘을 활동 팀이 정했다(`hours.facts_for` ⑤)
    act = facts.activity or {}
    # 휴무일
    if "closed_day" in codes or today == "closed":
        why = f"({act['quote']})" if act.get("closed") is True and act.get("quote") else ""
        if act.get("closed") is True and act.get("closure_reason") == "live_status":
            # 웹 공지로 확인한 임시휴무(`llm` 모드에서 인용이 있을 때만 판정에 들어온다) — 정기 휴무 요일과 말을 구분한다
            closed = _line("closed", "bad", f"웹 공지에 임시 휴무로 나와요 · 방문일에 열지 않을 수 있어요{why}")
        else:
            closed = _line("closed", "bad", f"{dow}요일은 쉬는 날이에요 · 방문일이 휴무예요{why}")
    else:
        off = closed_weekdays(facts.attributes)
        if off:
            closed = _line("closed", "ok", f"{'·'.join(off)}요일 휴무 · 방문은 {dow}요일")
        elif week_known_all(facts.attributes):
            closed = _line("closed", "ok", "쉬는 요일이 없어요")
        elif today is not None or act.get("closed") is False:
            closed = _line("closed", "ok", f"{dow}요일은 열어요")
        else:
            closed = _line("closed", "unknown", "휴무 정보가 없어요")
        if facts.conditions:
            closed = _line("closed", "warn" if closed["result"] != "bad" else "bad",
                           closed["text"] + " · 공휴일 조건이 있어요(" + "; ".join(facts.conditions[:1]) + ")")
    # 운영시간
    if today == "closed" or "closed_day" in codes:
        if act.get("closed") is True and act.get("closure_reason") == "live_status":
            return _line("hours", "unknown", "웹 공지상 임시 휴무라 운영하지 않을 수 있어요"), closed
        return _line("hours", "unknown", "쉬는 날이라 운영하지 않아요"), closed
    if act.get("cut_short") is True and act.get("closes_at") and act.get("usable_minutes"):
        # 도착 때는 열려 있지만 끝나기 전에 닫는다 — 「이미 닫힘」과 안내가 다르다(머물 수 있는 분을 알린다)
        return _line("hours", "warn", f"{act['closes_at']}에 닫아 {act['usable_minutes']}분만 머물 수 있어요"), closed
    if not isinstance(today, DayHours):
        if act.get("within_hours") is False:
            return _line("hours", "warn", "운영시간 밖이에요 · 시각을 옮겨 주세요"), closed
        if act.get("within_hours") is True:
            return _line("hours", "ok", "운영시간 안에 머물러요"), closed
        return _line("hours", "unknown", f"{dow}요일 운영시간을 읽지 못했어요"), closed
    opens, closes = today.opens.strftime("%H:%M"), today.closes.strftime("%H:%M")
    parts: list[tuple[str, str]] = []
    if "before_opening" in codes:
        parts.append(("warn", f"{opens}에 열어요 · {row['start']} 시작은 일러요"))
    if "after_closing" in codes:
        parts.append(("warn", f"{closes}에 닫아요 · {row['end'] or row['start']}까지는 늦어요"))
    if "after_last_entry" in codes:
        last = today.last_entry.strftime("%H:%M") if today.last_entry else ""
        parts.append(("warn", f"{last} 입장 마감이에요 · {row['start']} 시작은 늦어요"))
    if "outside_hours" in codes and not parts:
        parts.append(("warn", "운영시간 밖이에요 · 시각을 옮겨 주세요"))
    if "break_time" in codes:
        brk = facts.attributes.get("break") or ["", ""]
        parts.append(("warn", f"{brk[0]}–{brk[1]} 브레이크 타임에 걸쳐요"))
    if facts.order_ok is False and facts.open_at_slot:
        parts.append(("warn", "마지막 주문이 지났을 수 있어요"))
    elif facts.needs_check and facts.open_at_slot:
        parts.append(("warn", "닫을 시각이 가까워 마지막 주문을 확인해 주세요"))
    if parts:
        result, text = _worst(parts)
        return _line("hours", result, text), closed
    brk = facts.attributes.get("break")
    extra = f" · 브레이크 {brk[0]}–{brk[1]}" if isinstance(brk, (list, tuple)) and len(brk) == 2 else ""
    return _line("hours", "ok", f"{opens}–{closes} 안에 머물러요{extra}"), closed


# ── 한 판 계산 ────────────────────────────────────────────────────
class _Budgeted:
    """이동 계산기를 부르는 시간에 상한을 건다 — 넘으면 못 채웠다고 답해 그 구간은 어림값으로 간다. 같은 질문은 다시 묻지 않고 기억한 답을 쓴다
    (시각을 맞추려고 같은 구간을 되풀이해 묻는 자동 추천이 계산기 시간을 두 번 쓰지 않게).

    ☆한 번의 호출은 중간에 끊을 수 없다(2026-10-03 실측: 먼 구간 한 번이 16초) — 상한은 **다음 호출부터** 막는다."""

    def __init__(self, engine: Callable[..., Any], seconds: float) -> None:
        self._engine, self._left = engine, seconds
        self._memo: dict[tuple, Any] = {}

    @property
    def exhausted(self) -> bool:
        return self._left <= 0

    @staticmethod
    def _key(a: dict[str, Any], b: dict[str, Any], arrive: Any, not_before: Any) -> tuple:
        return (round(a["lat"], 5), round(a["lon"], 5), round(b["lat"], 5), round(b["lon"], 5), arrive, not_before)

    def __call__(self, a: dict[str, Any], b: dict[str, Any], arrive: Any, not_before: Any = None):
        key = self._key(a, b, arrive, not_before)
        if key in self._memo:
            return self._memo[key]
        if self._left <= 0:
            return None, {"code": "budget", "reason": "이동 계산에 시간이 오래 걸려 어림값으로 냈어요"}
        started = time.monotonic()
        try:
            answer = self._engine(a, b, arrive, not_before)
        finally:
            self._left -= time.monotonic() - started
        self._memo[key] = answer
        return answer


def default_engine(party_size: int | None, modes: list[str] | None = None, *, constraints=None) -> Callable[..., Any] | None:
    """이동 계산기(시간표 판정). 제품 조립 불가는 전파하고 명시적 standalone의 기존 None 계약은 유지한다.
    ★`[2026-10-06]` 팀이 조립 때 꽂은 자리에서 받는다(D-CS-013 `team_hooks/legs.py`).
    `modes` `[2026-10-07 이동수단 고르기]` 이 수단만으로 후보를 만드는 계산기 — 고객이 구간 수단을 골랐을 때 쓴다."""
    from app.core.team_availability import TeamUnavailable

    try:
        from app.domains.travel_ops.components.team_hooks import legs

        return legs.leg_planner(party_size, constraints or {}, modes=modes)
    except TeamUnavailable:
        raise
    except Exception:                                     # noqa: BLE001 — 독립 실행의 기존 확인 화면 계약
        from app.core.service_bindings import current_bindings

        if current_bindings() is not None:
            raise
        return None


def _fixed_neighbours(conn, tenant_id: str, intake_id: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """`[2026-10-15 ST4F-490]` 수정 접수면 여행의 **고정 일정**(`reopen.frozen` — 지난 일정 · 자정을 넘는 일정 · 좌표 없는 장소 · 다루지 않는 종류)을
    (값 줄 모양, 검사 항목 모양) 짝으로 — 이동 구간을 셀 때 「고칠 수 없는 이웃」으로 시각 순서에 끼운다. 보통 접수는 [].

    ☆전에는 접수 일정끼리만 구간을 셌다 — 항공 도착 5분 뒤 13 km 떨어진 곳 시작으로 고쳐도 「등록 가능」이었고, 「완료」 때는
      고정 일정 옆 이동이 빠져 그 구간 이동 줄 · 경로선 · 출발 알림이 사라졌다(Codex 검토 2026-10-14 ②). 검사 항목(`items`)에는 넣지 않는다 —
      화면은 고정 일정을 여행에서 읽어 회색 줄로 그리고, 구간의 `from` · `to` 는 그 여행 일정 id 다.
    ★숙소 · 항공 · 업체 예약 일정은 고정이 아니라 잠금으로 접수에 들어온다(`reopen.LOCKED_KINDS` — 2026-10-15 사용자 결정)."""
    from uuid import UUID

    from app.domains.travel_ops.components.itinerary.itinerary import TripStore
    from .reopen import session

    if conn is None:
        return []                                     # DB 없이 검사만 계산하는 시험 — 수정 접수가 있을 수 없다
    opened = session(conn, tenant_id=tenant_id, intake_id=intake_id)
    if not opened or not opened["frozen_item_ids"]:
        return []
    frozen = set(opened["frozen_item_ids"])
    _trip, trip_items = TripStore(tenant_id).latest(conn, UUID(opened["trip_id"]))
    out: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item in sorted(trip_items, key=lambda i: (i.starts_at, i.seq)):
        if str(item.item_id) not in frozen or item.kind == "mobility":
            continue
        start = item.starts_at.astimezone(KST)
        end = item.ends_at.astimezone(KST) if item.ends_at else None
        place = item.place or {}
        located = place.get("latitude") is not None and place.get("longitude") is not None
        value = ({"name": place.get("name") or item.title, "latitude": float(place["latitude"]), "longitude": float(place["longitude"])}
                 if located else None)
        row = {"date": start.date().isoformat(), "start": start.strftime("%H:%M"),
               # 숙소처럼 끝이 다른 날이면 그 날짜(체크아웃) — 같은 날이면 끝 시각만
               "end": end.strftime("%H:%M") if end and end.date() == start.date() else None,
               "end_date": end.date().isoformat() if end and end.date() != start.date() else None,
               "kind": item.kind, "title": item.title, "place": value, "fixed": True}
        shown = {"id": str(item.item_id), "title": item.title, "date": row["date"], "day": None,
                 "place_state": "found" if located else "none", "place": value}
        out.append((row, shown))
    return out


def _item_id(row: dict[str, Any], positions: dict[str, int]) -> str:
    return f"{positions.get(row['source_id'], 0)}-{row['index']}"


#: 진행 이벤트로 내보내는 일정 칸 — 실시간 진행(`stream.Feed`)이 DB 에서 읽어 내는 `item` 이벤트와 **같은 칸**이다(같은 키가 나중 값으로 덮인다)
_ITEM_EVENT_FIELDS = ("id", "source_id", "index", "title", "kind", "day", "date", "starts_at", "ends_at", "end_date", "locked", "status",
                      "can_lock", "place_state", "place", "candidates_hint", "booked", "parts", "rereads")


def build(conn, *, tenant_id: str, intake_id: Any, revision: int, sources: list[dict[str, Any]],
          claims: list[dict[str, Any]], engine: Callable[..., Any] | None = None, use_engine: bool = True,
          previous: dict[str, Any] | None = None, now: datetime | None = None,
          on_event: Callable[[str, dict[str, Any]], None] | None = None,
          engine_for_mode: Callable[[str], Any] | None = None) -> dict[str, Any]:
    """한 판의 검사를 계산한다. `previous` = 앞 판의 검사 — 같은 구간(좌표 · 시각이 같음)은 그 값을 재사용한다(`sig`).

    `engine_for_mode(수단)` `[2026-10-07 이동수단 고르기]` — 고객이 구간 수단을 골랐을 때 그 수단만으로 계산하는 계산기. 안 주고 기본 계산기를 쓰면 기본 팩토리를 쓴다.
      고른 수단이 닿으면 유지(`mode_choice.state=kept`) · 안 닿으면 추천으로 복귀(`dropped` + 이유)한다.
    `on_event(이름, 몸통)` `[2026-10-03 ui 세션 요청서 2번]` — **계산이 끝나는 대로** 알린다(검사는 끝나 커밋돼야 DB 에 보여서, 이게 없으면 실시간 진행이 끝에서 한꺼번에 낸다):
      `progress{phase: hours, done, total, current}` 운영시간 확인이 한 일정씩 · `item` 과 `check` 일정마다 검사 줄이 정해지는 대로(이동 계산 **전에**) ·
      `move` 와 `progress{phase: moves}` 이동이 한 구간씩. 이 값들은 **상태의 복사본**이라 끝에 DB 에서 읽은 최종 값이 같은 키로 와서 덮는다.
    알림이 던져도 계산은 계속된다(진행 알림은 부가 기능)."""
    def note(name: str, body: dict[str, Any]) -> None:
        if on_event is None:
            return
        try:
            on_event(name, body)
        except Exception:                                     # noqa: BLE001 — 알림 실패가 검사를 막지 않는다
            pass

    got = collect(sources=sources, claims=claims)
    # ★`[2026-10-14 핫픽스]` 택시 호출 상품 고르기가 꺼져 있으면(관리 콘솔 스위치) 앞서 저장된 고른 값도 계산에 쓰지 않는다
    taxi_pick_on = settings_hook.taxi_call_product_enabled(tenant_id)
    pricing = taxi_pricing.from_trip(got.trip) if taxi_pick_on else None
    pricing_constraints = taxi_pricing.constraints(pricing)
    rows = got.rows
    positions = {str(s["source_id"]): int(s["position"]) for s in sources}
    for r in rows:
        r["source_id"] = str(r["source_id"])
    notes = {(f["source_id"], f["field"]): f["note"] for f in got.filled}
    party = None
    try:
        party = int(got.trip["party_size"]["value"]) if got.trip.get("party_size") and got.trip["party_size"]["value"] is not None else None
    except (TypeError, ValueError):
        party = None
    if engine is None and use_engine:
        engine = default_engine(party, constraints=pricing_constraints) if pricing_constraints else default_engine(party)
        if engine_for_mode is None and engine is not None:
            if pricing_constraints:
                engine_for_mode = lambda mode: default_engine(party, [mode], constraints=pricing_constraints)  # noqa: E731
            else:
                engine_for_mode = lambda mode: default_engine(party, [mode])  # noqa: E731
    budgeted = _Budgeted(engine, ENGINE_BUDGET_S) if engine is not None else None
    dates = sorted({r["date"] for r in rows if r["date"]})
    day_no = {d: i + 1 for i, d in enumerate(dates)}

    # 항목마다 운영시간 사실 → 등록 판정기에 한꺼번에 넣는다(같은 판정이 다음 일정과의 겹침도 본다)
    states = {i: place_state(r) for i, r in enumerate(rows)}
    facts: dict[int, HoursFacts] = {}
    parts: list[Part] = []
    seq_of: dict[int, int] = {}
    for i, r in enumerate(rows):
        start, end = _dt(r["date"], r["start"]), _dt(r.get("end_date") or r["date"], r["end"])   # 숙소는 끝이 체크아웃 날이다
        facts[i] = facts_for(conn, tenant_id, r["place"], r["kind"], start, end)
        note("progress", {"phase": "hours", "done": i + 1, "total": len(rows),
                          "current": {"id": _item_id(r, positions), "title": r["title"]}})
        if start is None:
            continue
        seq_of[i] = len(parts) + 1
        attributes = dict(facts[i].attributes)
        parts.append(Part(seq=len(parts) + 1, kind=r["kind"], title=r["title"] or "(제목 없음)", starts_at=start,
                          ends_at=end, place={"name": r["title"] or "", "attributes": attributes,
                                              **({"activity": facts[i].activity} if facts[i].activity else {})}))
    violations = check_itinerary(parts)
    by_seq: dict[int, list[Violation]] = {}
    for v in violations:
        for s in v.seq:
            by_seq.setdefault(s, []).append(v)
    part_by_seq = {p.seq: p for p in parts}

    items: list[dict[str, Any]] = []
    overlapped: set[str] = set()
    for i, r in enumerate(rows):
        state, value = states[i]
        mine = by_seq.get(seq_of.get(i, -1), [])
        overlap = None
        order_bad = False
        for v in mine:
            if v.code == "overlap" and v.seq[-1] == seq_of.get(i):
                earlier = part_by_seq[v.seq[0]]
                mins = int(((earlier.ends_at or earlier.starts_at) - part_by_seq[v.seq[1]].starts_at).total_seconds() // 60)
                overlap = f"{gwa(earlier.title)} {mins}분 겹쳐요 · 등록 때 막힐 수 있어요"
                overlapped.add(_item_id(r, positions))
            if v.code == "time_order":
                order_bad = True
        hours_line, closed_line = _hours_lines(r, facts[i], [v for v in mine if v.code in _HOURS_CODES | {"closed_day"}])
        lines = [_place_line(r, state, value)]
        booked = booked_of(r, state)
        booking = _booking_line(booked, state, r["kind"])
        # ★`[2026-10-07 uiux 요청]` 사진 · 스캔을 두 번 다르게 읽은 제목 · 예약번호는 **그 일정을 「확인 필요」로 만든다**(고객이 고를 때까지) — 전에는 접수 조회에만 표시가 있고
        #   이 검토 응답(계획 확인 화면이 그리는 것)에는 안 나왔다. 제목은 장소 줄에, 예약번호는 예약 줄에 말을 덧붙이고, 화면이 두 단추를 그릴 재료를 `rereads` 로 준다
        rereads = rereads_of(r)
        for reread in rereads:
            if reread["field"] == "title":
                lines[0] = _with_note(lines[0], "place", reread["note"])
            else:
                booking = _with_note(booking, "booking", reread["note"])
        if booking:
            lines.append(booking)
        t = _time_line(r, notes, overlap, order_bad)
        if t:
            lines.append(t)
        lines += [hours_line, closed_line]
        edited = any((r["claims"].get(f) or {}).get("method") == "customer"
                     for f in ("title", "date", "starts_at", "ends_at", "place", "kind"))
        results = {ln["row"]: ln["result"] for ln in lines}
        review = (any(ln["result"] == "bad" for ln in lines) or results["place"] == "warn"
                  or results.get("hours") == "warn" or bool(rereads))
        status = "review" if review else ("adjusted" if edited or any(ln["result"] == "filled" for ln in lines) else "keep")
        items.append({
            "id": _item_id(r, positions), "source_id": r["source_id"], "index": r["index"], "title": r["title"],
            "kind": r["kind"], "day": day_no.get(r["date"]), "date": r["date"], "starts_at": r["start"], "ends_at": r["end"],
            # `[2026-10-13]` 끝이 다른 날인 항목(숙소 — 체크아웃 날). 그 밖에는 None — `ends_at` 은 그대로 「시:분」이다
            "end_date": r.get("end_date"),
            "locked": bool(r["locked"]), "edited": edited, "status": status,
            "can_lock": state in ("found", "customer") and not review,
            "place_state": state,
            # 번호들(`content_id` · `content_type_id` · `place_id`)은 운영시간 표를 다시 찾는 열쇠다(자동 추천 · 후보가 쓴다). `place_id` 는 공용 장소 행의 것뿐이다
            #   (읽을 때 `_our_places` 가 공용만 읽고, 고객이 고른 값은 `place_id` 를 받지 않는다) — 남의 여행 전용 행을 가리키지 않는다
            "place": ({"name": value["name"], "latitude": value.get("latitude"), "longitude": value.get("longitude"),
                       "source": value.get("source"), "kind": value.get("kind"), "content_id": value.get("content_id"),
                       "content_type_id": value.get("content_type_id"), "place_id": value.get("place_id"),
                       # 종류 이름(관광지 · 음식점 …) — 고객이 고른 값은 보낸 이름이 먼저, 없으면 관광공사 분류 번호를 표에서 읽는다
                       "category": value.get("category") or category_label(value.get("content_type_id"))} if value else None),
            "candidates_hint": len(((r["claims"].get("place") or {}).get("evidence") or {}).get("chosen_from") or [])
            if state == "picked_nearest" else None,
            # 예약했다고 적혀 있나(True · False · 말 없음 None) · 이름 없는 줄이 읽힌 조각(그 밖은 None) — 후보 중심 · 문장의 재료
            "booked": booked, "parts": nameless_parts(r, state),
            # `[2026-10-15 ST4F-490]` 업체 예약 표에 묶인 일정(수정 접수만) — 화면은 잠금을 풀 때 「업체 예약은 따로 취소 · 변경해야 해요」를 알린다
            "vendor_booking": ((r["claims"].get("vendor_booking") or {}).get("value") is True),
            # 두 번 다르게 읽은 제목 · 예약번호 — `[{field: title | booking_no, current, other(null 이면 두 읽기 문장만), note}]`. 없으면 [] (고객이 고르면 사라진다)
            "rereads": [{k: v for k, v in reread.items() if k != "note"} for reread in rereads],
            "rows": lines})
        # 이 일정의 검사 줄이 정해졌다 — 이동 계산(오래 걸린다) 전에 알린다. 겹침으로 확인 필요가 되는 일정은 아래 끝에서 status 가 바뀔 수 있어 최종 값이 같은 키로 덮는다
        note("item", {**{k: items[-1][k] for k in _ITEM_EVENT_FIELDS}, "place": public_place(items[-1]["place"])})
        for line in lines:
            note("check", {"item": items[-1]["id"], **line})

    mode_pick = picked_modes(claims)            # {"0-0~0-1": "taxi"} — 고객이 구간마다 고른 수단(없으면 추천)
    old_moves = {m.get("sig"): m for m in (previous or {}).get("moves", []) if m.get("sig") and m.get("basis") == "timetable"}
    moves: list[dict[str, Any]] = []
    # 구간을 셀 일정 줄 — 접수 일정(값 줄 순서 그대로)에 `[2026-10-15 ST4F-490]` 수정 접수의 고정 일정을 시각 순서로 끼운다. 보통 접수는 접수 일정 그대로다
    order: list[tuple[dict[str, Any], dict[str, Any]]] = list(zip(rows, items))
    for fixed_row, fixed_item in _fixed_neighbours(conn, tenant_id, intake_id):
        fixed_item["day"] = day_no.get(fixed_row["date"])
        key = (fixed_row["date"], fixed_row["start"])
        at = next((n for n, (r, _) in enumerate(order) if r["date"] and r["start"] and (r["date"], r["start"]) > key), len(order))
        order.insert(at, (fixed_row, fixed_item))
    now_at = now or datetime.now(KST)

    def counted(x: dict[str, Any], y: dict[str, Any]) -> bool:
        """이 두 이웃 사이 구간을 세나 — 같은 날이고, 고정끼리가 아니고, 고정 일정이 낀 구간이면 아직 지나지 않았을 때(뒤 일정 시작 > 지금)."""
        if not x["date"] or x["date"] != y["date"] or (x.get("fixed") and y.get("fixed")):
            return False
        if x.get("fixed") or y.get("fixed"):
            start = _dt(y["date"], y["start"])
            return start is not None and start > now_at
        return True

    pairs = [(order[n], order[n + 1]) for n in range(len(order) - 1) if counted(order[n][0], order[n + 1][0])]
    move_total = len(pairs)
    # `[2026-10-13 사용자 지시]` 묵는 날 아침 「숙소 → 그날 첫 일정」 — 등록 뒤 일정 화면과 같은 구간을 확인 화면에서도 보인다(등록은 이 구간을 그대로 싣는다 — `registered_moves`)
    morning: list[tuple[tuple[dict[str, Any], dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]]] = []
    for i, stay in enumerate(rows):
        if stay["kind"] != "lodging" or not stay.get("end_date") or not stay["date"]:
            continue
        for j, b in enumerate(rows):
            if b["kind"] == "lodging" or not b["date"] or not (stay["date"] < b["date"] <= stay["end_date"]):
                continue
            if not any(r["date"] == b["date"] and r["kind"] != "lodging" for r in rows[:j]):
                morning.append(((stay, items[i]), (b, items[j])))      # 그날 첫 일정
    # `[2026-10-15 ST4F-490]` 수정 접수의 숙소는 늘 고정이다 — 그날 첫 일정(고정 · 접수 통틀어)이 접수 일정이고 아직 시작 전이면 아침 구간을 센다
    for stay, stay_item in (entry for entry in order if entry[0].get("fixed") and entry[0]["kind"] == "lodging"):
        if not stay.get("end_date"):
            continue
        for day in sorted({r["date"] for r, _ in order if r["date"] and stay["date"] < r["date"] <= stay["end_date"]}):
            first = next(((r, it) for r, it in order if r["date"] == day and r["kind"] != "lodging"), None)
            start = _dt(day, first[0]["start"]) if first else None
            if first is not None and not first[0].get("fixed") and start is not None and start > now_at:
                morning.append(((stay, stay_item), first))
    move_total += len(morning)

    def add_move(move: dict[str, Any], ia: dict[str, Any], ib: dict[str, Any]) -> None:
        """구간 하나가 정해졌다 — 모으고 곧바로 알린다(이동 계산이 시간의 대부분이라 화면이 이 알림으로 진행을 안다)."""
        moves.append(move)
        note("move", {k: v for k, v in move.items() if k != "sig"})
        note("progress", {"phase": "moves", "done": len(moves), "total": move_total,
                          "current": {"id": f"{ia['id']}>{ib['id']}", "title": f"{ia['title']} → {ib['title']}"}})

    for (a, ia), (b, ib) in pairs:
        # `[2026-10-13]` 숙소는 체크인 시각에 떠난다고 본다 — 끝(체크아웃)은 며칠 뒤다
        a_end = _dt(a["date"], a["start"] if a["kind"] == "lodging" else (a["end"] or a["start"]))
        b_start = _dt(b["date"], b["start"])
        if a["place"] is None or b["place"] is None or a_end is None or b_start is None:
            add_move(_waiting_move(ia, ib, mode_pick.get(f"{ia['id']}~{ib['id']}")), ia, ib)
            continue
        pa = {"key": ia["id"], "name": a["place"]["name"], "lat": float(a["place"]["latitude"]), "lon": float(a["place"]["longitude"])}
        pb = {"key": ib["id"], "name": b["place"]["name"], "lat": float(b["place"]["latitude"]), "lon": float(b["place"]["longitude"])}
        # ★재사용 키 — 이름과 정확한 좌표까지 넣는다(같은 자리에서 지점 이름만 바뀌어도 앞 판의 경로 문구가 남지 않게)
        pick = mode_pick.get(f"{ia['id']}~{ib['id']}")
        sig = (f"{pa['name']}|{pa['lat']!r},{pa['lon']!r}>{pb['name']}|{pb['lat']!r},{pb['lon']!r}@{a_end.isoformat()}>{b_start.isoformat()}"
               f"#{ia['place_state']}{ib['place_state']}" + (f"#m={pick}" if pick else "") + taxi_pricing.signature(pricing))
        if sig in old_moves:
            # 재사용하는 것은 경로 계산뿐이다 — 어느 일정 · 몇째 날인지는 지금 판의 것으로 채운다(앞에 날짜가 하나 늘어 일차만 바뀐 경우)
            add_move({**old_moves[sig], "from": ia["id"], "to": ib["id"], "day": ia["day"], "date": ia["date"]}, ia, ib)
            continue
        leg = leg_between(budgeted, pa, pb, a_end, b_start)
        choice, recommended = None, leg.mode
        if pick:
            leg, choice, recommended = _apply_pick(pick, leg, engine_for_mode, pa, pb, a_end, b_start, b["start"])
        provisional = [x["place"]["name"] for x in (ia, ib) if x["place_state"] == "picked_nearest"]
        add_move({**_move(ia, ib, leg, provisional, sig), "recommended_mode": recommended, "mode_choice": choice}, ia, ib)

    for (a, ia), (b, ib) in morning:
        floor, b_start = _dt(b["date"], STAY_MORNING_FROM), _dt(b["date"], b["start"])
        if a["place"] is None or b["place"] is None or b_start is None:
            add_move({**_waiting_move(ia, ib, mode_pick.get(f"{ia['id']}~{ib['id']}")), "day": ib["day"], "date": ib["date"],
                      "from_stay": True}, ia, ib)
            continue
        pa = {"key": ia["id"], "name": a["place"]["name"], "lat": float(a["place"]["latitude"]), "lon": float(a["place"]["longitude"])}
        pb = {"key": ib["id"], "name": b["place"]["name"], "lat": float(b["place"]["latitude"]), "lon": float(b["place"]["longitude"])}
        pick = mode_pick.get(f"{ia['id']}~{ib['id']}")
        sig = (f"stay:{pa['name']}|{pa['lat']!r},{pa['lon']!r}>{pb['name']}|{pb['lat']!r},{pb['lon']!r}@{floor.isoformat()}>{b_start.isoformat()}"
               f"#{ia['place_state']}{ib['place_state']}" + (f"#m={pick}" if pick else "") + taxi_pricing.signature(pricing))
        if sig in old_moves:
            add_move({**old_moves[sig], "from": ia["id"], "to": ib["id"], "day": ib["day"], "date": ib["date"], "from_stay": True}, ia, ib)
            continue
        leg = leg_between(budgeted, pa, pb, floor, b_start)
        choice, recommended = None, leg.mode
        if pick:
            leg, choice, recommended = _apply_pick(pick, leg, engine_for_mode, pa, pb, floor, b_start, b["start"])
        provisional = [x["place"]["name"] for x in (ia, ib) if x["place_state"] == "picked_nearest"]
        add_move({**_move(ia, ib, leg, provisional, sig), "recommended_mode": recommended, "mode_choice": choice,
                  "day": ib["day"], "date": ib["date"], "from_stay": True}, ia, ib)

    # 겹침은 보통 앞 구간이 「늦게 닿는다」로 잡혀 이동이 확인 필요를 센다. 이동으로 안 잡히는 겹침(한쪽 장소를 모르거나 같은 곳이라 이동이 없는 것)은
    # 등록 판정이 거절할 일이므로 그 일정을 확인 필요로 센다 — 안 그러면 겹친 일정이 「등록 가능」으로 보인다
    counted = {m["to"] for m in moves if m["status"] == "review"}
    for it in items:
        if it["id"] in overlapped and it["id"] not in counted and it["status"] != "review":
            it["status"], it["can_lock"] = "review", False
    needs_items = sum(1 for it in items if it["status"] == "review")
    needs_moves = sum(1 for m in moves if m["status"] == "review")
    # 지도 모양: 일차별로 목록을 읽는 화면이 묶기 쉽게 항목 순서는 날짜 · 시각 순 그대로 둔다
    engines = {m["basis"] for m in moves if m.get("basis")}
    return {"revision": revision, "built_at": (now or datetime.now(KST)).isoformat(timespec="seconds"),
            "engine": ("timetable" if engines == {"timetable"} else "estimate" if engines == {"estimate"}
                       else "mixed" if engines else None),
            "items": items, "moves": moves, "taxi_pricing": (pricing if pricing is not None else taxi_pricing.default()) if taxi_pick_on else None,
            "needs": {"items": needs_items, "moves": needs_moves, "total": needs_items + needs_moves},
            "ready": bool(items) and not got.problems and needs_items + needs_moves == 0}


def public_place(place: dict[str, Any] | None) -> dict[str, Any] | None:
    """응답에 싣는 장소 — 서버 안의 장소 행 번호(`place_id`)는 뺀다."""
    return {k: v for k, v in place.items() if k != "place_id"} if place else None


def public(payload: dict[str, Any] | None, *, tenant_id: str | None = None) -> dict[str, Any] | None:
    """응답에 싣는 모양 — 저장본에서 **내부 칸**(이동 재사용 키 `sig` · 공용 장소 행 번호 `place_id`)을 뺀 복사본. 저장본은 그대로(자동 추천이 쓴다).

    ★`[2026-10-14 핫픽스]` `tenant_id` 를 주면 택시 호출 상품 고르기가 꺼져 있는 한 `taxi_pricing` 을 비워 보낸다 —
    스위치를 끄기 전에 만들어 저장된 검사에도 화면 칸이 남지 않게. (주지 않으면 저장본 그대로 — 이전 호출과 같다)"""
    if payload is None:
        return None
    if tenant_id is not None and not settings_hook.taxi_call_product_enabled(tenant_id):
        payload = {**payload, "taxi_pricing": None}
    items = []
    for it in payload.get("items", []):
        place = it.get("place")
        items.append({**it, "place": public_place(place)})
    # `uses` 는 경로선을 그리는 쪽(`/route-shapes`)이 저장본에서 읽는다 — 확인 화면 응답 모양은 그대로 둔다
    return {**payload, "items": items,
            "moves": [{k: v for k, v in m.items() if k not in ("sig", "uses", "departure_context", "selected_option_id")}
                      for m in payload.get("moves", [])]}


MOVE_MODES = ("subway", "bus", "taxi", "walk")
MOVE_LABEL = {"subway": "지하철", "bus": "버스", "taxi": "택시", "walk": "걸음"}


def picked_modes(claims: list[dict[str, Any]]) -> dict[str, str]:
    """고객이 구간마다 고른 수단 — 값 줄 `moves[{from}~{to}].mode`(고객 값 · `recommended` 로 되돌리면 값이 비어 이 표에서 빠진다).

    ★`[2026-10-14]` 수정 접수는 등록한 여행에 이미 정해 둔 수단을 `method: "trip"` 값 줄로 싣는다(`reopen.open_for_trip`) — 그것도 고른 수단으로 본다.
    안 그러면 다시 연 수정 화면이 저장된 수단(예: 지하철) 대신 추천(예: 도보)을 보였다(x600 실서버 확인). 칸마다 **마지막 값**이 이긴다 — 고객이 뒤에
    「추천으로」(빈 값)를 고르면 여행에서 가져온 수단도 빠진다."""
    out: dict[str, str] = {}
    for c in claims:
        field = str(c.get("field") or "")
        if not (field.startswith("moves[") and field.endswith("].mode") and c.get("method") in ("customer", "trip")):
            continue
        pair = field[len("moves["):-len("].mode")]
        if c.get("value") in MOVE_MODES:
            out[pair] = c["value"]
        else:
            out.pop(pair, None)
    return out


def customer_mode_pairs(claims: list[dict[str, Any]]) -> set[str]:
    """`[2026-10-14]` 고객이 **이 접수에서** 수단을 고르거나 「추천으로」 되돌린 구간 — 수정 접수의 「완료」가 그 구간만 옛 이동을 갈음한다(`registered_moves.fill_edited_moves`).
    여행에서 가져온 수단(`method: "trip"`)은 고친 것이 아니다."""
    return {str(c.get("field"))[len("moves["):-len("].mode")] for c in claims
            if str(c.get("field") or "").startswith("moves[") and str(c.get("field")).endswith("].mode") and c.get("method") == "customer"}


def mode_fits(leg: Leg) -> bool:
    """고른 수단이 **닿고 확인됐나** — 시간표 구간은 시간표로 확인(`verified`)돼야 한다. 택시 · 걸음은 시간표가 없다(끝나는 대로 떠난다)."""
    if leg.basis != "timetable" or leg.slack_min < 0:
        return False
    return True if leg.mode in ("taxi", "walk") else bool(leg.verified)


def why_not(label: str, leg: Leg | None, b_hhmm: str) -> str:
    """고른 수단이 안 닿는 이유 — 서버가 완성한 문장(화면은 그대로 보여 준다)."""
    if leg is None or leg.basis != "timetable" or leg.mode == "estimate":
        return f"{ro(label)}는 이 구간을 계산하지 못했어요"
    if leg.slack_min < 0:
        return f"{ro(label)}는 {-leg.slack_min}분 늦어요 · 다음 일정이 {b_hhmm}에 시작해요"
    return f"{label} — 시간표로 확인하지 못했어요 · 열차·버스를 놓치면 늦을 수 있어요"


def _apply_pick(pick: str, rec_leg: Leg, engine_for_mode: Callable[[str], Any] | None, pa: dict[str, Any],
                pb: dict[str, Any], a_end: datetime, b_start: datetime, b_hhmm: str):
    """(최종 구간, mode_choice, 추천 수단). 고른 수단으로 같은 구간을 다시 계산해 닿으면 그것을 쓰고(kept), 안 닿으면 추천으로 되돌린다(dropped + 이유)."""
    recommended = rec_leg.mode
    engine = engine_for_mode(pick) if engine_for_mode is not None else None
    if engine is None:
        return rec_leg, {"mode": pick, "state": "dropped", "why": "이동 계산기가 꺼져 있어 고른 수단으로 계산하지 못했어요"}, recommended
    try:
        mine = leg_between(_Budgeted(engine, ENGINE_BUDGET_S), pa, pb, a_end, b_start)
    except Exception:                                     # noqa: BLE001 — 한 수단의 오류가 확인 화면을 막지 않는다
        mine = None
    if mine is not None and mine.mode == pick and mode_fits(mine):
        return mine, {"mode": pick, "state": "kept"}, recommended
    return rec_leg, {"mode": pick, "state": "dropped", "why": why_not(MOVE_LABEL.get(pick, pick), mine, b_hhmm)}, recommended


def _waiting_move(a: dict[str, Any], b: dict[str, Any], pick: str | None = None) -> dict[str, Any]:
    wait = "한쪽 장소가 정해지지 않았어요"
    choice = {"mode": pick, "state": "dropped", "why": "장소가 정해지면 고른 수단으로 계산해요"} if pick else None
    return {"recommended_mode": None, "mode_choice": choice,
            "from": a["id"], "to": b["id"], "day": a["day"], "date": a["date"], "status": "waiting", "mode": None,
            "mode_label": None, "minutes": None, "km": None, "depart": None, "arrive": None, "slack_min": None,
            "basis": None, "summary": "장소가 정해지면 경로를 찾아요", "sig": None,
            "rows": [_line("route", "unknown", wait), _line("mode", "unknown", "장소를 정하면 찾아요"),
                     _line("arrival", "unknown", "장소를 정하면 확인해요")]}


def _move(a: dict[str, Any], b: dict[str, Any], leg: Leg, provisional: list[str], sig: str) -> dict[str, Any]:
    estimate = leg.basis == "estimate"
    if estimate:
        route = _line("route", "warn", f"이동 계산기로 구하지 못해 직선거리로 어림했어요 · {leg.why}")
    elif provisional:
        route = _line("route", "warn", f"{eul(provisional[0])} 임시로 골라서 그 곳 기준으로 계산했어요 · {leg.route}")
    else:
        route = _line("route", "ok", leg.route)
    mode = _line("mode", "ok", f"{leg.mode_label} {leg.minutes}분 · {leg.km}km" + (" [추정]" if estimate else ""))
    late = leg.slack_min < 0
    # 시간표로 확인하지 못한 값(이동 시간만 더함)이면 늦지 않아도 빠듯하다고 알린다 — 열차 · 버스를 기다리는 시간이 빠져 있다
    note = " · 시간표로 확인하지 못했어요(열차·버스를 놓치면 늦을 수 있어요)" if leg.tight else ""
    arrival = _line("arrival", "warn" if late or leg.tight else "ok",
                    f"{_hm(leg.depart)}에 나서면 {_hm(leg.arrive)} 도착 · {late_text(leg.slack_min)}{note}")
    return {"from": a["id"], "to": b["id"], "day": a["day"], "date": a["date"], "status": "review" if late else "keep",
            "mode": leg.mode, "mode_label": leg.mode_label, "minutes": leg.minutes, "km": leg.km,
            "depart": _hm(leg.depart), "arrive": _hm(leg.arrive), "slack_min": leg.slack_min, "basis": leg.basis,
            "summary": f"{leg.mode_label} {leg.minutes}분 · {leg.km}km" + (" [추정]" if estimate else ""),
            "fare_krw": leg.fare_krw, "sig": sig, "uses": list(leg.uses),
            "departure_context": deepcopy(leg.departure_context), "selected_option_id": leg.selected_option_id,
            "rows": [route, mode, arrival]}


# ── 저장 · 읽기 ──────────────────────────────────────────────────
def load(conn, tenant_id: str, intake_id: Any, revision: int) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute("SELECT payload FROM intake_reviews WHERE tenant_id=%s AND intake_id=%s AND revision=%s",
                    (tenant_id, intake_id, revision))
        row = cur.fetchone()
    return dict(row[0]) if row else None


def store(conn, tenant_id: str, intake_id: Any, revision: int, payload: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO intake_reviews (tenant_id, intake_id, revision, payload) VALUES (%s,%s,%s,%s) "
                    "ON CONFLICT (intake_id, revision) DO UPDATE SET payload=EXCLUDED.payload, built_at=now()",
                    (tenant_id, intake_id, revision, json.dumps(payload, ensure_ascii=False, default=str)))


def ensure(conn, *, tenant_id: str, intake_id: Any, revision: int, sources: list[dict[str, Any]],
           claims: list[dict[str, Any]], force: bool = False, previous_revision: int | None = None,
           **options: Any) -> dict[str, Any]:
    """그 판의 검사를 돌려준다 — 저장된 것이 있으면 그것, 없거나 `force` 면 새로 계산해 저장한다."""
    if not force:
        cached = load(conn, tenant_id, intake_id, revision)
        if cached is not None:
            return cached
    previous = load(conn, tenant_id, intake_id, previous_revision) if previous_revision else None
    payload = build(conn, tenant_id=tenant_id, intake_id=intake_id, revision=revision, sources=sources, claims=claims,
                    previous=previous, **options)
    store(conn, tenant_id, intake_id, revision, payload)
    return payload


__all__ = ["ENGINE_BUDGET_S", "build", "default_engine", "ensure", "load", "place_state", "store"]

