"""우리 가게에 구글 place_id 를 붙인다. 붙인 것은 candidate 이고 사람이 열어 보고 확정한다.

왜 붙이는가.
    변동 확인(Place Details)은 place_id 로 부른다. 이름으로 매번 찾으면 동명 가게가 섞이고
    호출도 두 배가 든다. 신원은 한 번만 해소하고 그다음부터는 id 로 본다(013 과 같은 생각).

무엇을 저장하는가.
    place_id 와 가게 링크(https://www.google.com/maps?cid=…) 두 가지뿐이다(036).
    구글이 돌려준 이름, 주소, 좌표는 우리 것과 비교하는 데만 쓰고 저장하지 않는다.
    note 에도 적지 않는다. 적는 것은 우리가 계산한 거리와 판정뿐이다.

무엇을 믿는가.
    자동으로 valid 를 만들지 않는다. 거리와 이름이 맞아도 candidate 로 넣는다.
    candidate 는 사용자에게 나가지 않는다(035). 사람이 열어 보고
        python scripts/dining/place_link.py verify --ref <ref_id> --by 이름
    으로 확정한다.

    후보가 없거나 둘 이상이면 넣지 않는다. 고르지 않는다. 엉뚱한 집을 붙이면
    그 집의 변동을 우리 가게의 변동으로 읽게 된다.

얼마나 부르는가.
    가게 하나에 Text Search 한 번. 기본 --limit 은 ACOP_RATE_GOOGLE_PLACES_PER_DAY(16)다.
    이미 google_place 링크가 있는 가게는 건너뛰므로 날마다 다시 돌리면 이어서 한다.
    붙이지 못한 가게는 MISSES 파일에 적어 두고 다음부터 건너뛴다. 다시 보려면 --retry.
    적지 않으면 못 찾는 가게가 날마다 한도를 먼저 먹는다.
    요청하는 칸(FIELD_MASK)에 따라 요금 등급이 바뀐다. 칸을 늘리기 전에 가격표를 본다.

사용법
    python scripts/dining/google_link.py --dry-run              부르고 판정만 보여 준다. 넣지 않는다
    python scripts/dining/google_link.py --limit 5
    python scripts/dining/google_link.py --place 닥터비건
    python scripts/dining/google_link.py --retry                전에 못 붙인 가게도 다시 본다
    python scripts/dining/google_link.py --by 홍길동             entered_by 에 남는 이름(기본 google_link)
    python scripts/dining/google_link.py --to-sql               구글_연결.csv → 적재 SQL(키 없이, rebuild 가 부른다)

붙인 것은 DB 와 datasets/dining/processed/google/구글_연결.csv 에 함께 남는다. rebuild 는 DB 를 새로 만들므로
CSV 가 원본이다. 열어 보고 맞으면 CSV 의 확인자 · 확인일을 채운다 → 다시 세우면 valid.

키는 ACOP_GOOGLE_MAPS_API_KEY. 접속은 run_check.py 와 같다.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

HERE = os.path.dirname(os.path.abspath(__file__))
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")

if hasattr(sys.stdout, "reconfigure"):      # 시험에서 불러올 때는 없다
    sys.stdout.reconfigure(encoding="utf-8")

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
#: 판정에 필요한 칸만 받는다. 영업시간은 여기서 받지 않는다 — 연결과 변동 확인은 다른 일이다.
FIELD_MASK = ("places.id,places.displayName,places.formattedAddress,"
              "places.location,places.googleMapsUri")
TIMEOUT = 10

#: 우리 좌표와 이만큼 안이어야 같은 가게로 본다(미터). 좌표는 둘 다 건물 입구 근처다.
MAX_DISTANCE_M = 150
#: 찾을 때 이 반경 안을 먼저 본다. 판정 거리보다 넓게 잡아 후보를 놓치지 않는다.
BIAS_RADIUS_M = 500
#: 못 붙인 가게. 우리 uid 와 우리 판정만 적는다. 구글이 돌려준 내용은 적지 않는다.
MISSES = os.path.join(DINING_DATA, "_build", "google_link_misses.json")
#: 붙인 연결의 원본. DB 는 rebuild 때 지워지므로 여기에 남기고 --to-sql 로 다시 넣는다.
#: place_id 와 링크만 적는다(약관). 사람이 열어 보고 맞으면 확인자 · 확인일을 적는다 → valid.
LINKS = os.path.join(DINING_DATA, "google", "구글_연결.csv")
LINK_HEAD = ["place_uid", "상호", "place_id", "url", "판정 근거", "붙인 날", "확인자", "확인일", "메모"]
LINKS_SQL = os.path.join(DINING_DATA, "_build", "google_links.sql")
DEFAULT_LIMIT = int(os.environ.get("ACOP_RATE_GOOGLE_PLACES_PER_DAY", "16"))


@dataclass
class Place:
    place_uid: str
    name: str
    address: str | None
    lat: float
    lng: float


@dataclass
class Verdict:
    """한 가게의 판정. matched 면 place_id 와 url 을 든다."""
    status: str                 # matched / none / ambiguous / far
    place_id: str | None = None
    url: str | None = None
    distance_m: float | None = None
    reason: str = ""


# ──────────────────────────────────────────────────────────────
# 판정
# ──────────────────────────────────────────────────────────────

def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 사이 거리(미터). 서울 안의 몇백 미터라 하버사인이면 충분하다."""
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


