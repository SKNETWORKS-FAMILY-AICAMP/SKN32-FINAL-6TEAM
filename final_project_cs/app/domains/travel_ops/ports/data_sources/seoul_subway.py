# -*- coding: utf-8 -*-
"""서울 열린데이터광장 **실시간 지하철 도착정보**(OA-12764) — 「실시간 지하철 인증키」 전용 `[2026-10-05]`.

    GET http://swopenapi.seoul.go.kr/api/subway/{KEY}/json/realtimeStationArrival/{시작}/{끝}/{역명}
    → {errorMessage:{status:200, code:"INFO-000", message:"정상 처리되었습니다.", total:N},
       realtimeArrivalList:[{subwayId · updnLine · trainLineNm · arvlMsg2 · arvlMsg3 · arvlCd · barvlDt · recptnDt · btrainSttus · statnNm …}]}

★이 키는 서울 열린데이터광장 **일반 인증키와 별개**다(따릉이용 `ACOP_SEOUL_OPENAPI_KEY` 로는 이 서비스가 안 열린다). 하루 **1,000건**(활용사례
  등록 심사 뒤 해제 · 공식 안내 2026-10-04). 제공처가 **http 만** 받는다 — 키가 주소 경로에 들어가고 평문으로 나간다. 그래서 키를 오류 기록에
  싣지 않는다(`_miss` 를 덮어 가린다 · `bike.py` 의 `BikeLive` 와 같은 이유).
★이 소스가 주는 것은 **지금 값**이다 — 미래 시각의 도착은 모른다. 시간표(이동 계산기)를 대신하지 않는다: 지금 이 역에 어느 열차가 몇 분 뒤 오는가를
  일반 비순환 첫 승차의 정확 ID 경로에서는 접근 이후 예측을 출발 안내에 적용한다. 승차 이후 소요와 미래 환승은 모델이다.
★`INFO-200 「해당하는 데이터가 없습니다」` 는 **오류가 아니라 빈 결과**다 — 운행 시간 밖이거나 그 역에 열차가 없다(실측 2026-10-05 01시: 인증은
  통과하고 이 코드가 왔다). 인증 실패 · 호출 한도 · 잘못된 요청(`INFO-100`·`ERROR-xxx`)만 못 읽음(`None`)이다.
★역명은 **「역」 접미사 없이** 넣는다(공식 안내). 호선 필터는 응답의 `subwayId` 로 우리가 한다.
★`[2026-10-09]` 공식 초 단위 ETA·생성시각·식별 필드를 보존한다. 공개 부분응답 재생과 통제 연결 시험은 실제 ETA 오차·탑승 검증을 대신하지 않는다.
"""
from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime, timedelta
import math
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .base import TravelSource
from .subway_boarding import select_boardable_arrival, selection_input_error

BASE = "http://swopenapi.seoul.go.kr/api/subway"
KST = ZoneInfo("Asia/Seoul")
#: OA-12764 프로토콜 상한. 환승역에서20행을 넘으면 뒤쪽 호선/열차를 잘랐다.
#: 한 응답으로 읽어 여러 페이지의 서로 다른 생성시각을 섞지 않는다.
PAGE_SIZE = 1000
SAMPLE_PAGE_SIZE = 5
#: 응답 `subwayId` → 호선 표기(우리 `uses` 의 「N호선」과 같은 이름만). 모르는 번호는 그대로 둔다
SUBWAY_ID = {"1001": "1호선", "1002": "2호선", "1003": "3호선", "1004": "4호선", "1005": "5호선", "1006": "6호선",
             "1007": "7호선", "1008": "8호선", "1009": "9호선", "1063": "경의중앙선", "1065": "공항철도", "1067": "경춘선",
             "1075": "수인분당선", "1077": "신분당선", "1092": "우이신설선", "1032": "GTX-A",
             # OA-12764 공개 역정보(2026-09-02): 누락하면 이름으로 거를 때 해당 열차를 전부 버린다.
             "1081": "경강선", "1093": "서해선", "1094": "신림선"}
#: 「없음」으로 읽는 코드(빈 결과) — 인증·한도 오류와 갈라야 한다
EMPTY_CODES = {"INFO-200"}


def clean_station(name: str) -> str:
    """공식 안내: 역명은 「역」 접미사 없이."""
    name = str(name or "").strip()
    return name[:-1] if name.endswith("역") else name


def _identity(value: Any) -> str | None:
    """식별 문자열의 선행 0을 보존하고 잘못된 객체로 ID를 만들지 않는다."""
    if isinstance(value, str):
        return value if value.strip() else None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return str(value)
    return None


