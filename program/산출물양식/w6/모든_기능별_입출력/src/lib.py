# -*- coding: utf-8 -*-
"""w6 모든 기능별 입출력 — 공통 조각 (CSS · 오버레이 설명 · 흐름 그림 · 페이지 틀).

형식은 w5/코어_에이전트_입출력 v7 의 오버레이(.k 밑줄 값 + .pop 설명 상자)와
w5/아키텍처_한눈에/v26 의 그림 읽는 법을 따른다. 흐름 그림은 멘토링 PDF
「유스케이스 & 멀티 에이전트 다이어그램」의 규칙(시작·끝, 노드 종류, 분기 조건식,
fan-out/fan-in, 루프 상한, 사람 개입 ⏸)을 지킨다.
"""
import html as H

NAV = [
    ("00_목차", "목차"),
    ("01_일정문제_감시", "01 일정 문제 감시"),
    ("02_처리건_열기_담당고르기", "02 처리 건 열기 · 담당 고르기"),
    ("03_작업지시서_TeamTask", "03 작업 지시서 (코어 → 에이전트)"),
    ("04_처리결과지_TeamResult", "04 처리 결과지 (에이전트 → 코어)"),
    ("05_일정관리_공통순서", "05 일정 관리 공통 순서"),
    ("06_외부정보_6종_점검", "06 외부 정보 6종 점검"),
    ("07_요식_에이전트", "07 요식 에이전트"),
    ("08_액티비티_에이전트", "08 액티비티 에이전트"),
    ("09_이동_판정_공용도구", "09 이동 판정 (공용 도구)"),
    ("10_고객신고_처리", "10 고객 신고 처리"),
    ("11_일정변경_적용", "11 일정 변경 적용"),
    ("12_알림_보관과_배달", "12 알림 보관과 배달"),
    ("13_계획_확인", "13 여행 계획 확인"),
    ("14_고객채팅_결정모델", "14 고객 채팅 (결정 모델)"),
    ("15_개인AI_입구_MCP", "15 개인 AI 입구 (MCP)"),
]