#: 상호가 아니라 회사 형태를 적은 말. 「(주)죠티인도레스토랑」 과 「죠티인도레스토랑」 은 같은 이름이다.
CORP_MARKS = re.compile(r"\(주\)|\(유\)|㈜|주식회사|유한회사")
#: 도로명과 건물번호. 「아리수로61길 33」 → ("아리수로61길", "33")
ROAD = re.compile(r"([가-힣0-9]+(?:로|길))\s*(\d+(?:-\d+)?)")


def name_key(name: str) -> str:
    """이름 비교용. 회사 형태, 공백, 기호, 대소문자를 뗀다. 지점명은 same_name 의 포함 검사가 맡는다."""
    text = CORP_MARKS.sub("", unicodedata.normalize("NFKC", name or "")).lower()
    return re.sub(r"[\s\W_]+", "", text)


def road_key(address: str | None) -> tuple[str, str] | None:
    """도로명 주소에서 (도로명, 건물번호). 못 읽으면 None."""
    m = ROAD.search(address or "")
    return (m.group(1), m.group(2)) if m else None


def same_name(ours: str, theirs: str) -> bool:
    """한쪽이 다른 쪽을 품으면 같은 이름으로 본다. 「닥터비건」 과 「닥터비건 성수점」."""
    a, b = name_key(ours), name_key(theirs)
    return bool(a) and bool(b) and (a in b or b in a)