def _eta(value: Any) -> tuple[int | None, str]:
    """0초·누락·잘못된 입력을 구별한다. isdigit은 제곱 숫자도 허용하므로 충분하지 않다."""
    if value is None:
        return None, "missing"
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value, "valid"
    if isinstance(value, str) and value.isascii() and value.isdigit():
        try:
            return int(value), "valid"
        except ValueError:  # Python의 정수 문자열 길이 제한도 명시된 잘못된 입력이다.
            pass
    return None, "invalid"


def _arrival_total(payload: dict[str, Any]) -> tuple[int | None, str | None]:
    """공식 JSON total 및 공통 명세 list_total_count의 일치 여부를 확인한다."""
    info = payload.get('errorMessage') if isinstance(payload.get('errorMessage'), dict) else payload
    values = [container[key] for container, key in ((info, 'total'), (payload, 'list_total_count'))
              if key in container]
    totals = []
    for value in values:
        total, status = _eta(value)
        if status != 'valid':
            return None, 'invalid_arrival_total'
        totals.append(total)
    if len(set(totals)) > 1:
        return None, 'conflicting_arrival_total'
    return (totals[0] if totals else None), None


class SeoulSubwayArrival(TravelSource):
    name = "seoul_subway_arrival"

    def __init__(self, *, service_key: str, now=None, cache_ttl_seconds=None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key
        self._now = now or (lambda: datetime.now(KST))
        if cache_ttl_seconds is not None:
            try:
                valid_ttl = (not isinstance(cache_ttl_seconds, bool)
                             and isinstance(cache_ttl_seconds, (int, float))
                             and math.isfinite(cache_ttl_seconds) and cache_ttl_seconds > 0)
            except OverflowError:
                valid_ttl = False
            if not valid_ttl:
                raise ValueError('지하철 도착 보관 기간이 올바르지 않다')
        self.cache_ttl_seconds = cache_ttl_seconds

    def _from_cache(self, url: str, params: dict[str, Any]) -> Any | None:
        value = super()._from_cache(url, params)
        if value is not None and self.cache_ttl_seconds is not None:
            age = (datetime.now(UTC) - self._fetch_state.fetched_at).total_seconds()
            if age >= self.cache_ttl_seconds:
                # 기존 공용 보관의 긴 TTL로 저장된 값도 현재 승차 정책에서는 재사용하지 않는다.
                self._fetch_state.fetched_at, self._fetch_state.from_cache = None, False
                return None
        return value

    def _miss(self, reason: str, detail: str = "") -> None:
        """★키가 주소 경로에 들어간다 — 기록에 새지 않게 가린다."""
        if self._key and detail:
            detail = detail.replace(self._key, "***").replace(urllib.parse.quote(self._key, safe=""), "***")
        super()._miss(reason, detail)

    def _get(self, url: str, params: dict[str, Any]) -> httpx.Response:  # type: ignore[override]
        return httpx.get(url, timeout=self._timeout)

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        """정상 빈 결과와 누락·잘못된 목록을 보관 전에 구분한다."""
        info = payload.get("errorMessage") if isinstance(payload.get("errorMessage"), dict) else payload
        code = str(info.get("code") or "")
        if code and code != "INFO-000" and code not in EMPTY_CODES and (code.startswith("ERROR") or code.startswith("INFO")):
            return f'{code} {info.get("message", "")}'.strip()
        problem = TravelSource._body_error(payload)
        if problem is not None:
            return problem
        total, problem = _arrival_total(payload)
        if problem is not None:
            return problem
        rows = payload.get("realtimeArrivalList")
        if code in EMPTY_CODES:
            # 공식 데이터 없음 코드만 누락/null을 허용한다. 열차 목록과 동시에 오면 모순이다.
            return (None if (rows is None or rows == []) and (total is None or total == 0)
                    else "conflicting_empty_arrivals")
        if rows is None:
            return "missing_realtimeArrivalList"
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            return "malformed_realtimeArrivalList"
        if total is not None and total < len(rows):
            return 'arrival_total_below_rows'
        return None

    def boardable_arrival(self, station: str, *, line_id: str, station_id: str, target_station_id: str,
                         allowed_services: list, now: datetime, ready_at: datetime,
                         max_age_seconds: float, max_provider_age_seconds: float,
                         max_provider_clock_ahead_seconds: float) -> dict[str, Any]:
        """조회 완료 시각의 접근 시간을 보존해 일반열차를 고른다. 제품 시간 대체는 별도 연결이다."""
        policy = dict(line_id=line_id, station_id=station_id, target_station_id=target_station_id,
                      allowed_services=allowed_services, now=now, ready_at=ready_at,
                      max_age_seconds=max_age_seconds, max_provider_age_seconds=max_provider_age_seconds,
                      max_provider_clock_ahead_seconds=max_provider_clock_ahead_seconds)
        error = selection_input_error(**policy)
        if error:
            return {'status': 'unavailable', 'reason': error, 'source': self.name,
                    'line_id': line_id, 'station_id': station_id, 'target_station_id': target_station_id}
        snapshot = self.arrivals(station)
        evaluated = self._now()
        if not isinstance(evaluated, datetime) or evaluated.utcoffset() is None or evaluated < now:
            return {'status': 'unavailable', 'reason': 'invalid_evaluation_clock', 'source': self.name,
                    'evaluated_at': str(evaluated)}
        def departure_minute(at):
            floor = at.replace(second=0, microsecond=0)
            return floor + timedelta(minutes=1) if at > floor else floor
        ready = ready_at + (departure_minute(evaluated) - departure_minute(now))
        result = select_boardable_arrival(snapshot, **dict(policy, now=evaluated, ready_at=ready))
        return {**result, 'evaluated_at': evaluated.isoformat(), 'ready_at': ready.isoformat()}

    def arrivals(self, station: str, *, line: str | None = None) -> dict[str, Any] | None:
        """그 역의 **지금 도착 예정 열차**(상·하행). 못 읽으면 `None`, 열차가 없으면 `trains: []`(실패가 아니라 빈 결과).

        `line` 을 주면(「2호선」) 그 호선만 남긴다. 값은 정규화 — 원값(`raw`)은 싣지 않는다(키·주소가 안 섞이게)."""
        if not self._key:
            self._miss("no_service_key")
            return None
        name = clean_station(station)
        if not name:
            self._miss("empty_station")
            return None
        page_size = SAMPLE_PAGE_SIZE if self._key == 'sample' else PAGE_SIZE
        url = f"{BASE}/{self._key}/json/realtimeStationArrival/0/{page_size}/{urllib.parse.quote(name)}"
        payload = self._fetch_json(url, {})
        if payload is None:
            return None
        # 기존 보관 응답은 _fetch_json의 본문 검사를 우회한다. 외부 호출 실패 수는 늘리지 않는다.
        problem = self._body_error(payload)
        if problem is not None:
            self._miss("malformed_arrivals", problem)
            return None
        rows = payload.get("realtimeArrivalList")
        if rows is None:                              # INFO-200 — 빈 결과
            rows = []
        total, _ = _arrival_total(payload)
        info = payload.get('errorMessage') if isinstance(payload.get('errorMessage'), dict) else payload
        if total is None and info.get('code') in EMPTY_CODES:
            total = 0  # 공식 빈 결과 코드 자체가 전체0의 근거다.
        response_count = len(rows)  # 호선 필터 전 전체 응답 범위를 보존한다.
        trains = []
        checked = self._now()
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=KST)
        for row in rows:
            line_name = SUBWAY_ID.get(str(row.get("subwayId") or ""), str(row.get("subwayId") or ""))
            if line and line_name != line:
                continue
            seconds, eta_status = _eta(row.get("barvlDt"))
            received = row.get("recptnDt")
            age = None
            try:
                received_dt = datetime.fromisoformat(str(received))
                if received_dt.tzinfo is None:
                    received_dt = received_dt.replace(tzinfo=KST)
                age = int((checked - received_dt).total_seconds())
            except (ValueError, TypeError):
                pass
            trains.append({
                "line": line_name, "direction": row.get("updnLine"), "route_label": row.get("trainLineNm"),
                "message": row.get("arvlMsg2"), "position": row.get("arvlMsg3"), "arrival_code": row.get("arvlCd"),
                "eta_seconds": seconds, "eta_status": eta_status,
                "line_id": _identity(row.get("subwayId")),
                "station_id": _identity(row.get("statnId")),
                "previous_station_id": _identity(row.get("statnFid")),
                "next_station_id": _identity(row.get("statnTid")),
                "terminal_station_id": _identity(row.get("bstatnId")),
                "terminal_station": _identity(row.get("bstatnNm")),
                "train_number": _identity(row.get("btrainNo")),
                "arrival_order": _identity(row.get("ordkey")),
                "received_at": received, "received_age_seconds": age,
                "source_clock_ahead": age < 0 if age is not None else None,
                "train_status": row.get("btrainSttus")})
        return self.stamp({"station": name, "line": line, "trains": trains, "kind": "subway_arrival",
                           "schema_version": "1.1", 'provider_total': total,
                           'response_row_count': response_count,
                           'coverage_complete': response_count == total if total is not None else None},
                          source=self.name)


__all__ = ["SUBWAY_ID", "SeoulSubwayArrival", "clean_station", "select_boardable_arrival"]
