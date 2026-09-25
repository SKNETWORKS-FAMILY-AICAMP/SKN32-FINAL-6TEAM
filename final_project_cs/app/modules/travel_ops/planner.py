# -*- coding: utf-8 -*-
"""요청 → **초안 일정** → 판정 통과 → 등록. 한 경로다.

★★**이것은 v11 §4-A 를 뒤집는 작업이다.** 기준선은 「계획 생성은 우리 일이 아니다 —
  외부 에이전트가 만든 일정을 받아 검증한다」고 적었다(`program/plan/A-COP_구현계획서_v11.md`
  §4-A). 사용자 지시로 **생성기를 우리가 만든다.** 계획서는 읽기 전용이라 고치지 않았고,
  뒤집는다는 사실과 이유는 리포트에 적었다
  (`wiki/records/reports/2026-09-22_2205_일정생성기_v11-4A를_뒤집는다.md`).

★**장소를 지어내지 않는다.** 후보는 두 곳에서만 온다.

    ① 우리 DB `places`        — 운영시간·가격·구·실내 여부까지 아는 장소
    ② `place_catalog`          — 관광공사 TourAPI 를 지역 단위로 받아 둔 표(011 마이그레이션).
                                 좌표·주소·종류만 안다
    ③ TourAPI 실시간            — ②가 비었을 때만. 부른 횟수를 결과에 센다

★**모르는 값은 비워 둔다.** 카탈로그 장소는 영업시간·가격이 없다. 그러면
  `itinerary_checks` 가 그 칸을 **판정하지 않는다**(모름은 위반이 아니다). 즉 카탈로그만으로
  짠 초안은 「시간이 겹치지 않는다」까지만 보장하고 「그 시각에 연다」는 보장하지 않는다.
  그 사실을 결과의 `coverage` 가 분자/분모로 말한다 — 조용히 통과시키지 않는다.

★**LLM 은 순서를 짜는 데만 쓴다.** 모델이 받는 것은 후보 목록(번호·종류·이름·구·실내 여부)과
  고객의 자유 문장이고, 내는 것은 **그 목록의 줄 번호 순서**뿐이다. 시각·좌표·가격·이름은
  우리가 채운다. 목록에 없는 값은 버린다. 모델이 없거나(설정이 비었거나) 실패하면 **규칙
  순위로 초안을 내고 그 사실을 `planner.mode`·`planner.note` 에 적는다** — 빈손으로 돌아가지
  않는다. ★모델을 불렀는데 **쓴 값이 하나도 없으면** `mode` 가 `rules` 로 내려간다
  (`planner.from_model` / `planner.items` 가 분자/분모다) — 조용한 폴백을 만들지 않는다.

★★**판정을 건너뛰는 길이 없다.** 초안은 `check_itinerary` 를 통과해야만 돌려준다. 위반이
  나오면 고쳐서 다시 판정하고(최대 `MAX_REPAIR_ROUNDS` 회), 끝내 못 고치면 **무엇이 왜 안
  됐는지**를 담아 거절한다(`PlanRefused`).

★**우리가 고른 값(측정 아님)** — `replan.py` 와 같은 자리에 모아 둔다. 바꿀 때 한 곳만 본다.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
import re
from typing import Any, Callable, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from .density import measure_density
from .itinerary_checks import Part, Violation, check_itinerary
from .replan import distance_m, walk_minutes

KST = ZoneInfo("Asia/Seoul")

# ── 우리가 고른 값 (측정 아님) ────────────────────────────────────
def _day_window() -> tuple[time, time]:
    """★`[2026-09-24]` 하루 시간은 **가드레일 한 곳**(`travel.day_window`)에서 읽는다(D-020).
    팀 결정 — 하루 시작 08:00(평균 일정 시작 9시보다 식사 1시간 앞), 마감 22:00. 생성기는 식사를 짜지
    않으니 **첫 활동은 시작 + 1시간(09:00)** 이다. 전에는 09:30~21:30 이 코드에 박혀 팀 결정과 달랐다."""
    from app.core.settings import get_guardrails

    guard = get_guardrails()
    start_h, start_m = (int(x) for x in str(guard.get("travel.day_window.default_start")).split(":"))
    end_h, end_m = (int(x) for x in str(guard.get("travel.day_window.default_end")).split(":"))
    return time(start_h + 1, start_m), time(end_h, end_m)


DAY_START, DAY_END = _day_window()   #: 하루 첫 활동 · 마지막 일정이 끝나야 하는 시각
ACTIVITY_MIN = 90                #: 활동 한 건에 두는 시간
MEAL_MIN = 60                    #: 식사 한 건에 두는 시간
LUNCH_FROM = time(12, 0)
DINNER_FROM = time(18, 0)
TRANSFER_MIN_MIN = 10            #: 겹침을 고칠 때 뒤로 미는 최소 분
TRANSFER_MAX_MIN = 60            #: 도보 환산이 이보다 크면 여기서 자른다(대중교통을 쓸 구간이다)
TRANSFER_UNKNOWN_MIN = 20        #: 좌표를 몰라 거리를 못 재는 구간
#: ★`[2026-09-24 사용자 지시]` 도착해서 다음 일정 시작까지 두는 **여유**. 출발 시각은
#:  **다음 일정 시작 − 이동 시간 − 이 여유**로 거꾸로 잡고, 이동 알림은 그 출발 시각에 간다(D-020).
MOVE_BUFFER_MIN = 10
ACTIVITIES_PER_DAY = 2          #: 밀도 목표가 **없을 때** 하루 활동 수(설문 16번을 안 받은 요청)
#: ★`[2026-09-24]` 밀도 목표가 있으면(설문 16번 여유 → `travel.survey.pace_to_density_level`) 하루 활동 수를
#:  **짜 본 하루를 재서** 정한다 — 이 범위에서 목표를 넘지 않는 가장 많은 수. 상한·하한은 우리가 고른 값이다.
MAX_ACTIVITIES_PER_DAY = 4
MIN_ACTIVITIES_PER_DAY = 1
DINING_PER_DAY = 2               #: 점심·저녁
MAX_REPAIR_ROUNDS = 3            #: 고쳐서 다시 판정하는 횟수. 넘으면 거절한다
CATALOG_LIMIT_PER_KIND = 400     #: 카탈로그에서 한 번에 읽는 후보 수(종류별)
SHORTLIST_PER_DAY = 8            #: 모델에게 보이는 하루치 활동 후보 수

#: ★`[2026-09-22]` **요청을 규정에 붙이는 데 읽는 scope.** 여행 것만 넣는다 — 여행 질의가
#:  쇼핑몰 `refund` 문서를 끌어와 top-8 중 7건이 쇼핑몰이던 적이 있다
#:  (`wiki/records/reports/debugs/2026-09-22_정책scope에_문서가_0건인_팀들.md`).
PLAN_SCOPES = ("travel_activity", "travel_dining", "travel_access", "travel_weather")
PLAN_RAG_TOP_K = 5               #: 우리가 고른 값
GROUNDING_CHARS = 420            #: 모델에게 보이는 규정 조각 하나의 길이 상한(우리가 고른 값)

#: 상품 범위 — v11 §1. **커버 못 하는 범위를 상품에 넣지 않는다.**
SUPPORTED_CITIES = {"서울", "seoul", "Seoul", "SEOUL"}
MAX_DAYS = 7
MAX_PARTY = 4
SEOUL_AREA_CODE = "1"

#: TourAPI 관광타입 → 우리 `places.kind`. v11 §5 Activity 는 자연·인문·레포츠·쇼핑에 걸쳐
#: 12·14·28·38 넷을 다 포함한다(`tour_api.py` 주석과 같은 근거).
KIND_BY_CONTENT_TYPE = {"12": "activity", "14": "activity", "28": "activity",
                        "38": "activity", "39": "dining"}
#: 같은 activity 안에서 우리가 고른 우선순위. ★인기·평점 소스가 없다 — 카탈로그에는 순위를
#: 매길 칸이 없어서(`place_catalog` 열 목록 참고) 종류 우선순위와 사전식 순서로만 고른다.
CONTENT_TYPE_RANK = {"12": 0, "14": 1, "28": 2, "38": 3, "39": 0}
#: ★**가정이다. 확인한 값이 아니다.** 문화시설(14)·쇼핑(38)은 대체로 실내지만 예외가 있다.
#: 그래서 `attributes.indoor` (확인된 값)가 아니라 `indoor_assumed` 로 따로 싣는다 —
#: 판정기(`itinerary_checks`·`replan`)는 `indoor` 만 읽으므로 이 가정이 판정에 새지 않는다.
INDOOR_ASSUMED_BY_CONTENT_TYPE = {"14": True, "38": True}

_DISTRICT = re.compile(r"([가-힣]{1,6}구)")


class PlanRefused(Exception):
    """초안을 낼 수 없다. **무엇이 왜 안 됐는지**를 들고 있다."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.code, self.message, self.detail = code, message, detail

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.detail}


