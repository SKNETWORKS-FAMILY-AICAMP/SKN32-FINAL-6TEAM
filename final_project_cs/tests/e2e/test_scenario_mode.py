# -*- coding: utf-8 -*-
"""시나리오 모드 — 확정 시나리오 하루가 **실제 시스템으로** 끝까지 도는가.

★LLM 만 흉내 낸다(분류기·추출기). 감시 루프·여행 창구·Case·일정 버전·통지는 실제 코드다.
  실제 Gemma 4 로 도는 것은 라이브 확인에서 본다.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.core.settings as settings_module
from app.infrastructure.db.session import get_connection
from app.modules.travel_ops.scenario_mode import SCENES, build_scenario_router
from app.presentation import security
from app.presentation.api.app import create_app


def _classifier(message):
    code = "dining_hours" if ("늦" in message or "휴무" in message) else "activity_other"
    return {"intent": "incident_report", "issue_code": code, "sentiment": "negative"}


class _Chat:
    def json(self, system, message):
        if "바꿔" in message:
            return {"type": "change"}
        if "늦" in message:
            return {"type": "delay", "minutes": 70, "products": []}
        if "휴무" in message:
            return {"type": "closed", "minutes": None, "products": []}
        if "품절" in message:
            return {"type": "stock_out", "products": ["라면 선물세트", "스팸 선물세트"]}
        return {"type": "other"}


def _client(monkeypatch, enabled=True):
    original = settings_module.get_settings()
    settings = original.model_copy(update={"scenario_mode_enabled": enabled})
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    return TestClient(create_app(
        classifier=lambda m: {"intent": "other", "issue_code": "other", "sentiment": "neutral"},
        domain_routers=[build_scenario_router(classifier_factory=lambda: _classifier,
                                              chat_factory=_Chat)]))


@pytest.fixture()
def client(monkeypatch):
    client = _client(monkeypatch)
    yield client
    client.post("/scenario/stop")


def _texts(feed, **match):
    return [m["text"] for m in feed["chat"] if all(m.get(k) == v for k, v in match.items())]


def test_the_whole_day_runs_through_the_real_system(client):
    feed = client.post("/scenario/start").json()
    assert feed["scene"] == 0 and feed["version"] == 1
    assert any("좋은 아침" in t for t in _texts(feed, kind="day_start"))
    assert client.get("/tripilot").status_code == 200

    def step():
        return client.post("/scenario/next").json()

    feed = step()                                              # 09:00 액-02
    assert feed["version"] == 2 and any(i["place"] == "아쿠아리움" for i in feed["items"])
    assert any("아쿠아리움" in t for t in _texts(feed, notice=True))
    feed = step()                                              # 10:45 이동-B1
    assert feed["version"] == 3
    feed = step()                                              # 11:15
    assert feed["version"] == 3
    feed = step()                                              # 13:00 요식-P3 — 고객 차례
    assert feed["awaiting_customer"] and "70분" in feed["suggestion"]
    feed = client.post("/scenario/message", json={"message": feed["suggestion"]}).json()
    assert feed["version"] == 4 and not feed["awaiting_customer"]
    last = feed["chat"][-1]
    assert last["case_status"] == "resolved" and last["version"] == 4
    feed = step()                                              # 15:00 출발 안내
    assert _texts(feed, kind="departure")
    step()                                                     # 15:30
    feed = step()                                              # 17:10 이동-A6
    assert feed["version"] == 5
    step()                                                     # 18:00 요식-P7
    feed = client.post("/scenario/message", json={"message": "저녁 식당이 오늘 임시휴무래요"}).json()
    assert feed["version"] == 6
    step()                                                     # 19:40 액-08
    feed = client.post("/scenario/message",
                       json={"message": "라면 선물세트랑 스팸 선물세트가 품절이에요"}).json()
    assert "[미확인]" in feed["chat"][-1]["text"] and feed["version"] == 6
    feed = step()                                              # 20:30 하루 정리
    assert feed["scene"] == len(SCENES) - 1 and _texts(feed, kind="summary")

    # 재요청 ① — 화면에서 다른 안 누르기
    lunch = next(i for i in feed["items"] if i["seq"] == 5)
    feed = client.post("/scenario/alternate", json={"item_id": lunch["item_id"],
                                                    "choice": lunch["other_options"][0]["key"]}).json()
    assert feed["version"] == 7
    # 재요청 ② — 채팅으로 「다른 안으로 바꿔줘」 → 방금 바꾼 점심을 다시 바꾼다
    feed = client.post("/scenario/message", json={"message": "다른 안으로 바꿔줘"}).json()
    assert feed["version"] == 8 and feed["chat"][-1]["case_status"] == "resolved"


def test_stopping_removes_the_scenario_tenant(client):
    tenant = client.post("/scenario/start").json()["tenant"]
    assert client.post("/scenario/stop").json() == {"active": False}
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tenants WHERE tenant_id=%s", (tenant,))
        assert cur.fetchone()[0] == 0
    assert client.get("/scenario/feed").json() == {"active": False}


def test_ops_console_reads_the_scenario_tenant(client):
    """★운영콘솔 Case 목록은 설정 테넌트만 본다 — 시나리오 판은 스위치 화면이 따로 읽는다."""
    feed = client.post("/scenario/start").json()
    for _ in range(4):                                         # 09:00 … 13:00 고객 차례
        feed = client.post("/scenario/next").json()
    client.post("/scenario/message", json={"message": feed["suggestion"]})
    ops = client.get("/scenario/ops").json()
    assert ops["tenant"] == feed["tenant"] and ops["version"] == 4
    assert [h["version"] for h in ops["history"]] == [1, 2, 3, 4]
    (case,) = ops["cases"]
    assert case["status"] == "resolved" and case["subject"] == feed["suggestion"]
    assert case["events"][0] == "created" and case["events"][-1] == "completed"
    assert "routed" in case["events"]
    assert "opsPanel" in client.get("/ui/scenario").text


@pytest.mark.parametrize("host,target", [("tripilot.localhost:8042", "/tripilot"),
                                         ("scenario.localhost:8042", "/ui/scenario"),
                                         ("localhost:8042", "/ui/cases")])
def test_preview_host_names_land_on_their_screens(client, host, target):
    """★앱 미리보기 목록은 localhost 주소에 경로를 못 붙인다 — 이름으로 나눠 같은 서버에 붙인다."""
    response = client.get("/", headers={"host": host}, follow_redirects=False)
    assert response.status_code == 307 and response.headers["location"] == target


def test_everything_is_hidden_when_the_setting_is_off(monkeypatch):
    client = _client(monkeypatch, enabled=False)
    assert client.get("/tripilot").status_code == 404
    assert client.get("/scenario/status").status_code == 404
    assert client.post("/scenario/start").status_code == 404
