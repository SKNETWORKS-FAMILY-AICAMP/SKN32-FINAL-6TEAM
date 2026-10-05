"""요식 원장의 가게를 **인허가 자료**(서울시 일반 · 휴게음식점, `fetch_license.py` 로 받은 것)와 대조해 폐업을 가린다. `[2026-10-05 사용자 지시]`

왜.
    폐업 대조는 사람이 인허가 파일과 카카오맵으로 하던 일이다(팀). 인허가 자료의 영업상태 · 폐업일자는 **정부가 공개한 사실**이라
    같은 주소 · 같은 상호로 폐업 기록만 남은 가게는 사람이 다시 보지 않아도 폐업으로 볼 수 있다.

어떻게 가리나. 가게마다 인허가 후보를 **같은 주소**(도로명 번지 또는 지번)로 모은 뒤 상호가 같은 것만 본다.
    영업      같은 주소 · 같은 상호의 **영업/정상** 기록이 있다 → 영업 확인(아무것도 쓰지 않는다)
    폐업      같은 주소 · 같은 상호의 기록이 **폐업뿐**이고 같은 주소에 다른 영업 기록이 없거나 있어도 상호가 다르다 → 폐업(폐업일자 · 관리번호를 메모에)
    모름      후보가 없다 · 상호가 갈린다 → 건드리지 않는다. ★「인허가에 없다」는 폐업이 아니다(전화 · 오타 · 업종 분류 차이일 수 있다)
    ★옛 상호로 폐업했는데 같은 자리에서 새 상호로 영업 중이면 「상호 변경」일 수 있다 — 폐업으로 단정하지 않고 모름으로 둔다.

결과. `closure/폐업대조_<날짜>.csv` — 앞선 시트(사람이 확인한 행)를 **그대로 이어 담고**, 인허가로 새로 가린 폐업만 확인일 · 메모를 적어 더한다
    (`make_closure_sql.py` 는 가장 최근 시트 하나만 읽는다). 이미 시트에 판정이 있는 가게는 건드리지 않는다.

사용법
    python scripts/dining/license_closure.py --report         가려진 결과 숫자만 본다(시트를 쓰지 않는다)
    python scripts/dining/license_closure.py                  시트를 쓴다
키는 필요 없다(DB 와 raw 의 인허가 CSV 만 읽는다). DB 는 `core_db.py` 와 같은 규칙.
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.environ.get("DINING_DATA") or os.path.join(os.path.dirname(ROOT), "datasets", "dining", "processed")
RAW = os.environ.get("DINING_RAW") or os.path.join(os.path.dirname(ROOT), "datasets", "dining", "raw")
CLOSURE = os.path.join(DATA, "closure")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#: 이 날 이후에 폐업 신고된 것만 자동으로 폐업 처리한다 — 오래전 폐업 기록이 있는데 지금도 목록에 있는 가게는 같은 자리에서 새로 영업을 시작했을 수 있다
#:  (예: 2015 년 폐업 기록의 「루비 떡볶이」는 카카오맵에서 영업 중이었다). ★우리가 고른 값(2023-01-01 — 최근 3년)
RECENT_FROM = "2023-01-01"

_ROAD = re.compile(r"(\S+구)\s+(\S+?(?:대로|로|길)\d*(?:번?길)?)\s*(\d+(?:-\d+)?)")
_JIBUN = re.compile(r"(\S+구)\s+(\S+?[동가])\s+(\d+(?:-\d+)?)")
_PAREN = re.compile(r"[\(\[（【].*?[\)\]）】]")
_BRANCH = re.compile(r"(본점|직영점|\S{1,6}점)$")


def road_key(address: str | None) -> str | None:
    text = _PAREN.sub(" ", unicodedata.normalize("NFKC", address or ""))
    found = _ROAD.search(text)
    return f"{found.group(1)} {found.group(2)} {found.group(3)}" if found else None


def jibun_key(address: str | None) -> str | None:
    text = _PAREN.sub(" ", unicodedata.normalize("NFKC", address or ""))
    found = _JIBUN.search(text)
    return f"{found.group(1)} {found.group(2)} {found.group(3)}" if found else None


def norm_name(name: str | None) -> str:
    text = _PAREN.sub("", unicodedata.normalize("NFKC", name or "")).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", text)


def same_name(a: str, b: str) -> bool:
    """상호가 같은가 — 정규화 후 같거나, 지점 꼬리(`강남점`)만 다르거나, 한쪽이 다른 쪽을 품거나(길이 3 이상) 유사도가 높다."""
    x, y = norm_name(a), norm_name(b)
    if not x or not y:
        return False
    if x == y:
        return True
    sx, sy = _BRANCH.sub("", x), _BRANCH.sub("", y)
    if sx and sx == sy:
        return True
    short, long_ = sorted((x, y), key=len)
    if len(short) >= 3 and short in long_:
        return True
    return SequenceMatcher(None, x, y).ratio() >= 0.8


def load_license() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for kind, pattern in (("일반", "서울시 일반음식점 인허가 정보_*.csv"), ("휴게", "서울시 휴게음식점 인허가 정보_*.csv")):
        files = sorted(glob.glob(os.path.join(RAW, pattern)))
        if not files:
            continue
        with open(files[-1], encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                out.append({"종류": kind, "관리번호": row["MGTNO"].strip(), "상호": row["BPLCNM"].strip(),
                            "상태": row["TRDSTATENM"].strip(), "폐업일": row["DCBYMD"].strip()[:10],
                            "도로명": row["RDNWHLADDR"].strip(), "지번": row["SITEWHLADDR"].strip(),
                            "허가일": row["APVPERMYMD"].strip()[:10], "업태": row["UPTAENM"].strip()})
    return out


def index(records: list[dict[str, str]]) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]]]:
    """(도로명 번지 → 기록들, 지번 → 기록들)."""
    road: dict[str, list[dict[str, str]]] = defaultdict(list)
    jibun: dict[str, list[dict[str, str]]] = defaultdict(list)
    for rec in records:
        key = road_key(rec["도로명"])
        if key:
            road[key].append(rec)
        for jk in {jibun_key(rec["지번"]), jibun_key(rec["도로명"])} - {None}:
            jibun[jk].append(rec)
    return road, jibun


def candidates(by, road_address: str | None, jibun_address: str | None) -> list[dict[str, str]]:
    road, jibun = by
    seen: dict[str, dict[str, str]] = {}
    key = road_key(road_address)
    for rec in road.get(key, []) if key else []:
        seen[rec["관리번호"]] = rec
    for jk in {jibun_key(jibun_address), jibun_key(road_address)} - {None}:
        for rec in jibun.get(jk, []):
            seen[rec["관리번호"]] = rec
    return list(seen.values())


def full_address(address: str | None) -> str:
    """층 · 호수까지 남긴 주소 — 같은 호수인지 가릴 때만 쓴다(`road_key` 는 건물까지만)."""
    text = _PAREN.sub(" ", unicodedata.normalize("NFKC", address or ""))
    return re.sub(r"[\s,]", "", text)


def judge(name: str, found: list[dict[str, str]]) -> tuple[str, dict[str, str] | None, int]:
    """(판정, 근거 기록, 같은 호수에서 영업 중인 다른 상호 수). 판정 = 영업 | 폐업 | 모름 | 후보없음.

    ★건물 하나에 가게가 수십 곳인 곳이 흔하다 — 같은 건물의 다른 영업 가게는 **후임이 아니다.** 상호 변경(후임)으로 보는 것은
      폐업한 기록과 **층 · 호수까지 같은 주소**에서 다른 상호가 영업 중일 때뿐이다.
    ★인허가 「영업」은 영업 중이라는 증거가 못 된다 — 신고가 늦어 실제로는 닫은 가게도 영업으로 남는다(사람이 폐업으로 확인한 46곳 중 22곳이 그랬다, 2026-10-05).
      그래서 「영업」 판정은 아무것도 바꾸지 않고, 쓰는 것은 **폐업 기록이 있는 쪽**뿐이다."""
    if not found:
        return "후보없음", None, 0
    matched = [r for r in found if same_name(name, r["상호"])]
    active = [r for r in matched if r["상태"].startswith("영업")]
    if active:
        return "영업", active[0], 0
    closed = [r for r in matched if r["상태"] == "폐업" and r["폐업일"]]
    if not closed:
        return "모름", None, 0
    latest = max(closed, key=lambda r: r["폐업일"])
    where = full_address(latest["도로명"] or latest["지번"])
    successors = [r for r in found if r["상태"].startswith("영업") and r not in matched
                  and where and full_address(r["도로명"] or r["지번"]) == where]
    if successors:
        return "모름", latest, len(successors)                      # 같은 호수에서 다른 상호가 영업 중 — 상호 변경일 수 있다
    return "폐업", latest, 0


def ledger_places(db: str | None = None) -> list[dict[str, str]]:
    sys.path.insert(0, HERE)
    import core_db                                                          # 같은 폴더 — DB 이름 규칙을 같이 쓴다
    import psycopg

    dsn = core_db.dsn() if not db else f"postgresql://postgres@localhost:{os.environ.get('DINING_PG_PORT', '5433')}/{db}"
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT place_uid::text, name_ko, coalesce(road_address,''), coalesce(jibun_address,''), record_status, "
                    "coalesce(area,'') FROM dining.dn_place WHERE NOT is_synthetic")
        return [dict(zip(("uid", "name", "road", "jibun", "status", "area"), row)) for row in cur.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--db")
    args = parser.parse_args()
    records = load_license()
    if not records:
        sys.exit("인허가 CSV 가 없다 — 먼저 scripts/dining/fetch_license.py")
    by = index(records)
    places = ledger_places(args.db)
    verdicts: dict[str, list[dict]] = defaultdict(list)
    for place in places:
        kind, rec, n_others = judge(place["name"], candidates(by, place["road"], place["jibun"]))
        verdicts[kind].append({**place, "rec": rec, "others": n_others})
    print(f"인허가 {len(records):,}건 · 원장 {len(places):,}곳")
    for kind in ("영업", "폐업", "모름", "후보없음"):
        print(f"  {kind}: {len(verdicts[kind]):,}곳")
    already_closed = sum(1 for p in verdicts["폐업"] if p["status"] == "closed")
    print(f"  (폐업으로 가려진 중 원장에 이미 closed 인 곳 {already_closed})")
    prior = sorted(glob.glob(os.path.join(CLOSURE, "폐업대조_[0-9]*.csv")))
    if not prior:
        sys.exit("앞선 폐업 대조 시트가 없다")
    with open(prior[-1], encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        columns, rows = list(reader.fieldnames or []), list(reader)
    decided = {r["place_uid"] for r in rows if (r.get("[확인] 영업 여부") or "").strip()}
    drafts = {r["place_uid"]: (r.get("카카오맵 대조(초안)") or "").strip() for r in rows}
    today = date.today().isoformat()
    added, old_closed, conflicts = 0, [], []
    for place in verdicts["폐업"]:
        if place["uid"] in decided or place["status"] == "closed":
            continue
        rec = place["rec"]
        if drafts.get(place["uid"], "").startswith("영업"):
            conflicts.append((place["name"], rec["폐업일"], drafts[place["uid"]]))   # 앞선 카카오맵 대조는 영업이라 했다 — 사람이 다시 본다
            continue
        if rec["폐업일"] < RECENT_FROM:
            old_closed.append((place["name"], rec["폐업일"]))                        # 오래된 폐업 기록 — 자동으로 닫지 않는다
            continue
        rows.append({"place_uid": place["uid"], "상호": place["name"], "자치구": place["area"], "원장 주소": place["road"],
                     "대조 결과": "인허가 폐업", "판단": "폐업", "근거 세기": "강(같은 주소 · 같은 상호 · 폐업일자)",
                     "인허가 상호": rec["상호"], "관리번호": rec["관리번호"],
                     "인허가 주소": rec["도로명"] or rec["지번"], "인허가일자": rec["허가일"],
                     "[확인] 영업 여부": "폐업", "확인일": today,
                     "메모": f"인허가 자료 폐업일자 {rec['폐업일']} (정부 공개자료 자동 대조 · {today})"})
        added += 1
    print(f"  자동 폐업 {added}곳 · 오래된 폐업 기록이라 보류 {len(old_closed)}곳 · 앞선 대조(카카오맵)와 어긋나 보류 {len(conflicts)}곳")
    for name, day, note in conflicts:
        print(f"    어긋남: {name} (인허가 폐업 {day}) ← {note[:50]}")
    for name, day in old_closed:
        print(f"    보류(오래됨): {name} ({day})")
    if args.report:
        return
    target = os.path.join(CLOSURE, f"폐업대조_{today.replace('-', '')}.csv")
    with open(target, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"→ {target} (앞선 시트 {len(rows) - added}행 이어 담음 + 새 폐업 {added}행)")


if __name__ == "__main__":
    main()
