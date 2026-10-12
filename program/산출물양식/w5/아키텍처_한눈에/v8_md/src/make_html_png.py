# -*- coding: utf-8 -*-
"""md 구조도를 같은 모양 그대로 HTML · PNG 로 — 문서 전체 한 장 + 글자 그림 두 장 따로 (2026-10-02)

    python make_html_png.py <판>   예) python make_html_png.py v9
        → ../triPilot_Multi-Agent구조도_<판>.html · .png · 그림1_전체구조도_<판>.png · 그림2_툴데이터계층_<판>.png

★md 모양을 바꾸지 않는다 — 제목 · 굵은 글씨 · 글자 그림(코드 블록) · 표를 GitHub 문서처럼 그대로 보여 준다.
★글자 그림 줄 맞춤: 한글이 영문 두 칸 폭인 고정폭 글꼴(나눔고딕코딩)을 웹 글꼴로 불러 쓴다.
★PNG 는 Edge 무인 모드로 2배 크기로 찍고 아래 빈 곳을 잘라 낸다 — Edge 는 한글 경로에 못 써서 임시 폴더에 찍고 옮긴다.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import re

import markdown
from PIL import Image, ImageChops

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ver = sys.argv[1] if len(sys.argv) > 1 else "v8"
md_path = OUT / f"triPilot_Multi-Agent구조도_{ver}.md"
md = md_path.read_text(encoding="utf-8")

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Nanum+Gothic+Coding:wght@400;700&family=Noto+Sans+KR:wght@400;700&display=swap');
:root{--ink:#1f2328;--muted:#59636e;--rule:#d1d9e0;--code:#f6f8fa;--accent:#0969da}
html{background:#fff}
body{margin:0;background:#fff;color:var(--ink);font-family:'Noto Sans KR','Malgun Gothic',sans-serif;font-size:16px;line-height:1.65}
main{max-width:1000px;margin:0 auto;padding:36px 32px 48px}
h1,h2,h3{line-height:1.3;margin:32px 0 14px}
h2{font-size:24px;padding-bottom:8px;border-bottom:1px solid var(--rule)}
h3{font-size:19px}
p{margin:0 0 14px}
strong{font-weight:700}
code{font-family:'Nanum Gothic Coding','D2Coding',monospace;background:rgba(175,184,193,.2);padding:.15em .4em;border-radius:6px;font-size:90%}
pre{background:var(--code);border:1px solid var(--rule);border-radius:8px;padding:18px 20px;overflow-x:auto;margin:0 0 18px}
pre code{background:none;padding:0;font-size:15px;line-height:1.32;font-family:'Nanum Gothic Coding',monospace;white-space:pre;display:block}
table{border-collapse:collapse;width:100%;margin:0 0 18px;font-size:14.5px}
th,td{border:1px solid var(--rule);padding:7px 12px;text-align:left;vertical-align:top}
th{background:var(--code);font-weight:700}
tr:nth-child(2n) td{background:#fbfcfd}
pre.art{padding:16px 18px;line-height:0}
.grid{font-family:Consolas,'Cascadia Mono','D2Coding',monospace;font-size:14.5px;color:#1f2328;display:inline-block}
.row{white-space:nowrap;height:19px;line-height:19px}
.row span{display:inline-block;text-align:center;overflow:visible;vertical-align:top}
.row .n{width:8px}
.row .w{width:16px;font-family:'Malgun Gothic','Noto Sans KR',sans-serif;font-size:13.5px}
blockquote{margin:0 0 16px;padding:4px 16px;color:var(--muted);border-left:4px solid var(--rule)}
"""

import html as _html
import unicodedata


def cells(text):
    """글자 그림을 칸 단위 span 으로 — 한글 2칸 · 나머지 1칸. 글꼴 폭이 달라도 줄이 맞는다"""
    out = []
    for ln in text.split(chr(10)):
        row = []
        for c in ln:
            wide = unicodedata.east_asian_width(c) in "WF"
            row.append(f'<span class="{"w" if wide else "n"}">{_html.escape(c) if c != " " else "&nbsp;"}</span>')
        out.append('<div class="row">' + "".join(row) + "&nbsp;</div>")
    return '<div class="grid">' + "".join(out) + "</div>"


body = markdown.markdown(md, extensions=["fenced_code", "tables"])
# fenced code(글자 그림) → 칸 그림판
body = re.sub(r'<pre><code class="language-text">(.*?)</code></pre>',
              lambda m: '<pre class="art">' + cells(_html.unescape(m.group(1)).rstrip(chr(10))) + "</pre>", body, flags=re.S)
title = "triPilot Multi-Agent 구조도"
page = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{title}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>')
html_path = OUT / f"triPilot_Multi-Agent구조도_{ver}.html"
html_path.write_text(page, encoding="utf-8")

# 글자 그림만 따로 — 코드 블록 두 개
blocks = []
for m in re.finditer(r"```text\n(.*?)```", md, flags=re.S):
    blocks.append(m.group(1).rstrip("\n"))


def shot(html, png, width):
    tmp = Path(tempfile.mkdtemp(prefix="md_png_"))
    p = tmp / "p.html"
    p.write_text(html, encoding="utf-8")
    raw = tmp / "p.png"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    "--virtual-time-budget=6000", f"--window-size={width},9000", f"--screenshot={raw}", p.as_uri()],
                   capture_output=True, timeout=180)
    im = Image.open(raw).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    box = ImageChops.difference(im, bg).getbbox()
    if box:
        im = im.crop((0, 0, im.size[0], min(im.size[1], box[3] + 60)))
    im.save(png)
    shutil.rmtree(tmp, ignore_errors=True)
    print("ok", png.name, im.size)


shot(page, OUT / f"triPilot_Multi-Agent구조도_{ver}.png", 1064)
names = ["그림1_전체구조도", "그림2_툴데이터계층"]
for name, b in zip(names, blocks):
    one = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>{CSS} main{{max-width:none;padding:24px;display:inline-block}} pre{{margin:0}}</style></head>'
           f'<body><main><pre class="art">{cells(b)}</pre></main></body></html>')
    shot(one, OUT / f"{name}_{ver}.png", 1000)
