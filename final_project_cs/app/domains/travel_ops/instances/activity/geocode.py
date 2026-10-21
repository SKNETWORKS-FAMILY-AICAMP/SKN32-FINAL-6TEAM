# -*- coding: utf-8 -*-
"""주소 → 좌표 — 브이월드(국토교통부) 지오코더. 활동 장소의 좌표를 채울 때 쓴다. `[2026-10-19 사용자 결정]`

☆왜: 원장에 없는 장소는 카카오로 **실존만** 확인하고(카카오 응답은 저장하지 않는다 — 운영정책 제5조), 주소 · 운영시간은 웹 검색으로 얻는다.
  좌표는 그 **주소를 지오코더에 넣어** 얻는다 — 거리 계산 · 대체 후보 · 같은 장소 판정이 좌표를 쓴다.
★브이월드는 공공 데이터라 좌표를 저장해도 된다(다이닝 마이그레이션 227의 기록 · 구글 좌표는 저장하지 않는다). 키는 코어 설정 `vworld_api_key`(`ACOP_VWORLD_API_KEY`).
★호출 방식은 `scripts/geocode_vworld.py`(원장 CSV 의 빈 좌표를 채우던 스크립트)와 같다 — 도로명 → 지번 순, 서울 범위 밖이면 실패.
★**「없음」과 「못 물어봄」을 가른다**(이 프로젝트의 원칙): `not_found`(주소를 못 찾았다)와 `unavailable`(키 없음 · 네트워크 · 서비스 오류)는 다르다.
  못 물어본 것을 「주소가 틀렸다」로 읽지 않는다.
★키가 로그 · 결과 · 오류에 실리지 않게 한다 — 예외는 **종류 이름만** 남긴다(예외 메시지에 요청 주소(키)가 실릴 수 있다).
★이 파일은 **좌표를 구하기만 한다.** DB 에 쓰지 않는다 — 쓰는 곳은 부르는 쪽이다. 네트워크 호출은 `fetch` 로 바꿀 수 있다(시험).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

API = "https://api.vworld.kr/req/address"
#: 서비스 범위 — 서울(`scripts/geocode_vworld.py` 와 같다). 밖이면 엉뚱한 곳의 같은 주소일 수 있어 실패로 본다.
SEOUL_LON = (126.7, 127.3)
SEOUL_LAT = (37.4, 37.75)
TIMEOUT_SECONDS = 10.0
#: 도로명 주소 → 지번 주소 순으로 묻는다
KINDS = ("road", "parcel")

OK = "ok"
NOT_FOUND = "not_found"            # 주소를 못 찾았다(서비스는 정상) — 서울 밖도 여기
UNAVAILABLE = "unavailable"        # 못 물어봤다(키 없음 · 네트워크 · 서비스 오류) — 「없음」이 아니다
NO_ADDRESS = "no_address"          # 물을 주소가 비었다


@dataclass(frozen=True)
class GeoResult:
    status: str                    # ok · not_found · unavailable · no_address
    latitude: float | None = None
    longitude: float | None = None
    kind: str | None = None        # 어느 주소 종류로 찾았나 — road · parcel
    reason: str | None = None      # 실패 사유(키 · 주소 원문은 싣지 않는다)

    @property
    def ok(self) -> bool:
        return self.status == OK


def clean_address(address: str | None) -> str:
    """지오코더에 넣을 주소 — 「서울특별시」 중복 · 괄호(동 · 건물명) · 겹친 공백을 정리한다."""
    text = re.sub(r"(서울특별시\s+)+", "서울특별시 ", (address or "").strip())
    text = re.sub(r"\(.*?\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _http_get(url: str, params: dict[str, str], timeout: float) -> dict[str, Any]:
    import httpx

    response = httpx.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


class VWorldGeocoder:
    """브이월드 지오코더. `fetch(url, params, timeout) -> dict` 로 네트워크를 바꿀 수 있다(시험)."""

    def __init__(self, key: str | None, *, fetch: Callable[[str, dict[str, str], float], dict[str, Any]] | None = None,
                 timeout: float = TIMEOUT_SECONDS) -> None:
        self._key = (key or "").strip()
        self._fetch = fetch or _http_get
        self._timeout = timeout
        #: 실제로 부른 횟수 — 호출 예산 · 시험용
        self.calls = 0

    @classmethod
    def from_settings(cls, **kwargs: Any) -> "VWorldGeocoder":
        """코어 설정(`vworld_api_key`)에서 키를 읽는다. 키가 없으면 `geocode` 가 `unavailable`(no_key) 이다."""
        from app.core.settings import get_settings

        return cls(getattr(get_settings(), "vworld_api_key", ""), **kwargs)

    def geocode(self, address: str | None) -> GeoResult:
        """주소 하나의 좌표. 도로명 → 지번 순으로 묻고, 둘 다 못 찾으면 `not_found`. 못 물어본 것은 `unavailable`."""
        cleaned = clean_address(address)
        if not cleaned:
            return GeoResult(NO_ADDRESS)
        if not self._key:
            return GeoResult(UNAVAILABLE, reason="no_key")          # 키 없이 부르지 않는다 — 「없음」이라고 말할 근거가 없다
        unavailable: str | None = None
        reason = "NOT_FOUND"
        for kind in KINDS:
            outcome = self._ask(cleaned, kind)
            if outcome.ok:
                return outcome
            if outcome.status == UNAVAILABLE:
                unavailable = unavailable or outcome.reason
            else:
                reason = outcome.reason or reason
        # 한 번이라도 못 물어봤고 나머지가 못 찾은 것이면 「없음」으로 단정하지 않는다
        return GeoResult(UNAVAILABLE, reason=unavailable) if unavailable else GeoResult(NOT_FOUND, reason=reason)

    def _ask(self, address: str, kind: str) -> GeoResult:
        params = {"service": "address", "request": "getcoord", "version": "2.0", "crs": "epsg:4326", "address": address,
                  "refine": "true", "simple": "false", "format": "json", "type": kind, "key": self._key}
        self.calls += 1
        try:
            body = self._fetch(API, params, self._timeout)
            response = body["response"]
        except Exception as exc:  # noqa: BLE001 — 메시지에 요청 주소(키)가 실릴 수 있어 종류 이름만 남긴다
            return GeoResult(UNAVAILABLE, kind=kind, reason=type(exc).__name__)
        status = str(response.get("status") or "")
        if status == "NOT_FOUND":
            return GeoResult(NOT_FOUND, kind=kind, reason="NOT_FOUND")
        if status != "OK":
            return GeoResult(UNAVAILABLE, kind=kind, reason=status or "ERROR")      # INCORRECT_KEY · ERROR … 서비스 쪽 문제다
        try:
            point = response["result"]["point"]
            lon, lat = float(point["x"]), float(point["y"])
        except (KeyError, TypeError, ValueError):
            return GeoResult(UNAVAILABLE, kind=kind, reason="BAD_RESPONSE")
        if not (SEOUL_LON[0] <= lon <= SEOUL_LON[1] and SEOUL_LAT[0] <= lat <= SEOUL_LAT[1]):
            return GeoResult(NOT_FOUND, kind=kind, reason="OUT_OF_SEOUL")           # 서울 밖 같은 주소는 받지 않는다
        return GeoResult(OK, latitude=lat, longitude=lon, kind=kind)
