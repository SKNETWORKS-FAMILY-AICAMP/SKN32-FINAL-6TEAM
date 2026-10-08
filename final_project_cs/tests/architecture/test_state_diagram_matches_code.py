# -*- coding: utf-8 -*-
"""★전이도가 코드와 어긋나면 여기서 막는다.

손으로 그린 그림은 코드가 바뀌는 순간 거짓말이 된다. 이 저장소에서 실제로 났다 —
2026-09-10 에 「Top-Level LangGraph 가 흐름을 정한다」는 설계 문장을 다섯 군데에서
고쳐야 했다. 그림과 글이 코드를 앞질러 적혀 있었고, **아무도 울지 않았기 때문에**
한 달 가까이 그대로였다.

검사하지 않는 규칙은 지켜지지 않는다(`test_basement_is_domain_free.py` 와 같은 이유).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.make_state_diagram import OUT, render  # noqa: E402


# invariant: INV-CS-ARCH-007
def test_state_diagram_is_regenerated_from_the_code():
    """★그림은 `app/core/case_lifecycle/events.py:TRANSITIONS` 에서만 나온다."""
    assert OUT.exists(), (
        "전이도 파일이 없다. `python -m scripts.make_state_diagram` 로 만든다:\n  %s"
        % OUT)
    assert OUT.read_text(encoding="utf-8") == render(), (
        "전이도가 코드와 어긋났다. 손으로 고치지 말고 다시 만든다:\n"
        "  python -m scripts.make_state_diagram\n  파일: %s" % OUT)


def test_the_generator_covers_every_state():
    """★반대 방향도 본다. 상태를 더했는데 그림에 안 나오면 이 검사가 헛돈다."""
    from app.core.contracts import CaseStatus

    text = render()
    missing = [s.value for s in CaseStatus if s.value not in text]
    assert not missing, "전이도에 안 나오는 상태가 있다: %s" % ", ".join(missing)
