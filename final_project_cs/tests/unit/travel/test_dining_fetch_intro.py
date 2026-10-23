"""fetch_intro 의 응답 읽기, 남은 것 고르기, 키 고르기.

망에 닿지 않는다. 응답은 손으로 만든 문자열이다.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "fetch_intro.py")


@pytest.fixture(scope="module")
def fi():
    spec = importlib.util.spec_from_file_location("dining_fetch_intro", os.path.abspath(MODULE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dining_fetch_intro"] = mod
    spec.loader.exec_module(mod)
    return mod


def ok(items) -> str:
    return json.dumps({"response": {"header": {"resultCode": "0000", "resultMsg": "OK"},
                                    "body": {"items": items}}})


def test_행_하나를_읽는다(fi):
    assert fi.parse_response(ok({"item": [{"contentid": "1"}]})) == {"contentid": "1"}


def test_행이_dict_로_와도_읽는다(fi):
    assert fi.parse_response(ok({"item": {"contentid": "1"}})) == {"contentid": "1"}


def test_행이_없으면_None(fi):
    assert fi.parse_response(ok("")) is None


def test_오류_코드면_멈춘다(fi):
    text = json.dumps({"response": {"header": {"resultCode": "22",
                                               "resultMsg": "LIMITED_NUMBER_OF_SERVICE_REQUESTS"}}})
    with pytest.raises(fi.Stop):
        fi.parse_response(text)


def test_XML_오류도_멈춘다(fi):
    with pytest.raises(fi.Stop):
        fi.parse_response("<OpenAPI_ServiceResponse><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR")


def test_남은_것은_목록에_있고_받지_않은_음식점(fi):
    listing = [{"contentid": "1", "contenttypeid": "39"}, {"contentid": "2", "contenttypeid": "39"},
               {"contentid": "3", "contenttypeid": "12"}]
    assert [r["contentid"] for r in fi.pending(listing, [{"contentid": "1"}])] == ["2"]


def test_우리_칸은_밑줄로_붙는다(fi):
    at = datetime(2026, 9, 23, 12, 0, tzinfo=timezone(timedelta(hours=9)))
    row = fi.with_ours({"contentid": "2", "opentimefood": "11:00~21:00"},
                       {"title": "가게", "addr1": "서울특별시 성동구 1"}, at)
    assert row["opentimefood"] == "11:00~21:00"
    assert (row["_title"], row["_addr"], row["_region"]) == ("가게", "서울특별시 성동구 1", None)
    assert row["_fetched_at"] == "2026-09-23T12:00:00+09:00"


def test_서비스_키가_공통_키보다_먼저(fi):
    assert fi.service_key({"ACOP_TOUR_API_KEY": "a", "ACOP_DATA_GO_KR_KEY": "b"}) == "a"
    assert fi.service_key({"ACOP_DATA_GO_KR_KEY": "b"}) == "b"


def test_인코딩된_키는_풀어_두고_보낼_때_한_번만_싼다(fi):
    key = fi.service_key({"ACOP_TOUR_API_KEY": "ab%2Bcd%3D%3D"})
    assert key == "ab+cd=="
    assert "serviceKey=ab%2Bcd%3D%3D" in fi.request_url(key, "1")


def test_저장은_바꿔_끼운다(fi, tmp_path):
    path = str(tmp_path / "intro.json")
    fi.save([{"contentid": "1"}], path)
    assert fi.load(path) == [{"contentid": "1"}]
    assert not os.path.exists(path + ".tmp")
