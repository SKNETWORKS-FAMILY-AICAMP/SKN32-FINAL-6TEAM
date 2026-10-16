# -*- coding: utf-8 -*-
"""Lodging Team — 숙소를 찾아 주고, 이미 잡은 숙소의 위치 · 정보를 찾아 준다. `[2026-10-07]`

흐름(`lodging.assist`): 모델 **한 번**이 문장(+ 여행 일정 요약)을 고정된 구조로 옮긴다 → 서버가 검증한다 →
빠진 값이 있으면 되묻고, 없으면 도구로 찾는다 → 받은 값으로 답을 쓴다.

- 모델은 **해석만** 한다. 검색 · 고르기 · 가격 · 링크는 전부 도구(`read.stay_search` · `read.stay_detail`)가 준 값이다.
- 문장 규칙(키워드 맞추기 · 정규식)으로 뜻을 가르지 않는다 — 찾기 / 내 숙소 / 예약 상태 / 모름을 모델이 고른다.
- 예약 · 결제는 하지 않는다. 마이리얼트립 숙소 페이지 링크만 준다. 일정에 저장하지도 않는다(아직 정하지 않았다).
- ★되묻기는 `waiting` 이 아니라 **답(`completed`)으로** 한다. Case 를 다시 깨우는 입구(`POST /v1/cases/{id}/messages`)가
  고객이 보낸 글을 팀에 넘기지 않아(`Controller.resume` 은 토큰만 받고, 팀은 처음 문장을 다시 받는다) `waiting` 으로 두면
  같은 질문만 되풀이된다. 고객이 조건을 채워 다시 보내면 새 요청으로 처리된다.
- `lodging.status` 는 전과 같다 — 잠긴 예약을 조회만 한다.
- `[2026-10-10]` **비교**: 찾기는 booking 모듈(`read.booking_search_stays`)을 한 번 부른다 — 마이리얼트립 목록 · 구글 호텔(SerpApi 한국 설정)
  목록 · 다른 곳 링크를 함께 받는다. 상세(`read.stay_detail`)는 보여 줄 곳만 이 팀이 부른다. 마이리얼트립 목록 아래에
  구글 호텔 쪽 숙소(호텔만, 이미 보인 이름은 빼고) 최대 `GOOGLE_SHOWN` 곳을 따로 보여 준다. 두 소스의 숙소 이름이 달라(한국어 · 영어 ·
  지점 표기) 같은 숙소로 묶지는 않는다. 끝에 「같은 조건으로 다른 곳에서 보기」 링크(booking 모듈이 정한 곳 — 부킹닷컴 · 익스피디아, 국내면 여기어때 · 야놀자, 해외면 호텔스닷컴 · 에어비앤비)를 붙인다. 가격은 조회 시점 참고값이다.
- `[2026-10-10]` **일정 반영**(팀 피드백 4): Case 에 여행이 붙어 있으면 그 숙박 기간(체크인~체크아웃 날)의 일정 장소 좌표로
  가운데를 잡는다(그 기간에 좌표 있는 장소가 없으면 일정 전체). 마이리얼트립 줄에는 상세 좌표로 그 가운데까지 거리를 붙이고(순서는
  마이리얼트립 그대로 — 더 부르지 않으려고), 구글 호텔 줄은 목록에 좌표가 오므로 **가까운 순**으로 고른다. 장소가 `SPREAD_KM` 보다
  넓게 흩어져 있으면(여러 도시 등) 가운데가 뜻이 없어 거리를 쓰지 않고 그렇다고 적는다. 거리는 직선거리다(이동 시간 아님).
- `[2026-10-11]` **일정 숙소 항목(`lodging.itinerary`)** — 팀장 안내(「lodging.itinerary 로 일감 들어갈 거에요」)와 사용자 결정에 따라
  식당 · 활동 팀과 같은 공용 부품(`_shared/itinerary_team.ItineraryWork`)을 쓴다. 여행 Case 가 **숙소 항목**(`subject_ref.part_id`)을 가리키면
  이 일감이 된다. 문장을 모델로 해석하지 않고 항목 · 여행에서 읽는다(체크인 = 항목 시작 날, 체크아웃 = 항목 끝 날, 인원 = 여행 인원,
  지역 = 항목 `detail.area` → 장소 `district` → 장소 이름).
  - 이미 예약한 숙소(`booking_id` · `locked` · `detail.booked`)는 바꾸지 않는다(사용자 결정 10-11 「이미 예약한 숙소는 바꿀 일이 없다」).
  - 「바꿔 줘」 = 보여 준 후보가 마음에 안 든다 → **새 후보 3곳**(앞서 보여 준 곳 · 지금 항목은 뺀다). 다시 말하면 또 새 3곳.
    `[2026-10-12]` 식당 · 활동과 같은 모양으로 내보낸다 — 후보는 항목의 「다른 안」(`detail.alternates`, `applied_record` 와 같은 칸 + 가격 ·
    평점 · 링크)이고 답은 한 줄(「○○ 대신 갈 수 있는 곳이에요 — 1) … 고르시면 바꿀게요」). 숙소는 그대로 두고 상세만 바꾼
    `itinerary.apply`(고객 요청, 판정 문 없음) — 일정 판 +1 · 알림 1번. 보여 준 곳은 `detail.shown` 에 남긴다.
  - 고르면(`request.choice` = 후보 `key`) 그 숙소로 항목을 바꾼다 — 원래 숙소는 「다른 안」으로. 우리 후보는 MCP 소스에서 왔고 장소 표(DB)에 없어
    `place_id` 를 비우고 이름 · 좌표 · 링크를 `detail.chosen` 에 둔다(예약 전 `detail.booked = False`).
  - 새 후보가 없으면 목록을 더 넓게(`ALTERNATE_SIZES`) 받아 다시 찾고, 그래도 없으면 그렇다고 답한다(다른 곳 링크와 함께).
  - 일정에 숙소 항목이 생기는 것은 우리 에이전트가 반영될 때다(사용자 10-11) — 그 전까지 이 길은 가짜 일정 시험으로만 돈다.
  - `[2026-10-12]` **고를 때 가격 재확인** — 마이리얼트립 후보를 고르면 그 숙소 상세(`read.stay_detail`)를 한 번 더 읽어 1박 값을 다시 본다.
    목록 1박(`price`)과 상세 1박 평균(`averagePrice`)은 같은 기준(세금 전)이다 — ☆10-12 18:22 playdata 명동 3박 두 곳 모두 같았다
    (`scripts/probe_price_basis.py`). 바뀌면 새 값으로 바꾸고 답에 적는다. 그 날짜에 객실이 없으면 바꾸지 않고 그렇다고 답한다.
    상세를 못 읽으면(429 등) 바꾸되 「다시 확인하지 못했다」고 적는다. 구글 호텔 후보는 한 곳만 다시 볼 도구가 없어 확인하지 않고 그렇게 적는다.
- 설문(`constraints.survey`)에는 숙소 문항(예산 · 숙소 유형)이 없다(`components/planning/survey.py` 2026-09-24.v1). 그래서 설문은
  아직 숙소 고르기에 쓰지 않는다 — 문항이 생기면 연결한다.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time as dtime, timedelta
import base64
import logging
from math import asin, cos, radians, sin, sqrt
import re
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.core.contracts import Evidence, NextAction, TeamManifest, TeamResult, TeamTask

from app.domains.travel_ops.instances._shared._base import TravelTeamBase
from app.domains.travel_ops.instances._shared.itinerary_team import ITINERARY_TOOLS, ItineraryWork
from app.domains.travel_ops.components.itinerary.itinerary_changes import ItineraryChange, NoChange, applied_record, with_request
from .ledger import item_key
from .interpret import (LABELS, Interpretation, InterpretationInvalid, ask, ground, model_context, needs, parse, rule_checks, rule_dates,
                        rule_ranges, settle_years)
from .wants import (DORMS, Wants, guest_block, kind_reason, price_reason, read_wants, restriction, stars_reason, stay_city, stay_kinds, stay_stars, strip_handled, summary,
                    wants_pet)

logger = logging.getLogger(__name__)

PROMPT_KEY = "lodging.interpret"
SEOUL = ZoneInfo("Asia/Seoul")
#: 답에 싣는 숙소 수 · 그만큼 채우려고 상세를 부르는 최대 횟수(객실 없는 곳은 건너뛴다). 우리가 고른 값
SHOWN, DETAIL_CALLS = 3, 2
#: 목록만 있는 곳의 숙소 페이지 — 상세가 준 `shareWebLink`(☆2026-10-10 17:02 · 17:14 playdata 6곳)와 같은 모양으로 숙소 번호에서 만든다
LIST_LINK = "https://accommodation.myrealtrip.com/union/products/{gid}?checkIn={check_in}&checkOut={check_out}&adultCount={adults}&childCount={children}"
#: 목록에서 받는 수(찾기) · 이름으로 찾을 때 받는 수(내 숙소). 우리가 고른 값
SEARCH_SIZE, NAME_SIZE = 20, 5
#: 구글 호텔에서 따로 보여 주는 수. 우리가 고른 값
GOOGLE_SHOWN = 3
#: 일정 장소가 가운데에서 이보다 멀리 있으면 가운데로 거리를 재지 않는다(여러 도시 · 당일치기 먼 곳). 우리가 고른 값
SPREAD_KM = 30.0
#: 일정 숙소 항목의 「바꿔 줘」 — 새 후보가 없으면 목록을 이만큼 더 받아 다시 찾는다(첫 값은 보통 찾기와 같다). 우리가 고른 값
ALTERNATE_SIZES = (SEARCH_SIZE, 50)
#: 「바꿔 줘」 새 후보를 고를 때 기준점(원래 숙소 · 없으면 일정 가운데)에서 이 거리 안이면 「가까운 곳」으로 먼저. 우리가 고른 값(2026-10-12)
NEAR_KM = 3.0
#: 원래 숙소 1박 가격을 알면 이 비율 안의 곳을 먼저(1박 10만 원 숙소에 40만 원을 먼저 내밀지 않게). 우리가 고른 값(2026-10-12)
PRICE_BAND = (0.7, 1.3)
#: `[2026-10-15 검수 D]` 기준점(카카오 `read.landmark`)에서 이보다 멀면 다른 지역으로 본다 — ☆10-15 검수 L01 · L03 · L05:
#:   「성수」에 군산 모텔, 「강남역」 · 「홍대」에 속초 · 제주 숙소가 왔다. 서울 끝에서 끝이 30km 남짓이라 그 절반 넘게. 우리가 고른 값
REGION_KM = 20.0
#: `[2026-10-15 검수 D]` 「걸어서 · 도보」 직선거리 상한 — 이동 계산기(도보)를 못 쓸 때만. 「근처 · 가까운」은 `NEAR_KM`. 우리가 고른 값 —
#:   ☆사용자 판정 L03 「강남역 도보 20분은 도보 거리 아님」(17:49 판: 베스트웨스턴 직선 0.9km 가 걸어서 20분) → 1.0 에서 0.8 로
WALK_KM = 0.8
#: `[2026-10-15 검수 D]` 「싼 곳」이면 목록을 이만큼 받아 그 안에서 싼 순으로(마이리얼트립 목록 호출은 그대로 1번). 우리가 고른 값
CHEAP_SIZE = 50
#: `[2026-10-15 검수 D]` 거리 조건이 있을 때 상세를 못 읽은 곳의 위치를 카카오(`read.stay_lookup`)로 찾는 최대 횟수. 우리가 고른 값
LOOKUP_CALLS = 2
#: 도시 전체를 뜻하는 검색어 — 기준점을 찾지 않는다(`_landmark`)
_WHOLE_SEOUL = frozenset({"서울", "서울시", "서울특별시", "seoul"})
#: `[2026-10-15 사용자 판정 L09]` 길게 이어진 곳 — 카카오 한 점(「한강」 → 용산 근처)을 거리 기준으로 쓰지 않는다. 서울 안으로는 본다
_WIDE_SEOUL = frozenset({"한강", "한강변", "강변", "한강뷰"})
#: `[2026-10-15 사용자 판정 L08]` 서울에 맞닿은 시 — 기준점이 있으면 시 이름으로 빼지 않고 거리로 본다(「김포 · 강서는 코앞」)
_NEXT_TO_SEOUL = frozenset({"김포", "고양", "부천", "광명", "과천", "안양", "성남", "하남", "구리", "남양주", "의정부", "시흥"})
#: `[2026-10-15 사용자 판정 L03]` 「걸어서 · 도보」 상한(분) — 이동 계산기(도보)가 있을 때. 없으면 직선 `WALK_KM`. 우리가 고른 값
WALK_MIN = 15


def _walk_cap(wants: Wants) -> tuple[int, float]:
    """걸어서 몇 분 안 · 직선 km 상한 — 문장에 「걸어서 N분」이 있으면 그 값(`[2026-10-16 평가 2차]` 전에는 15분 고정), 없으면 `WALK_MIN`.
    직선 상한은 `WALK_KM`(15분 기준)을 분 비율로 줄이거나 늘린다."""
    minutes = wants.walk_min or WALK_MIN
    return minutes, round(WALK_KM * minutes / WALK_MIN, 2)
#: 걸어서 몇 분인지 이동 계산기에 묻는 최대 곳 수(마이리얼트립 · 구글 각각). 우리가 고른 값
WALK_CHECKS = 5
#: 건너뛴 까닭 → 답에 적는 말(가격 없음 · 객실 없음은 전과 같은 문장으로 따로 적는다)
_SKIP_LABELS = {"region": "다른 지역", "kind": "{kind} 아님", "dorm": "호스텔 · 게스트하우스", "avoid": "빼 달라신 유형",
                "stars": "{stars}성급 미만이거나 성급 모름", "far": "{anchor}에서 {limit} 넘음",
                "restricted": "이용 조건(여성 · 외국인 전용 등)이 붙은 곳",
                "price_low": "1박 {low}원 미만", "price_high": "1박 상한 넘음"}
#: 한국 안 좌표인지(국내 · 해외 검색을 고른다) — 대략의 경계. 우리가 고른 값
_KOREA = ((33.0, 38.7), (124.5, 131.0))
#: `[2026-10-15 ST4F-557]` 서울 안 좌표인지(「바꿔 줘」 검색어에 「서울」을 붙일지) — 카카오 어댑터의 서울 사각(`SEOUL_RECT`)과 같은 대략의 경계. 우리가 고른 값
_SEOUL = ((37.41, 37.72), (126.73, 127.27))
#: `[2026-10-15 ST4F-578]` 숙소 이름 속 옛 이름 — 「더그랜드롯데 서울 (구: 롯데호텔 서울)」의 「롯데호텔 서울」
_OLD_NAME = re.compile(r"[(\[]\s*(?:구|舊|옛|old|formerly)\s*[:：.]?\s*([^)\]]+)[)\]]", re.IGNORECASE)


def _won(value: Any) -> str:
    return f"{int(value):,}원" if isinstance(value, (int, float)) else "가격 모름"


def _list_link(gid: Any, dates: dict[str, str], party: dict[str, Any]) -> str:
    return LIST_LINK.format(gid=gid, check_in=dates["check_in"], check_out=dates["check_out"],
                            adults=party.get("adults") or 1, children=party.get("children") or 0)


def _km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """두 좌표의 직선거리(km, 하버사인)."""
    d_lat, d_lon = radians(b_lat - a_lat), radians(b_lon - a_lon)
    h = sin(d_lat / 2) ** 2 + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(d_lon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def _coords(stay: dict[str, Any] | None) -> tuple[float, float] | None:
    if not stay:
        return None
    lat, lon = stay.get("latitude"), stay.get("longitude")
    return (float(lat), float(lon)) if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) else None


def trip_center(points: list[dict[str, Any]], check_in: date, check_out: date) -> dict[str, Any] | None:
    """숙박 기간의 일정 장소 가운데. 그 기간에 좌표 있는 장소가 없으면 일정 전체로. 장소가 없으면 `None`.

    돌려주는 것: latitude · longitude · places(쓴 장소 수) · window(숙박 기간 장소만 썼나) · spread_km(가장 먼 장소까지) ·
    usable(`spread_km <= SPREAD_KM`).
    """
    inside = [p for p in points if p.get("day") and check_in.isoformat() <= p["day"] <= check_out.isoformat()]
    chosen = inside or points
    if not chosen:
        return None
    lat = sum(p["latitude"] for p in chosen) / len(chosen)
    lon = sum(p["longitude"] for p in chosen) / len(chosen)
    spread = max(_km(lat, lon, p["latitude"], p["longitude"]) for p in chosen)
    return {"latitude": round(lat, 6), "longitude": round(lon, 6), "places": len(chosen), "window": bool(inside),
            "spread_km": round(spread, 1), "usable": spread <= SPREAD_KM}


def _distance(center: dict[str, Any] | None, stay: dict[str, Any] | None) -> float | None:
    where = _coords(stay)
    if not center or not center["usable"] or where is None:
        return None
    return round(_km(center["latitude"], center["longitude"], *where), 1)


def _same_name(left: str, right: str) -> bool:
    return "".join(left.split()).casefold() == "".join(right.split()).casefold()


def _key(name: str) -> str:
    return "".join(str(name).split()).casefold()


#: `[2026-10-12]` 소스 간 같은 숙소 — 이름에서 빼는 말(괄호 안 · 「호텔」 · 「서울」 · 공백 · 문장부호)
_NOT_NAME = re.compile(r"\(.*?\)|\[.*?\]|호텔|hotel|서울|seoul|[\s\-_·,.&']", re.IGNORECASE)
#: 이름 핵심이 같아도 둘 다 좌표가 있고 이보다 멀면 다른 숙소로 본다(m). 우리가 고른 값 —
#: ☆10-12 18:53 playdata 명동(`scripts/probe_stay_duplicates.py`): 같은 숙소(밀리오레 호텔 서울 명동 · 밀리오레호텔 명동) 42m,
#:   이름이 다른 가장 가까운 숙소 122m. 한쪽이 다른 쪽을 품는 이름(「더 스테이 호텔」 · 「더 스테이 휴 명동」, 「스탠포드호텔 명동」 ·
#:   「카페스탠포드 명동」)은 다른 숙소였다 — 그래서 **핵심이 같을 때만** 같은 숙소로 본다(포함은 안 본다).
SAME_STAY_M = 100


_HANGUL = re.compile(r"[가-힣]")
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")   # 가나 · 한자


def _korean_name(listed: Any, candidate: Any) -> str:
    """구글 호텔 목록 이름이 **원어**(가나 · 한자, 한글 없음)로 왔고 숙소 상세 이름이 한글이면 상세 이름을 보인다. 그 밖은 목록 이름 그대로(지어내지 않는다).
    ☆`[2026-10-13]` 14:03 playdata 명동: hl=ko 인데도 「相鉄フレッサイン ソウル明洞」(소테츠 프레사 인)이 일본어로 왔다. 상세 이름이 한글로 오는지는 확인 안 함."""
    listed, candidate = str(listed or ""), str(candidate or "")
    if _HANGUL.search(listed) or not _CJK.search(listed) or not _HANGUL.search(candidate):
        return listed
    return candidate


_SOURCE_NAMES = {"myrealtrip": "마이리얼트립", "google": "구글 호텔"}


def _eun(word: str) -> str:
    """「은 / 는」 — 마지막 글자에 받침이 있으면 「은」."""
    last = str(word or "").rstrip()[-1:]
    return "은" if last and "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 else "는"


def _missing_note(sources: dict[str, Any] | None) -> str:
    """「바꿔 줘」 답 끝 한 문장 — 쉬는 중(429)인 소스를 적는다(항공 팀 `_missing_note` 와 같은 꼴). 조회 실패는 기록에만. 둘 다 괜찮으면 빈 문자열.
    `[2026-10-13]` 검색 답(`_search`)에는 있었고 「바꿔 줘」 답에는 없었다 — 고객이 한쪽 소스가 빠진 줄 모르고 고르게 된다."""
    parts = []
    for name, state in (sources or {}).items():
        status, label = (state or {}).get("status"), _SOURCE_NAMES.get(name, name)
        if status == "resting":
            parts.append(f"{label}{_eun(label)} 요청 한도로 잠시 쉬는 중이에요")
    return (" " + " · ".join(parts) + " — 그쪽 숙소는 빠져 있어요.") if parts else ""


def _names(name: Any) -> list[str]:
    """숙소 이름과 그 안의 옛 이름들. `[2026-10-15 ST4F-578]` x600 실서버 「롯데호텔 서울」을 바꿔 달라 했더니 첫 후보가
    「더그랜드롯데 서울 (구: 롯데호텔 서울)」(같은 호텔, 0.1km)이었다 — 이미 보인 이름 빼기가 이름 글자만 봐서 걸러내지 못했다."""
    text = str(name or "")
    return [text, *(old.strip() for old in _OLD_NAME.findall(text) if old.strip())]


def _core(name: str) -> str:
    """숙소 이름 핵심 — 「밀리오레 호텔 서울 명동」 · 「밀리오레호텔 명동」 → 「밀리오레명동」. 영어 · 한국어 표기가 다르면 못 묶는다(확인 안 함)."""
    return _NOT_NAME.sub("", str(name or "")).casefold()


def _points(items: list[Any], *, skip: Any = None) -> list[dict[str, Any]]:
    """일정 항목(`Item`) → 좌표 있는 장소(날 · 위도 · 경도). 숙소 항목 자신은 뺀다(가운데를 숙소로 끌지 않게)."""
    out = []
    for item in items:
        where = _coords(item.place)
        if where is None or item.item_id == skip:
            continue
        out.append({"day": item.starts_at.astimezone(SEOUL).date().isoformat(), "latitude": where[0], "longitude": where[1],
                    "title": item.title})
    return out


def _anchor(item: Any, center: dict[str, Any] | None) -> dict[str, Any] | None:
    """「바꿔 줘」 후보의 거리 기준점 — 원래 숙소 좌표, 없으면 쓸 만한 일정 가운데. 둘 다 없으면 `None`."""
    where = _coords(item.place)
    if where is not None:
        return {"latitude": where[0], "longitude": where[1], "kind": "원래 숙소", "usable": True}
    if center and center["usable"]:
        return {**center, "kind": "일정 가운데"}
    return None


def _reference_price(item: Any) -> float | None:
    """원래 숙소의 1박 가격 — 고른 후보(`detail.chosen`)나 항목 상세에 있을 때만. 모르면 `None`(가격으로 거르지 않는다)."""
    for source in (item.detail.get("chosen") or {}, item.detail):
        value = source.get("price_per_night")
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def _conditions(ctx: dict[str, Any]) -> dict[str, Any]:
    """「바꿔 줘」에 붙은 조건 — 접수 해석(`interpretation.report`) · 요청(`subject_ref.request`)이 준 칸만 읽는다(문장을 다시 해석하지 않는다).

    받는 칸(`[2026-10-12]` 사용자 결정 — 조건은 접수 해석이 뽑아 넘긴다): `cheaper`(참이면 지금 숙소보다 싼 곳만) ·
    `max_price`(숙소 1박 원화 상한). 형식이 틀린 값은 없는 것으로 본다."""
    report = ctx.get("report") or {}
    limit = report.get("max_price")
    return {"cheaper": report.get("cheaper") is True,
            "max_price": int(limit) if isinstance(limit, (int, float)) and not isinstance(limit, bool) and limit > 0 else None}


def _same_stay(pick: dict[str, Any], name: str, where: tuple[float, float] | None) -> bool:
    """후보 `pick` 과 다른 소스의 숙소(`name` · 좌표)가 같은 숙소인가 — 이름 핵심이 같고, 둘 다 좌표가 있으면 `SAME_STAY_M` 안."""
    if not _core(name) or _core(pick["name"]) != _core(name):
        return False
    if where is None or pick.get("latitude") is None or pick.get("longitude") is None:
        return True
    return _km(pick["latitude"], pick["longitude"], *where) * 1000 <= SAME_STAY_M


def _fresh_picks(booked: dict[str, Any], exclude: set[str], anchor: dict[str, Any] | None,
                 dates: dict[str, str], party: dict[str, Any], reference_price: float | None = None,
                 details: dict[Any, dict[str, Any]] | None = None, *, price_limit: float | None = None,
                 by_price: bool = False) -> list[dict[str, Any]]:
    """새 후보 `SHOWN` 곳. 이름이 `exclude` 에 있으면 뺀다. 상세는 부르지 않는다(목록 값만).

    후보 모으기: 마이리얼트립 목록(제공처 순서, 가격 있는 곳만 — 목록에 좌표가 없다) → 구글 호텔(숙박 공유 · 가격 없음 · 링크 없음 제외, 좌표 있음).
    `details`(gid → 마이리얼트립 상세)가 있으면 그 곳은 상세 좌표로 거리를 재고, 그 날짜에 객실이 없으면 뺀다.
    ★`[2026-10-12]` 고르는 순서 — ① 원래 1박 가격의 `PRICE_BAND` 안(가격을 모르면 이 단계 없음) ② 기준점(`_anchor`)에서 `NEAR_KM` 안인 곳을
      가까운 순 ③ 나머지는 모은 순서 그대로. 좌표를 모르는 곳(상세를 안 읽은 마이리얼트립)은 「가까운 곳」으로 치지 않는다(거리를 지어내지 않는다).
    ★`[2026-10-12]` 고른 셋에 마이리얼트립이 하나도 없으면 셋째 자리를 마이리얼트립 첫 곳으로 바꾼다 — 그 날짜 예약 화면으로 바로 가는 링크는
      마이리얼트립만 준다(구글 호텔 링크는 결과 페이지).
    `price_limit` 이 있으면 1박 그 값을 넘는 곳은 뺀다. `by_price` 면 위 순서 대신 1박 가격이 낮은 순(「더 싸게」인데 원래 가격을 모를 때).
    """
    details = details or {}
    pool: list[dict[str, Any]] = []
    taken = set(exclude)
    # `[2026-10-12]` 앞서 보여 준 곳은 소스가 달라도(이름 핵심이 같으면) 뺀다 — 마이리얼트립에서 보인 곳이 다음엔 구글 이름으로 다시 나오지 않게
    shown_cores = {_core(name) for name in exclude if _core(name)}
    def known(name: str) -> bool:                  # `[2026-10-15 ST4F-578]` 옛 이름(「(구: …)」)까지 본다
        return any(_key(each) in taken or _core(each) in shown_cores for each in _names(name))

    for stay in ((booked.get("myrealtrip") or {}).get("stays") or []):
        if stay.get("price_per_night") is None or known(stay["name"]):
            continue
        detail = details.get(stay["gid"])
        if detail and (detail.get("no_rooms") or detail.get("sold_out")):
            continue                                # 그 날짜에 객실이 없다
        taken.add(_key(stay["name"]))
        where = _coords(detail)
        # `[2026-10-12]` 상세를 읽은 곳은 상세 1박 평균(예약 화면 값)을 쓴다 — 고를 때 재확인도 상세라 같은 기준끼리 비교한다.
        #   ☆20:28 playdata 밀리오레: 목록 257,044원 · 0.1초 뒤 상세 251,993원(18:22 · 18:40 에는 같았다) — 목록과 상세가 늘 같지는 않다
        detail_price = (detail or {}).get("price_per_night")
        use_detail = isinstance(detail_price, (int, float)) and detail_price > 0
        pool.append({"key": f"myrealtrip:{stay['gid']}", "name": stay["name"], "source": "마이리얼트립",
                     "price_per_night": detail_price if use_detail else stay.get("price_per_night"),
                     "price_basis": "detail" if use_detail else "list", "rating": stay.get("rating") or None,
                     "review_count": stay.get("review_count"), "distance_km": _distance(anchor, detail),
                     "latitude": where[0] if where else None, "longitude": where[1] if where else None,
                     "link": _list_link(stay["gid"], dates, party), "image": stay.get("thumbnail_url") or None})
    for stay in ((booked.get("google") or {}).get("stays") or []):
        if stay.get("type") == "vacation rental" or stay.get("price_per_night") is None or not stay.get("link") \
                or known(stay["name"]):
            continue
        where = _coords(stay)
        # `[2026-10-12]` 마이리얼트립에 이미 있는 같은 숙소면 뺀다(마이리얼트립 쪽이 그 날짜 예약 화면 링크를 준다)
        if any(_same_stay(pick, stay["name"], where) for pick in pool if pick["source"] == "마이리얼트립"):
            continue
        taken.add(_key(stay["name"]))
        pool.append({"key": f"google:{_key(stay['name'])}", "name": stay["name"], "source": "구글 호텔",
                     "price_per_night": stay.get("price_per_night"), "rating": stay.get("rating") or None,
                     "review_count": stay.get("review_count"), "distance_km": _distance(anchor, stay),
                     "latitude": where[0] if where else None, "longitude": where[1] if where else None, "link": stay["link"],
                     "image": stay.get("image"), "property_token": stay.get("property_token")})

    if price_limit is not None:
        pool = [pick for pick in pool if isinstance(pick["price_per_night"], (int, float)) and pick["price_per_night"] <= price_limit]
    if by_price:
        return sorted(pool, key=lambda pick: pick["price_per_night"])[:SHOWN]

    def order(pick: dict[str, Any]) -> tuple[bool, bool, float]:
        price = pick.get("price_per_night")
        outside = reference_price is not None and not (
            isinstance(price, (int, float)) and PRICE_BAND[0] * reference_price <= price <= PRICE_BAND[1] * reference_price)
        far = pick["distance_km"] is None or pick["distance_km"] > NEAR_KM
        return outside, far, 0.0 if far else pick["distance_km"]

    ranked = sorted(pool, key=order)               # sorted 는 안정 정렬 — 같은 칸 안에서는 모은 순서를 지킨다
    picks = ranked[:SHOWN]
    if len(picks) == SHOWN and not any(pick["source"] == "마이리얼트립" for pick in picks):
        first = next((pick for pick in ranked[SHOWN:] if pick["source"] == "마이리얼트립"), None)
        if first is not None:
            picks = [*picks[:SHOWN - 1], first]
    return picks


def _price_note(check: dict[str, Any]) -> str:
    """고를 때 가격 재확인 결과 한 문장(앞에 빈칸). 1박 값을 모르면 아무것도 적지 않는다."""
    before, now = check.get("before"), check.get("now")
    if check.get("basis") == "sellers":
        # `[2026-10-13]` 구글 호텔 — 판매처 최저가끼리 비교(「1박 ○원~」)
        if check["status"] == "same":
            return f" 지금도 판매처 최저가 1박 {_won(now)}~ 그대로예요."
        if check["status"] == "changed":
            return f" 보여 드릴 때 1박 {_won(before)}~이던 판매처 최저가가 지금 1박 {_won(now)}~이에요."
    if check["status"] == "changed" and check.get("basis") == "list":
        # 목록 값과 예약 화면(상세) 값이 다른 것일 수 있다 — 「가격이 바뀌었다」고 하지 않는다
        return f" 목록에서는 1박 {_won(before)}이었는데, 예약 화면 기준으로 지금 1박 {_won(now)}이에요."
    if check["status"] == "changed":
        return f" 보여 드릴 때 1박 {_won(before)}이던 가격이 지금 1박 {_won(now)}이에요."
    if check["status"] == "same":
        return f" 지금 가격도 1박 {_won(now)} 그대로예요."
    if before is not None:
        return f" 지금 가격은 다시 확인하지 못했어요(보여 드릴 때 1박 {_won(before)}) — 예약 전에 링크에서 확인해 주세요."
    return ""


def _lodging_option(rank: int, pick: dict[str, Any], item: Any) -> dict[str, Any]:
    """새 후보 하나 → 식당 · 활동의 「다른 안」 기록 모양(`itinerary_changes.applied_record` 와 같은 칸) + 숙소 칸(가격 · 평점 · 링크 · 좌표).
    `place_id` 는 비운다 — 우리 후보는 장소 표에 없다(고르면 `detail.chosen` 에 이름 · 좌표 · 링크를 둔다)."""
    return {"key": pick["key"], "rank": rank, "name": pick["name"], "place_id": None, "option": None, "option_label": None,
            "starts_at": item.starts_at.isoformat(), "ends_at": item.ends_at.isoformat() if item.ends_at else None,
            "walk_min": None, "source": pick["source"], "price_per_night": pick.get("price_per_night"),
            "price_basis": pick.get("price_basis"),
            "rating": pick.get("rating"), "review_count": pick.get("review_count"), "distance_km": pick.get("distance_km"),
            "latitude": pick.get("latitude"), "longitude": pick.get("longitude"), "link": pick["link"],
            # `[2026-10-13]` 화면용 — 사진 · 판매처별 가격(구글 호텔 후보만, 상세를 읽었을 때) · 주소
            "image": pick.get("image"), "sellers": pick.get("sellers") or [], "address": pick.get("address"),
            "link_seller": pick.get("link_seller"),
            # `[2026-10-13]` 목록 이름이 원어라 상세 이름으로 바꿔 보인 경우 원래(목록) 이름 — 다음 「바꿔 줘」에서 같은 곳을 빼는 데 쓴다
            "source_name": pick.get("source_name"),
            # `[2026-10-13 사용자 결정]` 판매처를 읽은 곳의 「1박 ○원~」 — 목록 최저가와 판매처 가격 중 가장 싼 값. 없으면 `None`
            "price_from": pick.get("price_from"),
            "property_token": pick.get("property_token")}


#: `[2026-10-13]` 구글 호텔 판매처 중 답에 보여 줄 곳 — 한국인이 많이 쓰는 곳 위주(사용자 결정). 이름은 상세 응답의 `source` 를 소문자로 맞춘다
SELLER_NAMES = {"agoda": "아고다", "trip.com": "트립닷컴", "klook": "클룩", "tripbtoz": "트립비토즈", "booking.com": "부킹닷컴",
                "hotels.com": "호텔스닷컴", "expedia": "익스피디아", "expedia.co.kr": "익스피디아"}
#: 후보 하나에 보여 주는 판매처 수. 우리가 고른 값
SELLERS_SHOWN = 3


def _sellers(detail: dict[str, Any] | None) -> list[dict[str, Any]]:
    """구글 호텔 상세의 판매처 → 보여 줄 판매처(공식 사이트 · `SELLER_NAMES`, 1박 가격이 있는 곳) 싼 순 `SELLERS_SHOWN` 곳."""
    out = []
    for row in (detail or {}).get("sellers") or []:
        price = row.get("price_per_night")
        if not isinstance(price, (int, float)) or price <= 0:
            continue
        name = "공식 사이트" if row.get("official") else SELLER_NAMES.get(str(row.get("seller") or "").strip().lower())
        if name and all(seller["name"] != name for seller in out):
            out.append({"name": name, "price_per_night": price, "link": row.get("link") or None})
    return sorted(out, key=lambda seller: seller["price_per_night"])[:SELLERS_SHOWN]


def _listing_reason(stay: dict[str, Any], wants: Wants, seoul: bool, *, anchored: bool = False, children: int = 0,
                    max_price: int | None = None) -> str | None:
    """마이리얼트립 목록 한 곳을 뺄 까닭(목록 칸만 본다 — 부르지 않는다). 없으면 `None`.
    `seoul` 이면 설명 마지막 칸(시)이 서울이 아닌 곳을 뺀다(☆10-15 검수 L01 「군산 성수」 — 설명 「모텔 · 군산」).
    `anchored`(기준점이 있음)면 서울에 맞닿은 시(`_NEXT_TO_SEOUL`)는 빼지 않고 거리로 본다(☆사용자 판정 L08)."""
    description = stay.get("description")
    city = stay_city(description)
    if seoul and city and city != "서울" and not (anchored and city in _NEXT_TO_SEOUL):
        return "region"
    if guest_block(stay.get("name"), wants.guest, children=children):
        return "restricted"                        # `[2026-10-16 사용자 판정 L05]` 묵을 분에게 맞지 않는 이용 조건만
    price = price_reason(wants, stay.get("price_per_night"), max_price)
    if price:
        return price                               # `[2026-10-16 평가 2차]` 「10만 원대」 아래 끝 · 구간 위 끝
    kind = kind_reason(wants, stay_kinds(description, stay.get("name")))
    if kind:
        return kind
    return stars_reason(wants, stay_stars(description))


def _restricted_text(guest: Any) -> str:
    """뺀 이용 조건 숙소를 말하는 조각 — 묵을 분을 알면 「묵을 분과 맞지 않는」, 모르면 「…이 붙은」."""
    if not guest.missing():
        return f"묵을 분({guest.text()})과 맞지 않는 이용 조건(여성 · 외국인 전용 등)이 이름에 보인"
    return "여성 · 외국인 전용처럼 이용 조건이 붙은"


def _outside_seoul(where: tuple[float, float] | None) -> bool:
    """좌표가 서울 대략 경계(`_SEOUL`) 밖인가 — 맞닿은 시(김포 · 고양 등)는 남게 0.03도(약 3km) 넓혀 본다. 좌표가 없으면 `False`(모름).
    `[2026-10-15]` ☆19:03 playdata 검수 L09 「한강」(기준점 없음)에 구글 칸으로 「롯데호텔앤리조트 김해」가 왔다."""
    if where is None:
        return False
    margin = 0.03
    return not (_SEOUL[0][0] - margin <= where[0] <= _SEOUL[0][1] + margin
                and _SEOUL[1][0] - margin <= where[1] <= _SEOUL[1][1] + margin)


def _google_keyword(keyword: str | None, wants: Wants, anchor: dict[str, Any] | None) -> str | None:
    """구글 호텔에만 쓸 검색어 — 기준점이 서울에서 찾혔으면 앞에 「서울」, 원하는 유형(호텔 밖)이 있으면 뒤에 그 말. 바뀐 게 없으면 `None`.
    ☆10-15 검수 L05 「홍대」 → 제주, L03 「강남역」 → 속초 · 부산. 「서울 ○○」로 물었을 때 결과는 **확인 안 함**(다음 검수에서 본다)."""
    word = str(keyword or "").strip()
    if not word:
        return None
    parts = [word]
    if anchor is not None and "서울" not in word:
        parts.insert(0, "서울")
    if wants.kind and wants.kind != "호텔" and wants.kind not in word:
        parts.append(wants.kind)
    joined = " ".join(parts)
    return joined if joined != word else None


def _varint(value: int) -> bytes:
    out = b""
    while True:
        low, value = value & 0x7F, value >> 7
        if not value:
            return out + bytes([low])
        out += bytes([low | 0x80])


def _proto(number: int, payload: int | bytes) -> bytes:
    """프로토콜 버퍼 칸 하나 — 정수(varint)거나 길이가 붙은 바이트."""
    if isinstance(payload, int):
        return _varint(number << 3) + _varint(payload)
    return _varint((number << 3) | 2) + _varint(len(payload)) + payload


def google_ts(check_in: str, check_out: str, adults: int) -> str:
    """구글 호텔 주소의 `ts` 칸 — 체크인 · 체크아웃 · 성인 수. `[2026-10-15 사용자 질문 「안내 대신 넣어서 링크를 보낼 수 없냐」]`

    ☆18시대 playdata 내장 브라우저: 구글 호텔 화면에서 날짜 · 인원을 바꾸면 주소의 `ts` 가 바뀐다(base64url 프로토콜 버퍼).
      화면이 만든 `ts`(11/28~30 · 3명)와 이 함수가 만든 값이 글자까지 같았고, 이 함수로 만든 다른 값(호텔케이월드 11/7~8 · 4명)을
      새로 열었더니 화면에 11월 7일 · 11월 8일 · 여행자 4명이 들어 있었다. 아이(나이)는 넣지 않는다 — 숙소 팀은 아이 나이를 몰라 어른 + 아이 인원으로 찾는다.
    ★구글이 공개한 주소 규칙이 아니다 — 구글이 바꾸면 날짜 · 인원 없이 열린다(그래도 숙소 검색은 된다)."""
    def day(text: str) -> bytes:
        y, m, d = (int(part) for part in text.split("-"))
        return _proto(1, y) + _proto(2, m) + _proto(3, d)
    people = b"".join(_proto(1, _proto(1, 3)) for _ in range(max(1, int(adults)))) + _proto(2, 1)
    dates = _proto(1, day(check_in)) + _proto(2, day(check_out))
    body = (_proto(1, 1) + _proto(2, people)
            + _proto(3, _proto(1, _proto(3, b"")) + _proto(2, _proto(2, dates) + _proto(6, _proto(1, 2))))
            + _proto(5, _proto(1, _proto(7, b"KRW")) + _proto(3, b"")))
    return base64.urlsafe_b64encode(body).decode().rstrip("=")


def google_qs(property_token: str) -> str:
    """구글 호텔 주소의 `qs` 칸 — 이 숙소 화면을 바로 연다. `[2026-10-16 사용자 판정 4차 L03 「렉시 호텔 링크 결과 없음」]`

    ☆10-16 playdata 내장 브라우저: 구글 호텔 목록에서 숙소를 누르면 주소에 `qs` 가 붙었다 — base64url 프로토콜 버퍼로
      6번 칸 = 숙소 열쇠(SerpApi `property_token` 과 같은 모양 「ChgI…」), 7번 칸 = 13. 이 함수로 만든 값이 화면 값과 글자까지 같았고,
      이름만으로는 「결과 없음」이던 「렉시 호텔」을 `q=렉시 호텔` + `ts`(11/20~22 · 2명 / 11/28~30 · 3명) + 이 `qs` 로 열었더니
      그 숙소 화면에 그 날짜 · 인원이 들어 있었다. ★구글이 공개한 주소 규칙이 아니다."""
    return base64.urlsafe_b64encode(_proto(6, str(property_token).encode()) + _proto(7, 13)).decode().rstrip("=")


def _google_page(name: str, dates: dict[str, str] | None = None, adults: int | None = None, *,
                 token: str | None = None, area: str | None = None) -> str:
    """구글 호텔에서 그 숙소를 연 화면 — 날짜 · 인원을 알면 `ts` 로 채운다(`google_ts`). `[2026-10-15 검수 D]` ☆사용자 판정 L01 —
    목록 `link`(숙소 자체 사이트) 「호텔케이월드」가 열리지 않았다(서비스 종료).
    `[2026-10-16]` 숙소 열쇠(`token`)가 있으면 `qs` 로 그 숙소 화면을 바로 연다. 없으면 이름(+ `area`, 「서울」)으로 찾은 목록 화면 —
    ☆10-16 playdata 「렉시 호텔」은 이름만이면 「결과 없음」, 「렉시 호텔 서울」이면 목록 첫 줄이었다."""
    query = str(name) if token or not area or area in str(name) else f"{name} {area}"
    url = f"https://www.google.com/travel/search?q={quote(query)}&hl=ko&gl=kr"
    if dates and dates.get("check_in") and dates.get("check_out") and adults:
        url += "&ts=" + google_ts(dates["check_in"], dates["check_out"], adults)
    if token:
        url += "&qs=" + google_qs(token)
    return url


class LodgingTeam(ItineraryWork, TravelTeamBase):
    conversation_change_by_team = True        # ★`[2026-10-15 LB-02]` 웹 채팅의 「다른 숙소」도 이 팀의 `_change`(MCP 후보 → 「선택이 필요해요」)로 온다
    manifest = TeamManifest(
        team_id="lodging",
        display_name="Lodging Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["lodging.assist", "lodging.status",
                      "lodging.itinerary",            # ★`[2026-10-11]` 일정 숙소 항목 — 새 후보 3곳 · 예약한 숙소는 그대로
                      "lodging.itinerary_question"],  # 공용 부품이 질문 Case 를 이리로 보낸다(규정을 읽고, 없으면 사람에게)
        accepted_case_types=["lodging"],
        # ★`[2026-10-11]` 식당 · 활동 팀과 같게 — `policy` 를 선언하고 **규정 질문만** 규정을 읽게 한다. 찾기 · 예약 조회 · 일정 숙소 항목은
        #   규정 검색 결과로 판단하지 않으므로 면제(`policy_optional_capabilities`). 전에는 `lodging` scope 에 문서가 0건이라 선언하지 않았다
        #   (`locked` 의 2026-09-22 주석) — 이제 scope 를 여행 문서가 있는 취소 · 이용 조건으로 둔다(숙소 전용 문서는 아직 없다).
        required_context=["case_state", "policy", "db_facts", "history"],
        policy_optional_capabilities=["lodging.assist", "lodging.status", "lodging.itinerary"],
        allowed_tools=["read.booking", "read.itinerary", "read.stay_search", "read.stay_detail", "read.booking_search_stays",
                       "read.offers_shown",
                       "read.stay_lookup",                    # `[2026-10-13]` 내 숙소 위치 — 마이리얼트립이 못 줄 때(카카오 · 관광공사)
                       "read.landmark",                       # `[2026-10-15]` 「강남역 도보」 「경복궁 근처」 기준점 · 서울인지(카카오)
                       "read.stay_google",                    # `[2026-10-13]` 내 숙소를 구글 호텔에서 같은 숙소로 찾기(가격 · 사진 · 판매처)
                       "read.stay_google_details",            # `[2026-10-13]` 구글 호텔 후보의 판매처별 가격 · 주소 · 사진
                       "read.policy", "read.booking_terms", *[name for name in ITINERARY_TOOLS if name != "read.itinerary"]],
        knowledge_scope=["travel_cancellation", "travel_access"],
        max_steps=8,                                  # 일정 1 + booking 1 + 상세 DETAIL_CALLS(2) + 여유(내 숙소 갈래 · 일정 항목 갈래의 넓혀 찾기 등)
        active=True,
        implementation_revision="2026-10-07",
        default_capability="lodging.assist",
    )

    @staticmethod
    def select_capability(intent: str | None, input_text: str, state: dict | None = None) -> str | None:
        """여행 Case 가 **일정 항목을 가리킬 때만**(`part_id`) 일정 관리로 — 식당 팀과 같은 부품. 항목 없이 여행만 붙은 Case 는
        지금처럼 문장 해석(`lodging.assist`)으로 간다(사용자 결정 10-11 「숙소 항목이 없으면 숙소 에이전트를 안 켠다」 — 항목을 가리키지
        않는 문장까지 일정 관리로 보내지 않는다)."""
        ref = (state or {}).get("subject_ref") or {}
        # ★`[2026-10-15 숙박예약 점검 LB-02]` 웹 채팅이 만든 구조화 요청(`request.type: conversation` — 「어느 일정인가요?」 되묻기 포함)은 문장이 아니라 항목 선택 흐름이다.
        #   되묻기 목록의 첫 후보가 숙소여서 이 팀이 맡는데 항목(`part_id`)이 아직 없으면, 문장 해석(`lodging.assist`)으로 가 모델에 되묻기 문장을 해석시켰다(실패해 사람에게 넘어갔다)
        if not ref.get("part_id") and (ref.get("request") or {}).get("type") != "conversation":
            return None
        return ItineraryWork.itinerary_route("lodging", state)

    async def execute(self, task: TeamTask) -> TeamResult:
        blocked = self._guard(task)
        if blocked is not None:
            return blocked
        if task.capability in (self.itinerary_capability, self.question_capability):
            return await self.run_itinerary(task)
        seen: set[str] = set()
        if task.capability == "lodging.status":
            return self._status(task, seen)

        trip, evidence, points = self._trip(task, seen)
        today = datetime.now(SEOUL).date()
        if self.llm is None:
            return self._escalate(task, "interpreter_missing", evidence)
        try:
            raw = await self.llm.complete(PROMPT_KEY, task.input_text,
                                          model_context(today, trip),   # `[2026-10-10]` 달력 · 요일을 함께 준다
                                          run_id=task.run_id)
            found, ungrounded = ground(parse(raw), task.input_text, has_trip=trip is not None, trip=trip)
            found, year_fixed = settle_years(found, today=today, text=task.input_text)   # `[2026-10-10]` 연도를 말하지 않은 날짜는 연도만 서버가 정한다
            found, date_rule = rule_dates(found, task.input_text, today=today)          # `[2026-10-15 L02]` 모델이 날짜를 비웠을 때만
            found, range_rule = rule_ranges(found, task.input_text, today=today)        # `[2026-10-16 평가 2차]` 「12/24~26」 같은 범위
            found, weak = rule_checks(found, task.input_text)                           # `[2026-10-16 평가 2차]` 근거 약한 날짜 · 인원은 비운다
        except InterpretationInvalid as exc:
            logger.warning("lodging interpretation invalid case=%s %s", task.case_id, exc)
            return self._escalate(task, "interpretation_invalid", evidence, warnings=[str(exc)[:200]])
        except Exception as exc:                      # noqa: BLE001 — 모델 호출 실패의 종류를 남기고 사람에게 넘긴다
            logger.warning("lodging interpretation failed case=%s %s", task.case_id, type(exc).__name__)
            return self._escalate(task, "interpretation_failed", evidence, warnings=[type(exc).__name__])

        evidence = [*evidence, Evidence(
            evidence_id=f"interpretation:{task.team_id}", source_type="customer_message", source_id=PROMPT_KEY,
            claim="고객 문장을 모델이 옮긴 구조", value={**found.model_dump(mode="json"), "ungrounded": ungrounded, "year_fixed": year_fixed}, confidence=1.0,
            observed_at=datetime.now(SEOUL))]
        decision = {"task": found.task, "interpretation": found.model_dump(mode="json", exclude={"question"}),
                    "ungrounded": ungrounded, "year_fixed": year_fixed, **({"date_rule": True} if date_rule else {}),
                    **({"range_rule": True} if range_rule else {}), **({"weak_cleared": weak} if weak else {})}

        if found.task == "status":
            return self._status(task, seen, evidence)
        if found.task == "unclear":
            return self._respond(task, evidence, {**decision, "needs": ["task"]},
                                 "숙소를 새로 찾아 드릴지, 이미 예약하신 숙소를 알려 주시는 것인지 말씀해 주세요. "
                                 "찾아 드리려면 지역 · 날짜 · 인원을, 예약하신 숙소라면 숙소 이름과 날짜를 알려 주세요.")
        missing = needs(found, today=today)
        if missing:
            places = list(dict.fromkeys((trip or {}).get("places") or []))[:3]
            if "keyword" in missing and places:
                # `[2026-10-15 검수 · GPT 검토 #17]` 여행 일정이 있는데 지역이 없으면 일정 장소 이름으로 묻는다(전에는 「지역을 알려 주세요」만)
                rest = [name for name in missing if name != "keyword"]
                question = (f"일정의 {' · '.join(places)} 중 어느 곳 근처로 찾을까요? 다른 지역이면 그 지역을 알려 주세요."
                            + (f" {' · '.join(LABELS[name] for name in rest)}도 알려 주시면 이어서 찾아 드리겠습니다." if rest else ""))
                return self._respond(task, evidence, {**decision, "needs": missing, "asked_places": places}, question)
            return self._respond(task, evidence, {**decision, "needs": missing}, ask(found, missing))
        if found.task == "my_stay":
            return self._my_stay(task, found, seen, evidence, decision)
        return self._search(task, found, seen, evidence, decision, points)

    # ── 갈래 ────────────────────────────────────────────────────
    def _status(self, task: TeamTask, seen: set[str], base: list[Evidence] | None = None) -> TeamResult:
        booking = self._read(task, "read.booking", {"case_id": str(task.case_id)}, seen)
        evidence = self._evidence(task, source_id="read.booking", claim="잠긴 예약", value=booking, base=base)
        if booking is None:
            return self._unknown(task, "예약 내역", evidence)
        return self._result(task, outcome="completed", confidence=1.0, evidence=evidence, next_action=NextAction.RESPOND,
                            answer="이 예약은 잠긴 예약으로 취급합니다. 일정 조정 대상이 아닙니다.",
                            decisions=[{"locked": True, "team": self.manifest.team_id}])

    def _search(self, task: TeamTask, found: Interpretation, seen: set[str], evidence: list[Evidence],
                decision: dict[str, Any], points: list[dict[str, Any]] | None = None) -> TeamResult:
        dates = {"check_in": found.check_in.isoformat(), "check_out": found.check_out.isoformat()}
        early = read_wants(task.input_text)
        if early.asks_guest:
            # `[2026-10-16 사용자 판정 L05]` 게스트하우스 · 호스텔은 여성 전용 · 외국인 전용 · 나이 제한이 붙은 곳이 많다 —
            #   바로 찾지 않고 묵을 분의 나이 · 성별 · 내국인/외국인을 먼저 묻는다(부르기 전에 — 도구 호출 0번)
            missing = early.asks_guest
            return self._respond(task, evidence, {**decision, "needs": ["guest_profile"], "guest_missing": missing},
                                 f"{early.kind}{_eun(early.kind)} 여성 전용 · 외국인 전용 · 나이 제한처럼 묵을 수 있는 사람을 정해 둔 곳이 많아요. "
                                 f"찾기 전에 묵으실 분의 정보({' · '.join(missing)})를 알려 주세요(예: 「20대 여자 1명, 내국인」). "
                                 "처음 말씀하신 조건과 함께 보내 주시면 그에 맞는 곳으로 찾아 드릴게요.")
        center = trip_center(points or [], found.check_in, found.check_out)
        if center is not None:
            decision = {**decision, "trip_center": center}
        # `[2026-10-15 검수 D]` 유형 · 성급 · 싼 순 · 거리 말은 서버 규칙으로(사용자 결정) — `wants.py`
        wants = read_wants(task.input_text)
        children = found.children or 0
        # `[2026-10-15 검수 · GPT 검토 #11 · 사용자 판정 L02]` 아이 나이를 모르므로(해석 칸이 수뿐) 어른 + 아이 인원이 묵을 방으로 찾는다 —
        #   전에는 「성인 2명」 방을 찾고 아이는 링크 칸에만 실었다. 객실 정원 칸은 소스에 없어 「링크에서 확인」으로 둔다
        party = {"adults": found.adults + children, "children": 0} if children else {"adults": found.adults, "children": found.children}
        anchor, evidence = self._landmark(task, found, seen, evidence)
        squeezed = "".join(str(found.keyword or "").split())
        seoul = anchor is not None or "서울" in squeezed or squeezed in _WIDE_SEOUL
        walk_min, walk_km = _walk_cap(wants)
        limit = (walk_km if wants.near == "walk" else NEAR_KM if wants.near == "near" else None) if anchor else None
        # `[2026-10-16 평가 2차]` 「10만 원대」 — 모델이 상한을 구간 시작(10만)으로 냈거나 비웠으면 구간 끝(199,999)으로
        max_price = found.max_price_per_night
        if wants.band_max and (max_price is None or max_price == wants.min_price):
            max_price = wants.band_max
        usable_center = center if center and center["usable"] else None
        base = anchor if limit is not None else (usable_center or anchor)
        label = f"{anchor['name']}에서" if base is anchor and anchor else "일정 가운데에서"
        # `[2026-10-15 사용자 판정 L03]` 「걸어서」는 이동 계산기(도보)로 몇 분인지 본다 — 없으면(꺼짐 · 미등록) 직선 `WALK_KM`
        walker = self._walker(anchor, found.check_in) if wants.near == "walk" and anchor else None
        limit_text = f"걸어서 {walk_min}분" if walker else (f"{limit:g}km" if limit is not None else "")
        google_keyword = _google_keyword(found.keyword, wants, anchor)
        decision = {**decision, "wants": {"kind": wants.kind, "avoid": sorted(wants.avoid), "stars": wants.stars,
                                          "no_dorm": wants.no_dorm, "cheapest": wants.cheapest, "near": wants.near},
                    "anchor": {key: anchor[key] for key in ("name", "latitude", "longitude")} if anchor else None,
                    "near_km": limit, "walk_engine": walker is not None if wants.near == "walk" else None,
                    "searched_party": party, "google_keyword": google_keyword}
        # `[2026-10-10]` 소스 고르기 · 다른 곳 링크는 booking 모듈(`components/booking/offers/stays.py`)이 한다(팀 피드백). 상세 확인 · 고르기는 여기서
        arguments = {"keyword": found.keyword, **dates, **party, "domestic": found.domestic,
                     "size": CHEAP_SIZE if wants.cheapest else SEARCH_SIZE,
                     "max_price": max_price, "min_review_rating": found.min_rating}
        if google_keyword:
            arguments["google_keyword"] = google_keyword
        booked = self._read(task, "read.booking_search_stays", arguments, seen) or {}
        evidence = self._evidence(task, source_id="read.booking_search_stays",
                                  claim="숙소 비교 결과(booking: 마이리얼트립 · 구글 호텔)", value=booked or None, base=evidence)
        states = {name: (booked.get("sources") or {}).get(name, {}).get("status", "failed") for name in ("myrealtrip", "google")}
        listing, google = booked.get("myrealtrip"), booked.get("google")
        resting = states["myrealtrip"] == "resting"
        google_trace: list[dict[str, Any]] = []
        block = {"trace": google_trace, "children": children, "wants": wants, "anchor": anchor, "max_price": max_price, "limit": limit, "base": base,
                 "label": label, "query": google_keyword, "walker": walker, "seoul": seoul, "dates": dates,
                 "adults": party.get("adults")}
        notes = self._wants_lines(found, wants, anchor, limit, children, party, text=task.input_text, walker=walker is not None)
        place_lines = self._anchor_line(anchor, walking=walker is not None) if base is anchor and anchor else self._center_line(center)
        extra = self._google_block(google, [], booked.get("elsewhere") or [], center, **block)
        who = f"성인 {found.adults}명" + (f" · 아이 {children}명" if children else "")
        if listing is None:
            why = "요청 한도로 잠시 조회를 쉬고 있습니다" if resting else "결과를 받지 못했습니다(조회 실패)"
            if (google and google.get("stays")) or resting:
                # 마이리얼트립을 못 읽어도 구글 호텔 · 다른 곳 링크는 보여 준다 — 그렇다고 적는다
                return self._respond(task, evidence, {**decision, "found": None, "resting": resting, "google_dropped": google_trace[:20],
                                                      "google": len((google or {}).get("stays") or [])},
                                     "\n".join([f"{found.keyword} · {dates['check_in']}~{dates['check_out']} 조건으로 마이리얼트립 검색은 {why}.",
                                                *notes, *place_lines, *extra]), wants=wants, near_done=limit is not None)
            return self._unknown(task, "숙소 검색 결과", evidence)
        if not listing["stays"] and google and google.get("stays"):
            # `[2026-10-15 검수 · GPT 검토 #10]` 마이리얼트립이 비었어도 구글 호텔에 후보가 있으면 「없습니다」라고 하지 않는다
            return self._respond(task, evidence, {**decision, "found": 0, "google": len(google["stays"]), "google_dropped": google_trace[:20]},
                                 "\n".join([f"{found.keyword} · {dates['check_in']}~{dates['check_out']} 조건으로 마이리얼트립에서는 숙소를 찾지 못했습니다.",
                                            *notes, *place_lines, *extra]), wants=wants, near_done=limit is not None)
        if not listing["stays"]:
            return self._respond(task, evidence, {**decision, "found": 0},
                                 f"{found.keyword} · {dates['check_in']}~{dates['check_out']} 조건으로 찾은 숙소가 없습니다. "
                                 "지역이나 가격 · 평점 조건을 바꿔 다시 말씀해 주세요.", wants=wants, near_done=limit is not None)
        # `[2026-10-15 검수 D]` 목록 칸(설명 · 이름)으로 다른 지역 · 원하지 않는 유형 · 성급 미달을 먼저 뺀다(부르는 수는 그대로).
        #   「싼 곳」이면 받은 목록 안에서 1박 가격 낮은 순 — 그 밖에는 제공처 순서 그대로
        dropped: dict[str, int] = {}
        dropped_names: list[dict[str, Any]] = []
        rows = []
        for stay in listing["stays"]:
            reason = _listing_reason(stay, wants, seoul, anchored=anchor is not None, children=children, max_price=max_price)
            if reason:
                dropped[reason] = dropped.get(reason, 0) + 1
                dropped_names.append({"name": stay.get("name"), "why": reason})   # `[2026-10-16]` 검수에서 뺀 이름을 보려고
                continue
            rows.append(stay)
        if wants.cheapest:
            rows.sort(key=lambda stay: (stay.get("price_per_night") is None, stay.get("price_per_night") or 0))
        # 순서는 제공처가 준 그대로 — 우리가 다시 매기지 않는다. 다만 그 날짜에 객실이 없는 곳은 싣지 않는다.
        # ☆2026-10-07 17:48 playdata — 앞의 셋을 그대로 실었더니 둘이 「해당 날짜 객실 없음 · 가격 모름」이었다.
        # `[2026-10-10]` 상세는 앞의 `DETAIL_CALLS` 곳만 부른다(전에는 4번까지). 나머지는 **목록 값**으로 싣고 링크는 숙소 번호로 만든다
        #   — ☆17:14 playdata 두 문장을 이어 돌리자 7번째 호출에서 429(`retryAfter` 60). 답 하나에 마이리얼트립 최대 1 + `DETAIL_CALLS` 번.
        lines, shown, skipped, calls, stopped, lookups, walks = [], [], [], 0, False, 0, 0
        for stay in rows:
            if len(lines) >= SHOWN:
                break
            if stay.get("price_per_night") is None:
                # ★목록에 가격이 없는 곳은 싣지 않는다 — 2026-10-08 14:41 playdata 에서 상세가 「객실 없음」이던 곳
                #   (1356616 · 3171484)이 같은 조건의 목록에서 가격 없이 왔다
                skipped.append({"gid": stay["gid"], "name": stay["name"], "reason": "no_price_in_list"})
                continue
            detail = None
            if calls < DETAIL_CALLS and not stopped:
                calls += 1
                detail = self._read(task, "read.stay_detail", {"gid": stay["gid"], **dates, **party}, seen)
                if detail and detail.get("cooldown_seconds"):
                    detail = None                     # 상세 도중 429 — 쉬는 표시는 상세가 아니다
                evidence = self._evidence(task, source_id=f"read.stay_detail:{stay['gid']}", claim="숙소 상세(마이리얼트립)",
                                          value=detail, base=evidence)
                if detail is None:
                    # ★상세를 못 읽었으면 더 부르지 않는다 — 대개 제공처가 거절한 것이고(2026-10-08 14:35 · 10-10 17:14 playdata 429),
                    #   이어 부르면 부하만 보탠다. 이 곳과 다음 곳은 목록 값으로 싣는다
                    stopped = True
                elif detail.get("no_rooms") or detail.get("sold_out"):
                    skipped.append({"gid": stay["gid"], "name": stay["name"], "reason": "no_rooms"})
                    continue
            where = _coords(detail)
            located = "detail" if where is not None else None
            if where is None and limit is not None and lookups < LOOKUP_CALLS:
                # `[2026-10-15 검수 D]` 거리 조건이 있는데 상세를 못 읽은 곳 — 이름으로 카카오(숙박)에서 위치를 찾는다(이름 핵심이 같을 때만)
                lookups += 1
                where, evidence = self._locate(task, stay["name"], seen, evidence)
                located = "kakao" if where is not None else None
            minutes = None
            if seoul and anchor is None and _outside_seoul(where):
                skipped.append({"gid": stay["gid"], "name": stay["name"], "reason": "region"})
                continue
            if anchor is not None and where is not None:
                gap = _km(anchor["latitude"], anchor["longitude"], *where)
                if walker is not None and gap <= REGION_KM and walks < WALK_CHECKS:
                    walks += 1
                    minutes = walker(where)
                too_far = (minutes > walk_min) if minutes is not None else (limit is not None and gap > limit)
                if gap > REGION_KM or too_far:
                    skipped.append({"gid": stay["gid"], "name": stay["name"], "reason": "region" if gap > REGION_KM else "far",
                                    "km": round(gap, 1), **({"walk_min": minutes} if minutes is not None else {})})
                    continue
            far = round(_km(base["latitude"], base["longitude"], *where), 1) if base is not None and where is not None else None
            shown.append({"gid": stay["gid"], "name": stay["name"], "detail_read": detail is not None,
                          **({"located": located} if located == "kakao" else {}),
                          **({"walk_min": minutes} if minutes is not None else {})})
            lines.append(self._line(len(lines) + 1, stay, detail, far, _list_link(stay["gid"], dates, party), label,
                                    unknown_far=limit is not None and far is None, walk_min=minutes))
        google_trace.clear()
        extra = self._google_block(google, [item["name"] for item in shown], booked.get("elsewhere") or [], center, **block)
        counts = dict(dropped)
        for item in skipped:
            counts[item["reason"]] = counts.get(item["reason"], 0) + 1
        decision = {**decision, "found": len(listing["stays"]), "shown": shown, "skipped": skipped, "dropped": dropped,
                    "dropped_names": dropped_names[:20], "google_dropped": list(google_trace)[:20],
                    "google": len((google or {}).get("stays") or []) if google is not None else None}
        basic = counts.get("no_price_in_list", 0) + counts.get("no_rooms", 0)
        others = self._skip_text(counts, wants, anchor, limit_text)
        if counts.get("restricted"):
            # `[2026-10-15 사용자 판정 L05]` 이용 조건이 붙은 숙소는 바로 주지 않고 고객 정보를 묻는다
            notes = [*notes, f"마이리얼트립에서 {_restricted_text(wants.guest)} {counts['restricted']}곳은 뺐어요"
                     + ("." if not wants.guest.missing() else " — 성별 · 국적 · 나이를 알려 주시면 다시 볼게요.")]
        if wants.kind in DORMS and wants.guest.text():
            notes = [*notes, "이용 조건은 숙소 이름에 보이는 것만 거를 수 있어요 — 나이 · 성별 제한은 링크한 화면에서 꼭 확인해 주세요."]
        if not lines:
            why = (f"{basic}곳이 가격이 없거나 그 날짜에 객실이 없었고, " if basic else "") \
                + (f"{others} — 말씀하신 조건에 맞는 곳을 찾지 못했습니다. " if others else "그 밖의 곳은 확인하지 못했습니다. ")
            return self._respond(task, evidence, decision,
                                 "\n".join([f"{found.keyword} · {dates['check_in']}~{dates['check_out']} 조건으로 받은 "
                                            f"{len(listing['stays'])}곳 중 " + why + "날짜나 지역 · 조건을 바꿔 다시 말씀해 주세요.",
                                            *notes, *extra]), wants=wants, near_done=limit is not None)
        order = f"받은 {len(listing['stays'])}곳 안에서 1박 가격 낮은 순" if wants.cheapest else "마이리얼트립 검색 순서"
        head = (f"{found.keyword} · {dates['check_in']}~{dates['check_out']} · {who} 조건으로 "
                f"{listing.get('total') or len(listing['stays'])}곳 중 {len(lines)}곳입니다({order}"
                + (f", 가격이 없거나 그 날짜에 객실이 없는 {basic}곳은 건너뜀" if basic else "")
                + (f", {others}" if others else "") + ").")
        tail = "가격과 잔여 객실은 조회 시점 기준이며 링크에서 다시 확인해 주세요. 예약은 링크한 페이지에서 직접 하시면 됩니다."
        return self._respond(task, evidence, decision, "\n".join([head, *notes, *place_lines, *lines, *extra, tail]),
                             wants=wants, near_done=limit is not None)

    def _landmark(self, task: TeamTask, found: Interpretation, seen: set[str],
                  evidence: list[Evidence]) -> tuple[dict[str, Any] | None, list[Evidence]]:
        """`[2026-10-15 검수 D · 사용자 결정 「카카오로 기준점 찾기」]` 검색 지역 이름의 기준점(카카오 · 서울 안). 해외 검색이면 부르지 않는다.
        찾으면 `{name, latitude, longitude, usable: True}` — 지역 확인(`REGION_KM`) · 거리 조건(도보 · 근처)에 쓴다. 못 찾으면 `None`."""
        if found.domestic is False or not found.keyword:
            return None, evidence
        if "".join(str(found.keyword).split()) in _WHOLE_SEOUL | _WIDE_SEOUL:
            # ☆10-15 17:49 playdata 검수 L10 · L12 — 「서울」 하나로는 카카오가 「청계천」을 주어 「청계천에서 12.3km」처럼 뜻 없는 거리가 붙었다.
            #   도시 전체면 기준점을 찾지 않는다(서울인지는 검색어로 안다)
            return None, evidence
        spot = self._read(task, "read.landmark", {"name": found.keyword}, seen)
        evidence = self._evidence(task, source_id="read.landmark", claim="검색 지역 기준점(카카오맵, 서울 안)", value=spot, base=evidence)
        if not spot or not spot.get("found") or not isinstance(spot.get("latitude"), (int, float)) \
                or not isinstance(spot.get("longitude"), (int, float)):
            return None, evidence
        return {"name": str(spot.get("name") or found.keyword), "latitude": float(spot["latitude"]),
                "longitude": float(spot["longitude"]), "usable": True}, evidence

    def _locate(self, task: TeamTask, name: str, seen: set[str],
                evidence: list[Evidence]) -> tuple[tuple[float, float] | None, list[Evidence]]:
        """숙소 이름 → 좌표(카카오 숙박 → 관광공사, `read.stay_lookup`). 이름 핵심(`_core`)이 같은 곳이 하나일 때만 — 지어내지 않는다."""
        looked = self._read(task, "read.stay_lookup", {"name": name}, seen)
        evidence = self._evidence(task, source_id=f"read.stay_lookup:{name}", claim="숙소 위치(이름으로, 거리 확인용)", value=looked,
                                  base=evidence)
        same = [stay for stay in (looked or {}).get("stays") or []
                if _core(stay.get("name")) and _core(stay.get("name")) == _core(name) and _coords(stay) is not None]
        return (_coords(same[0]) if len(same) == 1 else None), evidence

    @staticmethod
    def _skip_text(counts: dict[str, int], wants: Wants, anchor: dict[str, Any] | None, limit: str) -> str:
        parts = []
        for reason, label in _SKIP_LABELS.items():
            if counts.get(reason):
                text = label.format(kind=wants.kind, stars=f"{wants.stars:g}" if wants.stars else "", low=f"{wants.min_price or 0:,}",
                                    anchor=(anchor or {}).get("name", "기준점"), limit=limit)
                parts.append(f"{text} {counts[reason]}곳")
        return (" · ".join(parts) + "은 뺌") if parts else ""

    @staticmethod
    def _wants_lines(found: Interpretation, wants: Wants, anchor: dict[str, Any] | None, limit: float | None,
                     children: int, party: dict[str, Any], *, text: str = "", walker: bool = False) -> list[str]:
        """반영한 조건 · 못 한 조건 · 아이 인원 · 반려동물 안내 줄."""
        lines = []
        if children:
            # `[2026-10-16 GPT 검수 F-32 · G-31]` 나이를 말해도 「몰라」라고 했다 — 나이는 안 읽으므로 「반영 못 함」으로
            lines.append(f"아이 나이별 요금은 반영하지 못해 {party['adults']}명이 묵을 방 기준으로 찾았습니다 — 아이 요금 · 객실 정원은 링크에서 확인해 주세요.")
        done = summary(wants)
        if limit is not None and anchor:
            done.append(f"{anchor['name']}에서 걸어서 {_walk_cap(wants)[0]}분 안(이동 계산기 도보)" if walker
                        else f"{anchor['name']}에서 직선 {limit:g}km 안" + ("(이동 계산기를 못 써 직선거리로 봄)" if wants.near == "walk" else ""))
        if done:
            lines.append("반영한 조건: " + " · ".join(done) + ".")
        if wants.near and limit is None:
            wide = "".join(str(found.keyword or "").split()) in _WIDE_SEOUL | _WHOLE_SEOUL
            lines.append(f"「{found.keyword}」" + ("은(는) 넓게 이어진 곳이라" if wide else " 위치를 찾지 못해")
                         + " 거리 조건(도보 · 근처)은 확인하지 않았습니다.")
        if wants_pet(text):
            # `[2026-10-15 사용자 판정 L10]` 반영 못 함 목록만으로는 부족 — 따로 안내
            lines.append("반려동물 동반은 숙소마다 달라요. 받은 목록에는 동반 가능 여부 칸이 없어 거르지 못했어요 — "
                         "예약 전에 숙소에 동반 가능 여부 · 추가 요금 · 크기 제한을 꼭 확인해 주세요.")
        return lines

    def _walker(self, anchor: dict[str, Any], day: date) -> Any:
        """`[2026-10-15 사용자 판정 L03]` 숙소 → 기준점을 **걸어서** 몇 분인지 — 이동 계산기(`team_hooks.legs`, 도보만)를 **불러서 쓰기만** 한다.
        이동 팀이 없거나 꺼져 있으면 `None`(부르는 쪽은 직선거리로). 돌려주는 함수는 좌표 → 분(못 구하면 `None`).
        ☆소요가 걷는 시간만인지(여유 포함인지)는 확인 안 함 — 계산기의 `eta_min` 을 그대로 쓴다."""
        try:
            from app.domains.travel_ops.components.team_hooks import legs

            leg = legs.leg_planner(1, {}, modes=["walk"])
        except Exception as exc:                      # noqa: BLE001 — 이동 팀 부재 · 엔진 준비 실패면 직선거리로
            logger.info("lodging walk check unavailable %s", type(exc).__name__)
            return None
        if leg is None:
            return None
        arrive = datetime.combine(day, dtime(15, 0), tzinfo=SEOUL)
        target = {"key": "lodging_anchor", "name": anchor["name"], "kind": "activity", "lat": anchor["latitude"],
                  "lon": anchor["longitude"], "weather_sensitive": None, "attributes": {}}

        def minutes(where: tuple[float, float]) -> int | None:
            origin = {"key": "lodging_stay", "name": "숙소", "kind": "lodging", "lat": where[0], "lon": where[1],
                      "weather_sensitive": None, "attributes": {}}
            try:
                got, _ = leg(origin, target, arrive, None)
            except Exception as exc:                  # noqa: BLE001 — 한 곳 계산 실패는 그 곳만 「모름」
                logger.info("lodging walk check failed %s", type(exc).__name__)
                return None
            eta = (got or {}).get("eta_min")
            return int(eta) if isinstance(eta, (int, float)) else None
        return minutes

    @staticmethod
    def _anchor_line(anchor: dict[str, Any] | None, *, walking: bool = False) -> list[str]:
        if not anchor:
            return []
        if walking:
            # `[2026-10-15]` ☆19:29 검수 L03 — 「걸어서 13분」 옆에 「이동 시간 아님」이 함께 나와 어긋났다
            return [f"km 는 카카오맵의 「{anchor['name']}」 위치에서 잰 직선거리이고, 「걸어서 N분」은 이동 계산기(도보)로 잰 시간입니다."]
        return [f"거리는 카카오맵의 「{anchor['name']}」 위치에서 잰 직선거리입니다(이동 시간 아님)."]

    def _my_stay(self, task: TeamTask, found: Interpretation, seen: set[str], evidence: list[Evidence],
                 decision: dict[str, Any]) -> TeamResult:
        dates = {"check_in": found.check_in.isoformat(), "check_out": found.check_out.isoformat()}
        party = {"adults": found.adults, "children": found.children}
        listing = self._read(task, "read.stay_search", {"keyword": found.stay_name, **dates, **party,
                                                        "domestic": found.domestic, "size": NAME_SIZE}, seen)
        evidence = self._evidence(task, source_id="read.stay_search", claim="숙소 이름 검색 결과(마이리얼트립)", value=listing,
                                  base=evidence)
        # `[2026-10-13]` 마이리얼트립이 쉬는 중(429 뒤)이면 목록 대신 `cooldown_seconds` 만 온다 — 전에는 여기서 `stays` 를 읽다 멈췄다
        resting = bool(listing and listing.get("cooldown_seconds"))
        stays = [] if listing is None or resting else listing.get("stays") or []
        exact = [stay for stay in stays if _same_name(stay["name"], found.stay_name)] \
            or [stay for stay in stays if _core(stay["name"]) and _core(stay["name"]) == _core(found.stay_name)]
        # `[2026-10-15 검수 · GPT 검토 #13]` 결과가 하나여도 이름(핵심)이 맞지 않으면 「확인했다」고 하지 않는다 — 그 한 곳을 후보로 보이고
        #   맞는지 묻는다(`name_unmatched`). 개명한 숙소(☆10-13 「롯데호텔 서울」 → 「더그랜드롯데 서울」)도 있어 막지는 않는다
        chosen = exact[0] if len(exact) == 1 else stays[0] if len(stays) == 1 else None
        unmatched = chosen is not None and not exact
        if chosen is None:
            if not stays:
                why = "resting" if resting else "failed" if listing is None else "not_found"
                return self._my_stay_elsewhere(task, found, seen, evidence, decision, dates, why)
            names = " / ".join(stay["name"] for stay in stays)
            return self._respond(task, evidence, {**decision, "found": len(stays), "needs": ["stay_name"]},
                                 f"「{found.stay_name}」 에 해당할 수 있는 숙소가 여러 곳입니다: {names}. 어느 곳인지 이름을 그대로 알려 주세요.")
        detail = self._read(task, "read.stay_detail", {"gid": chosen["gid"], **dates, **party}, seen)
        evidence = self._evidence(task, source_id=f"read.stay_detail:{chosen['gid']}", claim="숙소 상세(마이리얼트립)",
                                  value=detail, base=evidence)
        if detail is None or detail.get("cooldown_seconds") or detail.get("latitude") is None or detail.get("longitude") is None:
            why = "resting" if detail and detail.get("cooldown_seconds") else "no_location"
            return self._my_stay_elsewhere(task, found, seen, evidence, decision, dates, why)
        stay = {key: detail.get(key) for key in ("gid", "name", "address", "latitude", "longitude", "link")}
        checked = (f"「{found.stay_name}」(으)로 찾은 곳은 이 한 곳뿐이라 이곳으로 알려 드려요 — 다른 숙소라면 예약 확인서에 적힌 이름을 알려 주세요."
                   if unmatched else f"{dates['check_in']}~{dates['check_out']} 숙박으로 확인했습니다.")
        answer = (f"{detail['name']} — {detail.get('address') or '주소 모름'} "
                  f"(위도 {detail['latitude']}, 경도 {detail['longitude']}). "
                  f"{checked} 숙소 페이지: {detail.get('link') or '링크 없음'}\n"
                  "위치는 마이리얼트립에 등록된 값입니다. 일정에는 아직 넣지 않았습니다.")
        return self._respond(task, evidence, {**decision, "my_stay": {**stay, **dates}, "name_unmatched": unmatched}, answer)

    def _my_stay_elsewhere(self, task: TeamTask, found: Interpretation, seen: set[str], evidence: list[Evidence],
                           decision: dict[str, Any], dates: dict[str, str], why: str) -> TeamResult:
        """`[2026-10-13]` 마이리얼트립이 못 줄 때(쉬는 중 · 실패 · 못 찾음 · 위치 없음) 내 숙소의 주소 · 좌표를 다른 곳에서 찾는다.

        `read.stay_lookup` — 카카오 로컬(숙박, 서울) → 관광공사(숙박). 날짜별 가격 · 예약 링크는 없다(위치만).
        이름 핵심(`_core`)이 같은 곳이 하나면 그곳, 결과가 하나면 그곳, 여럿이면 되묻는다. 위치를 지어내지 않는다.
        """
        looked = self._read(task, "read.stay_lookup", {"name": found.stay_name}, seen)
        evidence = self._evidence(task, source_id="read.stay_lookup", claim="숙소 이름으로 위치 찾기(카카오 · 관광공사)",
                                  value=looked, base=evidence)
        record = {**decision, "my_stay_fallback": why}
        if looked is None:
            if why == "not_found":
                return self._respond(task, evidence, {**record, "found": 0},
                                     f"「{found.stay_name}」 이름으로 찾은 숙소가 없습니다. 숙소 이름을 예약 확인서에 적힌 대로 다시 알려 주세요.")
            return self._unknown(task, "숙소 위치", evidence)
        stays = [stay for stay in looked.get("stays") or []
                 if stay.get("latitude") is not None and stay.get("longitude") is not None]
        exact = [stay for stay in stays if _core(stay["name"]) and _core(stay["name"]) == _core(found.stay_name)]
        pick = exact[0] if len(exact) == 1 else stays[0] if len(stays) == 1 else None
        unmatched = pick is not None and not exact          # `[2026-10-15 GPT 검토 #13]` 이름이 다르면 「이곳이 맞는지」 함께 묻는다
        if pick is None:
            if not stays:
                return self._respond(task, evidence, {**record, "found": 0},
                                     f"「{found.stay_name}」 이름으로 찾은 숙소가 없습니다. 숙소 이름을 예약 확인서에 적힌 대로 다시 알려 주세요.")
            names = " / ".join(stay["name"] for stay in stays)
            return self._respond(task, evidence, {**record, "found": len(stays), "needs": ["stay_name"]},
                                 f"「{found.stay_name}」 에 해당할 수 있는 숙소가 여러 곳입니다: {names}. 어느 곳인지 이름을 그대로 알려 주세요.")
        label = {"kakao": "카카오맵", "tour_api": "한국관광공사"}.get(str(looked.get("source")), "다른 지도 정보")
        reason = {"resting": "마이리얼트립이 요청 한도로 잠시 쉬는 중이라 ",
                  "failed": "마이리얼트립 조회에 실패해 ",
                  "not_found": "마이리얼트립에서 찾지 못해 ",
                  "no_location": "마이리얼트립에 위치가 없어 "}.get(why, "")
        stay = {"name": pick["name"], "address": pick.get("address"), "latitude": pick["latitude"],
                "longitude": pick["longitude"], "link": None, "source": looked.get("source")}
        stay, evidence, google = self._my_stay_google(task, found, stay, dates, seen, evidence)
        if stay.get("sellers"):
            sellers = " · ".join(f"{seller['name']} {_won(seller['price_per_night'])}" for seller in stay["sellers"])
            priced = (f"구글 호텔 기준 1박 {_won(stay['price_from'])}~ (판매처 {sellers}). "
                      + (f"예약은 {stay['link_seller']}에서: {stay['link']}" if stay.get("link") else "바로 갈 예약 링크는 없었어요."))
        else:
            priced = "이 경로로는 날짜별 가격 · 예약 링크를 확인하지 못했어요."
        answer = (f"{pick['name']} — {pick.get('address') or '주소 모름'} "
                  f"(위도 {pick['latitude']}, 경도 {pick['longitude']}). "
                  f"{reason}{label}에 등록된 위치로 알려 드려요. {priced}\n"
                  + (f"「{found.stay_name}」(으)로 찾은 곳은 이 한 곳뿐이라 이곳으로 알려 드렸어요 — 다른 숙소라면 예약 확인서에 적힌 이름을 알려 주세요.\n"
                     if unmatched else "")
                  + "일정에는 아직 넣지 않았습니다.")
        return self._respond(task, evidence, {**record, "my_stay": {**stay, **dates}, "google": google, "name_unmatched": unmatched},
                             answer)

    def _my_stay_google(self, task: TeamTask, found: Interpretation, stay: dict[str, Any], dates: dict[str, str],
                        seen: set[str], evidence: list[Evidence]) -> tuple[dict[str, Any], list[Evidence], dict[str, Any]]:
        """`[2026-10-13 사용자 결정]` 다른 지도에서 찾은 내 숙소에 구글 호텔의 가격 · 사진 · 판매처 · 예약 버튼을 붙인다(마이리얼트립 429 대비).

        ☆12:00 playdata(`scripts/probe_stay_google_match.py`): 구글 호텔에 **카카오가 돌려준 현재 이름**으로 물으면 같은 숙소가 맨 앞에
          왔다 — 더그랜드롯데 서울 6m · 밀리오레호텔 명동 27m · 스테이7 명동 3m. 고객이 말한 옛 이름(「롯데호텔 서울」)은 「결과 없음」,
          지역 검색(「서울 중구 호텔」 20곳)에는 그 숙소가 없었다(가장 가까운 곳 414m · 옆 건물 40m). 그래서 이름 검색 + **이름 핵심이 같고
          좌표 `SAME_STAY_M` 안(둘 다)**인 곳만 같은 숙소로 본다 — 좌표만으로는 옆 호텔을 잘못 잡는다.
        SerpApi 최대 2회(목록 1 + 상세 1). 못 찾거나 못 읽으면 위치만 돌려준다(지어내지 않는다). 기록 `google:{asked, matched, detail}`.
        """
        google = {"asked": True, "matched": False, "detail": False}
        party = {"adults": found.adults, "children": found.children}
        listing = self._read(task, "read.stay_google", {"keyword": stay["name"], **dates, **party}, seen)
        evidence = self._evidence(task, source_id="read.stay_google", claim="구글 호텔에서 같은 숙소 찾기(현재 이름)", value=listing,
                                  base=evidence)
        if listing is None:
            google["asked"] = False
            return stay, evidence, google
        where = (stay["latitude"], stay["longitude"])
        same = next((row for row in listing.get("stays") or []
                     if row.get("property_token") and row.get("latitude") is not None and row.get("longitude") is not None
                     and _same_stay(row, stay["name"], where)), None)
        if same is None:
            return stay, evidence, google
        google["matched"] = True
        out = {**stay, "google_name": same["name"], "property_token": same["property_token"], "image": same.get("image"),
               "price_per_night": same.get("price_per_night"), "link": same.get("link") or None, "price_basis": "list"}
        got = self._read(task, "read.stay_google_details", {"tokens": [same["property_token"]], "keyword": stay["name"], **dates,
                                                            "adults": found.adults}, seen)
        evidence = self._evidence(task, source_id="read.stay_google_details", claim="구글 호텔 판매처별 가격 · 사진(내 숙소)", value=got,
                                  base=evidence)
        detail = ((got or {}).get("details") or {}).get(same["property_token"])
        if not detail:
            return out, evidence, google
        google["detail"] = True
        out["sellers"] = _sellers(detail)
        out["image"] = out["image"] or detail.get("image")
        out["address"] = out.get("address") or detail.get("address") or None
        direct = next((seller for seller in out["sellers"] if seller.get("link")), None)
        if direct:
            out["link"], out["link_seller"] = direct["link"], direct["name"]
        prices = [p for p in [out.get("price_per_night"), *(s["price_per_night"] for s in out["sellers"])] if isinstance(p, (int, float))]
        out["price_from"] = min(prices) if out["sellers"] and prices else None
        return out, evidence, google

    # ── 일정 숙소 항목 (`lodging.itinerary`, 2026-10-11) ─────────────
    def _change(self, task: TeamTask, ctx: dict[str, Any]) -> TeamResult:
        """「바꿔 줘」 — 공용 부품(`ItineraryWork._change`, 들고 있던 다른 안으로 바꾸기)을 숙소용으로 덮는다.

        ★`[2026-10-12 사용자 지적 「왜 대본이 나가? 내보내는 건 후보」]` 식당 · 활동과 **같은 모양**으로 내보낸다:
          - 고른 안이 없으면(`request.choice` 없음) 새 후보 3곳을 계산해 항목의 **「다른 안」(`detail.alternates`)** 자리에 싣는다 — 식당 · 활동이
            안을 들고 있는 자리 · 모양(`key` · `name` · `place_id` · `starts_at` · `ends_at` · `rank` …)과 같다. 숙소는 그대로, 답은 한 줄
            (「○○ 대신 갈 수 있는 곳이에요 — 1) … 고르시면 바꿀게요」, `TripDesk.propose_alternatives` 와 같은 글). 가격 · 평점 · 링크는 후보 칸에 둔다.
          - 고른 안이 있으면(`request.choice` = 후보 `key`) 그 숙소로 항목을 바꾼다(`plan_swap` 과 같은 일 — 원래 숙소는 「다른 안」으로 돌아간다).
            ★우리 후보(마이리얼트립 · 구글)는 장소 표에 없어 `place_id` 를 비운다 — 적용기가 장소 표에 없는 id 를 거부하므로(`itinerary_actions`).
            고른 숙소의 이름 · 좌표 · 링크는 `detail.chosen` 에 둔다. 예약 전이다(`detail.booked = False`) — 예약은 링크에서 고객이.
        """
        ref, trip, items = ctx["ref"], ctx["trip"], ctx["items"]
        target = ref.get("part_id") or ref.get("recent_part_id")
        item = next((i for i in items if str(i.item_id) == str(target)), None) if target else None
        if item is None:
            return self._unknown(task, "숙소 일정 항목", ctx["evidence"])
        if item.kind != self.manifest.team_id:
            return self._escalate(task, "target_kind_mismatch", ctx["evidence"],
                                  warnings=[f"{item.kind} 항목은 {self.manifest.team_id} 팀 일이 아니다"])
        if item.locked or item.booking_id or item.detail.get("booked"):
            return self._result(task, outcome="completed", confidence=1.0, evidence=ctx["evidence"],
                                next_action=NextAction.RESPOND,
                                answer=f"{item.title}은(는) 이미 예약하신 숙소라 바꾸지 않았어요. 다른 숙소를 원하시면 예약하신 곳에서 "
                                       "먼저 취소 조건을 확인해 주세요.",
                                decisions=[{"itinerary": "booked_kept", "item": item.title}])
        choice = (ctx.get("request") or {}).get("choice")
        if choice:
            return self._choose(task, ctx, item, str(choice))
        query = self._stay_query(item, trip)
        if query is None and (ctx.get("request") or {}).get("type") == "conversation":
            # ★`[2026-10-15]` 인원만 모르면(웹 접수로 만든 여행은 인원이 비어 있다) 사람에게 넘기지 않고 고객에게 묻는다 — 답이 오면 그 인원으로 찾는다
            from app.domains.travel_ops.instances._shared.conversation_work import ask_party, known_party

            said = known_party(task, ctx)
            if said is not None:
                query = self._stay_query(item, {**trip, "party_size": said})
            elif self._stay_query(item, {**trip, "party_size": 1}) is not None:
                return ask_party(self, task, ctx, "숙소")
        if query is None:
            return self._unknown(task, "숙소 항목의 날짜 · 인원 · 지역", ctx["evidence"])
        dates = {"check_in": query["check_in"], "check_out": query["check_out"]}
        party = {"adults": query["adults"], "children": None}
        center = trip_center(_points(items, skip=item.item_id), date.fromisoformat(query["check_in"]),
                             date.fromisoformat(query["check_out"]))
        anchor, reference_price = _anchor(item, center), _reference_price(item)
        conditions = _conditions(ctx)
        price_limit = conditions["max_price"]
        if conditions["cheaper"] and reference_price is not None:
            price_limit = min(price_limit or reference_price, reference_price - 1)
        by_price = conditions["cheaper"] and reference_price is None
        asked = "더 싼" if conditions["cheaper"] else (f"1박 {_won(price_limit)} 이하" if price_limit is not None else "")
        shown = [str(name) for name in item.detail.get("shown") or []]
        # `[2026-10-13]` 후보는 이제 일정에 싣지 않고 보류 제안으로 내민다 — 앞서 보여 준 곳은 숙소 · 항공 원장에서 읽는다(항목 상세 `shown` 은 옛 판 몫)
        shown_key = item_key("lodging", query)
        ledger = self._read(task, "read.offers_shown", {"trip_id": trip["trip_id"], "item_key": shown_key}, ctx["seen"])             if shown_key else None
        shown += [str(offer["name"]) for offer in (ledger or {}).get("offers") or [] if offer.get("name")]
        exclude = {_key(name) for name in [*shown, item.title, (item.place or {}).get("name") or ""] if name}
        # `[2026-10-13]` 구글 호텔 후보는 원어 이름 대신 상세의 한글 이름으로 보일 수 있다 — 원장에는 보인 이름이 남으므로
        #   후보 key(`google:<목록 이름 열쇠>`)의 열쇠로도 뺀다(다음 목록은 원어 이름으로 온다)
        exclude |= {str(offer["key"]).split(":", 1)[1] for offer in (ledger or {}).get("offers") or []
                    if str(offer.get("key") or "").startswith("google:")}
        picks: list[dict[str, Any]] = []
        booked: dict[str, Any] = {}
        sizes_used: list[int] = []
        # `[2026-10-12]` 마이리얼트립 목록에는 좌표가 없다(10-07 실호출 · searchStays 입력에도 좌표 칸이 없다 — stayPoi · regionId 는 내부 번호).
        #   앞의 `DETAIL_CALLS` 곳만 상세를 읽어 좌표 · 객실 여부를 얻는다. 상세를 못 읽으면(429 등) 더 부르지 않는다 — 검색 갈래와 같은 규칙
        details: dict[Any, dict[str, Any]] = {}
        detail_calls, stopped = 0, False
        for size in ALTERNATE_SIZES:
            sizes_used.append(size)
            booked = self._read(task, "read.booking_search_stays", {
                "keyword": query["keyword"], **dates, **party, "domestic": query["domestic"], "size": size}, ctx["seen"]) or {}
            ctx["evidence"] = self._evidence(task, source_id=f"read.booking_search_stays:{size}",
                                             claim="숙소 새 후보(booking: 마이리얼트립 · 구글 호텔)", value=booked or None,
                                             base=ctx["evidence"])
            for stay in ((booked.get("myrealtrip") or {}).get("stays") or []):
                if detail_calls >= DETAIL_CALLS or stopped:
                    break
                if stay.get("price_per_night") is None or _key(stay["name"]) in exclude or stay["gid"] in details:
                    continue
                detail_calls += 1
                detail = self._read(task, "read.stay_detail", {"gid": stay["gid"], **dates, **party}, ctx["seen"])
                if detail and detail.get("cooldown_seconds"):
                    detail = None
                ctx["evidence"] = self._evidence(task, source_id=f"read.stay_detail:{stay['gid']}", claim="숙소 상세(마이리얼트립 · 좌표)",
                                                 value=detail, base=ctx["evidence"])
                if detail is None:
                    stopped = True
                else:
                    details[stay["gid"]] = detail
            picks = _fresh_picks(booked, exclude, anchor, dates, party, reference_price, details,
                                 price_limit=price_limit, by_price=by_price)
            if picks or not booked:
                break
        # `[2026-10-13]` 구글 호텔 후보는 상세를 **동시에** 읽어 판매처별 가격 · 주소 · 사진을 붙인다(사용자 결정 — 후보 3곳 모두).
        #   ☆10-13 playdata 상세 한 번 7.2초 · SerpApi 1회. 못 읽으면 목록 값(최저가 하나)만 그대로 보인다
        tokens = [pick["property_token"] for pick in picks if pick["source"] == "구글 호텔" and pick.get("property_token")]
        google_read = 0
        if tokens:
            got = self._read(task, "read.stay_google_details", {"tokens": tokens, "keyword": query["keyword"], **dates,
                                                                "adults": query["adults"]}, ctx["seen"]) or {}
            ctx["evidence"] = self._evidence(task, source_id="read.stay_google_details", claim="구글 호텔 판매처별 가격 · 주소",
                                             value=got or None, base=ctx["evidence"])
            for pick in picks:
                found = (got.get("details") or {}).get(pick.get("property_token")) if pick["source"] == "구글 호텔" else None
                if found:
                    google_read += 1
                    shown_name = _korean_name(pick["name"], found.get("name"))
                    if shown_name != pick["name"]:
                        pick["source_name"], pick["name"] = pick["name"], shown_name
                    pick["sellers"] = _sellers(found)
                    pick["address"] = found.get("address") or None
                    pick["image"] = pick.get("image") or found.get("image")
                    # 예약 버튼 — 보여 주는 판매처 중 바로 갈 주소가 있는 가장 싼 곳(날짜가 채워진 판매처 화면). 없으면 호텔 링크 그대로
                    direct = next((seller for seller in pick["sellers"] if seller.get("link")), None)
                    if direct:
                        pick["link"], pick["link_seller"] = direct["link"], direct["name"]
                    # `[2026-10-13 사용자 결정]` 대표 가격은 가장 싼 곳 「1박 ○원~」 — ☆10:40 playdata 스테이7 명동: 목록 255,093원인데
                    #   판매처 최저는 아고다 245,429원이라 대표 가격과 판매처 가격이 어긋나 보였다. 순서 · 재확인은 목록 값(`price_per_night`) 그대로
                    prices = [p for p in [pick.get("price_per_night"), *(s["price_per_night"] for s in pick["sellers"])]
                              if isinstance(p, (int, float))]
                    if pick["sellers"] and prices:
                        pick["price_from"] = min(prices)
        record = {"itinerary": "lodging_options", "item": item.title, "query": query, "shown_before": len(shown),
                  "sizes": sizes_used, "options": [pick["name"] for pick in picks],
                  "anchor": anchor["kind"] if anchor else None, "reference_price": reference_price, "details_read": len(details),
                  "conditions": {**conditions, "price_limit": price_limit, "by_price": by_price},
                  "near": sum(1 for pick in picks if pick["distance_km"] is not None and pick["distance_km"] <= NEAR_KM),
                  "google_details": {"asked": len(tokens), "read": google_read},
                  "sources": {name: (state or {}).get("status") for name, state in (booked.get("sources") or {}).items()}}
        if not picks:
            if not booked:
                return self._unknown(task, "숙소 검색 결과", ctx["evidence"])
            # ★식당 · 활동의 「바꿀 수 있는 다른 안이 없어요」(`ANSWERS["no_alternate"]`)와 같은 자리 — 일정은 그대로
            return self._result(task, outcome="completed", confidence=0.9, evidence=ctx["evidence"],
                                next_action=NextAction.RESPOND, decisions=[record],
                                answer=f"{item.title} 대신 갈 수 있는 {asked + ' ' if asked else ''}숙소를 더 찾지 못했어요. 일정은 그대로 두었어요.")
        options = [_lodging_option(rank, pick, item) for rank, pick in enumerate(picks, start=1)]
        def note(option: dict[str, Any]) -> str:
            if option.get("price_from") is not None:
                parts = [f"1박 {_won(option['price_from'])}~"]
            else:
                parts = [f"1박 {_won(option['price_per_night'])}"] if option.get("price_per_night") is not None else []
            if option.get("distance_km") is not None and anchor:
                parts.append(f"{anchor['kind']}에서 {option['distance_km']}km")
            if option.get("sellers"):
                parts.append("판매처 " + " · ".join(f"{seller['name']} {_won(seller['price_per_night'])}" for seller in option["sellers"]))
            return f"({' · '.join(parts)})" if parts else ""
        listed = " · ".join(f"{option['rank']}) {option['name']}{note(option)}" for option in options)
        said = ""
        if by_price:
            said = " 원래 숙소 가격을 몰라 1박 가격이 낮은 순으로 골랐어요."
        elif conditions["cheaper"]:
            said = f" 원래 숙소(1박 {_won(reference_price)})보다 싼 곳만 골랐어요."
        elif price_limit is not None:
            said = f" 말씀하신 대로 1박 {_won(price_limit)} 이하만 골랐어요."
        answer = (f"{item.title} 대신 갈 수 있는 곳이에요 — {listed}.{said}{_missing_note(booked.get('sources'))}"
                  " 고르시면 바꿀게요. 고르지 않으시면 원래 일정을 그대로 둡니다.")
        cause = with_request({"category": "customer_request", "type": "requested_options", "from": item.title,
                              "message": task.input_text}, task.context.current_state.get("request_id"))
        # ★`[2026-10-13]` 일정은 바꾸지 않는다 — 식당 · 활동의 「다른 후보」처럼 「선택이 필요해요」 제안으로 내민다(일정 판 그대로).
        #   고르면 고르기 경로가 숙소 원장으로 그 숙소를 여행 전용 장소로 들여놓고(좌표가 있을 때) 바꾼다(`pending.choose`)
        return self.offer(task, ctx, item, options=options, text=answer, causes=[cause], decision=record, shown_key=shown_key,
                          summary={"lodging_options": [o["name"] for o in options], "shown_total": len(shown) + len(options),
                                   **{k: v for k, v in record.items() if k in ("sizes", "shown_before", "anchor", "near", "details_read", "conditions", "google_details", "sources")}})

    def _choose(self, task: TeamTask, ctx: dict[str, Any], item: Any, choice: str) -> TeamResult:
        """후보 중 고른 숙소로 항목을 바꾼다 — `plan_swap` 과 같은 일(원래 숙소는 「다른 안」 끝으로, 알림 문장도 같은 꼴)."""
        trip = ctx["trip"]
        base = int(ctx["ref"].get("base_version") or trip["version"])
        if trip["version"] != base:
            return self.settle(task, ctx, NoChange("stale", {"version": trip["version"]}))
        alternates = list(item.detail.get("alternates") or [])
        pick = next((option for option in alternates if str(option.get("key")) == choice), None)
        if pick is None:
            return self._escalate(task, "itinerary_unknown_choice", ctx["evidence"],
                                  warnings=[f"고른 안 {choice} 이(가) 이 항목의 후보에 없다: {[o.get('key') for o in alternates]}"])
        held = pick
        pick, check = self._recheck(task, ctx, item, pick)
        if check["status"] == "gone":
            return self._result(task, outcome="completed", confidence=0.9, evidence=ctx["evidence"],
                                next_action=NextAction.RESPOND,
                                decisions=[{"itinerary": "lodging_gone", "item": item.title, "choice": held["key"], "price_check": check}],
                                answer=f"{held['name']}은(는) 다시 확인해 보니 그 날짜에 남은 객실이 없어요. 일정은 그대로 두었어요. "
                                       "다른 후보를 고르시거나 「바꿔 줘」라고 하시면 새로 찾아 드릴게요.")
        previous = {**applied_record(item), **({k: item.detail["chosen"][k] for k in ("source", "price_per_night", "link")
                                               if k in item.detail.get("chosen", {})})}
        remaining = [option for option in alternates if option is not held] + [previous]
        detail = {**item.detail, "alternates": remaining, "other_options": [option["name"] for option in remaining],
                  "chosen": pick, "booked": False, "customer_requested": True}
        cause = with_request({"category": "customer_request", "type": "alternate", "from": item.title, "to": pick["name"],
                              "message": task.input_text}, task.context.current_state.get("request_id"))
        text = (f"요청하신 대로 {item.title} 대신 {pick['name']}(으)로 바꿨습니다. 아직 예약 전이에요"
                + (f" — 예약은 이 링크에서 해 주세요: {pick['link']}" if pick.get("link") else "") + "." + _price_note(check))
        replacement = replace(item.replaced_by(place=None, title=pick["name"], detail=detail), place_id=None, place=None)
        change = ItineraryChange(reason="customer_request", causes=[cause],
                                 notice={"text": text, "language": "ko", "causes": [cause],
                                         "changed": {"from": item.title, "to": pick["name"], "at": item.starts_at.isoformat()},
                                         "other_options": detail["other_options"], "replay": False},
                                 replacements={item.item_id: replacement},
                                 summary={"to": pick["name"], "key": pick["key"], "price_check": check})
        return self.settle(task, ctx, change)

    def _recheck(self, task: TeamTask, ctx: dict[str, Any], item: Any,
                 pick: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """고른 숙소의 1박 값을 다시 본다(마이리얼트립 상세 1번). → (바꿀 때 쓸 후보, 확인 결과).

        확인 결과 `status`: `same` · `changed`(새 값으로) · `gone`(그 날짜 객실 없음 · 매진) · `unchecked`(구글 호텔 · 상세를 못 읽음 · 조건 모름)."""
        before = pick.get("price_per_night")
        source, _, gid = str(pick.get("key") or "").partition(":")
        query = item.detail.get("query") or self._stay_query(item, ctx["trip"])
        if source == "google" and pick.get("property_token"):
            return self._recheck_google(task, ctx, pick, query)
        if source != "myrealtrip" or not gid:
            return pick, {"status": "unchecked", "before": before, "now": None, "reason": "no_recheck_tool"}
        if not query:
            return pick, {"status": "unchecked", "before": before, "now": None, "reason": "no_query"}
        detail = self._read(task, "read.stay_detail", {"gid": gid, "check_in": query["check_in"], "check_out": query["check_out"],
                                                       "adults": query["adults"], "children": None}, ctx["seen"])
        if detail and detail.get("cooldown_seconds"):
            detail = None
        ctx["evidence"] = self._evidence(task, source_id=f"read.stay_detail:{gid}:recheck", claim="고른 숙소 가격 재확인(마이리얼트립 상세)",
                                         value=detail, base=ctx["evidence"])
        if detail is None:
            return pick, {"status": "unchecked", "before": before, "now": None, "reason": "detail_unreadable"}
        if detail.get("sold_out") or detail.get("no_rooms"):
            return pick, {"status": "gone", "before": before, "now": None}
        now = detail.get("price_per_night")
        if not isinstance(now, (int, float)) or before is None:
            return pick, {"status": "unchecked", "before": before, "now": now, "reason": "no_price"}
        status = "same" if now == before else "changed"
        check = {"status": status, "before": before, "now": now, "basis": pick.get("price_basis") or "list"}
        return ({**pick, "price_per_night": now, "price_basis": "detail"} if status == "changed" else pick), check

    def _recheck_google(self, task: TeamTask, ctx: dict[str, Any], pick: dict[str, Any],
                        query: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
        """`[2026-10-13]` 구글 호텔 후보를 고를 때 — 숙소 상세(`read.stay_google_details`, SerpApi 1회)를 다시 읽어 **판매처 최저가끼리** 비교한다.
        전에는 다시 볼 도구가 없어 「확인 못 함」이었다. 판매처가 하나도 없으면 「없어졌다」고 하지 않고 확인 못 함(`no_price`) — 구글 상세에
        가격이 없는 까닭(매진 · 표시 안 됨)을 가를 수 없다. 바뀌었으면 판매처 · 예약 버튼 · 「1박 ○원~」도 새 값으로."""
        # `[2026-10-13]` 판매처 최저가끼리 — 보여 준 판매처(`sellers`)의 최저가가 기준이다. `price_from` 은 구글 목록가까지 넣은 최저라
        #   기준이 다르다(☆x600 확인 — 목록 173,845원 · 판매처 최저 176,766원이 「바뀜」으로 나왔다). 판매처를 못 읽었던 후보만 `price_from`
        shown = [s.get("price_per_night") for s in pick.get("sellers") or [] if isinstance(s.get("price_per_night"), (int, float))]
        before = min(shown) if shown else (pick.get("price_from") if pick.get("price_from") is not None else pick.get("price_per_night"))
        if not query:
            return pick, {"status": "unchecked", "before": before, "now": None, "reason": "no_query"}
        token = pick["property_token"]
        got = self._read(task, "read.stay_google_details", {"tokens": [token], "keyword": query["keyword"], "check_in": query["check_in"],
                                                            "check_out": query["check_out"], "adults": query["adults"]}, ctx["seen"])
        ctx["evidence"] = self._evidence(task, source_id="read.stay_google_details:recheck", claim="고른 숙소 가격 재확인(구글 호텔 상세)",
                                         value=got, base=ctx["evidence"])
        detail = ((got or {}).get("details") or {}).get(token)
        if not detail:
            return pick, {"status": "unchecked", "before": before, "now": None, "reason": "detail_unreadable"}
        sellers = _sellers(detail)
        if not sellers or before is None:
            return pick, {"status": "unchecked", "before": before, "now": None, "reason": "no_price"}
        now = sellers[0]["price_per_night"]
        status = "same" if now == before else "changed"
        check = {"status": status, "before": before, "now": now, "basis": "sellers"}
        if status == "same":
            return pick, check
        direct = next((seller for seller in sellers if seller.get("link")), None)
        fresh = {**pick, "sellers": sellers, "price_from": now, "price_basis": "sellers",
                 **({"link": direct["link"], "link_seller": direct["name"]} if direct else {})}
        return fresh, check

    @staticmethod
    def _stay_query(item: Any, trip: dict[str, Any]) -> dict[str, Any] | None:
        """숙소 항목 · 여행 → 검색 조건. 하나라도 모르면 `None`(지어내지 않는다)."""
        check_in = item.starts_at.astimezone(SEOUL).date()
        check_out = item.ends_at.astimezone(SEOUL).date() if item.ends_at else None
        if check_out is None or check_out <= check_in:
            check_out = check_in + timedelta(days=1)   # 끝이 없거나 같은 날이면 1박으로 본다 — 답과 기록에 날짜가 그대로 보인다
        place = item.place or {}
        keyword = item.detail.get("area") or place.get("district") or place.get("name")
        adults = trip.get("party_size")
        if not keyword or not isinstance(adults, int) or adults < 1:
            return None
        where = _coords(place)
        domestic = item.detail.get("domestic")
        if domestic is None and where is not None:
            domestic = _KOREA[0][0] <= where[0] <= _KOREA[0][1] and _KOREA[1][0] <= where[1] <= _KOREA[1][1]
        keyword = str(keyword)
        if where is not None and "서울" not in keyword \
                and _SEOUL[0][0] <= where[0] <= _SEOUL[0][1] and _SEOUL[1][0] <= where[1] <= _SEOUL[1][1]:
            # `[2026-10-15 ST4F-557]` 장소 이름에 도시가 없으면(「더플라자호텔」) 다른 도시 후보가 왔다 — x600 실서버 광주 268km.
            #   이름에 「서울」이 든 「롯데호텔 서울」은 0.1 · 11.9km 였다. 숙소 좌표가 서울이면 검색어 앞에 「서울」을 붙인다
            #   (「서울 더플라자호텔」로 찾았을 때 결과는 확인 안 함). 고르는 순서(가까운 곳 먼저 · 없으면 먼 곳을 거리와 함께)는 그대로
            keyword = f"서울 {keyword}"
        return {"keyword": keyword, "check_in": check_in.isoformat(), "check_out": check_out.isoformat(),
                "adults": adults, "domestic": domestic}

    # ── 부품 ────────────────────────────────────────────────────
    @staticmethod
    def _google_block(google: dict[str, Any] | None, shown_names: list[str], links: list[dict[str, str]],
                      center: dict[str, Any] | None = None, *, wants: Wants | None = None, anchor: dict[str, Any] | None = None,
                      max_price: int | None = None, limit: float | None = None, base: dict[str, Any] | None = None,
                      label: str = "일정 가운데에서", query: str | None = None, walker: Any = None, seoul: bool = False,
                      dates: dict[str, str] | None = None, adults: int | None = None, children: int = 0,
                      trace: list[dict[str, Any]] | None = None) -> list[str]:
        """구글 호텔 쪽 줄 + 다른 곳에서 보기 링크. 이미 보인 이름(이름 핵심 `_core` — 공백 · 「호텔」 · 「서울」 무시)과 숙박 공유(vacation rental)는 뺀다.

        ★숙박 공유를 빼는 까닭 — ☆2026-10-10 14:21 playdata 「서울 명동」 앞의 셋이 숙박 공유(Bluepillow · Vio)였고 평점 · 후기가 없었다.
        ★가격이 없는 곳도 뺀다 — ☆15:37 「지요크 명동」이 가격 · 링크 없이 왔다(비교에 쓸 수 없다).
        ★링크가 없는 곳도 뺀다 — ☆17:02 「필스테이 명동 메트로」가 가격은 있고 링크 없이 왔다(고객이 들어갈 곳이 없다. 구글 페이지 줄은 남는다).
        ★일정 가운데가 쓸 만하면(`center.usable`) 구글 목록(최대 20곳) 안에서 **가까운 순**으로 고른다. 좌표 없는 곳은 뒤로.
        ★`[2026-10-15 검수 D]` 더 빼는 것 — 1박 상한을 넘는 곳(☆L05 50,135원), 기준점(`anchor`)에서 `REGION_KM` 넘게 먼 곳(☆L03 속초 · L05 제주),
          거리 조건(`limit`)보다 먼 곳, 이름 · 성급이 원하는 유형 · 성급과 맞지 않는 곳. 유형은 이름에 보일 때만 뺀다(검색어에 유형을 넣어 찾으므로 —
          ☆L06 「청춘재」는 이름에 「한옥」이 없지만 한옥이었다). 「싼 곳」이면 1박 가격 낮은 순, 거리 조건이 있으면 기준점에서 가까운 순.
          링크는 구글 호텔에서 그 이름으로 찾은 화면을 먼저, 숙소 자체 사이트를 뒤에(☆L01 「호텔케이월드」 사이트가 열리지 않았다).
        """
        wants = wants or Wants()
        lines: list[str] = []
        if google is None:
            lines.append("구글 호텔 비교는 받지 못했습니다(조회 실패).")
        else:
            # `[2026-10-12]` 이름 핵심(`_core`)으로 비교 — 「밀리오레 호텔 서울 명동」(마이리얼트립)과 「밀리오레호텔 명동」(구글)은 같은 곳
            seen = {_core(name) for name in shown_names if _core(name)}
            # `[2026-10-16 사용자 판정 5차 L06]` 「Hanok」처럼 외국어로 한옥이라고 적힌 곳도 넣는다 — 한옥을 찾을 때는
            #   이름에 한옥 · hanok 이 보이는 숙박 공유(vacation rental)도 남긴다(한옥 스테이가 숙박 공유로 오는 일이 많다고 봄 — 확인 안 함)
            hanok = wants.kind == "한옥"
            rows = []
            for stay in google.get("stays") or []:
                rental = stay.get("type") == "vacation rental"
                why = ("vacation_rental" if rental and not (hanok and "한옥" in stay_kinds(None, stay.get("name"))) else
                       "no_price" if stay.get("price_per_night") is None else "no_link" if not stay.get("link") else
                       "shown" if _core(stay["name"]) in seen else None)
                if why:
                    if trace is not None:
                        trace.append({"name": stay.get("name"), "why": why})
                    continue
                rows.append(stay)
            picks, dropped, restricted = [], 0, 0
            # 걸어서 몇 분을 계산기로 볼 때는 직선 상한 대신 넉넉한 거리(걸어서 15분이 넘을 게 뻔한 곳만)로 먼저 거른다
            straight_cap = (2.0 if walker is not None else limit) if limit is not None else None
            for stay in rows:
                where = _coords(stay)
                gap = _km(anchor["latitude"], anchor["longitude"], *where) if anchor and where else None
                if guest_block(stay.get("name"), wants.guest, children=children):
                    restricted += 1                  # `[2026-10-15 · 10-16 사용자 판정 L05]` 묵을 분에게 맞지 않는 여성 · 외국인 전용 등
                    if trace is not None:
                        trace.append({"name": stay.get("name"), "why": "restricted"})
                    continue
                why = (price_reason(wants, stay["price_per_night"], max_price)
                       or ("far" if gap is not None and (gap > REGION_KM or (straight_cap is not None and gap > straight_cap)) else
                           "region" if seoul and anchor is None and _outside_seoul(where) else None)
                       or kind_reason(wants, stay_kinds(None, stay.get("name")), strict=False)
                       or stars_reason(wants, stay_stars(None, stay.get("hotel_class"))))
                if why:
                    dropped += 1
                    if trace is not None:
                        trace.append({"name": stay.get("name"), "why": why})
                    continue
                picks.append(stay)
            if base is None and center and center["usable"]:
                base = center
            near = base is not None and (limit is not None or base is center)
            if wants.cheapest:
                picks.sort(key=lambda stay: stay["price_per_night"])
            elif near:
                picks.sort(key=lambda stay: (_distance(base, stay) is None, _distance(base, stay) or 0.0))
            walked: dict[int, int] = {}
            if walker is not None:
                kept, checks = [], 0
                for stay in picks:
                    if len(kept) >= GOOGLE_SHOWN:
                        break
                    where = _coords(stay)
                    minutes = walker(where) if where is not None and checks < WALK_CHECKS else None
                    checks += 1 if where is not None else 0
                    gap = _km(anchor["latitude"], anchor["longitude"], *where) if anchor and where else None
                    cap_min, cap_km = _walk_cap(wants)
                    if (minutes is not None and minutes > cap_min) or (minutes is None and gap is not None and gap > cap_km):
                        dropped += 1
                        if trace is not None:
                            trace.append({"name": stay.get("name"), "why": "walk"})
                        continue
                    if minutes is not None:
                        walked[id(stay)] = minutes
                    kept.append(stay)
                picks = kept
            picks = picks[:GOOGLE_SHOWN]
            if picks:
                order = "1박 가격 낮은 순" if wants.cheapest else (
                    ("일정 장소 가운데에서 가까운 순" if base is center else f"{label} 가까운 순") if near else "구글 순서")
                asked = f", 검색어 「{query}」" if query else ""
                lines.append(f"구글 호텔에서 본 같은 조건 숙소({order}, " + ("숙박 공유는 한옥만" if hanok else "숙박 공유 제외") + f"{asked}):")
                for stay in picks:
                    rating = (f"평점 {stay['rating']:.1f}/5" + (f"(후기 {stay['review_count']:,})" if isinstance(stay.get("review_count"), int) else "")
                              if stay.get("rating") else "평점 없음")
                    star = f"{stay['hotel_class']}성급 · " if stay.get("hotel_class") else ""
                    far = _distance(base, stay)
                    minutes = walked.get(id(stay))
                    rule = (" · 숙박 공유" if stay.get("type") == "vacation rental" else "") + \
                        (f" · 이용 조건 {restriction(stay.get('name'))}(묵을 분과 맞음)" if restriction(stay.get("name")) else "")
                    where = ((f" · {label} 걸어서 {minutes}분({far}km)" if minutes is not None and far is not None
                              else f" · {label} {far}km" if far is not None else " · 거리 모름") if base is not None else "")
                    lines.append(f"   · {stay['name']} — {star}1박 {_won(stay.get('price_per_night'))} · 전체 {_won(stay.get('total_price'))} · "
                                 f"{rating}{where}{rule}: 구글 호텔 "
                                 f"{_google_page(stay['name'], dates, adults, token=stay.get('property_token'), area='서울' if seoul else None)}"
                                 f" · 숙소 사이트 {stay.get('link')}")
                # `[2026-10-15 사용자 판정 L01 · L12]` 구글 호텔 화면 주소에는 날짜 · 인원이 넘어가지 않는다 —
                #   ☆18시대 playdata 내장 브라우저: `checkin` · `checkout` · `adults` 를 붙여도 그 화면은 다른 날짜 · 2명으로 열렸다
                # `[2026-10-15]` 안내 대신 링크에 날짜 · 인원을 싣는다(`google_ts`) — 최소 숙박 일수는 링크로 못 거른다
                lines.append("   (구글 호텔 링크는 날짜 · 인원을 채워 엽니다 — 최소 숙박 일수 같은 조건은 그 화면에서 확인해 주세요.)")
            elif dropped:
                lines.append(f"구글 호텔 목록 {len(rows)}곳은 다른 지역이거나 말씀하신 조건(가격 · 유형 · 성급 · 거리)에 맞지 않아 싣지 않았습니다.")
            if restricted:
                lines.append(f"구글 호텔에서 {_restricted_text(wants.guest)} {restricted}곳은 뺐어요"
                             + ("." if not wants.guest.missing() else "(성별 · 국적 · 나이를 알려 주시면 다시 볼게요)."))
            if google.get("page"):
                searched = query or google.get("keyword")
                if dates and adults and searched:
                    lines.append(f"구글 호텔 검색 결과 페이지(날짜 · 인원 채움): {_google_page(searched, dates, adults)}")
                else:
                    lines.append(f"구글 호텔 검색 결과 페이지(날짜는 그 화면에서 다시 고르셔야 할 수 있습니다): {google['page']}")
        if links:
            lines += ["같은 조건으로 다른 곳에서 보기(가격은 그 사이트에서 확인):",
                      *[f"   · {link['name']}" + (f"({link['note']})" if link.get("note") else "") + f": {link['url']}" for link in links]]
        return lines

    def _trip(self, task: TeamTask, seen: set[str]) -> tuple[dict[str, Any] | None, list[Evidence], list[dict[str, Any]]]:
        """Case 에 여행이 붙어 있으면 그 일정을 모델에 줄 요약으로 + 좌표 있는 장소들(날 · 위도 · 경도, 모델에는 주지 않는다).
        없거나 못 읽으면 `None` · 빈 목록 — 없이 해석한다. 좌표는 일정 항목의 `place`(장소 표) 값이다."""
        ref = task.context.current_state.get("subject_ref") or {}
        evidence = list(task.context.evidence)
        if ref.get("kind") != "trip" or not ref.get("id"):
            return None, evidence, []
        view = self._read(task, "read.itinerary", {"trip_id": ref["id"]}, seen)
        evidence = self._evidence(task, source_id="read.itinerary", claim="현재 일정 버전", value=view, base=evidence)
        if not view:
            return None, evidence, []
        points = []
        for item in view.get("items") or []:
            where = _coords(item.get("place"))
            if where is not None:
                points.append({"day": str(item.get("starts_at") or "")[:10] or None, "latitude": where[0], "longitude": where[1],
                               "title": item.get("title")})
        days = sorted(str(item["starts_at"])[:10] for item in view.get("items") or [] if item.get("starts_at"))
        return {"party_size": (view.get("trip") or {}).get("party_size"),
                "first_day": days[0] if days else None, "last_day": days[-1] if days else None,
                "places": [str(item.get("title")) for item in view.get("items") or [] if item.get("title")]}, evidence, points

    @staticmethod
    def _center_line(center: dict[str, Any] | None) -> list[str]:
        if center is None:
            return []
        span = "이 숙박 기간" if center["window"] else "여행 전체"
        if not center["usable"]:
            return [f"{span} 일정 장소 {center['places']}곳이 넓게 흩어져 있어(가운데에서 가장 먼 곳 {center['spread_km']}km) 거리는 재지 않았습니다."]
        return [f"거리는 {span} 일정 장소 {center['places']}곳의 가운데에서 잰 직선거리입니다(이동 시간 아님)."]

    @staticmethod
    def _line(number: int, stay: dict[str, Any], detail: dict[str, Any] | None, far: float | None = None,
              link: str = "", label: str = "일정 가운데에서", *, unknown_far: bool = False, walk_min: int | None = None) -> str:
        # 후기가 없는 곳은 평점이 0.0 으로 온다(2026-10-07 17:48 playdata) — 0점이 아니라 평점이 없는 것이다
        rating = f"평점 {stay['rating']}/5" + (f"(후기 {stay['review_count']:,})" if stay.get("review_count") else "") \
            if stay.get("rating") else "평점 없음"
        # `[2026-10-15 검수 D]` 거리 조건이 있는데 위치를 못 찾은 곳은 그렇다고 적는다(가깝다고 하지 않는다)
        distance = (f" · {label} 걸어서 {walk_min}분({far}km)" if walk_min is not None and far is not None
                    else f" · {label} {far}km" if far is not None else (" · 거리 확인 안 함" if unknown_far else ""))
        if detail is None:
            about = f" · {stay['description']}" if stay.get("description") else ""
            return (f"{number}. {stay['name']} — 1박 {_won(stay.get('price_per_night'))}(목록 가격 · 객실은 링크에서 확인) · {rating}{about}"
                    f"{distance} · {link or '링크 없음'}")
        return (f"{number}. {stay['name']} — 1박 {_won(detail.get('price_per_night'))} · 전체 {_won(detail.get('total_price'))}(세금 포함) · "
                f"{rating} · {detail.get('address') or '주소 모름'}{distance}"
                + f" · {detail.get('link') or '링크 없음'}")

    def _respond(self, task: TeamTask, evidence: list[Evidence], decision: dict[str, Any], answer: str, *,
                 wants: Wants | None = None, near_done: bool = False) -> TeamResult:
        # `[2026-10-11]` 고객이 말했지만 우리가 받는 칸이 없는 요청(모델이 문장에서 그대로 옮긴 조각, 서버가 문장에 있는지 확인함)은
        #   조용히 버리지 않고 답 끝에 적는다 — ☆10-11 사용자 문장 측정: 「욕조 있는」 「얼리체크인」 「저가항공 말고」가 말없이 사라졌다
        # `[2026-10-15 검수 D]` 서버 규칙(`wants.py`)이 반영한 조각(유형 · 성급 · 싼 순, 기준점을 찾았으면 거리)은 이 목록에서 뺀다
        others = (decision.get("interpretation") or {}).get("other_requests") or []
        if wants is not None:
            others = strip_handled(others, wants, near_done=near_done)
        if others:
            answer = answer + "\n말씀하신 조건 중 아직 반영하지 못한 것: " + " · ".join(f"「{item}」" for item in others) \
                + " — 링크한 화면에서 직접 확인해 주세요."
        return self._result(task, outcome="completed", confidence=1.0, evidence=evidence,
                            next_action=NextAction.RESPOND, answer=answer[:6000], decisions=[decision])


__all__ = ["LodgingTeam", "PROMPT_KEY"]