CSS = """
:root{--bg:#f6f4ee;--paper:#fffdf8;--ink:#1d2a23;--muted:#66716a;--line:#dcdfd6;--g1:#2d5f48;--g3:#e5efe8;--gold:#c8913a;--gold2:#f6ead4;--red:#b8503a;--red2:#f7e4dd;--code:#eef1ea;--dim:rgba(20,28,24,.45);--blue:#3b5bdb;--blue2:#eef4ff;--brown:#8a5f1c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Pretendard,"Malgun Gothic",sans-serif;line-height:1.6;font-size:15px}
.wrap{max-width:1180px;margin:0 auto;padding:22px 16px 60px}
h1{font-size:25px;margin:4px 0 4px}h2{font-size:19px;margin:30px 0 8px;border-top:2px solid var(--line);padding-top:14px}h3{font-size:16px;margin:18px 0 6px}
.eyebrow{font-size:12.5px;color:var(--g1);font-weight:800;margin:0}
.sub{color:var(--muted);font-size:13px}
.nav{font-size:13px;margin:6px 0 0}.nav a{color:var(--g1);margin-right:12px}
.top{background:var(--paper);border:1px solid var(--line);border-left:5px solid var(--g1);border-radius:12px;padding:10px 18px 10px 30px;margin:12px 0}
.top li{margin:4px 0}
.alert{background:var(--red2);border:1px solid var(--red);border-radius:12px;padding:8px 14px;margin:12px 0;font-size:14px}
table{width:100%;border-collapse:collapse;background:var(--paper);font-size:14px;margin:6px 0}
th,td{border-bottom:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:var(--g3);font-size:13px}
td.n{white-space:nowrap;font-weight:700;width:150px}
ol,ul{padding-left:24px}li{margin:3px 0}
.k{position:relative;display:inline-block;margin:1px 0;outline:none}
.k .lab{cursor:help;font-family:Consolas,"D2Coding",monospace;font-size:.92em;background:var(--code);padding:1px 6px;border-radius:5px;border-bottom:2px dotted var(--gold)}
.k:hover .lab,.k:focus .lab{background:var(--gold2)}
.dia{position:relative}
.hs{position:absolute;border-radius:10px;cursor:help;outline:none}
.hs:hover,.hs:focus{box-shadow:0 0 0 3px var(--gold)}
.pop{display:none;position:absolute;left:0;top:100%;margin-top:4px;z-index:30;width:min(560px,86vw);max-height:70vh;overflow:auto;background:var(--paper);border:1px solid var(--line);border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.22);padding:12px 16px;font-family:Pretendard,"Malgun Gothic",sans-serif;font-size:14px;line-height:1.55;text-align:left;white-space:normal;color:var(--ink);font-weight:400}
.k.r .pop,.hs.r .pop{left:auto;right:0}
.k:hover .pop,.k:focus .pop,.k:focus-within .pop,.hs:hover .pop,.hs:focus .pop,.hs:focus-within .pop{display:block}
.k:hover,.k:focus,.k:focus-within,.hs:hover,.hs:focus,.hs:focus-within{z-index:40}
.pop h3{margin:0 0 4px;font-size:16px;color:var(--ink)}.pop dl{margin:0}.pop dt{font-weight:800;font-size:12.5px;color:var(--g1);margin-top:8px}.pop dd{margin:1px 0 0}
.pop dt.cg{color:#8a938d;font-size:11.5px;margin-top:12px;border-top:1px dashed var(--line);padding-top:6px}.pop dd.cg{font-size:12.5px;color:#66716a}
.t{display:inline-block;font-size:11.5px;font-weight:800;padding:0 7px;border-radius:999px;border:1px solid;white-space:nowrap}
.t.no{color:var(--red);border-color:var(--red)}.t.yes{color:var(--g1);border-color:var(--g1)}.t.gap{color:#8a5f1c;border-color:var(--gold)}
.figwrap{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:10px;margin:10px 0}
.dia svg{display:block;width:100%;height:auto;font-family:Pretendard,"Malgun Gothic",sans-serif}
.legend{font-size:12.5px;color:var(--muted);margin:6px 2px 0}
.legend b{color:var(--ink)}
.card-table td.n{width:170px}
.note{font-size:13px;color:var(--muted)}
.foot{margin-top:34px;border-top:2px solid var(--line);padding-top:12px;font-size:14px}
.foot a{color:var(--g1);margin-right:14px}
@media (max-width:760px){.figwrap{overflow-x:auto}.dia{min-width:680px}table{font-size:13px}td.n{width:auto;white-space:normal}}
"""

LEGEND = ("<b>그림 읽는 법</b> · 타원 = 시작 · 끝(짙은 녹색 실선) · 빨간 점선 타원 = 오류로 끝남 · 회색 점선 타원 ⏸ = 고객이 답할 때까지 기다림 · "
          "흰 상자 = 정해진 규칙대로 하는 코드 · 파란 점선 상자 = 언어 모델이 돕는 자리 · 굵은 상자 = 담당 에이전트 · "
          "갈색 긴 점선 상자 = 공용 도구(에이전트가 아님) · 노란 마름모 = 코드의 판단(화살표 옆 글이 조건) · "
          "노란 화살표 = 되돌아가는 반복(옆에 상한) · 상자에 마우스를 올리거나 누르면 설명이 뜹니다.")


def esc(s):
    return H.escape(str(s), quote=False)


def tag(kind):
    text, cls = {"yes": ("근거 있음", "yes"), "no": ("근거 없음", "no"), "gap": ("부분 근거", "gap")}[kind]
    return f"<span class='t {cls}'>{text}</span>"


