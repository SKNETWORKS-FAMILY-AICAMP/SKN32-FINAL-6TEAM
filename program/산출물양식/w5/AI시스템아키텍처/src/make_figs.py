# -*- coding: utf-8 -*-
"""산출물 그림을 그림/ 폴더에 SVG · HTML · PNG 로 뽑는다. 규칙 검사(dd.Fig.check)가 하나라도 걸리면 멈춘다.

    python make_figs.py [--no-png]
"""
import sys
from pathlib import Path

import build_lib as base
from fig_agents import fig_agents
from fig_mas import fig_mas
from figs_more import fig_containers, fig_sequence
from figs_new import fig_context, fig_failures, fig_states

OUT = Path(__file__).resolve().parent.parent / "그림"
base.OUT = OUT
base.VER = VER = "v1"
ALL = [("그림1_시스템맥락도", fig_context), ("그림2_컨테이너도", fig_containers), ("그림3_에이전트아키텍처", fig_agents),
       ("그림4_케이스상태전이도", fig_states), ("그림5_멀티에이전트워크플로", fig_mas), ("그림6_대표시나리오순서도", fig_sequence),
       ("그림7_장애대응지도", fig_failures)]


def main():
    OUT.mkdir(exist_ok=True)
    figs = [(n, fn()) for n, fn in ALL]
    bad = False
    for n, f in figs:
        e = f.check()
        if e:
            print(n, "규칙 검사 실패:", e)
            bad = True
    if bad:
        sys.exit(1)
    for n, f in figs:
        (OUT / f"{n}_{VER}.html").write_text(base.fig_html(n, f), encoding="utf-8")
        (OUT / f"{n}_{VER}.svg").write_text(base.svg_file(f), encoding="utf-8")
    if "--no-png" in sys.argv:
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch()
        for n, f in figs:
            page = br.new_page(device_scale_factor=2, viewport={"width": 1280, "height": 900})
            page.goto((OUT / f"{n}_{VER}.html").as_uri(), wait_until="load", timeout=60000)
            page.wait_for_timeout(2500)
            page.evaluate("document.fonts.ready.then(() => true)")
            page.locator("svg").first.screenshot(path=str(OUT / f"{n}_{VER}.png"))
            print("png", n)
            page.close()
        br.close()


if __name__ == "__main__":
    main()
