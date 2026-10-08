"""택시 첫 호출에서 속도 그래프가 적재되고 같은 입력에서 재사용되는지 확인한다."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domains.travel_ops.instances.mobility.engine import car, paths, runtime


def test_lazy_car_loads_graph_once_across_services(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROCESSED", Path(tmp_path))
    monkeypatch.setattr(runtime, "_CAR_GRAPHS", {})
    calls = []
    graph = object()
    monkeypatch.setattr(car.CarGraph, "load", lambda folder, holidays: calls.append(folder) or graph)
    monkeypatch.setattr(car, "CarService", lambda graph, router, rules: SimpleNamespace(
        leg=lambda *args, **kwargs: {"fare_won": 12000}))
    first = runtime._LazyCar(object(), {}, set())
    second = runtime._LazyCar(object(), {}, set())
    assert first.leg(None, None, None, taxi=True) == {"fare_won": 12000}
    assert second.leg(None, None, None, taxi=True) == {"fare_won": 12000}
    assert len(calls) == 1


def test_missing_graph_raises_without_caching_a_service(monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "PROCESSED", Path(tmp_path))
    monkeypatch.setattr(runtime, "_CAR_GRAPHS", {})
    monkeypatch.setattr(car.CarGraph, "load", lambda folder, holidays: None)
    service = runtime._LazyCar(object(), {}, set())
    with pytest.raises(car.RouterDown, match="도로망 속도 자료"):
        service.leg(None, None, None, taxi=True)
    assert service._svc is None
    assert runtime._CAR_GRAPHS == {}
