# -*- coding: utf-8 -*-
"""국토교통부 TAGO — 열차 · 고속버스 · 시외버스 **운행 정보**(출발 · 도착 시각 · 등급 · 어른 요금). `[2026-10-14]` 예약 모듈 확장.

활용신청 셋(국토교통부_(TAGO)_열차정보 · 고속버스정보 · 시외버스정보, 공공데이터포털 공통 키 `ACOP_TAGO_API_KEY` → 공통 키) — 10-14 13:45 playdata 승인 즉시 통과.

★호출 주소는 **2026-03 에 바뀌었다** — `…/1613000/<이름>Service/get<동작>` → `…/1613000/<이름>/Get<동작>`(서비스 이름에서 `Service` 가 빠지고
  동작 첫 글자가 대문자). 옛 주소는 `NO_OPENAPI_SERVICE`(키 문제처럼 보이지만 주소 문제). 도시 코드 목록 셋은 13:45 실호출로 확인했고,
  나머지 동작 이름은 같은 규칙으로 옮긴 **추정**이다 — `scripts/probe_tago_transit.py` 로 확인한다(확인 전까지 「확인 안 함」).

- 예약 · 결제는 하지 않는다. 운행 정보만 주고 예매는 코레일 · SRT · 코버스 · 버스타고 링크로(`components/booking/offers/transit.py`).
- 요금은 공급자가 준 어른 1인 값 그대로(`adultcharge` · `charge`) — 할인 · 좌석 등급별 차이는 모른다. 좌석 남음은 주지 않는다.
- 시각은 공급자의 `YYYYMMDDHHMM` 을 날짜 · 시각으로 가른다. 소요 시간은 두 시각의 차(분) — 둘 다 있을 때만.
- 응답 칸 이름은 대소문자가 섞여 있어(`arrplandtime` · `arrPlandTime`) **소문자로 맞춰** 읽는다.
- 속도 제한 이름은 `tago`(설정 `rate_tago_per_day`) — 이동 모듈 지하철과 같은 키 · 같은 하루 한도를 나눠 쓴다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .base import TravelSource

BASE_URL = "https://apis.data.go.kr/1613000"
TRAIN, EXPRESS, SUBURBS = "TrainInfo", "ExpBusInfo", "SuburbsBusInfo"

#: 역 목록을 도시별로만 주므로 — 시 · 도 이름(우리 사전) → 공급자 `cityname` 앞머리
CITY_PREFIX = {"서울": ("서울",), "부산": ("부산",), "대구": ("대구",), "인천": ("인천",), "광주": ("광주",), "대전": ("대전",),
               "울산": ("울산",), "세종": ("세종",), "경기": ("경기",), "강원": ("강원",), "충북": ("충청북도", "충북"),
               "충남": ("충청남도", "충남"), "전북": ("전라북도", "전북"), "전남": ("전라남도", "전남"),
               "경북": ("경상북도", "경북"), "경남": ("경상남도", "경남"), "제주": ("제주",)}


def _low(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key).lower(): value for key, value in row.items()}


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _int(value: Any) -> int | None:
    try:
        number = int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _stamp(value: Any) -> datetime | None:
    """공급자 시각 → datetime. `YYYYMMDDHHMM`(숫자 · 문자) 그대로, 초가 붙은 14자리(☆10-14 탐침 — 열차 · 시외는 12자리가 아니었다)는 앞 12자리만."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) in (8, 10):                             # 날짜만 · 시까지만 온 값(00시대 — 팀장 점검 LB-10 후보 원인, 10-15) → 00분으로
        digits = digits.ljust(12, "0")
    if len(digits) < 12:
        return None
    try:
        if digits[8:10] == "24":                           # ★고속버스 자정 출발은 「2400」(10-16 심야우등, 팀장 점검 LB-10 · 실호출 10-15 08:43) → 다음 날 00시
            return datetime.strptime(digits[:8], "%Y%m%d") + timedelta(days=1, minutes=int(digits[10:12] or 0))
        return datetime.strptime(digits[:12], "%Y%m%d%H%M")
    except ValueError:
        return None


