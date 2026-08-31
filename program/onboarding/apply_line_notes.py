# -*- coding: utf-8 -*-
"""줄 주석 JSON 을 검사해서 `line_notes.py` 로 만든다.

    python program/onboarding/apply_line_notes.py <받은.json>

주석 본문은 코덱스가 쓰고 여기서 받는다. 그대로 믿지 않는다.
아래를 하나라도 어기면 그 항목을 통째로 물리고 무엇이 틀렸는지 적는다.

  - 원본에 없는 id 를 만들었나
  - 줄 수가 원본과 다른가        (하나만 밀려도 3번 줄 설명이 4번 줄에 붙는다)
  - 빈 줄에 설명을 달았나        (빈 줄에는 설명할 것이 없다)
  - 내용이 있는 줄을 통째로 비웠나
  - 너무 긴가                    (말풍선이 화면을 덮는다)
  - 금지 글자를 썼나
  - 한 덩어리 안에서 같은 말을 베꼈나
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from trace_data import STEPS  # noqa: E402

OUT = os.path.join(HERE, "line_notes.py")
BANNED = re.compile("[—–→⇒★☆✓✔✕▸…]")
LIMIT = 46          # 말풍선 한 줄 길이. 넘으면 화면을 덮는다.

HEAD = '''# -*- coding: utf-8 -*-
"""코드 한 줄마다 붙는 짧은 설명.

    NOTES["pack-3-0"][2]   3번 단계 첫째 덩어리의 셋째 줄 설명

★키의 순서와 줄 수가 원본과 정확히 맞아야 한다. 하나만 밀려도 3번 줄
  설명이 4번 줄에 붙는다. 그건 설명이 없는 것보다 나쁘다.
  `build_trace_html.notes_for()` 가 줄 수를 다시 대조하고 어긋나면 멈춘다.

★이 파일은 `apply_line_notes.py` 가 만든다. 손으로 고쳐도 되지만
  줄을 늘리거나 줄이면 원본과 짝이 깨진다.
"""

NOTES = {
'''


def sources():
    """원본 줄. {id: [줄, ...]}"""
    out = {}
    for s in STEPS:
        for i, (_k, _nm, lines) in enumerate(s["add"]):
            out["pack-%d-%d" % (s["n"], i)] = list(lines)
        for i, c in enumerate(s["code"]):
            out["code-%d-%d" % (s["n"], i)] = c["code"].split("\n")
    return out


def judge(src, items):
    """받은 것을 검사한다. (쓸 것, 물린 것) 을 돌려준다."""
    keep, drop = {}, []
    seen = set()
    for item in items:
        key = item.get("id")
        notes = item.get("notes")
        if key in seen:
            drop.append((key, "같은 id 가 두 번 왔다"))
            continue
        seen.add(key)
        lines = src.get(key)
        if lines is None:
            drop.append((key, "원본에 없는 id"))
            continue
        if not isinstance(notes, list) or len(notes) != len(lines):
            drop.append((key, "줄 수가 다르다: 주석 %s, 원본 %d"
                         % (len(notes) if isinstance(notes, list) else "?", len(lines))))
            continue
        bad = []
        for i, (line, note) in enumerate(zip(lines, notes)):
            note = (note or "").strip()
            if not line.strip():
                if note:
                    bad.append("%d번째: 빈 줄에 설명을 달았다" % (i + 1))
                continue
            if not note:
                continue                       # 설명할 것이 없는 줄은 비워도 된다
            if len(note) > LIMIT:
                bad.append("%d번째: %d자로 너무 길다" % (i + 1, len(note)))
            if BANNED.search(note):
                bad.append("%d번째: 금지 글자 %s" % (i + 1, BANNED.search(note).group()))
        filled = [n.strip() for n in notes if n and n.strip()]
        if len(filled) != len(set(filled)) and len(filled) > 2:
            bad.append("같은 설명을 여러 줄에 베꼈다")
        if not filled:
            drop.append((key, "설명이 하나도 없다"))
            continue
        if bad:
            drop.append((key, " / ".join(bad)))
            continue
        keep[key] = ["" if not ln.strip() else (nt or "").strip()
                     for ln, nt in zip(lines, notes)]
    for key in src:
        if key not in seen:
            drop.append((key, "안 왔다"))
    return keep, drop


def main(path):
    got = json.loads(io.open(path, encoding="utf-8").read())
    items = got["items"] if isinstance(got, dict) else got
    src = sources()
    keep, drop = judge(src, items)

    print("원본 %d덩어리 · 받음 %d · 통과 %d · 물림 %d"
          % (len(src), len(items), len(keep), len(drop)))
    for key, why in drop:
        print("  물림 %-12s %s" % (key, why))

    body = []
    for key in src:                              # 원본 순서를 지킨다
        if key not in keep:
            continue
        body.append('    "%s": [' % key)
        for note in keep[key]:
            body.append('        %s,' % json.dumps(note, ensure_ascii=False))
        body.append('    ],')
    tmp = OUT + ".part"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HEAD + "\n".join(body) + "\n}\n")
    os.replace(tmp, OUT)

    lines = sum(len(v) for v in keep.values())
    filled = sum(1 for v in keep.values() for n in v if n)
    print("만듦: %s  (덩어리 %d · 줄 %d · 설명 붙은 줄 %d)"
          % (OUT, len(keep), lines, filled))
    return 0 if not drop else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("쓰기: python apply_line_notes.py <받은.json>")
    raise SystemExit(main(sys.argv[1]))
