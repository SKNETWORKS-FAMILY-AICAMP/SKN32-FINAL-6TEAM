# -*- coding: utf-8 -*-
"""채팅 해석 문맥 길이(`ollama_num_ctx`) — 16항목 여행이 들어가는 값을 **모든 같은-모델 호출**이 같이 보낸다. `[2026-10-26]`

실측(Ollama 0.31.1 Gemma4 native tokenizer, 합성 16항목): 지시문 6,771 + 일정 943 + 대화 4턴 289 → 프롬프트 약 8,110 토큰.
출력 상한(`travel.decision_unit.num_predict` 1200)까지 8,192 안에 들어가지 않는다(x600 실측 7,842 + 400 > 8,192 → 유료 넘김).
이 시험은 토큰 수를 재지 않는다(저장소에 tokenizer 가 없다). 재는 것은 ① 기본값 · 배포 env · 개발 안내가 같은 값인지,
② 해석 · 끼니 고르기 · 공지 판정이 같은 모델이면 같은 `num_ctx` 를 보내는지(다르면 Ollama 가 호출마다 모델을 다시 올린다),
③ 해석 요청이 일정 · 대화를 줄이지 않고 그대로 보내는지다. 실제 잘림 해소 · GPU 적합은 실모델 · x600 확인 몫이다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.settings import Settings

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = 12288
KST = timezone(timedelta(hours=9))


def test_the_default_context_fits_a_sixteen_stop_trip_and_matches_deploy_and_dev_template():
    assert Settings.model_fields["ollama_num_ctx"].default == CONTEXT
    deploy = (ROOT / "deploy" / "make_server_env.py").read_text(encoding="utf-8")
    assert re.findall(r'"ACOP_OLLAMA_NUM_CTX=(\d+)"', deploy) == [str(CONTEXT)]
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.findall(r"^#?ACOP_OLLAMA_NUM_CTX=(\d+)", example, flags=re.M) == [str(CONTEXT)]


def _items(n: int):
    start = datetime(2030, 1, 1, 9, 0, tzinfo=KST)
    titles = ["경복궁 관람", "광장시장 점심", "국립중앙박물관", "명동 저녁"]
    return [SimpleNamespace(item_id=uuid4(), kind="dining" if k % 4 in (1, 3) else "activity",
                            starts_at=start + timedelta(days=k // 4, hours=3 * (k % 4)), seq=k + 1,
                            title=f"{titles[k % 4]} {k + 1}", place={"name": f"장소 {k + 1}"}, detail={}) for k in range(n)]


def test_the_interpreter_request_carries_the_context_and_full_output_reserve_with_every_stop_and_turn():
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.components.conversation import decision_unit
    from app.infrastructure.ollama_chat import from_settings

    sent = []

    def transport(url, payload):
        sent.append(payload)
        return SimpleNamespace(status_code=503, text="stub", json=lambda: {})

    settings = SimpleNamespace(ollama_base_url="http://ollama.test:11434",
                               ollama_num_ctx=Settings.model_fields["ollama_num_ctx"].default)
    chat = from_settings(settings)
    chat._post = transport
    items = _items(16)
    history = [{"role": "customer" if i % 2 == 0 else "assistant", "text": f"대화 {i} " + "가" * 150, "reply": {}}
               for i in range(4)]
    num_predict = int(get_guardrails().get("travel.decision_unit.num_predict"))
    with pytest.raises(decision_unit.DecisionFailed):
        decision_unit.decide(chat, stops=decision_unit.stops_of(items), changes=[], history=history,
                             selected_item_id=None, message="저녁 일정을 다른 식당으로 바꿔줘", num_predict=num_predict)
    assert len(sent) == 1
    options = sent[0]["options"]
    assert options["num_ctx"] == CONTEXT and options["num_predict"] == num_predict == 1200
    user = sent[0]["messages"][1]["content"]
    assert all(item.title in user for item in items)                      # 일정은 줄이지 않는다
    assert all(turn["text"][:160] in user for turn in history)            # 대화도 기존 상한(160자) 그대로


def _settings(**over):
    base = dict(ollama_base_url="http://ollama.test:11434", ollama_model="tripilot-pointer:e4b-ft",
                ollama_num_ctx=CONTEXT, ollama_keep_alive="", ollama_notice_model="tripilot-pointer:e4b-ft",
                ollama_notice_timeout_seconds=90.0, openai_api_key="")
    base.update(over)
    return SimpleNamespace(**base)


def test_the_meal_picker_on_the_interpreter_model_sends_the_same_context(monkeypatch):
    from app import composition
    from app.core import settings as settings_module
    from app.domains.travel_ops.components.planning import meal_pick

    made = []
    monkeypatch.setattr(settings_module, "dining_meal_pick", lambda: {"model": "ollama:"})
    monkeypatch.setattr(settings_module, "get_settings", lambda: _settings())
    monkeypatch.setattr(meal_pick, "make_flow_picker", lambda chat, **_: made.append(chat) or "picker")
    assert composition._dining_meal_picker() == "picker"
    assert made[0].model == "tripilot-pointer:e4b-ft" and made[0].num_ctx == CONTEXT


def test_a_meal_picker_on_another_ollama_model_keeps_its_own_context(monkeypatch):
    from app import composition
    from app.core import settings as settings_module
    from app.domains.travel_ops.components.planning import meal_pick

    made = []
    monkeypatch.setattr(settings_module, "dining_meal_pick", lambda: {"model": "ollama:gemma4:12b"})
    monkeypatch.setattr(settings_module, "get_settings", lambda: _settings())
    monkeypatch.setattr(meal_pick, "make_flow_picker", lambda chat, **_: made.append(chat) or "picker")
    composition._dining_meal_picker()
    assert made[0].model == "gemma4:12b" and made[0].num_ctx == 0


@pytest.mark.parametrize("notice_model, expected", [("tripilot-pointer:e4b-ft", CONTEXT), ("gemma4:12b", None)])
def test_notice_judges_send_the_interpreter_context_only_on_the_same_model(monkeypatch, notice_model, expected):
    from app.domains.travel_ops.ports.data_sources import notice_end_model, notice_impact, notice_status

    plugged = {}
    monkeypatch.setattr(notice_status, "set_second_opinion", lambda judge: plugged.__setitem__("end", judge))
    monkeypatch.setattr(notice_impact, "set_second_opinion", lambda judge: plugged.__setitem__("impact", judge))
    notice_end_model.register_from_settings(_settings(ollama_notice_model=notice_model))
    sent = []

    def post(url, payload, timeout):
        sent.append(payload["options"].get("num_ctx"))
        return SimpleNamespace(status_code=200, text="", json=lambda: {"message": {"content": '{"state": "ongoing"}'}})

    for name in ("end", "impact"):
        plugged[name]._post = post
        plugged[name]._ask("호우 경보")
    assert sent == [expected, expected]
