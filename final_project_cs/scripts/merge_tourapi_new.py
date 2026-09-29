"""TourAPI 서울 목록(tourapi_seoul_list.csv)에서 activity_total_data.csv 에 없는 장소를 추가한다.

- 이름과 주소가 **모두** 같은 장소는 이미 있는 것으로 보고 넣지 않는다.
- 이미 contentid 가 있는 행은 넣지 않는다.
- 커밋 이력에서 **의도적으로 지운 행**(폐점·중복 정리)은 다시 넣지 않는다.
- 새 행은 21개 컬럼 형식으로 만든다. 상세(영업시간·개요 등)는 비워 둔다 — 상세 수집은 별도 단계다.
- sigungucode 는 주소의 구 이름으로 채운다(TourAPI 는 지역코드가 빈 행에 시군구 코드를 주지 않는다).

사용:
    python -X utf8 scripts/merge_tourapi_new.py           # 시험(파일 수정 없음, 건수만 출력)
    python -X utf8 scripts/merge_tourapi_new.py --write   # CSV 에 추가
"""
import argparse
import collections
import csv
import difflib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
D = ROOT / "app/modules/travel_ops/activity/data_processing"
CSV_PATH = D / "activity_total_data.csv"
LIST_PATH = D / "tourapi_seoul_list.csv"
DUP_PATH = D / "tourapi_possible_dups.csv"
REL = "final_project_cs/app/modules/travel_ops/activity/data_processing/activity_total_data.csv"


def nt(s: str) -> str:
    """이름 비교용: 공백을 없애고, 끝의 '점'은 뺀다('성수'와 '성수점'은 같은 이름으로 본다)."""
    return re.sub(r"점$", "", re.sub(r"\s+", "", s or ""))


def similar_name(a: str, b: str) -> bool:
    x, y = nt(a), nt(b)
    return x in y or y in x or difflib.SequenceMatcher(None, x, y).ratio() >= 0.6


def addr_key(a: str) -> tuple:
    """도로명+번지가 있으면 그것으로, 없으면 공백·괄호를 뺀 주소 전체로 비교한다."""
    s = re.sub(r"서울(특별시|특별)?", "", a or "")
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"(\S)\s+(\d+길)", r"\1\2", s)
    m = re.search(r"(\S+?(?:로\d*길?|길|대로))\s*(?:지하)?\s*(\d+)", s)
    return ("road", m.group(1), m.group(2)) if m else ("raw", nt(s))


def gu_of(a: str):
    m = re.match(r"\s*(?:서울(?:특별시|특별)?\s+)+(\S+구)", a or "")   # "서울특별 광진구" 같은 오타도 읽는다
    return m.group(1) if m else None


def removed_ids(current: set[str]) -> set[str]:
    """커밋 이력에 있었지만 지금은 없는 contentid — 의도적으로 지운 행이다."""
    commits = subprocess.run(["git", "-C", str(REPO), "log", "--all", "--format=%H", "--", REL],
                             capture_output=True, text=True, encoding="utf-8").stdout.split()
    ever: set[str] = set()
    for c in commits:
        out = subprocess.run(["git", "-C", str(REPO), "show", f"{c}:{REL}"], capture_output=True).stdout
        if not out:
            continue
        for row in csv.reader(out.decode("utf-8-sig", "replace").splitlines()):
            if row:
                ever.add(row[0])
    ever.discard("contentid")
    return ever - current


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    cur_rows = list(csv.reader(CSV_PATH.open(encoding="utf-8-sig", newline="")))
    head, cur = cur_rows[0], cur_rows[1:]
    I = {c: head.index(c) for c in head}
    lst = list(csv.DictReader(LIST_PATH.open(encoding="utf-8-sig", newline="")))

    cur_ids = {r[0] for r in cur}
    gone = removed_ids(cur_ids)
    cur_name_addr = {(nt(r[I["title"]]), addr_key(r[I["addr1"]])) for r in cur}
    cur_by_addr = collections.defaultdict(list)
    for r in cur:
        cur_by_addr[addr_key(r[I["addr1"]])].append(r[I["title"]])

    code = collections.defaultdict(collections.Counter)
    for r in cur:
        g = gu_of(r[I["addr1"]])
        if g and r[I["sigungucode"]]:
            code[g][r[I["sigungucode"]]] += 1
    code = {g: c.most_common(1)[0][0] for g, c in code.items()}

    stat = collections.Counter()
    add, seen, maybe = [], set(), []
    for r in lst:
        cid = r["contentid"]
        if cid in cur_ids:
            stat["이미 contentid 있음"] += 1
            continue
        if cid in gone:
            stat["의도적으로 지운 행(재추가 방지)"] += 1
            continue
        na = (nt(r["title"]), addr_key(r["addr1"]))
        if na in cur_name_addr:
            stat["이름·주소 같음(제외)"] += 1
            continue
        if na in seen:
            stat["목록 안 중복(제외)"] += 1
            continue
        seen.add(na)
        add.append(r)
        # 같은 도로명+번지에 이름이 비슷한 기존 행이 있으면 중복 가능성으로 표시한다
        # (같은 건물의 다른 매장은 이름이 비슷하지 않아 표시하지 않는다).
        same_addr = cur_by_addr.get(addr_key(r["addr1"])) if addr_key(r["addr1"])[0] == "road" else None
        near = [t for t in (same_addr or []) if similar_name(r["title"], t)]
        if near:
            maybe.append([cid, r["title"], r["addr1"], " | ".join(near[:3])])

    print(f"TourAPI 목록 {len(lst)}행 | 현재 CSV {len(cur)}행")
    for k, v in stat.items():
        print(f"  {k}: {v}")
    print(f"  ⇒ 추가할 장소: {len(add)}건")
    by = collections.Counter(r["lclsSystm1"] for r in add)
    print("  분류별:", ", ".join(f"{k} {v}" for k, v in sorted(by.items())))
    nog = [r for r in add if gu_of(r["addr1"]) not in code]
    print(f"  구 코드를 못 찾는 행: {len(nog)} {[r['title'] for r in nog[:5]]}")
    print(f"  주소는 같고 이름이 비슷해 중복일 수 있는 추가 행: {len(maybe)} ({DUP_PATH.name} 에 저장)")

    if not args.write:
        print("\n(시험 실행: 파일은 수정하지 않았습니다. 반영은 --write)")
        return
    new_rows = []
    for r in add:
        row = [""] * len(head)
        for c in ("contentid", "contenttypeid", "title", "addr1", "addr2", "mapx", "mapy", "firstimage",
                  "cpyrhtDivCd", "lclsSystm1", "lclsSystm2", "lclsSystm3"):
            row[I[c]] = r.get(c, "") or ""
        row[I["sigungucode"]] = code.get(gu_of(r["addr1"]), "")
        row[I["data_source"]] = "tour_api"
        new_rows.append(row)
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, lineterminator="\r\n").writerows([head, *cur, *new_rows])
    with DUP_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(["contentid", "title(추가됨)", "addr1", "같은 주소의 기존 행"])
        w.writerows(maybe)
    print(f"\nCSV 에 {len(new_rows)}행 추가 완료 → 전체 {len(cur) + len(new_rows)}행")


if __name__ == "__main__":
    main()
