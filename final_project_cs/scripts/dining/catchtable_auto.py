"""브라우저를 직접 몰아 캐치테이블 한 곳을 읽는다. 시험용이며 기본은 꺼져 있다.

먼저 읽을 것 — 이것을 왜 기본으로 켜지 않는가.
    2026-09-22 에 app.catchtable.co.kr/robots.txt 를 직접 확인했다.
    검색엔진 봇 아홉 개만 이름을 대고 /ct/shop/ 등이 열려 있고, 그 뒤가
    User-agent: * / Disallow: / 다. 이 스크립트는 * 에 해당한다.
    읽기만 해도 해당한다. robots 는 애초에 읽기를 두고 하는 규칙이다.

    그래서 이 파일은 있되 저절로 돌지 않는다. 켜는 데 두 가지가 필요하다.

        1  DINING_CATCHTABLE_AUTO=1   환경 변수
        2  --i-know                    명령줄에서 한 번 더

    둘 다 없으면 아무것도 하지 않고 이유를 적은 채 끝난다. 실수로 스케줄러에
    물려도 돌지 않게 하려는 것이다. 무인 반복은 이 파일의 용도가 아니다.

무엇을 하는가.
    사람이 한 번 로그인해 둔 프로필을 그대로 쓴다. 로그인 자체는 하지 않는다.
    계정 정보를 받지 않고, 받을 자리도 두지 않는다.

        홈 → 검색창에 상호 입력 → 결과 첫 곳 → 매장 페이지 → 매장정보
        웨이팅 한 줄과 요일별 영업시간을 읽는다. 그뿐이다.

    예약 버튼을 누르지 않는다. 목록을 훑지 않는다. 한 번에 한 곳이다.

무엇을 지키는가.
    읽은 것은 catchtable.write_answer 로 넘긴다. 본 시각과 신선도와 값 모양을
    따지는 곳이 거기 한 곳이어야 하기 때문이다. 이 파일은 화면에서 글자를
    건져 올릴 뿐 판단하지 않는다.

    로그인이 풀려 화면이 비면 「없다」가 아니라 「모름」이다. 캐치테이블은
    로그인하지 않으면 껍데기만 오므로, 빈 화면을 값으로 읽으면 곧바로
    「웨이팅 없음」이라는 거짓말이 된다.

사용법
    set DINING_CATCHTABLE_AUTO=1
    python scripts/dining/catchtable_auto.py --place 메이플탑 --i-know
    python scripts/dining/catchtable_auto.py --place 메이플탑 --i-know --show

    --show 를 주면 브라우저 창이 보인다. 시연에서는 이쪽이 낫다.
    처음 한 번은 --login 으로 창을 띄워 두고 사람이 직접 로그인한다.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import catchtable                                    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))        # final_project_cs
HOME = "https://app.catchtable.co.kr/"

#: 사람이 로그인해 둔 상태가 사는 곳. 여기만 있으면 다시 로그인하지 않는다.
#: 저장소 밖이 아니라 _build 아래에 둔다. .gitignore 가 이미 _build 를 막는다.
PROFILE = os.path.join(ROOT, "data", "dining", "_build", "catchtable_profile")

#: 한 걸음마다 기다리는 상한. 넘으면 모름으로 끝낸다. 매달리지 않는다.
STEP_MS = 15000


def guard(args) -> str | None:
    """켜져 있는가. 꺼져 있으면 왜 안 도는지 한 줄로 돌려준다."""
    if os.environ.get("DINING_CATCHTABLE_AUTO") != "1":
        return "DINING_CATCHTABLE_AUTO=1 이 없다"
    if not args.i_know:
        return "--i-know 가 없다"
    return None


def _num_of_teams(text: str) -> int | None:
    """「현재 웨이팅 41팀」 같은 줄에서 숫자만. 없으면 None 이다.

    「웨이팅이 없어요」에는 숫자가 없다. 그때 0 을 넣는 것은 읽은 것이 아니라
    지어낸 것이므로, 0 은 부르는 쪽에서 붙인다.
    """
    got = re.search(r"(\d+)\s*팀", text)
    return int(got.group(1)) if got else None


def read_one(place_name: str, show: bool) -> dict:
    """한 곳을 읽는다. 돌려주는 것은 {url, seen} 이며 판단은 하지 않는다."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    seen: dict[str, dict] = {}
    url = HOME

    with sync_playwright() as pw:
        # 사람이 로그인해 둔 프로필을 그대로 연다. 로그인은 하지 않는다.
        browser = pw.chromium.launch_persistent_context(
            PROFILE, headless=not show, locale="ko-KR")
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.set_default_timeout(STEP_MS)
        try:
            # 1  홈. /ct/search?keyword= 는 껍데기만 오는 죽은 경로라 쓰지 않는다.
            page.goto(HOME, wait_until="domcontentloaded")

            # 2  검색창에 상호를 친다. 사람이 하던 것과 같은 길이다.
            box = page.get_by_placeholder(re.compile("검색"))
            box.first.click()
            box.first.fill(place_name)
            page.keyboard.press("Enter")
            page.wait_for_timeout(2500)

            # 3  결과에서 그 이름을 고른다. 없으면 여기서 끝이다.
            hit = page.get_by_text(place_name, exact=False).first
            hit.click()
            page.wait_for_timeout(3000)
            url = page.url

            body = page.inner_text("body")
            if "웨이팅" in body:
                if "웨이팅이 없어요" in body:
                    seen["waiting"] = {"state": "no", "num": 0,
                                       "detail": "웨이팅이 없어요"}
                else:
                    line = next((l for l in body.splitlines()
                                 if "웨이팅" in l and "팀" in l), "")
                    teams = _num_of_teams(line)
                    if teams is not None:
                        seen["waiting"] = {"state": "yes", "num": teams,
                                           "detail": line.strip()[:120]}
                    # 숫자를 못 찾았으면 아무것도 적지 않는다. 빈 칸이 모름이다.

            # 4  매장정보. 요일별 영업시간과 라스트오더가 여기에 있다.
            if "/ct/shop/" in url:
                info = url.split("?")[0].rstrip("/") + "/info"
                page.goto(info, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                text = page.inner_text("body")
                hours = [l.strip() for l in text.splitlines()
                         if re.match(r"^[월화수목금토일]\s*·", l.strip())]
                if hours:
                    seen["hours"] = {"state": "unknown",
                                     "detail": " / ".join(hours)[:200]}
                    # state 가 unknown 인 이유. 이 파일은 화면을 옮겨 적을 뿐이고
                    # 우리 원장과 같은지 다른지는 사람이 대조해 정한다.

        except PWTimeout:
            # 매달리지 않는다. 못 읽은 것은 빈 칸으로 남고 그것이 모름이다.
            pass
        finally:
            browser.close()

    return {"url": url, "seen": seen}


def cmd_login(show: bool) -> int:
    """창을 띄워 두고 사람이 직접 로그인한다. 여기서 계정 정보를 받지 않는다."""
    from playwright.sync_api import sync_playwright

    print("창이 열린다. 직접 로그인한 뒤 이 화면에서 Enter 를 눌러라.")
    print("계정 정보는 이 스크립트가 받지 않는다. 로그인 상태만 프로필에 남는다.")
    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(
            PROFILE, headless=False, locale="ko-KR")
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto(HOME)
        try:
            input("  로그인이 끝났으면 Enter > ")
        except EOFError:
            pass
        browser.close()
    print(f"프로필에 남았다: {PROFILE}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="브라우저를 몰아 한 곳을 읽는다. 시험용이며 기본은 꺼져 있다.")
    ap.add_argument("--place", help="상호명")
    ap.add_argument("--uid", help="place_uid. 주면 답 파일을 그 이름으로 놓는다")
    ap.add_argument("--i-know", action="store_true",
                    help="robots.txt 를 알고도 켠다")
    ap.add_argument("--show", action="store_true", help="창을 보이게")
    ap.add_argument("--login", action="store_true", help="한 번만. 사람이 로그인")
    args = ap.parse_args()

    if args.login:
        return cmd_login(args.show)

    stopped = guard(args)
    if stopped:
        print("돌지 않는다 — " + stopped)
        print()
        print("  이 파일은 저절로 돌지 않게 되어 있다.")
        print("  app.catchtable.co.kr/robots.txt 가 User-agent: * / Disallow: / 다.")
        print("  무인 반복은 이 파일의 용도가 아니다. 시험으로 한 번 볼 때만 켠다.")
        return 1

    if not args.place:
        print("--place 가 필요하다. 한 번에 한 곳이다.")
        return 2

    if not os.path.isdir(PROFILE):
        print("로그인해 둔 프로필이 없다. 먼저 --login 으로 한 번 로그인해라.")
        return 1

    print(f"{args.place} — 한 곳만 읽는다")
    got = read_one(args.place, args.show)
    seen = got["seen"]

    if not seen:
        # 로그인이 풀렸거나 못 찾았다. 어느 쪽이든 「없다」가 아니라 「모름」이다.
        print("  아무것도 읽지 못했다. 로그인이 풀렸거나 그 이름을 못 찾았다.")
        print("  값을 적지 않는다. 읽지 못한 것은 모름이다.")
        return 1

    for topic, one in seen.items():
        print(f"  {topic:8s} {one.get('state'):8s} "
              f"{one.get('num', '')} {one.get('detail', '')}".rstrip())

    if args.uid:
        path = catchtable.write_answer(args.uid, got["url"], seen)
        print(f"  답 놓음: {path}")
        print(f"  이제: run_check.py answer 없이도 run --backend catchtable 로 주워진다")
    else:
        print("  --uid 를 주면 답 파일로 놓는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
