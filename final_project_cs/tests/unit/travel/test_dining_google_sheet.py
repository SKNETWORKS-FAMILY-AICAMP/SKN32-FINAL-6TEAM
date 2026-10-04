"""google_sheet 의 판정. 사람이 고른 구글 가게와 cid 가 같을 때만 붙이는가, 폐업을 덮어쓰지 않는가.

망에도 DB 에도 닿지 않는다. 구글 응답은 손으로 만든 후보 목록이다.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.join(HERE, "..", "..", "..", "scripts", "dining", "google_sheet.py")
LINK = "구글 지도 링크(찾으면 붙여 넣기)"


@pytest.fixture(scope="module")
def gs():
    spec = importlib.util.spec_from_file_location("dining_google_sheet", os.path.abspath(MODULE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dining_google_sheet"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_cid_from_place_url(gs):
    url = ("https://www.google.com/maps/place/%EC%B2%AD%EB%8B%B4+%EA%B3%A0%EC%84%BC/data=!3m1!4b1!4m4"
           "!3m3!1s0x357ca47822057c51:0xd02a207d2a448e7a!16s%2Fg%2F1tpb8y62")
    assert gs.cid_from_url(url) == (str(int("d02a207d2a448e7a", 16)), "청담 고센")


def test_cid_from_cid_url(gs):
    assert gs.cid_from_url("https://maps.google.com/?cid=123&g_mp=x")[0] == "123"


def test_search_url_has_no_cid(gs):
    # 플러스 코드 검색 링크는 가게가 아니다 — 고르지 않는다
    assert gs.cid_from_url("https://www.google.com/maps/search/HR78%2B5M4")[0] is None


def test_short_address(gs):
    assert gs.short_address("서울특별시 강동구 성안로3길 27 주문진빌딩") == "강동구 성안로3길 27"
    assert gs.short_address("서울특별시 강북구 도봉로68길 36 (미아동)") == "강북구 도봉로68길 36"


def test_pick_only_same_cid(gs):
    cands = [{"id": "A", "googleMapsUri": "https://maps.google.com/?cid=1"},
             {"id": "B", "googleMapsUri": "https://maps.google.com/?cid=2"}]
    assert gs.pick(cands, "2") == "B"
    assert gs.pick(cands, "3") is None


def test_plan_splits_rows(gs):
    rows = [
        {"place_uid": "a", "상호": "가", LINK: "https://maps.app.goo.gl/x", "메모": ""},
        {"place_uid": "b", "상호": "나", LINK: "", "메모": "폐업"},
        {"place_uid": "c", "상호": "다", LINK: "https://maps.app.goo.gl/y", "메모": "같은 가게인지 확인"},
        {"place_uid": "d", "상호": "라", LINK: "https://maps.app.goo.gl/z", "메모": ""},
        {"place_uid": "e", "상호": "마", LINK: "", "메모": ""},
    ]
    todo = gs.plan(rows, [{"place_uid": "d"}])
    assert [r["place_uid"] for r in todo["link"]] == ["a"]
    assert [r["place_uid"] for r in todo["closed"]] == ["b"]
    assert [r["place_uid"] for r, _ in todo["review"]] == ["c"]
    assert [r["place_uid"] for r in todo["done"]] == ["d"]
    assert [r["place_uid"] for r in todo["empty"]] == ["e"]


def test_mark_closed_keeps_existing_verdict(gs):
    rows = [{"place_uid": "a", "[확인] 영업 여부": "", "확인일": "", "메모": ""},
            {"place_uid": "b", "[확인] 영업 여부": "영업", "확인일": "2026-09-28", "메모": ""}]
    done = gs.mark_closed(rows, {"a", "b"}, "2026-09-30")
    assert done == ["a"]
    assert rows[0]["[확인] 영업 여부"] == "폐업" and rows[0]["확인일"] == "2026-09-30"
    assert rows[1]["[확인] 영업 여부"] == "영업"


def test_plan_skips_rows_decided_in_closure_sheet(gs):
    rows = [{"place_uid": "a", "상호": "가", LINK: "https://maps.app.goo.gl/x", "메모": ""}]
    todo = gs.plan(rows, [], frozenset({"a"}))
    assert not todo["link"] and [r["place_uid"] for r in todo["done"]] == ["a"]
