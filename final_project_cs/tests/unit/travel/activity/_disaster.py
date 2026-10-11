# -*- coding: utf-8 -*-
"""시험용 `read.disaster` 응답 — 공유 점검 결과(`read.disruptions`)에 실린 재난문자와 **같은 문자**를 돌려준다. `[2026-10-11]`

★성립 판정은 공유 점검의 재난문자 항목이 `ok` 면 `read.disaster` 로 문자를 다시 읽어 수정본 §8 분류표로 가른다(구현 계획 2.4).
  실제로는 같은 소스 · 같은 구 판정이라 두 응답의 문자가 같다 — 시험도 그렇게 맞춘다.
"""
from __future__ import annotations

from typing import Any


def disaster_from(report: dict[str, Any] | None) -> dict[str, Any] | None:
    checks = [c for c in (report or {}).get("checks") or [] if c.get("category") == "disaster_msg"]
    if not checks:
        return None
    counted = [d for d in (report or {}).get("disruptions") or [] if d.get("category") == "disaster_msg"]
    return {"for_region": counted, "unclassified": list(checks[0].get("unclassified") or []), "covered": True}
