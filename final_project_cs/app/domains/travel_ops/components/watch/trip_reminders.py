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
    ③ 이동         ★**이동 항목이 시작하는 그 시각**(= 출발 시각)
                   현재 재검증 연결 시 미발행 안내는 다음 방문 시작 전까지 재확인한다.
                   재검증이 없는 기존 경로는 이동 항목 끝까지다.
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

from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.infrastructure.notify.phrase import Phrase

from app.domains.travel_ops.components.itinerary.itinerary import Item, StaleDeparture, TripStore
from app.domains.travel_ops.components.itinerary.itinerary_changes import option_hits, planned_option, route_of, route_targets
from app.domains.travel_ops.components.planning.pending import PendingStore
from app.domains.travel_ops.components.itinerary.itinerary_checks import STAY_KINDS

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
                   day_starts: dict[date, datetime] | None = None,
                   revalidate_departures: bool = False) -> list[Reminder]:
    """지금 나가야 할 안내. ★순수 함수 — 읽기·쓰기·조회가 없다(시험과 시나리오가 같은 것을 쓴다).

    `day_starts` — 사용자가 정한 그날 시작 시각(여행 제약의 하루 창). 없으면 `rules.day_start_at`(08:00).
    `revalidate_departures` — 현재 경로를 재검증할 때만 미발행 출발 후보를 다음 방문 전까지 유지한다.
    """
    due: list[Reminder] = []
    ordered = sorted(items, key=lambda i: i.seq)
    for day, day_items in _by_day(items).items():
        first = day_items[0]
        start_at = (day_starts or {}).get(day) or datetime.combine(day, rules.day_start_at, tzinfo=KST)
        # ★첫 일정이 하루 시작보다 이르면 그 전으로 당긴다 — 이미 시작한 뒤에 「좋은 아침」을 보내지 않는다
        start_due = min(start_at, first.starts_at - rules.day_start_lead)
        if start_due <= now < first.starts_at:
            due.append(Reminder("day_start", f"day_start:{day.isoformat()}", start_due, first.starts_at, day))
        # `[2026-10-13]` 숙소는 「다음 일정」 짝에서 뺀다 — 끝(체크아웃)이 며칠 뒤라 그 사이 내내 「다음 일정」 안내 대상이 된다
        stops = [i for i in day_items if i.kind != "mobility" and i.kind not in STAY_KINDS]
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
            # 현재 재검증이 있으면 저장된 종료 시각 뒤에도 다음 방문 전까지 후보로 둔다.
            # 후보 선택은 발행 허가가 아니다. tick의 중복 제외와 현재 도착 가능성 검사를 거친다.
            candidates = ordered if revalidate_departures else day_items
            following = next((i for i in candidates if i.seq > move.seq and i.kind != "mobility"), None)
            if revalidate_departures:
                if following is None:
                    continue
                until = following.starts_at
            else:
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
        values |= {"how": how["label"], "eta_min": how.get("eta_min")}
        if how.get("checked_at") is not None:
            template += f"\n가는 방법: {{how}}{eta} (경로 확인 {{checked}})"
            values["checked"] = _hm(how["checked_at"])
        else:
            # ☆`[2026-09-29 이동 계산기 문제목록 #37]` 확인하지 않은 경로에 「경로 확인 ○○:○○」을 붙이지 않는다
            template += f"\n가는 방법: {{how}}{eta}"
    return Phrase(template, values)


