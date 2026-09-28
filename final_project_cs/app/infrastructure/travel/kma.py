# -*- coding: utf-8 -*-
"""기상청 단기예보 어댑터 — 공공데이터포털 「기상청_단기예보 조회서비스」.

실측(2026-09-14):

    GET https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst
        ?serviceKey=…&dataType=JSON&base_date=20260914&base_time=0800&nx=60&ny=127
    → HTTP 200, header {"resultCode":"00","resultMsg":"NORMAL_SERVICE"}
      item 예: {"category":"TMP","fcstDate":"20260914","fcstTime":"0900","fcstValue":"21"}

★Open-Meteo 와 **같은 모양**으로 돌려준다(`temperature_c`·`precipitation_probability`·
  `precipitation_mm`·`wind_speed_kmh`·`matched_hour`·`kind`). Team 은 어느 공급자가
  답했는지 몰라도 되고, 알고 싶으면 `source` 를 본다. 모양이 갈리면 대체 소스로
  넘어가는 순간 Team 문구가 깨진다.

★단위가 다르다. 기상청 `WSD` 는 **m/s**, Open-Meteo `wind_speed_10m` 은 **km/h** 다.
  환산하지 않고 넘기면 풍속이 3.6배 작게 보여 주의 문구가 안 뜬다.

★좌표가 아니라 **격자(nx, ny)** 로 묻는다. 변환식은 기상청 제공 LCC(DFS) 식이다.
  서울시청(37.5665, 126.9780) → (60, 127) 이 기상청 격자표와 맞는지 단위
  시험이 확인한다.

★예보가 닿는 범위는 **발표 시각부터 약 3일**이다(Open-Meteo 16일보다 짧다). 그
  밖을 물으면 모름이다 — 가까운 칸으로 바꿔치기하지 않는다.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .base import TravelSource

ENDPOINT = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
KST = ZoneInfo("Asia/Seoul")

#: 단기예보 발표 시각(시). 발표 후 **약 10분 뒤**부터 조회된다(기상청 활용가이드).
ISSUE_HOURS = (2, 5, 8, 11, 14, 17, 20, 23)
ISSUE_DELAY = timedelta(minutes=10)

#: 한 발표에 담기는 항목 수는 12종 × 최대 약 80시간 ≈ 1,000 을 넘지 않는다.
#: ★한 번에 받는다. 페이지를 넘기다 중간에 실패하면 반쪽 표로 판정하게 된다.
PAGE_ROWS = 1000

#: `WSD` m/s → km/h
MS_TO_KMH = 3.6


# ── 격자 변환 (기상청 DFS · Lambert Conformal Conic) ─────────────────
_RE, _GRID = 6371.00877, 5.0
_SLAT1, _SLAT2, _OLON, _OLAT = 30.0, 60.0, 126.0, 38.0
_XO, _YO = 43, 136


def to_grid(latitude: float, longitude: float) -> tuple[int, int]:
    """위경도 → 기상청 격자 (nx, ny)."""
    degrad = math.pi / 180.0
    re = _RE / _GRID
    slat1, slat2 = _SLAT1 * degrad, _SLAT2 * degrad
    olon, olat = _OLON * degrad, _OLAT * degrad
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5))
    sf = math.pow(math.tan(math.pi * 0.25 + slat1 * 0.5), sn) * math.cos(slat1) / sn
    ro = re * sf / math.pow(math.tan(math.pi * 0.25 + olat * 0.5), sn)
    ra = re * sf / math.pow(math.tan(math.pi * 0.25 + latitude * degrad * 0.5), sn)
    theta = longitude * degrad - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    return (int(math.floor(ra * math.sin(theta) + _XO + 0.5)),
            int(math.floor(ro - ra * math.cos(theta) + _YO + 0.5)))


def latest_issue(now: datetime) -> datetime:
    """`now`(KST) 에 조회 가능한 가장 최근 발표 시각."""
    usable = now - ISSUE_DELAY
    for hour in reversed(ISSUE_HOURS):
        if usable.hour >= hour:
            return usable.replace(hour=hour, minute=0, second=0, microsecond=0)
    # 02시 발표 전 — 전날 23시
    return (usable - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0)


def parse_precipitation(text: Any) -> float | None:
    """`PCP` 문자열 → mm. **모르는 모양이면 `None`** — 0 으로 채우지 않는다.

    기상청 표기(활용가이드): 「강수없음」 · 「1mm 미만」 · 「1.0mm」 ·
    「30.0~50.0mm」 · 「50.0mm 이상」.
    ★범위·이상·미만은 **하한**을 돌려준다. 상한을 모르는 값에 상한을 지어내지
      않는다. 「1mm 미만」의 하한은 0 보다 크다는 것밖에 모르므로 0.0 이 아니라
      `None` 이 맞겠지만, 그러면 비가 온다는 사실까지 사라진다 — 그래서
      기상청이 정한 표기 최소 단위 0.1 을 쓴다.
    """
    if text is None:
        return None
    value = str(text).strip()
    if value in ("강수없음", "0", "-"):
        return 0.0
    if "미만" in value:
        return 0.1
    head = value.replace("mm", "").replace("이상", "").split("~")[0].strip()
    try:
        return float(head)
    except ValueError:
        return None


class KmaWeather(TravelSource):
    name = "kma"

    def __init__(self, *, service_key: str, now=None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key
        # ★시각 주입 지점. 발표 시각 규칙은 시각에 따라 갈리므로 시험이 고정한다.
        self._now = now or (lambda: datetime.now(KST))

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        """기상청은 `response.header.resultCode` 로 답한다. `00` 만 성공이다.

        ★`03 NO_DATA` 도 HTTP 200 이다. 이걸 성공으로 받으면 빈 표를 「확인했다」
          로 읽는다.
        """
        header = (payload.get("response") or {}).get("header") if isinstance(
            payload.get("response"), dict) else None
        if isinstance(header, dict):
            code = str(header.get("resultCode", ""))
            if code != "00":
                return f'{code} {header.get("resultMsg", "")}'.strip()
            return None
        return TravelSource._body_error(payload)

    def forecast(self, *, latitude: float, longitude: float,
                 at: datetime | None = None) -> dict[str, Any] | None:
        """`at` 시각의 예보 한 칸. 못 가져오거나 범위 밖이면 `None`(모름)."""
        now = self._now()
        target = self._as_kst(at) if at is not None else now
        issue = latest_issue(now)
        if target < issue - timedelta(hours=1):
            self._miss("before_forecast_window", f"요청 {target}, 발표 {issue}")
            return None

        nx, ny = to_grid(latitude, longitude)
        payload = self._fetch_json(ENDPOINT, {
            "serviceKey": self._key, "pageNo": 1, "numOfRows": PAGE_ROWS,
            "dataType": "JSON", "base_date": issue.strftime("%Y%m%d"),
            "base_time": issue.strftime("%H00"), "nx": nx, "ny": ny,
        })
        if payload is None:
            return None

        try:
            items = payload["response"]["body"]["items"]["item"]
        except (KeyError, TypeError):
            self._miss("empty_items", str(list(payload))[:120])
            return None
        if not isinstance(items, list) or not items:
            self._miss("empty_items", "item 없음")
            return None

        slot = target.replace(minute=0, second=0, microsecond=0)
        date_key, time_key = slot.strftime("%Y%m%d"), slot.strftime("%H00")
        cell = {item.get("category"): item.get("fcstValue") for item in items
                if item.get("fcstDate") == date_key and item.get("fcstTime") == time_key}
        if not cell:
            # ★정시 칸이 표에 없다 = 예보 범위 밖. 근처 칸으로 바꿔치기하지 않는다.
            self._miss("hour_not_in_response", f"{date_key} {time_key}")
            return None

        wind_ms = self._number(cell.get("WSD"))
        return self.stamp({
            "latitude": latitude,
            "longitude": longitude,
            "grid": {"nx": nx, "ny": ny},
            "requested_at": at.isoformat() if at else None,
            "matched_hour": slot.strftime("%Y-%m-%dT%H:%M"),
            "issued_at": issue.isoformat(),
            "temperature_c": self._number(cell.get("TMP")),
            "precipitation_probability": self._integer(cell.get("POP")),
            "precipitation_mm": parse_precipitation(cell.get("PCP")),
            "wind_speed_kmh": round(wind_ms * MS_TO_KMH, 1) if wind_ms is not None else None,
            "timezone": "Asia/Seoul",
            "kind": "forecast",   # ★관찰이 아니다
        }, source=self.name)

    # ── 부품 ────────────────────────────────────────────────────
    @staticmethod
    def _as_kst(value: datetime) -> datetime:
        """★시각대 없는 값은 KST 로 읽는다 — 서울만 다루는 제품이다(v11 §1)."""
        if value.tzinfo is None:
            return value.replace(tzinfo=KST)
        return value.astimezone(KST)

    @staticmethod
    def _number(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None      # ★없으면 없는 대로. 0 으로 채우지 않는다

    @staticmethod
    def _integer(value: Any) -> int | None:
        number = KmaWeather._number(value)
        return int(number) if number is not None else None


__all__ = ["ENDPOINT", "KmaWeather", "latest_issue", "parse_precipitation", "to_grid"]
