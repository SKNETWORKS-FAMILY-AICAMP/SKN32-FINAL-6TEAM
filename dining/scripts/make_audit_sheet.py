"""오추출률 측정용 대조표를 만든다.

원문과 적재된 값을 나란히 놓고 사람이 맞았는지 표시하는 표다.
지금까지 센 것은 "뽑았나" 였고, 이 표로 재는 것은 "맞게 뽑았나" 다.

표본은 고정 씨앗으로 무작위 추출한다. 어려운 것만 골라 보면
비율이 실제보다 나빠 보이고, 쉬운 것만 보면 좋아 보인다.

사용법:  python make_audit_sheet.py
출력:    오추출_대조표_100.csv  (엑셀에서 열어 표시)
         오추출_대조표_100.html (눈으로 읽기)
"""
from __future__ import annotations

import csv
import html
import json
import os
import random
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")   # 원본 데이터
OUT = ROOT                          # 생성물은 저장소 뿌리에 둔다
SAMPLE = 100
SEED = 20260921

DAY_NAME = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토", 7: "일"}


def hhmm(minute: int | None) -> str:
    if minute is None:
        return ""
    return f"{(minute // 60) % 24:02d}:{minute % 60:02d}" + ("(익일)" if minute >= 1440 else "")


def shape_text(intervals: list[dict]) -> str:
    """구간 목록을 사람이 읽는 한 줄로."""
    parts = []
    for iv in intervals:
        one = f"{hhmm(iv['open_min'])}-{hhmm(iv['close_min'])}"
        if iv["last_order_state"] == "present":
            one += f" LO {hhmm(iv['last_order_min'])}"
        parts.append(one)
    return " + ".join(parts)


def hours_summary(rules: dict) -> str:
    """요일이 같은 것끼리 묶어 적는다. 월~금 11:00-22:00 / 토,일 11:00-21:30"""
    groups: dict[str, list[int]] = {}
    for day_str, rule in rules.items():
        day = int(day_str)
        if rule["coverage"] != "intervals" or not rule["intervals"]:
            groups.setdefault("(모름)", []).append(day)
            continue
        groups.setdefault(shape_text(rule["intervals"]), []).append(day)

    out = []
    for shape, days in sorted(groups.items(), key=lambda kv: min(kv[1])):
        days = sorted(days)
        if days == [1, 2, 3, 4, 5, 6, 7]:
            label = "매일"
        elif days == [1, 2, 3, 4, 5]:
            label = "평일"
        elif days == [6, 7]:
            label = "주말"
        elif len(days) > 2 and days == list(range(days[0], days[-1] + 1)):
            label = f"{DAY_NAME[days[0]]}~{DAY_NAME[days[-1]]}"
        else:
            label = ",".join(DAY_NAME[d] for d in days)
        out.append(f"{label} {shape}")
    return " / ".join(out)


def closure_summary(closures: list[dict]) -> str:
    if not closures:
        return "(없음)"
    out = []
    for rule in closures:
        kind = rule["pattern_kind"]
        if kind == "weekly":
            out.append(f"매주 {DAY_NAME[rule['weekday']]}")
        elif kind == "monthly_nth":
            out.append(f"매월 {','.join(str(n) for n in rule['nth'])}째 {DAY_NAME[rule['weekday']]}")
        elif kind == "named_holiday":
            out.append(f"{rule['holiday_name']} "
                       + ("연휴" if rule["holiday_scope"] == "whole_period" else "당일"))
        elif kind == "public_holiday":
            out.append("공휴일")
        else:
            out.append(str(rule))
    return ", ".join(out)


def tags(row: dict) -> str:
    """유형별 비율도 따로 낼 수 있게 표시를 붙인다."""
    marks = []
    shapes = {shape_text(r["intervals"]) for r in row["rules"].values()
              if r["coverage"] == "intervals" and r["intervals"]}
    if len(shapes) > 1:
        marks.append("요일별")
    if any(len(r["intervals"]) > 1 for r in row["rules"].values()):
        marks.append("브레이크")
    if any(iv["last_order_state"] == "present"
           for r in row["rules"].values() for iv in r["intervals"]):
        marks.append("라스트오더")
    if any(iv["close_min"] > 1440
           for r in row["rules"].values() for iv in r["intervals"]):
        marks.append("자정넘김")
    if row["notes"]:
        marks.append("메모있음")
    return ",".join(marks) or "단순"


