# -*- coding: utf-8 -*-
"""전환 횟수 vs 시간 점유율 — 사건 하나가 하루를 얼마나 무너뜨리나(모의 실험).

★**사람의 체감은 재지 않는다.** 실사용자도 설문도 없다. 이 실험이 재는 것은
  「같은 사건을 줬을 때 뒤 일정이 얼마나 밀리는가」 하나다.

가설 비교: 하루의 취약성을 설명하는 것이 (A) 전환 횟수 t 인가, (B) 시간 점유율 r 인가,
           (C) 둘에서 파생되는 「전환당 여유 시간」인가.

일정 생성:  하루 창 720분(10:00~22:00). 이동 t 건(각 MOVE_MIN 분) + 활동 t+1 블록.
            점유 시간 = 720 × r  (활동 + 이동). 남은 시간은 전환 사이 여유로 무작위 배분(seed).
사건 주입:  첫 활동이 D 분 초과 진행 → 뒤 항목이 차례로 밀린다. 각 여유가 흡수하고 남은 만큼만 전달.
고정 예약:  하루의 60% 지점 활동 하나를 「예약」으로 둔다 — 밀 수 없다. 앞 항목이 밀려 이 시각을
            넘기면 **예약 놓침**으로 센다(v11 보호 순서: 고정 예약이 선택 활동보다 앞선다).
측정:       밀린 항목 수 · 하루 창 초과 분 · 예약 놓침 · 사건을 흡수했는지.
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))    # 저장소 루트 — 제품 판정 코드를 그대로 쓴다

from app.modules.travel_ops.itinerary_checks import Part, check_itinerary   # noqa: E402

KST = ZoneInfo("Asia/Seoul")
DAY = datetime(2026, 9, 23, tzinfo=KST)
WINDOW_START = DAY.replace(hour=10)
WINDOW_MIN = 720                      # 10:00~22:00
MOVE_MIN = 20                         # 이동 한 건의 소요(고정) — 변인을 전환 횟수와 점유율로 좁힌다
MIN_BLOCK_MIN = 25                    # 활동 블록의 하한. 이보다 짧으면 일정으로 보지 않는다
TRANSITIONS = (2, 3, 4, 5, 6, 7)
RATIOS = (0.40, 0.55, 0.70, 0.85)
DELAYS = (30, 60, 90, 120)
SEEDS = 30


def build_day(t: int, r: float, seed: int):
    """이동 t 건·활동 t+1 블록의 하루를 만든다. 만들 수 없으면 (None, 사유)."""
    occupied = WINDOW_MIN * r
    activity_total = occupied - MOVE_MIN * t
    block = activity_total / (t + 1)
    if block < MIN_BLOCK_MIN:
        return None, f"활동 블록 {block:.0f}분 < 하한 {MIN_BLOCK_MIN}분"
    slack_total = WINDOW_MIN - occupied
    rng = random.Random(seed * 1000 + t * 10 + int(r * 100))
    # 여유는 전환마다 하나씩(이동 앞) + 하루 끝 여유로 나눈다.
    weights = [rng.random() + 0.2 for _ in range(t + 1)]
    share = [w / sum(weights) * slack_total for w in weights]

    parts, cursor, seq = [], WINDOW_START, 1
    for index in range(t + 1):
        end = cursor + timedelta(minutes=block)
        reserved = index == max(1, round((t + 1) * 0.6)) - 1          # 하루 60% 지점 하나만 예약
        parts.append(Part(seq=seq, kind="dining" if reserved else "activity",
                          title=("예약 식사" if reserved else f"활동{index + 1}"),
                          starts_at=cursor, ends_at=end,
                          detail={"reservation": True} if reserved else None))
        seq += 1
        cursor = end
        if index < t:
            cursor = cursor + timedelta(minutes=share[index])       # 전환 앞 여유
            move_end = cursor + timedelta(minutes=MOVE_MIN)
            parts.append(Part(seq=seq, kind="mobility", title=f"이동{index + 1}",
                              starts_at=cursor, ends_at=move_end,
                              route={"planned": "m", "options": [{"id": "m", "eta_min": MOVE_MIN}]}))
            seq += 1
            cursor = move_end
    return parts, {"block_min": block, "slack_total": slack_total,
                   "slack_per_transition": slack_total / (t + 1), "gaps": share}


def cascade(parts, delay_min: float):
    """첫 활동이 delay_min 분 더 걸렸다. 뒤 항목을 차례로 민다 — 앞 여유가 있는 만큼 흡수한다."""
    shifted, carry, missed = 0, float(delay_min), 0
    ends = []
    previous_end = None
    for index, part in enumerate(parts):
        start, end = part.starts_at, part.ends_at
        if index == 0:                                   # 사건이 난 항목: 끝이 늦어진다
            end = end + timedelta(minutes=carry)
            previous_end = end
            ends.append((start, end))
            continue
        gap = (start - previous_end).total_seconds() / 60 if previous_end else 0
        if gap < 0:                                      # 여유가 없어 밀린다
            push = -gap
            if (part.detail or {}).get("reservation"):   # ★예약은 못 민다 — 놓친 것으로 센다
                missed += 1
                previous_end = end                       # 예약은 제 시각에 그대로 있다
                ends.append((start, end))
                continue
            start = start + timedelta(minutes=push)
            end = end + timedelta(minutes=push)
            shifted += 1
        previous_end = end
        ends.append((start, end))
    last_end = ends[-1][1]
    overflow = max(0.0, (last_end - (WINDOW_START + timedelta(minutes=WINDOW_MIN))).total_seconds() / 60)
    return {"shifted_items": shifted, "overflow_min": overflow, "missed_reservations": missed,
            "absorbed": overflow == 0 and shifted == 0 and missed == 0}


def spearman(xs, ys):
    """순위 상관 — 값의 크기가 아니라 순서만 본다(선형을 가정하지 않는다)."""
    def rank(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            average = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = average
            i = j + 1
        return ranks
    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")


def main() -> int:
    rows, skipped = [], []
    for t in TRANSITIONS:
        for r in RATIOS:
            for seed in range(SEEDS):
                parts, meta = build_day(t, r, seed)
                if parts is None:
                    skipped.append({"transitions": t, "ratio": r, "seed": seed, "reason": meta})
                    continue
                violations = check_itinerary(parts)
                for delay in DELAYS:
                    result = cascade(parts, delay)
                    rows.append({"transitions": t, "ratio": r, "seed": seed, "delay_min": delay,
                                 "violations_before": len(violations),
                                 "slack_total": meta["slack_total"],
                                 "slack_per_transition": meta["slack_per_transition"],
                                 "block_min": meta["block_min"], **result})
    out = Path(os.environ.get("ACOP_SIM_OUT")
               or Path(__file__).with_name("density_cascade_rows.json"))   # 결과는 저장소에 남기지 않는다
    out.write_text(json.dumps({"rows": rows, "skipped": skipped,
                               "설정": {"window_min": WINDOW_MIN, "move_min": MOVE_MIN,
                                      "min_block_min": MIN_BLOCK_MIN, "seeds": SEEDS,
                                      "transitions": list(TRANSITIONS), "ratios": list(RATIOS),
                                      "delays": list(DELAYS)}}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"판 {len(rows)}건 · 만들 수 없어 건너뛴 조합 {len(skipped)}건 → {out}")
    bad = [row for row in rows if row["violations_before"]]
    print(f"사건 전 위반이 있는 판: {len(bad)}건(0이어야 한다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
