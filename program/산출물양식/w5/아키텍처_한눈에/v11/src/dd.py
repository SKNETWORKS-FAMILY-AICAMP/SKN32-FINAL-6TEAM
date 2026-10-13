# -*- coding: utf-8 -*-
"""diagram-design 스킬 규칙을 코드로 지키는 작은 그림판 (2026-10-02, v10)

- 색 · 글꼴: ~/.diagram-design/profiles/acop.md (프로젝트 루트 .diagram-design → profile: acop)
- 4px 격자 · 둥근 직각 연결선 r=8 · 이름표 가림 사각형 + 선과 6~10px 간격
- 화살표를 상자보다 먼저 그린다 · 범례는 아래 가로 띠
- 그리면서 스스로 검사한다(check): 격자 · 글자 넘침 · 이름표-선 간격 · 이름표-상자 겹침 · 선이 남의 상자 뒤로 지나감 · 선끼리 겹침/교차
"""
import math
import unicodedata
from html import escape

PAPER = "#fbfcfd"
PAPER2 = "#f1f4f8"
INK = "#161c28"
MUTED = "#6b7488"
SOFT = "#7a8599"
RULE = "rgba(22,28,40,0.12)"
RULE_SOLID = "#dbe0ea"
ACCENT = "#a8720c"
ACCENT_TINT = "rgba(168,114,12,0.10)"
LINK = "#2f5bd8"

SANS = "'Geist', 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"
MONO = "'Geist Mono', ui-monospace, monospace"

KIND = {  # 스킬 node type → treatment (acop 값)
    "backend": ("#ffffff", INK, None),
    "focal": (ACCENT_TINT, ACCENT, None),
    "input": ("rgba(107,116,136,0.10)", SOFT, None),
    "external": ("rgba(22,28,40,0.03)", "rgba(22,28,40,0.30)", None),
    "store": ("rgba(22,28,40,0.05)", MUTED, None),
    "optional": ("rgba(22,28,40,0.02)", "rgba(22,28,40,0.20)", "4,3"),
}
STROKE = {"muted": (MUTED, "arrow", 1.2), "accent": (ACCENT, "arrow-accent", 1.6),
          "link": (LINK, "arrow-link", 1.2), "soft": (SOFT, "arrow-soft", 1)}


def wide(c):
    return unicodedata.east_asian_width(c) in "WF"


def has_kr(s):
    return any(wide(c) for c in s)


def tw(s, size, mono=False):
    """글자 폭 예산 — 넓은 글자 1em, 나머지 0.60em(sans)/0.62em(mono)"""
    w = 0.0
    for c in s:
        if unicodedata.combining(c):
            continue
        w += size if wide(c) else size * (0.62 if mono else 0.60)
    return w


def up4(v):
    return int(math.ceil(v / 4.0) * 4)


def fmt(v):
    return str(int(v)) if float(v).is_integer() else f"{v:.3f}"


