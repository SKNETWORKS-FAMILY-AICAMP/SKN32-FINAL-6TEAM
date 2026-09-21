"""TourAPI 음식점 영업시간과 휴무 원문을 요식 원장 구조로 바꾼다.

만든 이유. 이전 파서는 시각 범위를 하나만 읽어서 요일별 표기를 흘렸다.
표본 200건 중 70건(35.0%)이 요일을 나눠 적는데, 첫 줄만 읽으면
일요일에 평일 시간으로 판정하게 된다.

출력은 DB 설계 v3 의 dn_hours_rule / dn_hours_interval / dn_closure_rule 모양이다.
  시각은 자정부터의 분. 자정을 넘기면 1440 이상.
  브레이크는 별도 칸이 아니라 연속한 두 구간 사이의 빈 시간으로 표현한다.
  모르는 것은 unknown 으로 둔다. 없음으로 바꾸지 않는다.

사용법:  python parse_hours.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")   # 원본 데이터
OUT = ROOT                          # 생성물은 저장소 뿌리에 둔다

ALL_DAYS = (1, 2, 3, 4, 5, 6, 7)
WEEKDAYS = (1, 2, 3, 4, 5)
WEEKEND = (6, 7)

DAY_NO = {"월": 1, "화": 2, "수": 3, "목": 4, "금": 5, "토": 6, "일": 7}

RE_TAG = re.compile(r"<[^>]+>")
RE_RANGE = re.compile(r"(\d{1,2})\s*:\s*(\d{2})\s*[~\-]\s*(\d{1,2})\s*:\s*(\d{2})")
RE_ONE = re.compile(r"(\d{1,2})\s*:\s*(\d{2})")
RE_BREAK_WORD = re.compile(r"준비\s*시간|브레이크|브레익|break", re.I)
RE_LO_WORD = re.compile(r"마지막\s*주문|라스트\s*오더|last\s*order|L\.?O\.?", re.I)

#: [평일] 처럼 대괄호로 묶은 요일 블록
RE_BRACKET = re.compile(r"\[([^\]]{1,12})\]")
#: 준비시간(평일) 처럼 괄호로 요일을 한정한 경우
RE_QUALIFIER = re.compile(r"[(（]\s*(평일|주말|공휴일|[월화수목금토일][요일]*)\s*[)）]")
#: 화요일~토요일, 일~목요일, 월~금
RE_DAY_SPAN = re.compile(r"([월화수목금토일])(?:요일)?\s*[~\-]\s*([월화수목금토일])(?:요일)?")
#: 단독 요일 낱말
RE_DAY_WORD = re.compile(r"(평일|주중|주말|매일|공휴일|[월화수목금토일]요일)")
#: 문장 어디에서든 요일 묶음을 찾는다. 금,토,일 처럼 쉼표로 이은 것도 한 덩어리다.
RE_DAY_ANY = re.compile(
    r"(평일|주중|주말|매일|공휴일"
    r"|[월화수목금토일](?:요일)?\s*[~\-]\s*[월화수목금토일](?:요일)?"
    r"|[월화수목금토일](?:\s*,\s*[월화수목금토일])+"
    r"|[월화수목금토일]요일)")


def norm(text: str | None) -> str:
    """태그를 지우고 공백을 하나로 만든다. BOM 도 지운다."""
    text = RE_TAG.sub(" ", text or "")
    return re.sub(r"\s+", " ", text.replace("﻿", "")).strip()


def to_min(hour: str | int, minute: str | int) -> int:
    return int(hour) * 60 + int(minute)


def days_from_token(token: str) -> tuple[int, ...]:
    """요일 낱말 하나를 요일 번호로. 모르면 빈 값."""
    token = token.strip()
    if "평일" in token or "주중" in token:
        return WEEKDAYS
    if "주말" in token:
        return WEEKEND
    if "매일" in token:
        return ALL_DAYS
    span = RE_DAY_SPAN.search(token)
    if span:
        start, end = DAY_NO[span.group(1)], DAY_NO[span.group(2)]
        if start <= end:
            return tuple(range(start, end + 1))
        return tuple(range(start, 8)) + tuple(range(1, end + 1))
    found = []
    # 「토요일」 안의 「일」 을 일요일로 읽지 않도록 요일 표기를 먼저 떼어낸다.
    rest = token
    for one in re.findall(r"([월화수목금토일])요일", token):
        found.append(DAY_NO[one])
        rest = rest.replace(one + "요일", " ", 1)
    for one in re.findall(r"([월화수목금토일])", rest):
        if DAY_NO[one] not in found:
            found.append(DAY_NO[one])
    return tuple(sorted(set(found)))


def split_blocks(text: str) -> list[tuple[tuple[int, ...] | None, str]]:
    """요일 블록으로 자른다. 요일을 못 찾으면 전체를 한 덩어리로 둔다.

    세 가지 모양을 본다.
      [평일] ... [주말] ...        대괄호 블록
      - 평일 08:00~19:30 - 주말 ... 항목 앞에 요일이 붙은 형태
      화요일~토요일 12:00~20:00    요일 범위가 앞에 한 번만
    """
    if RE_BRACKET.search(text):
        out = []
        parts = RE_BRACKET.split(text)
        # split 결과는 [앞부분, 라벨, 내용, 라벨, 내용 ...]
        head = parts[0].strip(" -")
        if head and RE_RANGE.search(head):
            out.append((None, head))
        for i in range(1, len(parts) - 1, 2):
            days = days_from_token(parts[i])
            out.append((days or None, parts[i + 1]))
        if out:
            return out

    # 문장 어디에 있든 요일 묶음을 찾아 그 지점에서 자른다.
    # 「평일 11:00~22:00 (라스트오더 21:30) 주말 12:00~23:00」 처럼
    # 항목 구분자가 없는 표기가 있어서 구분자에 기대지 않는다.
    marks = []
    for match in RE_DAY_ANY.finditer(text):
        # 준비시간(평일) 의 괄호 안 요일은 구분점이 아니라 한정어다.
        if match.start() > 0 and text[match.start() - 1] in "(（":
            continue
        marks.append(match)

    if marks:
        blocks: list[tuple[tuple[int, ...] | None, str]] = []
        head = text[:marks[0].start()].strip(" -")
        if head and RE_RANGE.search(head):
            blocks.append((None, head))
        for i, match in enumerate(marks):
            stop = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            chunk = text[match.end():stop]
            if not RE_RANGE.search(chunk):
                continue
            blocks.append((days_from_token(match.group(0)) or None, chunk))
        if blocks:
            return blocks

    return [(None, text)]


def pick_ranges(chunk: str) -> tuple[list[tuple[int, int]], list[tuple[tuple[int, ...] | None, tuple[int, int]]]]:
    """한 덩어리에서 영업 범위와 브레이크 범위를 나눈다.

    브레이크에 요일 한정이 붙으면(준비시간(평일)) 그 요일에만 적용한다.
    """
    biz: list[tuple[int, int]] = []
    brk: list[tuple[tuple[int, ...] | None, tuple[int, int]]] = []
    for match in RE_RANGE.finditer(chunk):
        # 항목 경계를 넘어 옆 항목의 낱말을 자기 것으로 읽지 않게 자른다.
        # 「11:00~21:00 - 준비시간 15:00~17:00」에서 앞 범위가 브레이크로 잡히던 원인이다.
        left = chunk.rfind(" - ", 0, match.start())
        right = chunk.find(" - ", match.end())
        head = (left + 3) if left >= 0 else 0
        tail = right if right >= 0 else len(chunk)
        # 항목 경계 안에서도 거리를 둔다. 「11:30~22:00 (15:00~17:00 브레이크타임)」 처럼
        # 뒤따르는 괄호 안의 낱말을 앞 범위가 가져가지 않게 한다.
        before = chunk[max(head, match.start() - 14):match.start()]
        after = chunk[match.end():min(tail, match.end() + 9)]
        # 뒤에 괄호가 열리면 그 안의 낱말은 괄호 내용의 것이다.
        # 「11:00~22:00 (브레이크타임 15:00~17:00)」 에서 앞 범위가
        # 브레이크로 잡혀 영업시간이 통째로 사라지던 원인이다.
        if '(' in after:
            after = after[:after.index('(')]
        start = to_min(match.group(1), match.group(2))
        end = to_min(match.group(3), match.group(4))
        if end <= start:
            end += 1440
        if RE_BREAK_WORD.search(before) or RE_BREAK_WORD.search(after):
            qual = RE_QUALIFIER.search(before)
            days = days_from_token(qual.group(1)) if qual else None
            brk.append((days or None, (start, end)))
        else:
            biz.append((start, end))
    return biz, brk


def pick_last_orders(chunk: str) -> list[int]:
    """마지막 주문 시각들. 한 줄에 둘이 오기도 한다 (14:30, 20:20)."""
    out = []
    for match in RE_LO_WORD.finditer(chunk):
        tail = chunk[match.end():match.end() + 24]
        found_here = []
        for one in RE_ONE.finditer(tail):
            found_here.append(to_min(one.group(1), one.group(2)))
            nxt = tail[one.end():one.end() + 3]
            if not re.match(r"\s*,", nxt):
                break
        if not found_here:
            # 「21:00 라스트오더」 처럼 시각이 낱말 앞에 오는 표기
            head = chunk[max(0, match.start() - 10):match.start()]
            back = list(RE_ONE.finditer(head))
            if back:
                found_here.append(to_min(back[-1].group(1), back[-1].group(2)))
        out += found_here
    # 괄호 안에 쓰는 형태 (라스트오더 21:30) 는 위에서 잡힌다
    return out


def carve(biz: tuple[int, int], breaks: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """영업 범위에서 브레이크를 파내 구간 목록을 만든다."""
    pieces = [biz]
    for bs, be in sorted(breaks):
        nxt = []
        for ps, pe in pieces:
            if be <= ps or bs >= pe:
                nxt.append((ps, pe))
                continue
            if ps < bs:
                nxt.append((ps, bs))
            if be < pe:
                nxt.append((be, pe))
        pieces = nxt
    return [p for p in pieces if p[1] > p[0]]


def parse_hours(raw: str) -> tuple[dict[int, dict], list[str]]:
    """요일별 규칙을 만든다. 두 번째 값은 사람이 봐야 할 사유 목록."""
    text = norm(raw)
    notes: list[str] = []
    if not text:
        return {}, ["원문 없음"]

    per_day: dict[int, dict] = {d: {"biz": [], "brk": [], "lo": []} for d in ALL_DAYS}
    saw_holiday_block = False

    for days, chunk in split_blocks(text):
        targets = days or ALL_DAYS
        if days is None and RE_DAY_WORD.search(chunk or "") and "공휴일" in chunk:
            saw_holiday_block = True
        biz, brk = pick_ranges(chunk)
        los = pick_last_orders(chunk)
        for day in targets:
            per_day[day]["biz"] += biz
            per_day[day]["lo"] += los
        for bdays, span in brk:
            for day in (bdays or targets):
                per_day[day]["brk"].append(span)

    if saw_holiday_block:
        notes.append("공휴일 블록이 있어 주별 규칙으로만 담지 못함")

    rules: dict[int, dict] = {}
    for day in ALL_DAYS:
        data = per_day[day]
        if not data["biz"]:
            rules[day] = {"coverage": "unknown", "break_state": "unknown", "intervals": []}
            continue
        if len(set(data["biz"])) > 1:
            notes.append(f"{day}요일에 영업 범위가 여럿")
        biz = sorted(set(data["biz"]))[0]
        breaks = sorted(set(data["brk"]))
        pieces = carve(biz, breaks)
        intervals = []
        for seq, (start, end) in enumerate(pieces, 1):
            hit = [v for v in sorted(set(data["lo"])) if start <= v <= end]
            # 한 구간에 마지막 주문 값이 둘 이상 들어가면 어느 것인지 알 수 없다.
            # 이른 쪽을 고르면 실제보다 좁게 잡혀 멀쩡한 시간을 거른다. 모름으로 둔다.
            if len(hit) > 1:
                notes.append(f"{day}요일 구간 {seq} 에 마지막 주문 후보가 여럿 {hit}")
                hit = []
            intervals.append({
                "seq": seq,
                "open_min": start,
                "close_min": end,
                "last_order_min": hit[0] if hit else None,
                "last_order_state": "present" if hit else "unknown",
            })
        stray = [v for v in sorted(set(data["lo"]))
                 if not any(i["last_order_min"] == v for i in intervals)]
        if stray:
            notes.append(f"{day}요일 마지막 주문 {stray} 이 구간 밖")
        rules[day] = {
            "coverage": "intervals",
            "break_state": "present" if breaks else "unknown",
            "intervals": intervals,
        }
    return rules, notes


# ── 휴무 ────────────────────────────────────────────────────────
RE_WEEKLY = re.compile(r"매주\s*([월화수목금토일요일,·/~\-\s]+)")
#: 매월 둘째, 넷째 화요일 / 매월 두번 째, 네번 째 일요일
RE_NTH = re.compile(r"매월\s*([^월화수목금토일]*?)\s*([월화수목금토일])요일")
KOR_NTH = {"첫": 1, "한": 1, "둘": 2, "두": 2, "셋": 3, "세": 3,
           "넷": 4, "네": 4, "다섯": 5}


def parse_closure(raw: str) -> tuple[list[dict], list[str]]:
    text = norm(raw)
    notes: list[str] = []
    if not text:
        return [], ["원문 없음"]
    if "연중무휴" in text:
        return [], []

    out: list[dict] = []
    handled = False

    for match in RE_NTH.finditer(text):
        body = match.group(1)
        if "마지막" in body or "말" in body:
            notes.append("매월 마지막 주 표기는 주차 수로 담지 못함")
            handled = True
            continue
        nth = [int(n) for n in re.findall(r"\d+", body)]
        for word, num in KOR_NTH.items():
            if word in body and num not in nth:
                nth.append(num)
        if nth:
            out.append({"pattern_kind": "monthly_nth",
                        "weekday": DAY_NO[match.group(2)], "nth": sorted(nth)})
            handled = True

    for match in RE_WEEKLY.finditer(text):
        body = match.group(1)
        for part in re.split(r"[,·/]", body):
            for day in days_from_token(part):
                out.append({"pattern_kind": "weekly", "weekday": day})
        handled = True

    if not handled and not re.search(r"격주|비정기|부정기|유동", text):
        bare = days_from_token(text)
        if bare:
            for day in bare:
                out.append({"pattern_kind": "weekly", "weekday": day})
            handled = True

    if "설" in text or "추석" in text or "명절" in text:
        scope = "whole_period" if "연휴" in text else "day_of"
        for name in ("설날", "추석"):
            if name[0] in text or name in text:
                out.append({"pattern_kind": "named_holiday",
                            "holiday_name": name, "holiday_scope": scope})
        handled = True

    if re.search(r"\d{1,2}\s*월\s*\d{1,2}\s*일", text):
        notes.append("연도 없는 특정일 표기라 날짜 규칙으로 담지 못함")
        handled = True

    if re.search(r"격주", text):
        notes.append("격주 휴무는 규칙으로 담지 못함")
        handled = True

    if re.search(r"봄|여름|가을|겨울|비정기|부정기|유동", text):
        notes.append("계절 또는 비정기 휴무라 담지 못함")
        handled = True

    if not handled:
        notes.append("해석하지 못한 휴무 표기")

    seen = set()
    uniq = []
    for rule in out:
        key = json.dumps(rule, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            uniq.append(rule)
    return uniq, notes


def main() -> None:
    src = os.path.join(DATA, "tourapi_음식점_소개정보.json")
    rows = json.load(open(src, encoding="utf-8"))

    results = []
    stat = Counter()
    note_stat = Counter()

    for row in rows:
        hours, hnotes = parse_hours(row.get("opentimefood", ""))
        closures, cnotes = parse_closure(row.get("restdatefood", ""))
        covered = [d for d, r in hours.items() if r["coverage"] == "intervals"]
        distinct = {json.dumps(hours[d]["intervals"], sort_keys=True) for d in covered}

        stat["전체"] += 1
        if covered:
            stat["영업 구간 생성"] += 1
        if len(distinct) > 1:
            stat["요일마다 다름"] += 1
        if any(r["break_state"] == "present" for r in hours.values()):
            stat["브레이크 있음"] += 1
        if any(i["last_order_state"] == "present"
               for r in hours.values() for i in r["intervals"]):
            stat["라스트오더 있음"] += 1
        if closures:
            stat["휴무 규칙 생성"] += 1
        for note in hnotes + cnotes:
            note_stat[note.split("요일")[-1] if note[0].isdigit() else note] += 1

        results.append({
            "content_id": row.get("contentid"),
            "title": row.get("_title"),
            "area": row.get("_region"),
            "hours_text": norm(row.get("opentimefood", "")),
            "rest_text": norm(row.get("restdatefood", "")),
            "rules": hours,
            "closures": closures,
            "notes": hnotes + cnotes,
        })

    out = os.path.join(OUT, "parsed_hours.json")
    json.dump(results, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    total = stat["전체"]
    print("=" * 62)
    print(f"TourAPI 음식점 영업시간 구조화 · 표본 {total}건")
    print("=" * 62)
    for key in ("영업 구간 생성", "요일마다 다름", "브레이크 있음", "라스트오더 있음", "휴무 규칙 생성"):
        print(f"  {key:16s} {stat[key]:4d}  {stat[key]*100/total:5.1f}%")
    print("\n[사람이 봐야 할 것]")
    for note, count in note_stat.most_common(10):
        print(f"  {count:4d}  {note}")
    print(f"\n저장: {out}")


if __name__ == "__main__":
    main()
