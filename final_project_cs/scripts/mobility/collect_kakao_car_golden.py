# -*- coding: utf-8 -*-
"""카카오 모빌리티 자동차 길찾기로 **장소 쌍마다 자동차 소요·거리·택시 요금**을 받아 시험용 기준 파일에 쓴다. `[2026-10-07 사용자 지시]`

실행(저장소 안에서):  python -m scripts.mobility.collect_kakao_car_golden [--limit N]

- 장소 쌍은 `tests/unit/travel/mobility/golden_pairs_v1.json`(장소 이름·좌표만 — 카카오 값 없음).
- ★약관 · 팀 규칙: 카카오가 준 값은 **저장소에 올리지 않는다**. 결과는 `datasets/mobility/raw/kakao_golden/kakao_routes_v1.json`(`raw/` 는 .gitignore 가 막는다 — 이 PC 안에서만 쓴다).
- ★호출 예산: 하루 상한(`ACOP_RATE_KAKAO_PER_DAY` = 1,000)의 **80%(800회)** 까지만 — DB 호출 예산(`CallBudget`)에 새 줄 `kakao_mobility_directions` 로 센다.
  이 스크립트는 쌍마다 1회만 부른다(40쌍 = 40회). 이어 받기: 이미 받은 쌍은 다시 부르지 않는다.
- 키는 환경(`.env.apikeys` 의 `ACOP_KAKAO_REST_API_KEY`)에서만 읽고 출력·파일에 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import dotenv_values

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAIRS = ROOT / "tests" / "unit" / "travel" / "mobility" / "golden_pairs_v1.json"
OUT = ROOT.parent / "datasets" / "mobility" / "raw" / "kakao_golden" / "kakao_routes_v1.json"      # raw/ 는 .gitignore 가 막는다
URL = "https://apis-navi.kakaomobility.com/v1/directions"
METER = "kakao_mobility_directions"
DAY_SHARE = 0.8            # 하루 상한의 80%
DAY_CAP = 1000
KST = timezone(timedelta(hours=9))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    key = dotenv_values(ROOT / ".env.apikeys").get("ACOP_KAKAO_REST_API_KEY")
    if not key:
        raise SystemExit("ACOP_KAKAO_REST_API_KEY 가 없다")
    import sys
    sys.path.insert(0, str(ROOT))
    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget
    from app.infrastructure.db.session import get_connection

    budget = CallBudget(connection_factory=get_connection, caps={METER: {"month": 30000, "day": DAY_CAP}}, share=DAY_SHARE)
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))["pairs"]
    doc = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"_meta": {}, "routes": {}}
    doc["_meta"].update({"note": "카카오가 준 값 — 저장소에 올리지 않는다(약관·팀 규칙). 이 PC 안에서만 시험·대조에 쓴다.",
                         "car_source": "카카오 모빌리티 자동차 길찾기 v1/directions · priority=RECOMMEND · 호출 시각의 교통 상황"})
    done = refused = 0
    for p in pairs:
        row = doc["routes"].setdefault(p["id"], {})
        if "car" in row:
            continue
        if args.limit and done >= args.limit:
            break
        if not budget.reserve(METER):
            refused += 1
            print(f"{p['id']}: 하루 예산(80%)이 찼다 — 멈춘다")
            break
        r = httpx.get(URL, params={"origin": f"{p['alon']},{p['alat']}", "destination": f"{p['blon']},{p['blat']}",
                                   "priority": "RECOMMEND", "summary": "true"},
                      headers={"Authorization": f"KakaoAK {key}"}, timeout=20)
        read_at = datetime.now(KST).isoformat(timespec="seconds")
        if r.status_code != 200:
            row["car"] = {"error": r.status_code, "read_at": read_at}
            print(f"{p['id']}: 오류 {r.status_code}")
            continue
        route = (r.json().get("routes") or [{}])[0]
        s = route.get("summary") or {}
        if route.get("result_code") != 0:
            row["car"] = {"error": route.get("result_msg"), "read_at": read_at}
            print(f"{p['id']}: {route.get('result_msg')}")
            continue
        row["car"] = {"distance_m": s.get("distance"), "duration_s": s.get("duration"),
                      "taxi_fare_krw": (s.get("fare") or {}).get("taxi"), "toll_krw": (s.get("fare") or {}).get("toll"), "read_at": read_at}
        done += 1
        time.sleep(0.2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ok = sum(1 for v in doc["routes"].values() if "distance_m" in (v.get("car") or {}))
    print(f"받음 {done}건 · 누적 자동차 값 {ok}/{len(pairs)} · 예산 거절 {refused}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
