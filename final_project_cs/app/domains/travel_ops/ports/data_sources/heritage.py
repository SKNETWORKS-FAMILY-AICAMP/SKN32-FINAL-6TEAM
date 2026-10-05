# -*- coding: utf-8 -*-
"""국가유산청(옛 문화재청) 국가유산 OpenAPI — **키가 필요 없다.**

실측(2026-09-10):

    GET https://www.khs.go.kr/cha/SearchKindOpenapiList.do?ccbaMnm1=경복궁&pageUnit=5
    → HTTP 200, application/xml, 실제 데이터. **인증 파라미터를 아예 안 넣었다.**
      옛 도메인 www.cha.go.kr 도 같은 응답을 준다.

★**Open-Meteo 에 이어 두 번째 무키 소스다.** 나머지 정부 API 는 전부 키를
  요구했다(401 SERVICE_KEY_IS_NULL).

★★**이 소스가 주는 것과 안 주는 것을 분명히 한다.**

    준다   위도·경도 · 주소 · 관리기관 · 시대 · 해설(content) · 이미지
    안 준다 **관람시간 · 휴무일 · 요금**

  「궁·능 관람 정보」라고 부르면 과장이다. 운영시간은 TourAPI `detailIntro`
  (키 필요)나 궁능유적본부 쪽이 대야 한다. 여기서 안 오는 것을 온다고 적어
  두면 다음 사람이 그 값을 찾다가 시간을 버린다.

★그래서 이 어댑터의 쓰임은 하나다 — **좌표를 모르는 장소의 좌표를 채운다.**
  좌표가 없으면 `read.weather` 가 아무것도 못 한다(「어디인지 모르는 곳의
  날씨」는 없다). 시드의 `nowhere` 예약이 정확히 그 이유로 죽었다.
"""
from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree

from .base import TravelSource

LIST_ENDPOINT = "https://www.khs.go.kr/cha/SearchKindOpenapiList.do"
DETAIL_ENDPOINT = "https://www.khs.go.kr/cha/SearchKindOpenapiDt.do"

#: 한 번에 받아 볼 후보 수. ★크게 잡지 않는다 — 이름이 겹치면 사람이 골라야지
#:  우리가 「가장 그럴듯한 것」을 고르면 그게 지어내는 것이다.
_MAX_CANDIDATES = 5

_CDATA = re.compile(r"^\s*<!\[CDATA\[(.*?)\]\]>\s*$", re.S)


def _text(node: Any) -> str:
    """CDATA 를 벗긴 텍스트. 없으면 빈 문자열."""
    if node is None or node.text is None:
        return ""
    matched = _CDATA.match(node.text)
    return (matched.group(1) if matched else node.text).strip()


def _field(root: Any, tag: str) -> str:
    """★상세 응답은 **두 층으로 나뉘어 있다**(2026-09-10 실측).

        <result>
          <longitude>·<latitude>·<ccbaKdcd>…     ← 뿌리에 있다
          <item> <ccbaMnm1>·<ccbaLcad>·<content>… ← 나머지는 여기
        </result>

    뿌리만 보면 **좌표만 오고 이름·주소·해설이 전부 빈 문자열로 나온다** —
    처음에 그렇게 짰다가 실호출에서 잡았다. 두 곳을 다 본다.
    """
    found = root.find(tag)
    if found is None:
        found = root.find(f"item/{tag}")
    return _text(found)


class HeritageSource(TravelSource):
    """국가유산 이름 → 좌표. ★운영시간은 주지 않는다."""

    name = "heritage_khs"

    def locate(self, place_name: str) -> dict[str, Any] | None:
        """이름으로 찾아 좌표를 돌려준다. 못 찾거나 애매하면 `None`(모름).

        ★**후보가 여럿이면 고르지 않는다.** 「경복궁」으로 찾으면 근정전·경회루·
          자경전이 다 나온다(실측 5건). 그중 하나를 우리가 고르면 엉뚱한 건물의
          좌표로 날씨를 답하게 된다. 후보 수를 `candidates` 로 함께 돌려주고,
          **정확히 하나일 때만** 좌표를 확정한다.
        """
        if not place_name or not place_name.strip():
            self._miss("no_place_name")
            return None

        listing = self._fetch_xml(LIST_ENDPOINT, {
            "ccbaMnm1": place_name.strip(), "pageUnit": _MAX_CANDIDATES})
        if listing is None:
            return None

        try:
            root = ElementTree.fromstring(listing)
        except ElementTree.ParseError as exc:
            self._miss("xml_parse_error", str(exc)[:120])
            return None

        items = root.findall("item")
        if not items:
            self._miss("not_found", place_name)
            return None
        if len(items) > 1:
            # ★애매하면 확정하지 않는다. 몇 건이었는지는 남긴다.
            self._miss("ambiguous", f"{place_name}: {len(items)}건")
            return None

        item = items[0]
        detail = self._fetch_xml(DETAIL_ENDPOINT, {
            "ccbaKdcd": _text(item.find("ccbaKdcd")),
            "ccbaAsno": _text(item.find("ccbaAsno")),
            "ccbaCtcd": _text(item.find("ccbaCtcd"))})
        if detail is None:
            return None

        try:
            node = ElementTree.fromstring(detail)
        except ElementTree.ParseError as exc:
            self._miss("xml_parse_error", str(exc)[:120])
            return None

        latitude = self._number(node, "latitude")
        longitude = self._number(node, "longitude")
        if latitude is None or longitude is None:
            # ★빈 좌표가 오는 record 가 실제로 있다(2026-09-10 실측). 0 으로
            #   채우면 아프리카 앞바다 날씨를 답하게 된다.
            self._miss("no_coordinates", place_name)
            return None

        return self.stamp({
            "matched_name": _field(node, "ccbaMnm1"),
            "latitude": latitude,
            "longitude": longitude,
            "address": _field(node, "ccbaLcad"),
            "administrator": _field(node, "ccbaAdmin"),
            "kind_name": _field(node, "ccmaName"),
            # ★운영시간이 아니다. 이름을 그렇게 붙이지 않는다.
            "description": _field(node, "content")[:500],
            "provides_opening_hours": False,
        }, source=self.name)

    @staticmethod
    def _number(node: Any, tag: str) -> float | None:
        raw = _field(node, tag)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None


__all__ = ["DETAIL_ENDPOINT", "HeritageSource", "LIST_ENDPOINT"]
