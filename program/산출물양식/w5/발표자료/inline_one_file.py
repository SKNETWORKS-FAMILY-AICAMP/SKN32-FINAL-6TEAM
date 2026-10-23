# -*- coding: utf-8 -*-
"""발표 HTML 의 그림(src="../assets/...")을 base64 로 파일 안에 넣어, HTML 한 파일만으로 열리게 만든다.

    python inline_one_file.py <입력 html> <출력 html>

글꼴은 인터넷(CDN)에서 받는다 — 인터넷이 없으면 맑은 고딕으로 보인다.
"""
import base64
import mimetypes
import re
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
html = src.read_text(encoding="utf-8")
cache = {}


def to_data(rel):
    p = (src.parent / rel).resolve()
    if p not in cache:
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        cache[p] = f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    return cache[p]


n = 0


def rep(m):
    global n
    n += 1
    return f'{m.group(1)}="{to_data(m.group(2))}"'


html = re.sub(r'(src|href)="(\.\./assets/[^"]+\.(?:jpg|jpeg|png|svg|webp))"', rep, html)
left = re.findall(r'\.\./assets/', html)
dst.write_text(html, encoding="utf-8")
print(f"그림 {n}곳을 파일 안에 넣음(서로 다른 그림 {len(cache)}개) · 남은 외부 그림 참조 {len(left)}곳 · {dst.stat().st_size / 1024 / 1024:.1f} MB → {dst}")
