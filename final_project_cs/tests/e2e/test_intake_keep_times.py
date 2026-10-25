# -*- coding: utf-8 -*-
"""계획 확인의 질문 칸에서 고른 장소는 검사하되 다른 일정의 시각을 옮기지 않는다(`keep_times`). `[2026-10-25 사용자 결정 — 이동 확인 C안대로]`

☆왜: 검사 포함 고르기가 10-10 부터의 재배치(`direct_schedule.fit`)를 함께 돌려, 고르는 순간 그날 뒤 일정을 말없이 밀거나 밀다가 원래부터 문을 닫은
시각인 일정(밤 창덕궁)에 걸려 고르기 전체를 409 로 거절했다(2026-10-24 로컬 — 바꾸기 전 코드에서도 같음). 2026-10-20 「이동 확인 C안」은 늦어지는 구간을
그 구간이 닿는 카드의 「도착」 줄에서 묻기로 정했다(택시 · 늦추기 · 직접 수정).

재현:

    python -m pytest tests/e2e/test_intake_keep_times.py -v
"""
from __future__ import annotations

from app.domains.travel_ops.components.intake import direct_schedule

from .test_intake_review import ROOMY, _client, _field, _key, _send, rv  # noqa: F401 — 같은 환경 · 모방을 그대로 쓴다
from .test_trip_api import api  # noqa: F401 — `rv` 가 쓰는 픽스처

#: 경복궁 대신 고르는 곳 — 서울 안, 앞 일정에서 먼 곳(잠실)이라 다음 일정까지의 이동이 늘어난다(우리가 고른 값)
FAR = {"name": "롯데월드타워", "latitude": 37.5126, "longitude": 127.1025, "source": "search"}
NEAR = {"name": "덕수궁", "latitude": 37.5658, "longitude": 126.9751, "source": "search"}


def _times(view):
    return {item["id"]: (item["starts_at"], item["ends_at"]) for item in view["review"]["items"]}


def test_a_pick_in_the_question_is_checked_but_keeps_the_other_stops_times(rv, monkeypatch):
    client, _, _ = _client()
    headers = _key(client)
    view = _send(client, headers, ROOMY)
    first = view["review"]["items"][0]
    fitted = []
    real = direct_schedule.fit
    monkeypatch.setattr(direct_schedule, "fit", lambda *a, **k: fitted.append(1) or real(*a, **k))
    kept = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers,
                       json={"revision": view["revision"], "edits": [_field(first, "place", FAR)], "keep_times": True})
    assert kept.status_code == 200, kept.text
    after = kept.json()
    assert fitted == []                                                                           # 재배치를 부르지 않았다
    assert after["revision"] == view["revision"] + 1
    assert after["review"]["items"][0]["place"]["name"] == FAR["name"]
    others = {k: v for k, v in _times(after).items() if k != first["id"]}
    assert others == {k: v for k, v in _times(view).items() if k != first["id"]}                 # 다른 일정 시각은 그대로
    assert after["review"].get("checked") is not False                                            # 저장만이 아니다 — 그 판을 검사했다

    moved = client.post(f"/v1/web/trip-intakes/{view['intake_id']}/edits", headers=headers,
                        json={"revision": after["revision"], "edits": [_field(first, "place", NEAR)]})
    assert moved.status_code == 200, moved.text
    assert fitted == [1]                                                                          # 칸이 없으면 지금처럼 재배치한다


def test_keep_times_is_part_of_the_edit_request():
    from app.domains.travel_ops.entry.trip_api import IntakeEditIn

    body = IntakeEditIn.model_validate({"revision": 1, "edits": [{"source_id": "00000000-0000-0000-0000-000000000001",
                                                                   "field": "items[0].title", "value": "x"}], "keep_times": True})
    assert body.keep_times is True and body.check is True
    assert IntakeEditIn.model_validate({"revision": 1, "edits": [{"source_id": "00000000-0000-0000-0000-000000000001",
                                                                   "field": "items[0].title", "value": "x"}]}).keep_times is False
