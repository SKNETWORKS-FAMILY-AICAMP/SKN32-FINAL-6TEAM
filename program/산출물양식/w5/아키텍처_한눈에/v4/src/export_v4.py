# -*- coding: utf-8 -*-
"""v4 그림 두 장을 따로 떼어 .svg · .png 로 저장한다.

    python export_v4.py   → ../그림1_멀티에이전트_워크플로_v4.svg · .png, ../그림2_시스템_아키텍처_v4.svg · .png

★SVG 는 문서 없이도 같은 모양이 나오게 스타일을 안에 넣는다(밝은 테마 고정).
★PNG 는 Edge 무인 모드로 2배 크기로 찍는다 — Edge 는 한글 경로에 못 쓰므로 임시 폴더에 찍고 옮긴다.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import make_arch_v4 as m

OUT = Path(__file__).resolve().parent.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

css = re.sub(r"@media \(prefers-color-scheme:dark\)\{.*?\}\}\}", "", m.CSS, flags=re.S)   # 밝은 테마 고정
css = re.sub(r"@media print\{.*?\}\}", "", css, flags=re.S)
css = re.sub(r"body\{[^}]*\}|main\{[^}]*\}|h1\{[^}]*\}|h2\{[^}]*\}|\.lead\{[^}]*\}|\.note\{[^}]*\}|table\{[^}]*\}[^\n]*\n", "", css)

FIGS = [("그림1_멀티에이전트_워크플로_v4", m.workflow), ("그림2_시스템_아키텍처_v4", m.architecture)]
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
