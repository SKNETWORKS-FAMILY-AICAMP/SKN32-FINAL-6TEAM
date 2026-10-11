"""2026-09-08 게이트 — 작업 기록은 `wiki/records/` 에 산다. `docs/` 는 다시 생기면 안 된다.

★사용자 결정(2026-09-08): `docs/` 를 `wiki/records/` 로 합쳤다. 진입점 하나·검사기 하나.
  옛 규칙을 기억하는 세션이 `docs/reports/…` 에 리포트를 쓰면 그 순간 두 벌이 된다 —
  사람 눈으로는 못 막는다. 이 게이트가 막는다.
  기록 규칙: RULE.md §2 (evidence·reports 는 wiki/records/ 아래, history·plans 는 동결).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_docs_folder_does_not_come_back():
    assert not (ROOT / "docs").exists(), (
        "docs/ 가 다시 생겼다. 기록은 wiki/records/<evidence|reports>/ 에 쓴다 (RULE.md §2, 2026-09-08)"
    )


def test_records_are_where_the_rules_say():
    for sub in ("evidence", "reports"):
        assert (ROOT / "wiki" / "records" / sub).is_dir(), f"wiki/records/{sub}/ 가 없다"
