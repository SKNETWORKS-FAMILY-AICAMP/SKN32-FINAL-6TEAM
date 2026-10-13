# -*- coding: utf-8 -*-
"""v5 그림 두 장을 따로 떼어 .svg · .png 로 저장한다.

    python export_v5.py   → ../그림1_멀티에이전트_워크플로_v5.svg · .png, ../그림2_시스템_구성도_v5.svg · .png

★SVG 는 문서 없이도 같은 모양이 나오게 스타일을 안에 넣는다(밝은 테마 고정).
★PNG 는 Edge 무인 모드로 2배 크기로 찍는다 — Edge 는 한글 경로에 못 쓰므로 임시 폴더에 찍고 옮긴다.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import make_arch_v5 as m

OUT = Path(__file__).resolve().parent.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

css = re.sub(r"@media \(prefers-color-scheme:dark\)\{.*?\}\}\}", "", m.CSS, flags=re.S)   # 밝은 테마 고정
css = re.sub(r"@media print\{.*?\}\}", "", css, flags=re.S)
# ★문서용 규칙만 뺀다 — 앞이 글자 · 점 · 하이픈이면 그림 규칙의 일부라 건드리지 않는다
#  ☆v5 첫 판: 옛 규칙의 `main\{` 가 `.f-main{` 을 지워 그림 2의 주요 흐름 선이 PNG · SVG 에서 사라졌다
css = re.sub(r"(?<![\w.-])(body|main|h1|h2|table|th|td|th,td)\{[^}]*\}|(?<![\w-])\.(lead|note)\{[^}]*\}", "", css)

FIGS = [("그림1_멀티에이전트_워크플로_v5", m.workflow), ("그림2_시스템_구성도_v5", m.architecture)]
tmp = Path(tempfile.mkdtemp(prefix="arch_png_"))
for name, fn in FIGS:
    svg = fn()
    W, H = map(int, re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups())
    svg = svg.replace("<svg ", f'<svg class="diagram" width="{W}" height="{H}" style="background:#ffffff;color:#161c28" ', 1)
    svg = svg.replace(">", f"><style>{css}</style><rect x=\"0\" y=\"0\" width=\"{W}\" height=\"{H}\" fill=\"#ffffff\"/>", 1)
    (OUT / f"{name}.svg").write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + svg, encoding="utf-8")
    page = tmp / "p.html"
    page.write_text(f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;background:#fff}}svg{{display:block}}</style>{svg}', encoding="utf-8")
    png = tmp / "p.png"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    f"--window-size={W},{H}", f"--screenshot={png}", page.as_uri()], capture_output=True, timeout=120)
    shutil.copyfile(png, OUT / f"{name}.png")
    print("ok", name, W, "x", H)
shutil.rmtree(tmp, ignore_errors=True)
