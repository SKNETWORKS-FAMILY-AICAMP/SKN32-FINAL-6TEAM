"""구글 미연결 시트에서 사람이 찾은 것을 원장 입력 파일로 옮긴다.

    python scripts/dining/google_sheet.py --dry-run     부르고 판정만 보여 준다. 쓰지 않는다
    python scripts/dining/google_sheet.py               구글_연결.csv · 폐업대조 시트에 적는다
    python scripts/dining/google_sheet.py --check       키 없이, 아직 옮기지 않은 행만 센다(rebuild 가 부른다)

시트는 google/구글_미연결_<날짜>.csv (가장 최근 것). google_link.py 가 못 붙인 가게를 사람이
구글 지도에서 찾아 「구글 지도 링크」 칸에 붙이고, 메모에 폐업 · 이전을 적었다.
rebuild 는 이 시트를 읽지 않는다. 그래서 여기서 옮긴다.

    링크가 있다    짧은 링크(maps.app.goo.gl)를 풀어 구글 가게 번호(cid)를 얻고,
                   Text Search 로 cid 가 같은 후보의 place_id 를 찾는다(가게당 1~2 회).
                   사람이 고른 링크라 확인자 · 확인일을 채운다 → 다시 세우면 valid.
    메모 「폐업」  링크가 없으면 폐업대조 시트의 [확인] 영업 여부를 폐업으로 적는다.
                   이미 판정이 적힌 행은 건드리지 않는다.
    따로 볼 것     메모 「이전」 · 「확인」, 같은 구글 가게가 다른 원장 가게에 이미 붙은 것,
                   cid 가 맞는 후보가 없는 것. 적지 않고 목록으로 보여 준다.
                   「이전」 은 링크는 넣고, 새 주소는 사람이 폐업대조 시트에 적는다.

구글이 돌려준 이름 · 주소 · 좌표는 저장하지 않는다(google_link.py 와 같은 약관). place_id 와 링크만 적는다.
키는 ACOP_GOOGLE_MAPS_API_KEY. 환경변수에 없으면 final_project_cs/.env 에서 읽는다.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")
ROOT = os.path.dirname(os.path.dirname(HERE))          # final_project_cs

if hasattr(sys.stdout, "reconfigure"):      # 시험에서 불러올 때는 없다
    sys.stdout.reconfigure(encoding="utf-8")

SHEETS = os.path.join(DINING_DATA, "google", "구글_미연결_[0-9]*.csv")   # 좌표링크 사본은 뺀다
LINKS = os.path.join(DINING_DATA, "google", "구글_연결.csv")
CLOSURE = os.path.join(DINING_DATA, "closure", "폐업대조_*.csv")
REVIEW = os.path.join(DINING_DATA, "_build", "google_sheet_review.csv")
LINK_COL = "구글 지도 링크(찾으면 붙여 넣기)"
LINK_HEAD = ["place_uid", "상호", "place_id", "url", "판정 근거", "붙인 날", "확인자", "확인일", "메모"]

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = "places.id,places.googleMapsUri"
TIMEOUT = 10

#: 「0x357ca47822057c51:0xd02a207d2a448e7a」 — 뒤쪽 16진수가 cid 다.
FTID = re.compile(r"0x[0-9a-f]+:0x([0-9a-f]+)", re.I)


def latest(pattern: str) -> str | None:
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None


def read_csv(path: str) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh)
        return list(r.fieldnames or []), list(r)


def write_csv(path: str, head: list[str], rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=head)
        w.writeheader()
        w.writerows(rows)


# ──────────────────────────────────────────────────────────────
# 링크 → cid → place_id
# ──────────────────────────────────────────────────────────────

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def cid_from_url(url: str) -> tuple[str | None, str]:
    """긴 주소에서 (cid, 구글 가게 이름). 「?cid=」 와 「data=…0x…:0x…」 두 모양을 읽는다."""
    parts = urllib.parse.urlsplit(url)
    cid = urllib.parse.parse_qs(parts.query).get("cid", [None])[0]
    if not cid:
        m = FTID.search(urllib.parse.unquote(url))
        cid = str(int(m.group(1), 16)) if m else None
    m = re.search(r"/maps/place/([^/]+)", parts.path)
    name = urllib.parse.unquote_plus(m.group(1)) if m else ""
    return cid, name


def resolve(link: str) -> tuple[str | None, str]:
    """짧은 링크를 한 번만 따라가 (cid, 이름). 긴 링크면 부르지 않는다."""
    link = link.strip()
    if "maps.app.goo.gl" not in link and "goo.gl" not in link:
        return cid_from_url(link)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        resp = opener.open(link, timeout=TIMEOUT)
        location = resp.headers.get("Location") or resp.geturl()
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location") or ""
    return cid_from_url(location)


def api_key() -> str:
    key = os.environ.get("ACOP_GOOGLE_MAPS_API_KEY", "")
    if key:
        return key
    try:
        for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
            if line.startswith("ACOP_GOOGLE_MAPS_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return ""


def search(query: str, key: str) -> list[dict]:
    body = {"textQuery": query, "languageCode": "ko", "regionCode": "KR", "pageSize": 10}
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": key,
                 "X-Goog-FieldMask": FIELD_MASK})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8")).get("places") or []
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"구글이 거절했다({exc.code}): {detail}") from exc


def pick(candidates: list[dict], cid: str) -> str | None:
    """cid 가 같은 후보의 place_id. 이름 · 거리로 고르지 않는다 — 사람이 고른 가게와 같아야 한다."""
    for cand in candidates:
        got, _ = cid_from_url(cand.get("googleMapsUri") or "")
        if got == cid:
            return cand.get("id")
    return None


def short_address(address: str) -> str:
    """「서울특별시 강동구 성안로3길 27 주문진빌딩」 → 「강동구 성안로3길 27」. 긴 주소는 검색이 빗나간다."""
    text = re.sub(r"\(.*?\)", "", address or "").replace("서울특별시", "")
    m = re.search(r"([가-힣]+구)\s+([가-힣0-9]+(?:로|길))\s*(\d+(?:-\d+)?)", text)
    return " ".join(m.groups()) if m else text.strip()


def place_id_for(cid: str, gname: str, row: dict[str, str], key: str) -> tuple[str | None, int]:
    """(place_id, 부른 횟수). 구글 이름에 짧은 주소 → 자치구 → 이름만, cid 가 맞을 때까지 최대 세 번."""
    name = gname or row.get("상호", "")
    queries = [f"{name} {short_address(row.get('주소', ''))}".strip(),
               f"{name} {row.get('자치구', '')}".strip(), name]
    calls = 0
    for query in dict.fromkeys(queries):
        calls += 1
        pid = pick(search(query, key), cid)
        if pid:
            return pid, calls
    return None, calls


# ──────────────────────────────────────────────────────────────
# 분류
# ──────────────────────────────────────────────────────────────

def plan(sheet_rows: list[dict[str, str]], links: list[dict[str, str]],
         decided: frozenset[str] = frozenset()) -> dict[str, list]:
    """시트 행을 할 일로 나눈다. 부르지 않는다.

    decided 는 폐업대조 시트에서 사람이 이미 판정한 가게(중복 · 폐업 · 상호 변경 …)다. 다시 묻지 않는다.
    """
    linked = {r["place_uid"] for r in links}
    out: dict[str, list] = {"link": [], "closed": [], "review": [], "done": [], "empty": []}
    for row in sheet_rows:
        uid, memo = row["place_uid"].strip(), (row.get("메모") or "").strip()
        link = (row.get(LINK_COL) or "").strip()
        if uid in linked or uid in decided:
            out["done"].append(row)
        elif link and "확인" in memo:
            out["review"].append((row, f"메모: {memo}"))
        elif link:
            out["link"].append(row)
        elif "폐업" in memo:
            out["closed"].append(row)
        else:
            out["empty"].append(row)
    return out


def mark_closed(closure_rows: list[dict[str, str]], uids: set[str], today: str) -> list[str]:
    """폐업대조 시트에 폐업을 적는다. 판정이 이미 있는 행은 두고, 적은 place_uid 를 돌려준다."""
    done = []
    for r in closure_rows:
        if r["place_uid"] in uids and not (r.get("[확인] 영업 여부") or "").strip():
            r["[확인] 영업 여부"] = "폐업"
            r["확인일"] = today
            r["메모"] = "; ".join(x for x in ((r.get("메모") or "").strip(), "구글 미연결 시트에서 폐업 확인") if x)
            done.append(r["place_uid"])
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="부르고 판정만 본다. 쓰지 않는다")
    ap.add_argument("--check", action="store_true", help="키 없이 아직 옮기지 않은 행만 센다")
    ap.add_argument("--by", default="요식 담당", help="확인자 칸에 남는 이름")
    ap.add_argument("--limit", type=int, default=200, help="이번에 볼 링크 행 수")
    args = ap.parse_args(argv)

    sheet = latest(SHEETS)
    if not sheet:
        print("구글 미연결 시트가 없다")
        return 0
    _, rows = read_csv(sheet)
    link_head, links = read_csv(LINKS) if os.path.exists(LINKS) else (LINK_HEAD, [])
    closure = latest(CLOSURE)
    c_head, c_rows = read_csv(closure) if closure else ([], [])
    decided = frozenset(c["place_uid"] for c in c_rows
                        if (c.get("[확인] 영업 여부") or "").strip() not in ("", "영업")
                        and (c.get("확인일") or "").strip())
    todo = plan(rows, links, decided)
    open_closed = [r for r in todo["closed"]
                   if any(c["place_uid"] == r["place_uid"] and not (c.get("[확인] 영업 여부") or "").strip()
                          for c in c_rows)]
    print(f"{os.path.basename(sheet)}: 링크 {len(todo['link'])} · 폐업 {len(open_closed)} · "
          f"따로 볼 것 {len(todo['review'])} · 이미 연결 {len(todo['done'])} · 빈 행 {len(todo['empty'])}")
    if args.check:
        return 0

    key = api_key()
    if todo["link"] and not key:
        print("ACOP_GOOGLE_MAPS_API_KEY 가 비어 있다.", file=sys.stderr)
        return 2

    today = date.today().isoformat()
    used = {}
    for r in links:
        cid, _ = cid_from_url(r.get("url") or "")
        if cid:
            used[cid] = r["상호"]
    review = list(todo["review"])
    new_links, calls = [], 0
    for row in todo["link"][:args.limit]:
        name, memo = row["상호"], (row.get("메모") or "").strip()
        cid, gname = resolve(row[LINK_COL])
        if not cid:
            review.append((row, "링크에서 구글 가게 번호를 읽지 못했다"))
            print(f"  ??   {name}  링크를 읽지 못했다")
            continue
        if cid in used:
            review.append((row, f"같은 구글 가게가 이미 「{used[cid]}」에 붙어 있다"))
            print(f"  중복 {name}  이미 {used[cid]}")
            continue
        pid, n = place_id_for(cid, gname, row, key)
        calls += n
        if not pid:
            review.append((row, "cid 가 맞는 검색 결과가 없다"))
            print(f"  없음 {name}")
            continue
        used[cid] = name
        new_links.append({"place_uid": row["place_uid"], "상호": name, "place_id": pid,
                          "url": f"https://www.google.com/maps?cid={cid}",
                          "판정 근거": "사람이 구글 지도에서 찾은 링크 · cid 일치",
                          "붙인 날": today, "확인자": args.by, "확인일": today, "메모": memo})
        if "이전" in memo:
            review.append((row, "이전 — 링크는 넣었다. 새 주소를 폐업대조 시트에 적는다"))
        print(f"  연결 {name}")

    closed = []
    if not args.dry_run:
        if new_links:
            write_csv(LINKS, link_head, links + new_links)
        if closure and open_closed:
            closed = mark_closed(c_rows, {r["place_uid"] for r in open_closed}, today)
            write_csv(closure, c_head, c_rows)
        os.makedirs(os.path.dirname(REVIEW), exist_ok=True)
        write_csv(REVIEW, ["place_uid", "상호", "링크", "메모", "볼 것"],
                  [{"place_uid": r["place_uid"], "상호": r["상호"], "링크": r.get(LINK_COL, ""),
                    "메모": r.get("메모", ""), "볼 것": why} for r, why in review])

    print(f"\n구글 호출 {calls}회 · 연결 {len(new_links)}{'(쓰지 않음)' if args.dry_run else ''} · "
          f"폐업 표시 {len(closed) if not args.dry_run else len(open_closed)}"
          f"{'(쓰지 않음)' if args.dry_run else ''} · 따로 볼 것 {len(review)}")
    for r, why in review:
        print(f"  볼 것  {r['상호']}  {why}")
    if review and not args.dry_run:
        print(f"목록: {REVIEW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
