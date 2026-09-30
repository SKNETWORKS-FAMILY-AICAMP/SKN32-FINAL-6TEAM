# -*- coding: utf-8 -*-
"""깨진 일정 항목의 대안 — 후보 만들기 · 고르기 · 알림 문구 (v11 §6-C).

★★**고르는 규칙(§6-C-2)** — 탈락 먼저, 그다음 사전식 비교. 벌점으로 섞지 않는다.

    탈락   재검증 불통과 · 그 시각 영업 안 함 · 가격·소요 모름 · 다음 일정 늦음 · 조건 위반
    비교   ① 바뀌는 항목 수  ② 추가 비용  ③ 원래 시각과의 차이  ④ 되돌리기 쉬운가
    동률   정규화한 후보 식별자 — 같은 입력에 같은 결과가 나오게 한다

★**하나를 고른다**(결정 15). 나머지 통과 후보는 **재요청용으로 둘까지** 들고 있는다
  (§6-C-4 6단계). 시나리오의 「대안 둘」은 여기서 나온다 — 나열해서 고객에게 고르게
  하지 않고, 최선을 적용한 뒤 「다른 안」으로 보인다.

★**첫 통과 후보에서 멈추지 않는다.** 첫 번째는 되는 안이지 최선이 아니다.

★우리가 고른 값(측정 아님) — 코드 상수로 모아 둔다:
    WALK_M_PER_MIN        80   도보 분당 거리
    ORDER_MARGIN_MIN      20   라스트오더 전에 확보해야 할 주문 여유 — ★**탈락** 조건
    SEATING_BUFFER_MIN    10   도착해 자리 잡는 데 드는 시간

★`[2026-09-28]` 라스트오더는 **두 값**이다(사용자 결정 — 경고는 60분, 탈락은 20분).
    ORDER_MARGIN_MIN      20   라스트오더를 **알 때** — 도착 + 20분이 라스트오더를 넘으면 탈락
                               (브레이크 앞 라스트오더에만 걸던 것을 영업 종료 앞 라스트오더에도 건다)
    LAST_ORDER_WARN_MIN   60   라스트오더를 **모를 때** — 식사가 끝나는 시각이 영업 종료(또는 브레이크 시작)
                               60분 안이면 **경고만** 한다. 모르는 값으로 후보를 버리지 않는다.
                               요식 원장의 같은 규칙과 같은 값이다(`201_dining_core_link.sql` `needs_last_order_check`).
                               ★실측(2026-09-28 재계산, `scripts/dining/parse_hours.py` 현재판): 관광공사 음식점 원문
                               989곳 중 라스트오더를 적은 481곳 — 종료와 라스트오더 간격 중앙값 50분, 60분 이내
                               413/481 = 85.9%. 요식 문서의 「77곳 · 85.7%」는 09-21 옛 파서 값이라 지금은 재현되지 않는다.

★`[2026-09-28]` **식당은 가격으로 탈락시키지도 줄 세우지도 않는다**(사용자 결정 — 식당 가격은 정확히 매기기
  어렵다). 전에는 가격을 모르면 「추가 비용을 계산할 수 없다」로 **탈락**이라 가격 칸이 빈 식당이 전부 빠졌다.
  식당끼리는 도보 거리(③ 원래 시각과의 차이)로 가른다.

★`[2026-09-28]` **요식 원장은 후보를 내고, 고르는 것은 여기다**(사용자 결정). 원장(`dining/ledger.py`)이
  축마다 하나씩(덜 밀리는 곳 · 비슷한 곳 · 가까운 곳) 준 곳을 후보로 삼아 위 규칙으로 **하나**를 고르고,
  나머지는 「다른 안」이 된다. 원장이 말할 수 없으면(표 없음 · 짝 없음 · 후보 없음) 예전처럼 장소 목록에서 찾는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
from typing import Any, Callable

WALK_M_PER_MIN = 80
ORDER_MARGIN_MIN = 20
LAST_ORDER_WARN_MIN = 60
#: 시연용 순위가 없는 후보(= 실제 장소 전부)의 값 — 대본 장소의 순위(1, 2 …)보다 뒤다
SCENARIO_PRIORITY_NONE = 1_000
SEATING_BUFFER_MIN = 10


@dataclass
class Candidate:
    key: str                           # 정규화한 후보 식별자 — 동률 처리용
    place: dict[str, Any] | None
    changed_items: int
    extra_cost_krw: int | None
    shift_minutes: int
    reversible_internally: bool = True
    rejected: list[str] = field(default_factory=list)
    recheck: dict[str, Any] | None = None
    option: dict[str, Any] | None = None     # 경로 후보일 때
    walk_min: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    #: ★탈락은 아니지만 고객이 확인해야 할 것(라스트오더를 모르는데 마감이 가깝다 등). 통지에 싣는다
    warnings: list[str] = field(default_factory=list)
    #: 요식 원장이 낸 후보면 그 축(`axis` · `axis_label`). 원장 밖 후보는 None
    axis: dict[str, Any] | None = None
    #: 영업 판정을 어디서 가져왔나 — `dining_ledger` · `core_place`. 틀렸을 때 어디를 고칠지 알게 남긴다
    judged_by: str | None = None
    #: ★`[2026-09-29]` 활동 후보만 채운다 — 원래 장소와 비슷한 정도(클수록 비슷)와 직선거리(m).
    #:  식당·경로 후보는 둘 다 0 이라 순서가 예전 그대로다(`rank` 맨 뒤, `key` 바로 앞)
    similarity: int = 0
    distance_m: float = 0.0

    def rank(self) -> tuple:
        # ★`[2026-09-28]` 도보 분(③ 원래 시각과의 차이)과 경고 유무를 더했다. 활동·경로 후보는 `walk_min` 이
        #   None · 경고 없음이라 **예전 순서 그대로**다. 식당은 가격을 안 쓰므로 전에는 사실상 후보 id 순이었다
        # ★`[2026-09-28 사용자 지시]` 맨 앞은 **시연용 순위**(`scenario_priority`)다 — 시나리오 모드는 대본대로 도는
        #   데모 모드라, 실서비스 규칙이 바뀌어도(식당 가격을 순위에서 뺐다) 대본이 고른 곳이 골라져야 한다. 전에는
        #   가격으로 「성수 브런치 식당」을 골랐는데 가격을 빼자 이름순으로 「국수 식당」이 골라져 시나리오 시험 4건이
        #   깨졌다. 이 값은 대본 장소에만 있고 **탈락하지 않은 후보 사이에서만** 쓰인다 — 실제 장소는 모두 같은 값이다
        priority = ((self.place or {}).get("attributes") or {}).get("scenario_priority")
        # ☆`[2026-09-29 이동 계산기 문제목록 #22]` 경로 후보의 요금 모름은 0원(가장 쌈)이 아니라 **아는 후보 뒤** —
        #   경로 후보(option)에만 건다. 식당·활동은 종전 순서 그대로다
        fare_unknown = 1 if (self.option is not None and self.extra_cost_krw is None) else 0
        # ★`[2026-09-29]` 활동 후보는 전에 추가 비용이 같으면 **장소 id 순**이었다(거리도 종류도 안 봤다).
        #   이제 비용·변동 다음에 「비슷한 곳(관광공사 분류·구) → 가까운 곳」이다. 비슷한 정도가 거리보다 앞이라
        #   600m 안에서 더 먼 곳이 골라질 수 있다 — 대체 활동은 먼저 같은 종류여야 한다(코덱스 합의, 활동 PR #6 규칙)
        return (priority if isinstance(priority, int) else SCENARIO_PRIORITY_NONE,
                self.changed_items, fare_unknown, self.extra_cost_krw or 0, self.shift_minutes, self.walk_min or 0,
                0 if self.reversible_internally else 1, 1 if self.warnings else 0,
                -self.similarity, round(self.distance_m), self.key)

    @property
    def name(self) -> str:
        if self.place:
            return self.place["name"]
        return (self.option or {}).get("label", self.key)


def distance_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a["latitude"], a["longitude"],
                                                b["latitude"], b["longitude"]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def walk_minutes(meters: float) -> int:
    return max(1, math.ceil(meters / WALK_M_PER_MIN))


def _hm(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def _on(moment: datetime, hhmm: str) -> datetime:
    if hhmm in ("24:00",):
        return moment.replace(hour=23, minute=59, second=59, microsecond=0)
    hour, minute = map(int, hhmm.split(":"))
    return moment.replace(hour=hour, minute=minute, second=0, microsecond=0)


def open_during(place: dict[str, Any], start: datetime, end: datetime | None) -> bool | None:
    """영업시간 안인가. ★영업시간을 모르면 `None` — 「연다」로 읽지 않는다.
    ★`[2026-09-28]` 그날의 영업시간(`place_hours.hours_on` — 요일별 칸이 먼저, 쉬는 날이면 False)."""
    from .place_hours import fits

    return fits(place.get("attributes") or {}, start, end or start)


def dining_fits(place: dict[str, Any], arrival: datetime, minutes: int) -> tuple[bool | None, str]:
    """그 시각에 들어가 `minutes` 동안 먹을 수 있나. (판정, 이유)."""
    end = arrival + timedelta(minutes=minutes)
    opened = open_during(place, arrival, end)
    if opened is None:
        return None, "영업시간을 확인할 수 없다"
    if not opened:
        return False, "그 시각 영업하지 않는다"
    attributes = place.get("attributes") or {}
    rest = attributes.get("break")
    if rest:
        rest_start, rest_end = _on(arrival, rest[0]), _on(arrival, rest[1])
        margin = attributes.get("last_order_before_break_min")
        last_order = rest_start - timedelta(minutes=margin or 0)
        if arrival < rest_end and arrival + timedelta(minutes=ORDER_MARGIN_MIN) > last_order:
            left = max(0, int((last_order - arrival).total_seconds() // 60))
            return False, (f"{rest[0]} 브레이크타임 전 라스트오더({_hm(last_order)})까지 "
                           f"{left}분 — 주문 가능한 시간이 촉박하다")
        if arrival < rest_start < end:
            return False, f"{rest[0]} 브레이크타임에 걸린다"
    # ★`[2026-09-28]` 영업 종료 앞 라스트오더도 **알면** 같은 20분을 건다(전에는 브레이크 앞에만 걸었다)
    from .place_hours import hours_on

    day = hours_on(attributes, arrival.date())
    if not isinstance(day, str) and day is not None and day.last_entry is not None:
        last_order = arrival.replace(hour=day.last_entry.hour, minute=day.last_entry.minute,
                                     second=0, microsecond=0)
        if arrival + timedelta(minutes=ORDER_MARGIN_MIN) > last_order:
            left = max(0, int((last_order - arrival).total_seconds() // 60))
            return False, (f"라스트오더({_hm(last_order)})까지 {left}분 — "
                           f"주문 여유 {ORDER_MARGIN_MIN}분이 안 된다")
    return True, ""


def dining_warnings(place: dict[str, Any], arrival: datetime, minutes: int) -> list[str]:
    """★탈락은 아니지만 알려야 할 것 — 라스트오더를 **모르는데** 식사가 마감 60분 안에 끝난다. `[2026-09-28]`

    요식 원장의 `needs_last_order_check`(P-02)와 같은 규칙이다. 원장에 짝이 없는 식당도 같은 경고를 받게
    코어 영업시간으로 한 번 더 둔다. 라스트오더를 알면 경고하지 않는다 — 그때는 `dining_fits` 가 20분으로 판정했다.
    """
    from .place_hours import hours_on

    end = arrival + timedelta(minutes=minutes)
    attributes = place.get("attributes") or {}
    out: list[str] = []
    rest = attributes.get("break")
    if rest and attributes.get("last_order_before_break_min") is None:
        rest_start = _on(arrival, rest[0])
        if arrival < rest_start and end <= rest_start <= end + timedelta(minutes=LAST_ORDER_WARN_MIN):
            out.append(f"{rest[0]} 브레이크타임 1시간 안에 식사가 끝나요 — 마지막 주문 시각을 확인해 주세요")
    day = hours_on(attributes, arrival.date())
    if not isinstance(day, str) and day is not None and day.last_entry is None:
        closes = arrival.replace(hour=day.closes.hour, minute=day.closes.minute, second=0, microsecond=0)
        if end <= closes <= end + timedelta(minutes=LAST_ORDER_WARN_MIN):
            out.append(f"{_hm(closes)} 마감 1시간 안에 식사가 끝나요 — 마지막 주문 시각을 확인해 주세요")
    return out


#: 이 사건 종류는 **실내로 옮기면 원인이 사라진다** — 대안을 실내에서 찾는다.
WEATHER_LIKE = frozenset({"air_quality", "weather_warning", "forecast"})


# ── 후보: 활동 ─────────────────────────────────────────────────
def activity_candidates(*, original: dict[str, Any], places: list[dict[str, Any]],
                        start: datetime, end: datetime | None, causes: list[dict[str, Any]],
                        radius_m: int = 600,
                        similarity: Callable[[Any, Any], int] | None = None,
                        proposal: bool = False) -> list[Candidate]:
    """깨진 활동의 대안 후보. ★원인이 날씨·대기질이면 **실내**에서만 찾는다.

    `similarity(원래 장소의 분류, 후보의 분류) -> int` 는 활동 팀이 넘긴다(`activity/similarity.py`).
    ★순위에만 쓴다 — 후보를 거르지 않는다. 없으면 0(예전 순서).
    """
    indoor_only = any(cause.get("category") in WEATHER_LIKE for cause in causes)
    base_price = (original.get("attributes") or {}).get("price_krw")
    out = []
    for place in places:
        if place["place_id"] == original["place_id"] or place.get("kind") != "activity":
            continue
        if place.get("latitude") is None or distance_m(original, place) > radius_m:
            continue
        attributes = place.get("attributes") or {}
        # ★`[2026-09-29]` 「실내」는 출처가 적은 `indoor` 이거나, 날씨 영향이 **없다고 아는** 곳(`weather_sensitive is False`).
        #   모름(`None`)은 실내로 치지 않는다 — 비를 피하려고 고른 곳이 또 야외일 수 있다
        if indoor_only and not (attributes.get("indoor") or place.get("weather_sensitive") is False):
            continue
        candidate = Candidate(key=str(place["place_id"]), place=place, changed_items=1,
                              extra_cost_krw=None, shift_minutes=0,
                              distance_m=distance_m(original, place))
        if similarity is not None:
            candidate.similarity = similarity(original.get("catalog_class"), place.get("catalog_class"))
        price = attributes.get("price_krw")
        if price is None or base_price is None:
            # ★`[2026-09-29]` 가격 모름은 **경고**다(탈락이 아니다) — 실제 장소는 대부분 가격이 없어 자동 대체가 늘 실패했다.
            #   새벽 확인의 대체(`plan_activity_closed_on_day`)와 같은 규칙. 경고가 있으면 순위는 뒤로 간다(`Candidate.rank`)
            candidate.warnings.append("가격을 몰라 추가 비용을 계산할 수 없다")
        else:
            candidate.extra_cost_krw = max(0, int(price) - int(base_price))
        opened = open_during(place, start, end)
        if opened is False:
            candidate.rejected.append("그 시각 영업하지 않는다")
        elif opened is None:
            (candidate.warnings if proposal else candidate.rejected).append("그 시각 영업을 확인할 수 없다")
        out.append(candidate)
    return out


# ── 후보: 식당 ─────────────────────────────────────────────────
def dining_candidates(*, original: dict[str, Any], places: list[dict[str, Any]],
                      arrival: datetime, minutes: int, constraints: dict[str, Any],
                      radius_m: int, next_start: datetime | None,
                      exclude: set[str] = frozenset(), ledger: Any | None = None,
                      pool: dict[str, dict[str, Any]] | None = None) -> list[Candidate]:
    """주변 식당 후보. ★조건(결제수단)은 **탈락**이지 감점이 아니다(§6-C-2).

    ★`[2026-09-28]` 가격은 보지 않는다 — 탈락에도 순위에도(맨 위 머리말).
    ★`pool` 이 있으면 **요식 원장이 낸 후보만** 본다(`{place_id: 축}`). 원장은 반경 사다리(500→1000→2000m)를
      스스로 정하므로 여기 `radius_m` 을 다시 걸지 않는다. 영업 판정도 원장(`ledger.state`)에 먼저 묻고,
      원장이 모른다고 하면 코어 영업시간으로 본다. `judged_by` 에 어디서 판정했는지 남긴다.
    """
    need_payment = constraints.get("payment")
    end_of = lambda start: start + timedelta(minutes=minutes)  # noqa: E731
    out = []
    for place in places:
        if place["place_id"] == original["place_id"] or place["place_id"] in exclude:
            continue
        if place.get("kind") != "dining" or place.get("latitude") is None:
            continue
        if pool is not None and str(place["place_id"]) not in pool:
            continue
        meters = distance_m(original, place)
        if pool is None and meters > radius_m:
            continue
        walk = walk_minutes(meters)
        attributes = place.get("attributes") or {}
        candidate = Candidate(key=str(place["place_id"]), place=place, changed_items=1,
                              extra_cost_krw=None, shift_minutes=0, walk_min=walk,
                              axis=(pool or {}).get(str(place["place_id"])))
        if need_payment and need_payment not in (attributes.get("payment") or []):
            candidate.rejected.append(f"결제 조건({need_payment}) 불충족")
        state = ledger.state(str(place["place_id"]), arrival, end_of(arrival)) \
            if ledger is not None and pool is not None else None
        if state and state.get("available") and state.get("linked") \
                and state.get("open_at_slot") is not None:
            candidate.judged_by = "dining_ledger"
            if state["open_at_slot"] is False:
                candidate.rejected.append("그 시각 영업하지 않는다(요식 원장)")
            elif state.get("order_ok") is False:
                candidate.rejected.append(f"라스트오더까지 주문 여유 {ORDER_MARGIN_MIN}분이 안 된다(요식 원장)")
            else:
                if state.get("needs_check"):
                    candidate.warnings.append("마감 1시간 안에 식사가 끝나요 — 마지막 주문 시각을 확인해 주세요")
                if state.get("needs_holiday_check"):
                    candidate.warnings.append("명절·공휴일이라 영업시간이 다를 수 있어요")
        else:
            candidate.judged_by = "core_place"
            fits, why = dining_fits(place, arrival, minutes)
            if fits is not True:
                candidate.rejected.append(why)
            else:
                candidate.warnings += dining_warnings(place, arrival, minutes)
        candidate.starts_at = arrival
        candidate.ends_at = arrival + timedelta(minutes=minutes)
        if next_start is not None and candidate.ends_at > next_start:
            candidate.rejected.append(f"다음 일정({_hm(next_start)})과 겹친다")
        out.append(candidate)
    return out


# ── 후보: 경로 ─────────────────────────────────────────────────
def route_candidates(*, route: dict[str, Any], depart: datetime, planned_arrival: datetime,
                     next_start: datetime | None,
                     events: dict[str, dict[str, Any]]) -> list[Candidate]:
    """구간의 경로 후보. ★사건이 걸린 경로는 **효과대로** 다룬다.

        무정차(skip_station)   그 역을 쓰는 경로는 도달 불가 — 탈락
        도로 통제(road_control) 소요가 `eta_min_if_controlled` 로 바뀐다.
                                값이 없으면(택시 등) **소요 산출 불가 — 탈락**
    """
    options = {option["id"]: option for option in route.get("options", [])}
    # ☆`[2026-09-29 이동 계산기 문제목록 #23]` 원래 계획의 요금을 모르면 0원으로 두지 않는다 — 앞 판은 0 으로 두어
    #   대안 요금 전체가 「추가 비용」으로 잡혔다. 모르면 추가 비용을 모름(None)으로 둔다(지어내지 않는다).
    planned_fare = (options.get(route.get("planned")) or {}).get("fare_krw")
    out = []
    for option in options.values():
        eta = option.get("eta_min")
        candidate = Candidate(key=option["id"], place=None, changed_items=1,
                              extra_cost_krw=None, shift_minutes=0, option=dict(option))
        for target in option.get("uses", []):
            event = events.get(target)
            if event is None:
                continue
            if event.get("effect") == "skip_station":
                candidate.rejected.append(f"{event.get('summary')} — 이 경로로는 도달할 수 없다")
            elif event.get("effect") == "road_control":
                eta = option.get("eta_min_if_controlled")
                if eta is None:
                    candidate.rejected.append("통제 구간의 실제 소요를 확인할 수 없다")
        if eta is None:
            if not candidate.rejected:
                candidate.rejected.append("소요를 확인할 수 없다")
        else:
            arrival = depart + timedelta(minutes=int(eta))
            candidate.option["eta_effective"] = int(eta)
            candidate.starts_at, candidate.ends_at = depart, arrival
            candidate.shift_minutes = max(0, int((arrival - planned_arrival).total_seconds() // 60))
            if next_start is not None and arrival > next_start:
                candidate.rejected.append(f"다음 일정({_hm(next_start)})에 늦는다 — 도착 {_hm(arrival)}")
        fare = option.get("fare_krw")
        candidate.extra_cost_krw = (None if fare is None or planned_fare is None
                                    else max(0, int(fare) - int(planned_fare)))
        # ☆`[2026-09-29 이동 계산기 문제목록 #22]` 요금을 모른다고 **탈락시키지 않는다** — 앞 판은 탈락시켜 버스를 섞어
        #   갈아타는 대안(요금 칸이 없다)이 사고 때 전부 떨어졌다. 식당 가격과 같은 방향(2026-09-28 사용자 결정)이다.
        #   대신 순위에서 요금을 아는 후보보다 뒤에 선다(Candidate.rank — 경로 후보만).
        out.append(candidate)
    return out


# ── 후보: 매장(재고) ───────────────────────────────────────────
def _point_segment_detour(a: dict[str, Any], b: dict[str, Any], c: dict[str, Any]) -> float:
    """a→c→b 로 돌아갈 때 늘어나는 거리."""
    return distance_m(a, c) + distance_m(c, b) - distance_m(a, b)


def store_candidates(*, here: dict[str, Any], home: dict[str, Any], places: list[dict[str, Any]],
                     products: list[str], at: datetime, max_detour_m: int = 1500) -> list[Candidate]:
    """같은 상품을 **취급할 만한** 매장. ★재고는 확인하지 않는다 — 소스가 없다."""
    wanted = {"명절 선물세트"} if any("선물세트" in p for p in products) else set(products)
    out = []
    for place in places:
        if place["place_id"] == here["place_id"] or place.get("latitude") is None:
            continue
        attributes = place.get("attributes") or {}
        if not wanted & set(attributes.get("sells") or []):
            continue
        detour = _point_segment_detour(here, home, place)
        candidate = Candidate(key=str(place["place_id"]), place=place, changed_items=0,
                              extra_cost_krw=0, shift_minutes=int(detour // WALK_M_PER_MIN))
        candidate.option = {"detour_m": round(detour)}
        if detour > max_detour_m:
            candidate.rejected.append(f"귀가 동선에서 {round(detour)}m 벗어난다")
        if open_during(place, at, at) is not True:
            candidate.rejected.append("지금 영업을 확인할 수 없다")
        out.append(candidate)
    return out


def choose(candidates: list[Candidate],
           recheck: Callable[[Candidate], dict[str, Any]] | None = None,
           distinct: Callable[[Candidate, Candidate], bool] | None = None) -> tuple[
               Candidate | None, list[Candidate], list[Candidate]]:
    """(최선, 재요청용 둘, 탈락). ★재검증은 **탈락을 통과한 것에만** 돌린다.

    `distinct(a, b)` — 둘이 **같은 곳**이면 참(활동 — `itinerary_changes.same_site`). ★`[2026-09-29 ui 세션 지적]`
      「K-컬처 스크린(대한민국역사박물관)」과 「대한민국역사박물관」(같은 주소 · 6m)이 바뀐 곳과 다른 안에 함께 나왔다 —
      순위가 앞선 하나만 남긴다(뒤의 것은 탈락이 아니라 그냥 빠진다)."""
    survivors, rejected = [], []
    for candidate in candidates:
        if not candidate.rejected and recheck is not None:
            report = recheck(candidate)
            candidate.recheck = report
            if report.get("verdict") != "clear":
                candidate.rejected.append(f"재검증 불통과: {report.get('verdict')}")
        (rejected if candidate.rejected else survivors).append(candidate)
    survivors.sort(key=Candidate.rank)
    if distinct is not None:
        kept: list[Candidate] = []
        for candidate in survivors:
            if not any(distinct(candidate, other) for other in kept):
                kept.append(candidate)
        survivors = kept
    if not survivors:
        return None, [], rejected
    return survivors[0], survivors[1:3], rejected


# ── 알림 문구 ──────────────────────────────────────────────────
def _part_of_day(moment: datetime) -> str:
    return "오전" if moment.hour < 12 else "오후"


def _reason_phrase(causes: list[dict[str, Any]], place: dict[str, Any]) -> str:
    """★원인에서만 문장을 만든다. 원인에 없는 이유를 붙이지 않는다."""
    categories = {cause.get("category") for cause in causes}
    attributes = place.get("attributes") or {}
    if "air_quality" in categories and attributes.get("view_dependent"):
        return "시야 확보가 어려울 것으로 예상되어"
    if "air_quality" in categories:
        return "미세먼지 기준을 넘어 야외 활동이 어려울 것으로 예상되어"
    if categories & {"weather_warning", "forecast"}:
        return "기상 악화가 예상되어"
    return "운영 상황이 바뀌어"


def alternate_record(candidate: Candidate) -> dict[str, Any]:
    """재요청용으로 들고 있는 「다른 안」 하나(§6-C-4 6단계).

    ★이름만 두면 재요청 때 **다시 계산**해야 하고, 그 사이 입력이 바뀌면 고객이 본
      「다른 안」과 다른 것이 들어간다. 적용에 필요한 값을 그대로 적어 둔다.
    """
    return {"key": candidate.key, "name": candidate.name,
            "place_id": candidate.place["place_id"] if candidate.place else None,
            "option": (candidate.option or {}).get("id") if candidate.option else None,
            "option_label": (candidate.option or {}).get("label") if candidate.option else None,
            "starts_at": candidate.starts_at.isoformat() if candidate.starts_at else None,
            "ends_at": candidate.ends_at.isoformat() if candidate.ends_at else None,
            "walk_min": candidate.walk_min,
            # ★`[2026-09-28]` 화면은 key·name 만 읽고 나머지는 무시한다(UI 조사) — 더해도 깨지지 않는다
            **({"warnings": list(candidate.warnings)} if candidate.warnings else {}),
            **({"axis": candidate.axis} if candidate.axis else {}),
            **({"judged_by": candidate.judged_by} if candidate.judged_by else {}),
            # ★`[2026-09-29]` 관광공사 목록에서 온 후보 — 아직 우리 장소가 아니다. 고객이 고르면 그때 이 값으로 그 여행
            #   전용 장소를 등록한다(`TripStore.add_catalog_place` · pending.choose). 미리 등록하지 않는다(코덱스 합의)
            **({"catalog_place": candidate.place} if candidate.place
               and (candidate.place.get("attributes") or {}).get("catalog_pending") else {})}


def _notice(text: str, *, causes, changed, alternates, replay, **extra) -> dict[str, Any]:
    return {"text": text, "language": "ko",      # ★고객 언어 옮김은 보낼 때(결정 14)
            "causes": causes, "changed": changed,
            "other_options": [c.name for c in alternates], "replay": replay, **extra}


def change_notice(*, original: dict[str, Any], replacement: dict[str, Any], start: datetime,
                  causes: list[dict[str, Any]], alternates: list[Candidate],
                  replay: bool) -> dict[str, Any]:
    """활동 변경 통지."""
    same_building = (original.get("attributes") or {}).get("building") and \
        (original.get("attributes") or {}).get("building") == \
        (replacement.get("attributes") or {}).get("building")
    area = (original.get("attributes") or {}).get("area")
    subject = f"{original['name']} {area}" if area else original["name"]
    floor = (replacement.get("attributes") or {}).get("floor")
    where = " ".join(part for part in (
        "같은 건물" if same_building else None, floor, replacement["name"]) if part)
    text = (f"오늘 {_part_of_day(start)} {subject}는 {_reason_phrase(causes, original)}, "
            f"{where}으로 변경됩니다.")
    return _notice(text, causes=causes, alternates=alternates, replay=replay,
                   changed={"from": original["name"], "to": replacement["name"],
                            "at": start.isoformat()})


def route_notice(*, route: dict[str, Any], planned: dict[str, Any], best: Candidate,
                 alternates: list[Candidate], rejected: list[Candidate],
                 causes: list[dict[str, Any]], planned_arrival: datetime,
                 next_title: str | None, replay: bool) -> dict[str, Any]:
    """경로 변경 통지. ★탈락시킨 수단도 **왜 뺐는지** 말한다(택시 「확인 불가」)."""
    option = best.option or {}
    lines = [f"{cause.get('summary')}." for cause in causes if cause.get("summary")]
    if best.key != route.get("planned"):
        lines.append(f"{option.get('label')}로 바꿔 안내합니다"
                     f"(도보 {option.get('walk_m')}m, 예상 {option.get('eta_effective')}분).")
    if alternates:
        lines.append("다른 안: " + ", ".join(
            f"{(c.option or {}).get('label')}(도보 {(c.option or {}).get('walk_m')}m, "
            f"예상 {(c.option or {}).get('eta_effective')}분)" for c in alternates) + ".")
    for candidate in rejected:
        if candidate.key == route.get("planned"):
            continue
        if any("실제 소요" in reason for reason in candidate.rejected):
            lines.append(f"{(candidate.option or {}).get('label')}는 통제 구간의 실제 소요를 "
                         f"확인할 수 없어 권하지 않습니다.")
    if option.get("walk_note"):
        lines.append(f"{option['walk_note']}합니다.")
    if best.ends_at and best.ends_at > planned_arrival and next_title:
        lines.append(f"도착이 조금 늦어지지만 {next_title} 일정에는 영향이 없습니다.")
    return _notice(" ".join(lines), causes=causes, alternates=alternates, replay=replay,
                   changed={"from": planned.get("label"), "to": option.get("label")},
                   excluded={(c.option or {}).get("label"): c.rejected for c in rejected})


def dining_notice(*, original: dict[str, Any], best: Candidate, alternates: list[Candidate],
                  reason: str, cause: dict[str, Any], after: str | None,
                  constraint_note: str | None = None) -> dict[str, Any]:
    """식사 변경 통지."""
    parts = [f"{reason}.",
             f"도보 {best.walk_min}분 거리{', ' + constraint_note if constraint_note else ''}"
             f" {best.name}(으)로 안내합니다({_hm(best.starts_at)} 입장)."]
    if best.warnings:
        # ★`[2026-09-28]` 라스트오더를 모르는데 마감이 가깝다 등 — 바꾸기는 하되 확인할 것을 알린다
        parts.append(" ".join(f"{w}." for w in best.warnings))
    if alternates:
        parts.append("다른 안: " + ", ".join(f"{c.name}(도보 {c.walk_min}분)"
                                            for c in alternates) + ".")
    if after:
        parts.append(f"이후 {after} 일정에는 영향이 없습니다.")
    return _notice(" ".join(parts), causes=[cause], alternates=alternates, replay=False,
                   changed={"from": original["name"], "to": best.name,
                            "at": best.starts_at.isoformat()},
                   **({"warnings": list(best.warnings)} if best.warnings else {}),
                   **({"judged_by": best.judged_by} if best.judged_by else {}))


__all__ = ["Candidate", "activity_candidates", "alternate_record", "change_notice", "choose", "dining_candidates",
           "dining_fits", "dining_notice", "dining_warnings", "distance_m", "open_during", "route_candidates",
           "route_notice", "store_candidates", "walk_minutes"]
