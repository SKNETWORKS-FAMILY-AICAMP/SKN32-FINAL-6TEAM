# -*- coding: utf-8 -*-
"""열두 낱장의 내용을 그림 코드에서 그대로 가져온다.

★내용을 옮겨 적지 않는다. `trace/steps.py` 가 유일한 출처다.
  그림을 그리는 `draw.step()` 을 가로채서 넘어오는 값을 그대로 받는다.
  그래서 그림과 화면이 어긋날 수 없다. steps.py 를 고치면 둘 다 바뀐다.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "trace"))

import draw  # noqa: E402

_SHEETS = []


def _collect(n, head, color, coord_rows, in_label, in_lines, action,
             out_label, out_lines, states, code, why, mark=()):
    _SHEETS.append({
        "n": n, "head": head, "color": color,
        "coord": [(label, list(value)) for label, value in coord_rows],
        "in_label": in_label, "in_lines": list(in_lines),
        "action": list(action),
        "out_label": out_label, "out_lines": list(out_lines),
        "mark": sorted(mark),
        "states": [[t, c] for t, c in states],
        "code": code, "why": why,
    })


draw.step = _collect

import steps  # noqa: E402

steps.build_steps()

#: 진행바 열두 칸. 그림 위쪽에 그리는 것과 같은 것을 쓴다.
BAR = [{"name": name, "color": color} for name, color in draw.STEPS]

#: 낱장 열두 개. steps.py 순서 그대로다.
SHEETS = _SHEETS

if len(SHEETS) != 12 or len(BAR) != 12:
    raise SystemExit("낱장이 12개가 아니다: 낱장 %d, 진행바 %d" % (len(SHEETS), len(BAR)))
