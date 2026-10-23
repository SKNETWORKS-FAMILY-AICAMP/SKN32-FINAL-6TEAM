# -*- coding: utf-8 -*-
"""이동 계산기 점검 스크립트를 자동 시험으로 돌린다 — 이동 계산기 문제목록(2026-09-29) #55.

앞 판은 입력 변환(어댑터)·결과 접기 계약·자기점검 불변식을 **사람이 명령줄로만** 돌렸다 — CI 가 그 부분을 보지 않았다.
스크립트는 고치지 않고 그대로 부른다(이동 담당이 명령줄로 쓰는 것과 같은 판정). 종료 코드 0 이 통과다.

자료(시간표) 없이 도는 것만 여기 둔다. 실제 시간표를 올리는 check_runtime.py 는 자료가 있는 기기에서만 돈다 —
없으면 **이유를 달고 건너뛴다**(보고에 SKIP 으로 드러난다).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# 저장소 맨 위(final_project_cs/ 가 있는 조상)를 위로 찾는다 — #56 과 같은 규칙. 없으면 멈춘다(조용한 스킵 금지)
REPO = next((p for p in Path(__file__).resolve().parents if (p / "final_project_cs" / "app").is_dir()), None)
if REPO is None:
    raise RuntimeError(f"final_project_cs/ 를 못 찾았다(시작: {Path(__file__).resolve()})")
CHECKS = Path(__file__).resolve().parent   # 81: 점검 스크립트는 이 시험과 같은 폴더

NO_DATA = [
    ("check_adapter.py", "합계"),            # 가짜 판정기로 어댑터 분기 30가지
    ("check_fold.py", "실패 0 건"),           # 결과 접기 산출물 스키마 + 구조 보장
    ("check_selfcheck_invariants.py", "통과"),         # 자기점검 불변식 13가지
]


def _run(rel: str, timeout: int = 300) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               PYTHONPATH=os.pathsep.join([str(REPO / "final_project_cs"), str(REPO)]))
    return subprocess.run([sys.executable, "-B", str(CHECKS / rel)], cwd=REPO, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=timeout)


@pytest.mark.parametrize("rel,marker", NO_DATA, ids=[r for r, _ in NO_DATA])
def test_check_script_passes(rel, marker):
    out = _run(rel)
    tail = (out.stdout + out.stderr)[-2000:]
    assert out.returncode == 0, f"{rel} 가 실패했다(종료 코드 {out.returncode}):\n{tail}"
    assert marker in out.stdout, f"{rel} 가 끝 요약을 내지 않았다 — 도중에 멈췄을 수 있다:\n{tail}"


def test_check_runtime_on_real_timetable():
    """실제 시간표로 어댑터를 끝까지(약 33초). 자료가 없는 기기는 이유를 달고 건너뛴다."""
    from app.domains.travel_ops.instances.mobility.engine.paths import cli_processed, UNSET_DIR
    import app.domains.travel_ops.instances.mobility.engine.paths as paths
    before = (paths.SOURCE, paths.DATA_DIR)
    try:
        processed = cli_processed()
    finally:
        paths._layout(before[1], before[0])       # 이 시험이 다른 시험의 자료 폴더 상태를 바꾸지 않게
    if processed == UNSET_DIR / "travel" / "processed" or not (processed / "mobility" / "timetable_v1.jsonl").exists():
        pytest.skip("시간표 없음(DATA_DIR/travel/processed/mobility/timetable_v1.jsonl) — 자료 기기에서만 돈다(문제목록 #54)")
    out = _run("check_runtime.py", timeout=900)
    assert out.returncode == 0, (out.stdout + out.stderr)[-2000:]
