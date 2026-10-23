"""검사 누락을 확정 판정과 분리해 현재 접수에 안내한다."""
from __future__ import annotations

from typing import Any


CHECK_LABELS = {"found": "식당 확인", "open_at": "방문 시각 영업 확인", "closed_day": "휴무 확인",
                "business": "폐업·이전 확인", "dietary": "식사 조건 확인", "kids": "아이 동반 확인",
                "payment": "결제 조건 확인", "_request": "요청 조건 확인"}
ATTRIBUTE_LABELS = {"halal": "할랄", "vegetarian": "채식", "kids": "아이 동반", "card": "카드 결제"}


def merge_missing(review: dict[str, Any], missing: dict[str, list[dict[str, Any]]]) -> None:
    """누락 안내만 갱신한다. 기존 결과·상태·등록 가능 여부는 변경하지 않는다."""
    for item in review.get("items") or []:
        if item.get("kind") != "dining":
            continue
        rows = item.setdefault("rows", [])
        rows[:] = [r for r in rows if not (r.get("row") == "dining_check" and r.get("by") == "agent_check")]
        gaps = missing.get(str(item.get("id"))) or []
        if not gaps:
            continue
        labels = list(dict.fromkeys(ATTRIBUTE_LABELS.get(g.get("attribute"))
                                    or CHECK_LABELS.get(g.get("check"), "식당 조건 확인") for g in gaps))
        rows.append({"row": "dining_check", "result": "unknown", "by": "agent_check",
                     "text": "추가 확인을 마치지 못했어요: " + " · ".join(labels) + " · 원하시면 다시 확인해 주세요",
                     "missing_checks": [{k: g[k] for k in ("check", "failure", "request_id", "attribute") if k in g}
                                        for g in gaps]})