BLANKS = ["시작", "종료", "브레이크", "라스트오더", "요일", "휴무", "틀린방향", "메모"]


def main() -> None:
    rows = json.load(open(os.path.join(OUT, "parsed_hours.json"), encoding="utf-8"))
    rows = [r for r in rows if r["hours_text"]]

    random.seed(SEED)
    picked = random.sample(rows, min(SAMPLE, len(rows)))
    picked.sort(key=lambda r: (r["area"] or "", r["title"] or ""))

    header = ["번호", "지역", "상호", "유형", "원문(영업시간)", "적재된 영업시간",
              "원문(휴무)", "적재된 휴무", "파서 메모"] + BLANKS

    body = []
    for i, row in enumerate(picked, 1):
        body.append([
            i, row["area"], row["title"], tags(row),
            row["hours_text"], hours_summary(row["rules"]),
            row["rest_text"], closure_summary(row["closures"]),
            " / ".join(row["notes"]),
        ] + [""] * len(BLANKS))

    csv_path = os.path.join(OUT, "오추출_대조표_100.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(header)
        writer.writerows(body)

    style = (
        "body{font-family:'Malgun Gothic',sans-serif;font-size:13px;margin:24px;color:#1F2933}"
        "h1{font-size:17px;font-weight:600}"
        "p{color:#556;line-height:1.7;max-width:900px}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #D3D9DF;padding:6px 8px;vertical-align:top;text-align:left}"
        "th{background:#EEF3F8;font-weight:600;position:sticky;top:0}"
        "tr:nth-child(even) td{background:#FAFBFC}"
        ".raw{color:#444;max-width:300px}"
        ".got{color:#0B4F8A;max-width:260px}"
        ".tag{color:#7A5A00;white-space:nowrap}"
        ".mark{background:#FFFDF5;min-width:52px}"
        ".note{color:#A33;max-width:180px}"
    )
    out = ["<!doctype html><meta charset='utf-8'><title>오추출 대조표</title>",
           f"<style>{style}</style>",
           "<h1>영업시간 구조화 오추출 대조표</h1>",
           f"<p>표본 {len(picked)}건. 고정 씨앗 무작위 추출이라 다시 돌려도 같은 표본이 나온다. "
           "원문과 적재된 값을 비교해 항목마다 맞으면 O, 틀리면 X 를 적는다. "
           "틀렸다면 방향도 적는다. <b>넓게</b>는 실제보다 영업 시간을 길게 잡은 것이고 "
           "<b>좁게</b>는 짧게 잡은 것이다. 좁게 잡는 쪽이 더 나쁘다. "
           "멀쩡한 식당을 거르면 사용자가 그곳에 가지 않으므로 우리가 틀렸다는 것을 영영 알 수 없다.</p>",
           "<table><thead><tr>"]
    for name in header:
        cls = " class='mark'" if name in BLANKS else ""
        out.append(f"<th{cls}>{html.escape(str(name))}</th>")
    out.append("</tr></thead><tbody>")
    for line in body:
        out.append("<tr>")
        for idx, cell in enumerate(line):
            name = header[idx]
            cls = ("raw" if name.startswith("원문") else
                   "got" if name.startswith("적재") else
                   "tag" if name == "유형" else
                   "note" if name == "파서 메모" else
                   "mark" if name in BLANKS else "")
            out.append(f"<td class='{cls}'>{html.escape(str(cell))}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")

    html_path = os.path.join(OUT, "오추출_대조표_100.html")
    open(html_path, "w", encoding="utf-8").write("\n".join(out))

    from collections import Counter
    spread = Counter(t for row in picked for t in tags(row).split(","))
    print(f"표본 {len(picked)}건")
    for name, count in spread.most_common():
        print(f"  {name:10s} {count:4d}  {count*100/len(picked):5.1f}%")
    print(f"\n저장: {csv_path}\n      {html_path}")


if __name__ == "__main__":
    main()
