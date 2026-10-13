"""제품 입구 시험에 계산 제공자를 명시한다. 운영 계산의 정확도 시험용은 아니다."""
from __future__ import annotations

import copy
from datetime import timedelta

from app.core.service_bindings import BindingTable


def publish_test_services(app, replacements):
    """기존 등록표·판 번호를 보존한 새 시험용 계산 표를 발행한다."""
    runtime = app.state.runtime
    published = runtime.published_snapshot()
    controller = copy.copy(published.controller)
    prior = controller.service_bindings
    assert isinstance(prior, BindingTable), "시험도 고정된 조립 표를 사용해야 합니다"
    assert prior.registry is controller.registry and prior.revision == published.revision
    values = dict(prior.values)
    values.update(replacements)
    controller.service_bindings = BindingTable(values, controller.registry, published.revision)
    runtime.swap(controller, published.revision)
    assert runtime.published_snapshot().controller.service_bindings is controller.service_bindings
    return controller


def publish_fixed_mobility(app, *, eta_min=5, source="fixed_mobility_test"):
    """좌표·시각 계약을 검사하는 고정 구간. 호출 기록에는 원 좌표를 남기지 않는다."""
    assert eta_min > 0
    calls = []
    duration = timedelta(minutes=eta_min)

    def planner(party_size, constraints, **kwargs):
        def leg(a, b, arrive, not_before=None):
            assert all(isinstance(p[axis], (int, float)) for p in (a, b) for axis in ("lat", "lon"))
            start = not_before if not_before is not None else arrive - duration
            end = start + duration
            if end > arrive:
                return None, {"code": "arrive_late", "source": source}
            calls.append((a["name"], b["name"], start, end))
            route = {"from": a["name"], "to": b["name"], "planned": "test_route",
                     "options": [{"id": "test_route", "label": "시험용 이동 구간", "eta_min": eta_min,
                                  "uses": [], "source": source}]}
            return {"route": route, "starts_at": start, "ends_at": end,
                    "eta_min": eta_min, "left_out": []}, None
        return leg

    publish_test_services(app, {
        ("legs", "leg_planner"): planner,
        ("legs", "walk_limit_m"): lambda: 1200,
        ("legs", "basis"): lambda: {"mode": "test_fixture", "source": source},
    })
    return calls
