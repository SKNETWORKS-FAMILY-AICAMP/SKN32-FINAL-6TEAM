# -*- coding: utf-8 -*-
"""국가유산청 어댑터 — **키가 없는 소스**라 규율이 더 중요하다.

★키가 필요 없다는 것은 「아무나 부를 수 있다」는 뜻이지 「값이 항상 옳다」가
  아니다. 오히려 인증이 없어서 실패가 **조용히** 온다 — 빈 좌표, 빈 item,
  동명이인. 그 셋을 여기서 본다.
"""
from __future__ import annotations

import httpx

from app.infrastructure.travel.heritage import HeritageSource
from app.infrastructure.travel.base import TravelSources
from app.tools.read_tools import ReadToolbox

LIST_ONE = '<?xml version="1.0"?><result><item><ccbaKdcd>11</ccbaKdcd>' \
           '<ccbaAsno>0002230000000</ccbaAsno><ccbaCtcd>11</ccbaCtcd></item></result>'
LIST_TWO = LIST_ONE.replace("</result>", "<item><ccbaKdcd>12</ccbaKdcd>"
                            "<ccbaAsno>9</ccbaAsno><ccbaCtcd>11</ccbaCtcd></item></result>")
LIST_NONE = '<?xml version="1.0"?><result></result>'


def _detail(lat="37.578342", lon="126.976953") -> str:
    return ('<?xml version="1.0"?><result>'
            f'<latitude>{lat}</latitude><longitude>{lon}</longitude>'
            '<item><ccbaMnm1><![CDATA[경복궁 근정전]]></ccbaMnm1>'
            '<ccbaLcad><![CDATA[서울특별시 종로구 사직로 161]]></ccbaLcad>'
            '<ccbaAdmin><![CDATA[국가유산청 경복궁관리소]]></ccbaAdmin>'
            '<ccmaName><![CDATA[국보]]></ccmaName>'
            '<content><![CDATA[해설]]></content></item></result>')


def _source(responses: list[str]) -> HeritageSource:
    """호출 순서대로 응답을 돌려준다 — 목록 → 상세."""
    queue = list(responses)

    def transport(url, params):
        return httpx.Response(200, text=queue.pop(0),
                              headers={"content-type": "application/xml"},
                              request=httpx.Request("GET", url))

    return HeritageSource(transport=transport)


def test_a_single_match_returns_coordinates_with_provenance():
    result = _source([LIST_ONE, _detail()]).locate("경복궁 근정전")
    assert result is not None
    assert (result["latitude"], result["longitude"]) == (37.578342, 126.976953)
    assert result["source"] == "heritage_khs"
    assert result["confirmed_at"]
    # ★두 층으로 나뉜 응답을 둘 다 읽는지 — 좌표는 뿌리, 이름은 item 안이다.
    assert result["matched_name"] == "경복궁 근정전"
    assert result["address"].startswith("서울특별시")


def test_it_says_plainly_that_it_has_no_opening_hours():
    """★「궁·능 관람 정보」로 읽히면 안 된다. 운영시간은 여기서 안 온다."""
    result = _source([LIST_ONE, _detail()]).locate("경복궁 근정전")
    assert result["provides_opening_hours"] is False
    assert "open_at_slot" not in result and "hours" not in result


def test_an_ambiguous_name_is_unknown_not_the_first_hit():
    """★★「경복궁」으로 찾으면 근정전·경회루·자경전이 다 나온다(실측 5건).

    하나를 우리가 고르면 **엉뚱한 건물의 좌표로 날씨를 답하게 된다.**
    """
    source = _source([LIST_TWO])
    assert source.locate("경복궁") is None
    assert source.misses["ambiguous"] == 1


def test_no_match_is_counted():
    source = _source([LIST_NONE])
    assert source.locate("없는 이름") is None
    assert source.misses["not_found"] == 1


def test_an_empty_coordinate_is_unknown_not_zero():
    """★빈 좌표가 오는 record 가 실제로 있다. 0 으로 채우면 앞바다 날씨가 된다."""
    source = _source([LIST_ONE, _detail(lat="", lon="")])
    assert source.locate("경복궁 근정전") is None
    assert source.misses["no_coordinates"] == 1


def test_an_empty_name_never_goes_out():
    source = _source([])
    assert source.locate("   ") is None
    assert source.misses["no_place_name"] == 1


def test_broken_xml_is_counted_not_raised():
    def transport(url, params):
        return httpx.Response(200, text="<result><unclosed>",
                              request=httpx.Request("GET", url))
    source = HeritageSource(transport=transport)
    assert source.locate("경복궁 근정전") is None
    assert source.misses["xml_parse_error"] == 1


# ── read.place 보강 ─────────────────────────────────────────────
class _FakeHeritage:
    def __init__(self, result=None):
        self.result, self.asked = result, []

    def locate(self, place_name):
        self.asked.append(place_name)
        return self.result


def _toolbox(heritage=None) -> ReadToolbox:
    return ReadToolbox(lambda: None, travel=TravelSources(heritage=heritage))


def test_a_row_that_already_has_coordinates_is_marked_as_coming_from_the_db():
    heritage = _FakeHeritage({"latitude": 1, "longitude": 2, "source": "x",
                              "confirmed_at": "t"})
    row = _toolbox(heritage)._fill_coordinates(
        {"name": "경복궁 근정전", "latitude": 37.5, "longitude": 127.0})
    assert row["coordinates_source"] == "db"
    assert heritage.asked == [], "DB 에 좌표가 있는데 바깥으로 나갔다"


def test_a_missing_coordinate_is_filled_and_the_source_is_recorded():
    """★★출처를 안 남기면 좌표가 틀렸을 때 어디를 고칠지 알 수 없다."""
    heritage = _FakeHeritage({"latitude": 37.578342, "longitude": 126.976953,
                              "source": "heritage_khs", "confirmed_at": "2026-09-10T00:00:00Z"})
    row = _toolbox(heritage)._fill_coordinates(
        {"name": "경복궁 근정전", "latitude": None, "longitude": None})
    assert (row["latitude"], row["longitude"]) == (37.578342, 126.976953)
    assert row["coordinates_source"] == "heritage_khs"
    assert row["coordinates_confirmed_at"] == "2026-09-10T00:00:00Z"


def test_when_the_source_cannot_find_it_the_coordinate_stays_empty():
    """★못 채우면 비운 채 둔다. 지어내지 않는다."""
    row = _toolbox(_FakeHeritage(None))._fill_coordinates(
        {"name": "좌표미상 체험장", "latitude": None, "longitude": None})
    assert row["latitude"] is None and row["longitude"] is None
    assert "coordinates_source" not in row


def test_without_a_heritage_source_nothing_goes_out():
    row = ReadToolbox(lambda: None)._fill_coordinates(
        {"name": "경복궁 근정전", "latitude": None, "longitude": None})
    assert row["latitude"] is None


def test_a_row_without_a_name_is_not_looked_up():
    heritage = _FakeHeritage({"latitude": 1, "longitude": 2, "source": "x", "confirmed_at": "t"})
    _toolbox(heritage)._fill_coordinates({"name": None, "latitude": None, "longitude": None})
    assert heritage.asked == []
