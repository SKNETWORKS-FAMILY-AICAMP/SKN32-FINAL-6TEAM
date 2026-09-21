# -*- coding: utf-8 -*-
"""한국관광공사 TourAPI(KorService2) — 장소 좌표와 **운영시간 원문**.

실측(2026-09-10, 실 키로):

    searchKeyword2 keyword=경복궁
      → 126508 / 12 경복궁          (37.5760, 126.9767)
        3577022 / 39 경복궁          ← ★울산 **음식점**
        2648460 / 15 경복궁 별빛야행

    detailIntro2 contentId=126508 contentTypeId=12
      usetime  "[1월~2월/11월~12월]09:00~17:00 (입장마감 16:00)[3월~5월/9월~10월]…"
      restdate "매주 화요일. 단 정기휴일이 공휴일·대체공휴일과 겹치면 개방하며,
                그 다음의 첫 번째 비공휴일이 정기휴일임"

실측(2026-09-21, 실 키로) — ACOP_TOUR_API_KEY 검증. 4/4 live 테스트 통과:
  [1] find("경복궁", allowed_types={12,14,28}) → content_id=126508, lat=37.5760, lon=126.9767
  [2] operating(126508, 12) → usetime/restdate 원문 정상 반환, parsed=False
  [3] by_content_id(126508, 12) → matched_title=경복궁, address=서울특별시 종로구 사직로 161
  [4] find("듣도보도못한곳XYZ") → None (not_found 미스 정상 기록)

★★**`usetime`·`restdate` 를 파싱해 boolean 으로 만들지 않는다.**
  둘 다 **자연어**다. 위 `restdate` 하나만 봐도 「매주 화요일 휴무 / 단 공휴일과
  겹치면 개방 / 그 다음 첫 비공휴일이 휴무」라는 3중 조건이다. 이걸 규칙으로
  펴다가 하나 틀리면 **고객이 문 닫힌 곳 앞에 선다.**

  그래서 이 어댑터는 **원문을 그대로 싣고 `parsed=False` 를 밝힌다.**
  Team 은 원문을 근거로 전하고, 확정 판정이 필요하면 사람에게 넘긴다
  (`CLAUDE.md` §0.1 — 근거를 못 대면 확정 답변을 만들지 않는다).

★**동명이인이 실재한다.** 「경복궁」이 서울 궁궐(12)·**울산 음식점**(39)·
  야간행사(15) 셋으로 나온다. 이름만으로 하나를 고르면 **울산 음식점 좌표로
  날씨를 답하게 된다.** 제목이 정확히 같은 것 하나일 때만 확정한다.
"""
from __future__ import annotations

from typing import Any

from .base import TravelSource

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"

#: 신분류체계 대분류(lclsSystm1) → 이름. 한국관광공사 2023년 개편.
#: 실측(2026-09-21): searchKeyword2 응답에서 직접 확인한 코드.
#: Activity 담당(wiki/teams/activity.md §범위): NA·HS·VE·LS·EX·SH.
#: 대분류 10종 중 9종 확인 — 나머지 1종은 아직 미관측.
LARGE_CLASS_NAMES = {
    # ── Activity 담당 ──────────────────────────────────────
    "NA": "자연관광",    # 산·하천·해양·생태·자연공원
    "HS": "역사관광",    # 역사유적지·유물·종교성지·안보관광지 (경복궁=HS01)
    "VE": "문화관광",    # 랜드마크·테마파크·공연·전시·박물관·미술관
    "LS": "레저스포츠",  # 골프·스키·수상레저·항공레저
    "EX": "체험관광",    # 전통·공예·농산어촌체험·템플스테이·웰니스
    "SH": "쇼핑",        # 대형마트(SH03) 포함
    # ── Activity 미담당 ────────────────────────────────────
    "FD": "음식",        # 음식점·식도락
    "AC": "숙박",        # 호텔·리조트·펜션·캠핑
    "EV": "행사·이벤트", # 축제·공연·전시 행사 (contenttypeid=15)
}