def _with_boarding_steps(phrase, observation, departure, arrival):
    """시각·역명은 원값으로 보존하고 구간별 근거만 문구틀로 구분한다."""
    steps = observation.get('boarding_steps', [])
    if not isinstance(steps, list):
        raise ValueError('승차 안내 목록 형식 오류')
    template, values = phrase.template, dict(phrase.values)
    previous_idx, previous_arrival = -1, departure
    def clock(at):
        local = at.astimezone(KST)
        return (local.strftime('%Y-%m-%d %H:%M')
                if local.date() != departure.astimezone(KST).date() else _hm(at))
    if steps:
        template += '\n구간별 승차 안내 (하차·환승 시각은 예상):'
    for position, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError('승차 안내 행 형식 오류')
        idx, mode = step.get('idx'), step.get('mode')
        if (isinstance(idx, bool) or not isinstance(idx, int) or idx <= previous_idx
                or mode not in ('bus', 'subway') or step.get('ride_basis') != 'model'):
            raise ValueError('승차 안내 구간 또는 근거 오류')
        for key in ('service', 'from', 'to'):
            if not isinstance(step.get(key), str) or not step[key].strip():
                raise ValueError('승차 안내 노선·장소 누락')
        board = datetime.fromisoformat(str(step['board_at']))
        alight = datetime.fromisoformat(str(step['alight_at']))
        if (board.utcoffset() is None or alight.utcoffset() is None
                or not previous_arrival <= board <= alight <= arrival):
            raise ValueError('승차 안내 시각 역전 또는 범위 오류')
        basis = step.get('boarding_basis')
        if basis == 'realtime_arrival_prediction':
            if (position != 0 or idx != 0 or observation.get('status') != 'realtime'
                    or mode != observation.get('realtime_mode')):
                raise ValueError('현재 승차 관측 구간 오표시')
            certainty = '현재 도착 예측 반영 · 하차 시각 예상'
        elif basis == 'timetable_model':
            if position == 0 and observation.get('status') == 'realtime':
                raise ValueError('현재 승차 관측 근거 누락')
            certainty = '시간표·이동 모델 예상'
        else:
            raise ValueError('승차 안내 근거 누락')
        prefix = f'boarding_{position}_'
        kind = '승차' if position == 0 else '환승'
        template += ('\n{' + prefix + 'service}: {' + prefix + 'board} {' + prefix + 'from} '
                     + kind + ' → {' + prefix + 'alight} {' + prefix + 'to} 하차 (' + certainty + ')')
        values.update({prefix+'service': step['service'], prefix+'board': clock(board),
                       prefix+'alight': clock(alight), prefix+'from': step['from'], prefix+'to': step['to']})
        if 'train_number' in step or 'towards' in step:
            if (basis != 'realtime_arrival_prediction' or mode != 'subway'
                    or any(not isinstance(step.get(k), str) or not step[k].strip()
                           for k in ('train_number', 'towards'))):
                raise ValueError('선택 열차 정보 오류')
            template += ' · {' + prefix + 'towards} 방면 · 열차 {' + prefix + 'train}'
            values.update({prefix+'towards':step['towards'], prefix+'train':step['train_number']})
        previous_idx, previous_arrival = idx, alight
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
    stale: list[dict[str, Any]] = field(default_factory=list)
    held: list[dict[str, Any]] = field(default_factory=list)
    fatal: list[dict[str, Any]] = field(default_factory=list)
    no_route: int = 0
    #: ☆`[2026-09-29 이동 계산기 문제목록 #37]` 계획 경로에 사건 소스가 확인하지 못하는 노선(지하철·버스 등)이 있어
    #:  「경로 확인」 없이 보낸 출발 안내. 그 노선의 사고 출처(#36)가 생기면 0 이 되어야 한다.
    unchecked: list[dict[str, Any]] = field(default_factory=list)


class DepartureBasisUnavailable(RuntimeError):
    """저장 직전 이동 입력 판을 확인하지 못함. 낡은 안내로 대신하지 않는다."""


