"""고객에게 나가는 답변 문장이 한국어인지 소스에서 직접 검사한다.

★`TeamResult.answer` 는 장식이 아니라 **고객이 읽는 문장**이다 —
  `Controller._event_for_result()` 가 `state_json.answer` 로 넣고
  `GET /v1/cases/{case_id}` 가 그대로 돌려준다. 이 제품의 고객은 한국어를
  쓴다.

★2026-09-02 실측: `procurement_order_payment.py` 세 곳이 답변을 영어로
  하드코딩하고 있었고, holdout 24건 중 **6건이 영어 답변**을 받았다
  (`docs/reports/debugs/2026-09-02_한국어_문의에_영어로_답한다.md`).
  문자열만 고치면 다음에 또 생기므로 이 검사를 둔다.

★**소스를 읽어 검사한다.** 실행해서 잡으려면 모든 capability 의 모든 분기에
  fixture 를 만들어야 하는데, 그 fixture 를 빠뜨리는 순간 검사도 같이
  사라진다. `answer=` 리터럴은 AST 로 빠짐없이 셀 수 있다.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

TEAM_DIR = Path(__file__).resolve().parents[3] / "app" / "modules" / "customer_ops"
HANGUL = re.compile(r"[가-힣]")

#: 값을 그대로 끼워 넣는 자리(`{status}` 등)는 영문 토큰일 수 있다. 문장이
#: 한국어인지만 본다 — 상태값 어휘까지 한국어로 옮길지는 도메인 판단이다.
PLACEHOLDER = re.compile(r"\{[^}]*\}")


def _answer_literals(path: Path) -> list[tuple[int, str]]:
    """`answer=` 로 넘기는 문자열 리터럴을 전부 뽑는다 (f-string 포함)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []

    def literal_text(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            # f-string: 리터럴 조각만 잇는다. `{...}` 안은 값이라 언어 검사 대상이 아니다.
            return "".join(part.value for part in node.values
                           if isinstance(part, ast.Constant) and isinstance(part.value, str))
        if isinstance(node, ast.IfExp):
            # `A if cond else B` — 양쪽 다 고객에게 나갈 수 있다.
            return None
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "answer":
                continue
            value = keyword.value
            branches = [value.body, value.orelse] if isinstance(value, ast.IfExp) else [value]
            for branch in branches:
                text = literal_text(branch)
                if text is not None:
                    found.append((getattr(branch, "lineno", node.lineno), text))
    return found


TEAM_FILES = sorted(
    p for p in TEAM_DIR.glob("*.py")
    if p.name not in {"__init__.py"} and not p.name.endswith("_policy.py")
)


# invariant 성격 — 팀이 늘어나도 자동으로 포함된다.
@pytest.mark.parametrize("path", TEAM_FILES, ids=lambda p: p.name)
def test_customer_facing_answers_are_written_in_korean(path: Path):
    offenders = []
    for lineno, text in _answer_literals(path):
        stripped = PLACEHOLDER.sub("", text).strip()
        if not stripped:
            continue  # 값만 끼워 넣는 자리 — 검사할 문장이 없다
        if not HANGUL.search(stripped):
            offenders.append(f"{path.name}:{lineno}  {text[:70]!r}")

    assert not offenders, (
        "고객에게 나가는 answer 가 한국어가 아니다. 이 문장은 그대로 고객이 읽는다:\n  "
        + "\n  ".join(offenders))


def test_the_check_actually_finds_answer_literals():
    """★검사가 아무것도 못 찾으면 위 테스트는 언제나 통과한다 — 빈 검사 방지."""
    total = sum(len(_answer_literals(path)) for path in TEAM_FILES)
    assert total >= 5, f"answer 리터럴을 {total}개밖에 못 찾았다 — AST 추출이 깨졌는지 확인한다"