@dataclass(frozen=True)
class PlanRequest:
    city: str
    start_date: date
    days: int
    party_size: int
    constraints: Mapping[str, Any] = field(default_factory=dict)
    preferences: str = ""
    title: str | None = None
    locale: str | None = None

    def validate(self) -> None:
        if self.city.strip() not in SUPPORTED_CITIES:
            raise PlanRefused("city_not_supported",
                              f"지금 여는 도시는 서울 하나다(v11 §1). 받은 값: {self.city}",
                              supported=sorted(SUPPORTED_CITIES))
        if not 1 <= self.days <= MAX_DAYS:
            raise PlanRefused("out_of_product_scope",
                              f"기준 상품은 최대 {MAX_DAYS}일이다(v11 §1). 받은 값: {self.days}일")
        if not 1 <= self.party_size <= MAX_PARTY:
            raise PlanRefused("out_of_product_scope",
                              f"기준 상품은 최대 {MAX_PARTY}인이다(v11 §1). 받은 값: {self.party_size}인")


@dataclass
class Cand:
    """후보 장소 하나. ★**우리가 아는 것만 들고 있다** — 모르는 칸은 없는 채로 둔다."""

    key: str
    name: str
    kind: str                       # activity | dining
    lat: float | None
    lon: float | None
    attributes: dict[str, Any]
    origin: str                     # places | place_catalog | tour_api
    weather_sensitive: bool = False
    rank_hint: int = 9

    @property
    def district(self) -> str | None:
        return self.attributes.get("district") or None

    @property
    def indoorish(self) -> bool | None:
        """실내인가. **확인된 값이 먼저**, 없으면 가정, 그것도 없으면 모름(`None`)."""
        if "indoor" in self.attributes:
            return bool(self.attributes["indoor"])
        if "indoor_assumed" in self.attributes:
            return bool(self.attributes["indoor_assumed"])
        return None

    def as_place(self) -> dict[str, Any]:
        """`POST /v1/trips` 의 `places[]` 모양. ★`PlaceIn` 은 extra 를 금지하므로 출처는
        `attributes` 안에 싣는다(모델 칸을 늘리지 않는다)."""
        return {"key": self.key, "name": self.name, "kind": self.kind,
                "lat": self.lat, "lon": self.lon,
                # ★`PlaceIn.weather_sensitive` 는 bool 이라 「모름」을 못 담는다. 아는 장소의
                #   값만 True 로 올리고, 모르는 곳은 기본값 False 가 들어간다 — 우리가 「야외가
                #   아니다」라고 **단정한 것이 아니다**. DB 칸은 NULL 을 받으므로 이 한계는
                #   계약 쪽에 있다(리포트 「못 하는 것」에 적었다).
                "weather_sensitive": bool(self.weather_sensitive),
                "attributes": dict(self.attributes)}

    def for_check(self) -> dict[str, Any]:
        return {"name": self.name, "attributes": dict(self.attributes)}


@dataclass
class Preference:
    """자유 문장에서 뽑은 선호. ★**키워드 대조다** — 모델이 아니다.

    ☆한계: 문장을 쉼표·마침표로 잘라 「부정 표현 + 낱말」이 같은 조각에 있을 때만 싫다고
      읽는다. 「맵지 않은 것도 좋지만」 같은 문장은 구분하지 못한다.
    """

    indoor_first: bool = False
    outdoor_first: bool = False
    with_children: bool = False
    avoid: tuple[str, ...] = ()
    raw: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"indoor_first": self.indoor_first, "outdoor_first": self.outdoor_first,
                "with_children": self.with_children, "avoid": list(self.avoid)}


_INDOOR_WORDS = ("실내", "indoor", "비가", "비 오", "더워", "더운", "추워", "추운", "미세먼지")
_OUTDOOR_WORDS = ("야외", "바깥", "outdoor", "산책", "공원", "자연")
_CHILD_WORDS = ("아이", "아기", "유아", "어린이", "child", "kid", "toddler")
_NEGATIVE = ("싫", "안 ", "안돼", "못 ", "말고", "빼", "없이", "제외", "avoid", "without",
             "no ", "not ", "dislike", "hate")
#: 싫다고 한 낱말 → 후보 이름에서 거를 말들. ★요리 종류 표가 없어서 **이름으로만** 거른다
#: (`place_catalog` 에 음식 분류 칸이 없다). 이름에 안 드러나는 곳은 못 거른다.
_AVOID_TERMS: dict[str, tuple[str, ...]] = {
    "매운": ("매운", "마라", "불닭", "떡볶이", "닭발", "짬뽕", "매워", "spicy"),
    "spicy": ("매운", "마라", "불닭", "떡볶이", "닭발", "짬뽕", "spicy"),
    # ★「회」 한 글자는 쓰지 않는다 — 「회관」·「한정식회」까지 걸린다(이름으로만 거르는 한계).
    "해산물": ("해산물", "횟집", "수산", "조개", "생선", "초밥", "seafood"),
    "seafood": ("해산물", "횟집", "수산", "조개", "생선", "초밥", "seafood"),
    "술": ("술집", "포차", "호프", "이자카야", "펍", "bar"),
}
#: 아이 동반이면 자동으로 빼는 것. ★고객이 말하지 않아도 빼는 유일한 항목이고 그 이유를 적는다.
_CHILD_AVOID = ("술집", "포차", "호프", "이자카야", "펍")


def preference_profile(text: str) -> Preference:
    lowered = (text or "").lower()
    pieces = [piece for piece in re.split(r"[.,;·\n?!]| 그리고 | 그런데 ", lowered) if piece.strip()]
    avoid: list[str] = []
    for piece in pieces:
        if not any(mark in piece for mark in _NEGATIVE):
            continue
        for word, terms in _AVOID_TERMS.items():
            if word in piece:
                avoid += [term for term in terms if term not in avoid]
    children = any(word in lowered for word in _CHILD_WORDS)
    if children:
        avoid += [term for term in _CHILD_AVOID if term not in avoid]
    return Preference(indoor_first=any(word in lowered for word in _INDOOR_WORDS),
                      outdoor_first=any(word in lowered for word in _OUTDOOR_WORDS),
                      with_children=children, avoid=tuple(avoid), raw=text or "")


# ── 후보 모으기 ──────────────────────────────────────────────────
def _district_of(address: str | None) -> str | None:
    match = _DISTRICT.search(address or "")
    return match.group(1) if match else None


