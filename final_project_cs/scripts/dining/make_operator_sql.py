"""검수자가 확인한 실제 값을 원장에 넣는 SQL 로 바꾼다.

무엇을 하는가.
    대조표에서 검수자가 적은 실제 값을 읽어 operator_check 출처의 규칙으로 만든다.
    같은 요일의 관광공사 규칙은 지우지 않고 retired_at 으로 물러나게 한다.
    지우면 무엇이 어떻게 틀렸는지가 사라진다.

왜 물러나게 해야 하는가.
    day_intervals 는 출처를 가리지 않고 살아 있는 규칙을 모두 돌려준다.
    관광공사 규칙을 그대로 두면 구간이 두 겹으로 겹쳐 판정이 엉킨다.

무엇을 고치는가.
    검수자가 적은 칸만 고친다. 적지 않은 칸은 관광공사 값을 그대로 쓴다.
    「종료만 틀렸다」는 기록을 「전부 다시 넣는다」로 바꾸면 안 적은 것까지 건드리게 된다.

읽는 표기
    11:30                         모든 요일
    [월~금] - 11:00, [토] - 11:30  요일 묶음
    [일, 월, 화] - 20:00           요일 나열
    평일 22:00, 주말 20:30         평일과 주말
    14:30~18:00                   브레이크 구간
    [월~금] - 13:20, 20:00        구간이 둘일 때의 마지막 주문

사용법:  python scripts/dining/make_operator_sql.py [--dry]
출력:    data/dining/_build/operator.sql
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import uuid

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, "data", "dining")
OUT = os.path.join(DATA, "_build")
SHEET = os.path.join(DATA, "truth", "대조표100_검수_2026-09-21.csv")

NS = uuid.UUID("6f1c0d2e-0000-4000-8000-000000000001")
SOURCE = "operator_check"
ENTERED_BY = "hwansj"
VERIFIED_AT = "2026-09-21 20:00+09"
VALID_FROM = "2026-09-21"

DAY_NO = {"월": 1, "화": 2, "수": 3, "목": 4, "금": 5, "토": 6, "일": 7}
ALL_DAYS = [1, 2, 3, 4, 5, 6, 7]
WEEKDAYS = [1, 2, 3, 4, 5]
WEEKEND = [6, 7]

RE_TIME = re.compile(r"(\d{1,2}):(\d{2})")
RE_GROUP = re.compile(r"\[([^\]]+)\]\s*-\s*([^\[]+)")


def to_min(text: str) -> int:
    h, m = RE_TIME.search(text).groups()
    return int(h) * 60 + int(m)


def days_of(label: str) -> list[int]:
    """「월~금」「일, 월, 화」「평일」을 요일 번호로."""
    label = label.strip()
    if "평일" in label:
        return list(WEEKDAYS)
    if "주말" in label:
        return list(WEEKEND)
    span = re.match(r"^([월화수목금토일])\s*~\s*([월화수목금토일])$", label)
    if span:
        a, b = DAY_NO[span.group(1)], DAY_NO[span.group(2)]
        return list(range(a, b + 1)) if a <= b else list(range(a, 8)) + list(range(1, b + 1))
    found = [DAY_NO[c] for c in label if c in DAY_NO]
    return found or list(ALL_DAYS)


def by_day(text: str) -> dict[int, str]:
    """검수자가 쓴 한 칸을 요일별 값으로 펼친다."""
    text = (text or "").strip()
    if not text:
        return {}
    out: dict[int, str] = {}
    groups = RE_GROUP.findall(text)
    if groups:
        for label, value in groups:
            for d in days_of(label):
                out[d] = value.strip().rstrip(",").strip()
        return out
    # 「평일 21:00, 주말 20:40」
    parts = re.findall(r"(평일|주말)\s*([^,]+)", text)
    if parts:
        for label, value in parts:
            for d in days_of(label):
                out[d] = value.strip()
        return out
    # 값 하나면 모든 요일
    for d in ALL_DAYS:
        out[d] = text
    return out


def q(value) -> str:
    if value is None or value == "":
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def build(base: dict, over: dict[str, dict[int, str]], day: int):
    """그 요일의 구간을 만든다. 검수자가 적지 않은 것은 원래 값을 쓴다."""
    ivs = base.get("intervals") or []
    if not ivs:
        return None, "관광공사 구간이 없어 고칠 바탕이 없다"

    open_min = to_min(over["시작"][day]) if day in over.get("시작", {}) else ivs[0]["open_min"]
    close_min = to_min(over["종료"][day]) if day in over.get("종료", {}) else ivs[-1]["close_min"]

    brk = None
    if day in over.get("브레이크", {}):
        times = RE_TIME.findall(over["브레이크"][day])
        if len(times) >= 2:
            brk = (int(times[0][0]) * 60 + int(times[0][1]),
                   int(times[1][0]) * 60 + int(times[1][1]))
    elif len(ivs) >= 2:
        brk = (ivs[0]["close_min"], ivs[1]["open_min"])

    if brk and not (open_min < brk[0] < brk[1] < close_min):
        return None, f"브레이크 {brk} 가 영업 {open_min}~{close_min} 안에 들어가지 않는다"

    spans = [(open_min, brk[0]), (brk[1], close_min)] if brk else [(open_min, close_min)]

    los: list[int | None] = [None] * len(spans)
    if day in over.get("라스트오더", {}):
        found = RE_TIME.findall(over["라스트오더"][day])
        vals = [int(h) * 60 + int(m) for h, m in found]
        if len(vals) == len(spans):
            los = vals
        elif vals:
            los[-1] = vals[-1]          # 값이 하나면 마지막 구간에 붙인다
    else:
        for i, iv in enumerate(ivs[:len(spans)]):
            los[i] = iv.get("last_order_min")

    rows = []
    for i, (o, c) in enumerate(spans):
        lo = los[i]
        if lo is not None and not (o <= lo <= c):
            lo = None                   # 구간 밖이면 버린다. 억지로 맞추지 않는다
        rows.append({"seq": i + 1, "open_min": o, "close_min": c, "last_order_min": lo,
                     "last_order_state": "present" if lo is not None else "unknown"})
    return {"intervals": rows, "break_state": "present" if brk else "none"}, None


def main() -> None:
    dry = "--dry" in sys.argv
    rows = list(csv.DictReader(open(SHEET, encoding="utf-8-sig")))
    parsed = {r["title"].strip(): r for r in json.load(
        open(os.path.join(OUT, "parsed_hours.json"), encoding="utf-8"))}

    lines = ["-- 검수자가 확인한 실제 값. 생성 파일이므로 직접 고치지 않는다.",
             "BEGIN;", "",
             "-- 같은 검수를 다시 넣어도 쌓이지 않게 이 검수자의 것을 먼저 비운다.",
             f"DELETE FROM dining.dn_hours_rule WHERE source_code = '{SOURCE}' "
             f"AND entered_by = '{ENTERED_BY}';",
             "-- 물러나게 했던 관광공사 규칙을 되돌린다. 다시 계산해 다시 물러나게 한다.",
             "UPDATE dining.dn_hours_rule SET retired_at = NULL "
             "WHERE source_code = 'tourapi_kor_food' AND retired_at IS NOT NULL;", ""]

    report, skipped = [], []
    n_rule = n_retire = 0

    for row in rows:
        name = (row.get("상호") or "").strip()
        over = {ko: by_day(row.get(ko, "")) for ko in
                ("시작", "종료", "브레이크", "라스트오더")}
        if not any(over.values()):
            continue
        base_row = parsed.get(name)
        if not base_row:
            skipped.append((name, "파싱 결과에서 못 찾음"))
            continue
        cid = base_row["content_id"]
        place_uid = str(uuid.uuid5(NS, f"place:tourapi:{cid}"))

        days = sorted({d for m in over.values() for d in m})
        for day in days:
            base = base_row["rules"].get(str(day))
            if not base or base.get("coverage") != "intervals":
                skipped.append((f"{name} {day}요일", "바탕 규칙이 없다"))
                continue
            built, why = build(base, over, day)
            if built is None:
                skipped.append((f"{name} {day}요일", why))
                continue

            before = " + ".join(f"{i['open_min']}-{i['close_min']}" for i in base["intervals"])
            after = " + ".join(f"{i['open_min']}-{i['close_min']}" for i in built["intervals"])
            if before != after:
                report.append((name, day, before, after))

            rule_id = str(uuid.uuid5(NS, f"rule:operator:{cid}:{day}"))
            lines.append(
                f"UPDATE dining.dn_hours_rule SET retired_at = now() "
                f"WHERE place_uid = '{place_uid}' AND weekday = {day} "
                f"AND source_code = 'tourapi_kor_food' AND retired_at IS NULL;")
            n_retire += 1
            lines.append(
                "INSERT INTO dining.dn_hours_rule (rule_id, place_uid, source_code, "
                "entered_by, verified_by, verified_at, rule_kind, weekday, coverage, "
                "break_state, source_text, extract_method, rules_version, valid_from) VALUES ("
                f"'{rule_id}', '{place_uid}', '{SOURCE}', '{ENTERED_BY}', '{ENTERED_BY}', "
                f"'{VERIFIED_AT}', 'weekly', {day}, 'intervals', '{built['break_state']}', "
                f"{q('네이버 지도 대조 2026-09-21')}, 'manual', 'operator-2026-09-21', "
                f"'{VALID_FROM}');")
            n_rule += 1
            for iv in built["intervals"]:
                lo = iv["last_order_min"]
                lines.append(
                    "INSERT INTO dining.dn_hours_interval (rule_id, seq, open_min, close_min, "
                    "last_order_min, last_order_state) VALUES ("
                    f"'{rule_id}', {iv['seq']}, {iv['open_min']}, {iv['close_min']}, "
                    f"{lo if lo is not None else 'NULL'}, '{iv['last_order_state']}');")

    # 폐업
    for row in rows:
        if "폐업" in (row.get("틀린방향") or ""):
            name = (row.get("상호") or "").strip()
            base_row = parsed.get(name)
            if base_row:
                uid = str(uuid.uuid5(NS, f"place:tourapi:{base_row['content_id']}"))
                lines.append(f"UPDATE dining.dn_place SET record_status = 'closed', "
                             f"updated_at = now() WHERE place_uid = '{uid}';")
                report.append((name, 0, "unknown", "closed"))

    lines += ["", "COMMIT;"]
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "operator.sql")
    if not dry:
        open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print(f"{'상호':22s} {'요일':4s} {'전':22s} {'후'}")
    for name, day, before, after in report:
        print(f"{name:22s} {day if day else '-':<4} {before:22s} {after}")
    print(f"\n규칙 {n_rule}건, 물러나게 할 관광공사 규칙 {n_retire}건")
    if skipped:
        print(f"\n넣지 못한 것 {len(skipped)}건")
        for what, why in skipped:
            print(f"  {what} — {why}")
    print(f"\n{'(--dry 라 쓰지 않았다)' if dry else '저장: ' + path}")


if __name__ == "__main__":
    main()
