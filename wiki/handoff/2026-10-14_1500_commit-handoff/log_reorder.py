"""log.md 의 날짜 항목을 최신순으로 다시 늘어놓는다. 글은 바꾸지 않고 위치만 옮긴다.

- 첫 「## 」 앞(머리말·제목)은 그대로 맨 앞.
- 「## YYYY-MM-DD…」 로 시작하는 항목: 날짜 내림차순, 같은 날짜는 원래 순서(안정 정렬).
- 날짜 없는 절(과거 변경 기록·관계·이관 예정 등)은 원래 순서대로 맨 뒤.
- 바꾼 뒤 줄 묶음(빈 줄 제외)이 전과 같은지 대조한다.
"""
import collections
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\playdata2\Documents\final_workspace")
STAMP = "2026-10-14_1040_log_date_order"

for rel in sys.argv[1:]:
    p = ROOT / rel
    raw = p.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    lines = text.split("\n")
    head, blocks, cur = [], [], None
    for line in lines:
        if line.startswith("## "):
            cur = [line]
            blocks.append(cur)
        elif cur is None:
            head.append(line)
        else:
            cur.append(line)
    dated, other = [], []
    for i, b in enumerate(blocks):
        m = re.match(r"^## (\d{4}-\d{2}-\d{2})", b[0])
        (dated if m else other).append((m.group(1) if m else "", i, b))
    dated.sort(key=lambda x: (x[0], -x[1]), reverse=True)

    def norm(b):
        while b and b[-1].strip() == "":
            b = b[:-1]
        return b + [""]

    out = [l for l in head]
    while out and out[-1].strip() == "":
        out.pop()
    out.append("")
    for _, _, b in dated + other:
        out.extend(norm(list(b)))
    new = "\n".join(out).rstrip("\n") + "\n"
    before = collections.Counter(l for l in lines if l.strip())
    after = collections.Counter(l for l in new.split("\n") if l.strip())
    assert before == after, f"{rel}: 줄 묶음이 달라졌다"
    bk = p.parent / "_backup" / STAMP
    bk.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, bk / p.name)
    p.write_bytes(new.replace("\n", nl).encode("utf-8"))
    heads = [re.match(r"^## (\d{4}-\d{2}-\d{2})", l).group(1) for l in new.split("\n") if re.match(r"^## \d{4}-\d{2}-\d{2}", l)]
    bad = sum(1 for a, b in zip(heads, heads[1:]) if a < b)
    print(rel, "항목", len(dated), "날짜 없는 절", len(other), "어긋남", bad, "백업", bk.relative_to(ROOT))
