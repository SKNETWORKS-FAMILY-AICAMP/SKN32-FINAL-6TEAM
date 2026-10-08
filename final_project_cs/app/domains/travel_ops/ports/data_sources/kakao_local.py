# -*- coding: utf-8 -*-
"""카카오 로컬 키워드 검색 — 계획 읽기의 **장소 이름 찾기** 전용. `[2026-09-27]` 설계서 §4-1 4단계 · §4-5

★약관(카카오디벨로퍼스 운영정책 제5조 · 서비스 약관 제11조 ③, triPilot : RAG 가 읽음):
  받은 값을 공용 표에 쌓거나 다른 고객에게 재사용하면 「복제·디렉터리 입력」이 될 수 있다. 그래서
    ① **이름 찾기에만** 쓴다 — 찾은 이름으로 관광공사를 다시 조회한다
    ② 관광공사에 없으면 카카오 값을 **그 여행 항목에만**(출처 `kakao`) 싣고 공용 표에는 넣지 않는다
    ③ 응답을 공용 캐시에 담지 않는다(`cache_ttl_seconds = 0`)
★무료 한도는 키워드 검색 하루 100,000건(개발자 계정에서 처음 켠 앱 하나에만). 한도 초과 사용 자체가 금지라
  호출 예산(`call_budget`, 하루 `travel.kakao_budget`)을 **필수**로 건다 — 없으면 어댑터를 만들지 않는다.
★서울 범위(사각)로만 찾고, 받은 뒤 주소로 한 번 더 거른다(사각은 경기 일부를 포함한다).

출처: `GET https://dapi.kakao.com/v2/local/search/keyword.json` · 헤더 `Authorization: KakaoAK {키}`.
"""
from __future__ import annotations

from typing import Any, Callable

import httpx

from .base import TravelSource

URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
#: 서울 사각(경도 최소, 위도 최소, 경도 최대, 위도 최대) — 경기 일부가 들어오므로 주소로 다시 거른다
SEOUL_RECT = "126.76,37.41,127.19,37.72"
METER = "kakao_local_keyword"
#: 가까운 곳 찾기 반경(미터) — 카카오 키워드 검색의 최대값이 20,000 이다. 우리가 고른 값
NEAR_RADIUS_M = 20000


class KakaoLocal(TravelSource):
    name = "kakao"
    cache_ttl_seconds = 0          # ★약관 — 응답을 담아 두지 않는다

    def __init__(self, *, api_key: str, budget: Any,
                 request: Callable[..., httpx.Response] | None = None, **kwargs: Any) -> None:
        kwargs.pop("cache", None)
        super().__init__(**kwargs)
        if not api_key:
            raise ValueError("ACOP_KAKAO_REST_API_KEY 가 비어 있다 — 어댑터를 만들지 않는다")
        if budget is None:
            raise ValueError("호출 예산 없이 카카오를 부르지 않는다 — 무료 한도 초과 사용은 약관 위반이다")
        self._key, self._budget = api_key, budget
        self._request = request or (lambda url, params, headers: httpx.get(
            url, params=params, headers=headers, timeout=self._timeout))

    def search(self, query: str, *, size: int = 5, near: tuple[float, float] | None = None,
               radius: int | None = None, category_group_code: str | None = None,
               anywhere: bool = False) -> list[dict[str, Any]] | None:
        """서울 안의 결과(주소가 「서울」로 시작하는 것)만. 못 불렀으면 `None`, 없으면 `[]`.

        `near=(위도, 경도)` 를 주면 그 점에서 반경 `NEAR_RADIUS_M` 안을 **거리순**으로 찾는다(계획 읽기의 「앞뒤 일정에
        가장 가까운 곳」). 서울 사각 대신 이 원을 쓰고, 주소로 서울만 거르는 것은 같다.
        ★`[2026-10-07]` 체인점 지점 고르기(`intake/chain_pick`) — `radius`(미터, `near` 와 함께) · `category_group_code`
          (FD6 음식점 · CE7 카페 · SW8 지하철역) · `size`(카카오 상한 15)를 받는다. 주지 않으면 예전 그대로다.
          `anywhere=True` 면 `near` 를 무시하고 서울 전역을 관련도 순으로 — 지점명 위치(「강남역」) 찾기용.
          ☆접수의 카카오 연결층이 앞 일정 좌표를 자동으로 넣어 「강남역」을 경복궁 근처에서 찾았다
        """
        if not query or not query.strip():
            return []
        if not self._allow():
            return None
        if not self._budget.try_reserve(METER):
            self._miss("budget_exhausted", METER)
            return None
        try:
            params = {"query": query.strip(), "size": str(max(1, min(int(size), 15)))}
            if category_group_code:
                params["category_group_code"] = category_group_code
            if near is not None and not anywhere:
                params.update({"y": f"{near[0]:.6f}", "x": f"{near[1]:.6f}",
                               "radius": str(max(1, min(int(radius or NEAR_RADIUS_M), NEAR_RADIUS_M))),
                               "sort": "distance"})
            else:
                params["rect"] = SEOUL_RECT
            response = self._request(URL, params, {"Authorization": f"KakaoAK {self._key}"})
        except httpx.TimeoutException as exc:
            self._miss("timeout", str(exc))
            return None
        except httpx.HTTPError as exc:
            self._miss("transport_error", f"{type(exc).__name__}: {exc}")
            return None
        if response.status_code != 200:
            self._miss(f"http_{response.status_code}", response.text[:200])
            return None
        try:
            payload = response.json()
        except ValueError:
            self._miss("not_json", response.text[:200])
            return None
        documents = payload.get("documents") if isinstance(payload, dict) else None
        if not isinstance(documents, list):
            self._miss("unexpected_shape", str(payload)[:120])
            return None
        out = []
        for doc in documents:
            address = str(doc.get("road_address_name") or doc.get("address_name") or "")
            if not address.startswith("서울"):
                continue
            try:
                latitude, longitude = float(doc["y"]), float(doc["x"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append({"id": str(doc.get("id") or ""), "name": str(doc.get("place_name") or ""),
                        "category": str(doc.get("category_name") or ""),
                        "category_group": str(doc.get("category_group_code") or ""),
                        "address": address, "latitude": latitude, "longitude": longitude})
        return out


__all__ = ["KakaoLocal", "METER", "SEOUL_RECT"]