def judge(place: Place, candidates: list[dict[str, Any]],
          normalize: Callable[[str, str], str]) -> Verdict:
    """구글 후보들 가운데 우리 가게 하나를 고른다. 딱 하나일 때만 고른다."""
    near_named: list[tuple[float, dict[str, Any]]] = []
    closest_named: float | None = None
    for cand in candidates:
        loc = cand.get("location") or {}
        title = (cand.get("displayName") or {}).get("text", "")
        if "latitude" not in loc or not same_name(place.name, title):
            continue
        d = distance_m(place.lat, place.lng, loc["latitude"], loc["longitude"])
        closest_named = d if closest_named is None else min(closest_named, d)
        if d <= MAX_DISTANCE_M:
            near_named.append((d, cand))

    if not near_named and closest_named is None:
        # 이름이 달라도 도로명 · 건물번호가 같고 가까우면 같은 가게로 본다.
        # 「33Acre」 와 「33에이커」 처럼 표기만 다른 경우. 같은 건물에 둘 이상이면 고르지 않는다.
        ours = road_key(place.address)
        same_addr = []
        for cand in candidates:
            loc = cand.get("location") or {}
            if ours and "latitude" in loc and road_key(cand.get("formattedAddress")) == ours:
                d = distance_m(place.lat, place.lng, loc["latitude"], loc["longitude"])
                if d <= MAX_DISTANCE_M:
                    same_addr.append((d, cand))
        if len({c["id"] for _, c in same_addr}) > 1:
            return Verdict("ambiguous", reason=f"같은 주소에 {len(same_addr)}곳이 있다")
        if same_addr:
            d, cand = same_addr[0]
            try:
                url = normalize("google_place", cand.get("googleMapsUri") or "")
            except ValueError as exc:
                return Verdict("none", reason=f"가게 주소를 다듬지 못했다: {exc}")
            return Verdict("matched", place_id=cand["id"], url=url, distance_m=d,
                           reason=f"주소 일치 · 이름 표기 다름, {d:.0f}m")

    if not near_named:
        if closest_named is not None:
            return Verdict("far", distance_m=closest_named,
                           reason=f"이름은 맞는데 {closest_named:.0f}m 떨어졌다")
        return Verdict("none", reason=f"후보 {len(candidates)}곳 중 이름이 맞는 곳이 없다")
    if len({c["id"] for _, c in near_named}) > 1:
        return Verdict("ambiguous", reason=f"{len(near_named)}곳이 이름과 거리가 맞는다")

    d, cand = near_named[0]
    try:
        url = normalize("google_place", cand.get("googleMapsUri") or "")
    except ValueError as exc:
        return Verdict("none", reason=f"가게 주소를 다듬지 못했다: {exc}")
    return Verdict("matched", place_id=cand["id"], url=url, distance_m=d,
                   reason=f"이름 일치, {d:.0f}m")


# ──────────────────────────────────────────────────────────────
# 구글
# ──────────────────────────────────────────────────────────────

def search_body(place: Place) -> dict[str, Any]:
    query = " ".join(x for x in (place.name, place.address) if x)
    return {
        "textQuery": query,
        "languageCode": "ko",
        "regionCode": "KR",
        "pageSize": 5,
        "locationBias": {"circle": {
            "center": {"latitude": place.lat, "longitude": place.lng},
            "radius": float(BIAS_RADIUS_M)}},
    }


def search(place: Place, key: str) -> list[dict[str, Any]]:
    """Text Search 한 번. 후보 목록을 돌려준다. 저장하지 않는다."""
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(search_body(place)).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": key,
                 "X-Goog-FieldMask": FIELD_MASK})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8")).get("places") or []
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"구글이 거절했다({exc.code}): {detail}") from exc


# ──────────────────────────────────────────────────────────────
# DB
# ──────────────────────────────────────────────────────────────

def _modules():
    sys.path.insert(0, HERE)
    import place_link                                  # noqa: E402
    import run_check                                   # noqa: E402
    return place_link, run_check


PENDING_SQL = """
SELECT p.place_uid::text, p.name_ko, coalesce(p.road_address, p.jibun_address), p.lat, p.lng
  FROM dining.dn_place p
 WHERE NOT p.is_synthetic
   AND p.record_status <> 'closed'
   AND p.lat IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM dining.dn_external_ref r
                    WHERE r.place_uid = p.place_uid AND r.kind = 'google_place'
                      AND r.retired_at IS NULL)
"""


def load_misses(path: str = MISSES) -> dict[str, dict[str, str]]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_misses(misses: dict[str, dict[str, str]], path: str = MISSES) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(misses, f, ensure_ascii=False, indent=1, sort_keys=True)


