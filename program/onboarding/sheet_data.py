# -*- coding: utf-8 -*-
"""열두 낱장의 내용을 그림 코드에서 그대로 가져온다.

★내용을 옮겨 적지 않는다. `trace/steps.py` 가 유일한 출처다.
  그림을 그리는 `step()` 자리에 수집 함수를 끼워 넣고 `build_steps()` 를 돌려
  넘어오는 값을 그대로 받는다. 그래서 그림과 화면이 어긋날 수 없다.

★전역 `draw.step` 을 바꿔치기하지 않는다. 처음엔 그렇게 했는데 결함이 있었다.
  `make_trace_images.py` 처럼 `steps` 를 먼저 import 한 프로세스에서는
  `sys.modules` 에 캐시된 옛 모듈이 그대로 쓰여 수집이 한 건도 안 되고,
  그 와중에 PNG 열두 장을 조용히 다시 그려 놓고 나서야 실패했다. 반대로
  이쪽이 먼저 돌면 이후의 그림 생성이 수집으로 바뀐다. import 순서에 따라
  동작이 달라지는 것은 고칠 수 있는 결함이지 감수할 일이 아니다.

  그래서 `draw` 와 `steps` 를 이 파일 전용 이름으로 따로 읽는다.
  진짜 모듈은 건드리지 않고, 끝나면 `sys.modules` 와 `sys.path` 를 되돌린다.
  누가 먼저 import 하든 결과가 같다.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRACE = os.path.join(HERE, "trace")

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


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _read():
    """`steps.py` 를 이 파일 전용으로 한 번 읽어 낱장과 진행바를 받는다."""
    saved_path = list(sys.path)
    saved_mods = {k: sys.modules.get(k) for k in ("draw", "steps")}
    try:
        sys.path.insert(0, TRACE)
        # steps.py 는 `from draw import ... step` 을 한다. 그 draw 가
        # 우리 사본이어야 하므로 잠시 sys.modules 에 얹었다가 되돌린다.
        draw = _load("draw", os.path.join(TRACE, "draw.py"))
        draw.step = _collect
        steps = _load("steps", os.path.join(TRACE, "steps.py"))
        steps.build_steps()
        return list(_SHEETS), [{"name": nm, "color": c} for nm, c in draw.STEPS]
    finally:
        sys.path[:] = saved_path
        for k, v in saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


#: 낱장 열두 개(steps.py 순서 그대로)와 진행바 열두 칸.
SHEETS, BAR = _read()

if len(SHEETS) != 12 or len(BAR) != 12:
    raise SystemExit("낱장이 12개가 아니다: 낱장 %d, 진행바 %d" % (len(SHEETS), len(BAR)))