class TripReminders:
    """되잡기 작업 — 한 번 돌 때마다 지금 나가야 할 안내를 바깥함에 넣는다."""

    def __init__(self, *, store: TripStore, connection_factory: Callable[[], Any],
                 clock: Callable[[], datetime], route_events: Any = None,
                 rules: ReminderRules | None = None, routes: dict[str, Any] | None = None,
                 link: Callable[[Any], str] | None = None,
                 departure_observer: Callable[..., dict[str, Any]] | None = None) -> None:
        self.store, self._connect, self.clock = store, connection_factory, clock
        self.route_events, self.routes, self.link = route_events, routes or {}, link
        self.departure_observer = departure_observer
        self.rules = rules or ReminderRules.from_guardrails()

    def tick(self) -> ReminderTickResult:
        result = ReminderTickResult()
        now = self.clock()
        with self._connect() as conn:
            trip_ids = self.store.active_trip_ids(conn, now)       # ★`[2026-10-06]` 재난 정지 중인 여행은 안내도 멈춘다 — 시계는 이 반복의 것
        for trip_id in trip_ids:
            result.trips += 1
            with self._connect() as conn:
                trip, items = self.store.latest(conn, trip_id)
                waiting = {row["item_id"] for row in
                           PendingStore(self.store.tenant_id).list(conn, trip_id, only_open=True)}
            departure_inputs = deepcopy({"party_size": trip.get("party_size"),
                                         "constraints": trip.get("constraints")})
            for reminder in plan_reminders(items, now=now, rules=self.rules,
                                           day_starts=_day_starts(trip.get("constraints")),
                                           revalidate_departures=self.departure_observer is not None):
                # 이미 발행한 안내의 외부 조회를 되풀이하지 않는다. 최종 UNIQUE는 그대로 둔다.
                with self._connect() as conn:
                    already = self.store.message_exists(conn, trip_id=trip_id, key=reminder.key)
                if already:
                    result.already += 1
                    continue
                payload = self._payload(trip_id, trip, items, reminder, now, result, waiting=waiting)
                if payload is None:
                    continue
                check_basis = reminder.kind == 'departure' and not payload.get('waiting')
                observation = payload.get('departure_observation')
                observed_basis = deepcopy(observation.get('basis')) if isinstance(observation, dict) else None
                try:
                    with self._connect() as conn, conn.transaction():
                        if check_basis:
                            self._check_departure_basis(observed_basis)
                        check_inputs = ({"expected_departure_inputs": departure_inputs}
                                        if reminder.kind == "departure" else {})
                        fresh = self.store.enqueue_message(conn, trip_id=trip_id, key=reminder.key,
                                                           payload=payload, **check_inputs)
                        if fresh and check_basis:
                            # INSERT 뒤 바뀐 급행 표도 COMMIT 전에 발견하면 이 거래 전체를 되돌린다.
                            self._check_departure_basis(observed_basis)
                except StaleDeparture as exc:
                    result.stale.append({"trip_id": str(trip_id), "key": reminder.key, "reason": str(exc)})
                    continue
                except DepartureBasisUnavailable:
                    result.fatal.append({'trip_id': str(trip_id), 'key': reminder.key,
                                         'failed_categories': ['departure_basis'],
                                         'reason': 'departure_basis_unavailable'})
                    continue
                if fresh:
                    result.sent.append({"trip_id": str(trip_id), "key": reminder.key})
                else:
                    result.already += 1
        return result

    def _check_departure_basis(self, basis):
        validator = getattr(self.departure_observer, 'validate_basis', None)
        if validator is None:
            return  # 관측 기능이 꺼진 경로와 옛 단순 시험 콜백의 기존 계약.
        try:
            matched = validator(deepcopy(basis))
        except Exception as exc:  # noqa: BLE001 — 치명 상태를 보고하고 거래를 되돌린다
            raise DepartureBasisUnavailable(type(exc).__name__) from None
        if matched is True:
            return
        if matched is False:
            raise StaleDeparture('departure express basis changed')
        raise DepartureBasisUnavailable('invalid_basis_validation_result')

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
        observations = []
        def observed(*args, **kwargs):
            value = self.departure_observer(*args, **kwargs)
            observations.append(value)
            return value
        status, phrase = build_departure(reminder.move, items, route_events=self.route_events,
                                         routes=self.routes, now=now,
                                         trip=trip,
                                         departure_observer=observed if self.departure_observer else None)
        entry = {"trip_id": str(trip_id), "item": reminder.move.title}
        if observations:
            entry['departure_observation'] = observations[-1]
        if status == "fatal":
            result.fatal.append({**entry, "failed_categories": ["departure_observer" if observations else "route_events"]})
            return None
        if status == "held":
            result.held.append(entry)
            return None
        if status == "no_route":
            result.no_route += 1
        if status == "unchecked":
            result.unchecked.append(entry)
        return {**base, **notice_fields(phrase), "item_id": str(reminder.move.item_id),
                **({'departure_observation': observations[-1]} if observations else {})}


