# -*- coding: utf-8 -*-
"""에어코리아 대기오염정보 — 측정소별 실시간 측정값(공공데이터포털 15073861).

실측(2026-09-14, 공통 키 · `public_data_key()` 로 디코드한 키):

    GET https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty
        ?serviceKey=…&returnType=json&sidoName=서울&ver=1.0&numOfRows=100
    → header {"resultCode":"00","resultMsg":"NORMAL_CODE"}, 서울 측정소 40곳
      측정소 이름이 **구 이름**(중구·송파구 …)이거나 도로 이름(강변북로 …)이다

  ★처음엔 403 「등록되지 않은 서비스키」가 나서 「승인 뒤 반영 대기」로 판단했는데
    **틀렸다.** 인코딩된 키를 그대로 넣은 탓이었다 — `settings.public_data_key()`
    docstring 이 이미 적어 둔 함정이다. 디코드한 키로는 바로 200 이었다.

★「경보」는 이 서비스가 **발령하지 않는다.** 주는 것은 1시간 측정값과 등급뿐이다.
  그래서 발령 기준에 대 본다 — 대기환경보전법 시행규칙 별표 7(미세먼지 경보제):

      PM10  주의보 150㎍/㎥ · 경보 300㎍/㎥ (2시간 이상 지속)
      PM2.5 주의보  75㎍/㎥ · 경보 150㎍/㎥ (2시간 이상 지속)

  ★공식 발령은 **2시간 평균**인데 우리는 **1시간 값**을 본다. 그 차이를 결과의
    `basis` 에 적는다 — 「경보가 발령됐다」고 말하지 않고 「경보 기준을 넘었다」고 말한다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import TravelSource

ENDPOINT = "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"

#: (항목, 단계, 기준값) — 높은 단계부터 본다.
ALERT_THRESHOLDS: tuple[tuple[str, str, int], ...] = (
    ("pm25", "경보", 150), ("pm10", "경보", 300),
    ("pm25", "주의보", 75), ("pm10", "주의보", 150),
)
LABEL = {"pm10": "미세먼지(PM10)", "pm25": "초미세먼지(PM2.5)"}
BASIS = "1시간 측정값을 발령 기준에 대 본 것 — 공식 발령은 2시간 평균이다"


def alert_level(pm10: int | None, pm25: int | None) -> dict[str, Any] | None:
    """발령 기준을 넘은 가장 높은 단계. 넘지 않았으면 `None`."""
    values = {"pm10": pm10, "pm25": pm25}
    for field, level, limit in ALERT_THRESHOLDS:
        value = values[field]
        if value is not None and value >= limit:
            return {"level": level, "pollutant": LABEL[field], "value": value, "limit": limit}
    return None


def _int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None      # ★「-」 같은 결측을 0 으로 채우지 않는다


def reading(row: dict[str, Any], *, source: str) -> dict[str, Any]:
    """측정소 한 줄 → 판정 모양. 재생 입력도 같은 모양을 쓴다."""
    pm10, pm25 = _int(row.get("pm10Value")), _int(row.get("pm25Value"))
    return {
        "station": row.get("stationName"),
        "data_time": row.get("dataTime"),
        "pm10": pm10, "pm25": pm25,
        "pm10_grade": _int(row.get("pm10Grade")), "pm25_grade": _int(row.get("pm25Grade")),
        "alert": alert_level(pm10, pm25),
        "basis": BASIS,
        "kind": "air_quality",
    }


class AirKoreaRealtime(TravelSource):
    name = "airkorea"

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        response = payload.get("response")
        header = response.get("header") if isinstance(response, dict) else None
        if isinstance(header, dict):
            code = str(header.get("resultCode", ""))
            return None if code == "00" else f'{code} {header.get("resultMsg", "")}'.strip()
        return TravelSource._body_error(payload)

    def at(self, *, district: str | None, sido: str = "서울",
           at: datetime | None = None) -> dict[str, Any] | None:
        """그 구의 측정소 값. 구를 모르면 `None` — 시도 전체로 뭉개 답하지 않는다.

        ★`at` 은 받기만 한다. 이 서비스는 **지금 값**만 준다 — 먼 미래 시각이면
          점검이 예보 쪽을 봐야 한다(아직 없다). 지금 값을 미래 값으로 쓰지 않도록
          결과에 `data_time` 을 그대로 싣는다.
        """
        if not district:
            self._miss("no_district", "구를 모르면 측정소를 고를 수 없다")
            return None
        payload = self._fetch_json(ENDPOINT, {
            "serviceKey": self._key, "returnType": "json", "numOfRows": 100, "pageNo": 1,
            "sidoName": sido, "ver": "1.0"})
        if payload is None:
            return None
        try:
            rows = payload["response"]["body"]["items"]
        except (KeyError, TypeError):
            self._miss("unexpected_shape", str(list(payload))[:120])
            return None
        match = next((row for row in rows or [] if row.get("stationName") == district), None)
        if match is None:
            self._miss("no_station", f"{sido} 에 '{district}' 측정소가 없다")
            return None
        return self.stamp(reading(match, source=self.name), source=self.name)


__all__ = ["ALERT_THRESHOLDS", "AirKoreaRealtime", "alert_level", "reading"]
