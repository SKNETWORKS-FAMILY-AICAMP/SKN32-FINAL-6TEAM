"""실행 트레이스를 뜬다.

CPython 3.12 의 `sys.monitoring` 으로 대상 저장소의 `app/` 프레임만 모은다.
`sys.settrace` 는 line 추적 machinery 까지 개입해 느리므로 쓰지 않는다.

채점에 쓰려면 같은 시나리오를 두 번 돌렸을 때 결과가 같아야 한다. 그래서
호스트명·PID·시각·소요시간처럼 실행마다 달라지는 값은 트레이스에 넣지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "acop-trace/1.0"


def _enum(value: object) -> str | None:
    """Enum 이면 값을, 아니면 None. 자유 문자열은 절대 꺼내지 않는다."""
    inner = getattr(value, "value", None)
    return str(inner) if isinstance(inner, str) else None


def _count(value: object) -> int | None:
    try:
        return len(value)  # type: ignore[arg-type]
    except TypeError:
        return None


#: 함수 진입 시 꺼낼 도메인 값. **allowlist 다** — payload 나 자유 문자열은 넣지 않는다.
#: 앱이 저장 전에 마스킹하더라도 tracer 는 그보다 먼저 인자를 보기 때문에,
#: 무엇을 꺼낼지 여기서 못 박지 않으면 원문 PII 가 학습자 화면까지 간다.
DOMAIN_FIELDS = {
    "transition_case": lambda loc: {
        "event": _enum(loc.get("event_type")),
        "expected_version": loc.get("expected_version") if isinstance(
            loc.get("expected_version"), int) else None,
    },
    "ContextPack._budget_and_signals": lambda loc: {
        "degraded": bool(getattr(loc.get("self"), "degraded", False)),
        "omissions": _count(getattr(loc.get("self"), "omissions", None)),
        "tokens": getattr(loc.get("self"), "estimated_input_tokens", None),
        "budget": getattr(loc.get("self"), "token_budget", None),
    },
    "TeamResult._next_action_consistency": lambda loc: {
        "next_action": _enum(getattr(loc.get("self"), "next_action", None)),
        "proposals": _count(getattr(loc.get("self"), "action_proposals", None)),
        "evidence": _count(getattr(loc.get("self"), "evidence", None)),
    },
    "TeamTask._resume_consistency": lambda loc: {
        "capability": _enum(getattr(loc.get("self"), "capability", None)),
        "resume": bool(getattr(loc.get("self"), "resume", False)),
    },
    "next_status": lambda loc: {
        "from": _enum(loc.get("current")),
        "event": _enum(loc.get("event")),
    },
}


@dataclass
class Collector:
    """`sys.monitoring` 콜백이 채우는 버퍼."""

    app_root: str
    cwd: str
    active: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)

    def on_py_start(self, code, offset):
        if not self.active:
            return sys.monitoring.DISABLE
        filename = code.co_filename
        if not filename.startswith(self.app_root):
            return sys.monitoring.DISABLE
        if code.co_name == "<module>":
            return None
        qualname = code.co_qualname
        # 클래스 본문 프레임은 호출이 아니라 정의다. 흐름에 넣지 않는다.
        if qualname and "." not in qualname and qualname[:1].isupper():
            return None
        # 연속한 두 이벤트는 호출 관계가 아니다. 지도에 "누가 누구를 부른다"를 그리려면
        # 실제 호출자를 봐야 한다. 콜백 위쪽 프레임이 지금 진입한 함수이고, 그 f_back 이 호출자다.
        caller = None
        try:
            frame = sys._getframe(1)
            back = frame.f_back if frame else None
            while back is not None and not back.f_code.co_filename.startswith(self.app_root):
                back = back.f_back
            if back is not None:
                caller = back.f_code.co_qualname
        except (ValueError, AttributeError):
            caller = None
        # 도메인 값은 allowlist 로만 꺼낸다. 프레임 로컬을 통째로 읽지 않는다.
        domain = None
        extractor = DOMAIN_FIELDS.get(qualname)
        if extractor is not None:
            try:
                frame = sys._getframe(1)
                values = extractor(frame.f_locals) if frame else {}
                domain = {k: v for k, v in values.items() if v is not None}
            except Exception:
                domain = None
        self.events.append(
            {
                "symbol": qualname,
                "path": os.path.relpath(filename, self.cwd).replace("\\", "/"),
                "line": code.co_firstlineno,
                "caller": caller,
                "domain": domain or None,
            }
        )
        return None


#: 트레이스에 들어가면 안 되는 값의 이름. 시나리오마다 달라지는 것들이다.
#: 지금은 프레임 로컬을 allowlist 로만 읽으므로 이 목록에 걸릴 일이 없지만,
#: DOMAIN_FIELDS 에 새 항목을 넣을 때 실수로 흘리는 것을 막는 이중 잠금이다.
FORBIDDEN_KEYS = frozenset({
    "payload", "state_json", "arguments", "text", "input_text", "answer",
    "message", "prompt", "token", "authorization", "secret", "api_key",
    "customer_id", "tenant_id", "email", "phone",
})


def audit(trace: dict[str, Any]) -> list[str]:
    """채점 파일에 들어가면 안 되는 것이 섞였는지 본다.

    tracer 는 앱이 마스킹하기 **전에** 인자를 본다. 무엇을 꺼낼지 못 박아 두지 않으면
    원문 PII 가 학습자 화면까지 간다. 그래서 뜬 뒤에도 한 번 더 검사한다.
    """
    problems: list[str] = []
    for step in trace.get("steps", []):
        for key, value in (step.get("domain") or {}).items():
            if key in FORBIDDEN_KEYS:
                problems.append(f"{step['symbol']}: 금지된 필드 {key}")
            if isinstance(value, str) and len(value) > 40:
                problems.append(f"{step['symbol']}: 긴 문자열 {key} ({len(value)}자)")
    for key in ("generated_at", "hostname", "pid", "duration"):
        if key in trace:
            problems.append(f"실행마다 달라지는 값이 들어 있다: {key}")
    return problems


def collapse(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """연속으로 같은 함수가 반복되면 하나로 접는다.

    재귀나 루프 안의 반복 호출이 트레이스를 수천 줄로 부풀리는 것을 막는다.
    접힌 횟수는 `repeat` 로 남겨 정보를 잃지 않는다.
    """
    out: list[dict[str, Any]] = []
    for event in events:
        key = (event["path"], event["symbol"],
               json.dumps(event.get("domain"), sort_keys=True))
        previous = (out[-1]["path"], out[-1]["symbol"],
                    json.dumps(out[-1].get("domain"), sort_keys=True)) if out else None
        if previous == key:
            out[-1]["repeat"] = out[-1].get("repeat", 1) + 1
            continue
        out.append(dict(event))
    for index, event in enumerate(out):
        event["i"] = index
    return out


def canonical_json(payload: dict[str, Any]) -> str:
    """같은 내용이면 언제나 같은 바이트가 나오는 직렬화."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def digest(payload: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def code_revision(target: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=target, capture_output=True, text=True, timeout=20, check=False,
        )
        return "git:" + out.stdout.strip() if out.returncode == 0 else "git:unknown"
    except Exception:
        return "git:unknown"


