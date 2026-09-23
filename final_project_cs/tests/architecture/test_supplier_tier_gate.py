"""★공급자 원장을 바꾸는 코드는 **등급 게이트를 먼저 지나야 한다** — v11 §12 DoD-14·15.

    14  실제 공급자에는 자동 실행이 걸리지 않는다 — 승인 경로로 간다
    15  자동 실행 분기는 `tier == 'simulated'` 에서만 열린다

★왜 아키텍처 테스트인가. 행동 시험(「real 등급이면 원장이 안 바뀐다」)은 **지금 있는 경로
  하나**를 본다. 새 적용기·새 스크립트·새 되돌림 경로가 `UPDATE supplier_bookings` 를
  한 줄 더 쓰면 행동 시험은 여전히 초록이고 아무도 모른다. 이 저장소는 그 함정을 실제로
  밟았다 — 「Mock 공급자 한정」이 **주석에만** 있었고 코드는 등급을 보지 않았다
  (wiki `teams/booking-handoff.md` 「자동 실행 분기 전체」, 2026-09-10 실측).

★DoD-23 의 교훈도 같이 받는다 — **통과하면서 아무것도 못 잡는 가드**가 이 저장소에 실제로
  있었다. 그래서 이 파일은 게이트가 **없는 코드를 실제로 빨갛게 만드는지**를 스스로
  시험한다(`test_the_gate_actually_catches_an_ungated_write`) — 검사기를 검사한다.

재현:

    python -m pytest tests/architecture/test_supplier_tier_gate.py -v
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.core.actions import ActionRejected
from app.modules.travel_ops.booking_actions import (APPROVED_HANDLERS, SIMULATED_TIER,
                                                    require_simulated_tier)

APP = Path("app")
SCRIPTS = Path("scripts")

#: 공급자 원장(`supplier_bookings`)을 **바꾸는** SQL. 읽기(`SELECT … FOR UPDATE`)는 아니다 —
#: 잠그고 등급을 읽는 것 자체가 게이트의 일부다.
WRITE_SQL = re.compile(r"\b(UPDATE\s+supplier_bookings"
                       r"|INSERT\s+INTO\s+supplier_bookings"
                       r"|DELETE\s+FROM\s+supplier_bookings)", re.IGNORECASE)

#: 게이트로 인정하는 호출 이름. ★문자열 비교(`tier == 'simulated'`)를 손으로 또 쓰는 것은
#:  인정하지 않는다 — 게이트가 여러 벌이 되면 한 벌만 고쳐도 조용히 새기 때문이다.
GATE = "require_simulated_tier"

#: ★시드·시험 준비처럼 **원장을 만드는** 자리는 게이트 대상이 아니다. 게이트는 「자동 실행이
#:  남의 원장을 바꾸는 것」을 막는 문이지 원장 자체를 못 만들게 하는 문이 아니다.
#:  ☆예외는 **경로마다 이유와 함께** 적는다. 목록이 늘면 그 자체가 신호다.
SEEDING_FILES = {
    # 시연 데이터 적재. 새 행을 만들 뿐 남의 예약을 바꾸지 않는다.
    "scripts/seed_travel.py",
    # 시험 잔여물 정리. 시험 tenant 만 지운다(`tenant_id LIKE`).
    "scripts/cleanup_test_residue.py",
    # ★`[2026-09-22]` DoD-18 측정 하네스. **자기가 만든 throwaway tenant** 안에서만
    #   원장 행을 만들고(INSERT) 재고 나서 지운다(DELETE) — 남의 예약을 바꾸는 `UPDATE`
    #   는 한 줄도 없다. 자동 실행 분기는 이 파일에 없다. 그 분기가 게이트를 지나는지를
    #   **재는** 쪽이고, 그 측정이 실제로 게이트를 세는 것은
    #   `tests/integration/controller/test_delegation_scope.py` 가 확인한다.
    #   ☆예외를 셋으로 늘린 것은 경계가 한 칸 물러난 것이다. 넷째를 넣으려면 그때는
    #     「원장을 만드는 자리」를 한 모듈로 모으는 쪽을 먼저 검토한다.
    "scripts/measure_delegation_scope.py",
}


def _python_files() -> list[Path]:
    out: list[Path] = []
    for root in (APP, SCRIPTS):
        if root.exists():
            out.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return out


def _ungated_writes(source: str, label: str) -> list[str]:
    """등급 게이트 없이(또는 게이트보다 **먼저**) 공급자 원장을 바꾸는 자리를 센다.

    판정 단위는 **함수 하나**다. 함수 안에 쓰기 SQL 이 있으면 같은 함수 안에
    `require_simulated_tier(...)` 호출이 있어야 하고, 그 호출이 쓰기보다 **위**에 있어야 한다.
    """
    tree = ast.parse(source)
    problems: list[str] = []

    #: 함수 밖(모듈 최상위)에 쓰기 SQL 이 있으면 게이트를 걸 자리가 없다 — 그것도 잡는다.
    owned: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            gates = sorted(call.lineno for call in ast.walk(node)
                           if isinstance(call, ast.Call)
                           and getattr(call.func, "id", getattr(call.func, "attr", None)) == GATE)
            for literal in ast.walk(node):
                if not (isinstance(literal, ast.Constant) and isinstance(literal.value, str)):
                    continue
                if not WRITE_SQL.search(literal.value):
                    continue
                owned.append(literal.lineno)
                if not gates:
                    problems.append(f"{label}:{literal.lineno}  {node.name}() 가 게이트 없이 공급자 "
                                    f"원장을 바꾼다 — {GATE}() 를 쓰기 **앞에** 둔다")
                elif min(gates) > literal.lineno:
                    problems.append(f"{label}:{literal.lineno}  {node.name}() 의 {GATE}() 가 쓰기보다 "
                                    f"뒤에 있다({min(gates)}줄) — 먼저 막고 바꾼다")

    for literal in ast.walk(tree):
        if (isinstance(literal, ast.Constant) and isinstance(literal.value, str)
                and WRITE_SQL.search(literal.value) and literal.lineno not in owned):
            problems.append(f"{label}:{literal.lineno}  함수 밖에서 공급자 원장을 바꾼다 — "
                            f"게이트를 걸 자리가 없다")
    return problems


# invariant: DoD-15
def test_every_write_to_the_supplier_ledger_passes_the_tier_gate_first():
    """★게이트를 지우거나 쓰기 아래로 내리면 여기서 빨갛게 난다."""
    problems: list[str] = []
    for path in _python_files():
        label = path.as_posix()
        if label in SEEDING_FILES:
            continue
        source = path.read_text(encoding="utf-8")
        if "supplier_bookings" not in source:
            continue
        problems.extend(_ungated_writes(source, label))
    assert not problems, ("공급자 원장을 등급 게이트 없이 바꾼다 — 실제 공급자면 승인 한 번에 "
                          "남의 돈이 나간다(v11 §4-C · DoD-14·15):\n" + "\n".join("  " + p for p in problems))


# invariant: DoD-15
def test_the_gate_actually_catches_an_ungated_write():
    """★**검사기를 검사한다.** 통과만 보면 아무것도 안 세는 가드도 초록이다(DoD-23 의 교훈).

    게이트를 지운 코드를 손으로 만들어 넣고, 검사기가 그것을 실제로 잡는지 본다.
    """
    gated = ("def apply(self, conn):\n"
             "    supplier = _lock_supplier(conn)\n"
             "    require_simulated_tier(supplier)\n"
             "    conn.execute(\"UPDATE supplier_bookings SET status='cancelled'\")\n")
    ungated = ("def apply(self, conn):\n"
               "    supplier = _lock_supplier(conn)\n"
               "    conn.execute(\"UPDATE supplier_bookings SET status='cancelled'\")\n")
    too_late = ("def apply(self, conn):\n"
                "    conn.execute(\"UPDATE supplier_bookings SET status='cancelled'\")\n"
                "    require_simulated_tier(supplier)\n")
    outside = "conn.execute(\"DELETE FROM supplier_bookings WHERE 1=1\")\n"

    assert _ungated_writes(gated, "x.py") == []
    assert len(_ungated_writes(ungated, "x.py")) == 1
    assert "뒤에 있다" in _ungated_writes(too_late, "x.py")[0]
    assert "함수 밖" in _ungated_writes(outside, "x.py")[0]


# invariant: DoD-15
def test_the_gate_opens_only_for_the_simulated_tier():
    """★`simulated` 가 **아닌 모든 것**을 막는다 — `real` 만 막는 게 아니다.

    모름(`None`)·빈 값·오타가 통과하면 등급을 못 읽은 행이 자동 실행 대상이 된다.
    """
    require_simulated_tier({"tier": SIMULATED_TIER})          # 이것만 열린다
    for tier in ("real", None, "", "Simulated", "simulate", "mock", "SIMULATED"):
        with pytest.raises(ActionRejected):
            require_simulated_tier({"tier": tier})
    with pytest.raises(ActionRejected):
        require_simulated_tier({})                            # 등급 칸을 아예 안 읽었다


# invariant: DoD-14
def test_no_booking_handler_applies_without_human_approval():
    """★DoD-14 의 앞쪽 — 실제 공급자든 아니든 예약 적용기는 **승인 경로로만** 온다.

    `auto_apply=True` 가 되면 코어가 승인 없이 적용하므로, 등급 게이트만으로는
    「승인 없이 Mock 을 자동 실행」이 열린다. 두 문을 같이 잠근다.
    """
    opened = [handler.action_type for handler in APPROVED_HANDLERS if handler.auto_apply]
    assert not opened, f"승인 없이 적용되는 예약 적용기가 있다: {opened} (v11 §4-C)"


# invariant: DoD-14
def test_the_tier_column_defaults_to_the_real_supplier():
    """★기본값이 안전한 쪽이어야 한다 — 등급을 잊은 행은 **실제 공급자**로 취급된다.

    마이그레이션 017 을 문서가 아니라 파일에 대고 센다(DB 실측은 행동 시험이 본다).
    """
    sql = Path("app/infrastructure/db/migrations/017_supplier_tier.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS tier text NOT NULL DEFAULT 'real'" in sql, \
        "tier 기본값이 'real' 이 아니다 — 잊음의 대가가 돈인 쪽으로 기울면 안 된다"
    assert "CHECK (tier IN ('real', 'simulated'))" in sql, "등급 값을 DB 가 안 지킨다"


def test_the_exception_list_stays_small():
    """★예외가 늘면 경계가 무너지는 중이다.

    ★`[2026-09-22]` 상한을 2 → 3 으로 올렸다(DoD-18 측정 하네스). 숫자만 올리지 않고
      **예외가 무엇을 해도 되는지**를 함께 못박는다 — 예외 파일은 원장 행을 만들고
      지울 수 있을 뿐 **남의 행을 바꾸지 못한다**(`UPDATE supplier_bookings` 금지).
      자동 실행이 바꾸는 것은 언제나 이미 있는 행이므로, UPDATE 를 예외에서 빼면
      「자동 실행이 예외 파일로 새는」 길이 닫힌다.
    """
    assert len(SEEDING_FILES) <= 3, f"예외가 {len(SEEDING_FILES)}개다: {sorted(SEEDING_FILES)}"
    stale = sorted(path for path in SEEDING_FILES if not Path(path).exists())
    assert not stale, f"없는 파일을 가리키는 예외다: {stale}"
    updating = sorted(path for path in SEEDING_FILES
                      if re.search(r"\bUPDATE\s+supplier_bookings", Path(path).read_text(encoding="utf-8"),
                                   re.IGNORECASE))
    assert not updating, ("예외 파일이 공급자 원장을 **바꾼다**(UPDATE) — 예외는 행을 만들고 "
                          f"지우는 자리까지다: {updating}")
