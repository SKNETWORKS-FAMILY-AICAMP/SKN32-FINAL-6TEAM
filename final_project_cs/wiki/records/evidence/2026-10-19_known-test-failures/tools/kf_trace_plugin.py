"""조사용 추적 플러그인 — 저장소 코드는 바꾸지 않고, 시험 중 함수 호출 결과만 찍는다."""
import functools
import sys


def _wrap(module, name):
    original = getattr(module, name)

    @functools.wraps(original)
    def traced(*args, **kwargs):
        try:
            result = original(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            print(f"[TRACE] {module.__name__}.{name} raised {type(exc).__name__}: {exc}", file=sys.stderr)
            raise
        summary = result
        if isinstance(result, (list, tuple, set, dict)):
            summary = f"{type(result).__name__}(len={len(result)})"
        extra = {k: (v if not hasattr(v, "__len__") or isinstance(v, str) else f"len={len(v)}")
                 for k, v in kwargs.items() if k in ("now", "radius_m", "wide_radius_m", "indoor_only", "causes", "places", "options")}
        print(f"[TRACE] {module.__name__}.{name}({extra}) -> {str(summary)[:200]}", file=sys.stderr)
        return result

    setattr(module, name, traced)


def pytest_configure(config):
    from app.domains.travel_ops.components.watch import watch_relaxed
    from app.domains.travel_ops.components.places import catalog_pool

    for name in ("offer_relaxed", "relaxed_options", "verified_options", "other_sites", "unused_places"):
        if hasattr(watch_relaxed, name):
            _wrap(watch_relaxed, name)
    _wrap(catalog_pool, "widen_activity_pool")
