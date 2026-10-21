# -*- coding: utf-8 -*-
"""채팅 「다른 데로 바꿔 줘」가 등록 때 남긴 「다른 안」을 건너뛰고 늘 새로 찾던 결함 — 재현과 고친 동작. `[2026-10-20]`

☆x600 실서버 확인(2026-10-20 15:36, role-manager fb840cd1, 게스트 여행 a2d3bcbb): 「북촌한옥마을 산책」 항목은 등록 때 대안
  빨래골 · 은평한옥마을 · 서울 관상감 관천대를 들고 있었다(`itinerary_items.detail.alternates`). 「북촌한옥마을 다른 데로 바꿔 줘」를
  해석이 「후보 알아봐 줘」(`propose_alternatives`)로 읽자(설문 「먼저 물어봐」 여행) 활동 팀 `_propose_alternatives` 가 저장분을 보지 않고
  `plan_fresh_alternate` 로 새로 찾아 북촌전망대 · 그랑핸드 가회점 · 세인트제임스 부티크 삼청 · 「14:30으로 늦추면」 북촌동양문화박물관을 보였다.

고친 것: 묻는 안을 저장분에서 먼저 낸다(`itinerary_changes.stored_alternates` — 지금 곳 · 이 여행에 장소 행이 없는 곳 · 시작이 지난 안은 뺀다).
  새로 찾는 것은 저장분이 없거나 낡았을 때만. 바로 바꾸는 길(`apply_change` → 팀 `_change`)은 전부터 저장분을 썼다.

모든 바깥 서비스는 메모리 대역이다(mock 서버 시험 — 실서버 확인은 따로 적는다).
"""
from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from app.core.contracts import NextAction
from app.domains.travel_ops.components.itinerary.itinerary import item_to_dict
from app.domains.travel_ops.components.itinerary.itinerary_changes import stored_alternates

from tests.unit.travel.test_conversation_work import run, task_for


def _place(name, lat):
    return {"place_id": str(uuid4()), "name": name, "kind": "dining", "latitude": lat, "longitude": 126.98,
            "attributes": {"hours": ["09:00", "23:00"], "payment": ["card", "cash"]}}


def _record(place, starts, ends):
    return {"key": place["place_id"], "name": place["name"], "place_id": place["place_id"],
            "starts_at": starts.isoformat(), "ends_at": ends.isoformat(), "walk_min": None}


def _request(*, stored_in_catalog=True):
    """식사 하나 + 등록 때 남긴 「다른 안」 둘 + 새로 찾으면 걸릴 가까운 곳 하나. 요청 시각은 하루 전."""
    work, task, items = task_for({"action": "propose_alternatives"})
    item = items[0]
    home = {**_place("원래 식당", 37.57), "place_id": str(item.place_id)}
    saved = [_place("저장 대안 1", 37.58), _place("저장 대안 2", 37.585)]
    fresh = _place("새로 찾은 곳", 37.5702)
    item.place = home
    item.detail = {"alternates": [_record(p, item.starts_at, item.ends_at) for p in saved], "alternates_from": "intake"}
    work.tools.view["items"] = [item_to_dict(item)]
    work.tools.catalog = [home, fresh, *(saved if stored_in_catalog else [])]
    state = task.context.current_state
    state["subject_ref"]["part_id"] = str(item.item_id)
    state["subject_ref"]["request"]["at"] = (item.starts_at - timedelta(days=1)).isoformat()
    return work, task, item, saved, fresh


def test_asking_offers_the_alternates_saved_at_registration_first():
    work, task, item, saved, fresh = _request()
    result = run(work, task)
    assert result.next_action == NextAction.WAIT_FOR_INPUT and not result.action_proposals
    names = [o["name"] for o in result.decisions[0]["options"]]
    assert names == [p["name"] for p in saved]                       # ☆고치기 전: 새로 찾은 곳이 1위
    assert fresh["name"] not in names
    assert "저장 대안 1" in result.answer


def test_choosing_a_saved_alternate_applies_that_place():
    work, task, item, saved, _ = _request()
    first = run(work, task)
    task.context.current_state.update(required_input_schema=first.required_input_schema,
                                      customer_input="2번", customer_input_history=["2번"])
    result = run(work, task)
    assert result.next_action == NextAction.RESPOND and len(result.action_proposals) == 1
    assert result.action_proposals[0].arguments["replacements"][0]["item"]["place_id"] == saved[1]["place_id"]


def test_stale_saved_alternates_fall_back_to_a_fresh_search():
    work, task, item, saved, fresh = _request(stored_in_catalog=False)   # 저장 대안의 장소 행이 이 여행에 없다(낡음)
    result = run(work, task)
    names = [o["name"] for o in result.decisions[0]["options"]]
    assert fresh["name"] in names and not set(names) & {p["name"] for p in saved}


def test_stored_alternates_drops_the_current_place_missing_rows_and_past_starts():
    _, _, items = task_for({"action": "propose_alternatives"})
    item = items[0]
    keep, gone, past = _place("남길 곳", 37.58), _place("행 없는 곳", 37.59), _place("지난 안", 37.6)
    here = {"key": str(item.place_id), "name": "지금 곳", "place_id": str(item.place_id),
            "starts_at": item.starts_at.isoformat(), "ends_at": None}
    item.detail = {"alternates": [here, _record(keep, item.starts_at, item.ends_at), _record(gone, item.starts_at, item.ends_at),
                                  _record(past, item.starts_at - timedelta(hours=3), item.starts_at - timedelta(hours=2))]}
    places = {p["place_id"]: p for p in (keep, past)} | {str(item.place_id): {"place_id": str(item.place_id)}}
    now = item.starts_at - timedelta(hours=1)
    assert [r["name"] for r in stored_alternates(item, places, now)] == ["남길 곳"]
    assert stored_alternates(item, places, item.starts_at) == []                    # 시작 시각이 지났으면 모두 낡음
