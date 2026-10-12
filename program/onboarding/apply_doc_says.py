# -*- coding: utf-8 -*-
"""문서 칸 설명 JSON 을 검사해서 `doc_says.py` 로 만든다.

    python program/onboarding/apply_doc_says.py <받은.json>

낱장 가운데의 두 칸(들어온 문서, 나간 문서)마다 그 칸이 무엇인지 설명한다.
본문은 코덱스가 쓰고 여기서 받는다. 그대로 믿지 않는다.

  - 원본에 없는 id 를 만들었나 / 안 왔나
  - 너무 짧거나 너무 긴가
  - 금지 글자를 썼나
  - 줄을 하나씩 다시 읽어 준 것에 불과한가 (줄별 설명은 따로 있다)
  - 24개가 서로 다른 말인가
"""
import collections
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sheet_data import SHEETS  # noqa: E402

OUT = os.path.join(HERE, "doc_says.py")
BANNED = re.compile("[—–→⇒★☆✓✔✕▸…]")
LO, HI = 80, 260

HEAD = '''# -*- coding: utf-8 -*-
"""낱장 가운데 두 칸이 각각 무엇인지, 비전공자가 읽는 설명.

    SAYS["in-3"]    3번 단계에 들어온 문서 칸 설명
    SAYS["out-3"]   3번 단계가 내놓은 문서 칸 설명

★줄별 설명(line_notes.py)과 역할이 다르다. 저쪽은 줄 하나, 이쪽은 칸 전체다.
  칸 전체가 무엇이고 왜 이렇게 생겼는지를 말한다.

★이 파일은 `apply_doc_says.py` 가 만든다.
"""

SAYS = {
'''


def main(path):
    got = json.loads(io.open(path, encoding="utf-8").read())
    items = got["items"] if isinstance(got, dict) else got
    want = set()
    for s in SHEETS:
        want |= {"in-%d" % s["n"], "out-%d" % s["n"]}

    keep, drop, seen = {}, [], set()
    for item in items:
        key, text = item.get("id"), (item.get("text") or "").strip()
        if key in seen:
            drop.append((key, "두 번 왔다"))
            continue
        seen.add(key)
        if key not in want:
            drop.append((key, "원본에 없는 id"))
            continue
        if not (LO <= len(text) <= HI):
            drop.append((key, "%d자다. %d~%d자여야 한다" % (len(text), LO, HI)))
            continue
        hit = BANNED.search(text)
        if hit:
            drop.append((key, "금지 글자 %s" % hit.group()))
            continue
        keep[key] = text
    for key in sorted(want - seen):
        drop.append((key, "안 왔다"))

    same = [k for k, v in keep.items() if list(keep.values()).count(v) > 1]
    for key in same:
        drop.append((key, "다른 칸과 같은 글이다"))
        keep.pop(key, None)

    # ★똑같은 글만 막으면 부족하다. 처음 받은 것은 24개 중 23개가
    #   "...게 생겼습니다" 로 끝났다. 글자는 다르지만 틀을 베낀 것이고,
    #   스물넷을 이어 읽으면 같은 소리로 들린다. 어미가 몰리면 물린다.
    tails = collections.Counter(v[-7:] for v in keep.values())
    for tail, n in tails.items():
        if n > len(keep) // 3:
            for key in [k for k, v in keep.items() if v.endswith(tail)]:
                drop.append((key, "끝맺음 '%s' 이 %d칸에서 반복된다" % (tail, n)))
                keep.pop(key, None)

    print("칸 %d개 · 받음 %d · 통과 %d · 물림 %d"
          % (len(want), len(items), len(keep), len(drop)))
    for key, why in drop:
        print("  물림 %-8s %s" % (key, why))

    body = []
    for s in SHEETS:
        for side in ("in", "out"):
            key = "%s-%d" % (side, s["n"])
            if key in keep:
                body.append('    "%s":\n        %s,'
                            % (key, json.dumps(keep[key], ensure_ascii=False)))
    tmp = OUT + ".part"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HEAD + "\n".join(body) + "\n}\n")
    os.replace(tmp, OUT)
    print("만듦: %s  (칸 %d개 · 평균 %d자)"
          % (OUT, len(keep), sum(len(v) for v in keep.values()) // max(len(keep), 1)))
    return 0 if not drop else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("쓰기: python apply_doc_says.py <받은.json>")
    raise SystemExit(main(sys.argv[1]))
