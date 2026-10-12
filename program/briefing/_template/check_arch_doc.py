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

# ★2026-09-10 정정 — 앞 판은 8·12·16 만 허용해 v1 의 글자 위계(배지 7 · 코드 9)를
#   위반으로 잡았고, 그 규칙을 따른 v2 도해가 v1 보다 퇴화했다. v1 에서 센 값으로 바꾼다.
bad_fs = sorted({v for v in re.findall(r'font-size="(\d+(?:\.\d+)?)"', " ".join(svgs))
                 if v not in ("7", "8", "9", "12", "16")})
if bad_fs:
    fail.append(f"도해 font-size 가 7·8·9·12·16 밖이다: {bad_fs}")

# ★표현 문법 — 위반 수만 세면 디자인이 무너져도 합격이 나온다(2026-09-10 v2 퇴화).
#   v1 처럼 모든 글자·선의 색과 글꼴을 직접(또는 감싼 <g> 로) 정하고, 도해마다 굵은 제목이 있어야 한다.
import xml.etree.ElementTree as _ET
def _style_walk(el, inh, out):
    tag = el.tag.split("}")[-1]
    cur = dict(inh)
    for k in ("fill", "font-family", "stroke", "font-weight"):
        if el.get(k) is not None:
            cur[k] = el.get(k)
    if tag in ("defs", "marker", "title", "desc"):
        return
    if tag == "text":
        out["text"] += 1
        if not cur.get("fill"): out["text_nofill"] += 1
        if not cur.get("font-family"): out["text_nofont"] += 1
        if cur.get("font-weight") in ("600", "700", "bold"): out["bold"] += 1
    if tag in ("path", "line", "polyline"):
        out["line"] += 1
        if not cur.get("stroke") or cur.get("stroke") == "none": out["line_nostroke"] += 1
    for ch in el:
        _style_walk(ch, cur, out)
for i, g in enumerate(svgs, 1):
    try:
        root = _ET.fromstring(g)
    except Exception as e:
        fail.append(f"SVG{i} XML 로 읽을 수 없다: {str(e)[:60]}"); continue
    o = {"text": 0, "text_nofill": 0, "text_nofont": 0, "bold": 0, "line": 0, "line_nostroke": 0}
    _style_walk(root, {}, o)
    if o["text_nofill"]: fail.append(f"SVG{i} 글자 색이 안 정해진 text {o['text_nofill']}/{o['text']}")
    if o["text_nofont"]: fail.append(f"SVG{i} 글꼴이 안 정해진 text {o['text_nofont']}/{o['text']}")
    if o["line_nostroke"]: fail.append(f"SVG{i} 선 색이 안 정해진 선 {o['line_nostroke']}/{o['line']}")
    _bold_total = globals().get("_bold_total", 0) + o["bold"]
    globals()["_bold_total"] = _bold_total
# v1 은 전체 구성도에만 굵은 제목(10곳)을 쓰고 팀 세부 도해는 쓰지 않는다 — 문서 단위로 본다
if svgs and not globals().get("_bold_total", 0):
    fail.append("도해 전체에 굵은 제목(font-weight 600)이 하나도 없다 — v1 의 제목 위계가 빠졌다")

# 역할별 표현이 한 가지로 뭉개졌나 — v1 은 글자 색 5종 · 선 색 5종 · 가운데 정렬 40/46(전체 구성도) · 자간 15곳
def _roles(el, inh, acc):
    tag = el.tag.split("}")[-1]; cur = dict(inh)
    for k in ("fill", "stroke", "text-anchor", "letter-spacing"):
        if el.get(k) is not None: cur[k] = el.get(k)
    if tag in ("defs", "marker", "title", "desc"): return
    if tag == "text":
        acc["tfill"].add(cur.get("fill")); acc["texts"] += 1
        acc["mid"] += cur.get("text-anchor") == "middle"
        acc["ls"] += bool(cur.get("letter-spacing"))
    if tag in ("path", "line", "polyline"): acc["stroke"].add(cur.get("stroke"))
    for ch in el: _roles(ch, cur, acc)
_acc = {"tfill": set(), "stroke": set(), "texts": 0, "mid": 0, "ls": 0}
for g in svgs:
    try: _roles(_ET.fromstring(g), {}, _acc)
    except Exception: pass
if svgs:
    if len(_acc["tfill"] - {None}) < 3:
        fail.append(f"도해 글자 색이 {len(_acc['tfill'] - {None})}종뿐이다 — 제목·설명·코드·강조를 색으로 나누지 않았다(v1 5종)")
    if len(_acc["stroke"] - {None, "none"}) < 3:
        fail.append(f"도해 선 색이 {len(_acc['stroke'] - {None, 'none'})}종뿐이다 — 주 흐름·일반·강조·구분을 나누지 않았다(v1 5종)")
    if _acc["texts"] and _acc["mid"] / _acc["texts"] < 0.15:
        fail.append(f"가운데 정렬 글자 {_acc['mid']}/{_acc['texts']} — 상자 제목을 가운데 두지 않았다(v1 40/183)")
    if not _acc["ls"]:
        fail.append("자간을 준 캡션·배지가 하나도 없다(v1 15곳)")

# 한글 12px 미만 — <text font-size=..> 와 <g font-size=..> 안의 text 둘 다 본다
# ★2026-09-10 정정 — 앞 판은 정규식으로 <g …font-size>…</g> 를 잘라 읽어, <g> 가 겹치면
#   바깥 크기를 안쪽 글자에 붙였다(오탐 4곳). XML 로 읽고 상속을 따라가 글자 조각마다 잰다.
import xml.etree.ElementTree as _ETk
small = []
def _ko_walk(el, fs):
    fs = el.get("font-size", fs)
    tag = el.tag.split("}")[-1]
    if tag in ("text", "tspan"):
        own = (el.text or "")
        if re.search("[가-힣]", own) and fs and float(fs) < 12:
            small.append(own.strip()[:24])
    for ch in el:
        _ko_walk(ch, fs)
        if tag in ("text", "tspan") and ch.tail and re.search("[가-힣]", ch.tail) and fs and float(fs) < 12:
            small.append(ch.tail.strip()[:24])
for g in svgs:
    try:
        _ko_walk(_ETk.fromstring(g), None)
    except Exception:
        pass
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
