# -*- coding: utf-8 -*-
"""재난 뒤 다시 짤 때의 제약이 **일정 생성 입구**를 지난다 — `POST /v1/trips/plan` 의 `constraints`. `[결정 2026-10-07 사용자]`

후보를 심는 방식은 `test_trip_planner.py` 와 같다(그 파일의 `api` 픽스처 — 후보가 전부 종로구다).

★지키려는 것
 ①피해 구를 주면 그 구의 후보가 빠진다 — 후보가 모자라면 **거절하고 어떤 구를 얼마나 뺐는지** 알린다(조용히 줄이지 않는다)
 ②다른 구를 주면 아무것도 안 빠지고, 결과의 `planner.recovery` 가 「0곳 뺐다」를 적는다
 ③이 제약은 **초안(여행)에 박히지 않는다** — 그대로 등록하면 여행 제약에 남지 않는다
 ④구 이름이 아닌 값은 422(지어내지 않는다)

재현:

    python -m pytest tests/e2e/test_trip_planner_recovery.py -v
"""
from __future__ import annotations

from .test_trip_planner import _plan_without_the_dining_ledger, api  # noqa: F401 — 픽스처를 그대로 쓴다


def test_avoiding_the_only_district_refuses_with_what_was_excluded(api):
    response = api["ask"](constraints={"avoid_districts": ["종로구"]})
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "not_enough_candidates"
    assert error["recovery"]["avoid"]["avoid_districts"] == ["종로구"] and error["recovery"]["avoid"]["excluded"] > 0     # 어떤 구를 얼마나 뺐는지 남긴다


def test_another_district_changes_nothing_and_the_draft_does_not_keep_the_constraints(api):
    response = api["ask"](constraints={"avoid_districts": ["마포구"], "lighter_day": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "drafted" and body["checks"]["violations"] == []
    recovery = body["planner"]["recovery"]
    assert recovery["avoid"] == {"avoid_districts": ["마포구"], "excluded": 0, "kept_without_district": 0}
    assert recovery["lighter_day"]["requested"] is True and recovery["lighter_day"]["applied"] is False   # 밀도 목표가 없어 낮출 단계가 없다
    assert "avoid_districts" not in body["draft"]["constraints"] and "lighter_day" not in body["draft"]["constraints"]
    created = api["client"].post("/v1/trips", headers=api["auth"]("trip:write"),
                                 json={"request_id": "recovery-hand-1", "customer_id": str(api["customer"]), **body["draft"]})
    assert created.status_code == 201, created.text                                              # 그대로 등록해도 된다


def test_without_the_constraints_the_answer_has_no_recovery_note(api):
    body = api["ask"]().json()
    assert "recovery" not in body["planner"]


def test_a_value_that_is_not_a_list_of_names_is_refused(api):
    response = api["ask"](constraints={"avoid_districts": "종로구"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_avoid_districts", response.text
