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

★★**`usetime`·`restdate` 를 파싱해 boolean 으로 만들지 않는다.**
  둘 다 **자연어**다. 위 `restdate` 하나만 봐도 「매주 화요일 휴무 / 단 공휴일과
  겹치면 개방 / 그 다음 첫 비공휴일이 휴무」라는 3중 조건이다. 이걸 규칙으로
  펴다가 하나 틀리면 **고객이 문 닫힌 곳 앞에 선다.**

  그래서 이 어댑터는 **원문을 그대로 싣고 `parsed=False` 를 밝힌다.**
  Team 은 원문을 근거로 전하고, 확정 판정이 필요하면 사람에게 넘긴다
  (`CLAUDE.md` §0.1 — 근거를 못 대면 확정 답변을 만들지 않는다).

  ★`[2026-09-28 사용자 결정]` **일정 생성기는 이 원문을 요일별 시각으로 옮겨 쓴다**(`domains/travel_ops/components/places/place_hours.py`).
  실제 일정 38항목 중 영업시간을 아는 항목이 0개라, 「일~목 휴무」인 곳이 월요일에 들어갔다. 이 어댑터는 여전히
  원문만 준다 — 옮기는 쪽이 위험을 줄인다: 단순한 원문만 규칙으로, 나머지는 **원문에 글자 그대로 있는 인용**이
  붙은 것만 받고, 계절이 다르면 가장 짧은 시간대, 공휴일 조건은 펴지 않고, **최종 판정은 당일 새벽 구글 확인**이 한다.

★**동명이인이 실재한다.** 「경복궁」이 서울 궁궐(12)·**울산 음식점**(39)·
  야간행사(15) 셋으로 나온다. 이름만으로 하나를 고르면 **울산 음식점 좌표로
  날씨를 답하게 된다.** 제목이 정확히 같은 것 하나일 때만 확정한다.