def run_in_process(nodeid: str) -> dict[str, Any]:
    """대상 저장소 안에서 호출된다. pytest 를 돌리며 트레이스를 모은다."""
    import pytest

    cwd = os.getcwd()
    collector = Collector(app_root=str(Path("app").resolve()), cwd=cwd)
    tool = sys.monitoring.PROFILER_ID
    events_mod = sys.monitoring.events

    class Plugin:
        outcome = {"status": "unknown"}

        @pytest.hookimpl(wrapper=True)
        def pytest_runtest_call(self, item):
            collector.active = True
            sys.monitoring.restart_events()
            try:
                result = yield
                self.outcome["status"] = "passed"
                return result
            except BaseException:
                self.outcome["status"] = "failed"
                raise
            finally:
                collector.active = False

    plugin = Plugin()
    sys.monitoring.use_tool_id(tool, "acop_dojo")
    sys.monitoring.register_callback(tool, events_mod.PY_START, collector.on_py_start)
    sys.monitoring.set_events(tool, events_mod.PY_START)
    try:
        pytest.main([nodeid, "-q", "--no-header", "-p", "no:cacheprovider"], plugins=[plugin])
    finally:
        sys.monitoring.set_events(tool, 0)
        sys.monitoring.free_tool_id(tool)

    steps = collapse(collector.events)
    return {
        "schema_version": SCHEMA_VERSION,
        "entry": nodeid,
        "runtime": {"python": "%d.%d" % sys.version_info[:2], "backend": "sys.monitoring"},
        "outcome": plugin.outcome,
        "steps": steps,
        "summary": {
            "raw_events": len(collector.events),
            "steps": len(steps),
            "unique_symbols": len({(s["path"], s["symbol"]) for s in steps}),
        },
    }


def capture(nodeid: str, *, target: Path, out_path: Path) -> dict[str, Any]:
    """대상 저장소에서 시나리오를 돌려 트레이스 파일을 만든다."""
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    package_root = str(Path(__file__).resolve().parent.parent)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_root, env.get("PYTHONPATH", "")]))
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-m", "acop_dojo._runner", nodeid, str(out_path)],
        cwd=target, env=env, capture_output=True, text=True, timeout=600, check=False,
    )
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(
            "트레이스를 뜨지 못했다.\n"
            f"  종료코드 {proc.returncode}\n  stdout: {proc.stdout[-800:]}\n  stderr: {proc.stderr[-800:]}"
        )
    trace = json.loads(out_path.read_text(encoding="utf-8"))
    trace["code_revision"] = code_revision(target)
    return trace