def pop_html(p):
    """p = {'h': 제목, '한마디로', '예를 들면', '왜 있나', '이렇게 움직입니다', '주의', 'src': 코드 · 근거}"""
    out = [f"<h3>{p['h']}</h3>", "<dl>"]
    for key in ("한마디로", "예를 들면", "왜 있나", "이렇게 움직입니다", "주의"):
        if p.get(key):
            out.append(f"<dt>{key}</dt><dd>{p[key]}</dd>")
    if p.get("src"):
        out.append(f"<dt class='cg'>코드 · 근거</dt><dd class='cg'>{p['src']}</dd>")
    out.append("</dl>")
    return f'<div class="pop" role="tooltip">{"".join(out)}</div>'


def term(label, p, right=False):
    """글 속 밑줄 값 하나 + 설명 상자 (v7 의 .k 구조)."""
    cls = "k r" if right else "k"
    return f'<span class="{cls}" tabindex="0"><span class="lab">{esc(label)}</span>{pop_html(p)}</span>'


# ---------- 흐름 그림 ----------
W = 1000
KIND_DEFAULT_SIZE = {"start": (200, 50), "end": (200, 50), "err": (230, 56), "wait": (230, 56),
                     "dec": (230, 84), "code": (270, 60), "llm": (270, 60), "agent": (270, 62),
                     "tool": (270, 60), "ext": (210, 56)}


def _inside(kind, w, h, dx, dy):
    if kind in ("start", "end", "err", "wait"):
        return (dx / (w / 2)) ** 2 + (dy / (h / 2)) ** 2 <= 1
    if kind == "dec":
        return abs(dx) / (w / 2) + abs(dy) / (h / 2) <= 1
    return abs(dx) <= w / 2 and abs(dy) <= h / 2


def _clip(n, tx, ty):
    """n 의 중심에서 (tx,ty) 쪽으로 가다가 모양의 가장자리에 닿는 점."""
    x0, y0 = n["x"], n["y"]
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        x, y = x0 + (tx - x0) * mid, y0 + (ty - y0) * mid
        if _inside(n["kind"], n["w"], n["h"], x - x0, y - y0):
            lo = mid
        else:
            hi = mid
    return x0 + (tx - x0) * hi, y0 + (ty - y0) * hi


def _node_svg(n):
    x, y, w, h, k = n["x"], n["y"], n["w"], n["h"], n["kind"]
    if k in ("start", "end"):
        shape = f'<ellipse cx="{x}" cy="{y}" rx="{w/2}" ry="{h/2}" fill="#eef1ea" stroke="#2d5f48" stroke-width="2"/>'
    elif k == "err":
        shape = f'<ellipse cx="{x}" cy="{y}" rx="{w/2}" ry="{h/2}" fill="#f7e4dd" stroke="#b8503a" stroke-width="2.5" stroke-dasharray="7 4"/>'
    elif k == "wait":
        shape = f'<ellipse cx="{x}" cy="{y}" rx="{w/2}" ry="{h/2}" fill="#ecebe7" stroke="#66716a" stroke-width="2" stroke-dasharray="4 4"/>'
    elif k == "dec":
        pts = f"{x},{y-h/2} {x+w/2},{y} {x},{y+h/2} {x-w/2},{y}"
        shape = f'<polygon points="{pts}" fill="#fff3cf" stroke="#c8913a" stroke-width="2"/>'
    elif k == "llm":
        shape = f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" rx="8" fill="#eef4ff" stroke="#3b5bdb" stroke-width="2" stroke-dasharray="6 3"/>'
    elif k == "agent":
        shape = f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" rx="8" fill="#e5efe8" stroke="#2d5f48" stroke-width="4"/>'
    elif k == "tool":
        shape = f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" rx="6" fill="#fbf6ea" stroke="#8a5f1c" stroke-width="2.5" stroke-dasharray="14 5"/>'
    elif k == "ext":
        shape = f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" rx="8" fill="#ffffff" stroke="#66716a" stroke-width="1.5"/>'
    else:
        shape = f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" rx="8" fill="#fffdf8" stroke="#1d2a23" stroke-width="1.6"/>'
    lines = n["label"].split("\n")
    step = 18
    y0 = y - (len(lines) - 1) * step / 2
    texts = "".join(
        f'<text x="{x}" y="{y0 + i*step}" text-anchor="middle" dominant-baseline="middle" font-size="14" fill="#1d2a23">{esc(t)}</text>'
        for i, t in enumerate(lines))
    return shape + texts


