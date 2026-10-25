# -*- coding: utf-8 -*-
"""도착 질문의 「뒤 일정까지 함께 미루기」 — `POST …/autofix {item_id, push: true}`. `[2026-10-25 사용자 결정 — D1~D7]`

☆왜: 오는 길이 늦은 일정을 그 일정 하나만 늦추면 뒤 일정까지 30분도 못 머무는 계획(2026-10-25 로컬 — 광장시장 13:10 → 국립중앙박물관 13:15 → 인사동 15:00)은
서버가 「늦추기」를 내지 않아(`kept: no_fitting_time`) 질문 칸에 직접 수정만 남았다. 그 일정을 앞에서 닿는 시각으로 옮기고(머무는 시간 그대로) 그날 뒤 일정을
늦춘 판을 미리 보여 주고, 고르면 그 값을 그대로 저장한다(계약 `wiki/external/rest-endpoints/web-intakes.md` 「`push: true`」).

★지키려는 것: ①그 일정 하나로 맞으면 `push` 없이와 같다(D1) ②미리 보기는 아무것도 저장하지 않는다 ③응답의 `edits` 를 그대로 저장하면 미리 보기와 같은 시각
④못 늦추면 바꾸지 않고 서버 문장으로 말한다(`push_refused`) ⑤`push` 는 `item_id` 와 함께만.

재현:

    python -m pytest tests/e2e/test_intake_push_later.py -v
"""
from __future__ import annotations

from app.domains.travel_ops.components.intake import direct_schedule

from .test_intake_autofix_dry_run import _counts
from .test_intake_review import _client, _item, _key, _send, rv  # noqa: F401 — 같은 환경 · 모방을 그대로 쓴다
from .test_trip_api import api  # noqa: F401 — `rv` 가 쓰는 픽스처

#: N서울타워는 경복궁에서 늦게 닿고, 그 하나만 늦추면 광장시장까지 30분을 못 머문다 — 뒤 일정까지 미뤄야 맞는 모양(우리가 고른 시각)
TIGHT = ("2026-10-15\n"
         "10:00~11:30 경복궁 관람\n"
         "11:35~12:05 N서울타워\n"
         "12:20~13:20 광장시장 빈대떡")
#: 같은 N서울타워인데 뒤가 넉넉하다 — 그 일정 하나만 늦추면 맞는 모양(「늦추기」)
ROOMY_AFTER = ("2026-10-15\n"
               "10:00~11:30 경복궁 관람\n"
               "11:35~12:05 N서울타워\n"
               "16:00~17:00 광장시장 빈대떡")


def _autofix(client, headers, view, **extra):
    return client.post(f"/v1/web/trip-intakes/{view['intake_id']}/autofix", headers=headers,
                       json={"revision": view["revision"], **extra})


def _times(view):
    return {i["id"]: (i["starts_at"], i["ends_at"]) for i in view["review"]["items"]}


def test_a_push_moves_the_stop_and_the_stops_after_it_and_saves_nothing(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, TIGHT)
    tower = _item(view, "N서울타워")
    alone = _autofix(client, headers, view, item_id=tower["id"], dry_run=True).json()
    assert alone["changed"] == [] and [k["reason"] for k in alone["kept"] if k["id"] == tower["id"]] == ["no_fitting_time"]
    before = _counts(view["intake_id"])
    got = _autofix(client, headers, view, item_id=tower["id"], dry_run=True, push=True)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["applied"] is False and body["dry_run"] is True and body["revision"] == view["revision"]
    first, *pushed = body["changed"]
    assert first["id"] == tower["id"] and first["reason"] == "time" and "pushed" not in first
    assert first["to"]["starts_at"] > first["from"]["starts_at"]
    length = lambda t: int(t["ends_at"][:2]) * 60 + int(t["ends_at"][3:]) - int(t["starts_at"][:2]) * 60 - int(t["starts_at"][3:])  # noqa: E731
    assert length(first["to"]) == length(first["from"])                                       # D2 머무는 시간 그대로
    assert [c["title"] for c in pushed] == ["광장시장 빈대떡"] and all(c["pushed"] is True for c in pushed)
    assert pushed[0]["to"]["starts_at"] > pushed[0]["from"]["starts_at"]
    assert body["view"]["preview"] is True and _times(body["view"])[tower["id"]] == (first["to"]["starts_at"], first["to"]["ends_at"])
    assert {e["field"] for e in body["edits"]} >= {f"items[{tower['index']}].starts_at", f"items[{tower['index']}].ends_at"}
    assert not [k for k in body["kept"] if k["id"] == tower["id"]]
    assert _counts(view["intake_id"]) == before                                                # 아무것도 안 남았다


def test_saving_the_edits_of_a_push_gives_the_times_it_showed(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, TIGHT)
    tower = _item(view, "N서울타워")
    body = _autofix(client, headers, view, item_id=tower["id"], dry_run=True, push=True).json()
    saved = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers,
                        json={"revision": view["revision"], "edits": body["edits"], "keep_times": True})
    assert saved.status_code == 200, saved.text
    after = saved.json()
    assert after["revision"] == view["revision"] + 1
    assert _times(after) == _times(body["view"])                                               # 미리 보기와 같은 시각


def test_a_stop_that_fits_alone_is_moved_alone_with_or_without_push(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY_AFTER)
    tower = _item(view, "N서울타워")
    alone = _autofix(client, headers, view, item_id=tower["id"], dry_run=True).json()
    pushed = _autofix(client, headers, view, item_id=tower["id"], dry_run=True, push=True).json()
    assert [c["id"] for c in alone["changed"]] == [tower["id"]]
    assert pushed["changed"] == alone["changed"] and pushed["kept"] == alone["kept"]           # D1 — push 는 아무 일도 하지 않는다
    assert "edits" not in pushed


def test_a_push_that_cannot_be_made_says_why_and_changes_nothing(rv, monkeypatch):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, TIGHT)
    tower = _item(view, "N서울타워")

    def refuse(*_a, **_k):
        raise direct_schedule.ScheduleConflict("이동에 맞춰 시각을 옮기면 운영시간에 맞지 않아요. 다른 시각이나 장소를 골라 주세요.")
    monkeypatch.setattr(direct_schedule, "fit", refuse)
    before = _counts(view["intake_id"])
    body = _autofix(client, headers, view, item_id=tower["id"], dry_run=True, push=True).json()
    assert body["changed"] == [] and "edits" not in body
    [refused] = [k for k in body["kept"] if k["id"] == tower["id"]]
    assert refused["reason"] == "push_refused" and refused["message"].startswith("이동에 맞춰 시각을 옮기면")
    assert refused["starts_at"] > tower["starts_at"] and refused["ends_at"]
    assert _counts(view["intake_id"]) == before


def test_push_is_sent_only_with_an_item(rv):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, TIGHT)
    assert _autofix(client, headers, view, push=True, dry_run=True).status_code == 422
