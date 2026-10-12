"""단계별 전환 계획 — 하루 질문 수마다 가장 싼 조합(무료 서버 · API · GPU 서버 대수)을 계산한다 (2026-10-07).

사용자: 「트래픽이 적을 때는 무료 서버로 운영하다가 일정 이상이면 API, 더 늘면 RunPod 등 GPU 서버, 다음에는 API 까지 하고 서버 증설 —
각각의 최적 전환 시기와 조합을 알고 싶다. 금액 · 성능 · 트래픽 수치는 이미 다 나와 있으니 그걸로 조합 순서를 짜라.」

입력(모두 이미 잰 값 · 공식 단가):
- 오라클 무료 서버(2코어 ARM · 12GB, RAG 세션 실측 2026-10-07): 이어지는 질문 7.7초, 새 일정 첫 질문 112.5초(15초 기준 넘음)
  → 새 일정 첫 질문은 무료 서버에 맡기지 않는다(API 나 GPU 로). 이어지는 질문만 하루 11,193건(쉬지 않을 때) · 안전선 50% = 5,600건
- RunPod GPU 1대(RTX 2000 Ada, 연구 문서 §80 실측): 동시 4건 · 캐시 없음 0.83초 → 하루 10.4만 건 · 안전선 50% = 5.2만 건, 월 24.5만원
- API 1건(공식 단가, 입력 1,700 + 출력 12토큰, 1,400원/달러): Luna 0.25원 · Sol 4.93원
- 새 일정 첫 질문 비율 20%(가정 — 실제 사용 기록이 쌓이면 바꾼다), 한 달 30일
계산: 하루 D 건마다 GPU 대수 g = 0,1,2,… 를 바꿔 가며 월 비용 g×24.5만 + API 단가×30×(API 로 가는 건수)가 가장 작은 조합을 고른다.
  새 일정 첫 질문은 GPU 가 있으면 GPU, 없으면 API. 이어지는 질문은 무료 서버 5,600건 → 남으면 GPU → 그래도 남으면 API.
"""
from __future__ import annotations

import json
from pathlib import Path

ORACLE_FOLLOW = 5600      # 무료 서버가 안전하게 받는 이어지는 질문(하루)
GPU_CAP = 52000           # GPU 1대가 안전하게 받는 질문(하루)
GPU_WON = 245000          # GPU 1대 월 비용(원)
NEW_SHARE = 0.2           # 새 일정 첫 질문 비율(가정)
API = {"Luna": 0.25, "Sol": 4.93}


# 무료 서버만 쓰는 구간(2026-10-07 사용자: 「무료 서버만 가지고 커버하는 구간이 있어야 하지 않을까」):
# 일정을 등록 · 변경할 때 무료 서버가 미리 읽어 두면(112.5초, 고객은 안 기다림) 새 일정 첫 질문도 이어지는 질문(7.7초)이 된다.
# 일하는 총량은 같으므로 하루 처리 = 0.5 × 86,400초 ÷ (20% × 112.5 + 80% × 7.7) ≈ 1,500건(안전선 50%).
# 조건: 무료 서버 메모리에 일정 캐시가 남아 있어야 한다 — 실측은 일정 3개까지 서로 밀어내지 않음, 그 이상은 아직 안 잼.
FIRST_SEC, FOLLOW_SEC, SAFE = 112.5, 7.7, 0.5


def free_only_cap():
    return SAFE * 86400 / (NEW_SHARE * FIRST_SEC + (1 - NEW_SHARE) * FOLLOW_SEC)


def best(D, won):
    # 무료 서버의 하루 일할 시간(안전선 50%)을 이어지는 질문(7.7초)에 먼저 쓰고, 남는 시간으로 새 일정을 미리 읽는다(112.5초).
    # 같은 시간에 API 호출을 더 많이 아끼는 쪽이 이어지는 질문이라서다. 이렇게 하면 무료 서버만 쓰는 구간(⓪)에서
    # API 를 섞는 구간(①)으로 비용이 끊기지 않고 이어진다(앞 판은 1,550건에서 Sol 월 4.6만원으로 계단처럼 뛰었다).
    N, F = NEW_SHARE * D, (1 - NEW_SHARE) * D
    budget = SAFE * 86400
    f_free = min(F, budget / FOLLOW_SEC)
    n_free = min(N, max(0.0, budget - f_free * FOLLOW_SEC) / FIRST_SEC)
    N2, F2 = N - n_free, F - f_free
    out = None
    for g in range(0, 10):
        G = g * GPU_CAP
        n_gpu = min(N2, G)
        f_gpu = min(F2, G - n_gpu)
        api = (N2 - n_gpu) + (F2 - f_gpu)
        cost = g * GPU_WON + won * 30 * api
        if out is None or cost < out["cost"] - 1e-6:
            out = {"g": g, "api": api, "cost": cost}
    return out


def stages(won):
    rows, prev = [], None
    D = 100
    while D <= 200000:
        b = best(D, won)
        key = (b["g"], b["api"] > 0.5)
        if key != prev:
            rows.append({"from": D, "g": b["g"], "api": b["api"] > 0.5})
            prev = key
        D += 50
    return rows


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    res = {}
    for m, won in API.items():
        st = stages(won)
        res[m] = st
        print("##", m)
        for r in st:
            c = best(r["from"], won)
            print(f"  하루 {r['from']:>7,}건부터: GPU {r['g']}대 + {'API' if r['api'] else 'API 없음'} · 그때 월 {c['cost'] / 10000:.1f}만원")
    for D in (1000, 3000, 7000, 10000, 20000, 40000, 60000, 100000):
        print(D, {m: round(best(D, w)["cost"] / 10000, 1) for m, w in API.items()}, {m: best(D, w)["g"] for m, w in API.items()})
    Path(__file__).resolve().parent.joinpath("scaling_plan.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
