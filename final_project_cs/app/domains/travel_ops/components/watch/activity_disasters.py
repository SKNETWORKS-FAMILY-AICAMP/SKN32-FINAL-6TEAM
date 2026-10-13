# -*- coding: utf-8 -*-
"""감시 — 관광지 항목의 재난문자 이상을 **활동 판정으로 다시 가른다**. `[2026-10-13]` 활동 코어 전달 사항 3번(감시)

★왜. 공유 점검(`DisruptionCheck`)은 재난문자를 「날씨형인가」로만 가른다 — 날씨 영향이 있는 장소면 다 이상, 없으면 날씨형을 뺀다.
  활동 팀의 재해 분류표(지역 위험형 · 야외 위험형 · 반영 안 함, 해제 · 복구 문자, 통제 시간, 장소 지목 중단)로 보면 둘 다 틀린다:
    「정전 복구가 완료되었습니다」   공유 점검은 이상 → 활동 판정은 영향 없음(뺀다)
    실내 박물관 + 「호우 · 산사태」  공유 점검은 날씨형이라 뺐다 → 활동 판정은 지역 위험형이라 막는다(더한다)
★판정은 활동 팀이 한다(`team_hooks/activity_ledger.disaster`). 미등록이면 공유 점검 결과를 그대로 쓴다(모름 — 바꾸지 않는다).
★「모름」은 지우지 않는다. 실내외를 몰라 묻게 될 문자 · 분류되지 않은 문자는 공유 점검이 센 대로 남긴다 — 감시는 묻지 않고
  (활동 팀 판정 메모 — 감시 루프는 보류), 이상을 활동 쪽 모름으로 없애지 않는다. 활동 팀의 감시 Case 경로(`plan_activity_trigger`)와 같은 기준이다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domains.travel_ops.components.team_hooks import activity_ledger


def rejudge(report: dict[str, Any], item: Any) -> dict[str, Any]:
    """관광지 항목의 점검 결과에서 재난문자 이상을 활동 판정으로 다시 센다. 바뀐 것이 없으면 받은 `report` 그대로."""
    if getattr(item, "kind", None) != "activity" or report.get("verdict") == "fatal":
        return report
    disruptions = list(report.get("disruptions") or [])
    held = [row for check in report.get("checks") or [] if check.get("category") == "disaster_msg"
            for row in check.get("weather_held_back") or []]
    if not held and not any(d.get("category") == "disaster_msg" for d in disruptions):
        return report
    place = getattr(item, "place", None) or {}
    at = item.starts_at if isinstance(getattr(item, "starts_at", None), datetime) else None

    def judged(message: dict[str, Any]) -> dict[str, Any] | None:
        return activity_ledger.disaster([message], outdoor=place.get("weather_sensitive"), at=at,
                                        place_name=place.get("name"))

    kept: list[dict[str, Any]] = []
    dropped = 0
    for row in disruptions:
        if row.get("category") != "disaster_msg":
            kept.append(row)
            continue
        verdict = judged(row)
        if verdict is None:
            return report                      # 미등록 — 공유 점검 결과 그대로
        if not verdict.get("blocks") and verdict.get("no_effect"):
            dropped += 1                       # 해제 · 복구 · 통제 시간 밖 · 실내의 야외 위험형 · 반영 안 함
            continue
        kept.append(row)
    added: list[dict[str, Any]] = []
    for row in held:
        verdict = judged(row)
        if verdict is None:
            return report
        if verdict.get("blocks"):
            added.append({**row, "indoor_region_hazard": True})
    if not dropped and not added:
        return report
    found = kept + added
    return {**report, "disruptions": found, "verdict": "disrupted" if found else "clear",
            "activity_rejudged": {"dropped": dropped, "added": len(added)}}


__all__ = ["rejudge"]
