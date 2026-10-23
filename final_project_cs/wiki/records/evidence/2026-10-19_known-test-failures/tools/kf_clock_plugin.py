"""조사용 확인 플러그인 — 지정한 모듈의 벽시계(datetime.now)만 고정 시각으로 바꾼다.
저장소 코드는 바꾸지 않는다. 「시각만 맞으면 통과하나」를 가르는 실험이다.
KF_FIXED_NOW: 고정 시각(기본 2026-09-23T09:00+09:00) · KF_MODULES: 쉼표로 나눈 모듈 경로(기본 watch_relaxed)."""
import importlib
import os
from datetime import datetime as _dt


def pytest_configure(config):
    fixed = _dt.fromisoformat(os.environ.get("KF_FIXED_NOW", "2026-09-23T09:00:00+09:00"))
    modules = os.environ.get("KF_MODULES", "app.domains.travel_ops.components.watch.watch_relaxed").split(",")

    class Frozen(_dt):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

    for path in modules:
        importlib.import_module(path.strip()).datetime = Frozen
