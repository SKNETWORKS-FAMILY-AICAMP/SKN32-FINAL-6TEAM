# -*- coding: utf-8 -*-
"""읽은 값 → 등록 몸통. `[2026-09-27]` 설계서 §3-7 · §3-8 · §5

    effective   한 판(revision)의 값 줄들 → (원본, 필드)마다 **마지막 값 하나**(고객이 고친 값이 뒤에 온다)
    assemble    → (`CreateTrip` 몸통, 막는 문제들). 문제가 하나라도 있으면 등록하지 않는다

★빈칸 채우기(§3-7) — 시각이 없는 항목은 **규칙으로 배치**하고 그렇게 했다고 적는다(`method: rule`):
    끼니  원문 줄에 끼니 말이 있으면 그 시각 — 아침·조식 08:00 · 점심·중식 12:00 · 저녁·석식 18:00
          ☆2026-09-27 실제 화면: 「점심은 토속촌에서」가 18:00 에 놓였다(끼니 말을 안 봤고, 원문 순서가 아니라
            항목 번호 순서로 채웠다 — 모델이 가리킨 항목은 번호가 규칙 항목 뒤에 붙는다)
    식사  (끼니 말이 없으면) 앞 항목이 12시 전에 끝나면 12:00, 아니면 18:00
    활동  앞 항목 끝 + 여유(`MOVE_BUFFER_MIN`), 첫 항목이면 하루 첫 활동 시각(`planner.DAY_START`)
    끝    적혀 있지 않으면 시작 + 활동 90분 · 식사 60분(`planner`) — 다음 항목 시작을 넘지 않게 자른다
★필수값 검사(§3-7) — 판정기 `check_itinerary` 는 **값이 없는 칸을 통과시킨다.** 그래서 앞에서 막는다:
    제목 없음 · 날짜 없음 · 장소를 못 정함(고객이 「장소 없음」으로 두면 통과) · 예약번호가 있는데 시각이 규칙 배치
★근거(§5) — 항목마다 `detail.provenance` 에 필드별 방법과 근거(원문 줄·조각 · 조회 출처)를 싣는다.
★예약번호(§3-8) — `detail.booking` 에 싣는다. **예약 표(`bookings`)는 만들지 않는다** — 업체 확인 없는 번호를
  「확정 예약」으로 적게 된다(업체 연결은 Booking Handoff, MVP 밖). 대신 이 표시가 있는 항목은
  `pending.protected_reason` 이 「booked」로 보고 **바꾸기 전에 묻는다.**
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
import re
from typing import Any
from zoneinfo import ZoneInfo

from app.domains.travel_ops.components.planning import planner

from .rules import meal_mention
from . import schedule_cards
from .span_segments import split_segments

KST = ZoneInfo("Asia/Seoul")
MAX_PARTY = 4                      #: 상품 범위 — 서울 · 최대 7일 · 4인
_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
#: 제목으로 쓰지 않는 첫 줄 — 일차 머리줄
_DAY_HEADING = re.compile(r"^\s*(\d+\s*일\s*차|day\s*\d+)", re.IGNORECASE)
#: 외부 서비스에서 온 장소 — 등록할 때 그 여행 전용 행이 된다(`trip_api.EXTERNAL_PLACE_SOURCES`)
_SOURCE_ATTRS = {"tour_api": "source_content_id",
                 # ★요식 원장도 관광공사 ID 를 싣는다 — 판정 때 그 ID 로 원장 가게와 다시 잇는다(220)
                 "dining_ledger": "source_content_id",
                 # ★`[2026-10-05]` 인허가(사업자 등록) 자료에서 찾은 식당 — 관광공사 번호가 아니라 인허가 관리번호다(영업시간은 모른다)
                 "dining_license": "license_mgt_no"}
#: 원문 줄의 끼니 말 → 시각. 우리가 고른 값(planner 의 LUNCH_FROM · DINNER_FROM 과 같다)
#: `[2026-10-13 사용자 결정 — 숙소 항목 B안]` 숙소 한 항목 = 한 숙박. 체크인 줄이 시작, 그 뒤 체크아웃 줄이 끝(다른 날)이다
_CHECK_IN = re.compile(r"체크\s*인|check[\s-]*in", re.IGNORECASE)
_CHECK_OUT = re.compile(r"체크\s*아웃|check[\s-]*out|퇴실", re.IGNORECASE)
#: 적혀 있지 않을 때 두는 체크인 · 체크아웃 시각 — 국내 숙소의 흔한 시각. 규칙으로 채웠다고 적는다(`filled`)
STAY_IN, STAY_OUT = "15:00", "11:00"
_MEAL_TIMES = (("아침", "08:00"), ("조식", "08:00"), ("점심", "12:00"), ("중식", "12:00"),
               ("저녁", "18:00"), ("석식", "18:00"))


@dataclass
class Problem:
    code: str
    field: str
    message: str
    source_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "field": self.field, "message": self.message, "source_id": self.source_id}


@dataclass
class Assembled:
    body: dict[str, Any]
    problems: list[Problem] = field(default_factory=list)
    filled: list[dict[str, Any]] = field(default_factory=list)     # 규칙으로 채운 칸 — 화면이 배지로 보인다
    #: 「일정 짜 줘」 — 일정 생성기에 넘길 기본값(화면이 미리 채우고 고객이 고친다). 모르는 값은 None
    plan: dict[str, Any] = field(default_factory=dict)
    #: `[2026-10-16 D-025 후속]` 이해 에이전트가 읽은 성향 · 조건 → 담당 열쇠(`reading_prefs.carry`). 등록 직전 `reading_prefs.apply` 가 빈 자리에만 옮긴다
    reading: list[dict[str, Any]] = field(default_factory=list)


def effective(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """(원본, 필드)마다 마지막 값 하나. `claims` 는 만든 순서여야 한다(`view` 가 그렇게 읽는다)."""
    last: dict[tuple[Any, str], dict[str, Any]] = {}
    for claim in claims:
        last[(claim["source_id"], claim["field"])] = claim
    return list(last.values())


@dataclass
class Collected:
    """한 판의 값 줄 → 항목 줄들(빈칸을 규칙으로 채운 뒤, 날짜·시각 순). ★확인 화면의 검사(`review.py`)와 등록 몸통(`assemble`)이 **같은 줄**을 본다."""

    rows: list[dict[str, Any]]
    filled: list[dict[str, Any]]
    problems: list[Problem]
    trip: dict[str, dict[str, Any]]
    first_day: date | None


def collect(*, sources: list[dict[str, Any]], claims: list[dict[str, Any]]) -> Collected:
    """`sources` = 원본 행(`position` 순), `claims` = 그 판의 값 줄(만든 순서). 고객이 뺀 항목(`removed`)은 들어오지 않는다.

    각 줄(`rows[]`)은 `index`(원본 안 항목 번호 — 고치는 칸 이름 `items[n]` 의 n) · `source_id` · `title` · `date` · `start` · `end` · `kind` ·
    `place`(좌표를 아는 장소 값 또는 None) · `claims`(그 항목의 칸별 값 줄 — 근거·확인 필요·메모) · `locked`(고객이 「꼭 넣을 일정」으로 고정) 을 든다."""
    original_titles = {(c["source_id"], c["field"]): c.get("evidence") or {} for c in claims
                       if c["field"].endswith(".title") and isinstance((c.get("evidence") or {}).get("start"), int)}
    missing_cards = schedule_cards.omissions(sources, claims)
    claims = effective(claims)
    trip = {c["field"][5:]: c for c in claims if c["field"].startswith("trip.")}
    problems: list[Problem] = [Problem("source_item_missing", "reading.source_items",
                                     f"원문 일정이 읽기 결과에서 빠졌어요: {card['title']}", str(card["source_id"]))
                               for card in missing_cards]
    rows: list[dict[str, Any]] = []
    all_rows: list[tuple[dict[str, Any], bool]] = []
    first_day = _date_value(trip.get("first_day"))
    for source in sources:
        mine = [c for c in claims if c["source_id"] == source["source_id"]]
        marks = _day_marks(mine)
        by_index: dict[int, dict[str, dict[str, Any]]] = {}
        for claim in mine:
            if claim["field"].startswith("items["):
                index = int(claim["field"][6:claim["field"].index("]")])
                by_index.setdefault(index, {})[claim["field"][claim["field"].index("]") + 2:]] = claim
        for index in sorted(by_index):
            fields = by_index[index]
            removed = (fields.get("removed") or {}).get("value") is True
            # 삭제한 항목도 원문 경계를 정할 때는 남긴다. 그 항목의 수식어가
            # 살아 있는 앞 항목으로 다시 들어오면 안 된다.
            all_rows.append((_row(source, index, fields, marks, first_day, [] if removed else problems), removed))
    _split_shared_lines([row for row, _ in all_rows], original_titles)
    rows = [row for row, removed in all_rows if not removed]
    # `[2026-10-26 사용자 지시 — 호텔 종류 확인]` 답하지 않은 종류 확인 질문은 등록을 막는다(계산은 1안으로 한다 — Codex 검토)
    from .interpretations import kind_problems

    problems += [Problem("kind_unanswered", f"items[{index}].kind", text, sid) for sid, index, text in kind_problems(claims, rows)]
    # ★시각이 없는 것은 **원문 순서** 안에서 규칙으로 배치한다 — 시각순으로 먼저 세우면 시각 없는 「점심」이
    #   그날 마지막 항목 뒤로 밀려 저녁이 된다. 채운 뒤에 날짜·시각 순으로 세운다.
    rows.sort(key=lambda r: (r["date"] or "9999", r["order"]))       # order = (원본, 원문 줄, 번호)
    filled: list[dict[str, Any]] = []
    rows = _stays(rows, filled, problems)
    _fill_times(rows, filled, problems)
    _fit_day_end(rows, claims, filled, problems)
    rows.sort(key=lambda r: (r["date"] or "9999", r["start"] or "99:99", r["order"]))
    return Collected(rows=rows, filled=filled, problems=problems, trip=trip, first_day=first_day)


def assemble(*, intake_id: str, revision: int, sources: list[dict[str, Any]],
             claims: list[dict[str, Any]]) -> Assembled:
    """`sources` = 원본 행(`position` 순), `claims` = 그 판의 값 줄(만든 순서)."""
    got = collect(sources=sources, claims=claims)
    rows, filled, problems, trip, first_day = got.rows, got.filled, got.problems, got.trip, got.first_day
    # 지역만 적은 줄(「인사동 · 점심」) — 처음 읽은 장소 값 줄이 이름 없는 줄이다. 서버가 채운 그 줄은 적힌 이름을 둔다(`_item_title`)
    nameless = {(str(c["source_id"]), c["field"]) for c in claims
                if c["field"].endswith(".place") and (c.get("evidence") or {}).get("method") == "nameless"}
    places: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for seq, row in enumerate(rows, start=1):
        key = None
        if row["place"]:
            key = f"p{len(places) + 1}"
            places.append(_place_in(key, row["place"], row["kind"]))
        detail: dict[str, Any] = {"provenance": row["provenance"],
                                  "intake": {"intake_id": intake_id, "revision": revision,
                                             "source_id": row["source_id"], "index": row["index"]}}
        if row.get("role") == "origin":
            detail["origin"] = True
        if row["booking_no"] or row["booked"] is True:
            detail["booking"] = {"declared_by": "customer_plan",
                                 **({"booking_no": row["booking_no"]} if row["booking_no"] else {})}
        if row["locked"]:
            # ★`[2026-10-02 사용자 지시]` 고객이 「꼭 넣을 일정」으로 고정했다 — 등록되면 **감시 루프가 다시 자동으로 바꾸지 않고**
            #   바꾸기 전에 묻는다(`pending.protected_reason` 「customer_pinned」 · `trip_watch`). 되살린 항목과 같은 표시다.
            detail["customer_pinned"] = True
        if row["date"] and row["start"]:
            items.append({"seq": seq, "kind": row["kind"], "place": key,
                          "title": _item_title(row, filled=(row["source_id"], f"items[{row['index']}].place") in nameless),
                          "starts_at": _at(row["date"], row["start"]).isoformat(),
                          # 숙소는 끝이 다른 날이다(체크아웃 날 · `_stays`)
                          "ends_at": _at(row.get("end_date") or row["date"], row["end"]).isoformat() if row["end"] else None,
                          "detail": detail})
    body = {"request_id": f"intake:{intake_id}:r{revision}", "title": _title(trip, sources),
            "locale": "ko", "party_size": _int_value(trip.get("party_size")),
            "places": places, "items": items}
    if trip.get("constraints") is not None:
        body["constraints"] = deepcopy(trip["constraints"]["value"])
    from . import taxi_pricing
    pricing = taxi_pricing.from_trip(trip)
    if pricing is not None:
        body["constraints"] = taxi_pricing.constraints(pricing, body.get("constraints"))
    plan = _plan_basis(trip, rows, sources, first_day)
    if not rows and not plan["requested"]:
        problems.append(Problem("no_items", "items", "읽은 일정이 없습니다 — 항목을 하나 이상 넣어 주세요"))
    party = body["party_size"]
    if party is not None and not 1 <= party <= MAX_PARTY:
        # ★상품은 최대 4인(루트 CLAUDE.md 「가격 · 비용」). 범위 밖 인원은 계약 오류로 새지 않게 여기서 막는다
        problems.append(Problem("party_size_out_of_range", "trip.party_size",
                                f"인원이 {party}명으로 읽혔습니다 — 1~{MAX_PARTY}명으로 고쳐 주세요"))
    from . import reading_prefs
    return Assembled(body=body, problems=problems, filled=filled, plan=plan, reading=reading_prefs.carry(claims))


def _item_title(row: dict[str, Any], *, filled: bool = False) -> str:
    """등록할 일정 이름. `filled` = 지역만 적은 줄이었다(처음 읽은 장소 값 줄이 `nameless` — `assemble`).

    ★`[2026-10-25 사용자 결정]` 장소가 **바뀐** 일정은 **그 장소 이름**이다 — 고객이 고른 곳(장소 값 줄 `method: customer` — 후보 「○○로 바꾸기」 · 검색 ·
    「「…」 맞아요」)과 「전체 자동 추천」이 바꾼 곳(근거 `via: autofix`). 확인 화면 카드 · 수정 모드 완료(`reopen.py`)와 같다(원래 적힌 말은 `provenance.title`).
    지역만 적어 서버가 채운 곳(`filled` + `via: autofix` — 「인사동 · 점심 → 양반댁」)은 적힌 이름 그대로 두고 여행 화면이 장소 이름을 그 아래 줄에 보인다.
    숙소는 제목이 「체크인」을 말하므로 그대로다. 고객이 제목을 직접 고쳤으면(제목 값 줄도 `customer`) 그 제목이 먼저다.
    ☆전에는 적힌 이름만 써서 휴무 대안 「쌈지길로 바꾸기」 · 전체 자동 추천 뒤 여행 화면이 「창덕궁」 + 아래 「쌈지길」이었다."""
    place = row.get("place") or {}
    if row["title"] in ("거기", "여기", "식사", "밥") and row["kind"] == "dining":
        return place.get("name", "식사") + " 식사"
    claims = row.get("claims") or {}
    claim = claims.get("place") or {}
    autofix = (claim.get("evidence") or {}).get("via") == "autofix"
    changed = claim.get("method") == "customer" and not (autofix and filled)
    written = (claims.get("title") or {}).get("method") == "customer"
    if changed and not written and row["kind"] in ("activity", "dining") and place.get("name") and place["name"] != row["title"]:
        return str(place["name"])
    return row["title"] or "(제목 없음)"


# ── 항목 하나 ─────────────────────────────────────────────────────
def _row(source, index, fields, marks, first_day, problems) -> dict[str, Any]:
    def value(name):
        return (fields.get(name) or {}).get("value")

    where = f"items[{index}]"
    sid = str(source["source_id"])
    title = (value("title") or "").strip() or None
    if not title:
        problems.append(Problem("no_title", f"{where}.title", "이 항목의 이름이 없습니다", sid))
    line = min((c["evidence"].get("line") or 0 for c in fields.values() if c["evidence"].get("line")), default=0)
    day, marked = _day_for(line, marks)
    when = value("date") or marked
    date_claim = fields.get("date")
    if first_day and (date_claim is None or date_claim["method"] != "customer") and \
            (not when or (date_claim and date_claim["evidence"].get("how") in ("unknown", "day_offset"))):
        # ★고객이 첫날을 알려 줬다 — 적힌 날짜가 없는 항목은 첫날 + (일차 − 1)
        when = (first_day + timedelta(days=(day or 1) - 1)).isoformat()
    if when and when.startswith("--"):
        when = None                      # 해가 없는 날짜는 날짜 해석이 채운다 — 여기까지 왔으면 모르는 것이다
    if not when:
        problems.append(Problem("no_date", f"{where}.date", f"「{title or '이 항목'}」의 날짜를 모릅니다 — "
                                "첫날 날짜를 알려 주세요", sid))
    place = value("place")
    # ★`[2026-10-13]` 수정 접수가 등록한 여행에서 가져온 「장소 없음」(`method: trip`)도 고객이 정한 「장소 없음」과 같다(`reopen.py`)
    no_place = (fields.get("place") or {}).get("method") in ("customer", "trip") and place is None
    if not place and not no_place:
        problems.append(Problem("no_place", f"{where}.place", f"「{title or '이 항목'}」의 장소를 정하지 못했습니다 — "
                                "장소 이름을 고치거나 「장소 없음」으로 두세요", sid))
    # `[2026-10-26 사용자 지시 — 호텔 종류 확인]` 숙박(lodging)도 받는다 — 읽기 AI 의 숙박 읽기 · 고객이 고른 숙박(종류 확인 질문 · 확인 화면 고치기).
    #   ☆전에는 활동 · 식사만 받아 AI 가 숙박으로 읽어도 활동이 됐다(숙박은 줄에 「체크인」 글자가 있을 때만 — `_stays`)
    kind = value("kind") if value("kind") in ("activity", "dining", "lodging") else \
        ("dining" if (place or {}).get("kind") == "dining" else "activity")
    if (fields.get("kind") or {}).get("method") == "trip" and value("kind") in ("lodging", "flight"):
        kind = value("kind")            # `[2026-10-15 ST4F-490]` 수정 접수가 등록한 여행에서 가져온 숙소 · 항공은 그 종류 그대로(읽은 줄은 지금처럼 활동 · 식사)
    start, end = value("starts_at"), value("ends_at")
    lines = (source.get("transcript") or "").splitlines()
    text = lines[line - 1] if 0 < line <= len(lines) else ""
    # 예약했나 — 「예약 있음 · 없음」을 읽은 칸이 먼저, 예약번호가 있으면 예약한 것이다. 아무 말도 없으면 모른다(None — 예약 안 했다고 적지 않는다)
    booked = value("booked") if isinstance(value("booked"), bool) else (True if value("booking_no") else None)
    return {"order": (source["position"], line or 10_000, index), "source_id": sid, "index": index, "title": title,
            "text": text, "booked": booked, "role": value("role") or "visit",
            "date": when, "start": start if start and _HHMM.match(str(start)) else None,
            "end": end if end and _HHMM.match(str(end)) else None, "kind": kind,
            "place": place if place and place.get("latitude") is not None else None,
            "booking_no": value("booking_no"), "provenance": _provenance(fields), "where": where,
            "claims": fields, "locked": value("locked") is True, "day": day, "no_place": no_place,
            # 끝이 다른 날인 항목(숙소)만 채운다 — `_stays` · `[2026-10-15]` 수정 접수가 등록한 숙소에서 가져온 체크아웃 날(`end_date` 값 줄)
            "end_date": value("end_date") if kind == "lodging" else None}


def _stays(rows, filled, problems) -> list[dict[str, Any]]:
    """체크인 줄 + 그 뒤 체크아웃 줄 → **숙소 항목 하나**(`kind: lodging`, 끝 = 체크아웃 날 · 시각). `[2026-10-13 사용자 결정 — B안]`

    ★숙소 팀은 항목의 시작 날을 체크인, 끝 날을 체크아웃으로 읽는다(`instances/lodging/team._stay_query`). 전에는 「롯데호텔 체크인」이
      숙소 분류 활동 하나로, 「체크아웃」은 장소를 못 찾은 활동으로 따로 남았다.
    ★합친 체크아웃 줄은 항목이 되지 않는다 — 그 줄에 붙은 문제(장소를 못 정함 등)도 뺀다.
    ★적혀 있지 않은 값은 규칙으로 채우고 그렇게 적는다(`filled` — 화면이 「규칙으로 채움」 배지로 보인다):
      체크인 시각 없음 → 15:00 · 체크아웃 줄 없음 → 다음 체크인 날(없으면 여행 마지막 날, 같은 날이면 다음 날) 11:00 · 체크아웃 시각 없음 → 11:00.
    ★식사 줄(「호텔 조식」)은 숙소가 아니다 — 체크인 말이 있어도 건드리지 않는다."""
    def words(row):
        return f"{row['title'] or ''} {row['text'] or ''}"

    # `[2026-10-15 ST4F-490]` 이미 숙소인 줄(수정 접수가 등록한 숙소에서 가져온 것 — 끝 날짜를 값 줄로 안다)은 합치지 않는다
    # `[2026-10-26 사용자 지시 — 호텔 종류 확인]` 체크인 말이 없어도 숙박으로 읽었거나 고객이 숙박을 고른 줄(끝 날을 모르는 숙박)도 체크인 줄과 같다
    # `[2026-10-27 A 접수·읽기 전수검사]` 단 체크아웃 말만 있는 숙박 줄(읽기 에이전트는 「체크아웃」 줄도 숙박으로 읽는다 — 지시문 `lodging for
    #   hotel stay/check-in/check-out`)은 새 숙박의 시작이 아니라 체크아웃이다. ☆이 갈래가 없어 마지막 날 11:00 에 시작하는 가짜 숙박이 생기고
    #   진짜 숙박은 「체크아웃 줄이 없어」로 채워졌다
    def leaving(row):
        return bool(_CHECK_OUT.search(words(row))) and not _CHECK_IN.search(words(row))

    ins = [r for r in rows if r["date"] and ((r["kind"] not in ("dining", "lodging") and _CHECK_IN.search(words(r)))
                                             or (r["kind"] == "lodging" and not r.get("end_date") and not leaving(r)
                                                 and (r["claims"].get("kind") or {}).get("method") != "trip"))]
    if not ins:
        return rows
    outs = [r for r in rows if r["date"] and _CHECK_OUT.search(words(r)) and not any(r is i for i in ins)
            and (r["kind"] != "lodging" or (leaving(r) and not r.get("end_date")
                                            and (r["claims"].get("kind") or {}).get("method") != "trip"))]
    last_day = max(r["date"] for r in rows if r["date"])
    merged: list[int] = []

    def fill(row, field, value, note):
        filled.append({"source_id": row["source_id"], "field": f"{row['where']}.{field}", "value": value,
                       "method": "rule", "note": note})
        row["provenance"][field] = {"method": "rule", "rule": "intake.stay_default", "why": note}

    for n, row in enumerate(ins):
        next_in = ins[n + 1]["date"] if n + 1 < len(ins) else None
        begin = (row["date"], row["start"] or "00:00")
        out = next((o for o in outs if id(o) not in merged and (o["date"], o["start"] or "99:99") > begin
                    and (next_in is None or o["date"] <= next_in)), None)
        row["kind"] = "lodging"
        row["title"] = _CHECK_IN.sub("", row["title"] or "").strip(" ·-~") or (row["place"] or {}).get("name") or row["title"]
        if not row["start"]:
            row["start"] = STAY_IN
            fill(row, "starts_at", STAY_IN, f"체크인 시각이 없어 {STAY_IN} 에 두었다")
        if out is not None:
            merged.append(id(out))
            row["end_date"], row["end"] = out["date"], out["start"] or STAY_OUT
            row["provenance"]["ends_at"] = {"method": "rule", "rule": "intake.stay_checkout", "from": out["where"],
                                            "source_id": out["source_id"]}
            if not out["start"]:
                fill(row, "ends_at", STAY_OUT, f"체크아웃 시각이 없어 {STAY_OUT} 로 두었다")
        else:
            end_date = next_in or last_day
            if end_date <= row["date"]:
                end_date = (date.fromisoformat(row["date"]) + timedelta(days=1)).isoformat()
            row["end_date"], row["end"] = end_date, STAY_OUT
            fill(row, "ends_at", STAY_OUT, f"체크아웃 줄이 없어 {end_date} {STAY_OUT} 로 두었다")
    gone = [o for o in outs if id(o) in merged]
    problems[:] = [p for p in problems
                   if not any(p.source_id == o["source_id"] and (p.field == o["where"] or p.field.startswith(o["where"] + "."))
                              for o in gone)]
    return [r for r in rows if id(r) not in merged]


def _fill_times(rows, filled, problems) -> None:
    previous_end: dict[str, str] = {}
    for n, row in enumerate(rows):
        if not row["date"]:
            continue
        if row["kind"] == "lodging":
            # 숙소는 `_stays` 가 시각을 정했다 — 그날 뒤 일정은 체크인 시각 뒤로 둔다(끝은 체크아웃 날이다)
            previous_end[row["date"]] = row["start"]
            continue
        if not row["start"]:
            row["start"], why = _placed(row, previous_end.get(row["date"]))
            filled.append({"source_id": row["source_id"], "field": f"{row['where']}.starts_at",
                           "value": row["start"], "method": "rule", "note": why})
            row["provenance"]["starts_at"] = {"method": "rule", "rule": "intake.fill_start", "why": why}
            if row["booking_no"]:
                problems.append(Problem("booking_without_time", f"{row['where']}.starts_at",
                                        f"「{row['title']}」에 예약번호가 있는데 시각이 없습니다 — 예약 시각을 알려 주세요",
                                        row["source_id"]))
        if row.get("role") == "origin":
            row["end"] = None
            previous_end[row["date"]] = row["start"]
            continue
        if not row["end"]:
            minutes = planner.MEAL_MIN if row["kind"] == "dining" else planner.ACTIVITY_MIN
            end = _plus(row["start"], minutes)
            following = next((r for r in rows[n + 1:] if r["date"] == row["date"] and r["start"]), None)
            if following and row["start"] < following["start"] < end:
                end = following["start"]           # ★우리가 채운 끝이 다음 항목과 겹치게 하지 않는다
            if end <= row["start"]:
                end = None                          # 자정을 넘기면 끝을 비운다(판정기가 끝 없는 항목을 받는다)
            row["end"] = end
            if end:
                filled.append({"source_id": row["source_id"], "field": f"{row['where']}.ends_at", "value": end,
                               "method": "rule", "note": f"끝 시각이 없어 {minutes}분으로 두었다"})
                row["provenance"]["ends_at"] = {"method": "rule", "rule": "intake.default_duration",
                                                "minutes": minutes}
        previous_end[row["date"]] = row["end"] or row["start"]


def _fit_day_end(rows, claims, filled, problems):
    """Shorten only inferred durations; explicit clocks and protected visits remain anchors."""
    from . import reading_prefs
    from .autofix import MIN_STAY_MIN
    constraints = reading_prefs.apply({reading_prefs.CARRY_KEY: reading_prefs.carry(claims)})
    finish = (constraints.get("day_hours") or {}).get("end")
    if not finish:
        return
    if any(r["date"] and not r["start"] for r in rows):
        problems.append(Problem("time_window", "items", "하루 안에 모든 방문을 배치하지 못했어요. 방문 수나 마감 시각을 조정해 주세요."))
    for day in sorted({r["date"] for r in rows if r["date"]}):
        chain = [r for r in rows if r["date"] == day and r["kind"] != "lodging" and r["start"]]
        if not chain:
            continue
        deadline = _at(day, finish)
        durations, flexible = {}, set()
        for n, row in enumerate(chain):
            if row.get("role") == "origin":
                durations[n] = timedelta(0)
                continue
            inferred = not (row["claims"].get("ends_at") or {}).get("value")
            if inferred:
                durations[n] = ((_at(day, row["end"]) - _at(day, row["start"])) if row["end"]
                                else timedelta(minutes=planner.MEAL_MIN if row["kind"] == "dining" else planner.ACTIVITY_MIN))
                if not row["locked"] and not row["booked"] and not row["booking_no"]:
                    flexible.add(n)
            else:
                durations[n] = _at(day, row["end"]) - _at(day, row["start"]) if row["end"] else timedelta(0)

        def timing():
            result, previous = [], None
            for n, row in enumerate(chain):
                begin = _at(day, row["start"])
                if (previous is not None and (row["provenance"].get("starts_at") or {}).get("rule") == "intake.fill_start"
                        and begin == _at(day, chain[n - 1]["end"] or chain[n - 1]["start"]) + timedelta(minutes=planner.MOVE_BUFFER_MIN)):
                    begin = previous + timedelta(minutes=planner.MOVE_BUFFER_MIN)
                end = begin + durations[n]
                result.append((begin, end))
                previous = end
            return result

        moments = timing()
        for n in sorted(flexible, reverse=True):
            excess = max((end for _, end in moments), default=deadline) - deadline
            if excess <= timedelta(0):
                break
            available = max(timedelta(0), durations[n] - timedelta(minutes=MIN_STAY_MIN))
            durations[n] -= min(available, excess)
            moments = timing()
        if any(end > deadline for _, end in moments):
            problems.append(Problem("day_deadline", "items", f"{finish} 마감 안에 최소 체류와 지정 시각을 함께 맞추지 못했어요. 방문을 줄이거나 다른 날로 옮겨 주세요."))
            continue
        for n, (row, (begin, end)) in enumerate(zip(chain, moments)):
            for clock_field, value in (("start", begin.strftime("%H:%M")), ("end", end.strftime("%H:%M"))):
                if row.get("role") == "origin" and clock_field == "end":
                    continue
                if row[clock_field] == value:
                    continue
                row[clock_field] = value
                name = "starts_at" if clock_field == "start" else "ends_at"
                row["provenance"][name] = {"method": "rule", "rule": "intake.fit_day_deadline", "finish_by": finish}
                filled.append({"source_id": row["source_id"], "field": f"{row['where']}.{name}", "value": value,
                               "method": "rule", "note": f"고객 마감 {finish} 안에 기본 체류를 맞췄어요"})


def _split_shared_lines(rows, original_titles=None) -> None:
    """저장된 항목 구간을 재사용한다. 옛 근거는 삭제 전 항목들로 같은 경계를 계산한다."""
    shared: dict[tuple[str, int], list[tuple[int, int, dict[str, Any], str, dict[str, Any]]]] = {}
    for row in rows:
        evidence = (row["claims"].get("title") or {}).get("evidence") or {}
        if not isinstance(evidence.get("start"), int):
            evidence = (original_titles or {}).get((row["source_id"], f"{row['where']}.title"), evidence)
        if isinstance(evidence.get("start"), int) and isinstance(evidence.get("end"), int) and row["text"]:
            row["_title_start"] = evidence["start"]
            shared.setdefault((row["source_id"], row["order"][1]), []).append(
                (evidence["start"], evidence["end"], row, row["text"], evidence))
    for group in shared.values():
        group.sort(key=lambda g: g[0])
        bounds = split_segments(group[0][3], [(start, end) for start, end, *_ in group])
        for (start, end, row, text, evidence), (left, right) in zip(group, bounds):
            segment = evidence.get("segment") or {}
            saved_left, saved_right = segment.get("start"), segment.get("end")
            if isinstance(saved_left, int) and isinstance(saved_right, int) and \
                    0 <= saved_left <= start < end <= saved_right <= len(text) and \
                    segment.get("text") == text[saved_left:saved_right]:
                left, right = saved_left, saved_right
            row["text"] = text[left:right]
            row["_segment_start"] = left


def _placed(row, previous: str | None) -> tuple[str, str]:
    """(시각, 그렇게 정한 이유). ★끼니 말은 그 항목 몫에서, 「먹고 나서」는 빼고 본다(`rules.meal_mention`)."""
    title_start = row.get("_title_start", row["text"].find(row["title"] or ""))
    offset = title_start - row.get("_segment_start", 0)
    mention = meal_mention(row["text"], place_start=offset if offset >= 0 else None)
    at = dict(_MEAL_TIMES).get(mention[0]) if mention else None
    if at:
        return at, f"시각이 없어 원문의 「{mention[0]}」로 {at} 에 두었다"
    if row["kind"] == "dining":
        at = "12:00" if not previous or previous <= "12:00" else "18:00"
        return at, f"시각이 없어 식사 시간({at})에 두었다"
    if previous:
        return _plus(previous, planner.MOVE_BUFFER_MIN), "시각이 없어 앞 일정 뒤에 두었다"
    return planner.DAY_START.strftime("%H:%M"), "시각이 없어 하루 첫 일정 시각에 두었다"


# ── 일정 생성 기본값 ─────────────────────────────────────────────
def _plan_basis(trip, rows, sources, first_day) -> dict[str, Any]:
    """「일정 짜 줘」의 기본값 — **읽은 값에서만** 낸다. 없으면 None 으로 두고 화면이 묻는다(지어내지 않는다).

    첫날 = 고객이 알려 준 첫날 > 읽은 항목의 가장 이른 날짜. 일수 = 「n박 m일」의 m > 읽은 날짜 수.
    선호 = 고객이 올린 원문 그대로(일정 생성기가 규정에 붙여 읽는다, `planner.ground_request`).
    """
    dates = sorted({r["date"] for r in rows if r["date"]})
    days = _int_value(trip.get("days")) or (len(dates) or None)
    text = "\n".join(s.get("transcript") or "" for s in sources).strip()
    return {"requested": bool((trip.get("plan_request") or {}).get("value")),
            "start_date": first_day.isoformat() if first_day else (dates[0] if dates else None),
            "days": days if days is None or 1 <= days <= planner.MAX_DAYS else None,
            "party_size": _int_value(trip.get("party_size")),
            "preferences": text[:2000]}


# ── 부품 ─────────────────────────────────────────────────────────
def _seoul_district(place: dict[str, Any]) -> str | None:
    """★`[2026-10-20]` 등록 장소의 서울 자치구 — 성립 점검이 장소의 `district` 로 대기질 측정소(에어코리아)를 고른다.
    ☆전에는 접수로 들어온 장소에 구가 없어 대기질 1차 소스가 늘 「구 모름」으로 실패했다(채팅 교체가 막힌 원인의 하나, x600 2026-10-20).
    주소의 「서울(특별시) ○○구」가 먼저, 없으면 좌표 상자가 **한 구만** 가리킬 때만 쓴다(겹치면 비운다 — 엉뚱한 측정소를 고르지 않게)."""
    from app.domains.travel_ops.ports.data_sources.disaster_msg import seoul_districts

    if place.get("district"):
        return str(place["district"])
    try:
        lat, lon = float(place["latitude"]), float(place["longitude"])
    except (KeyError, TypeError, ValueError):
        lat = lon = None
    found, basis = seoul_districts(lat, lon, place.get("address"))
    return found[0] if found and basis in ("address", "box") else None


def _place_in(key: str, place: dict[str, Any], kind: str) -> dict[str, Any]:
    source = str(place.get("source") or "")
    attributes: dict[str, Any] = {}
    if source in ("tour_api", "kakao", "dining_ledger", "dining_license"):   # ★`[2026-10-05]` 요식 원장 가게도 그 여행 전용 사본으로 들어간다(팀 판)
        attributes["source"] = source
        if source in _SOURCE_ATTRS and place.get("content_id"):
            attributes[_SOURCE_ATTRS[source]] = str(place["content_id"])
            if place.get("content_type_id") and source != "dining_license":     # 인허가 관리번호는 관광공사 종류 번호와 짝이 아니다
                attributes["source_content_type_id"] = str(place["content_type_id"])
        if source == "dining_ledger" and place.get("dining_place_uid"):
            # ★`[2026-10-07 팀]` 원장 가게 id — 관광공사 id 가 없는 원장 가게도 등록 때 원장과 잇는다(trip_api 등록)
            attributes["dining_place_uid"] = str(place["dining_place_uid"])
    elif source == "customer_pick":
        # ★`[2026-10-02]` 고객이 후보 · 검색 · 지도에서 고른 장소 — 관광공사 · 카카오 값으로 위장하지 않는다. 공용 장소 표에 섞이지 않게
        #   그 여행 전용 행으로만 들어간다(`trip_api.EXTERNAL_PLACE_SOURCES`). 관광공사 번호는 운영시간 표를 찾는 데만 쓴다.
        attributes["source"] = "customer_pick"
        if place.get("origin"):
            attributes["pick_origin"] = str(place["origin"])
        if place.get("content_id"):
            attributes["source_content_id"] = str(place["content_id"])
        if place.get("dining_place_uid"):
            # ★`[2026-10-10]` 서버가 공용 원장 식당 행과 같은 곳으로 확인한 경우만 있다(`pipeline._linked_ledger_pick`) — 등록 판정 · 원장 연결이 이 번호로 간다
            attributes["dining_place_uid"] = str(place["dining_place_uid"])
    if place.get("provider_ref"):
        attributes["provider_ref"] = place["provider_ref"]
    district = _seoul_district(place)
    if district:
        attributes["district"] = district
    return {"key": key, "name": place["name"], "kind": place.get("kind") or kind,
            "lat": float(place["latitude"]), "lon": float(place["longitude"]),
            "weather_sensitive": None, "attributes": attributes}   # ★`[2026-09-29]` 모름 — 확실한 분류로 채운다(`fill_weather_sensitive`)


def _provenance(fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for name, claim in fields.items():
        evidence = claim.get("evidence") or {}
        keep = {k: evidence[k] for k in ("source", "line", "start", "end", "text", "how", "query",
                                        "content_id", "source_id") if evidence.get(k) is not None}
        # ★근거 안의 `method`(장소를 찾은 단계 — places · typo · tour_api · kakao)는 `via` 로 옮긴다.
        #   그대로 펼치면 값의 방법(lookup)을 덮어쓴다(시험에서 잡았다).
        if evidence.get("method"):
            keep["via"] = evidence["method"]
        out[name] = {**keep, "method": claim["method"]}
    return out


def _day_marks(claims) -> list[tuple[int, int | None, str | None]]:
    marks: dict[int, list] = {}
    for claim in claims:
        field_name, line = claim["field"], claim["evidence"].get("line", 0)
        if field_name.startswith("days[") and field_name.endswith(".heading"):
            marks.setdefault(line, [None, None])[0] = claim["value"]
        elif field_name.startswith("days[") and field_name.endswith(".date"):
            marks.setdefault(line, [None, None])[1] = claim["value"]
    return [(line, day, when) for line, (day, when) in sorted(marks.items())]


def _day_for(line, marks) -> tuple[int | None, str | None]:
    day = when = None
    for mark_line, mark_day, mark_date in marks:
        if mark_line > line:
            break
        if mark_day is not None:
            day, when = mark_day, mark_date
        elif mark_date is not None:
            when = mark_date
    return day, when


def _title(trip: dict[str, dict[str, Any]], sources: list[dict[str, Any]]) -> str:
    if trip.get("title") and str(trip["title"]["value"] or "").strip():
        return str(trip["title"]["value"]).strip()[:80]
    from .rules import TIME, _date_in

    for source in sources:
        for line in (source.get("transcript") or "").splitlines():
            text = line.strip()
            if not text or _DAY_HEADING.match(text) or re.match(r"^\d{1,2}[:시]", text):
                continue
            # ★`[2026-09-28]` 날짜로 시작하고 뒤에 날짜 말고 쓴 것이 없거나 시각이 오면 제목이 아니다 —
            #   「2026-10-05」·「10월 5일 (월)」·「2026-10-05 09:00 경복궁」이 제목이 됐다(ui 세션 실서버 시험)
            _, found = _date_in(text)
            if found is not None and found.start() == 0:
                rest = re.sub(r"^[\s·,()（）월화수목금토일요]*", "", text[found.end():])
                if not rest or TIME.match(rest):
                    continue
            return text[:80]
    return "내 여행"


def _date_value(claim: dict[str, Any] | None) -> date | None:
    try:
        return date.fromisoformat(str(claim["value"])) if claim and claim.get("value") else None
    except ValueError:
        return None


def _int_value(claim: dict[str, Any] | None) -> int | None:
    try:
        return int(claim["value"]) if claim and claim.get("value") is not None else None
    except (TypeError, ValueError):
        return None


def _plus(hhmm: str, minutes: int) -> str:
    moved = datetime.combine(date(2000, 1, 1), time.fromisoformat(hhmm)) + timedelta(minutes=minutes)
    return "23:59" if moved.date() != date(2000, 1, 1) else moved.strftime("%H:%M")


def _at(day: str, hhmm: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), time.fromisoformat(hhmm), tzinfo=KST)


__all__ = ["Assembled", "Collected", "Problem", "assemble", "collect", "effective"]