def load_candidates(conn, *, tenant_id: str, kinds: Sequence[str] = ("activity", "dining"),
                    limit_per_kind: int = CATALOG_LIMIT_PER_KIND) -> list[Cand]:
    """①우리 DB `places` + ②`place_catalog`. **같은 (이름, 종류)면 ①이 이긴다** — 아는 값이 많다."""
    found: dict[tuple[str, str], Cand] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT place_id, name, kind, latitude, longitude, weather_sensitive, "
                    "attributes FROM places WHERE tenant_id=%s AND kind = ANY(%s) ORDER BY name",
                    (tenant_id, list(kinds)))
        for place_id, name, kind, lat, lon, sensitive, attributes in cur.fetchall():
            if lat is None or lon is None:
                # ★좌표를 모르는 장소는 후보에서 뺀다. 등록 계약(`PlaceIn.lat`·`lon`)이 필수로
                #   받고, 여기서 0 이나 서울시청 좌표로 채우면 그게 지어낸 값이다.
                continue
            attributes = dict(attributes or {})
            found[(name, kind)] = Cand(key=f"db_{place_id}", name=name, kind=kind,
                                       lat=lat, lon=lon, attributes=attributes,
                                       origin="places", weather_sensitive=bool(sensitive),
                                       rank_hint=0)
        wanted_types = [code for code, kind in KIND_BY_CONTENT_TYPE.items() if kind in kinds]
        cur.execute(
            "SELECT content_id, content_type_id, title, address, latitude, longitude "
            "FROM place_catalog WHERE tenant_id=%s AND source='tour_api' "
            "AND content_type_id = ANY(%s) AND latitude IS NOT NULL AND longitude IS NOT NULL "
            "AND (area_code=%s OR address LIKE '서울%%') ORDER BY content_type_id, content_id "
            "LIMIT %s",
            (tenant_id, wanted_types, SEOUL_AREA_CODE, limit_per_kind * max(1, len(wanted_types))))
        for content_id, content_type, title, address, lat, lon in cur.fetchall():
            kind = KIND_BY_CONTENT_TYPE.get(str(content_type))
            if kind is None or (title, kind) in found:
                continue
            attributes: dict[str, Any] = {"source": "tour_api", "source_content_id": str(content_id),
                                          "source_content_type_id": str(content_type)}
            district = _district_of(address)
            if district:
                attributes["district"] = district
            if address:
                attributes["address"] = address
            assumed = INDOOR_ASSUMED_BY_CONTENT_TYPE.get(str(content_type))
            if assumed is not None:
                attributes["indoor_assumed"] = assumed
            # ★영업시간·가격은 **넣지 않는다.** 카탈로그가 모른다. 빈 칸이면 판정이 건너뛴다.
            found[(title, kind)] = Cand(key=f"tour_{content_id}", name=title, kind=kind,
                                        lat=lat, lon=lon, attributes=attributes,
                                        origin="place_catalog",
                                        rank_hint=1 + CONTENT_TYPE_RANK.get(str(content_type), 9))
    return list(found.values())


def fill_from_tour_api(candidates: list[Cand], *, source: Any, area_code: str = SEOUL_AREA_CODE,
                       pages: int = 1, rows: int = 100) -> tuple[list[Cand], int]:
    """③ 카탈로그가 비었을 때만 부른다. **부른 횟수를 같이 돌려준다** — 하루 한도가 있다."""
    calls = 0
    known = {(cand.name, cand.kind) for cand in candidates}
    for page in range(1, pages + 1):
        body = source.area_page(area_code, page=page, rows=rows)
        calls += 1
        if body is None:
            break
        for row in body.get("items") or []:
            kind = KIND_BY_CONTENT_TYPE.get(str(row.get("content_type_id") or ""))
            title = str(row.get("title") or "").strip()
            if kind is None or not title or (title, kind) in known:
                continue
            if row.get("latitude") is None or row.get("longitude") is None:
                continue
            attributes: dict[str, Any] = {
                "source": "tour_api", "source_content_id": str(row.get("content_id") or ""),
                "source_content_type_id": str(row.get("content_type_id") or "")}
            district = _district_of(row.get("address"))
            if district:
                attributes["district"] = district
            assumed = INDOOR_ASSUMED_BY_CONTENT_TYPE.get(str(row.get("content_type_id") or ""))
            if assumed is not None:
                attributes["indoor_assumed"] = assumed
            known.add((title, kind))
            candidates.append(Cand(key=f"tour_{row.get('content_id')}", name=title, kind=kind,
                                   lat=row.get("latitude"), lon=row.get("longitude"),
                                   attributes=attributes, origin="tour_api", rank_hint=2))
    return candidates, calls


# ── 선호 반영 · 순위 (규칙) ───────────────────────────────────────
def _avoided(cand: Cand, pref: Preference) -> bool:
    name = cand.name.lower()
    return any(term.lower() in name for term in pref.avoid)


def rank_candidates(candidates: Iterable[Cand], pref: Preference) -> list[Cand]:
    """★**결정적이다** — 같은 입력이면 같은 순서다. 동률은 이름으로 가른다.

    선호는 여기서 반영한다. 모델은 이 순위 위에서 고르고 섞을 뿐이다.
    """
    ranked = []
    for cand in candidates:
        if _avoided(cand, pref):
            continue                      # ★싫다고 한 것은 **탈락**이지 감점이 아니다
        indoor = cand.indoorish
        if pref.indoor_first:
            fit = 0 if indoor is True else (1 if indoor is None else 2)
        elif pref.outdoor_first:
            fit = 0 if indoor is False else (1 if indoor is None else 2)
        else:
            fit = 0
        # ★**아는 값이 많은 장소가 먼저다** — 영업시간을 알면 판정이 실제로 그 칸을 본다.
        #   종류 우선순위(`rank_hint`)보다 앞에 둔다: 판정 가능한 초안이 예쁜 초안보다 낫다.
        known = 0 if "hours" in cand.attributes else 1
        ranked.append(((fit, known, cand.rank_hint, cand.name), cand))
    ranked.sort(key=lambda pair: pair[0])
    return [cand for _, cand in ranked]


def _by_district(candidates: list[Cand]) -> dict[str, list[Cand]]:
    groups: dict[str, list[Cand]] = {}
    for cand in candidates:
        groups.setdefault(cand.district or "", []).append(cand)
    return groups


def pick_day_pools(activities: list[Cand], dining: list[Cand], days: int
                   ) -> list[tuple[list[Cand], list[Cand]]]:
    """하루씩 **같은 구로 묶는다.** 구가 다른 항목을 0분 간격으로 붙이면 판정이 걸고
    (`no_transfer_time`), 애초에 하루 동선이 흩어진다.

    ★구를 모르는 후보는 버리지 않는다 — 묶을 수 없을 뿐이라 남은 자리에 채운다.
    """
    groups = _by_district(activities)
    ordered = sorted((key for key in groups if key),
                     key=lambda key: (-len(groups[key]), key))
    pools: list[tuple[list[Cand], list[Cand]]] = []
    used: set[str] = set()
    spare_act = [cand for cand in activities if not cand.district]
    for index in range(days):
        district = ordered[index] if index < len(ordered) else None
        day_acts = [cand for cand in (groups.get(district) or []) if cand.key not in used]
        if len(day_acts) < ACTIVITIES_PER_DAY:
            day_acts = day_acts + [cand for cand in activities
                                   if cand.key not in used and cand not in day_acts]
        day_acts = (day_acts + spare_act)[:SHORTLIST_PER_DAY]
        used.update(cand.key for cand in day_acts[:ACTIVITIES_PER_DAY])
        near = _near_dining(dining, day_acts[:ACTIVITIES_PER_DAY], district)
        pools.append((day_acts, near))
    return pools


def _near_dining(dining: list[Cand], anchors: list[Cand], district: str | None) -> list[Cand]:
    """같은 구 → 그다음 **가까운 순**. 거리를 모르면 순위 그대로 뒤에 붙인다."""
    same = [cand for cand in dining if district and cand.district == district]
    rest = [cand for cand in dining if cand not in same]
    anchor = next((cand for cand in anchors if cand.lat is not None), None)
    if anchor is not None:
        def far(cand: Cand) -> tuple[int, float, str]:
            if cand.lat is None:
                return (1, 0.0, cand.name)
            return (0, distance_m({"latitude": anchor.lat, "longitude": anchor.lon},
                                  {"latitude": cand.lat, "longitude": cand.lon}), cand.name)
        same, rest = sorted(same, key=far), sorted(rest, key=far)
    return (same + rest)[:SHORTLIST_PER_DAY]


# ── 모델: 순서만 짠다 ────────────────────────────────────────────
#
# ★★`[실측 2026-09-22, gemma4:12b]` 처음에는 후보를 `id=tour_126508` 로 보이고 **그 문자열**을
#   받으려 했다. 모델은 **줄 번호**를 냈다(`{"activities":[3],"dining":[4,5]}`). 그래서 서울 3일
#   실행에서 모델이 낸 값이 **하나도 목록에 없는 것**이 되어 전부 규칙 순위로 떨어졌는데,
#   결과에는 `mode="llm"` 이라고 적혀 있었다 — **조용한 폴백**이다.
#   지금은 ①번호로 물어보고 ②번호와 우리 후보 키를 **둘 다** 받고 ③몇 개가 실제로 쓰였는지
#   `planner.from_model` 로 센다. 하나도 안 쓰였으면 `mode` 가 `rules` 로 내려간다.
ORDER_SYSTEM = (
    "You arrange the visiting ORDER of places for one day in Seoul.\n"
    "You are given a numbered list of candidate places and the traveller's own words.\n"
    "Return JSON with exactly two keys: "
    "{\"activities\": [numbers], \"dining\": [numbers]}.\n"
    "RULES:\n"
    "- Each number is the number at the START of a candidate line. Use ONLY those numbers.\n"
    "- Never invent a place or a number that is not in the list.\n"
    "- Never output times, dates, coordinates, prices, durations or names. "
    "The server fills those.\n"
    "- activities: the activity lines you would visit, in visiting order, best first.\n"
    "- dining: the dining lines for lunch and dinner, lunch first.\n"
    "- Respect the traveller's words (e.g. indoor first, with a child, dislikes)."
)


