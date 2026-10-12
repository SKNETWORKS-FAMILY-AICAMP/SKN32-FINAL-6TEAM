# -*- coding: utf-8 -*-
"""발표용 SVG 흐름도 도구. 노드는 단계(step) 순서로 나타나고, 연결선은 흐르는 점선으로 움직인다."""
from html import escape

STY = {
    "trig": ("#f6ead4", "#c8913a", "#6d4a14"),
    "proc": ("#fffdf7", "#9fb0a6", "#1d2a23"),
    "dec": ("#e2eef7", "#2f6c9a", "#1d3f5c"),
    "agent": ("#e5efe8", "#2d5f48", "#1f4332"),
    "out": ("#2d5f48", "#2d5f48", "#ffffff"),
    "fail": ("#f6e3dc", "#b8503a", "#7a2f20"),
    "ghost": ("#f1f1ec", "#c9cdc6", "#6f7872"),
}


class Flow:
    def __init__(self, w, h):
        self.w, self.h, self.items, self.nodes = w, h, [], {}

    def node(self, key, x, y, w, h, text, kind="proc", step=0, size=19, bold=False):
        fill, stroke, ink = STY[kind]
        self.nodes[key] = (x, y, w, h)
        lines = text.split("\n")
        lh = size * 1.3
        ty = y + h / 2 - (len(lines) - 1) * lh / 2
        rx = 14 if kind != "dec" else 30
        t = "".join(f'<tspan x="{x + w / 2}" y="{ty + i * lh + size * 0.35}">{escape(l)}</tspan>' for i, l in enumerate(lines))
        self.items.append((step, f'<g class="{"step " if step else ""}n" data-s="{step}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2.2"/>'
                                 f'<text text-anchor="middle" font-size="{size}" font-weight="{700 if bold or kind in ("out", "agent", "trig") else 500}" fill="{ink}">{t}</text></g>'))

    def label(self, x, y, text, size=17, color="#5f6b64", step=0, anchor="start", weight=600):
        self.items.append((step, f'<text class="{"step" if step else ""}" x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(text)}</text>'))

    def _pt(self, key, side):
        x, y, w, h = self.nodes[key]
        return {"r": (x + w, y + h / 2), "l": (x, y + h / 2), "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[side]

    def edge(self, a, b, sa="r", sb="l", step=0, via=None, text=None, color="#8fa197", curve=True):
        x1, y1 = self._pt(a, sa)
        x2, y2 = self._pt(b, sb)
        if via:
            d = f"M{x1},{y1} " + " ".join(f"L{px},{py}" for px, py in via) + f" L{x2},{y2}"
        elif curve and sa in "rl" and sb in "rl":
            mx = (x1 + x2) / 2
            d = f"M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}"
        elif curve:
            my = (y1 + y2) / 2
            d = f"M{x1},{y1} C{x1},{my} {x2},{my} {x2},{y2}"
        else:
            d = f"M{x1},{y1} L{x2},{y2}"
        lab = ""
        if text:
            lx, ly = ((via[0][0] + via[-1][0]) / 2, via[0][1] - 10) if via else ((x1 + x2) / 2, (y1 + y2) / 2 - 8)
            lab = f'<text x="{lx}" y="{ly}" font-size="16" fill="#5f6b64" text-anchor="middle" font-weight="700" paint-order="stroke" stroke="#f5f3ec" stroke-width="6">{escape(text)}</text>'
        self.items.append((step, f'<g class="{"step" if step else ""}"><path class="edge" d="{d}" style="stroke:{color}" marker-end="url(#arr)"/>{lab}</g>'))

    def svg(self, cls=""):
        body = "".join(s for _, s in sorted(self.items, key=lambda t: t[0]))
        return (f'<svg class="{cls}" viewBox="0 0 {self.w} {self.h}" width="100%" height="100%" preserveAspectRatio="xMidYMid meet">'
                '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                '<path d="M0,0 L10,5 L0,10 z" fill="#8fa197"/></marker></defs>' + body + "</svg>")
