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
from datetime import date, datetime, time as dtime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ..itinerary_checks import Part, Violation, check_itinerary
from ..place_hours import DayHours, hours_on
from .assemble import collect
from .hours import HoursFacts, closed_weekdays, facts_for, week_known_all, weekday_ko
from .moves import Leg, late_text, leg_between
from .terms import category_label

KST = ZoneInfo("Asia/Seoul")
#: 한 번 계산하는 동안 이동 계산기에 쓰는 시간 상한(초). 넘으면 남은 구간은 어림값으로 낸다(이유가 줄에 적힌다) — 화면이 끝없이 기다리지 않게. ★우리가 고른 값
ENGINE_BUDGET_S = 25.0
SOURCE_LABEL = {"places": "우리 장소 목록", "tour_api": "관광공사", "kakao": "카카오 지도", "customer_pick": "직접 고른 곳",
                "customer": "직접 고른 곳"}
_HOURS_CODES = {"before_opening", "after_closing", "after_last_entry", "break_time"}
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


def _hours_lines(row: dict[str, Any], facts: HoursFacts, vios: list[Violation]) -> tuple[dict[str, str], dict[str, str]]:
    """(운영시간 줄, 휴무일 줄)."""
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
    # 휴무일
    if "closed_day" in codes or today == "closed":
        closed = _line("closed", "bad", f"{dow}요일은 쉬는 날이에요 · 방문일이 휴무예요")
    else:
        off = closed_weekdays(facts.attributes)
        if off:
            closed = _line("closed", "ok", f"{'·'.join(off)}요일 휴무 · 방문은 {dow}요일")
        elif week_known_all(facts.attributes):
            closed = _line("closed", "ok", "쉬는 요일이 없어요")
        elif today is not None:
            closed = _line("closed", "ok", f"{dow}요일은 열어요")
        else:
            closed = _line("closed", "unknown", "휴무 정보가 없어요")
        if facts.conditions:
            closed = _line("closed", "warn" if closed["result"] != "bad" else "bad",
                           closed["text"] + " · 공휴일 조건이 있어요(" + "; ".join(facts.conditions[:1]) + ")")
    # 운영시간
    if today == "closed" or "closed_day" in codes:
        return _line("hours", "unknown", "쉬는 날이라 운영하지 않아요"), closed
    if not isinstance(today, DayHours):
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


def default_engine(party_size: int | None) -> Callable[..., Any] | None:
    """이동 계산기(시간표 판정). 꺼져 있으면 None."""
    try:
        from ..mobility.wiring import leg_planner

        return leg_planner(party_size, {})
    except Exception:                                     # noqa: BLE001 — 계산기 장애가 확인 화면을 막지 않는다
        return None


def _item_id(row: dict[str, Any], positions: dict[str, int]) -> str:
    return f"{positions.get(row['source_id'], 0)}-{row['index']}"


#: 진행 이벤트로 내보내는 일정 칸 — 실시간 진행(`stream.Feed`)이 DB 에서 읽어 내는 `item` 이벤트와 **같은 칸**이다(같은 키가 나중 값으로 덮인다)
_ITEM_EVENT_FIELDS = ("id", "source_id", "index", "title", "kind", "day", "date", "starts_at", "ends_at", "locked", "status",
                      "can_lock", "place_state", "place", "candidates_hint", "booked", "parts")