def _order_lines(candidates: list[Cand]) -> str:
    lines = []
    for index, cand in enumerate(candidates, start=1):
        indoor = cand.indoorish
        mark = "indoor" if indoor is True else ("outdoor" if indoor is False else "indoor unknown")
        lines.append(f"{index}. {cand.kind} | {cand.name} | "
                     f"{cand.district or 'district unknown'} | {mark}")
    return "\n".join(lines)


def ground_request(*, tenant_id: str, request: PlanRequest,
                   search: Callable[..., Any] | None = None) -> dict[str, Any]:
    """고객이 **요청한 것**을 우리 규정에 붙인다 — 여행 코퍼스를 그 요청으로 검색한다.

    ★★**이것이 바꾸는 것은 「근거」이지 「후보 고르기」가 아니다.** 규정 문서는 장소를 담지
      않는다(무엇이 열려 있고 얼마인지는 `places`·`place_catalog` 가 안다). 그래서 여기서 온
      조각은 ①모델이 순서를 짤 때 같이 보는 바탕이 되고 ②초안에 `evidence` 로 실려 나간다.
      **후보를 걸러 내지 않는다** — 규정 문장과 장소 속성을 기계로 맞출 방법이 아직 없다.
      「RAG 를 붙였으니 초안이 규정을 지킨다」고 읽으면 안 된다.

    ★**검색이 실패하거나 0건이면 그 사실을 적는다.** 조용히 넘기면 부르는 쪽은 규정을 보고
      짠 초안과 못 보고 짠 초안을 구별할 수 없다 — 신호 없는 축소다(`RULE.md` §3.2).
      다만 초안 만들기 자체는 멈추지 않는다. 규정은 초안의 **설명**이고, 성립 조건은
      `check_itinerary` 가 따로 본다.
    """
    finder = search
    if finder is None:                      # 부르는 쪽이 안 주면 실제 검색기를 쓴다
        from app.infrastructure.rag.retriever import search_policy as finder  # noqa: PLC0415
    query = (request.preferences.strip()
             or f"{request.city} {request.days}일 {request.party_size}인 여행 일정을 짠다")
    asked = "고객의 말" if request.preferences.strip() else "요청 요약(고객이 아무 말도 안 했다)"
    found: dict[str, Any] = {"query": query, "asked": asked, "scopes": list(PLAN_SCOPES),
                             "hits": 0, "evidence": [], "note": ""}
    try:
        chunks = finder(tenant_id=tenant_id, query=query,
                        allowed_scopes=list(PLAN_SCOPES), top_k=PLAN_RAG_TOP_K)
    except Exception as exc:                # noqa: BLE001 — 어떤 실패든 **말하고** 넘어간다
        found["note"] = f"규정을 못 읽었다({type(exc).__name__}: {exc}) — 초안은 규정을 보지 않고 짰다"
        return found
    found["evidence"] = [
        {"source_type": "policy", "source_id": getattr(chunk, "source_id", ""),
         "scope": getattr(chunk, "scope", ""),
         "score": round(float(getattr(chunk, "score", 0.0)), 4),
         "excerpt": str(getattr(chunk, "content", ""))[:GROUNDING_CHARS]}
        for chunk in chunks or []]
    found["hits"] = len(found["evidence"])
    found["note"] = ("규정 조각을 모델에게 보이고 초안에 근거로 실었다. ★후보를 거르지는 않는다"
                     if found["hits"] else
                     f"scope {list(PLAN_SCOPES)} 에서 0건이다 — 초안은 규정을 보지 않고 짰다")
    return found


def grounding_text(found: Mapping[str, Any]) -> str:
    """모델에게 보일 형태로. 없으면 **빈 문자열**이라 프롬프트에 그 절이 아예 안 붙는다."""
    return "\n".join(f"- ({item['scope']}) {item['excerpt']}"
                        for item in found.get("evidence") or [])


def order_with_model(chat: Any, *, activities: list[Cand], dining: list[Cand],
                     preferences: str, day_label: str,
                     grounding: str = "") -> dict[str, list[str]]:
    """모델에게 **순서만** 받는다. 번호도 우리 후보 키도 받고, 목록에 없는 값은 버린다."""
    listed = activities + dining
    by_number = {str(index): cand.key for index, cand in enumerate(listed, start=1)}
    allowed = {cand.key for cand in listed}
    # ★규정은 **바탕**으로만 붙인다. 모델이 내는 것은 여전히 줄 번호뿐이고, 규정에서
    #   시각·가격·장소를 읽어 오지 않는다 — 그건 우리가 DB 에서 채운다.
    policy = ((f"\n\nOperator policy (background only, do not quote numbers from it):\n{grounding}") if grounding else "")
    user = (f"Day: {day_label}\nTraveller's words: {preferences or '(none)'}{policy}\n\n"
            f"Candidates (use the number at the start of the line):\n{_order_lines(listed)}")
    raw = chat.json(ORDER_SYSTEM, user)
    picked: dict[str, list[str]] = {}
    for field_name in ("activities", "dining"):
        values = raw.get(field_name) if isinstance(raw, dict) else None
        seen: list[str] = []
        for value in values or []:
            token = str(value).strip()
            key = by_number.get(token) if token in by_number else (token if token in allowed else None)
            if key is not None and key not in seen:
                seen.append(key)
        picked[field_name] = seen
    return picked


def _merge(model_keys: list[str], ranked: list[Cand], need: int) -> list[Cand]:
    """모델이 고른 것을 앞에, 모자라면 **규칙 순위**로 채운다."""
    by_key = {cand.key: cand for cand in ranked}
    chosen = [by_key[key] for key in model_keys if key in by_key]
    for cand in ranked:
        if len(chosen) >= need:
            break
        if cand not in chosen:
            chosen.append(cand)
    return chosen[:need]


# ── 시각은 우리가 채운다 ─────────────────────────────────────────
def _at(day: date, clock: time) -> datetime:
    return datetime.combine(day, clock, tzinfo=KST)


def _transfer_minutes(here: Cand, there: Cand) -> tuple[int, str, str]:
    """**이동 시간**(여유 제외). (분, 근거, 수단 표기). ★**추정이다** — 직선거리를 도보 분당 80m 로
    환산하고 실제 경로를 조회하지 않는다(경로 조회 소스가 아직 없다 — 구글 경로 키 자리만 있다).
    ☆`[2026-09-24]` 앞 판은 이 값에 최소 10분을 섞어 「이동 + 여유」를 한 숫자로 냈다. 이제 둘을 나눈다 —
      이동 시간은 이동 항목의 길이가 되고, 여유(`MOVE_BUFFER_MIN`)는 도착 뒤에 둔다."""
    if here.lat is None or there.lat is None:
        return TRANSFER_UNKNOWN_MIN, "좌표를 몰라 기본 이동 시간", "기본 이동 시간"
    meters = distance_m({"latitude": here.lat, "longitude": here.lon},
                        {"latitude": there.lat, "longitude": there.lon})
    walk = walk_minutes(meters)
    if walk > TRANSFER_MAX_MIN:
        return (TRANSFER_MAX_MIN,
                f"직선 {round(meters)}m — 도보 {walk}분이라 대중교통 구간, {TRANSFER_MAX_MIN}분 상한 [추정]",
                "대중교통 권장")
    return walk, f"직선 {round(meters)}m ÷ 도보 80m/분 [추정]", "도보 기준"


