# -*- coding: utf-8 -*-
"""LLM 이 정한 값으로 판정했을 때 고객 답에 붙이는 안내 — D-CS-015 개정 2(2026-10-12 사용자 결정) 「고객 안내」. `[2026-10-12]`

★규칙이 정한 값 · 고객이 답한 값에는 붙이지 않는다. 모델이 원문을 읽어 만든 값(요일표 · 실내외)으로 판정했을 때만.
★문구는 이 파일 한 곳에 둔다 — 고객 문의 · 계획 검증 · 감시가 같은 말을 쓰게.
"""
from __future__ import annotations

from typing import Any

#: 운영시간 · 휴무를 모델이 읽은 요일표로 판정했을 때
HOURS_AUTO_READ = "운영시간은 공개된 안내문을 자동으로 읽어 확인했어요. 방문 전 한 번 더 확인해 주세요."
#: 실내외를 모델이 판정한 값으로 판정했을 때 — 고객이 고치면 그 값이 우선한다(`indoor_store`)
INDOOR_AUTO = "실내·야외 여부는 자동으로 판단한 결과예요. 다르면 알려 주세요."


def hours_read_by_model(hours: dict[str, Any] | None) -> bool:
    """요일표를 모델이 읽었나 — `hours_read.method == "llm"`. 원장 행(`hours_read`)과 코어 운영시간(`attributes.hours_read`) 둘 다 본다."""
    if not isinstance(hours, dict):
        return False
    record = hours.get("hours_read") or (hours.get("attributes") or {}).get("hours_read") or {}
    return isinstance(record, dict) and record.get("method") == "llm"


def with_notice(text: str | None, notice: str | None) -> str | None:
    """문장 뒤에 안내를 붙인다. 둘 중 하나가 없으면 있는 것만."""
    if not notice:
        return text
    return f"{text} {notice}" if text else notice
