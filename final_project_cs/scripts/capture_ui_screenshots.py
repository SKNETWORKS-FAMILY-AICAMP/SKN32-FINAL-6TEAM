"""운영 UI 화면을 Playwright 로 캡처하고, 캡처하는 김에 실측까지 한다.

★`docs/release_checklist.md` §5-3 의 마지막 미체크 항목("스크린샷 증거
  `docs/screenshots/` 없음 — 텍스트 실측으로 대체")을 채운다.

★**그림만 찍지 않는다.** 이 저장소는 "건수만 세는 검증"으로 두 번 실패했다
  (`CLAUDE.md` §5). 스크린샷은 사람이 봐야 의미가 생기는 증거라, 기계가
  자동으로 판정할 수 있는 것을 같이 잰다:

    - 가로 스크롤(375px 에서 가로밀림 0) — `CLAUDE.md` 상태표의 주장
    - 콘솔 오류 — 화면은 200 이어도 JS 가 죽어 있을 수 있다
    - 화면이 실제로 내용을 담았는지(빈 페이지를 찍고 통과시키지 않는다)

  하나라도 어긋나면 **exit 1** 이다. 그림은 남기되 판정은 숨기지 않는다.

    python -m scripts.capture_ui_screenshots
    python -m scripts.capture_ui_screenshots --base-url http://localhost:8042
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: (파일명, 경로). Case 상세·trace 는 실제 case_id 가 필요해 실행 중에 채운다.
STATIC_SCREENS = (
    ("cases", "/ui/cases"),
    ("approvals", "/ui/approvals"),
    ("voc", "/ui/voc"),
    ("admin", "/ui/admin"),
)

VIEWPORTS = (
    ("desktop", 1280, 900),
    # ★375px 는 `CLAUDE.md` 상태표가 "가로밀림 0" 이라고 주장하는 폭이다.
    ("mobile", 375, 812),
)

#: 내용이 있다고 볼 최소 길이. 빈 껍데기를 찍고 통과시키지 않기 위한 하한이다.
MIN_TEXT_LENGTH = 120

#: ★"비어 있다"와 "비었다고 정직하게 말한다"는 다르다.
#:  이 제품은 데이터가 없을 때 "없음"을 표시하는 것이 **설계**다
#:  (`CLAUDE.md` 상태표: "VOC 데이터 없을 때 '없음'을 정직하게 표시").
#:  그 화면을 짧다는 이유로 결함으로 부르면, 정직하게 만든 쪽이 벌을 받는다.
#:  대신 **비었다는 사실 자체는 결과에 적는다**(`empty_state: true`).
#:
#: ★단 이 마커는 **짧은 화면에서만** 본다. 처음엔 본문 전체에서 찾았는데,
#:  승인 화면의 경고 문구("승인은 되돌릴 수 **없습니다**")가 걸려서 데이터가
#:  1건 들어 있는 화면을 "비어 있다"고 보고했다(2026-09-02 실측). 낱말이
#:  어딘가 있다는 것과 그 화면이 빈 상태라는 것은 다르다.
EMPTY_STATE_MARKERS = ("없음", "없습니다", "비어 있", "표시할 내용")


def _discover_case_id(page, base_url: str) -> str | None:
    page.goto(f"{base_url}/ui/cases", wait_until="networkidle")
    match = re.search(r"/ui/cases/([0-9a-f-]{36})", page.content())
    return match.group(1) if match else None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="운영 UI 스크린샷 캡처 + 실측")
    parser.add_argument("--base-url", default="http://localhost:8042")
    parser.add_argument("--out-dir", default="docs/screenshots")
    parser.add_argument("--theme", default="light", choices=["light", "dark"])
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright 가 없다: pip install playwright && python -m playwright install chromium")
        return 1

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    captured: list[dict] = []
    problems: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            probe = browser.new_page()
            case_id = _discover_case_id(probe, args.base_url)
            probe.close()

            screens = list(STATIC_SCREENS)
            if case_id:
                screens += [("case-detail", f"/ui/cases/{case_id}"),
                            ("case-trace", f"/ui/cases/{case_id}/trace")]
            else:
                # ★조용히 건너뛰지 않는다. Case 가 없으면 그 사실이 결과다.
                problems.append("Case 가 하나도 없어 상세·trace 화면을 캡처하지 못했다 "
                                "(scripts/seed_demo_cases.py 를 먼저 실행한다)")

            for viewport_name, width, height in VIEWPORTS:
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    color_scheme=args.theme,
                )
                page = context.new_page()
                console_errors: list[str] = []
                page.on("console", lambda message: console_errors.append(message.text)
                        if message.type == "error" else None)

                for name, path in screens:
                    console_errors.clear()
                    response = page.goto(f"{args.base_url}{path}", wait_until="networkidle")
                    status = response.status if response else 0
                    text = page.inner_text("body")
                    # 문서가 뷰포트보다 넓으면 가로 스크롤이 생긴다.
                    overflow = page.evaluate(
                        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")

                    filename = f"{name}--{viewport_name}--{args.theme}.png"
                    page.screenshot(path=str(out_dir / filename), full_page=True)

                    empty_state = (len(text) < MIN_TEXT_LENGTH
                                   and any(marker in text for marker in EMPTY_STATE_MARKERS))
                    record = {"screen": name, "path": path, "viewport": viewport_name,
                              "status": status, "text_length": len(text),
                              "empty_state": empty_state,
                              "h_overflow_px": overflow, "console_errors": len(console_errors),
                              "file": filename}
                    captured.append(record)

                    if status != 200:
                        problems.append(f"{path} ({viewport_name}) 가 {status} 를 냈다")
                    if len(text) < MIN_TEXT_LENGTH and not empty_state:
                        problems.append(f"{path} ({viewport_name}) 의 본문이 {len(text)}자뿐인데 "
                                        f"'없음' 표시도 없다 — 빈 화면을 찍었을 수 있다")
                    if overflow > 0:
                        problems.append(f"{path} ({viewport_name}) 에서 가로 스크롤 {overflow}px 발생")
                    if console_errors:
                        problems.append(f"{path} ({viewport_name}) 콘솔 오류 "
                                        f"{len(console_errors)}건: {console_errors[0][:80]}")
                context.close()
        finally:
            browser.close()

    print(json.dumps({"out_dir": str(out_dir.relative_to(ROOT)), "captured": captured},
                     ensure_ascii=False, indent=2))
    print(f"\n스크린샷 {len(captured)}장 → {args.out_dir}")
    empties = sorted({record["path"] for record in captured if record["empty_state"]})
    if empties:
        # ★결함은 아니지만 숨기지도 않는다 — 이 스크린샷이 무엇의 증거인지
        #   보는 사람이 알아야 한다("데이터가 있는 화면"이 아니다).
        print(f"  ※ 데이터 없이 '없음'을 표시한 화면: {', '.join(empties)}")
    if problems:
        print(f"\n★문제 {len(problems)}건 — 조용히 넘기지 않는다:")
        for problem in problems:
            print(f"    {problem}")
        return 1
    print("★전 화면 200 · 본문 있음 · 가로밀림 0 · 콘솔 오류 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