def build_departure(move: Item, items: list[Item], *, route_events: Any, routes: dict[str, Any] | None,
                    now: datetime, departure_observer=None, trip=None) -> tuple[str, Phrase | None]:
    """출발 안내 문구(틀+원값)와 상태 — `ok` · `no_route`(경로 정의·소스 없음, 어디로·언제만) ·
    `held`(계획한 수단에 사건 — 감시가 고칠 일) · `fatal`(경로 사건을 못 읽음, 결정 15) ·
    `unchecked`(계획한 수단 중 사건 소스가 **확인하지 못하는** 대상이 있다 — 「경로 확인」 없이 보낸다).

    ☆`[2026-09-29 이동 계산기 문제목록 #37]` 앞 판은 사건 소스가 지하철·버스를 `unsupported` 로 돌려주는데도
      `affecting()` 의 빈 결과를 「사건 없음」으로 읽어 「경로 확인 ○○:○○」을 붙였다 — 지하철이 멈춰도 확인한 것처럼 안내했다."""
    following = next((i for i in sorted(items, key=lambda i: i.seq)
                      if i.seq > move.seq and i.kind != 'mobility'), None)
    route = route_of(move, routes)
    if not route or route_events is None:
        if departure_observer is None:
            # 관측 기능이 꺼진 기존 안내 계약.
            return "no_route", departure_phrase(move, following, None)
        if not route:
            # 현재 재검증이 필요한 경로에서 저장된 출발 문구로 우회하지 않는다.
            return "held", None
    _, planned = planned_option(move, route)
    # ☆`[2026-09-30 이동 계산기 실제 흐름 확인 C2]` 확인할 노선·도로(`uses`)가 하나도 없는 이동(어림값·도보)은 사건 소스가 볼 것이
    #   없다 — 「확인 못 한 대상이 없다」를 「확인했다」로 읽어 「경로 확인 HH:MM」을 붙이면 어림값 이동이 확인된 경로처럼 보인다
    no_targets = not planned.get("uses")
    if departure_observer is not None and no_targets:
        # 확인할 사건 대상이 없다는 사실과 현재 이동시간 재검증은 별개다.
        # 불필요한 사건 조회로 도보 재계산을 막거나 예전 안내를 보내지 않는다.
        events, blind = {}, []
    else:
        if route_events is None:
            return "fatal", None
        events = route_events.affecting(route_targets(route))
        if events is None:
            # ★결정 15 — 경로를 못 읽었는데 「그럴듯한 경로 문장」을 보내지 않는다.
            return "fatal", None
        if option_hits(planned, events):
            return "held", None
        unsupported_of = getattr(route_events, "unsupported", None)
        blind = unsupported_of(list(planned.get("uses", []))) if callable(unsupported_of) else []
    how = {"label": planned.get("label") or planned.get("id"), "eta_min": planned.get("eta_min"),
           "checked_at": None if (blind or no_targets) else now}
    if departure_observer is not None:
        current = {'trip': trip} if trip is not None else {}
        observation = departure_observer(move, items, planned=planned, now=now, events=events, **current)
        if not isinstance(observation, dict) or observation.get('status') == 'fatal':
            return 'fatal', None
        if observation.get('status') == 'needs_replan':
            return 'held', None
        if observation.get('status') not in ('realtime', 'model_revalidated'):
            return 'fatal', None
        try:
            depart = datetime.fromisoformat(str(observation['departure_at']))
            arrival = datetime.fromisoformat(str(observation['arrival_at']))
            eta = observation['eta_min']
            if (depart.utcoffset() is None or arrival.utcoffset() is None or depart < now
                    or arrival < depart or isinstance(eta, bool) or not isinstance(eta, int)
                    or eta < 0 or following is None or arrival > following.starts_at):
                return 'fatal', None
        except (ValueError, KeyError, TypeError):
            return 'fatal', None
        move = replace(move, starts_at=depart, ends_at=arrival)
        how['eta_min'] = eta
        if 'route_label' in observation:
            label = observation['route_label']
            if not isinstance(label, str) or not label.strip():
                return 'fatal', None
            how['label'] = label
        realtime_label = (' · 현재 지하철 대기 반영' if observation.get('realtime_mode') == 'subway'
                          else ' · 현재 버스 대기 반영')
        how['label'] += (realtime_label if observation['status'] == 'realtime'
                         else ' · 현재 시각 기준 예상')
    phrase = departure_phrase(move, following, how)
    if departure_observer is not None:
        try:
            phrase = _with_boarding_steps(phrase, observation, depart, arrival)
        except (ValueError, TypeError, KeyError, OverflowError):
            return 'fatal', None
    return ("unchecked" if blind else "ok"), phrase


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

