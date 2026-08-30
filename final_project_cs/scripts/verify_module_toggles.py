# -*- coding: utf-8 -*-
"""모듈 토글을 실제로 껐다 켜며 앱 동작을 확인한다.

    python -m scripts.verify_module_toggles

계약 `docs/handoff/08_모듈_컴포넌트_목록.md` §2·§6-4 가 요구하는 동작을
선언을 진짜로 고쳐 가며 확인한다. 단위 테스트는 설정을 주입해서 보지만,
이 스크립트는 `config/project.yaml` 을 실제로 바꾸고 앱을 새 프로세스에서
띄운다 — 조립이 기동 시점에 한 번만 일어나기 때문이다.

★설정 파일을 되돌리는 것을 finally 로 감싼다. 중간에 죽어도 원본이 남아야 한다.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
CFG = REPO / "config" / "project.yaml"
BAK = REPO / "config" / "project.yaml.verifybak"


def _set_module(text: str, module: str, enabled: bool) -> str:
    pattern = re.compile(r"(^  %s:\n    enabled: )(true|false)$" % re.escape(module), re.M)
    new, count = pattern.subn(lambda m: m.group(1) + ("true" if enabled else "false"), text)
    if count != 1:
        raise SystemExit("선언에서 모듈 %s 를 한 번 찾지 못했다 (%d건)" % (module, count))
    return new


def run(label: str, module: str, enabled: bool, probe: str) -> None:
    shutil.copy(CFG, BAK)
    try:
        CFG.write_text(_set_module(CFG.read_text(encoding="utf-8"), module, enabled),
                       encoding="utf-8")
        print("\n===== %s   (%s: %s)" % (label, module, "true" if enabled else "false"))
        out = subprocess.run([sys.executable, "-c", probe], cwd=REPO, capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
        print((out.stdout or "").strip())
        if out.returncode != 0:
            tail = (out.stderr or "").strip().splitlines()
            print("   stderr:", tail[-1] if tail else "(없음)")
    finally:
        shutil.copy(BAK, CFG)
        BAK.unlink()


PROBE_UI = """
import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from fastapi.testclient import TestClient
from app.presentation.api.app import create_app
client = TestClient(create_app())
print('GET /ui/voc ->', client.get('/ui/voc').status_code)
print('상단 메뉴에 VOC 링크 ->', '/ui/voc' in client.get('/ui/cases').text)
"""

PROBE_GRAPH = """
import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import app.presentation.ui.routes as routes
print('관리자 화면 GraphStorePort 줄 ->', routes._graph_port_name('demo'))
"""

PROBE_MCP = """
import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from app.presentation.api import cases
try:
    cases._mcp_cases('11111111-1111-1111-1111-111111111111', 10)
    print('tool 호출 -> 통과 (DB 조회까지 감)')
except Exception as exc:
    print('tool 호출 ->', type(exc).__name__, '|', exc)
"""

PROBE_BOOT = """
import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')
try:
    from app.presentation.api.app import create_app
    create_app(); print('기동 -> 성공')
except Exception as exc:
    print('기동 ->', type(exc).__name__, '|', exc)
"""


def main() -> int:
    run("VOC 켬 — 화면과 메뉴가 있다", "voc", True, PROBE_UI)
    run("VOC 끔 — 기동 자체가 거부된다", "voc", False, PROBE_BOOT)
    run("graph_store 켬 — 어댑터 이름이 뜬다", "graph_store", True, PROBE_GRAPH)
    run("graph_store 끔 — 껐다고 적는다", "graph_store", False, PROBE_GRAPH)
    run("mcp 켬 — tool 이 동작 경로로 간다", "mcp", True, PROBE_MCP)
    run("mcp 끔 — tool 이 거부된다", "mcp", False, PROBE_MCP)
    print("\n원복 확인:", CFG.read_text(encoding="utf-8").count("enabled: true"), "개가 켜져 있다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
