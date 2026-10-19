# -*- coding: utf-8 -*-
"""요식 판정 도구 — 형식이 틀린 가게 번호는 **거절로 돌려준다**(DB 오류로 판정 전체를 멈추지 않는다). `[2026-10-16 luna 실측]`

☆실제 접수(장면 1)를 gpt-6-luna 로 3번 돌려 2번, 모델이 가게 번호의 한 칸을 빼고(`e21d00b5-11c8-5c4f-0697254991bd`) 넘겨
  `check_business` · `check_closed_day` 의 SQL 이 uuid 오류를 냈고 그날 판정이 통째로 사라졌다.
"""
from __future__ import annotations

from contextlib import nullcontext

from app.domains.travel_ops.instances.dining.agent_tools import DiningTools

BROKEN = "e21d00b5-11c8-5c4f-0697254991bd"


class NoDb(DiningTools):
    def _check_business(self, place_uid):
        raise AssertionError("형식이 틀린 번호로 DB 를 부르지 않는다")


def test_a_malformed_place_uid_is_refused_before_the_database():
    tools = NoDb(lambda: nullcontext(None))
    got = tools.call("check_business", {"place_uid": BROKEN})
    assert "refused" in got and "place_uid" in got["refused"]
    assert tools.calls == [] and tools.refused[0]["tool"] == "check_business"


def test_a_well_formed_place_uid_still_reaches_the_tool():
    class Ok(DiningTools):
        def _check_business(self, place_uid):
            return {"verdict": "ok", "reason": "영업 중"}

    tools = Ok(lambda: nullcontext(None))
    got = tools.call("check_business", {"place_uid": "e21d00b5-11c8-5c4f-9a1b-0697254991bd"})
    assert got["verdict"] == "ok" and got["call_id"] == "c1"
