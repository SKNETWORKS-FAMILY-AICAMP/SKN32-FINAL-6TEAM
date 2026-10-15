# -*- coding: utf-8 -*-
"""공지 「끝났나」 2차 확인 — 규칙과 모델이 둘 다 끝남일 때만 끝남, 모델 실패는 규칙 결과 `[2026-10-13]`."""
import json

import pytest

from app.domains.travel_ops.ports.data_sources import notice_end_model, notice_status as ns
from app.domains.travel_ops.ports.data_sources.notice_end_model import NoticeEndModel, evidence_in_text

ENDED_TEXT = "[서울시] 지하철 파업 철회, 정상 운행합니다"
NOT_ENDED_TEXT = "[강남구] 봉은사로 사고 발생, 우회 바랍니다"


class _Resp:
    def __init__(self, content, status=200):
        self.status_code, self._content = status, content
        self.text = str(content)

    def json(self):
        return {"message": {"content": self._content}}


def _model(answer=None, *, mode="on", fail=False):
    calls = []

    def post(url, payload, timeout):
        calls.append(payload)
        if fail:
            raise TimeoutError("모델 서버 시간 초과")
        return _Resp(json.dumps(answer, ensure_ascii=False))

    return NoticeEndModel(base_url="http://model", model="m", mode=mode, post=post), calls


@pytest.fixture(autouse=True)
def _reset():
    yield
    ns.set_second_opinion(None)


def test_model_veto_turns_rule_end_into_disputed():
    judge, calls = _model({"state": "no_end_signal", "ended": False, "evidence": ""})
    ns.set_second_opinion(judge)
    status = ns.notice_status(ENDED_TEXT)
    assert status.state == ns.DISPUTED and not status.ended and status.basis
    assert len(calls) == 1 and calls[0]["think"] is False and calls[0]["options"]["temperature"] == 0


def test_both_ended_stays_ended_and_same_text_is_asked_once():
    judge, calls = _model({"state": "ended", "ended": True, "evidence": "파업 철회"})
    ns.set_second_opinion(judge)
    assert ns.notice_status(ENDED_TEXT).ended
    assert ns.notice_status(ENDED_TEXT).ended
    assert len(calls) == 1


def test_model_is_not_asked_when_rule_does_not_say_ended():
    judge, calls = _model({"state": "ended", "ended": True, "evidence": "사고 발생"})
    ns.set_second_opinion(judge)
    assert not ns.notice_status(NOT_ENDED_TEXT).ended          # 모델은 끝남을 새로 만들지 않는다
    assert calls == []


def test_model_failure_falls_back_to_rule_and_is_counted():
    before = notice_end_model.STATS["failed"]
    judge, _ = _model(fail=True)
    ns.set_second_opinion(judge)
    assert ns.notice_status(ENDED_TEXT).ended
    assert notice_end_model.STATS["failed"] == before + 1


def test_shadow_mode_records_but_keeps_rule_result():
    judge, calls = _model({"state": "unsettled", "ended": False, "evidence": ""}, mode="shadow")
    ns.set_second_opinion(judge)
    assert ns.notice_status(ENDED_TEXT).ended and len(calls) == 1


def test_off_mode_does_not_call_model():
    judge, calls = _model({"state": "no_end_signal", "ended": False, "evidence": ""}, mode="off")
    ns.set_second_opinion(judge)
    assert ns.notice_status(ENDED_TEXT).ended and calls == []


def test_ended_without_quotable_evidence_is_not_ended():
    judge, _ = _model({"state": "ended", "ended": True, "evidence": "파업이 끝났다"})   # 본문에 없는 말
    ns.set_second_opinion(judge)
    assert ns.notice_status(ENDED_TEXT).state == ns.DISPUTED


def test_evidence_joined_with_ellipsis_is_checked_piece_by_piece():
    text = "서울 시내버스 파업이 종료되어 관내 시내버스가 정상 운행됩니다."
    assert evidence_in_text("파업이 종료되어... 정상 운행됩니다", text)
    assert evidence_in_text("파업이 종료되어…정상 운행됩니다", text)
    assert not evidence_in_text("파업이 종료되어... 운행 재개", text)
    assert not evidence_in_text("", text)


def test_register_without_model_name_keeps_rules_only():
    class S:
        ollama_notice_model = ""
        ollama_base_url = "http://model"

    assert notice_end_model.register_from_settings(S()) is None
    assert ns._second_opinion is None
