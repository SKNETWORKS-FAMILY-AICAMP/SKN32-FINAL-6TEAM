# -*- coding: utf-8 -*-
"""「기타」 · 모르는 구분 재난 문자 — 여행 영향이 있으면 영향 종류를 붙여 보내고, 없으면 보내지 않는다 `[2026-10-13 사용자 결정]`."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.ports.data_sources import notice_impact
from app.domains.travel_ops.ports.data_sources.disaster_msg import judge
from app.domains.travel_ops.ports.data_sources.notice_end_model import NoticeImpactModel

KST = ZoneInfo("Asia/Seoul")
AT = datetime(2026, 10, 13, 9, 0, tzinfo=KST)


@pytest.fixture(autouse=True)
def _reset():
    yield
    notice_impact.set_second_opinion(None)


def _row(text, kind="기타"):
    return {"created_at": AT, "kind": kind, "step": "안전안내", "regions": ["서울특별시 종로구 청운효자동"], "text": text, "serial": 1}


def _judge(*rows):
    return judge(list(rows), region="서울", district="종로구", window_start=AT, at=AT)


def test_gita_with_travel_impact_is_sent_with_its_kind():
    messages, unclassified = _judge(_row("서울 시내버스 파업으로 오늘 첫차부터 시내버스 운행 중단, 지하철을 이용 바랍니다."))
    assert len(messages) == 1 and messages[0]["kind"] == "기타" and messages[0]["impact"] == "bus"
    assert messages[0]["impact_by"] == "rule" and messages[0]["weather"] is False and unclassified == []


def test_outdoor_impact_goes_only_to_weather_sensitive_places():
    messages, _ = _judge(_row("폭염 지속중 ▲한낮 야외활동 자제 ▲충분한 수분 섭취 바랍니다"))
    assert messages[0]["impact"] == "outdoor" and messages[0]["weather"] is True


def test_gita_without_travel_impact_is_not_sent_anywhere():
    messages, unclassified = _judge(_row("물놀이 시 ▲구명조끼 착용 ▲준비운동 등 안전수칙을 준수 바랍니다."))
    assert messages == [] and unclassified == []


def test_unknown_kind_without_impact_stays_visible_as_unclassified():
    messages, unclassified = _judge(_row("설 연휴 문 여는 병의원은 응급의료포털에서 확인하세요", kind="새이름"))
    assert messages == [] and len(unclassified) == 1


def test_unknown_kind_with_impact_is_sent():
    # `[2026-10-13]` 「교통사고」는 공식 목록 41종에 들어 이름만으로 보낸다 — 본문 판정은 목록에 없는 새 이름에서 본다
    messages, _ = _judge(_row("금일 신목동역 앞 안양천로 교통사고로 차량 정체중입니다. 인근 차량은 우회 바랍니다.", kind="새이름"))
    assert messages and messages[0]["impact"] == "road"


class _Resp:
    def __init__(self, content):
        self.status_code, self.text = 200, content

    def json(self):
        return {"message": {"content": self.text}}


def _model(answer, *, mode="on", fail=False):
    calls = []

    def post(url, payload, timeout):
        calls.append(payload)
        if fail:
            raise TimeoutError("시간 초과")
        return _Resp(json.dumps(answer, ensure_ascii=False))

    return NoticeImpactModel(base_url="http://m", model="m", mode=mode, post=post), calls


RULE_MISSES = "오늘 저녁 관내 일대에 사람이 크게 몰릴 것으로 보입니다. 홈페이지를 참고하시기 바랍니다."


def test_model_can_add_impact_when_rule_says_none():
    judge_model, calls = _model({"impact": "crowd", "relevant": True, "evidence": "사람이 크게 몰릴"})
    notice_impact.set_second_opinion(judge_model)
    assert notice_impact.rule_impact(RULE_MISSES) is None
    assert notice_impact.impact_detail(RULE_MISSES) == {"impact": "crowd", "by": "model"}
    messages, _ = _judge(_row(RULE_MISSES))
    assert messages and messages[0]["impact"] == "crowd" and messages[0]["impact_by"] == "model"
    assert len(calls) == 1                                   # 같은 본문은 한 번만 묻는다


def test_model_is_not_asked_when_rule_already_found_impact():
    judge_model, calls = _model({"impact": "none", "relevant": False, "evidence": ""})
    notice_impact.set_second_opinion(judge_model)
    assert notice_impact.travel_impact("○○동 일대 정전 발생, 복구 중입니다") == "utility"
    assert calls == []


def test_model_answer_without_quotable_evidence_is_ignored():
    judge_model, _ = _model({"impact": "hazard", "relevant": True, "evidence": "본문에 없는 말"})
    notice_impact.set_second_opinion(judge_model)
    assert notice_impact.travel_impact("홈페이지를 참고하시기 바랍니다") is None


def test_model_failure_and_shadow_mode_keep_rule_result():
    judge_model, _ = _model({}, fail=True)
    notice_impact.set_second_opinion(judge_model)
    assert notice_impact.travel_impact("홈페이지를 참고하시기 바랍니다") is None
    judge_model, calls = _model({"impact": "road", "relevant": True, "evidence": "홈페이지"}, mode="shadow")
    notice_impact.set_second_opinion(judge_model)
    assert notice_impact.travel_impact("홈페이지를 참고하시기 바랍니다") is None and len(calls) == 1


def test_excluded_gita_is_handed_to_the_record_sink_not_to_agents():
    from app.domains.travel_ops.ports.data_sources import disaster_msg

    seen = []
    disaster_msg.set_excluded_sink(seen.append)
    try:
        judge_model, _ = _model({"impact": "none", "relevant": False, "evidence": ""})
        notice_impact.set_second_opinion(judge_model)
        messages, unclassified = _judge(_row("관내 문화행사 안내는 홈페이지를 참고하시기 바랍니다"))
        assert messages == [] and unclassified == []
        assert len(seen) == 1 and seen[0]["kind"] == "기타" and seen[0]["model_checked"] is True
        assert seen[0]["prompt_version"] == "notice_impact.v1-2026-10-13"
        seen.clear()
        _judge(_row("서울 시내버스 파업으로 시내버스 운행 중단"))       # 영향 있음은 기록 대상이 아니다
        assert seen == []
    finally:
        disaster_msg.set_excluded_sink(None)
