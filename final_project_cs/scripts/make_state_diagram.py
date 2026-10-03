# -*- coding: utf-8 -*-
"""Case 상태 전이도를 **코드에서** 뽑는다.

    python -m scripts.make_state_diagram          # 파일을 다시 쓴다
    python -m scripts.make_state_diagram --check  # 어긋나면 1 로 끝난다(관문용)

★손으로 그린 그림은 코드가 바뀌는 순간 거짓말이 된다. 실제로 이 저장소는
  2026-09-10 에 「Top-Level LangGraph 가 흐름을 정한다」는 설계 문장을 다섯 군데에서
  고쳐야 했다 — 그림과 글이 코드를 앞질러 적혀 있었기 때문이다.

★유일한 출처는 `app/domain/events.py:TRANSITIONS` 다. 이 스크립트는 그 표를 읽어
  옮겨 적기만 한다. 전이 규칙을 여기서 다시 쓰지 않는다.

★출력은 Mermaid 다. GitHub 이 마크다운 안에서 그대로 그려 주고, 글자라서 검색도
  되고 차이도 보인다. 그림 파일로 두면 바뀐 자리를 리뷰에서 볼 수 없다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.core.contracts import CaseStatus  # noqa: E402
from app.domain.events import TERMINAL_STATUSES, TRANSITIONS  # noqa: E402

OUT = REPO_ROOT / "wiki" / "runtime" / "case-state-machine.generated.md"

#: 시작 상태. 들어오는 전이가 없는 상태를 기계로 찾는다 — 박아 두면 그것도 낡는다.
def _entry_states() -> list[CaseStatus]:
    incoming = {nxt for nxt in TRANSITIONS.values()}
    return [s for s in CaseStatus if s not in incoming]


def _rows() -> list[tuple[str, str, str]]:
    """(현재, 다음, 이벤트) 를 상태 선언 순서대로. 순서가 흔들리면 관문이 헛걸린다."""
    order = {s: i for i, s in enumerate(CaseStatus)}
    rows = [(cur.value, nxt.value, evt.value)
            for (cur, evt), nxt in TRANSITIONS.items()]
    return sorted(rows, key=lambda r: (order[CaseStatus(r[0])], r[2]))


def mermaid() -> str:
    lines = ["stateDiagram-v2"]
    for state in _entry_states():
        lines.append("    [*] --> %s" % state.value)
    for cur, nxt, evt in _rows():
        lines.append("    %s --> %s: %s" % (cur, nxt, evt))
    for state in sorted(TERMINAL_STATUSES, key=lambda s: s.value):
        lines.append("    %s --> [*]" % state.value)
    return "\n".join(lines)


def table() -> str:
    """상태마다 「여기서 어디로 갈 수 있나」. 그림이 안 그려지는 자리에서도 읽힌다."""
    by_state: dict[str, list[tuple[str, str]]] = {}
    for cur, nxt, evt in _rows():
        by_state.setdefault(cur, []).append((evt, nxt))
    out = ["| 상태 | 이벤트 | 다음 상태 |", "|---|---|---|"]
    for state in CaseStatus:
        moves = by_state.get(state.value)
        if not moves:
            out.append("| `%s` | 없음 | 끝 |" % state.value)
            continue
        for i, (evt, nxt) in enumerate(moves):
            out.append("| %s | `%s` | `%s` |"
                       % ("`%s`" % state.value if i == 0 else "", evt, nxt))
    return "\n".join(out)


def render() -> str:
    return "\n".join([
        "<!-- 이 파일은 `python -m scripts.make_state_diagram` 이 만든다. 손으로 고치지 않는다. -->",
        "<!-- 출처: app/domain/events.py:TRANSITIONS -->",
        "",
        "# Case 상태 전이도 (자동 생성)",
        "",
        "상태 %d개 · 전이 %d개. 이 표에 없는 전이는 `transition_case()` 가 거부한다."
        % (len(CaseStatus), len(TRANSITIONS)),
        "",
        "```mermaid",
        mermaid(),
        "```",
        "",
        "## 전이표",
        "",
        table(),
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="다시 만들어 보고 지금 파일과 다르면 1 로 끝난다")
    args = parser.parse_args()

    want = render()
    if args.check:
        have = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if have == want:
            print("전이도가 코드와 같다: %s" % OUT.relative_to(REPO_ROOT))
            return 0
        print("전이도가 코드와 어긋났다. `python -m scripts.make_state_diagram` 로 다시 만든다.\n"
              "  파일: %s" % OUT.relative_to(REPO_ROOT), file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(want, encoding="utf-8", newline="\n")
    print("만듦: %s · 상태 %d · 전이 %d"
          % (OUT.relative_to(REPO_ROOT), len(CaseStatus), len(TRANSITIONS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
