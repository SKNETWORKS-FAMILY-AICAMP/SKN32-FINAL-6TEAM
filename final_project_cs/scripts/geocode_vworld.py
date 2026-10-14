"""activity_total_data.csv 의 빈 mapx/mapy 를 V-World 지오코더로 채운다.

- 키는 .env 의 ACOP_VWORLD_API_KEY 에서 읽는다(출력·로그에 찍지 않는다).
- 이미 좌표가 있는 행은 건드리지 않는다.
- 도로명 → 지번 순으로 조회하고, 서울 범위를 벗어나면 실패로 처리한다.
- 못 찾은 행은 geocode_failed.csv 로 저장한다(수기 큐레이션 대상).

사용:
    python scripts/geocode_vworld.py --limit 5     # 5건만 시험(파일 수정 없음)
    python scripts/geocode_vworld.py --write       # 전체 실행 후 CSV에 반영
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "app/domains/travel_ops/instances/activity/data_processing/activity_total_data.csv"
FAILED_PATH = CSV_PATH.with_name("geocode_failed.csv")
API = "https://api.vworld.kr/req/address"
SEOUL_LON, SEOUL_LAT = (126.7, 127.3), (37.4, 37.75)


def load_key() -> str:
    key = os.environ.get("ACOP_VWORLD_API_KEY", "")
    for name in (".env.apikeys", ".env"):
        env = ROOT / name
        if key or not env.exists():
            continue
        for line in env.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*ACOP_VWORLD_API_KEY\s*=\s*(.*)", line)
            if m:
                key = m.group(1).strip().strip("\"'")
    if not key:
        sys.exit("ACOP_VWORLD_API_KEY 가 .env.apikeys / .env 에 없습니다.")
    return key


def clean_address(addr: str) -> str:
    a = re.sub(r"(서울특별시\s+)+", "서울특별시 ", addr.strip())
    a = re.sub(r"\(.*?\)", "", a)  # 괄호(동·건물명) 제거
    return re.sub(r"\s+", " ", a).strip()


def query(key: str, address: str, kind: str):
    params = {
        "service": "address", "request": "getcoord", "version": "2.0",
        "crs": "epsg:4326", "address": address, "refine": "true",
        "simple": "false", "format": "json", "type": kind, "key": key,
    }
    try:
        r = requests.get(API, params=params, timeout=10)
        j = r.json()["response"]
    except Exception as e:  # 예외 메시지에 URL(키)이 실릴 수 있어 타입만 출력
        return None, type(e).__name__
    if j.get("status") != "OK":
        return None, j.get("status", "ERROR")
    p = j["result"]["point"]
    lon, lat = float(p["x"]), float(p["y"])
    if not (SEOUL_LON[0] <= lon <= SEOUL_LON[1] and SEOUL_LAT[0] <= lat <= SEOUL_LAT[1]):
        return None, "OUT_OF_SEOUL"
    return (f"{lon:.10f}", f"{lat:.10f}"), "OK"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="처리할 최대 건수(시험용)")
    ap.add_argument("--write", action="store_true", help="CSV 에 반영")
    args = ap.parse_args()

    key = load_key()
    rows = list(csv.reader(CSV_PATH.open(encoding="utf-8-sig", newline="")))
    head, data = rows[0], rows[1:]
    i = {c: head.index(c) for c in head}
    todo = [r for r in data if not r[i["mapx"]].strip() or not r[i["mapy"]].strip()]
    if args.limit:
        todo = todo[: args.limit]
    print(f"대상 {len(todo)}행")

    ok, failed = 0, []
    for n, r in enumerate(todo, 1):
        addr = clean_address(r[i["addr1"]])
        res, why = None, ""
        for kind in ("road", "parcel"):
            res, why = query(key, addr, kind)
            if res:
                break
            time.sleep(0.1)
        if res:
            r[i["mapx"]], r[i["mapy"]] = res
            ok += 1
        else:
            failed.append([r[i["contentid"]], r[i["title"]], r[i["addr1"]], why])
        if not args.write:
            print(n, r[i["title"]], "->", res or why)
        time.sleep(0.1)

    print(f"성공 {ok} / 실패 {len(failed)}")
    if not args.write:
        print("(시험 실행: 파일은 수정하지 않았습니다. 전체 반영은 --write)")
        return
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, lineterminator="\r\n").writerows(rows)
    with FAILED_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(["contentid", "title", "addr1", "reason"])
        w.writerows(failed)
    print(f"CSV 반영 완료 · 실패 목록: {FAILED_PATH.name}")


if __name__ == "__main__":
    main()