def pending(cur, place: str | None, limit: int, skip: set[str] = frozenset()) -> list[Place]:
    """아직 구글 링크가 없는 가게. dead 로 내린 것도 있음으로 본다 — 같은 걸 또 붙이지 않게.

    skip 은 전에 못 붙인 가게다. --place 로 콕 집으면 skip 해도 본다.
    """
    sql, params = PENDING_SQL, []
    if place:
        sql += " AND (p.place_uid::text = %s OR p.name_ko = %s)"
        params += [place, place]
        skip = frozenset()
    elif skip:
        sql += " AND NOT (p.place_uid::text = ANY(%s))"
        params.append(sorted(skip))
    sql += " ORDER BY p.name_ko LIMIT %s"
    params.append(limit)
    cur.execute(sql, params)
    return [Place(*row) for row in cur.fetchall()]


def insert(cur, place: Place, v: Verdict, by: str) -> str | None:
    """candidate 로 넣는다. 같은 id 나 링크가 다른 가게에 있으면 넣지 않는다."""
    cur.execute("SELECT place_uid::text FROM dining.dn_external_ref "
                "WHERE kind = 'google_place' AND retired_at IS NULL "
                "AND (provider_id = %s OR url = %s)", (v.place_id, v.url))
    row = cur.fetchone()
    if row:
        print(f"  넣지 않았다: 같은 구글 가게가 이미 {row[0]} 에 붙어 있다")
        return None
    cur.execute(
        "INSERT INTO dining.dn_external_ref (place_uid, kind, url, provider_id, status, "
        "entered_by, note) VALUES (%s, 'google_place', %s, %s, 'candidate', %s, %s) "
        "RETURNING ref_id",
        (place.place_uid, v.url, v.place_id, by, f"google_link 자동 연결: {v.reason}"))
    return str(cur.fetchone()[0])


def append_link(place: Place, v: Verdict, path: str = LINKS, day: str | None = None) -> None:
    import csv
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(LINK_HEAD)
        w.writerow([place.place_uid, place.name, v.place_id, v.url, v.reason,
                    day or date.today().isoformat(), "", "", ""])


def sync_links(cur, path: str = LINKS) -> int:
    """DB 에는 있는데 CSV 에 없는 연결을 CSV 에 더한다. 파일이 잠겨 못 적은 것을 메운다."""
    import csv
    have = set()
    if os.path.exists(path):
        have = {r["place_uid"] for r in csv.DictReader(open(path, encoding="utf-8-sig"))}
    cur.execute("SELECT r.place_uid::text, p.name_ko, r.provider_id, r.url, "
                "replace(coalesce(r.note, ''), 'google_link 자동 연결: ', ''), r.entered_at::date "
                "FROM dining.dn_external_ref r JOIN dining.dn_place p USING (place_uid) "
                "WHERE r.kind = 'google_place' AND r.retired_at IS NULL ORDER BY p.name_ko")
    added = 0
    for uid, name, pid, url, reason, day in cur.fetchall():
        if uid not in have:
            append_link(Place(uid, name, None, 0.0, 0.0),
                        Verdict("matched", place_id=pid, url=url, reason=reason), path, day=str(day))
            added += 1
    return added