def _when(value: Any) -> tuple[str | None, str | None]:
    """공급자 시각 → (날짜 ISO, HH:MM). 모양이 다르면 (None, None)."""
    at = _stamp(value)
    return (at.date().isoformat(), at.strftime("%H:%M")) if at else (None, None)


def _minutes(depart: Any, arrive: Any) -> int | None:
    a, b = _stamp(depart), _stamp(arrive)
    if a is None or b is None:
        return None
    minutes = int((b - a).total_seconds() // 60)
    return minutes if 0 < minutes < 24 * 60 else None


class TagoTransit(TravelSource):
    """열차 · 고속버스 · 시외버스 운행 정보. 한 어댑터가 세 서비스를 다 부른다(키 · 주소 규칙이 같다)."""

    name = "tago"

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key
        self._cities: list[dict[str, Any]] | None = None

    # ── 공통 ─────────────────────────────────────────────
    def _call(self, service: str, operation: str, params: dict[str, Any], *, rows: int) -> list[dict[str, Any]] | None:
        if not self._key:
            self._miss("no_service_key")
            return None
        payload = self._fetch_json(f"{BASE_URL}/{service}/{operation}", {
            "serviceKey": self._key, "_type": "json", "numOfRows": str(rows), "pageNo": "1", **params})
        if payload is None:
            return None
        return [_low(row) for row in self._rows(payload)]

    @staticmethod
    def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
        body = (payload.get("response") or {}).get("body")
        if not isinstance(body, dict):
            return []
        items = body.get("items")
        if isinstance(items, dict):
            rows = items.get("item") or []
        elif isinstance(items, list):
            rows = items
        else:
            rows = []                                     # 빈 결과는 `items: ""` 로 온다
        if isinstance(rows, dict):
            return [rows]
        return [r for r in rows if isinstance(r, dict)]

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        header = (payload.get("response") or {}).get("header")
        if isinstance(header, dict):
            code = str(header.get("resultCode", ""))
            if code and code not in ("00", "0000"):
                return f'{code} {header.get("resultMsg", "")}'.strip()
        return TravelSource._body_error(payload)

    def shape(self, service: str, operation: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """탐침용 — 첫 줄의 **칸 이름과 값의 자릿수만**(값은 돌려주지 않는다 · 응답 저장 안 함)."""
        rows = self._call(service, operation, params, rows=1)
        if not rows:
            return None if rows is None else {}
        return {key: (type(value).__name__, len(str(value))) for key, value in rows[0].items()}

    # ── 열차 ─────────────────────────────────────────────
    def train_cities(self) -> list[dict[str, Any]] | None:
        if self._cities is None:
            rows = self._call(TRAIN, "GetCtyCodeList", {}, rows=50)
            if rows is None:
                return None                               # 못 불렀다 — 빈 목록으로 굳히지 않고 다음에 다시 부른다(검토 10-14)
            self._cities = [{"code": _text(row.get("citycode")), "name": _text(row.get("cityname"))}
                            for row in rows if _text(row.get("citycode"))]
        return self._cities

    def train_stations(self, city: str) -> list[dict[str, Any]] | None:
        """시 · 도 이름(사전 값: 서울 · 경기 · 충북 …)의 역 목록 [{id, name}]. 도시 코드를 못 찾으면 `None`(모름)."""
        prefixes = CITY_PREFIX.get(city, (city,))
        cities = self.train_cities()
        if cities is None:
            return None
        code = next((item["code"] for item in cities if item["name"] and item["name"].startswith(prefixes)), None)
        if code is None:
            self._miss("unknown_city", city)
            return []                                     # 공급자 목록에 그 시 · 도가 없다 — 장애가 아니라 「못 찾음」
        rows = self._call(TRAIN, "GetCtyAcctoTrainSttnList", {"cityCode": code}, rows=200)
        if rows is None:
            return None
        return [{"id": _text(row.get("nodeid")), "name": _text(row.get("nodename"))}
                for row in rows if _text(row.get("nodeid")) and _text(row.get("nodename"))]

    def train_schedules(self, *, dep_id: str, arr_id: str, date: str) -> list[dict[str, Any]] | None:
        """출발역 id → 도착역 id · 날짜(ISO)의 열차. 등급 · 열차 번호 · 시각 · 어른 요금. 못 부르면 `None`."""
        rows = self._call(TRAIN, "GetStrtpntAlocFndTrainInfo",
                          {"depPlaceId": dep_id, "arrPlaceId": arr_id, "depPlandTime": date.replace("-", "")}, rows=300)
        if rows is None:
            return None
        found = []
        for row in rows:
            day, depart = _when(row.get("depplandtime"))
            _, arrive = _when(row.get("arrplandtime"))
            found.append(self.stamp({
                "mode": "train", "kind": None, "grade": _text(row.get("traingradename")),
                "number": (_text(row.get("trainno")) or "").lstrip("0") or _text(row.get("trainno")),   # 「00001」 → 「1」
                "origin": _text(row.get("depplacename")), "destination": _text(row.get("arrplacename")),
                "date": day, "depart": depart, "arrive": arrive,
                "minutes": _minutes(row.get("depplandtime"), row.get("arrplandtime")),
                "price": _int(row.get("adultcharge")),
            }, source=self.name))
        return found

    # ── 버스 ─────────────────────────────────────────────
    def bus_terminals(self, kind: str, keyword: str) -> list[dict[str, Any]] | None:
        """터미널 이름 조각으로 [{id, name}]. `kind` 는 express(고속) · suburbs(시외). 공급자가 거르지 않아도 이름에 조각이 든 것만 남긴다."""
        service, operation = (EXPRESS, "GetExpBusTrminlList") if kind == "express" else (SUBURBS, "GetSuberbsBusTrminlList")
        rows = self._call(service, operation, {"terminalNm": keyword}, rows=100)
        if rows is None:
            return None
        found: list[dict[str, Any]] = []
        for row in rows:
            item = {"id": _text(row.get("terminalid")), "name": _text(row.get("terminalnm"))}
            if item["id"] and item["name"] and item["id"] not in {f["id"] for f in found}:
                found.append(item)                        # ☆10-14 「센트럴시티(서울)」이 두 줄(id 둘)로 온다 — `[10-15]` id 로 가른다: 이름으로 하나만
                                                          #   남기면 죽은 id 가 남아 호남선 0편(서울→광주 · 전주 실호출)이 될 수 있어 둘 다 둔다
        return [item for item in found if keyword in item["name"]] or found

    def bus_schedules(self, kind: str, *, dep_id: str, arr_id: str, date: str) -> list[dict[str, Any]] | None:
        service, operation = ((EXPRESS, "GetStrtpntAlocFndExpbusInfo") if kind == "express"
                              else (SUBURBS, "GetStrtpntAlocFndSuberbsBusInfo"))
        rows = self._call(service, operation,
                          {"depTerminalId": dep_id, "arrTerminalId": arr_id, "depPlandTime": date.replace("-", "")}, rows=300)
        if rows is None:
            return None
        found = []
        for row in rows:
            day, depart = _when(row.get("depplandtime"))
            _, arrive = _when(row.get("arrplandtime"))
            found.append(self.stamp({
                "mode": "bus", "kind": kind, "grade": _text(row.get("gradenm")), "number": _text(row.get("routeid")),
                "origin": _text(row.get("depplacenm")), "destination": _text(row.get("arrplacenm")),
                "date": day, "depart": depart, "arrive": arrive,
                "minutes": _minutes(row.get("depplandtime"), row.get("arrplandtime")),
                "price": _int(row.get("charge")),
                # 시각을 못 읽은 줄은 받은 값의 모양을 남긴다(숫자 자릿수 · 형) — 00시대 1건(LB-10) 원인 찾기용. 값 자체는 시각이라 민감하지 않다
                **({"depart_raw": f"{type(row.get('depplandtime')).__name__}:{str(row.get('depplandtime'))[:16]}"} if depart is None else {}),
            }, source=self.name))
        return found


__all__ = ["BASE_URL", "CITY_PREFIX", "TagoTransit"]