def _place_slot(cand: Cand, start: datetime, minutes: int) -> tuple[datetime, datetime]:
    """여는 시각 전이면 여는 시각으로 **민다.** 모르면 그대로 둔다(모름은 판정 대상이 아니다)."""
    hours = cand.attributes.get("hours")
    end = start + timedelta(minutes=minutes)
    if not (isinstance(hours, (list, tuple)) and len(hours) == 2):
        return start, end
    try:
        opens = time(*map(int, str(hours[0]).split(":")))
    except (TypeError, ValueError):
        return start, end
    if start.time() < opens:
        start = _at(start.date(), opens)
        end = start + timedelta(minutes=minutes)
    # ★`[2026-09-24]` 닫는 시각을 넘어도 **앞으로 당기지 않는다.** 앞 판은 시작을 당겨 맞췄는데, 그러면
    #   앞 일정과의 사이(이동 시간 + 여유)를 먹는다 — 이동 항목을 넣으며 다시 밀려 결국 닫는 시각을 넘겼다
    #   (실측: 「18:18 종료인데 18:00 에 닫는다」). 넘으면 그대로 두고 판정(`after_closing`)이 장소를 바꾸게 한다.
    return start, end


def build_day(day: date, activities: list[Cand], dining: list[Cand], *, seq_from: int
              ) -> list[dict[str, Any]]:
    """활동·식사를 하루에 늘어놓는다. **시각은 전부 여기서 나온다 — 모델이 아니다.**"""
    plan: list[tuple[Cand, str, int]] = []
    if activities:
        plan.append((activities[0], "activity", ACTIVITY_MIN))
    if dining:
        plan.append((dining[0], "dining", MEAL_MIN))
    if len(activities) > 1:
        plan.append((activities[1], "activity", ACTIVITY_MIN))
    if len(dining) > 1:
        plan.append((dining[1], "dining", MEAL_MIN))
    for cand in activities[2:]:
        plan.insert(len(plan) - 1 if len(dining) > 1 else len(plan), (cand, "activity", ACTIVITY_MIN))

    items: list[dict[str, Any]] = []
    cursor = _at(day, DAY_START)
    previous: Cand | None = None
    for index, (cand, kind, minutes) in enumerate(plan):
        basis = "하루 시작"
        if previous is not None:
            # ★이동 시간 + 도착 뒤 여유를 비워 둔다 — 그 자리에 이동 항목이 들어간다(`add_moves`)
            travel, basis, _ = _transfer_minutes(previous, cand)
            cursor = cursor + timedelta(minutes=travel + MOVE_BUFFER_MIN)
        if kind == "dining":
            floor = LUNCH_FROM if not any(it["kind"] == "dining" for it in items) else DINNER_FROM
            cursor = max(cursor, _at(day, floor))
        start, end = _place_slot(cand, cursor, minutes)
        items.append({"seq": seq_from + index, "kind": kind, "title": cand.name,
                      "place": cand.key, "starts_at": start, "ends_at": end,
                      # ★**어느 날의 항목인가**를 적어 둔다. 고치다 자정을 넘기면 `starts_at.date()`
                      #   가 바뀌어 「같은 날」을 못 세므로, 계획한 날을 값으로 들고 간다.
                      "detail": {"planner": {"origin": cand.origin, "transfer_basis": basis,
                                             "district": cand.district, "day": day.isoformat()}}})
        cursor, previous = end, cand
    return items