class Fig:
    def __init__(self, slug, w, h, title, desc):
        self.slug, self.w, self.h, self.title, self.desc = slug, w, h, title, desc
        self.nodes = {}      # name → (x, y, w, h, shape)
        self.node_svg = []
        self.paths = []      # dict(id, pts, src, dst, color, dash)
        self.raw_paths = []  # 순환 그림의 호 · 방사선 (직접 만든 d)
        self.labels = []     # dict(rect, svg, path)
        self.extra = []      # 범례 등 마지막에
        self.errors = []
        self.accents = 0
        self.zones = []
        self.max_nodes, self.max_arrows, self.max_accents = 9, 12, 2

    def zone(self, x, y, w, h, label, lx=16):
        """구역 — 화살표보다 먼저 그린다. 이름은 왼쪽 위"""
        self._grid(x, y, w, h, what=label)
        self.zones.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="rgba(22,28,40,0.025)" stroke="{RULE}" stroke-width="1"/>'
                          f'<text x="{x + lx}" y="{y + 20}" class="zone">{escape(label)}</text>')

    # ---------- 상자 ----------
    def _grid(self, *vals, what=""):
        for v in vals:
            if v % 4:
                self.errors.append(f"격자 벗어남 {what}: {vals}")
                return

    def box(self, name, x, y, w, h, kind="backend", title=None, tag=None, lines=(), io=(), align="center"):
        """일반 상자 — 이름(12px 600) + 설명 줄(한글 12px) 또는 I/O 줄"""
        self._grid(x, y, w, h, what=name)
        fill, stroke, dash = KIND[kind]
        if kind == "focal":
            self.accents += 1
        self.nodes[name] = (x, y, w, h, "rect")
        s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{PAPER}"/>',
             f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1"'
             + (f' stroke-dasharray="{dash}"' if dash else "") + "/>"]
        top = y + 8
        if tag:
            tgw = up4(tw(tag, 8, True) + 10)
            s.append(f'<rect x="{x + 8}" y="{top}" width="{tgw}" height="12" rx="2" fill="none" stroke="{stroke}" stroke-opacity="0.45" stroke-width="0.8"/>')
            s.append(f'<text x="{x + 8 + tgw / 2:g}" y="{top + 9}" class="tag" fill="{stroke}">{escape(tag)}</text>')
        title = title or name
        cx = x + w / 2
        if tag or io:
            ty = y + 36
        else:
            ty = y + h / 2 + 4 - 9 * len(lines)
        s.append(f'<text x="{cx:g}" y="{ty:g}" class="name{" focal-name" if kind == "focal" else ""}">{escape(title)}</text>')
        self._fit(name, title, 12, w - 24)
        ly = ty + 20
        for ln in lines:
            if isinstance(ln, tuple):  # ("mono", 툴 이름)
                s.append(f'<text x="{cx:g}" y="{ly:g}" class="tech">{escape(ln[1])}</text>')
                if tw(ln[1], 12, True) > w - 24:
                    self.errors.append(f"글자 넘침 {name}: 「{ln[1]}」")
            else:
                s.append(f'<text x="{cx:g}" y="{ly:g}" class="sub">{escape(ln)}</text>')
                self._fit(name, ln, 12, w - 24)
            ly += 18
        for pre, txt in io:
            s.append(f'<text x="{x + 16}" y="{ly:g}" class="io-k">{pre}</text>')
            s.append(f'<text x="{x + 34}" y="{ly:g}" class="io">{escape(txt)}</text>')
            self._fit(name, txt, 12, w - 34 - 14)
            ly += 20
        if ly - 20 + 12 > y + h:
            self.errors.append(f"상자 높이 부족 {name}: 마지막 줄 {ly - 20} > {y + h - 12}")
        self.node_svg.append("\n".join(s))

    def oval(self, name, x, y, w, h, kind="external", title=None, lines=()):
        self._grid(x, y, w, h, what=name)
        fill, stroke, _ = KIND[kind]
        if kind == "focal":
            self.accents += 1
        self.nodes[name] = (x, y, w, h, "oval")
        title = title or name
        cx = x + w / 2
        ty = y + h / 2 + 4 - 9 * len(lines)
        s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h // 2}" fill="{PAPER}"/>',
             f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h // 2}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>',
             f'<text x="{cx:g}" y="{ty:g}" class="name{" focal-name" if kind == "focal" else ""}">{escape(title)}</text>']
        self._fit(name, title, 12, w - 32)
        ly = ty + 18
        for ln in lines:
            s.append(f'<text x="{cx:g}" y="{ly:g}" class="sub">{escape(ln)}</text>')
            self._fit(name, ln, 12, w - 32)
            ly += 18
        self.node_svg.append("\n".join(s))

    def diamond(self, name, cx, cy, w, h, title):
        self._grid(cx, cy, w, h, what=name)
        x, y = cx - w // 2, cy - h // 2
        self.nodes[name] = (x, y, w, h, "diamond")
        pts = f"{cx},{y} {x + w},{cy} {cx},{y + h} {x},{cy}"
        s = [f'<polygon points="{pts}" fill="{PAPER}"/>',
             f'<polygon points="{pts}" fill="#ffffff" stroke="{INK}" stroke-width="1"/>',
             f'<text x="{cx}" y="{cy + 4}" class="name">{escape(title)}</text>']
        self._fit(name, title, 12, w / 2 + 8)
        self.node_svg.append("\n".join(s))

    def _fit(self, name, text, size, room):
        if tw(text, size) > room:
            self.errors.append(f"글자 넘침 {name}: 「{text}」 {tw(text, size):.0f}px > {room:.0f}px")

    # ---------- 선 ----------
    def path(self, pid, pts, src, dst, color="muted", dash=None):
        for p in pts:
            self._grid(*p, what=pid)
        for a, b in zip(pts, pts[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                self.errors.append(f"사선 {pid}: {a}→{b}")
        if color == "accent":
            self.accents += 1
        self.paths.append(dict(id=pid, pts=pts, src=src, dst=dst, color=color, dash=dash))

    def label(self, pid, x, y, text, color=None, anchor="center"):
        """이름표 — (x, y) 는 가림 사각형의 왼쪽 위(anchor=left) 또는 가운데 위(center)"""
        kr = has_kr(text)
        size = 12 if kr else 8
        h = 16 if kr else 12
        w = up4(tw(text, size, mono=not kr) + 8)
        x0 = x - w // 2 if anchor == "center" else (x - w if anchor == "right" else x)
        x0 = x0 - x0 % 4
        col = color or (dict(muted=MUTED, accent=ACCENT, link=LINK, soft=SOFT)[self._pcolor(pid)])
        cls = "lab" if kr else "lab-mono"
        svg = (f'<rect x="{x0}" y="{y}" width="{w}" height="{h}" rx="2" fill="{PAPER}"/>'
               f'<text x="{x0 + w / 2:g}" y="{y + (12 if kr else 9)}" class="{cls}" fill="{col}">{escape(text)}</text>')
        self.labels.append(dict(rect=(x0, y, w, h), svg=svg, path=pid, text=text))

    def _pcolor(self, pid):
        for p in self.paths:
            if p["id"] == pid:
                return p["color"]
        return "muted"

    @staticmethod
    def elbow(pts, r=8):
        d = f"M{fmt(pts[0][0])} {fmt(pts[0][1])}"
        for i in range(1, len(pts) - 1):
            p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
            l1 = abs(p1[0] - p0[0]) + abs(p1[1] - p0[1])
            l2 = abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])
            v1 = ((p1[0] > p0[0]) - (p1[0] < p0[0]), (p1[1] > p0[1]) - (p1[1] < p0[1]))
            v2 = ((p2[0] > p1[0]) - (p2[0] < p1[0]), (p2[1] > p1[1]) - (p2[1] < p1[1]))
            rr = min(r, l1 / 2, l2 / 2)
            a = (p1[0] - v1[0] * rr, p1[1] - v1[1] * rr)
            b = (p1[0] + v2[0] * rr, p1[1] + v2[1] * rr)
            sweep = 1 if v1[0] * v2[1] - v1[1] * v2[0] > 0 else 0
            d += f" L{fmt(a[0])} {fmt(a[1])} A{fmt(rr)} {fmt(rr)} 0 0 {sweep} {fmt(b[0])} {fmt(b[1])}"
        d += f" L{fmt(pts[-1][0])} {fmt(pts[-1][1])}"
        return d

    # ---------- 검사 ----------
    @staticmethod
    def _segs(pts):
        return list(zip(pts, pts[1:]))

    @staticmethod
    def _rect_seg_dist(rect, a, b):
        x, y, w, h = rect
        if a[0] == b[0]:  # 세로
            sx, y1, y2 = a[0], min(a[1], b[1]), max(a[1], b[1])
            dx = max(x - sx, 0, sx - (x + w))
            dy = max(y - y2, 0, y1 - (y + h))
        else:
            sy, x1, x2 = a[1], min(a[0], b[0]), max(a[0], b[0])
            dy = max(y - sy, 0, sy - (y + h))
            dx = max(x - x2, 0, x1 - (x + w))
        return math.hypot(dx, dy)

    @staticmethod
    def _overlap(r1, r2):
        return not (r1[0] + r1[2] <= r2[0] or r2[0] + r2[2] <= r1[0] or r1[1] + r1[3] <= r2[1] or r2[1] + r2[3] <= r1[1])

    def check(self):
        E = self.errors
        # 이름표 ↔ 자기 선 6~10px(최소 6), 남의 선과도 안 닿게(4px), 상자와 겹치지 않게
        for lb in self.labels:
            r = lb["rect"]
            for p in self.paths:
                dmin = min(self._rect_seg_dist(r, a, b) for a, b in self._segs(p["pts"]))
                if p["id"] == lb["path"]:
                    if dmin < 6:
                        E.append(f"이름표가 자기 선에 붙음 「{lb['text']}」 {dmin:.1f}px")
                    if dmin > 16:
                        E.append(f"이름표가 자기 선에서 멂 「{lb['text']}」 {dmin:.1f}px")
                elif dmin < 4:
                    E.append(f"이름표가 남의 선({p['id']})을 가림 「{lb['text']}」 {dmin:.1f}px")
            for n, nr in self.nodes.items():
                inside = nr[0] <= r[0] and nr[1] <= r[1] and r[0] + r[2] <= nr[0] + nr[2] and r[1] + r[3] <= nr[1] + nr[3]
                if self._overlap(r, nr[:4]) and not inside:
                    E.append(f"이름표가 상자 {n} 와 겹침 「{lb['text']}」")
            for lb2 in self.labels:
                if lb2 is not lb and self._overlap(r, lb2["rect"]):
                    E.append(f"이름표끼리 겹침 「{lb['text']}」·「{lb2['text']}」")
            if r[0] < 0 or r[1] < 0 or r[0] + r[2] > self.w or r[1] + r[3] > self.h:
                E.append(f"이름표가 그림 밖 「{lb['text']}」")
        # 선이 끝점이 아닌 상자 뒤로 지나감
        for p in self.paths:
            for a, b in self._segs(p["pts"]):
                for n, (x, y, w, h, _) in self.nodes.items():
                    if n in (p["src"], p["dst"]):
                        continue
                    if self._rect_seg_dist((x + 1, y + 1, w - 2, h - 2), a, b) == 0:
                        E.append(f"선 {p['id']} 이 상자 {n} 뒤로 지나감 {a}→{b}")
        # 선끼리: 같은 줄 겹침 · 직각 교차 · 평행 12px 미만
        for i, p in enumerate(self.paths):
            for q in self.paths[i + 1:]:
                for a, b in self._segs(p["pts"]):
                    for c, d in self._segs(q["pts"]):
                        self._seg_pair(p["id"], q["id"], a, b, c, d)
        # 같은 상자 같은 점에 두 선
        ends = {}
        for p in self.paths:
            for pt in (p["pts"][0], p["pts"][-1]):
                ends.setdefault(pt, []).append(p["id"])
        for pt, ids in ends.items():
            if len(ids) > 1:
                E.append(f"한 점에 선 여러 개 {pt}: {ids}")
        if self.accents > self.max_accents:
            E.append(f"강조색 {self.accents}개 > {self.max_accents}")
        if len(self.nodes) > self.max_nodes:
            E.append(f"상자 {len(self.nodes)}개 > {self.max_nodes}")
        if len(self.paths) + len(self.raw_paths) > self.max_arrows:
            E.append(f"화살표 {len(self.paths) + len(self.raw_paths)}개 > 12")
        return E

    def _seg_pair(self, pid, qid, a, b, c, d):
        E = self.errors
        av, cv = a[0] == b[0], c[0] == d[0]
        if av and cv:
            if abs(a[0] - c[0]) < 12:
                lo = max(min(a[1], b[1]), min(c[1], d[1]))
                hi = min(max(a[1], b[1]), max(c[1], d[1]))
                if hi > lo:
                    E.append(f"세로 선 {pid}·{qid} 가 12px 안으로 나란함 x={a[0]},{c[0]} y {lo}~{hi}")
        elif not av and not cv:
            if abs(a[1] - c[1]) < 12:
                lo = max(min(a[0], b[0]), min(c[0], d[0]))
                hi = min(max(a[0], b[0]), max(c[0], d[0]))
                if hi > lo:
                    E.append(f"가로 선 {pid}·{qid} 가 12px 안으로 나란함 y={a[1]},{c[1]} x {lo}~{hi}")
        else:
            v, hz = ((a, b), (c, d)) if av else ((c, d), (a, b))
            x, y = v[0][0], hz[0][1]
            if min(hz[0][0], hz[1][0]) < x < max(hz[0][0], hz[1][0]) and min(v[0][1], v[1][1]) < y < max(v[0][1], v[1][1]):
                E.append(f"선 {pid}·{qid} 가 교차 ({x},{y})")

    # ---------- 출력 ----------
    def legend(self, y, items):
        """items: (종류, 글) — 종류: 상자 kind 이름 / 'line:색' / 'dash:색' / 'diamond' / 'oval'"""
        s = [f'<line x1="32" y1="{y - 8}" x2="{self.w - 32}" y2="{y - 8}" stroke="{RULE}" stroke-width="0.8"/>',
             f'<text x="32" y="{y + 12}" class="lab-mono" fill="{MUTED}" text-anchor="start">LEGEND</text>']
        x = 104
        for kind, text in items:
            if kind.startswith("line:") or kind.startswith("dash:"):
                col = kind.split(":")[1]
                c, m, sw = STROKE[col]
                s.append(f'<line x1="{x}" y1="{y + 8}" x2="{x + 28}" y2="{y + 8}" stroke="{c}" stroke-width="{sw}"'
                         + (' stroke-dasharray="5,4"' if kind.startswith("dash") else "") + f' marker-end="url(#{m})"/>')
            elif kind == "diamond":
                s.append(f'<polygon points="{x + 14},{y} {x + 28},{y + 8} {x + 14},{y + 16} {x},{y + 8}" fill="#ffffff" stroke="{INK}" stroke-width="1"/>')
            elif kind == "hub":
                s.append(f'<rect x="{x}" y="{y}" width="28" height="16" rx="4" fill="{INK}"/>')
            else:
                fill, stroke, dash = KIND[kind[5:] if kind.startswith("oval:") else kind]
                rx = 8 if kind.startswith("oval:") else 3
                s.append(f'<rect x="{x}" y="{y}" width="28" height="16" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1"'
                         + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
            s.append(f'<text x="{x + 36}" y="{y + 12}" class="leg">{escape(text)}</text>')
            x += 36 + up4(tw(text, 12)) + 28
        if x > self.w:
            self.errors.append(f"범례가 그림 폭을 넘음 {x} > {self.w}")
        self.extra.append("\n".join(s))

    def svg(self):
        sl = self.slug
        out = [f'<svg viewBox="0 0 {self.w} {self.h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="{sl}-title {sl}-desc">',
               f'<title id="{sl}-title">{escape(self.title)}</title>',
               f'<desc id="{sl}-desc">{escape(self.desc)}</desc>',
               "<defs>" + STYLE_DEFS + "</defs>",
               f'<rect width="{self.w}" height="{self.h}" fill="{PAPER}"/>',
               *self.zones,
               "<!-- 화살표 먼저 -->"]
        for p in self.paths:
            c, m, sw = STROKE[p["color"]]
            out.append(f'<path d="{self.elbow(p["pts"])}" fill="none" stroke="{c}" stroke-width="{sw}"'
                       + (f' stroke-dasharray="{p["dash"]}"' if p["dash"] else "") + f' marker-end="url(#{m})"/>')
        out += self.raw_paths
        out.append("<!-- 이름표 -->")
        out += [lb["svg"] for lb in self.labels]
        out.append("<!-- 상자 -->")
        out += self.node_svg
        out += self.extra
        out.append("</svg>")
        return "\n".join(out)


STYLE_DEFS = (
    f'<marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{MUTED}"/></marker>'
    f'<marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{ACCENT}"/></marker>'
    f'<marker id="arrow-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{LINK}"/></marker>'
    f'<marker id="arrow-soft" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{SOFT}"/></marker>'
    "<style>"
    f".name{{font-family:{SANS};font-size:12px;font-weight:600;fill:{INK};text-anchor:middle}}"
    f".focal-name{{fill:{ACCENT}}}"
    f".sub{{font-family:{SANS};font-size:12px;font-weight:400;fill:{MUTED};text-anchor:middle}}"
    f".io{{font-family:{SANS};font-size:12px;font-weight:400;fill:{INK}}}"
    f".io-k{{font-family:{MONO};font-size:12px;font-weight:600;fill:{SOFT}}}"
    f".tag{{font-family:{MONO};font-size:8px;font-weight:500;letter-spacing:0.08em;text-anchor:middle}}"
    f".lab{{font-family:{SANS};font-size:12px;font-weight:500;text-anchor:middle}}"
    f".lab-mono{{font-family:{MONO};font-size:8px;letter-spacing:0.14em;text-anchor:middle}}"
    f".tech{{font-family:{MONO};font-size:12px;fill:{INK};text-anchor:middle}}"
    f".zone{{font-family:{SANS};font-size:12px;font-weight:600;fill:{MUTED}}}"
    f".leg{{font-family:{SANS};font-size:12px;fill:{MUTED}}}"
    f".hub-name{{font-family:{SANS};font-size:16px;font-weight:600;fill:{PAPER};text-anchor:middle}}"
    f".hub-sub{{font-family:{SANS};font-size:12px;fill:rgba(251,252,253,0.78);text-anchor:middle}}"
    f".layer-name{{font-family:{SANS};font-size:16px;font-weight:600;fill:{INK}}}"
    f".layer-note{{font-family:{SANS};font-size:12px;fill:{MUTED}}}"
    f".layer-tech{{font-family:{MONO};font-size:12px;fill:{INK}}}"
    "</style>"
)
