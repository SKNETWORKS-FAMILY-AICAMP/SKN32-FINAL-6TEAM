"""서울시 일반음식점 · 휴게음식점 **인허가 정보**(지방행정 인허가, 사업자 등록)를 서울 열린데이터광장 오픈API 로 전부 받아 CSV 로 둔다. `[2026-10-05]`

왜.
    ① **폐업 대조** — 인허가 자료의 영업상태(`TRDSTATENM`)와 폐업일자(`DCBYMD`)로 요식 목록의 가게가 지금도 영업하는지 가린다.
       전에는 팀이 이 파일을 손으로 내려받아 대조했다(팀 드라이브 `raw/서울시 *음식점 인허가 정보.csv`, 9/20 기준). 이제 스크립트로 최신을 받는다.
    ② **목록 넓히기** — 관광공사 음식점은 1,600곳뿐이다. 인허가 자료는 서울 영업 중 음식점 전체다(상호 · 주소 · 전화 · 업태 · 좌표).

서비스. LOCALDATA_072404(일반음식점) · LOCALDATA_072405(휴게음식점). 한 번에 1,000행. 폐업 이력까지 모두 들어 있어 일반음식점만 50만 건이 넘는다.
    키 `ACOP_SEOUL_OPENAPI_KEY`(없으면 환경변수 → `.env.apikeys`). 받는 중에 끊겨도 `<이름>.partial.jsonl` 에 쪽마다 쌓아 두어 이어 받는다.

사용법
    python scripts/dining/fetch_license.py --dry-run      건수만 본다
    python scripts/dining/fetch_license.py                 두 서비스 모두
    python scripts/dining/fetch_license.py --only general  일반음식점만

결과: datasets/dining/raw/서울시 일반음식점 인허가 정보_<날짜>.csv · 서울시 휴게음식점 인허가 정보_<날짜>.csv (git 밖).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.environ.get("DINING_RAW") or os.path.join(os.path.dirname(ROOT), "datasets", "dining", "raw")
SERVICES = {"general": ("LOCALDATA_072404", "서울시 일반음식점 인허가 정보"),
            "rest": ("LOCALDATA_072405", "서울시 휴게음식점 인허가 정보")}
PAGE = 1000
PAUSE = 0.15
TIMEOUT = 30

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def api_key() -> str:
    key = os.environ.get("ACOP_SEOUL_OPENAPI_KEY", "")
    if not key:
        try:
            with open(os.path.join(ROOT, ".env.apikeys"), encoding="utf-8") as f:
                for line in f:
                    if line.startswith("ACOP_SEOUL_OPENAPI_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
        except FileNotFoundError:
            pass
    return key


def get(url: str, tries: int = 4) -> dict:
    last: Exception | None = None
    for n in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as exc:                                     # noqa: BLE001 — 몇 번은 다시 해 본다
            last = exc
            time.sleep(1.5 * (n + 1))
    raise RuntimeError(f"받지 못했다: {type(last).__name__}")


def page(key: str, service: str, start: int, end: int) -> tuple[int, list[dict]]:
    data = get(f"http://openapi.seoul.go.kr:8088/{key}/json/{service}/{start}/{end}/")
    body = data.get(service)
    if not body:                                                     # 키 오류 · 한도 초과는 RESULT 만 온다
        raise RuntimeError(f"오류 응답: {str(data)[:160]}")
    return int(body.get("list_total_count") or 0), list(body.get("row") or [])


def fetch(name: str, key: str, dry: bool) -> None:
    service, label = SERVICES[name]
    total, _ = page(key, service, 1, 1)
    print(f"{label}: 전체 {total:,}건 ({service})")
    if dry:
        return
    os.makedirs(RAW, exist_ok=True)
    partial = os.path.join(RAW, f"{label}.partial.jsonl")
    done = 0
    if os.path.exists(partial):
        with open(partial, encoding="utf-8") as f:
            done = sum(1 for _ in f)
    rows_written = done
    with open(partial, "a", encoding="utf-8") as out:
        start = done + 1
        while start <= total:
            end = min(start + PAGE - 1, total)
            _, rows = page(key, service, start, end)
            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            rows_written += len(rows)
            if (start // PAGE) % 20 == 0:
                print(f"  {rows_written:,}/{total:,}")
            if not rows:
                break
            start = end + 1
            time.sleep(PAUSE)
    stamp = datetime.now().strftime("%Y%m%d")
    target = os.path.join(RAW, f"{label}_{stamp}.csv")
    with open(partial, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    columns = list(rows[0].keys())
    with open(target, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    os.remove(partial)
    print(f"  → {target} ({len(rows):,}행)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", choices=list(SERVICES))
    args = parser.parse_args()
    key = api_key()
    if not key:
        sys.exit("서울 열린데이터광장 키가 없다(ACOP_SEOUL_OPENAPI_KEY)")
    for name in ([args.only] if args.only else list(SERVICES)):
        fetch(name, key, args.dry_run)


if __name__ == "__main__":
    main()