def to_sql(path: str = LINKS, out: str = LINKS_SQL) -> int:
    """구글_연결.csv → 적재 SQL. 확인일이 있으면 valid, 없으면 candidate. 키가 필요 없다."""
    import csv
    q = lambda s: "'" + s.replace("'", "''") + "'"          # noqa: E731
    lines = ["-- 구글 연결. 만든 것: scripts/dining/google_link.py --to-sql", "BEGIN;"]
    n = {"candidate": 0, "valid": 0}
    if os.path.exists(path):
        for r in csv.DictReader(open(path, encoding="utf-8-sig")):
            uid, pid, url = r["place_uid"].strip(), r["place_id"].strip(), r["url"].strip()
            if not (uid and pid and url):
                continue
            by, day = (r.get("확인자") or "").strip(), (r.get("확인일") or "").strip()
            valid = bool(by and day)
            n["valid" if valid else "candidate"] += 1
            lines.append(
                "INSERT INTO dining.dn_external_ref (place_uid, kind, url, provider_id, status, entered_by, "
                "entered_at, verified_by, verified_at, note) "
                f"SELECT {q(uid)}, 'google_place', {q(url)}, {q(pid)}, "
                f"'{'valid' if valid else 'candidate'}', 'google_link', {q(r['붙인 날'] or date.today().isoformat())}, "
                f"{q(by) if valid else 'NULL'}, {q(day) if valid else 'NULL'}, {q('google_link 자동 연결: ' + r['판정 근거'])} "
                f"WHERE EXISTS (SELECT 1 FROM dining.dn_place WHERE place_uid = {q(uid)}) "
                "AND NOT EXISTS (SELECT 1 FROM dining.dn_external_ref x WHERE x.kind = 'google_place' "
                f"AND x.retired_at IS NULL AND (x.place_uid = {q(uid)} OR x.provider_id = {q(pid)}));")
    lines += ["COMMIT;", ""]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"구글 연결 {n} → {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--place", help="가게 이름이나 place_uid 하나만")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--by", default="google_link")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--retry", action="store_true", help="전에 못 붙인 가게도 다시 본다")
    ap.add_argument("--sync-csv", action="store_true", help="DB 의 연결 중 CSV 에 없는 것을 적는다")
    ap.add_argument("--to-sql", action="store_true", help="구글_연결.csv 를 적재 SQL 로(rebuild 가 부른다)")
    args = ap.parse_args(argv)
    if args.to_sql:
        return to_sql()

    key = os.environ.get("ACOP_GOOGLE_MAPS_API_KEY", "")
    if not key:
        print("ACOP_GOOGLE_MAPS_API_KEY 가 비어 있다.", file=sys.stderr)
        return 2

    place_link, run_check = _modules()
    if args.sync_csv:
        with run_check.connect() as conn, conn.cursor() as cur:
            print(f"CSV 에 더한 연결 {sync_links(cur)}곳")
        return 0
    counts: dict[str, int] = {}
    misses = load_misses()
    with run_check.connect() as conn, conn.cursor() as cur:
        todo = pending(cur, args.place, args.limit, set() if args.retry else set(misses))
        print(f"이번에 볼 가게 {len(todo)}곳 (limit {args.limit})")
        for place in todo:
            v = judge(place, search(place, key), place_link.normalize)
            counts[v.status] = counts.get(v.status, 0) + 1
            print(f"{v.status:9s} {place.name}  {v.reason}")
            if args.dry_run:
                continue
            ref_id = insert(cur, place, v, args.by) if v.status == "matched" else None
            if ref_id:
                conn.commit()
                try:
                    append_link(place, v)
                except PermissionError:
                    print("  CSV 가 잠겨 있다(엑셀?). 끝에서 DB 기준으로 다시 적는다")
                misses.pop(place.place_uid, None)
                print(f"  candidate ref={ref_id}  {v.url}")
            else:
                status = v.status if v.status != "matched" else "duplicate"
                misses[place.place_uid] = {"name": place.name, "status": status,
                                           "reason": v.reason, "at": date.today().isoformat()}
            save_misses(misses)
        if not args.dry_run:
            try:
                added = sync_links(cur)
                if added:
                    print(f"CSV 에 빠진 연결 {added}곳을 DB 기준으로 적었다")
            except PermissionError:
                print("CSV 가 잠겨 있어 맞추지 못했다. 파일을 닫고 --sync-csv 로 다시 맞춘다")
    print("합계: " + ", ".join(f"{k} {n}" for k, n in sorted(counts.items())) if counts else "합계: 없음")
    if counts.get("matched") and not args.dry_run:
        print("열어 보고 맞으면: python scripts/dining/place_link.py verify --ref <ref_id> --by 이름")
    return 0


if __name__ == "__main__":
    sys.exit(main())
