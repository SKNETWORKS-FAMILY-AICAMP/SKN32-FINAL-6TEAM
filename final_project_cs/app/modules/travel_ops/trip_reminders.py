# -*- coding: utf-8 -*-
"""일정 안내 — 하루 시작(②)과 항목 출발(③). v11 §6-B · wiki `architecture/notifications.md`.

★①(변경 통지)과 성질이 다르다 — **Case 를 만들지 않고 LLM 을 부르지 않는다.** 이미 검증을
  통과해 저장된 최신 일정 버전을 읽어 「지금 무엇을 하면 되나」를 알린다. 변화가 없어도 간다.

★`[2026-09-18]` 전에는 문구가 시나리오 모드(`scenario_mode._day_start`·`_departure`)에만 있었고
  운영에서 이것을 띄우는 장치가 **없었다** — 시연 버튼을 눌러야만 나갔다. 계산은 이 파일
  한 곳에 두고, 시나리오 모드와 되잡기 작업(`scripts/run_sweepers.py --only trip_reminders`)이
  같은 것을 쓴다.

언제 나가나(값은 `config/guardrails.yaml` 의 `travel.reminders.*` 한 곳):

    ② 하루 시작   그날 첫 항목 시작 − day_start_lead_minutes   ~ 첫 항목 시작
       전날 저녁   전날 eve_hour 시                             ~ 하루 시작 안내 시각
    ③ 출발        이동 항목 시작 − departure_lead_minutes       ~ 이동 항목 시작

★③의 「출발 시각」은 **이동 항목의 시작 시각**이다 — 일정이 이동을 항목으로 들고 온다
  (`kind="mobility"`, `route_def`). 이동 시간은 그 항목이 이미 품고 있다.
  `[미구현]` 이동 항목 없이 장소만 이어진 구간은 이동 시간을 계산할 경로 조회
  (`read.route`)가 없어 출발 안내를 **만들지 않는다**(v11 §6-B 역산의 선행 조건).

★③의 「어떻게 가나」는 **보낼 때 조회한다**(경로 사건). 조회가 안 되면 보내지 않고
  `fatal` 로 센다(결정 15 — 「모름」으로 보내지 않는다). 계획한 수단에 사건이 걸려 있으면
  낡은 경로를 알리지 않고 `held` 로 센다 — 그건 감시 루프가 고칠 일이고, 고치면 새 이동
  항목(새 `item_id`)의 안내가 나간다.

★두 번 보내지 않는다 — 안내 키가 `outbox UNIQUE(tenant_id, topic, dedupe_key)` 에 걸린다
  (DoD-26). 출발 안내 키는 **항목 id** 라서 감시가 이동을 바꾸면 바뀐 이동은 새로 안내된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.infrastructure.notify.phrase import Phrase

from .itinerary import Item, TripStore
from .itinerary_changes import planned_option, route_of, route_targets

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class ReminderRules:
    day_start_lead: timedelta = timedelta(minutes=60)
    departure_lead: timedelta = timedelta(minutes=15)
    eve_hour: int | None = 20

    @classmethod
    def from_guardrails(cls) -> "ReminderRules":
        from app.core.settings import get_guardrails

        g = get_guardrails()
        eve = g.get("travel.reminders.eve_hour")
        return cls(day_start_lead=timedelta(minutes=float(g.get("travel.reminders.day_start_lead_minutes"))),
                   departure_lead=timedelta(minutes=float(g.get("travel.reminders.departure_lead_minutes"))),
                   eve_hour=None if eve is None else int(eve))


@dataclass(frozen=True)
class Reminder:
    kind: str                 # day_eve | day_start | departure
    key: str                  # 바깥함 dedupe 뒷부분 — `{trip_id}:{key}`
    due_at: datetime
    until: datetime
    day: date
    move: Item | None = None


def _hm(value: datetime | None) -> str:
    return value.astimezone(KST).strftime("%H:%M") if value else "?"


def _by_day(items: list[Item]) -> dict[date, list[Item]]:
    days: dict[date, list[Item]] = {}
    for item in sorted(items, key=lambda i: (i.starts_at, i.seq)):
        days.setdefault(item.starts_at.astimezone(KST).date(), []).append(item)
    return days


def plan_reminders(items: list[Item], *, now: datetime, rules: ReminderRules) -> list[Reminder]:
    """지금 나가야 할 안내. ★순수 함수 — 읽기·쓰기·조회가 없다(시험과 시나리오가 같은 것을 쓴다)."""
    due: list[Reminder] = []
    for day, day_items in _by_day(items).items():
        first = day_items[0]
        start_due = first.starts_at - rules.day_start_lead
        if start_due <= now < first.starts_at:
            due.append(Reminder("day_start", f"day_start:{day.isoformat()}", start_due, first.starts_at, day))
        if rules.eve_hour is not None:
            eve = datetime.combine(day - timedelta(days=1), time(rules.eve_hour), tzinfo=KST)
            if eve <= now < min(start_due, first.starts_at):
                due.append(Reminder("day_eve", f"day_eve:{day.isoformat()}", eve, start_due, day))
        for move in day_items:
            if move.kind != "mobility":
                continue
            leave_due = move.starts_at - rules.departure_lead
            if leave_due <= now < move.starts_at:
                due.append(Reminder("departure", f"departure:{move.item_id}", leave_due, move.starts_at,
                                    day, move))
    return due


# ★★안내 문구는 **틀 + 원값**으로 만든다(`app/infrastructure/notify/phrase.py`).
#   시각·장소 이름·소요 분은 전부 `{...}` 자리의 **값**이라 번역을 타지 않고, 틀은 값이
#   없으므로 **언어마다 한 번만** 옮기면 된다(wiki `architecture/notifications.md` 「언어」).
#   ☆완성 문장을 담아 두면 값이 다른 알림끼리 섞인다 — 그래서 틀만 담는다.
def day_phrase(items: list[Item], day: date, *, eve: bool = False) -> Phrase:
    stops = [f"{_hm(i.starts_at)} {i.title}" for i in _by_day(items).get(day, []) if i.kind != "mobility"]
    head = ("내일 일정을 미리 안내해 드릴게요." if eve else "좋은 아침이에요! 오늘 일정을 안내해 드릴게요.")
    return Phrase(head + "\n{stops}\n\n일정에 영향을 주는 변동이 확인되면 먼저 조정하고 알려드릴게요.",
                  {"stops": " → ".join(stops)})


def departure_phrase(move: Item, following: Item | None, how: dict[str, Any] | None) -> Phrase:
    template = "{leave} 출발 — {title} ({leave}–{ends})."
    values: dict[str, Any] = {"leave": _hm(move.starts_at), "title": move.title,
                              "ends": _hm(move.ends_at)}
    if following:
        template += "\n다음 일정: {next_at} {next_title}."
        values |= {"next_at": _hm(following.starts_at), "next_title": following.title}
    if how:
        eta = " · 약 {eta_min}분" if how.get("eta_min") is not None else ""
        template += f"\n가는 방법: {{how}}{eta} (경로 확인 {{checked}})"
        values |= {"how": how["label"], "eta_min": how.get("eta_min"), "checked": _hm(how["checked_at"])}
    return Phrase(template, values)


def day_text(items: list[Item], day: date, *, eve: bool = False) -> str:
    return day_phrase(items, day, eve=eve).render()


def departure_text(move: Item, following: Item | None, how: dict[str, Any] | None) -> str:
    return departure_phrase(move, following, how).render()


def notice_fields(phrase: Phrase) -> dict[str, Any]:
    """통지 payload 에 실을 칸 — 완성 문장(`text`)과 **틀·원값**을 같이 싣는다.

    ★`text` 는 화면·시험이 읽는 한국어 원문이고, `template`·`values` 는 발송이 언어마다
      한 번만 옮기기 위한 것이다. 둘은 같은 `Phrase` 에서 나오므로 어긋날 수 없다.
    """
    return {"text": phrase.render(), "template": phrase.template, "values": dict(phrase.values)}


@dataclass
class ReminderTickResult:
    trips: int = 0
    sent: list[dict[str, Any]] = field(default_factory=list)
    already: int = 0
    held: list[dict[str, Any]] = field(default_factory=list)
    fatal: list[dict[str, Any]] = field(default_factory=list)
    no_route: int = 0


class TripReminders:
    """되잡기 작업 — 한 번 돌 때마다 지금 나가야 할 안내를 바깥함에 넣는다."""

    def __init__(self, *, store: TripStore, connection_factory: Callable[[], Any],
                 clock: Callable[[], datetime], route_events: Any = None,
                 rules: ReminderRules | None = None, routes: dict[str, Any] | None = None,
                 link: Callable[[Any], str] | None = None) -> None:
        self.store, self._connect, self.clock = store, connection_factory, clock
        self.route_events, self.routes, self.link = route_events, routes or {}, link
        self.rules = rules or ReminderRules.from_guardrails()

    def tick(self) -> ReminderTickResult:
        result = ReminderTickResult()
        now = self.clock()
        with self._connect() as conn:
            trip_ids = self.store.active_trip_ids(conn)
        for trip_id in trip_ids:
            result.trips += 1
            with self._connect() as conn:
                trip, items = self.store.latest(conn, trip_id)
            for reminder in plan_reminders(items, now=now, rules=self.rules):
                payload = self._payload(trip_id, trip, items, reminder, now, result)
                if payload is None:
                    continue
                with self._connect() as conn, conn.transaction():
                    fresh = self.store.enqueue_message(conn, trip_id=trip_id, key=reminder.key, payload=payload)
                if fresh:
                    result.sent.append({"trip_id": str(trip_id), "key": reminder.key})
                else:
                    result.already += 1
        return result

    def _payload(self, trip_id, trip, items, reminder: Reminder, now, result) -> dict[str, Any] | None:
        base = {"kind": reminder.kind, "version": trip["version"]}
        if self.link is not None:
            base["plan_url"] = self.link(trip_id)
        if reminder.kind != "departure":
            return {**base,
                    **notice_fields(day_phrase(items, reminder.day, eve=reminder.kind == "day_eve"))}
        status, phrase = build_departure(reminder.move, items, route_events=self.route_events,
                                         routes=self.routes, now=now)
        entry = {"trip_id": str(trip_id), "item": reminder.move.title}
        if status == "fatal":
            result.fatal.append({**entry, "failed_categories": ["route_events"]})
            return None
        if status == "held":
            result.held.append(entry)
            return None
        if status == "no_route":
            result.no_route += 1
        return {**base, **notice_fields(phrase), "item_id": str(reminder.move.item_id)}


def build_departure(move: Item, items: list[Item], *, route_events: Any, routes: dict[str, Any] | None,
                    now: datetime) -> tuple[str, Phrase | None]:
    """출발 안내 문구(틀+원값)와 상태 — `ok` · `no_route`(경로 정의·소스 없음, 어디로·언제만) ·
    `held`(계획한 수단에 사건 — 감시가 고칠 일) · `fatal`(경로 사건을 못 읽음, 결정 15)."""
    following = next((i for i in sorted(items, key=lambda i: i.seq) if i.seq > move.seq), None)
    route = route_of(move, routes)
    if not route or route_events is None:
        # ★경로 정의나 경로 사건 소스가 없다 — 어디로·언제만 보낸다. 「모름」 문장은 안 넣는다.
        return "no_route", departure_phrase(move, following, None)
    _, planned = planned_option(move, route)
    events = route_events.affecting(route_targets(route))
    if events is None:
        # ★결정 15 — 경로를 못 읽었는데 「그럴듯한 경로 문장」을 보내지 않는다.
        return "fatal", None
    if any(target in events for target in planned.get("uses", [])):
        return "held", None
    how = {"label": planned.get("label") or planned.get("id"), "eta_min": planned.get("eta_min"),
           "checked_at": now}
    return "ok", departure_phrase(move, following, how)


__all__ = ["Reminder", "ReminderRules", "ReminderTickResult", "TripReminders", "build_departure",
           "day_phrase", "day_text", "departure_phrase", "departure_text", "notice_fields",
           "plan_reminders"]