def build(conn, *, tenant_id: str, intake_id: Any, revision: int, sources: list[dict[str, Any]],
          claims: list[dict[str, Any]], engine: Callable[..., Any] | None = None, use_engine: bool = True,
          previous: dict[str, Any] | None = None, now: datetime | None = None,
          on_event: Callable[[str, dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """한 판의 검사를 계산한다. `previous` = 앞 판의 검사 — 같은 구간(좌표 · 시각이 같음)은 그 값을 재사용한다(`sig`).

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
        engine = default_engine(party)
    budgeted = _Budgeted(engine, ENGINE_BUDGET_S) if engine is not None else None
    dates = sorted({r["date"] for r in rows if r["date"]})
    day_no = {d: i + 1 for i, d in enumerate(dates)}

    # 항목마다 운영시간 사실 → 등록 판정기에 한꺼번에 넣는다(같은 판정이 다음 일정과의 겹침도 본다)
    states = {i: place_state(r) for i, r in enumerate(rows)}
    facts: dict[int, HoursFacts] = {}
    parts: list[Part] = []
    seq_of: dict[int, int] = {}
    for i, r in enumerate(rows):
        start, end = _dt(r["date"], r["start"]), _dt(r["date"], r["end"])
        facts[i] = facts_for(conn, tenant_id, r["place"], r["kind"], start, end)
        note("progress", {"phase": "hours", "done": i + 1, "total": len(rows),
                          "current": {"id": _item_id(r, positions), "title": r["title"]}})
        if start is None:
            continue
        seq_of[i] = len(parts) + 1
        attributes = dict(facts[i].attributes)
        parts.append(Part(seq=len(parts) + 1, kind=r["kind"], title=r["title"] or "(제목 없음)", starts_at=start,
                          ends_at=end, place={"name": r["title"] or "", "attributes": attributes}))
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
                  or results.get("hours") == "warn")
        status = "review" if review else ("adjusted" if edited or any(ln["result"] == "filled" for ln in lines) else "keep")
        items.append({
            "id": _item_id(r, positions), "source_id": r["source_id"], "index": r["index"], "title": r["title"],
            "kind": r["kind"], "day": day_no.get(r["date"]), "date": r["date"], "starts_at": r["start"], "ends_at": r["end"],
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
            "rows": lines})
        # 이 일정의 검사 줄이 정해졌다 — 이동 계산(오래 걸린다) 전에 알린다. 겹침으로 확인 필요가 되는 일정은 아래 끝에서 status 가 바뀔 수 있어 최종 값이 같은 키로 덮는다
        note("item", {**{k: items[-1][k] for k in _ITEM_EVENT_FIELDS}, "place": public_place(items[-1]["place"])})
        for line in lines:
            note("check", {"item": items[-1]["id"], **line})

    old_moves = {m.get("sig"): m for m in (previous or {}).get("moves", []) if m.get("sig") and m.get("basis") == "timetable"}
    moves: list[dict[str, Any]] = []
    move_total = sum(1 for i in range(len(rows) - 1) if rows[i]["date"] and rows[i]["date"] == rows[i + 1]["date"])

    def add_move(move: dict[str, Any], ia: dict[str, Any], ib: dict[str, Any]) -> None:
        """구간 하나가 정해졌다 — 모으고 곧바로 알린다(이동 계산이 시간의 대부분이라 화면이 이 알림으로 진행을 안다)."""
        moves.append(move)
        note("move", {k: v for k, v in move.items() if k != "sig"})
        note("progress", {"phase": "moves", "done": len(moves), "total": move_total,
                          "current": {"id": f"{ia['id']}>{ib['id']}", "title": f"{ia['title']} → {ib['title']}"}})

    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        if not a["date"] or a["date"] != b["date"]:
            continue
        ia, ib = items[i], items[i + 1]
        a_end, b_start = _dt(a["date"], a["end"] or a["start"]), _dt(b["date"], b["start"])
        if a["place"] is None or b["place"] is None or a_end is None or b_start is None:
            add_move(_waiting_move(ia, ib), ia, ib)
            continue
        pa = {"key": ia["id"], "name": a["place"]["name"], "lat": float(a["place"]["latitude"]), "lon": float(a["place"]["longitude"])}
        pb = {"key": ib["id"], "name": b["place"]["name"], "lat": float(b["place"]["latitude"]), "lon": float(b["place"]["longitude"])}
        # ★재사용 키 — 이름과 정확한 좌표까지 넣는다(같은 자리에서 지점 이름만 바뀌어도 앞 판의 경로 문구가 남지 않게)
        sig = (f"{pa['name']}|{pa['lat']!r},{pa['lon']!r}>{pb['name']}|{pb['lat']!r},{pb['lon']!r}@{a_end.isoformat()}>{b_start.isoformat()}"
               f"#{ia['place_state']}{ib['place_state']}")
        if sig in old_moves:
            # 재사용하는 것은 경로 계산뿐이다 — 어느 일정 · 몇째 날인지는 지금 판의 것으로 채운다(앞에 날짜가 하나 늘어 일차만 바뀐 경우)
            add_move({**old_moves[sig], "from": ia["id"], "to": ib["id"], "day": ia["day"], "date": ia["date"]}, ia, ib)
            continue
        leg = leg_between(budgeted, pa, pb, a_end, b_start)
        provisional = [x["place"]["name"] for x in (ia, ib) if x["place_state"] == "picked_nearest"]
        add_move(_move(ia, ib, leg, provisional, sig), ia, ib)

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
            "items": items, "moves": moves,
            "needs": {"items": needs_items, "moves": needs_moves, "total": needs_items + needs_moves},
            "ready": bool(items) and not got.problems and needs_items + needs_moves == 0}


def public_place(place: dict[str, Any] | None) -> dict[str, Any] | None:
    """응답에 싣는 장소 — 서버 안의 장소 행 번호(`place_id`)는 뺀다."""
    return {k: v for k, v in place.items() if k != "place_id"} if place else None


def public(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """응답에 싣는 모양 — 저장본에서 **내부 칸**(이동 재사용 키 `sig` · 공용 장소 행 번호 `place_id`)을 뺀 복사본. 저장본은 그대로(자동 추천이 쓴다)."""
    if payload is None:
        return None
    items = []
    for it in payload.get("items", []):
        place = it.get("place")
        items.append({**it, "place": public_place(place)})
    return {**payload, "items": items, "moves": [{k: v for k, v in m.items() if k != "sig"} for m in payload.get("moves", [])]}


def _waiting_move(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    wait = "한쪽 장소가 정해지지 않았어요"
    return {"from": a["id"], "to": b["id"], "day": a["day"], "date": a["date"], "status": "waiting", "mode": None,
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
            "fare_krw": leg.fare_krw, "sig": sig, "rows": [route, mode, arrival]}


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
