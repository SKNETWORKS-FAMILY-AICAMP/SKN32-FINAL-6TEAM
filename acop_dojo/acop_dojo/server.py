"""로컬 실행 서버. 브라우저에서 도장을 돌린다.

지금까지 화면은 거울이었다 — CLI 가 남긴 것을 보여 주기만 했다. 여기서 실행까지 연다.
다만 **판정은 그대로 pytest 와 실측 트레이스가 한다.** 서버는 CLI 를 그대로 띄우고
출력을 중계할 뿐이다. 브라우저에서 점수를 만들지 않는다.

안전
  · 127.0.0.1 에만 붙인다. 바깥에서 못 들어온다.
  · 돌릴 수 있는 것은 아래 ACTIONS 에 적은 도장 명령뿐이다. 임의 명령을 받지 않는다.
  · 인자도 목록에 있는 값(트랙·시나리오·단계 번호)이나 작업 폴더 안의 경로만 받는다.

학습 단계는 표준 입력을 묻는다(번호 고르기·설명 쓰기). 그래서 작업마다 stdin 을 열어 두고
브라우저가 한 줄씩 보낼 수 있게 했다. 그러지 않으면 learn·boss 를 웹에서 못 돌린다.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import WORKSPACE_ROOT, build_workspace, target_root

#: 브라우저가 부를 수 있는 것. 이름 → (도장 명령 조각, 받는 인자)
ACTIONS: dict[str, dict[str, Any]] = {
    "doctor": {"argv": ["doctor"], "params": []},
    "status": {"argv": ["status"], "params": []},
    "tracks": {"argv": ["tracks"], "params": []},
    "scenarios": {"argv": ["scenarios"], "params": []},
    "invariants": {"argv": ["invariants"], "params": []},
    "patches": {"argv": ["patches"], "params": []},
    "report": {"argv": ["report"], "params": []},
    "map": {"argv": ["map"], "params": ["track"]},
    "trace": {"argv": ["trace"], "params": ["scenario"]},
    "learn": {"argv": ["learn"], "params": ["stage", "track"], "asks": True},
    "defect": {"argv": ["defect"], "params": ["track", "fix"], "asks": True},
    "boss": {"argv": ["boss"], "params": ["fix", "force"], "asks": True},
    "review": {"argv": ["review"], "params": [], "asks": True},
    "placement": {"argv": ["placement"], "params": ["track"], "asks": True},
    "build_steps": {"argv": ["build", "steps"], "params": []},
    "build_start": {"argv": ["build", "start"], "params": ["force"]},
    "build_brief": {"argv": ["build", "brief"], "params": ["step"]},
    "build_check": {"argv": ["build", "check"], "params": ["step"]},
}
MAX_LINES = 4000


@dataclass
class Job:
    job_id: str
    action: str
    argv: list[str]
    process: subprocess.Popen
    lines: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LINES))
    done: bool = False
    returncode: int | None = None

    def snapshot(self, offset: int) -> dict[str, Any]:
        lines = list(self.lines)
        return {"job": self.job_id, "action": self.action, "done": self.done,
                "returncode": self.returncode, "next_offset": len(lines),
                "lines": lines[offset:]}


JOBS: dict[str, Job] = {}
_LOCK = threading.Lock()


def _pump(job: Job) -> None:
    assert job.process.stdout is not None
    for line in job.process.stdout:
        job.lines.append(line.rstrip("\n"))
    job.returncode = job.process.wait()
    job.done = True


def _validate(action: str, params: dict[str, Any]) -> list[str]:
    """인자를 목록에 있는 값으로만 좁힌다. 임의 문자열을 명령줄에 넣지 않는다."""
    from . import build, scenarios, tracks

    spec = ACTIONS[action]
    argv = list(spec["argv"])
    for name in spec["params"]:
        value = params.get(name)
        if value in (None, "", False):
            continue
        if name == "track":
            tracks.get(str(value))
            argv += ["--track", str(value)]
        elif name == "scenario":
            scenarios.get(str(value))
            argv.append(str(value))
        elif name == "stage":
            if str(value) not in {"0", "1", "2"}:
                raise ValueError(f"모르는 단계다: {value}")
            argv.append(str(value))
        elif name == "step":
            argv.append(str(build.get(int(value)).index))
        elif name == "force":
            argv.append("--force")
        elif name == "fix":
            patch = (build_workspace().parent / str(value)).resolve()
            if not patch.is_file() or WORKSPACE_ROOT not in patch.parents:
                raise ValueError("패치 파일은 작업 폴더 안에 있어야 한다")
            argv += ["--fix", str(patch)]
    return argv


def start(action: str, params: dict[str, Any]) -> Job:
    if action not in ACTIONS:
        raise ValueError(f"모르는 동작이다: {action}")
    argv = _validate(action, params)
    process = subprocess.Popen(
        [sys.executable, "-u", str(WORKSPACE_ROOT / "dojo.py"), *argv],
        cwd=WORKSPACE_ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1)
    job = Job(job_id=uuid.uuid4().hex[:12], action=action, argv=argv, process=process)
    with _LOCK:
        JOBS[job.job_id] = job
    threading.Thread(target=_pump, args=(job,), daemon=True).start()
    return job


def send_input(job_id: str, line: str) -> None:
    """학습 단계가 묻는 것에 답한다. CLI 가 stdin 을 읽고 있다."""
    job = JOBS[job_id]
    if job.done or job.process.stdin is None:
        raise ValueError("이미 끝난 작업이다")
    job.process.stdin.write(line.rstrip("\n") + "\n")
    job.process.stdin.flush()
    job.lines.append(f"> {line}")


def state() -> dict[str, Any]:
    """화면이 그릴 재료. 여기서 판정하지 않는다 — 파일에 있는 것만 읽는다."""
    from . import build, defect_stage, defects, progress, scenarios, tracks

    catalog = defects.load_catalog()
    entries = catalog.get("entries", {})
    survived = sorted(d for d, e in entries.items() if not e.get("gates", {}).get("kills_tests"))
    build_state = build.load_state()
    return {
        "target": str(target_root()),
        "build_target": str(build_workspace()),
        "tracks": [{"id": t.track_id, "title": t.title, "owner": t.owner_hint,
                    "focus": t.focus, "scenarios": list(t.scenarios)}
                   for t in tracks.TRACKS.values()],
        "parked_tracks": sorted(tracks.PARKED_TRACK_IDS),
        "scenarios": [{"id": s.scenario_id, "title": s.title, "needs_db": s.needs_db,
                       "objective": s.objective, "nodeid": s.nodeid}
                      for s in scenarios.SCENARIOS.values()],
        "build_steps": [{"index": s.index, "title": s.title, "claim": s.claim,
                         "files": s.paths(), "tests": list(s.tests),
                         "status": build_state["steps"].get(str(s.index), {}).get("status")}
                        for s in build.steps()],
        "build_revealed": build_state.get("revealed", []),
        "progress": progress.load(),
        "catalog": {"entries": len(entries), "playable": len(defect_stage.playable(catalog)),
                    "survived": survived, "parked": len(catalog.get("parked", {})),
                    "baseline": catalog.get("baseline", {}).get("summary")},
        "actions": {name: spec["params"] for name, spec in ACTIONS.items()},
        "asks_input": sorted(n for n, s in ACTIONS.items() if s.get("asks")),
    }


def ui_path() -> Path | None:
    """화면 파일. 없으면 지도를 대신 낸다."""
    web = Path(__file__).resolve().parent / "web" / "index.html"
    if web.is_file():
        return web
    generated = WORKSPACE_ROOT / ".acop_dojo" / "map.html"
    return generated if generated.is_file() else None


class Handler(BaseHTTPRequestHandler):
    server_version = "acop-dojo"

    def log_message(self, fmt: str, *args: Any) -> None:  # 조용히
        pass

    def _send(self, code: int, payload: Any, content_type: str = "application/json") -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path)
        try:
            if route.path in ("/", "/index.html"):
                path = ui_path()
                if path is None:
                    return self._send(200, b"<p>\xed\x99\x94\xeb\xa9\xb4\xec\x9d\xb4 \xec\x95\x84\xec\xa7\x81 \xec\x97\x86\xeb\x8b\xa4. python dojo.py map \xec\x9d\x84 \xeb\xa8\xbc\xec\xa0\x80 \xeb\x8f\x8c\xeb\xa6\xb0\xeb\x8b\xa4.</p>", "text/html")
                return self._send(200, path.read_bytes(), "text/html")
            if route.path == "/api/state":
                return self._send(200, state())
            if route.path.startswith("/api/jobs/"):
                job_id = route.path.split("/")[3]
                offset = int(dict(p.split("=", 1) for p in route.query.split("&") if "=" in p).get("offset", 0))
                job = JOBS.get(job_id)
                if job is None:
                    return self._send(404, {"error": "모르는 작업이다"})
                return self._send(200, job.snapshot(offset))
        except Exception as error:  # 화면에 사유를 그대로 보여 준다
            return self._send(400, {"error": f"{type(error).__name__}: {error}"})
        self._send(404, {"error": "없는 주소다"})

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            if route.path == "/api/run":
                job = start(payload.get("action", ""), payload.get("params") or {})
                return self._send(200, {"job": job.job_id, "argv": job.argv})
            if route.path.endswith("/input"):
                send_input(route.path.split("/")[3], str(payload.get("line", "")))
                return self._send(200, {"ok": True})
            if route.path.endswith("/stop"):
                JOBS[route.path.split("/")[3]].process.terminate()
                return self._send(200, {"ok": True})
        except Exception as error:
            return self._send(400, {"error": f"{type(error).__name__}: {error}"})
        self._send(404, {"error": "없는 주소다"})


def serve(port: int = 8765, *, open_browser: bool = True) -> int:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"도장 서버: {url}")
    if open_browser:
        # 터미널을 못 보는 사람도 바로 화면을 본다. 서버가 뜬 뒤에 연다.
        import webbrowser
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    print(f"  대상 저장소 {target_root()}")
    print("  돌릴 수 있는 것: " + ", ".join(ACTIONS))
    print("  멈추려면 Ctrl+C")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 닫는다")
    finally:
        httpd.server_close()
        for job in JOBS.values():
            if not job.done:
                job.process.terminate()
    return 0
