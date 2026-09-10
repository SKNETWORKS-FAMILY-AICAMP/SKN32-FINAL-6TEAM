# -*- coding: utf-8 -*-
"""아키텍처 문서 관문 — 붙이기 전에 반드시 통과시킨다.

v1 의 check_fragment.py 를 잇고, v2 를 만들다 실제로 터진 것을 더했다
(아키텍처문서_템플릿.md §3 규칙 11~13, §4).

    python program/briefing/_template/check_arch_doc.py <문서.html>

★글자가 상자를 넘는지는 여기서 못 잰다 — 폰트 폭이 필요하다.
  그건 check_text_fit.js 를 브라우저에서 돌린다.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]          # final_workspace
CODE = ROOT / "final_project_cs"

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
fail, warn = [], []

# ── 1. 외부 의존 ────────────────────────────────────────────────────
if "<script" in s.lower():
    fail.append("<script> 가 있다")
for m in re.finditer(r'<(?:img|image)\b[^>]*(?:src|href)\s*=\s*["\']https?://', s):
    fail.append("외부 이미지를 부른다")

# ── 2. 도해 규칙 ────────────────────────────────────────────────────
svgs = re.findall(r"<svg\b.*?</svg>", s, re.S)
ids = []
for i, g in enumerate(svgs, 1):
    head = g[: g.find(">") + 1]
    if 'role="img"' not in head:
        fail.append(f"svg#{i}: role=img 없음")
    if "aria-labelledby" not in head:
        fail.append(f"svg#{i}: aria-labelledby 없음")
    if not g[g.find(">") + 1:].lstrip().startswith("<title"):
        fail.append(f"svg#{i}: <title> 이 첫 자식이 아니다")
    if "<desc" not in g:
        fail.append(f"svg#{i}: <desc> 없음")
    ids += re.findall(r'<(?:title|desc)\s+id="([^"]+)"', g)
    n_acc = len(re.findall(r'(?:stroke|fill)="#a8720c"', g))
    if n_acc > 6:
        warn.append(f"svg#{i}: accent {n_acc}곳 — 도해당 2노드 원칙 확인")
    for m in re.finditer(r'<line\b[^>]*?x1="([\d.]+)"[^>]*?y1="([\d.]+)"[^>]*?x2="([\d.]+)"[^>]*?y2="([\d.]+)"', g):
        x1, y1, x2, y2 = map(float, m.groups())
        if x1 != x2 and y1 != y2:
            fail.append(f"svg#{i}: 대각선 <line> ({x1:g},{y1:g})→({x2:g},{y2:g})")
dup = sorted({x for x in ids if ids.count(x) > 1})
if dup:
    fail.append(f"title/desc id 중복: {dup}")

grid = [m.group(0)[:60] for m in re.finditer(
    r'<rect\b[^>]*?x="(\d+)"[^>]*?y="(\d+)"[^>]*?width="(\d+)"[^>]*?height="(\d+)"', s)
    if any(int(v) % 4 for v in m.groups())]
if grid:
    fail.append(f"4px 격자 위반 {len(grid)}곳 — 예: {grid[0]}")

bad_fs = sorted({v for v in re.findall(r'font-size="(\d+(?:\.\d+)?)"', " ".join(svgs))
                 if v not in ("8", "12", "16")})
if bad_fs:
    fail.append(f"도해 font-size 가 8·12·16 밖이다: {bad_fs}")

# 한글 12px 미만 — <text font-size=..> 와 <g font-size=..> 안의 text 둘 다 본다
small = []
for g in svgs:
    for gm in re.finditer(r'<g\b[^>]*font-size="(\d+)"[^>]*>(.*?)</g>', g, re.S):
        if int(gm.group(1)) < 12:
            for tm in re.finditer(r"<text\b[^>]*>([^<]*)</text>", gm.group(2)):
                if re.search("[가-힣]", tm.group(1)):
                    small.append(tm.group(1)[:24])
    for tm in re.finditer(r'<text\b[^>]*font-size="(\d+)"[^>]*>([^<]*)</text>', g):
        if int(tm.group(1)) < 12 and re.search("[가-힣]", tm.group(2)):
            small.append(tm.group(2)[:24])
if small:
    fail.append(f"12px 미만 한글 {len(small)}곳 — 예: {small[0]}")

# ── 3. 문자 — 한국어와 영어만 ──────────────────────────────────────
kana = re.findall(r"[぀-ヿ]", s)
han = re.findall(r"[一-鿿]", s)
if kana:
    fail.append(f"가나 {len(kana)}자")
if han:
    fail.append(f"한자 {len(han)}자")

# ── 4. 작업 메모가 본문에 샜나 ─────────────────────────────────────
for phrase in ("제공 원문", "과제에 명시된", "원문에서 확인할 수 없어", "TODO", "FIXME"):
    if phrase in s:
        fail.append(f"작업 메모가 본문에 있다: 「{phrase}」")

# ── 5. 코드에 없는 것을 지어냈나 ───────────────────────────────────
for k in ("read.hotel", "read.flight_api", "activity.book", "dining.reserve"):
    if k in s:
        fail.append(f"코드에 없는 것을 지어냈다: {k}")

# ── 6. 코드 인용 전수 대조 ─────────────────────────────────────────
index = {}
for f in CODE.rglob("*.py"):
    if "__pycache__" in f.parts or ".venv" in f.parts:
        continue
    index.setdefault(f.name, []).append(f)
cites = 0
for m in re.finditer(r"\b([A-Za-z_][\w]*\.py):(\d+)(?:~(\d+))?", s):
    name, a, b = m.group(1), int(m.group(2)), m.group(3)
    hi = int(b) if b else a
    cites += 1
    cands = index.get(name)
    if not cands:
        warn.append(f"인용한 파일을 저장소에서 못 찾았다: {m.group(0)}")
        continue
    if len(cands) > 1:
        cands = [c for c in cands if "travel_ops" in c.parts or "application" in c.parts
                 or "core" in c.parts or "tools" in c.parts or c.parent.name == "app"] or cands
    n = len(cands[0].read_text(encoding="utf-8").splitlines())
    if hi > n or (b and int(b) < a):
        fail.append(f"인용 범위 밖: {m.group(0)} (파일 {n}줄)")

# ── 7. 장 번호 ────────────────────────────────────────────────────
nums = [int(x) for x in re.findall(r'<span class="n">(\d+)</span>', s)]
if nums and nums != list(range(nums[0], nums[0] + len(nums))):
    fail.append(f"장 번호가 이어지지 않는다: {nums}")

# ── 보고 ──────────────────────────────────────────────────────────
print(f"문서 {p.name} · {len(s.encode()):,}B · SVG {len(svgs)}장 · 코드 인용 {cites}건")
if fail:
    print(f"\n★불합격 {len(fail)}건")
    for f in fail:
        print("   ✗", f)
else:
    print("\n합격 — 규칙 위반 0")
if warn:
    print(f"\n확인 필요 {len(warn)}건")
    for w in warn:
        print("   ·", w)
print("\n★글자 넘침·겹침·선통과는 check_text_fit.js 로 브라우저에서 잰다.")
sys.exit(1 if fail else 0)
