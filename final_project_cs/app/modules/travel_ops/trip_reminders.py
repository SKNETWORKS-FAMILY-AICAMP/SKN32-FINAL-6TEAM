# -*- coding: utf-8 -*-
"""일정 안내 — 하루 시작(②)과 항목 출발(③). v11 §6-B · wiki `architecture/notifications.md`.

★①(변경 통지)과 성질이 다르다 — **Case 를 만들지 않고 LLM 을 부르지 않는다.** 이미 검증을
  통과해 저장된 최신 일정 버전을 읽어 「지금 무엇을 하면 되나」를 알린다. 변화가 없어도 간다.

★`[2026-09-18]` 전에는 문구가 시나리오 모드(`scenario_mode._day_start`·`_departure`)에만 있었고
  운영에서 이것을 띄우는 장치가 **없었다** — 시연 버튼을 눌러야만 나갔다. 계산은 이 파일
  한 곳에 두고, 시나리오 모드와 되잡기 작업(`scripts/run_sweepers.py --only trip_reminders`)이
  같은 것을 쓴다.

언제 나가나(값은 `config/guardrails.yaml` 의 `travel.reminders.*` · `travel.day_window.*` 한 곳):

    ★`[2026-09-24]` 사용자가 정한 흐름(D-020) — **하루 시작 → 다음 일정 안내 → 이동 → (반복)**

    ① 하루 시작    사용자가 정한 그날 시작 시각(없으면 08:00) — 단 첫 항목이 더 이르면
                   첫 항목 − day_start_lead 로 당긴다                         ~ 첫 항목 시작
                   ★새벽 3시에 모은 전날까지의 이슈(바뀐 일정 · 답을 기다리는 일정)를 함께 싣는다
    ② 다음 일정    각 일정(이동 제외)이 **시작할 때** 그다음 일정을 안내          ~ 그 일정 끝
    ③ 이동         ★**이동 항목이 시작하는 그 시각**(= 출발 시각)             ~ 이동 항목 끝
                   `[2026-09-24 사용자 지시]` 앞 판은 「이동 15분 전」이었다 — 이동이 몇 분인지와 상관없이
                   고정 15분을 앞에 붙인 것이라 틀렸다. 여유는 **일정이 이미 품는다**: 출발 = 다음 일정 시작
                   − 이동 시간 − 여유(생성기가 거꾸로 잡는다, `planner.add_moves`). 알림은 그 출발 시각에 간다.
       (전날 저녁   전날 eve_hour 시 — 2026-09-24 에 껐다. ①이 그 몫이다)

    ★답을 기다리는 일정(보류 제안, `pending.py`)으로는 「출발하세요」를 보내지 않는다 —
      대신 「답을 기다리는 중」 안내를 보낸다. 답이 없어 닫히면 다음 틱부터 원래대로 간다.

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
from .pending import PendingStore

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class ReminderRules:
    day_start_lead: timedelta = timedelta(minutes=60)
    eve_hour: int | None = None     # [2026-09-24] 끈다 — 하루 시작 알림이 그 몫이다(D-020)
    #: 사용자가 그날 시작 시각을 안 줬을 때의 하루 시작 알림 시각 — 팀 결정 08:00(D-020)
    day_start_at: time = time(8, 0)

    @classmethod
    def from_guardrails(cls) -> "ReminderRules":
        from app.core.settings import get_guardrails

        g = get_guardrails()
        eve = g.get("travel.reminders.eve_hour")
        hour, minute = (int(x) for x in str(g.get("travel.day_window.default_start")).split(":"))
        return cls(day_start_lead=timedelta(minutes=float(g.get("travel.reminders.day_start_lead_minutes"))),
                   eve_hour=None if eve is None else int(eve), day_start_at=time(hour, minute))


@dataclass(frozen=True)
class Reminder:
    kind: str                 # day_start | next_item | departure (day_eve 는 꺼져 있다)
    key: str                  # 바깥함 dedupe 뒷부분 — `{trip_id}:{key}`
    due_at: datetime
    until: datetime
    day: date
    move: Item | None = None
    current: Item | None = None     # next_item — 지금 일정
    following: Item | None = None   # next_item — 다음 일정


def _hm(value: datetime | None) -> str:
    return value.astimezone(KST).strftime("%H:%M") if value else "?"


def _by_day(items: list[Item]) -> dict[date, list[Item]]:
    days: dict[date, list[Item]] = {}
    for item in sorted(items, key=lambda i: (i.starts_at, i.seq)):
        days.setdefault(item.starts_at.astimezone(KST).date(), []).append(item)
    return days


def plan_reminders(items: list[Item], *, now: datetime, rules: ReminderRules,
                   day_starts: dict[date, datetime] | None = None) -> list[Reminder]:
    """지금 나가야 할 안내. ★순수 함수 — 읽기·쓰기·조회가 없다(시험과 시나리오가 같은 것을 쓴다).

    `day_starts` — 사용자가 정한 그날 시작 시각(여행 제약의 하루 창). 없으면 `rules.day_start_at`(08:00).
    """
    due: list[Reminder] = []
    for day, day_items in _by_day(items).items():
        first = day_items[0]
        start_at = (day_starts or {}).get(day) or datetime.combine(day, rules.day_start_at, tzinfo=KST)
        # ★첫 일정이 하루 시작보다 이르면 그 전으로 당긴다 — 이미 시작한 뒤에 「좋은 아침」을 보내지 않는다
        start_due = min(start_at, first.starts_at - rules.day_start_lead)
        if start_due <= now < first.starts_at:
            due.append(Reminder("day_start", f"day_start:{day.isoformat()}", start_due, first.starts_at, day))
        stops = [i for i in day_items if i.kind != "mobility"]
        for current, following in zip(stops, stops[1:]):
            # ★② 다음 일정 — 지금 일정이 **시작할 때**. 그날 마지막 일정은 다음이 없어 보내지 않는다
            until = current.ends_at or following.starts_at
            if current.starts_at <= now < until:
                due.append(Reminder("next_item", f"next_item:{current.item_id}", current.starts_at, until,
                                    day, current=current, following=following))
        if rules.eve_hour is not None:
            eve = datetime.combine(day - timedelta(days=1), time(rules.eve_hour), tzinfo=KST)
            if eve <= now < min(start_due, first.starts_at):
                due.append(Reminder("day_eve", f"day_eve:{day.isoformat()}", eve, start_due, day))
        for move in day_items:
            if move.kind != "mobility":
                continue
            # ★③ 이동 — **출발 시각 그 자체**(이동 항목 시작). 「N분 전」을 붙이지 않는다(D-020).
            #   틱이 늦게 돌아도 이동이 끝나기 전이면 보낸다 — 끝난 뒤의 「출발하세요」는 보내지 않는다.
            following = next((i for i in day_items if i.seq > move.seq and i.kind != "mobility"), None)
            until = move.ends_at or (following.starts_at if following else move.starts_at + timedelta(minutes=1))
            if move.starts_at <= now < until:
                due.append(Reminder("departure", f"departure:{move.item_id}", move.starts_at, until,
                                    day, move))
    return sorted(due, key=lambda r: (r.due_at, r.kind))


# ★★안내 문구는 **틀 + 원값**으로 만든다(`app/infrastructure/notify/phrase.py`).
#   시각·장소 이름·소요 분은 전부 `{...}` 자리의 **값**이라 번역을 타지 않고, 틀은 값이
#   없으므로 **언어마다 한 번만** 옮기면 된다(wiki `architecture/notifications.md` 「언어」).
#   ☆완성 문장을 담아 두면 값이 다른 알림끼리 섞인다 — 그래서 틀만 담는다.
def day_phrase(items: list[Item], day: date, *, eve: bool = False,
               changed: int = 0, waiting: list[str] | None = None) -> Phrase:
    """① 하루 시작. ★`[2026-09-24]` 새벽 3시까지 모인 이슈를 함께 싣는다(D-020) —
    `changed` 어제 이후 바뀐 일정 버전 수, `waiting` 답을 기다리는 일정 제목."""
    stops = [f"{_hm(i.starts_at)} {i.title}" for i in _by_day(items).get(day, []) if i.kind != "mobility"]
    head = ("내일 일정을 미리 안내해 드릴게요." if eve else "좋은 아침이에요! 오늘 일정을 안내해 드릴게요.")
    template = head + "\n{stops}"
    values: dict[str, Any] = {"stops": " → ".join(stops)}
    if changed:
        template += "\n\n어제 이후 바뀐 일정이 {changed}건 있어요 — 위 일정이 바뀐 뒤의 최신입니다."
        values["changed"] = changed
    if waiting:
        template += ("\n답을 기다리는 일정: {waiting} — 계획서 링크에서 골라 주세요. "
                     "답이 없으면 원래 일정대로 진행합니다.")
        values["waiting"] = ", ".join(waiting)
    template += "\n\n일정에 영향을 주는 변동이 확인되면 먼저 조정하고 알려드릴게요."
    return Phrase(template, values)


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


def next_item_phrase(current: Item, following: Item, move: Item | None) -> Phrase:
    """② 다음 일정 안내 — 지금 일정이 시작할 때. 이동이 끼면 몇 시에 나서는지도 미리 알린다."""
    template = "지금 일정: {now_title}.\n다음 일정: {next_at} {next_title}."
    values: dict[str, Any] = {"now_title": current.title, "next_at": _hm(following.starts_at),
                              "next_title": following.title}
    if move is not None:
        template += "\n이동은 {leave} 출발 예정이에요 — 출발할 때 다시 알려 드릴게요."
        values["leave"] = _hm(move.starts_at)
    return Phrase(template, values)


def waiting_phrase(target: Item) -> Phrase:
    """답을 기다리는 일정으로는 「출발하세요」 대신 이것을 보낸다(D-020)."""
    return Phrase("{title} — 답을 기다리고 있는 일정이에요. 계획서 링크에서 어떻게 할지 골라 주세요. "
                  "답이 없으면 원래 일정대로 진행합니다.", {"title": target.title})


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
                waiting = {row["item_id"] for row in
                           PendingStore(self.store.tenant_id).list(conn, trip_id, only_open=True)}
            for reminder in plan_reminders(items, now=now, rules=self.rules,
                                           day_starts=_day_starts(trip.get("constraints"))):
                payload = self._payload(trip_id, trip, items, reminder, now, result, waiting=waiting)
                if payload is None:
                    continue
                with self._connect() as conn, conn.transaction():
                    fresh = self.store.enqueue_message(conn, trip_id=trip_id, key=reminder.key, payload=payload)
                if fresh:
                    result.sent.append({"trip_id": str(trip_id), "key": reminder.key})
                else:
                    result.already += 1
        return result

    def _changed_since(self, trip_id, due_at: datetime) -> int:
        """하루 시작 전 24시간 동안 바뀐 일정 버전 수(생성 제외). ★새벽 3시 정리의 몫이다."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(_changed_since_sql(),
                        (self.store.tenant_id, trip_id, due_at - timedelta(days=1), due_at))
            return int(cur.fetchone()[0])

    def _payload(self, trip_id, trip, items, reminder: Reminder, now, result,
                 waiting: set | None = None) -> dict[str, Any] | None:
        waiting = waiting or set()
        base = {"type": "guidance", "kind": reminder.kind, "version": trip["version"]}
        if self.link is not None:
            base["plan_url"] = self.link(trip_id)
        if reminder.kind == "next_item":
            move = next((i for i in items if i.kind == "mobility"
                         and reminder.current.seq < i.seq < reminder.following.seq), None)
            fields = notice_fields(next_item_phrase(reminder.current, reminder.following, move))
            if reminder.following.item_id in waiting:
                fields = notice_fields(waiting_phrase(reminder.following))
                base["waiting"] = True
            return {**base, **fields, "item_id": str(reminder.current.item_id)}
        if reminder.kind != "departure":
            changed = self._changed_since(trip_id, reminder.due_at) if reminder.kind == "day_start" else 0
            titles = [i.title for i in items if i.item_id in waiting]
            return {**base, **notice_fields(day_phrase(items, reminder.day, eve=reminder.kind == "day_eve",
                                                       changed=changed, waiting=titles))}
        # ★답을 기다리는 일정으로 가는 이동이면 「출발하세요」를 보내지 않는다(D-020)
        target = next((i for i in items if i.seq > reminder.move.seq and i.kind != "mobility"), None)
        pending_target = reminder.move if reminder.move.item_id in waiting else (
            target if target is not None and target.item_id in waiting else None)
        if pending_target is not None:
            return {**base, **notice_fields(waiting_phrase(pending_target)), "waiting": True,
                    "item_id": str(reminder.move.item_id)}
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


def _changed_since_sql() -> str:
    return ("SELECT count(*) FROM itinerary_versions WHERE tenant_id=%s AND trip_id=%s "
            "AND reason <> 'created' AND created_at > %s AND created_at <= %s")


def _day_starts(constraints: dict[str, Any] | None) -> dict[date, datetime]:
    """사용자가 정한 날마다의 시작 시각(`constraints.density.days`). ★모르는 모양이면 비운다 — 기본값(08:00)이 쓰인다."""
    days = ((constraints or {}).get("density") or {}).get("days") or {}
    out: dict[date, datetime] = {}
    for key, window in days.items() if isinstance(days, dict) else []:
        try:
            out[date.fromisoformat(str(key))] = datetime.fromisoformat(str(window["starts_at"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out

