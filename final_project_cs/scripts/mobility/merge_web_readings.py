"""복구한 웹 읽기 기록을 검증해 새 파일로 합친다. API는 호출하지 않는다."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LINE = re.compile(r"(G\d+) car (\d+)/(\d+(?:\.\d+)?)/(\d+) rec=(\d+)/(\d+)/(\d+) best=(\d+)/(\d+)/(\d+)")


def merge(base: dict, readings: str) -> dict:
    result = json.loads(json.dumps(base))
    seen = set()
    for line in readings.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        match = LINE.fullmatch(line.strip())
        if match is None:
            raise ValueError(f"읽기 형식 오류: {line}")
        key, minutes, km, fare, *transit = match.groups()
        if key in seen or key in result["routes"]:
            raise ValueError(f"중복 경로: {key}")
        seen.add(key)
        values = list(map(int, transit))
        result["routes"][key] = {
            "car": {"duration_s": int(minutes) * 60, "distance_m": round(float(km) * 1000),
                    "taxi_fare_krw": int(fare), "source": "kakao_map_web", "read_on": "2026-10-07"},
            "transit": {name: dict(zip(("min", "walk_min", "transfers"), values[offset:offset + 3]))
                        for name, offset in (("rec", 0), ("best", 3))},
        }
    result["_meta"]["web_car_count"] = len(seen)
    result["_meta"]["legacy_api_car_count"] = len(base["routes"])
    result["_meta"]["note"] = "원본 40쌍의 자동차는 API 값이다. 추가 웹 기록과 출처를 구분한다. git 밖 로컬 대조용."
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("readings", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = merge(json.loads(args.base.read_text(encoding="utf-8")), args.readings.read_text(encoding="utf-8"))
    # 원본을 덮어쓰지 않는다.
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=1)
        output.write("\n")
    print(f"통합 {len(result['routes'])}쌍, 웹 자동차 {result['_meta']['web_car_count']}쌍")


if __name__ == "__main__":
    main()
