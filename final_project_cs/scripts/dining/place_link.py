"""가게 링크를 넣는다. 단축 주소는 한 번 따라가 긴 주소로 바꿔 넣는다.

왜 바꾸는가.
    naver.me/…, maps.app.goo.gl/… 은 눌러서 쓰는 데는 문제가 없다. 그러나 모양만으로는
    어느 가게인지 알 수 없어서 DB 의 모양 검사와 중복 검사가 무력해진다(035 머리말).
    공유 버튼으로 복사한 것을 그대로 붙여 넣어도 되게 하려고 여기서 바꾼다.

무엇을 여는가.
    단축 주소 서버에 한 번 묻고, 돌려준 「어디로 가라(Location)」만 읽는다.
    목적지 — 네이버·구글 지도 페이지 — 는 열지 않는다. 링크 하나에 요청 한두 번이며
    사람이 넣을 때만 돈다. 무인으로 돌리지 않는다.

무엇을 믿는가.
    모양 규칙은 DB 의 external_ref_url_ok 한 곳에 있다. 여기서는 긴 주소를 한 모양으로
    다듬기만 하고, 넣기 전에 그 함수에 물어본다. 규칙을 여기에 다시 적지 않는다.

사용법
    python scripts/dining/place_link.py add    --place 닥터비건 --kind naver_place --url https://naver.me/5abcXYZ --by 홍길동
    python scripts/dining/place_link.py add    --place 닥터비건 --kind instagram --url https://instagram.com/drvegan_official --by 홍길동 --valid
    python scripts/dining/place_link.py add    ... --dry-run          바꾼 주소만 보고 넣지 않는다
    python scripts/dining/place_link.py list   --place 닥터비건
    python scripts/dining/place_link.py verify --ref <ref_id> --by 홍길동    열어 보니 맞다
    python scripts/dining/place_link.py dead   --ref <ref_id> --by 홍길동    열어 보니 죽었거나 다른 가게다

    --valid 는 지금 넣는 사람이 방금 열어 보고 맞다고 확인했다는 뜻이다. 없으면 candidate 로 들어가
    사용자에게 나가지 않는다.

접속은 run_check.py 와 같다. DINING_DSN 이 있으면 그것을 쓴다.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

HERE = os.path.dirname(os.path.abspath(__file__))

if hasattr(sys.stdout, "reconfigure"):      # 시험에서 불러올 때는 없다
    sys.stdout.reconfigure(encoding="utf-8")

KINDS = ("naver_place", "google_place", "instagram", "tripadvisor", "homepage")

#: 이 호스트면 한 번 따라간다. 목록에 없는 호스트는 따라가지 않는다.
SHORT_HOSTS = {
    "naver.me", "maps.app.goo.gl", "goo.gl", "instagr.am", "bit.ly", "tinyurl.com",
}

#: 단축 주소가 단축 주소로 넘기는 일이 있다. 그 이상은 이상한 것이다.
MAX_HOPS = 3
TIMEOUT = 5
USER_AGENT = "acop-dining-place-link/1 (manual, one request per link)"

#: 인스타의 계정이 아닌 자리. 이 이름으로는 계정을 만들 수 없다.
INSTAGRAM_RESERVED = {"p", "reel", "reels", "stories", "explore", "tv", "accounts"}


class LinkError(ValueError):
    """넣을 수 없는 링크. 무엇이 문제인지 사람이 읽을 말을 담는다."""


# ──────────────────────────────────────────────────────────────
# 단축 주소 따라가기
# ──────────────────────────────────────────────────────────────

class _NoFollow(urllib.request.HTTPRedirectHandler):
    """넘겨주는 곳을 따라가지 않는다. Location 만 읽고 멈추려는 것이다."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def fetch_location(url: str) -> str | None:
    """url 에 한 번 묻고 Location 을 돌려준다. 넘기지 않으면 None 이다.

    본문은 읽지 않는다.
    """
    opener = urllib.request.build_opener(_NoFollow)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(req, timeout=TIMEOUT):
            return None                               # 200 — 넘기지 않았다
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            loc = exc.headers.get("Location")
            return urllib.parse.urljoin(url, loc) if loc else None
        raise LinkError(f"단축 주소가 {exc.code} 로 답했다: {url}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LinkError(f"단축 주소에 닿지 못했다: {url} ({exc})") from exc


def host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def expand(url: str, fetch: Callable[[str], str | None] = fetch_location) -> str:
    """단축 주소면 긴 주소가 나올 때까지 따라간다. 단축 주소가 아니면 그대로 돌려준다.

    fetch 는 시험에서 갈아끼운다.
    """
    seen = [url]
    while host_of(url) in SHORT_HOSTS:
        if len(seen) > MAX_HOPS:
            raise LinkError("단축 주소가 너무 여러 번 넘겼다: " + " → ".join(seen))
        nxt = fetch(url)
        if not nxt:
            raise LinkError(f"단축 주소가 어디로도 넘기지 않았다: {url}")
        if urllib.parse.urlsplit(nxt).scheme not in ("http", "https"):
            raise LinkError(f"단축 주소가 웹 주소가 아닌 곳으로 넘겼다: {nxt}")
        url = nxt
        seen.append(url)
    return url


# ──────────────────────────────────────────────────────────────
# 한 모양으로 다듬기
# ──────────────────────────────────────────────────────────────
#
# 같은 가게가 여러 모양의 주소로 온다. 한 모양으로 다듬어야 중복 검사가 걸린다.
# 여기서 못 다듬는 모양은 그대로 두고, 통과 여부는 DB 가 정한다.

_NAVER_ID = [
    re.compile(r"^https?://(?:m\.)?map\.naver\.com/(?:p|v5)/(?:entry|search/[^/]+)/place/(\d+)"),
    re.compile(r"^https?://(?:m\.|pcmap\.)?place\.naver\.com/[a-z]+/(\d+)"),
    re.compile(r"^https?://map\.naver\.com/.*[?&](?:id|pinId)=(\d+)"),
]


def normalize(kind: str, url: str) -> str:
    url = url.strip()
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()

    if kind == "naver_place":
        for pat in _NAVER_ID:
            m = pat.match(url)
            if m:
                return f"https://map.naver.com/p/entry/place/{m.group(1)}"
        raise LinkError(f"네이버 플레이스 번호를 찾지 못했다: {url}")

    if kind == "google_place":
        if re.fullmatch(r"(?:www\.|maps\.)?google\.(?:com|co\.kr)", host):
            cid = urllib.parse.parse_qs(parts.query).get("cid")
            if cid and cid[0].isdigit():
                return f"https://www.google.com/maps?cid={cid[0]}"
            if parts.path.startswith("/maps/place/"):
                # 물음표 뒤는 추적용이다. 가게를 가리키는 것은 경로에 있다.
                return "https://www.google.com" + parts.path
        raise LinkError(f"구글 지도의 가게 주소가 아니다: {url}")

    if kind == "instagram":
        if host in ("instagram.com", "www.instagram.com", "m.instagram.com"):
            seg = [s for s in parts.path.split("/") if s]
            if len(seg) == 1 and seg[0].lower() not in INSTAGRAM_RESERVED:
                return f"https://www.instagram.com/{seg[0].lower()}/"
            raise LinkError(f"인스타 계정 주소가 아니다(게시물이나 다른 자리): {url}")
        raise LinkError(f"인스타 주소가 아니다: {url}")

    if kind == "tripadvisor":
        m = re.fullmatch(r"(?:www\.|m\.)?tripadvisor\.(co\.kr|com)", host)
        if m and parts.path.startswith("/Restaurant_Review-"):
            return f"https://www.tripadvisor.{m.group(1)}{parts.path}"
        raise LinkError(f"트립어드바이저 식당 주소가 아니다: {url}")

    if kind == "homepage":
        return url

    raise LinkError(f"모르는 kind: {kind}")


def prepare(kind: str, url: str, fetch: Callable[[str], str | None] = fetch_location) -> str:
    """붙여 넣은 것을 넣을 주소로 바꾼다. 따라가고, 다듬는다."""
    if kind not in KINDS:
        raise LinkError(f"kind 는 {', '.join(KINDS)} 중 하나다: {kind}")
    return normalize(kind, expand(url, fetch))


# ──────────────────────────────────────────────────────────────
# DB
# ──────────────────────────────────────────────────────────────

def _run_check():
    """접속과 장소 찾기는 run_check 의 것을 쓴다. 같은 규칙으로 같은 곳을 찾게."""
    sys.path.insert(0, HERE)
    import run_check                                   # noqa: E402
    return run_check


def _already_valid(exc) -> bool:
    """한 가게의 한 kind 에 확인 링크가 이미 있다(035 의 dn_external_ref_one_valid_idx)."""
    return "dn_external_ref_one_valid_idx" in str(exc)


ALREADY_VALID = ("이 가게의 이 kind 에는 확인된 링크가 이미 있다. "
                 "list 로 보고, 옛것이 틀렸으면 dead 로 내린 뒤 다시 하라.")


def cmd_add(args) -> int:
    try:
        url = prepare(args.kind, args.url)
    except LinkError as exc:
        print(f"넣지 않았다: {exc}", file=sys.stderr)
        return 2
    if url != args.url.strip():
        print(f"바꾼 주소: {url}")

    rc = _run_check()
    with rc.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT dining.external_ref_url_ok(%s, %s)", (args.kind, url))
        if not cur.fetchone()[0]:
            print(f"넣지 않았다: {args.kind} 로 받는 주소 모양이 아니다: {url}", file=sys.stderr)
            return 2
        place_uid, name = rc.resolve_place(cur, args.place)

        cur.execute("SELECT place_uid, status FROM dining.dn_external_ref "
                    "WHERE kind = %s AND url = %s AND retired_at IS NULL", (args.kind, url))
        row = cur.fetchone()
        if row:
            other, status = row
            where = "이 가게에" if str(other) == str(place_uid) else f"다른 가게({other})에"
            print(f"넣지 않았다: 같은 링크가 이미 {where} {status} 로 있다.", file=sys.stderr)
            return 2

        if args.dry_run:
            print(f"넣을 것: {name} {args.kind} {url} ({'valid' if args.valid else 'candidate'})")
            return 0

        import psycopg
        try:
            cur.execute(
                "INSERT INTO dining.dn_external_ref (place_uid, kind, url, status, entered_by, "
                "verified_by, verified_at, note) VALUES (%s, %s, %s, %s, %s, %s, "
                "CASE WHEN %s THEN now() END, %s) RETURNING ref_id",
                (place_uid, args.kind, url, "valid" if args.valid else "candidate", args.by,
                 args.by if args.valid else None, args.valid, args.note))
        except psycopg.errors.UniqueViolation as exc:
            if not _already_valid(exc):
                raise
            print(f"넣지 않았다: {ALREADY_VALID}", file=sys.stderr)
            return 2
        ref_id = cur.fetchone()[0]
        conn.commit()
    print(f"넣었다: {name} {args.kind} {'valid' if args.valid else 'candidate'}  ref={ref_id}")
    if not args.valid:
        print("  열어 보고 맞으면: place_link.py verify --ref", ref_id, "--by", args.by)
    return 0


def _set_status(args, status: str) -> int:
    rc = _run_check()
    with rc.connect() as conn, conn.cursor() as cur:
        import psycopg
        try:
            cur.execute(
                "UPDATE dining.dn_external_ref SET status = %s, verified_by = %s, "
                "verified_at = now() WHERE ref_id = %s AND retired_at IS NULL "
                "RETURNING place_uid, kind, url",
                (status, args.by, args.ref))
        except psycopg.errors.UniqueViolation as exc:
            if not _already_valid(exc):
                raise
            print(f"바꾸지 않았다: {ALREADY_VALID}", file=sys.stderr)
            return 2
        row = cur.fetchone()
        if not row:
            print(f"그런 링크가 없다: {args.ref}", file=sys.stderr)
            return 2
        conn.commit()
    print(f"{status}: {row[1]} {row[2]}")
    return 0


def cmd_verify(args) -> int:
    return _set_status(args, "valid")


def cmd_dead(args) -> int:
    return _set_status(args, "dead")


def cmd_list(args) -> int:
    rc = _run_check()
    with rc.connect() as conn, conn.cursor() as cur:
        place_uid, name = rc.resolve_place(cur, args.place)
        cur.execute(
            "SELECT ref_id, kind, status, url, entered_by, verified_by FROM dining.dn_external_ref "
            "WHERE place_uid = %s AND retired_at IS NULL ORDER BY kind, status", (place_uid,))
        rows = cur.fetchall()
    print(f"{name} ({place_uid})")
    if not rows:
        print("  링크 없음")
    for ref_id, kind, status, url, by, vby in rows:
        print(f"  {kind:13s} {status:9s} {url}")
        print(f"  {'':13s} ref={ref_id} 넣은이={by} 확인={vby or '-'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="가게 링크를 넣는다.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="링크 하나를 넣는다")
    p.add_argument("--place", required=True, help="상호나 place_uid")
    p.add_argument("--kind", required=True, choices=KINDS)
    p.add_argument("--url", required=True, help="단축 주소도 된다")
    p.add_argument("--by", required=True, help="넣는 사람")
    p.add_argument("--valid", action="store_true", help="방금 열어 보고 맞다고 확인했다")
    p.add_argument("--note")
    p.add_argument("--dry-run", action="store_true", help="바꾼 주소만 보고 넣지 않는다")
    p.set_defaults(func=cmd_add)

    for name, func, doc in (("verify", cmd_verify, "열어 보니 맞다"),
                            ("dead", cmd_dead, "열어 보니 죽었거나 다른 가게다")):
        p = sub.add_parser(name, help=doc)
        p.add_argument("--ref", required=True)
        p.add_argument("--by", required=True)
        p.set_defaults(func=func)

    p = sub.add_parser("list", help="한 가게의 링크를 본다")
    p.add_argument("--place", required=True)
    p.set_defaults(func=cmd_list)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
