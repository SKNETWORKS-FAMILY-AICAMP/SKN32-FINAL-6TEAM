# -*- coding: utf-8 -*-
"""기능별 워크플로 그림 — 흐름 명세(YAML)를 v26 「아키텍처 한눈에」와 같은 모양의 SVG 로 그린다 (2026-10-07)

- 자리 잡기 · 직각 연결선: 공식 Graphviz(dot, splines=ortho) 에 맡긴다
- 그리기: v26 의 그림판(../../아키텍처_한눈에/v26/src/dd.py) — 색 · 글꼴 · 범례 · 상자 종류가 v26 과 같다
- 상자 종류는 v26 범례를 따른다: 시작 · 끝 · 기다림 · 오류로 끝남 · 코드 · 담당 에이전트 · 공용 도구 · 언어 모델이 돕는 자리 · 고객 · 코드의 판단 · 반복
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "아키텍처_한눈에" / "v26" / "src"))
from dd import Fig, tw, up4  # noqa: E402

GV = r"C:\Program Files\Graphviz\bin"
if os.path.isdir(GV):
    os.environ["PATH"] = GV + os.pathsep + os.environ["PATH"]

PAUSE = "⏸"
TAG_KIND = {"코드": "backend", "에이전트": "worker", "공용 도구": "tool", "언어 모델": "ai_call",
            "고객": "input", "개인 AI": "input", "사람(운영)": "input", "외부 정보": "external"}
TAG_LABEL = {"코드": "[코드]", "에이전트": "[에이전트]", "공용 도구": "[공용 도구]", "언어 모델": "[언어 모델]",
             "고객": PAUSE + " 고객", "개인 AI": "[개인 AI]", "사람(운영)": "[운영]", "외부 정보": "[외부 정보]"}
OVAL = {"start": "timer", "end": "external", "wait": "optional", "error": "stop"}
LEGEND = [("oval:timer", "시작"), ("oval:external", "끝"), ("oval:optional", "기다림"), ("oval:stop", "오류로 끝남"),
          ("backend", "코드"), ("worker", "담당 에이전트"), ("tool", "공용 도구"), ("ai_call", "언어 모델이 돕는 자리"),
          ("input", "고객 · 개인 AI"), ("diamond", "코드의 판단"), ("line:accent", "반복")]


def g4(v):
    return int(round(v / 4.0)) * 4


def _title(n):
    t = n["title"]
    if n["kind"] in ("step",) and n.get("tag") in TAG_LABEL and not t.endswith("]"):
        t = f'{t} {TAG_LABEL[n["tag"]]}'
    if n["kind"] == "start" and not t.startswith("시작"):
        t = "시작 — " + t
    if n["kind"] == "end" and not t.startswith("끝"):
        t = "끝 — " + t
    if n["kind"] == "error" and not t.startswith("오류"):
        t = "오류 — " + t
    if n["kind"] == "wait" and not t.startswith(PAUSE):
        t = PAUSE + " " + t
    return t


def _size(n):
    lines = list(n.get("lines") or [])
    if n["kind"] == "decision":
        w = g4(max(176, tw(n["title"], 12) * 1.9 + 40))
        return w, 80
    title = _title(n)
    wid = max([tw(title, 12)] + [tw(x, 12) for x in lines]) + (48 if n["kind"] in OVAL else 32)
    w = g4(max(200, min(wid, 420)))
    h = g4(32 + 18 * len(lines) + (16 if lines else 8)) if n["kind"] not in OVAL else g4(40 + 18 * len(lines))
    return w, max(h, 52)


def normalize(spec):
    """그림으로 읽히게 정리한다 — 같은 두 상자 사이의 선은 하나로(이름표를 · 로 잇는다), 제자리로 도는 선은 상자 안 한 줄로."""
    nodes = {n["id"]: n for n in spec["nodes"]}
    merged, order = {}, []
    for e in spec["edges"]:
        if e["from"] == e["to"]:
            n = nodes[e["from"]]
            note = f'↻ {e.get("label") or "반복"}'
            n["lines"] = list(n.get("lines") or [])[:2] + [note]
            continue
        key = (e["from"], e["to"])
        if key not in merged:
            merged[key] = dict(e, labels=[])
            order.append(key)
        lab = (e.get("label") or "").strip()
        if lab and lab not in merged[key]["labels"]:
            merged[key]["labels"].append(lab)
        merged[key]["loop"] = merged[key].get("loop") or e.get("loop")
    edges = []
    for key in order:
        e = merged[key]
        labs = e.pop("labels")
        e["label"] = labs[0] if len(labs) == 1 else (" · ".join(labs) if sum(len(x) for x in labs) <= 14 else labs[0] + " 외")
        edges.append(e)
    return {"nodes": list(nodes.values()), "edges": edges}


def main_path(spec):
    """시작에서 첫 갈래를 따라 끝까지 — 큰 줄기"""
    out = {}
    for e in spec["edges"]:
        if not e.get("loop"):
            out.setdefault(e["from"], []).append(e["to"])
    kinds = {n["id"]: n["kind"] for n in spec["nodes"]}
    cur = next(n["id"] for n in spec["nodes"] if n["kind"] == "start")
    path = [cur]
    while out.get(cur):
        nxt = [t for t in out[cur] if t not in path]
        if not nxt:
            break
        good = [t for t in nxt if kinds[t] not in ("error", "wait")] or nxt
        cur = good[0]
        path.append(cur)
    return path


def rules(spec):
    """그림용 흐름 규칙(의뢰서 1~6)을 센다"""
    E = []
    nodes, edges = spec["nodes"], spec["edges"]
    if len(nodes) > 11:
        E.append(f"상자 {len(nodes)} > 11")
    if len(edges) > 13:
        E.append(f"선 {len(edges)} > 13")
    order = {n: i for i, n in enumerate(main_path(spec))}
    back = [e for e in edges if e["from"] in order and e["to"] in order and order[e["to"]] < order[e["from"]]]
    if len([e for e in back if not e.get("loop")]) or len(back) > 1:
        E.append(f"거꾸로 가는 선 {len(back)}")
    if sum(1 for n in nodes if n["kind"] == "error") > 1:
        E.append("오류 상자 2개 이상")
    if sum(1 for n in nodes if n["kind"] == "decision") > 3:
        E.append("판단 3개 초과")
    if any(e["from"] == e["to"] for e in edges):
        E.append("제자리 선")
    return E


def _layout(spec, opt=(0.9, 0.75, False)):
    nodes, edges = spec["nodes"], spec["edges"]
    lines = ["digraph G {", f'graph [rankdir=TB, splines=ortho, nodesep={opt[0]}, ranksep={opt[1]}, pad=0.3{", ordering=out" if opt[2] else ""}];',
             'node [shape=box, fixedsize=true, label=""];', 'edge [arrowhead=none];']
    main = main_path(spec)
    for n in nodes:
        w, h = _size(n)
        n["_w"], n["_h"] = w, h
        grp = ', group="main"' if n["id"] in main else ""
        lines.append(f'"{n["id"]}" [width={w / 72:.3f}, height={h / 72:.3f}{grp}];')
    pairs = set(zip(main, main[1:]))
    for e in edges:
        extra = ", constraint=false" if e.get("loop") else ""
        if (e["from"], e["to"]) in pairs:
            extra += ", weight=20"
        lines.append(f'"{e["from"]}" -> "{e["to"]}" [xlabel=" "{extra}];')
    lines.append("}")
    out = subprocess.run(["dot", "-Tjson"], input="\n".join(lines).encode("utf-8"), capture_output=True, check=True)
    g = json.loads(out.stdout.decode("utf-8"))
    bb = [float(v) for v in g["bb"].split(",")]
    H = bb[3]
    pos = {}
    for o in g.get("objects", []):
        x, y = (float(v) for v in o["pos"].split(","))
        pos[o["name"]] = (x, H - y)
    routes = []
    for e in g.get("edges", []):
        pts = []
        for op in e.get("_draw_", []):
            if op["op"] in ("b", "B", "L"):
                pts = [(p[0], H - p[1]) for p in op["points"]]
        routes.append(pts)
    return pos, routes, bb


def _ortho(pts):
    """Graphviz 직각 선의 제어점에서 꺾이는 점만 남긴다"""
    keep = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - keep[-1][0]) < 0.5 and abs(p[1] - keep[-1][1]) < 0.5:
            continue
        keep.append(p)
    out = [keep[0]]
    for i in range(1, len(keep) - 1):
        a, b, c = out[-1], keep[i], keep[i + 1]
        if (abs(a[0] - b[0]) < 0.5 and abs(b[0] - c[0]) < 0.5) or (abs(a[1] - b[1]) < 0.5 and abs(b[1] - c[1]) < 0.5):
            continue
        out.append(b)
    out.append(keep[-1])
    return out


def _candidates(pts, w, h):
    segs = list(zip(pts, pts[1:]))
    order = [0] + ([len(segs) - 1] if len(segs) > 1 else []) + list(range(1, len(segs) - 1))
    for k in order:
        a, b = segs[k]
        L = abs(a[0] - b[0]) + abs(a[1] - b[1])
        if L < h + 16 and a[0] == b[0] or L < w + 16 and a[1] == b[1]:
            continue
        if a[0] == b[0]:  # 세로
            d = 1 if b[1] > a[1] else -1
            for t in (0.0, 0.5, 1.0):
                ys = a[1] + d * 12 + t * (L - 24 - h) * d
                y0 = ys if d > 0 else ys - h
                for x0 in (a[0] + 8, a[0] - 8 - w):
                    yield x0, y0
        else:             # 가로
            d = 1 if b[0] > a[0] else -1
            for t in (0.0, 0.5, 1.0):
                xs = a[0] + d * 12 + t * (L - 24 - w) * d
                x0 = xs if d > 0 else xs - w
                for y0 in (a[1] - 8 - h, a[1] + 8):
                    yield x0, y0


def _place(f, p, text):
    w, h = up4(tw(text, 12) + 8), 16
    first = None
    for x0, y0 in _candidates(p["pts"], w, h):
        x0, y0 = int(x0) - int(x0) % 4, int(y0)
        r = (x0, y0, w, h)
        first = first or (x0, y0)
        if r[0] < 8 or r[1] < 8 or r[0] + w > f.w - 8:
            continue
        if any(f._overlap(r, (nr[0] - 4, nr[1] - 4, nr[2] + 8, nr[3] + 8)) for nr in f.nodes.values()):
            continue
        if any(f._overlap(r, (lb["rect"][0] - 4, lb["rect"][1] - 4, lb["rect"][2] + 8, lb["rect"][3] + 8)) for lb in f.labels):
            continue
        clash = False
        for q in f.paths:
            dmin = min(f._rect_seg_dist(r, a, b) for a, b in f._segs(q["pts"]))
            if (q is not p and dmin < 6) or (q is p and not 6 <= dmin <= 16):
                clash = True
                break
        if not clash:
            return x0, y0
    return first or (p["pts"][0][0] + 8, p["pts"][0][1] + 8)


OPTS = [(0.9, 0.75, False), (0.9, 0.75, True), (0.6, 0.6, False), (1.2, 0.9, False), (0.6, 0.6, True), (1.2, 0.9, True), (0.75, 1.0, False), (1.5, 0.75, True)]


def best(spec, slug, title, desc):
    """간격 설정 몇 가지로 그려 보고 검사 위반이 가장 적은 판(같으면 넓이가 작은 판)"""
    figs = []
    for opt in OPTS:
        try:
            figs.append(draw(spec, slug, title, desc, opt))
        except Exception as exc:  # noqa: BLE001
            print("배치 실패", opt, exc)
    return min(figs, key=lambda f: (len(f.errors), f.w * f.h))


def draw(spec, slug, title, desc, opt=(0.9, 0.75, False)):
    import copy
    spec = normalize(copy.deepcopy(spec))
    pos, routes, bb = _layout(spec, opt)
    M, LEG = 40, 64
    W = g4(bb[2] + 2 * M)
    W = max(W, 1480)
    off = (W - bb[2]) / 2
    Hh = g4(bb[3] + 2 * M + LEG)
    f = Fig(slug, W, Hh, title, desc)
    f.max_nodes, f.max_arrows, f.max_accents = 40, 60, 12
    for n in spec["nodes"]:
        cx, cy = pos[n["id"]]
        w, h = n["_w"], n["_h"]
        x, y = g4(cx + off - w / 2), g4(cy + M - h / 2)
        lines = list(n.get("lines") or [])
        if n["kind"] == "decision":
            f.diamond(n["id"], g4(x + w / 2), g4(y + h / 2), w, h, n["title"])
        elif n["kind"] in OVAL:
            f.oval(n["id"], x, y, w, h, kind=OVAL[n["kind"]], title=_title(n), lines=lines)
        else:
            f.box(n["id"], x, y, w, h, kind=TAG_KIND.get(n.get("tag"), "backend"), title=_title(n), lines=lines)
    for i, (e, pts) in enumerate(zip(spec["edges"], routes)):
        if len(pts) < 2:
            continue
        pts = [(g4(px + off), g4(py + M)) for px, py in _ortho(pts)]
        # 반올림으로 생긴 사선을 직각으로 편다
        fixed = [pts[0]]
        for p in pts[1:]:
            a = fixed[-1]
            if a[0] != p[0] and a[1] != p[1]:
                fixed.append((a[0], p[1]) if abs(a[0] - p[0]) < abs(a[1] - p[1]) else (p[0], a[1]))
            fixed.append(p)
        pid = f"e{i}"
        f.path(pid, fixed, e["from"], e["to"], color="accent" if e.get("loop") else "muted")
    # 이름표 — 선이 다 그려진 뒤, 출발점 가까운 자리부터 부딪히지 않는 곳을 고른다
    for i, e in enumerate(spec["edges"]):
        lab = (e.get("label") or "").strip()
        p = next((q for q in f.paths if q["id"] == f"e{i}"), None)
        if lab and p:
            x0, y0 = _place(f, p, lab)
            f.label(p["id"], x0, y0, lab, anchor="left")
    f.legend(Hh - 36, LEGEND)
    f.rule_errors = rules(spec)
    try:
        f.check()
    except Exception as exc:  # noqa: BLE001
        f.errors.append(f"검사 실패 {exc}")
    return f


FONT_LINK = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
             '<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500;600'
             '&family=Noto+Sans+KR:wght@400;500;600&display=swap" rel="stylesheet">')


def fig_html(f):
    from html import escape
    return (f'<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><title>{escape(f.title)}</title>{FONT_LINK}'
            f'<style>body{{margin:0;background:#fbfcfd}} svg{{display:block;width:{f.w}px;height:auto}}</style></head>'
            f'<body>{f.svg()}</body></html>')


def export_png(items):
    """items: [(html 경로, png 경로)] — v26 과 같이 브라우저로 열어 SVG 를 2배로 찍는다"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch()
        for html_path, png_path in items:
            page = br.new_page(device_scale_factor=2, viewport={"width": 1400, "height": 900})
            page.goto(Path(html_path).as_uri(), wait_until="load", timeout=60000)
            page.wait_for_timeout(1500)
            page.evaluate("document.fonts.ready.then(() => true)")
            page.locator("svg").first.screenshot(path=str(png_path))
            page.close()
        br.close()


if __name__ == "__main__":
    import yaml
    spec = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
    fig = draw(spec, "t", "시험", "시험")
    out = Path(sys.argv[2])
    out.with_suffix(".html").write_text(fig_html(fig), encoding="utf-8")
    export_png([(out.with_suffix(".html"), out.with_suffix(".png"))])
    print("errors", len(fig.errors), fig.errors[:8])
