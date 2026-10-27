# -*- coding: utf-8 -*-
"""훈련 · 가상 상황 문자 판정 — 세 곳(재난문자 판정 · 재난 정지 · 활동 성립)이 **같은 공용 판정**을 쓰는지.

`[2026-10-27 C 전수검사 · 알려진 이슈 (a)]` 전에는 제외 낱말(「훈련」 · 「실제 상황이 아」)이 글자 그대로 한 번만 있어도 버렸다.
 ① 「훈련」 없이 가상 상황을 알리는 문자 → 지진 · 긴급재난으로 판정(놓침 반대 — 쓸데없는 정지)
 ② 「훈련 중 실제 화재」 · 「훈련이 아닌 실제 상황」 → 통째 제외(실제 사건을 놓침 — 더 위험)
 ③ 「훈련장 화재」 → 훈련 문자로 제외
낱말은 모두 `config/guardrails.yaml` `travel.safety.*` 에서 읽는다(시험도 실제 설정을 쓴다).

재현:

    python -m pytest tests/unit/travel/test_notice_drill.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domains.travel_ops.components.planning.safety import SafetyRules, classify
from app.domains.travel_ops.instances.activity.disaster_impact import IGNORED, ImpactRules
from app.domains.travel_ops.ports.data_sources.disaster_msg import judge

KST = ZoneInfo("Asia/Seoul")
AT = datetime(2026, 9, 23, 10, 30, tzinfo=KST)

#: 훈련 · 가상 상황 문자 — 세 곳 모두 거른다
DRILLS = [
    "오늘 14시 민방위 훈련 공습경보 발령 — 실제 상황이 아닙니다.",
    "[행정안전부] 지진 대피 가상 상황입니다. 침착하게 행동 요령을 확인하세요",
    "이 문자는 재난문자 시험 발송입니다. 강남구 일대 지진 발생 가정",
    "실제상황이 아닙니다. 지진 발생 시 행동요령 안내",            # 띄어쓰기가 다른 표지
    "가상의 상황을 가정한 지진 대응 모의 상황 안내입니다",
    # ★실제 사건 표지가 **조건 · 가정**으로만 나오면(「실제 화재 시에는」 · 「실제 상황 발생 시」) 실제 사건이 아니다 — 훈련 안내의 흔한 말투
    "소방 훈련 중입니다. 실제 화재 시에는 119에 신고하세요",
    "민방위 훈련입니다. 실제 상황 발생 시 가까운 대피소로 이동하세요",
    "지진 대피 훈련 — 실제로 발생할 경우 탁자 밑으로 몸을 피하세요",
    # `[2026-10-27 실측 — 전국 재난문자 2023~2026]` 공공 문자 말투를 본뜬 것: 부정 · 문자 이야기도 실제 사건 단언이 아니다
    "오늘 15:00~16:00 ○○영업소에서 화재 대응 합동 훈련 실시 중입니다. 연기 발생 시 실제 화재가 아니오니 안심하시기 바랍니다",
    "(정정) 오늘 10:57 발송된 산사태 발생 문자는 훈련 상황 중 실제 재난문자로 오발송되었음을 알려드립니다",
    # `[Codex 검토 2026-10-27]` 「발생 시」 · 「하는 경우」 꼬리
    "화재 대피 훈련입니다. 실제 화재 발생 시 계단으로 대피하세요",
    "지진 훈련 안내 — 실제로 발생하는 경우 머리를 보호하세요",
]
#: 실제 사건 문자 — 「훈련」이 들어 있어도 거르지 않는다
ACTUALS = [
    "민방위 훈련 중 강남구 역삼동 건물에 실제 화재가 발생했습니다. 인근 주민은 대피 바랍니다",
    "이것은 훈련이 아닌 실제 상황입니다. 서울 전역 지진 발생, 즉시 대피 바랍니다",
    "OO 소방 훈련장 화재 발생 — 인근 차량 우회 바랍니다",              # 장소 이름 속 「훈련」
    "눈비로 ○○마을 ~ 예비군훈련장 방면 도로를 통제하오니 우회하여 주시기 바랍니다",   # 실측 말투 — 장소 이름 속 「훈련」
    # `[Codex 검토]` 「문자」를 통째 꼬리로 두면 이것을 놓친다 — 오발송 정정만 꼬리다
    "훈련 중 실제 재난 발생, 실제 재난문자 발송합니다. 즉시 대피 바랍니다",
]


def _rows(text, kind):
    return [{"created_at": AT - timedelta(minutes=20), "kind": kind, "step": "긴급재난", "text": text,
             "regions": ["서울특별시 전체"], "serial": "1"}]


@pytest.mark.parametrize("text", DRILLS)
def test_drill_notices_are_not_counted_anywhere(text):
    messages, _ = judge(_rows(text, "지진"), region="서울", district=None, window_start=AT - timedelta(hours=6), at=AT)
    assert messages == [], text
    cause = {"category": "disaster_msg", "kind": "지진", "step": "긴급재난", "text": text,
             "created_at": "2026-09-23T10:07:00+09:00"}
    assert classify([cause], SafetyRules.from_guardrails()) is None, text
    assert ImpactRules.load().is_released(text), text


@pytest.mark.parametrize("text", ACTUALS)
def test_actual_events_mentioning_a_drill_are_still_counted(text):
    messages, _ = judge(_rows(text, "화재"), region="서울", district=None, window_start=AT - timedelta(hours=6), at=AT)
    assert len(messages) == 1, text
    cause = {"category": "disaster_msg", "kind": "화재", "step": "긴급재난", "text": text,
             "created_at": "2026-09-23T10:07:00+09:00"}
    event = classify([cause], SafetyRules.from_guardrails())
    assert event is not None and event.level == "day", text
    rules = ImpactRules.load()
    assert not rules.is_released(text), text
    assert rules.kind_class("화재", text) != IGNORED, text


def test_the_drill_words_have_one_source():
    # ★세 곳이 같은 설정 낱말을 쓴다 — 표가 갈라지면 정지와 성립 판정이 또 어긋난다
    from app.core.settings import get_guardrails

    guard = get_guardrails()
    safety, impact = SafetyRules.from_guardrails(), ImpactRules.load()
    assert safety.exclude_keywords == tuple(guard.get("travel.safety.exclude_keywords")) == impact.exclude_words
    assert safety.drill_actual_keywords == tuple(guard.get("travel.safety.drill_actual_keywords")) == impact.drill_actual_words
    assert safety.drill_place_words == tuple(guard.get("travel.safety.drill_place_words")) == impact.drill_place_words
    assert safety.drill_conditional_tails == tuple(guard.get("travel.safety.drill_conditional_tails")) == impact.drill_conditional_tails