"""
from __future__ import annotations

import re
from typing import Any

from .base import TravelSource

BASE_URL = "https://apis.data.go.kr/B551011/KorService2"


def _bare(title: str) -> str:
    """괄호 병기 · 공백을 뺀 이름(정확 일치 비교용)."""
    return re.sub(r"\s+", "", re.sub(r"[(\[（【].*?[)\]）】]", "", title)).lower()

def _joined(title: str, bare_name: str) -> bool:
    """제목이 「이름 + 과·와·및 + 다른 이름」인가(괄호·공백을 뺀 비교). 「창덕궁과 후원」 → 「창덕궁」 이면 참."""
    rest = _bare(title)
    return bool(bare_name) and rest.startswith(bare_name) \
        and re.fullmatch(r"(과|와|및)\S+", rest[len(bare_name):]) is not None


#: 관광 타입. v11 §5 의 Activity 범위(A01 자연·A02 인문·A03 레포츠·A04 쇼핑)와
#: 대응한다. 39(음식점)는 Dining 쪽이고 32(숙박)는 Lodging 쪽이다.
CONTENT_TYPE_NAMES = {
    "12": "관광지", "14": "문화시설", "15": "행사·공연·축제", "25": "여행코스",
    "28": "레포츠", "32": "숙박", "38": "쇼핑", "39": "음식점",
}


#: 지역 코드(우리가 쓰는 구분값) → 관광공사 조회 조건. `TourApiPlace.region_filter` 참고.
#: ★서울만 쟀다(2026-09-26). 다른 지역은 재고 나서 더한다 — 추측으로 법정동 코드를 채우지 않는다.
REGION_FILTERS: dict[str, dict[str, str]] = {"1": {"lDongRegnCd": "11"}}


class TourApiPlace(TravelSource):
    name = "tour_api"
    #: ☆`[2026-09-27]` 응답 캐시를 0 으로 막았다가 `[2026-09-28]` 되돌렸다 — 보존 시간은 가드레일
    #:  `travel.tour_api_cache_seconds` 가 정한다(`base.py`). 근거는 `settings.tour_catalog_enabled` 주석
    cache_ttl_seconds = None

    def __init__(self, *, service_key: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._key = service_key

    def _common(self) -> dict[str, Any]:
        # ★`MobileApp` 은 서비스 고유명 — 운영계정(트래픽 증설) 승인 요건이다(2026-09-27, 옛 값 "acop")
        return {"serviceKey": self._key, "MobileOS": "ETC",
                "MobileApp": "triPilot", "_type": "json"}

    # ── 찾기 ────────────────────────────────────────────────────
    def find(self, place_name: str, *,
             content_type_id: str | None = None,
             allowed_types: "set[str] | None" = None,
             area_code: str | None = None) -> dict[str, Any] | None:
        """이름으로 장소 하나를 찾는다. 애매하면 `None`(모름).

        ★`content_type_id` 를 주면 공급자 쪽에서 그 종류로 좁혀 검색한다.
        ★`allowed_types` 는 **받아 온 뒤 걸러 낼** 종류들이다.

          둘을 나눈 이유(2026-09-10). 우리 `activity` 는 관광타입 하나가
          아니다 — 계획서 v11 §5 의 Activity 는 자연·인문·레포츠·쇼핑을 다
          포함해서 **12·14·28·38 에 걸친다.** 공급자 파라미터는 한 번에 한
          종류만 받으므로, 여러 종류를 허용하려면 **넓게 받아 좁게 거른다.**
          처음엔 `activity → 12` 하나로 잡았다가 레포츠·문화시설 장소가
          전부 「못 찾음」이 됐다.
        """
        if not self._key:
            self._miss("no_service_key")
            return None
        if not place_name or not place_name.strip():
            self._miss("no_place_name")
            return None

        params = {**self._common(), "keyword": place_name.strip(),
                  "numOfRows": "20", "pageNo": "1"}
        if area_code:
            # ★`[2026-09-27 실측]` 키워드 검색에도 법정동 필터가 먹는다 — 「경복궁」 정확 일치가 필터 없이는
            #   서울 궁궐(12)·울산 음식점(39) 둘이라 애매 → 모름, `lDongRegnCd=11` 이면 서울 궁궐 하나
            params.update(self.region_filter(area_code))
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
        if not exact:
            # ★괄호 병기는 같은 이름으로 본다 — 「동대문디자인플라자」 = 「동대문디자인플라자(DDP)」(2026-09-28 평가셋 9건).
            #   부분일치는 여전히 받지 않는다(「경복궁」 ≠ 「경복궁 별빛야행」)
            bare = _bare(wanted)
            exact = [row for row in rows if _bare(str(row.get("title", ""))) == bare]
        if not exact:
            # ★`[2026-09-28]` 「A과 B」 병칭도 A 로 본다 — 관광공사에 창덕궁은 「창덕궁과 후원 [유네스코 세계유산]」 하나뿐이라
            #   「창덕궁」이 정확일치 0 이었고, 등록이 카카오 후보 「창덕궁 종합관람지원센터」로 갔다(ui 세션 실서버 시험).
            #   뒤에 붙은 것이 **과·와·및 + 다른 이름**일 때만이다 — 「창덕궁 낙선재」·「창덕궁 달빛기행」은 여전히 다르다.
            #   여럿이면 아래에서 애매 → 모름이다
            exact = [row for row in rows if _joined(str(row.get("title", "")), _bare(wanted))]
        if allowed_types:
            # ★우리가 다루는 종류 밖은 뺀다. 「경복궁」의 울산 음식점(39)이
            #   activity 후보에서 이걸로 빠진다.
            exact = [row for row in exact
                     if str(row.get("contenttypeid") or "") in allowed_types]
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
        return self.stamp({
            "content_id": str(row.get("contentid") or ""),
            "content_type_id": content_type,
            "content_type_name": CONTENT_TYPE_NAMES.get(content_type),
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

    def images(self, content_id: str, *, limit: int = 8) -> list[dict[str, Any]] | None:
        """그 장소에 **등록된 사진**의 주소(`detailImage2`). 못 가져오면 `None`, 사진이 없으면 `[]`.

        ★`[2026-10-02 사용자 지시 — 계획 확인 시나리오 목업]` 수정 화면이 후보 장소의 사진을 보인다. 사진은 창작물이라 **저장하지 않는다**
          (루트 사실표 「외부 공공데이터 저장」 — 사진·소개글은 저장하지 않고 출처 표시를 유지한다). 부를 때마다 주소만 받아 그대로 넘기고
          서버는 사진 파일도 주소도 담아 두지 않는다. 출처 표시(ⓒ한국관광공사)는 부르는 쪽이 붙인다.
        """
        if not self._key:
            self._miss("no_service_key")
            return None
        if not content_id or not str(content_id).isdigit():
            self._miss("no_content_id")
            return None
        rows = self._items(self._fetch_json(f"{BASE_URL}/detailImage2", {
            **self._common(), "contentId": content_id, "imageYN": "Y", "numOfRows": str(limit), "pageNo": "1"}))
        if rows is None:
            return None
        out = []
        for row in rows:
            url = str(row.get("originimgurl") or "").strip()
            thumb = str(row.get("smallimageurl") or "").strip()
            if url.startswith(("http://", "https://")):
                # 썸네일 주소도 같은 검사를 한다 — 원본만 거르면 `javascript:` 같은 주소가 썸네일 칸으로 새어 나간다
                out.append({"url": url, "thumb": thumb if thumb.startswith(("http://", "https://")) else None,
                            "name": str(row.get("imgname") or "").strip() or None})
        return out

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
        return self.stamp({
            "content_id": content_id,
            "content_type_id": str(row.get("contenttypeid") or content_type_id),
            "content_type_name": CONTENT_TYPE_NAMES.get(
                str(row.get("contenttypeid") or content_type_id)),
            "matched_title": str(row.get("title") or ""),
            "latitude": self._number(row, "mapy"),
            "longitude": self._number(row, "mapx"),
            "address": str(row.get("addr1") or ""),
        }, source=self.name)

    # ── 지역 단위 수집 (카탈로그 동기화용) ──────────────────────
    @staticmethod
    def region_filter(area_code: str) -> dict[str, str]:
        """지역 수집의 거르는 조건. ★서울은 **법정동 코드**(`lDongRegnCd=11`)로 거른다.

        ★★`[2026-09-26 실측, 같은 키]` `areaBasedList2` 의 서울 전체 건수 —
          `areaCode=1` 이면 **1,965건**, `lDongRegnCd=11` 이면 **7,996건**. 응답 대부분이 `areacode` 를
          빈칸으로 주어 지역 코드로 거르면 서울 자료의 약 24.6%만 온다. 그래서 `place_catalog` 에
          경복궁(관광지 12)·명동난타극장·토속촌삼계탕이 없었다(triPilot : RAG 세션 인계, 이 세션이 다시 쟀다).
        ★저장하는 구분값(`area_code`)은 그대로다 — 장소를 읽는 쪽(`planner.load_candidates`)이 그 값으로 찾는다.
        ★표에 없는 지역은 예전처럼 `areaCode` 로 거른다(그 지역은 아직 재지 않았다).
        """
        return dict(REGION_FILTERS.get(str(area_code), {"areaCode": str(area_code)}))

    def area_page(self, area_code: str, *, page: int, rows: int
                  ) -> dict[str, Any] | None:
        """지역 한 페이지. ★**사용자별이 아니라 지역별로 당긴다** —
        그래야 콜 수가 사용자 수에 비례하지 않는다."""
        body = self._body(f"{BASE_URL}/areaBasedList2", {
            **self._common(), **self.region_filter(area_code),
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
            **self._common(), **self.region_filter(area_code), "numOfRows": str(rows),
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


__all__ = ["BASE_URL", "CONTENT_TYPE_NAMES", "TourApiPlace"]
