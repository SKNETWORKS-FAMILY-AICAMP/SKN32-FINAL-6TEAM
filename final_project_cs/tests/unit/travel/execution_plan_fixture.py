"""격리 회귀 전용 명시적 모델 대역. 제품 코드의 대체 순서가 아니다."""
from app.domains.travel_ops.components.planning.execution_plan import validate_plan


def fixture_plan(*, query, trip, items, issues, teams):
    by_id = {str(i.item_id): i for i in items}
    # 기존 계산 회귀를 동일 조건으로 재생한다. 동적 순서는 별도 인수 시험에서 바꾼다.
    ordered = sorted(issues, key=lambda e: ({"activity": 0, "dining": 1, "mobility": 2}[by_id[str(e["item_id"])].kind],
                                         by_id[str(e["item_id"])].starts_at))
    raw = {"schema_version": "1.0", "base_version": trip["version"], "steps": [
        {"item_id": str(e["item_id"]), "team_id": by_id[str(e["item_id"])].kind, "order": index,
         "priority": 1, "depends_on": [], "tools": teams[by_id[str(e["item_id"])].kind]["tools"],
         "max_calls": teams[by_id[str(e["item_id"])].kind]["max_calls"], "reason": "명시적 회귀 재생 계획"}
        for index, e in enumerate(ordered, 1)]}
    return validate_plan(raw, version=trip["version"], issues=[{**e, "kind": by_id[str(e["item_id"])].kind} for e in issues], teams=teams)