#: 구분류(contenttypeid) → 이름. ★API 서버 필터링(find() allowed_types,
#: watch.py KIND_TO_CONTENT_TYPES)은 여전히 이 축을 쓴다 —
#: 신분류 lclsSystm1 코드로 서버 필터링이 되는지 미확인.
CONTENT_TYPE_NAMES = {
    "12": "관광지", "14": "문화시설", "15": "행사·공연·축제", "25": "여행코스",
    "28": "레포츠", "32": "숙박", "38": "쇼핑", "39": "음식점",
}


class TourApiPlace(TravelSource):
    name = "tour_api"

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key

    def _common(self) -> dict[str, Any]:
        return {"serviceKey": self._key, "MobileOS": "ETC",
                "MobileApp": "acop", "_type": "json"}

    # ── 찾기 ────────────────────────────────────────────────────
    def find(self, place_name: str, *,
             content_type_id: str | None = None,
             allowed_types: "set[str] | None" = None,
             allowed_large_classes: "set[str] | None" = None) -> dict[str, Any] | None:
        """이름으로 장소 하나를 찾는다. 애매하면 `None`(모름).

        ★`content_type_id` 를 주면 공급자 쪽에서 그 종류로 좁혀 검색한다.
        ★`allowed_types` 는 **받아 온 뒤 걸러 낼** 구분류(contenttypeid) 집합이다.
        ★`allowed_large_classes` 는 **신분류체계 대분류(lclsSystm1)** 로 걸러 낼
          집합이다(2026-09-21 개편). `watch.py.KIND_TO_LARGE_CLASSES` 가 이걸 쓴다.

          서버 파라미터는 여전히 contenttypeid 한 종류만 받는다 — lclsSystm1 로
          서버 필터링이 되는지 미확인. 따라서 넓게 받아 클라이언트에서 좁힌다.
        """
        if not self._key:
            self._miss("no_service_key")
            return None
        if not place_name or not place_name.strip():
            self._miss("no_place_name")
            return None

        params = {**self._common(), "keyword": place_name.strip(),
                  "numOfRows": "20", "pageNo": "1"}
        if content_type_id:
            params["contentTypeId"] = content_type_id

        rows = self._items(self._fetch_json(f"{BASE_URL}/searchKeyword2", params))
        if rows is None:
            return None
        if not rows:
            self._miss("not_found", place_name)
            return None

        # ★제목이 **정확히 같은 것**만 남긴다. 부분일치를 받아들이면
        #   「경복궁」 검색에 「경복궁 별빛야행」이 섞인다.
        wanted = place_name.strip()
        exact = [row for row in rows if str(row.get("title", "")).strip() == wanted]
        if allowed_types:
            # 구분류(contenttypeid) 필터 — 하위호환.
            exact = [row for row in exact
                     if str(row.get("contenttypeid") or "") in allowed_types]
        if allowed_large_classes:
            # ★신분류체계 대분류(lclsSystm1) 필터 — 같은 contenttypeid=12라도
            #   HS(역사관광)·NA(자연관광)·VE(문화관광)를 정확히 구분한다.
            exact = [row for row in exact
                     if str(row.get("lclsSystm1") or "") in allowed_large_classes]
        if not exact:
            self._miss("no_exact_title", f"{wanted}: {len(rows)}건 중 정확일치 0")
            return None
        if len(exact) > 1:
            kinds = ", ".join(sorted({str(r.get("contenttypeid")) for r in exact}))
            self._miss("ambiguous", f"{wanted}: {len(exact)}건 (타입 {kinds})")
            return None

        row = exact[0]
        latitude, longitude = self._number(row, "mapy"), self._number(row, "mapx")
        if latitude is None or longitude is None:
            self._miss("no_coordinates", wanted)
            return None

        content_type = str(row.get("contenttypeid") or "")
        large_class = str(row.get("lclsSystm1") or "")
        return self.stamp({
            "content_id": str(row.get("contentid") or ""),
            "content_type_id": content_type,
            "content_type_name": CONTENT_TYPE_NAMES.get(content_type),
            "large_class_code": large_class or None,
            "large_class_name": LARGE_CLASS_NAMES.get(large_class),
            "matched_title": str(row.get("title") or ""),
            "latitude": latitude,
            "longitude": longitude,
            "address": str(row.get("addr1") or ""),
        }, source=self.name)

    # ── 운영 정보 ────────────────────────────────────────────────
    def operating(self, content_id: str, content_type_id: str
                  ) -> dict[str, Any] | None:
        """운영시간·휴무일을 **원문 그대로**. 못 가져오면 `None`."""
        if not self._key:
            self._miss("no_service_key")
            return None
        rows = self._items(self._fetch_json(f"{BASE_URL}/detailIntro2", {
            **self._common(), "contentId": content_id,
            "contentTypeId": content_type_id}))
        if rows is None:
            return None
        if not rows:
            self._miss("no_intro", content_id)
            return None

        row = rows[0]
        # ★타입마다 필드 이름이 다르다. 음식점은 opentimefood/restdatefood 다.
        usetime = self._first(row, "usetime", "usetimeculture", "opentimefood",
                              "usetimeleports", "opentime")
        restdate = self._first(row, "restdate", "restdateculture", "restdatefood",
                               "restdateleports", "restdateshopping")
        if not usetime and not restdate:
            self._miss("no_hours_fields", content_id)
            return None

        return self.stamp({
            "content_id": content_id,
            # ★★원문이다. 우리가 해석한 값이 아니다.
            "usetime_text": usetime or None,
            "restdate_text": restdate or None,
            "parsed": False,
            # ★이 소스는 「그 시각에 여는가」를 boolean 으로 답하지 않는다.
            "answers_open_at_slot": False,
            "info_phone": self._first(row, "infocenter", "infocenterfood",
                                      "infocenterculture") or None,
        }, source=self.name)

    def by_content_id(self, content_id: str, content_type_id: str
                      ) -> dict[str, Any] | None:
        """이미 아는 신원으로 집는다. ★이름으로 헤매지 않는다 — 애매함이 없다."""
        if not self._key:
            self._miss("no_service_key")
            return None
        if not content_id:
            self._miss("no_content_id")
            return None

        # ★★`detailCommon2` 는 **`contentTypeId` 를 받지 않는다**(2026-09-10 실측).
        #   넣으면 `INVALID_REQUEST_PARAMETER_ERROR(contentTypeId)` 가 난다.
        #   같은 포털인데 오퍼레이션마다 받는 인자가 다르다 — 한 번 통했다고
        #   다른 곳에도 통할 것으로 보면 안 된다.
        rows = self._items(self._fetch_json(
            f"{BASE_URL}/detailCommon2", {**self._common(), "contentId": content_id}))
        if rows is None:
            return None
        if not rows:
            # ★없어졌을 수도 있고 일시적일 수도 있다. 「모름」으로 둔다 —
            #   「폐업」으로 단정하면 그게 고객 답변까지 간다.
            self._miss("content_not_found", content_id)
            return None

        row = rows[0]
        large_class = str(row.get("lclsSystm1") or "")
        return self.stamp({
            "content_id": content_id,
            "content_type_id": str(row.get("contenttypeid") or content_type_id),
            "content_type_name": CONTENT_TYPE_NAMES.get(
                str(row.get("contenttypeid") or content_type_id)),
            "large_class_code": large_class or None,
            "large_class_name": LARGE_CLASS_NAMES.get(large_class),
            "matched_title": str(row.get("title") or ""),
            "latitude": self._number(row, "mapy"),
            "longitude": self._number(row, "mapx"),
            "address": str(row.get("addr1") or ""),
        }, source=self.name)

    # ── 지역 단위 수집 (카탈로그 동기화용) ──────────────────────
    def area_page(self, area_code: str, *, page: int, rows: int
                  ) -> dict[str, Any] | None:
        """지역 한 페이지. ★**사용자별이 아니라 지역별로 당긴다** —
        그래야 콜 수가 사용자 수에 비례하지 않는다."""
        body = self._body(f"{BASE_URL}/areaBasedList2", {
            **self._common(), "areaCode": area_code,
            "numOfRows": str(rows), "pageNo": str(page), "arrange": "C"})
        if body is None:
            return None
        return {"total_count": body.get("totalCount"),
                "items": [self._catalog_row(r, area_code)
                          for r in self._rows(body)]}

    def changed_since(self, area_code: str, *, since: str, rows: int
                      ) -> dict[str, Any] | None:
        """그 시각 이후 바뀐 것만.

        ★★2026-09-10 실측: 7가지 조합을 다 시도해도 **0건**이었다
          (8/14자리 `modifiedtime`, `showflag` 1/0/생략, 지역 서울/제주/생략,
          기준일 2025-01~2026-09). 같은 키로 `areaBasedList2` 는 2,063건이
          오므로 키 문제가 아니라 **파라미터를 못 맞춘 것**이다.
          그래서 이 결과를 **믿을 수 있는 것으로 취급하지 않는다** —
          `PlaceCatalogSync.audit()` 이 전체 대조로 판정한다.
        """
        body = self._body(f"{BASE_URL}/areaBasedSyncList2", {
            **self._common(), "areaCode": area_code, "numOfRows": str(rows),
            "pageNo": "1", "modifiedtime": since, "showflag": "1"})
        if body is None:
            return None
        return {"total_count": body.get("totalCount"),
                "items": [self._catalog_row(r, area_code)
                          for r in self._rows(body)]}

    @staticmethod
    def _catalog_row(row: dict[str, Any], area_code: str) -> dict[str, Any]:
        """카탈로그 표가 쓰는 모양으로. ★원본도 함께 들고 간다 — 나중에
        필요해진 필드를 다시 받으러 나가지 않아도 되게."""
        def number(key: str) -> float | None:
            try:
                return float(str(row.get(key) or "").strip())
            except (TypeError, ValueError):
                return None

        return {
            "content_id": str(row.get("contentid") or ""),
            "content_type_id": str(row.get("contenttypeid") or "") or None,
            "area_code": area_code,
            "title": str(row.get("title") or "").strip(),
            "address": str(row.get("addr1") or "").strip() or None,
            "latitude": number("mapy"), "longitude": number("mapx"),
            "large_class_code": str(row.get("lclsSystm1") or "") or None,
            "large_class_name": LARGE_CLASS_NAMES.get(str(row.get("lclsSystm1") or "")),
            "lclsSystm2": str(row.get("lclsSystm2") or "") or None,
            "lclsSystm3": str(row.get("lclsSystm3") or "") or None,
            # ★공급자가 말한 수정 시각. 우리가 받은 시각과 섞지 않는다.
            "source_modified_at": str(row.get("modifiedtime") or "") or None,
            "raw": row,
        }

    def _body(self, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        payload = self._fetch_json(url, params)
        if payload is None:
            return None
        body = (payload.get("response") or {}).get("body")
        if not isinstance(body, dict):
            self._miss("unexpected_envelope", str(list(payload))[:120])
            return None
        return body

    @staticmethod
    def _rows(body: dict[str, Any]) -> list[dict[str, Any]]:
        items = body.get("items")
        if not isinstance(items, dict):
            return []          # ★0건은 실패가 아니다
        rows = items.get("item") or []
        return [rows] if isinstance(rows, dict) else list(rows)

    # ── 부품 ────────────────────────────────────────────────────
    def _items(self, payload: dict[str, Any] | None) -> list[dict[str, Any]] | None:
        if payload is None:
            return None
        body = (payload.get("response") or {}).get("body")
        if not isinstance(body, dict):
            self._miss("unexpected_envelope", str(list(payload))[:120])
            return None
        items = body.get("items")
        if not isinstance(items, dict):
            return []          # ★결과 0건은 실패가 아니다. 빈 목록이다
        rows = items.get("item") or []
        return [rows] if isinstance(rows, dict) else list(rows)

    @staticmethod
    def _first(row: dict[str, Any], *names: str) -> str:
        for name in names:
            value = str(row.get(name) or "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _number(row: dict[str, Any], key: str) -> float | None:
        try:
            return float(str(row.get(key) or "").strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        """포털 정상 응답은 `resultCode` 가 `00` 또는 `0000` 이다."""
        header = (payload.get("response") or {}).get("header")
        if isinstance(header, dict):
            code = str(header.get("resultCode", ""))
            if code and code not in ("00", "0000"):
                return f'{code} {header.get("resultMsg", "")}'.strip()
        return TravelSource._body_error(payload)


__all__ = ["BASE_URL", "CONTENT_TYPE_NAMES", "LARGE_CLASS_NAMES", "TourApiPlace"]