def _edge_svg(e, nodes):
    a, b = nodes[e["a"]], nodes[e["b"]]
    x1, y1 = _clip(a, b["x"], b["y"]) if not e.get("via") else _clip(a, e["via"][0], e["via"][1])
    x2, y2 = _clip(b, a["x"], a["y"]) if not e.get("via") else _clip(b, e["via"][0], e["via"][1])
    style = e.get("style", "solid")
    stroke, dash, marker, width = {
        "solid": ("#1d2a23", "", "ar", 1.8),
        "dash": ("#66716a", ' stroke-dasharray="6 4"', "ar", 1.6),
        "loop": ("#c8913a", ' stroke-dasharray="4 3"', "arg", 2.2),
        "err": ("#b8503a", ' stroke-dasharray="5 3"', "arr", 2.0),
    }[style]
    if e.get("via"):
        cx, cy = e["via"]
        d = f"M{x1:.1f},{y1:.1f} Q{cx},{cy} {x2:.1f},{y2:.1f}"
        mx, my = 0.25 * x1 + 0.5 * cx + 0.25 * x2, 0.25 * y1 + 0.5 * cy + 0.25 * y2
    else:
        d = f"M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}"
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    out = f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{width}"{dash} marker-end="url(#{marker})"/>'
    if e.get("label"):
        dx, dy = e.get("lt", (0, 0))
        lx, ly = mx + dx, my + dy
        tw = 13 * len(e["label"]) + 14
        out += (f'<rect x="{lx - tw/2:.1f}" y="{ly - 11:.1f}" width="{tw}" height="22" rx="5" fill="#fffdf8" stroke="{stroke}" stroke-width="0.8" opacity="0.97"/>'
                f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="13" fill="{stroke if style!="solid" else "#1d2a23"}">{esc(e["label"])}</text>')
    return out


def flow(nodes, edges, note=None):
    """nodes: [dict(id, kind, label, x, y, [w, h], pop)], edges: [dict(a, b, label, style, via, lt)]"""
    for n in nodes:
        dw, dh = KIND_DEFAULT_SIZE[n["kind"]]
        n.setdefault("w", dw)
        n.setdefault("h", dh)
    by = {n["id"]: n for n in nodes}
    H_ = int(max(n["y"] + n["h"] / 2 for n in nodes)) + 30
    defs = ('<defs>'
            '<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#1d2a23"/></marker>'
            '<marker id="arg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#c8913a"/></marker>'
            '<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#b8503a"/></marker>'
            '</defs>')
    edges_svg = "".join(_edge_svg({**e, "a": e["a"], "b": e["b"]}, by) for e in edges)
    nodes_svg = "".join(_node_svg(n) for n in nodes)
    svg = f'<svg viewBox="0 0 {W} {H_}" xmlns="http://www.w3.org/2000/svg" role="img">{defs}{edges_svg}{nodes_svg}</svg>'
    spots = []
    for n in nodes:
        if not n.get("pop"):
            continue
        left = (n["x"] - n["w"] / 2) / W * 100
        top = (n["y"] - n["h"] / 2) / H_ * 100
        width = n["w"] / W * 100
        height = n["h"] / H_ * 100
        cls = "hs r" if n["x"] > 560 else "hs"
        spots.append(f'<div class="{cls}" tabindex="0" style="left:{left:.2f}%;top:{top:.2f}%;width:{width:.2f}%;height:{height:.2f}%">{pop_html(n["pop"])}</div>')
    note_html = f'<p class="note">{note}</p>' if note else ""
    return (f'<div class="figwrap"><div class="dia">{svg}{"".join(spots)}</div>'
            f'<p class="legend">{LEGEND}</p>{note_html}</div>')


# ---------- 페이지 틀 ----------
def _nav_links(slug):
    idx = [s for s, _ in NAV]
    i = idx.index(slug)
    prev_ = NAV[i - 1] if i > 0 else None
    next_ = NAV[i + 1] if i + 1 < len(NAV) else None
    parts = ['<a href="00_목차.html">목차로</a>']
    if prev_:
        parts.append(f'<a href="{prev_[0]}.html">← {esc(prev_[1])}</a>')
    if next_:
        parts.append(f'<a href="{next_[0]}.html">{esc(next_[1])} →</a>')
    return " ".join(parts)


def page(slug, title, sub, top, spec=None, scenario=None, ext=None, diagram=None,
         io=None, card=None, notes=None, evidence=None, alert=None, diagram_title="그림"):
    o = [f"<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
         f"<title>{esc(title)}</title>",
         '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">',
         f"<style>{CSS}</style></head><body><div class=\"wrap\">",
         '<p class="eyebrow">guguroute · 모든 기능별 입출력 · 2026-10-12</p>',
         f"<h1>{esc(title)}</h1>",
         f'<div class="sub">{sub}</div>',
         f'<div class="nav">{_nav_links(slug)}</div>',
         '<ul class="top">' + "".join(f"<li>{t}</li>" for t in top) + "</ul>"]
    if alert:
        o.append(f'<div class="alert">{alert}</div>')
    if spec:
        o.append("<h2>1. 명세 머리 — 누가 무엇을 이루려고 하나</h2>")
        o.append('<table class="card-table"><tbody>' + "".join(f"<tr><td class='n'>{k}</td><td>{v}</td></tr>" for k, v in spec) + "</tbody></table>")
    if scenario:
        o.append("<h2>2. 주 성공 시나리오</h2><ol>" + "".join(f"<li>{s}</li>" for s in scenario) + "</ol>")
    if ext:
        o.append("<h2>3. 확장 · 예외 — 주 시나리오에서 갈라지는 길</h2><ul>" + "".join(f"<li>{s}</li>" for s in ext) + "</ul>")
    if diagram:
        o.append(f"<h2>4. {diagram_title}</h2>")
        o.append(flow(diagram["nodes"], diagram["edges"], diagram.get("note")))
    if io:
        o.append("<h2>5. 입력 · 출력</h2>")
        for part, rows in (("입력 — 들어오는 것", io.get("in", [])), ("출력 — 나가는 것", io.get("out", []))):
            if not rows:
                continue
            o.append(f"<h3>{part}</h3><table><thead><tr><th style='width:210px'>칸</th><th>무엇을 담나</th><th style='width:260px'>정해지는 곳 · 쓰는 곳</th></tr></thead><tbody>")
            for label, meaning, pop, where in rows:
                o.append(f"<tr><td>{term(label, pop)}</td><td>{meaning}</td><td>{where}</td></tr>")
            o.append("</tbody></table>")
    if card:
        o.append("<h2>6. 에이전트 명세 카드 — 그림이 못 담는 것을 표로</h2>")
        o.append("<table class='card-table'><thead><tr><th>항목</th><th>내용</th></tr></thead><tbody>" + "".join(f"<tr><td class='n'>{k}</td><td>{v}</td></tr>" for k, v in card) + "</tbody></table>")
    if notes:
        o.append("<h2>7. 미확정 · 한계 · 정할 것</h2><ul>" + "".join(f"<li>{s}</li>" for s in notes) + "</ul>")
    if evidence:
        o.append("<h2>8. 코드 위치 · 근거</h2><ul class='note'>" + "".join(f"<li>{s}</li>" for s in evidence) + "</ul>")
    o.append(f'<div class="foot">{_nav_links(slug)}</div>')
    o.append("</div></body></html>")
    return "".join(o)