# ── 이동 항목 — 출발 시각을 거꾸로 잡는다 ────────────────────────
def add_moves(items: list[dict[str, Any]], places: Mapping[str, Cand]
              ) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    """같은 날 이어지는 두 장소 사이에 **이동 항목**을 넣는다. (항목들, routes, 민 내역).

    ★`[2026-09-24 사용자 지시]` 출발 = **다음 일정 시작 − 이동 시간 − 여유**(`MOVE_BUFFER_MIN`).
      이동 알림은 이 출발 시각에 간다(`trip_reminders`) — 「N분 전」을 따로 붙이지 않는다.
      앞 판은 이동 항목을 만들지 않아 **생성기가 짠 여행에는 이동 알림이 아예 없었다.**
    ★앞 장소가 끝난 뒤 이동 + 여유를 둘 자리가 모자라면(고치는 중 장소가 바뀐 경우) 다음 일정부터
      **그날 안에서 뒤로 민다** — 민 내역을 돌려준다. 하루 마감을 넘기는지는 부르는 쪽이 본다.
    ★이동 시간은 `_transfer_minutes` 의 **추정**이다. 경로 정의의 `uses` 는 비워 둔다 — 어떤 노선을
      타는지 우리가 모르기 때문이다(지어내지 않는다). 그래서 감시는 이 구간의 노선 사건을 보지 않는다.
    """
    ordered = sorted(items, key=lambda it: (_planned_day(it), it["starts_at"], it["seq"]))
    out: list[dict[str, Any]] = []
    routes: dict[str, Any] = {}
    notes: list[str] = []
    for index, item in enumerate(ordered):
        previous = ordered[index - 1] if index else None
        if previous is not None and _planned_day(previous) == _planned_day(item):
            travel, basis, label = _transfer_minutes(places[previous["place"]], places[item["place"]])
            need = travel + MOVE_BUFFER_MIN
            end = previous["ends_at"] or previous["starts_at"]
            free = int((item["starts_at"] - end).total_seconds() // 60)
            if free < need:
                # ★번호(seq)가 아니라 **시각**으로 민다 — 고치는 중 민 항목은 번호 순서와 시각 순서가
                #   어긋날 수 있다(실측: 번호로 밀었더니 저녁 식당과 그 앞 이동이 겹쳤다).
                pivot, day = item["starts_at"], _planned_day(item)
                for later in items:
                    if _planned_day(later) == day and later["starts_at"] >= pivot:
                        later["starts_at"] += timedelta(minutes=need - free)
                        if later["ends_at"]:
                            later["ends_at"] += timedelta(minutes=need - free)
                notes.append(f"move({item['seq']}): 이동 {travel}분 + 여유 {MOVE_BUFFER_MIN}분을 두려고 "
                             f"{item['title']} 부터 {need - free}분 뒤로 밀었다")
            leave = item["starts_at"] - timedelta(minutes=need)
            key = f"move-{len(routes) + 1}"
            routes[key] = {"planned": "estimate",
                           "options": [{"id": "estimate", "label": label, "eta_min": travel, "uses": []}]}
            out.append({"seq": 0, "kind": "mobility", "title": f"{previous['title']} → {item['title']}",
                        "place": None, "route": key, "starts_at": leave,
                        "ends_at": leave + timedelta(minutes=travel),
                        "detail": {"planner": {"day": _planned_day(item), "transfer_basis": basis,
                                               "travel_min": travel, "buffer_min": MOVE_BUFFER_MIN,
                                               "leave_rule": "다음 일정 시작 − 이동 시간 − 여유"}}})
        out.append(item)
    for number, item in enumerate(out, start=1):
        item["seq"] = number
    return out, routes, notes


# ── 밀도 목표에 맞춘 하루 (설문 16번) ─────────────────────────────
def density_target(constraints: Mapping[str, Any]) -> float | None:
    """여행 제약의 밀도 목표(0~1). 없으면 None — 그때는 하루 활동 수를 기본값으로 둔다.
    ★목표를 읽는 규칙은 `measure_density` 와 같다(직접 준 `target_density` 가 이기고, 아니면 `level`)."""
    density = constraints.get("density")
    if not isinstance(density, Mapping):
        return None
    if density.get("target_density") is not None:
        return float(density["target_density"])
    if density.get("level") is None:
        return None
    from app.core.settings import get_guardrails

    return float(get_guardrails().get("travel.density.targets")[density["level"]])


def _parts_of(items: list[dict[str, Any]], places: Mapping[str, Cand],
              routes: Mapping[str, Any]) -> list[Part]:
    return [Part(seq=item["seq"], kind=item["kind"], title=item["title"],
                 starts_at=item["starts_at"], ends_at=item["ends_at"],
                 place=places[item["place"]].for_check() if item.get("place") else None,
                 route=routes.get(str(item.get("route"))) if item.get("route") else None,
                 detail=item["detail"])
            for item in items]


def fit_day(day: date, activities: list[Cand], dining: list[Cand], *, places: Mapping[str, Cand],
            constraints: Mapping[str, Any], seq_from: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """★밀도 목표 안에서 **활동을 가장 많이** 넣은 하루. (항목들, 잰 결과).

    곳 수를 표로 박지 않는다 — 활동 n 곳으로 하루를 **실제로 짜고**(이동 항목 포함) `measure_density` 로
    재서, 목표를 넘지 않고 하루 마감(`DAY_END`) 안에 끝나는 가장 큰 n 을 고른다. 거리가 가까운 날은 더
    들어가고 먼 날은 덜 들어간다. ★하루 창이 없어 **잴 수 없으면** 기본 수(`ACTIVITIES_PER_DAY`)로 짜고
    그렇다고 적는다 — 못 잰 것을 맞췄다고 하지 않는다.
    """
    top = min(MAX_ACTIVITIES_PER_DAY, len(activities))
    tried: list[dict[str, Any]] = []
    for count in range(top, MIN_ACTIVITIES_PER_DAY - 1, -1):
        items = build_day(day, activities[:count], dining, seq_from=seq_from)
        trial, routes, _ = add_moves(copy.deepcopy(items), places)
        measured = measure_density(_parts_of(trial, places, routes), constraints)
        entry = next((row for row in measured["density"] if row["date"] == day.isoformat()), None)
        if entry is None or entry["status"] == "unmeasurable":
            fallback = min(ACTIVITIES_PER_DAY, len(activities))
            return (build_day(day, activities[:fallback], dining, seq_from=seq_from),
                    {"date": day.isoformat(), "activities": fallback, "status": "unmeasurable",
                     "reasons": (entry or {}).get("reasons") or ["그날 하루 창이 없다"],
                     "note": f"밀도를 잴 수 없어 기본 {fallback}곳으로 짰다"})
        ends = max((item["ends_at"] or item["starts_at"]) for item in trial)
        # ★밀도만 보지 않는다 — 이동을 넣은 하루가 **같은 판정기**(영업시간·겹침·이동 시간)도 통과해야 한다
        broken = check_itinerary(_parts_of(trial, places, routes), constraints=constraints)
        tried.append({"activities": count, "actual_density": round(entry["actual_density"], 3),
                      "violations": [v.code for v in broken]})
        if entry["status"] == "ok" and not broken and ends <= _at(day, DAY_END):
            return items, {"date": day.isoformat(), "activities": count, "status": "ok",
                           "candidates": len(activities),        # ★이날 넣어 볼 수 있던 활동 후보 수
                           "target_density": entry["target_density"],
                           "actual_density": round(entry["actual_density"], 3), "tried": tried}
    # ★하한으로도 목표를 넘는다 — 빈 하루를 내지 않고 하한으로 짜고 넘는다고 적는다(밀도는 관측값, D-019)
    items = build_day(day, activities[:MIN_ACTIVITIES_PER_DAY], dining, seq_from=seq_from)
    return items, {"date": day.isoformat(), "activities": MIN_ACTIVITIES_PER_DAY, "status": "exceeded",
                   "target_density": tried[-1:] and entry["target_density"], "tried": tried,
                   "note": f"활동 {MIN_ACTIVITIES_PER_DAY}곳으로도 목표를 넘는다 — 식사·이동만으로 찬다"}


# ── 고쳐서 다시 판정한다 ─────────────────────────────────────────
def _planned_day(item: dict[str, Any]) -> str:
    return str(((item.get("detail") or {}).get("planner") or {}).get("day") or "")


def _shift(items: list[dict[str, Any]], from_seq: int, minutes: int) -> None:
    """그 항목부터 **같은 날 안에서** 뒤로 민다. ★날은 `detail.planner.day` 로 본다 —
    자정을 넘긴 뒤에는 `starts_at.date()` 가 그 날을 더 이상 가리키지 않는다."""
    day = next((_planned_day(it) for it in items if it["seq"] == from_seq), "")
    for item in items:
        if item["seq"] >= from_seq and _planned_day(item) == day:
            item["starts_at"] += timedelta(minutes=minutes)
            if item["ends_at"]:
                item["ends_at"] += timedelta(minutes=minutes)


def _swap_place(item: dict[str, Any], spares: list[Cand], used: set[str],
                accept: Callable[[Cand], bool], places: dict[str, Cand]) -> Cand | None:
    """★바꿔 넣은 후보를 **`places` 에 바로 등록한다** — 뒤따르는 판정·집계가 같은 칸을 본다."""
    for cand in spares:
        if cand.key in used or cand.kind != item["kind"] or not accept(cand):
            continue
        item["place"], item["title"] = cand.key, cand.name
        item["detail"].setdefault("planner", {})["origin"] = cand.origin
        item["detail"]["planner"]["swapped_in"] = True
        used.add(cand.key)
        places[cand.key] = cand
        return cand
    return None


def repair(items: list[dict[str, Any]], places: dict[str, Cand], violations: list[Violation],
           *, spares: list[Cand], used: set[str], constraints: Mapping[str, Any],
           party_size: int) -> list[str]:
    """위반 하나하나에 **정해진 고침**을 건다. 고친 내역을 돌려준다(빈 목록 = 못 고쳤다)."""
    done: list[str] = []
    by_seq = {item["seq"]: item for item in items}
    for violation in violations:
        code, seqs = violation.code, violation.seq
        if code == "time_order" and seqs[0] in by_seq:
            item = by_seq[seqs[0]]
            item["ends_at"] = item["starts_at"] + timedelta(minutes=MEAL_MIN)
            done.append(f"{code}({seqs[0]}): 끝나는 시각을 시작 뒤로 다시 잡았다")
        elif code == "overlap" and len(seqs) == 2 and all(seq in by_seq for seq in seqs):
            earlier, later = by_seq[seqs[0]], by_seq[seqs[1]]
            end = earlier["ends_at"] or earlier["starts_at"]
            gap = int((end - later["starts_at"]).total_seconds() // 60) + TRANSFER_MIN_MIN
            _shift(items, later["seq"], max(TRANSFER_MIN_MIN, gap))
            done.append(f"{code}({seqs[1]}): {max(TRANSFER_MIN_MIN, gap)}분 뒤로 밀었다")
        elif code == "no_transfer_time" and len(seqs) == 2 and seqs[1] in by_seq:
            _shift(items, seqs[1], TRANSFER_UNKNOWN_MIN)
            done.append(f"{code}({seqs[1]}): 이동 여유 {TRANSFER_UNKNOWN_MIN}분을 넣었다")
        elif code in ("before_opening", "break_time") and seqs[0] in by_seq:
            item = by_seq[seqs[0]]
            attributes = places[item["place"]].attributes
            target = (attributes.get("hours") or ["", ""])[0] if code == "before_opening" \
                else (attributes.get("break") or ["", ""])[1]
            try:
                clock = time(*map(int, str(target).split(":")))
            except (TypeError, ValueError):
                continue
            minutes = int((_at(item["starts_at"].date(), clock)
                           - item["starts_at"]).total_seconds() // 60)
            if minutes <= 0:
                continue
            _shift(items, item["seq"], minutes)
            done.append(f"{code}({seqs[0]}): {target} 뒤로 {minutes}분 밀었다")
        elif code == "after_closing" and seqs[0] in by_seq:
            item = by_seq[seqs[0]]
            swapped = _swap_place(item, spares, used,
                                  lambda cand: "hours" not in cand.attributes, places)
            if swapped is None:
                return done
            done.append(f"{code}({seqs[0]}): {swapped.name} 로 바꿨다(닫는 시각을 넘었다)")
        elif code == "payment_not_accepted" and seqs[0] in by_seq:
            wanted = str(constraints.get("payment"))
            item = by_seq[seqs[0]]
            swapped = _swap_place(
                item, spares, used,
                lambda cand: wanted in [str(v) for v in (cand.attributes.get("payment") or [])]
                or not cand.attributes.get("payment"), places)
            if swapped is None:
                return done
            done.append(f"{code}({seqs[0]}): {swapped.name} 로 바꿨다(결제 조건)")
        elif code == "over_budget":
            # ★가장 비싼 항목을 **더 싸거나 가격을 모르는** 후보로 바꾼다. 없으면 못 고친다.
            priced = sorted((item for item in items
                             if (places[item["place"]].attributes.get("price_krw"))),
                            key=lambda it: -int(places[it["place"]].attributes["price_krw"]))
            if not priced:
                return done
            item = priced[0]
            ceiling = int(places[item["place"]].attributes["price_krw"])
            swapped = _swap_place(item, spares, used,
                                  lambda cand: int(cand.attributes.get("price_krw") or 0) < ceiling,
                                  places)
            if swapped is None:
                return done
            done.append(f"{code}: {item['title']} 로 바꿨다(더 싼 곳)")
        else:
            return done                    # ★모르는 위반은 고친 척하지 않는다
    return done


# ── 초안 ────────────────────────────────────────────────────────
@dataclass
class PlanDraft:
    title: str
    locale: str | None
    party_size: int
    constraints: dict[str, Any]
    places: list[dict[str, Any]]
    items: list[dict[str, Any]]
    routes: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"title": self.title, "locale": self.locale, "party_size": self.party_size,
                "constraints": self.constraints, "places": self.places,
                "items": [{**item, "starts_at": item["starts_at"].isoformat(),
                           "ends_at": item["ends_at"].isoformat() if item["ends_at"] else None}
                          for item in self.items],
                "routes": self.routes}

    def as_create_body(self, *, request_id: str, customer_id: Any) -> dict[str, Any]:
        """`POST /v1/trips` 가 받는 그대로. ★**등록은 같은 판정기를 다시 지난다** —
        여기서 통과했다고 등록이 건너뛰지 않는다."""
        return {"request_id": request_id, "customer_id": str(customer_id), **self.as_dict()}


@dataclass
class PlanOutcome:
    draft: PlanDraft
    planner: dict[str, Any]
    candidates: dict[str, Any]
    checks: dict[str, Any]
    coverage: dict[str, Any]
    calls: dict[str, int]
    #: ★`[2026-09-22]` 이 요청을 **우리 규정에 붙인 결과**. `evidence` 가 초안과 함께 나가고,
    #:  같은 조각을 모델이 순서를 짤 때 바탕으로 봤다. **후보를 거르지는 않는다**
    #:  (`ground_request` 의 설명). 0건이거나 못 읽었으면 `note` 가 그렇게 말한다.
    rag: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"draft": self.draft.as_dict(), "planner": self.planner,
                "candidates": self.candidates, "checks": self.checks,
                "coverage": self.coverage, "calls": self.calls, "rag": self.rag}


def _coverage(items: list[dict[str, Any]], places: dict[str, Cand]) -> dict[str, Any]:
    """★**판정이 실제로 본 칸이 몇이나 되는지** 분자/분모로 적는다. 모르는 칸은 통과가 아니라
    「판정하지 않음」이고, 그 사실을 숨기면 초안이 실제보다 안전해 보인다."""
    items = [item for item in items if item.get("place")]      # 이동 항목은 장소 칸이 없다
    total = len(items)
    with_hours = sum(1 for item in items if "hours" in places[item["place"]].attributes)
    with_price = sum(1 for item in items if "price_krw" in places[item["place"]].attributes)
    with_district = sum(1 for item in items if places[item["place"]].district)
    return {"items": total,
            "hours_known": with_hours, "price_known": with_price, "district_known": with_district,
            "note": (f"영업시간 {with_hours}/{total} · 가격 {with_price}/{total} · "
                     f"구 {with_district}/{total} 만 판정 대상이다. 나머지 칸은 "
                     f"`check_itinerary` 가 보지 않는다(모름은 위반이 아니다)")}


def plan_trip(*, conn, tenant_id: str, request: PlanRequest, chat: Any | None = None,
              tour_api: Any | None = None,
              search: Callable[..., Any] | None = None) -> PlanOutcome:
    """요청 → 판정을 통과한 초안. 못 내면 `PlanRefused`."""
    request.validate()
    # ★`[2026-09-24]` 설문(`constraints.survey`)을 **등록과 같은 함수로** 먼저 적용한다 — 16번 여유가
    #   밀도 목표가 되고, 생성기는 그 목표에 맞춰 하루 활동 수를 정한다(`fit_day`). 등록이 다시 적용해도
    #   이미 채운 목표는 그대로다.
    from .survey import apply_survey

    try:
        request = replace(request, constraints=apply_survey(
            request.constraints, (request.start_date + timedelta(days=i) for i in range(request.days))))
    except ValidationError as exc:
        raise PlanRefused("invalid_survey", "constraints.survey 가 설문 계약과 다르다",
                          problems=[{"field": ".".join(str(p) for p in e["loc"]), "reason": e["msg"]}
                                    for e in exc.errors()]) from None
    target = density_target(request.constraints)
    per_day = MAX_ACTIVITIES_PER_DAY if target is not None else ACTIVITIES_PER_DAY
    floor_per_day = MIN_ACTIVITIES_PER_DAY if target is not None else ACTIVITIES_PER_DAY
    pref = preference_profile(request.preferences)
    calls = {"tour_api": 0}
    # ★요청을 **우리 규정에 붙인다**(RAG). 근거로 실어 내보내고 모델에게도 바탕으로 보인다.
    #   ★후보를 거르지는 않는다 — `ground_request` 의 설명을 그대로 읽는다.
    rag = ground_request(tenant_id=tenant_id, request=request, search=search)
    grounding = grounding_text(rag)

    pool = load_candidates(conn, tenant_id=tenant_id)
    if tour_api is not None and not any(cand.origin != "places" for cand in pool):
        # ★카탈로그가 비었을 때만 바깥에 나간다. 하루 한도가 있다.
        pool, calls["tour_api"] = fill_from_tour_api(pool, source=tour_api)

    ranked = rank_candidates(pool, pref)
    activities = [cand for cand in ranked if cand.kind == "activity"]
    dining = [cand for cand in ranked if cand.kind == "dining"]
    need_act, need_din = floor_per_day * request.days, DINING_PER_DAY * request.days
    if len(activities) < need_act or len(dining) < need_din:
        raise PlanRefused(
            "not_enough_candidates",
            f"{request.days}일치를 짜려면 활동 {need_act}곳·식사 {need_din}곳이 필요한데 "
            f"활동 {len(activities)}곳·식사 {len(dining)}곳뿐이다",
            need={"activity": need_act, "dining": need_din},
            have={"activity": len(activities), "dining": len(dining)},
            pool_before_preference=len(pool),
            preference=pref.as_dict(),
            remedy="장소 카탈로그를 더 받거나(TourAPI 동기화) 선호 조건을 줄인다")

    mode, note = "rules", "모델을 쓰지 않았다"
    if chat is not None:
        mode, note = "llm", ""
    pools = pick_day_pools(activities, dining, request.days)

    items: list[dict[str, Any]] = []
    chosen: dict[str, Cand] = {}
    used: set[str] = set()
    model_calls, from_model = 0, 0        # ★몇 번 불렀고 **그중 몇 개가 실제로 쓰였나**
    fits: list[dict[str, Any]] = []       # ★하루마다 밀도 목표에 맞춘 결과(설문 16번)
    want = 0
    for index, (day_acts, day_dine) in enumerate(pools):
        # ★**같은 곳을 이틀 넣지 않는다.** 하루치 후보에서 이미 쓴 것을 빼고, 모자라면 전체
        #   순위에서 아직 안 쓴 것으로 채운다.
        day_acts = _available(day_acts, activities, used, per_day)
        day_dine = _available(day_dine, dining, used, DINING_PER_DAY)
        day = request.start_date + timedelta(days=index)
        picks = {"activities": [], "dining": []}
        if chat is not None:
            try:
                picks = order_with_model(chat, activities=day_acts, dining=day_dine,
                                         preferences=request.preferences,
                                         day_label=f"{day.isoformat()} (day {index + 1})",
                                         grounding=grounding)
                model_calls += 1
            except Exception as exc:                      # noqa: BLE001 — 어떤 실패든 규칙으로 간다
                mode, note = "rules", f"모델을 부르지 못해 규칙으로 짰다: {type(exc).__name__}: {exc}"
                chat = None
        day_act = _merge(picks["activities"], day_acts, per_day)
        day_din = _merge(picks["dining"], day_dine, DINING_PER_DAY)
        if target is not None:
            day_items, fit = fit_day(day, day_act, day_din, places={c.key: c for c in day_act + day_din},
                                     constraints=request.constraints, seq_from=len(items) + 1)
            day_act = day_act[:fit["activities"]]
            fits.append(fit)
        else:
            day_items = build_day(day, day_act, day_din, seq_from=len(items) + 1)
        from_model += sum(1 for cand in day_act if cand.key in picks["activities"])
        from_model += sum(1 for cand in day_din if cand.key in picks["dining"])
        # ★실제로 넣은 것만 「썼다」로 센다 — 목표 때문에 빠진 후보는 다른 날이 쓸 수 있다
        used.update(cand.key for cand in day_act + day_din)
        for cand in day_act + day_din:
            chosen[cand.key] = cand
        want += len(day_act) + len(day_din)
        items += day_items

    # ★★**조용히 짧아지지 않게 센다.** 후보가 모자라면 `_merge` 가 자리를 덜 채우고, 그러면
    #   「3일 일정」이라며 항목이 덜 든 초안이 나간다 — 아무 신호 없이. 위에서 총량을 확인했으니
    #   여기 걸리면 그건 **우리 쪽 결함**이고, 그때도 조용히 넘기지 않는다.
    if len(items) != want or want < request.days * (floor_per_day + DINING_PER_DAY):
        raise PlanRefused("plan_short",
                          f"{request.days}일치는 항목 {want}개여야 하는데 {len(items)}개만 짜였다",
                          have=len(items), need=want,
                          remedy="후보를 더 받거나 선호 조건을 줄인다")

    spares = [cand for cand in ranked if cand.key not in used]
    rounds, fixed = 0, []
    violations = _check(items, chosen, request)
    while violations and rounds < MAX_REPAIR_ROUNDS:
        rounds += 1
        applied = repair(items, chosen, violations, spares=spares, used=used,
                         constraints=request.constraints, party_size=request.party_size)
        for cand in spares:
            if cand.key in used:
                chosen.setdefault(cand.key, cand)
        fixed += applied
        if not applied:
            break
        violations = _check(items, chosen, request)
    if violations:
        raise PlanRefused(
            "plan_infeasible",
            "초안을 짰지만 판정을 통과시키지 못했다: "
            + " / ".join(violation.reason for violation in violations),
            violations=[violation.as_dict() for violation in violations],
            repair_rounds=rounds, repairs_applied=fixed,
            remedy="완화 조건을 하나 풀거나(예산·결제 조건) 후보를 더 받는다")
    _refuse_overflow(items, rounds=rounds, fixed=fixed, why="고치다 보니")
    # ★이동 항목을 넣고(출발 = 다음 일정 시작 − 이동 − 여유) **같은 판정기로 한 번 더** 본다 —
    #   자리가 모자라 민 항목이 영업시간을 넘길 수 있다. 여기서 걸리면 고친 척하지 않고 거절한다.
    items, routes, moved = add_moves(items, chosen)
    fixed += moved
    violations = _check(items, chosen, request, routes)
    if violations:
        raise PlanRefused(
            "plan_infeasible",
            "이동 시간을 넣고 나니 판정을 통과하지 못했다: "
            + " / ".join(violation.reason for violation in violations),
            violations=[violation.as_dict() for violation in violations],
            repair_rounds=rounds, repairs_applied=fixed,
            remedy="하루 항목을 줄이거나 가까운 장소로 바꾼다")
    _refuse_overflow(items, rounds=rounds, fixed=fixed, why="이동 시간을 넣고 나니")

    draft = PlanDraft(
        title=request.title or f"서울 {request.days}일 여행 ({request.start_date.isoformat()})",
        locale=request.locale, party_size=request.party_size,
        constraints=dict(request.constraints),
        places=[chosen[key].as_place() for key in
                sorted({item["place"] for item in items if item.get("place")}, key=lambda k: str(k))],
        items=items, routes=routes)
    if mode == "llm" and from_model == 0:
        # ★★모델을 부르긴 했는데 **쓴 것이 하나도 없다.** 그래도 `llm` 이라고 적으면 조용한
        #   폴백이다(`RULE.md` §3.2) — 실제로 gemma4:12b 가 줄 번호를 내서 이 상태가 났었다.
        mode = "rules"
        note = (f"모델을 {model_calls}회 불렀지만 낸 값이 하나도 후보 목록에 없어 "
                f"규칙 순위로 짰다")
    calls["model"] = model_calls
    return PlanOutcome(
        draft=draft,
        planner={"mode": mode, "note": note or "모델이 순서를 짰다(시각·좌표·가격은 서버가 채웠다)",
                 "model_calls": model_calls,
                 # ★**분자/분모** — 일정에 들어간 항목 중 몇 개를 모델이 골랐나.
                 "from_model": from_model,
                 "items": sum(1 for item in items if item.get("place")),
                 "preference": pref.as_dict(),
                 # ★설문 16번 → 밀도 목표 → 하루 활동 수. 목표가 없으면 기본 수로 짰다고 적는다
                 "density": ({"target_density": target, "days": fits} if target is not None else
                             {"target_density": None,
                              "note": f"밀도 목표가 없어 하루 활동 {ACTIVITIES_PER_DAY}곳으로 짰다"})},
        candidates={"pool": len(pool), "after_preference": len(ranked),
                    "activity": len(activities), "dining": len(dining),
                    "chosen": len({item["place"] for item in items if item.get("place")}),
                    "by_source": _count_by(chosen.values(), "origin")},
        checks={"rounds": rounds, "repairs": fixed, "violations": []},
        coverage=_coverage(items, chosen), calls=calls, rag=rag)


def _refuse_overflow(items: list[dict[str, Any]], *, rounds: int, fixed: list[str], why: str) -> None:
    """★★`check_itinerary` 는 **하루가 몇 시에 끝나야 하는지 모른다** — 그건 우리 상품의 약속이지
    일정의 성립 조건이 아니다. 고치는 과정이나 이동 자리를 내는 과정에서 뒤로 민 항목이 한밤중으로
    넘어갈 수 있으므로 따로 본다. 넘으면 「고쳤다」고 하지 않고 거절한다."""
    overflow = [item for item in items
                if (item["ends_at"] or item["starts_at"])
                > _at(date.fromisoformat(_planned_day(item)), DAY_END)]
    if overflow:
        raise PlanRefused(
            "day_overflow",
            f"{why} {len(overflow)}개 항목이 하루 마감({DAY_END.strftime('%H:%M')})을 넘었다: "
            + ", ".join(f"{item['title']}"
                        f"({(item['ends_at'] or item['starts_at']).strftime('%m-%d %H:%M')})"
                        for item in overflow),
            items=[item["seq"] for item in overflow],
            repair_rounds=rounds, repairs_applied=fixed,
            remedy="하루 항목을 줄이거나 시작 시각을 앞당길 수 있는 장소로 바꾼다")


def _available(shortlist: list[Cand], everything: list[Cand], used: set[str],
               need: int) -> list[Cand]:
    """아직 안 쓴 후보만. 모자라면 전체 순위에서 잇는다."""
    free = [cand for cand in shortlist if cand.key not in used]
    if len(free) >= max(need, 1):
        return free
    for cand in everything:
        if cand.key in used or cand in free:
            continue
        free.append(cand)
        if len(free) >= SHORTLIST_PER_DAY:
            break
    return free


def _count_by(candidates: Iterable[Cand], attribute: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for cand in candidates:
        counts[getattr(cand, attribute)] = counts.get(getattr(cand, attribute), 0) + 1
    return counts


def _check(items: list[dict[str, Any]], places: dict[str, Cand],
           request: PlanRequest, routes: Mapping[str, Any] | None = None) -> list[Violation]:
    """★**등록이 쓰는 것과 같은 판정기다.** 여기에 따로 만든 판정은 없다."""
    return check_itinerary(
        [Part(seq=item["seq"], kind=item["kind"], title=item["title"],
              starts_at=item["starts_at"], ends_at=item["ends_at"],
              place=places[item["place"]].for_check() if item.get("place") else None,
              route=(routes or {}).get(str(item.get("route"))) if item.get("route") else None,
              detail=item["detail"])
         for item in items],
        constraints=request.constraints, party_size=request.party_size)


__all__ = ["Cand", "PlanDraft", "PlanOutcome", "PlanRefused", "PlanRequest", "Preference",
           "add_moves", "build_day", "density_target", "fit_day", "ground_request", "grounding_text", "load_candidates",
           "order_with_model", "plan_trip", "preference_profile", "rank_candidates", "repair"]
