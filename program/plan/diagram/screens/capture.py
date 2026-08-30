# -*- coding: utf-8 -*-
"""화면설계서에 넣을 실제 화면을 Playwright 로 찍는다.

전제
  1) 가짜 대상을 띄운다.        python program/plan/diagram/screens/fake_target.py
  2) 연결된 콘솔을 8064 에 띄운다. 환경변수 CONSOLE_COMPOSER_URL,
     CONSOLE_COMPOSER_ISSUER_SECRET, CONSOLE_INTROSPECTION_URL 를 주고 reload=False 로 띄운다.
  3) 연결 안 한 콘솔을 8065 에 띄운다. 환경변수 없이 띄운다.
  4) 이 스크립트를 실행한다.    python program/plan/diagram/screens/capture.py

결과는 같은 폴더의 shot_*.png 다.

★뷰포트를 1160 으로 잡는다. 콘솔 본문이 최대 1100px 라 그보다 넓게 잡으면
  오른쪽에 흰 여백이 크게 남는다. 문서에 넣으면 그만큼 글씨가 작아진다.
★페이지 전체가 아니라 main 요소만 찍는다. 세로가 5000px 를 넘으면 문서에서 읽을 수 없다.
"""
import os
import sys

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
# screens -> diagram -> plan -> program -> 저장소 루트. 네 단계다.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
TARGET = os.path.join(REPO, "final_project_cs")
Q = TARGET.replace("\\", "%5C").replace(":", "%3A")

CONNECTED = "http://127.0.0.1:8064"
BARE = "http://127.0.0.1:8065"

# 카드 이름으로 펼치고 접는다. 안 쓰는 카드를 펼치면 그림이 쓸데없이 길어진다.
OPEN_ONLY = """
(names) => {
  document.querySelectorAll('details').forEach(d => {
    const t = (d.querySelector('summary') || d).textContent || '';
    d.open = names.some(n => t.includes(n));
  });
}
"""


def snap(page, url, name, open_names, width=1160, max_h=None, start_y=0):
    """main 영역을 찍는다. max_h 를 주면 위에서 그만큼만 잘라 찍는다.

    ★세로가 2000 CSS px 를 넘으면 문서에 6인치로 넣었을 때 글씨를 읽을 수 없다.
      그래서 긴 화면은 위쪽 중요한 부분만 자르고, 나머지는 별도 그림으로 나눈다.
    """
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(url, wait_until="networkidle")
    page.evaluate(OPEN_ONLY, open_names)
    page.wait_for_timeout(500)
    out = os.path.join(HERE, name)
    box = page.locator("main.shell").first.bounding_box()
    if box is None:
        page.screenshot(path=out)
        print("  ", name)
        return
    # ★clip 은 full_page 없이는 뷰포트 안만 잡는다. 뷰포트 아래를 자르려면 full_page 가 필요하다.
    #   start_y 를 주면 그만큼 내려간 지점부터 자른다. 한 화면을 위아래로 나눠 찍을 때 쓴다.
    remain = box["height"] - start_y
    if remain <= 0:
        raise ValueError("start_y 가 화면보다 길다: %s (%s > %s)" % (name, start_y, box["height"]))
    height = min(max_h, remain) if max_h else remain
    if start_y == 0 and (max_h is None or box["height"] <= max_h):
        page.locator("main.shell").first.screenshot(path=out)
    else:
        page.screenshot(path=out, full_page=True,
                        clip={"x": box["x"], "y": box["y"] + start_y,
                              "width": box["width"], "height": height})
    print("  ", name)


with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(device_scale_factor=2)

    print("실제 화면:")
    snap(pg, CONNECTED + "/", "shot_scr01_projects.png", ["프로젝트"])
    snap(pg, CONNECTED + "/project?path=" + Q, "shot_scr02_assembly.png",
         ["조립", "무엇이 막혀", "평가 실행", "연결"], max_h=1150)
    # Composer 는 위쪽 조작부와 아래쪽 구조도를 나눠 찍는다
    snap(pg, CONNECTED + "/composer?path=" + Q, "shot_scr03_composer.png",
         ["빠른 토글", "모듈", "Port", "Team"], max_h=1250)
    snap(pg, CONNECTED + "/composer?path=" + Q, "shot_scr03_structure.png",
         ["구조", "컴포넌트"], max_h=1500)
    # ★SCR-02 는 한 장에 안 들어간다. 위아래로 자르면 카드 하나가 경계에 걸려 잘리므로
    #   설명이 있는 카드는 카드 단위로 찍는다. 문서에 카드 2, 3 설명만 있고 그림이 없다는
    #   지적을 받아 고쳤다(2026-08-29).
    pg.set_viewport_size({"width": 1160, "height": 900})
    pg.goto(CONNECTED + "/project?path=" + Q, wait_until="networkidle")
    pg.wait_for_timeout(400)
    for idx, out in [(2, "shot_scr02_card2_dod.png"), (3, "shot_scr02_card3_eval.png"),
                     (6, "shot_scr02_card5_connections.png")]:
        pg.locator(".card").nth(idx).screenshot(path=os.path.join(HERE, out))
        print("  ", out)
    # SCR-03 편집 폼의 아래쪽(Team 표와 사유와 버튼)도 따로 찍는다.
    snap(pg, CONNECTED + "/composer?path=" + Q, "shot_scr03_composer_lower.png",
         ["빠른 토글", "모듈", "Port", "Team"], max_h=900, start_y=1250)
    snap(pg, BARE + "/composer?path=" + Q, "shot_scr03_not_connected.png", [])

    # 빠른 토글 카드만 따로
    pg.goto(CONNECTED + "/composer?path=" + Q, wait_until="networkidle")
    pg.evaluate(OPEN_ONLY, ["빠른 토글"])
    pg.wait_for_timeout(200)
    card = pg.locator("details").filter(has_text="빠른 토글").first
    if card.count():
        card.screenshot(path=os.path.join(HERE, "shot_scr03_toggle.png"))
        print("   shot_scr03_toggle.png")

    print("목업:")
    for html, out in [("mockup_shop_cs.html", "shot_mockup_shop_cs.png"),
                      ("mockup_personal_agent_mcp.html", "shot_mockup_personal_agent.png"),
                      ("mockup_platform_product.html", "shot_mockup_platform.png")]:
        pg.set_viewport_size({"width": 1290, "height": 1000})
        pg.goto("file:///" + os.path.join(HERE, html).replace("\\", "/"))
        pg.wait_for_timeout(400)
        pg.locator(".wrap").screenshot(path=os.path.join(HERE, out))
        print("  ", out)

    br.close()

print("\n크기:")
for f in sorted(os.listdir(HERE)):
    if f.startswith("shot_") and f.endswith(".png"):
        import struct
        with open(os.path.join(HERE, f), "rb") as fh:
            w, h = struct.unpack(">II", fh.read(24)[16:24])
        print("   %-36s %d x %d" % (f, w, h))
