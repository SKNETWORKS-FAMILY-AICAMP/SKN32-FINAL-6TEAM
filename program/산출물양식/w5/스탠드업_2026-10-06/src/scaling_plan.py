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

# 2026-10-07 개정 — 하루 평균이 아니라 「가장 몰리는 한 시간」 기준으로 대수를 정한다(사용자 지시 · 실무 점검 지적 1).
# 앞 판은 하루 처리량의 50% 를 안전선으로 잡았다. 실무는 피크 시간 부하가 용량 안에 드는지로 정하고,
# 피크가 아닌 시간에는 남는 용량으로 넘침을 흡수한다. 그래서 시간대별로 나눠 계산한다.
# - 가장 몰리는 한 시간의 몫: 하루 질문의 15% (가정 — 콜센터 인력 계획에서 흔히 쓰는 기본값. 24시간 이동통신망은 8~12%.
#   보수적인 쪽을 골랐다. 실제 사용 기록이 쌓이면 바꾼다)
# - 시간대 모양: 새벽에 적고 오전 · 저녁에 몰리는 두 봉우리(가정). 가장 몰리는 시간이 15% 가 되게 맞춘다.
# - 목표 가동률: 피크 시간에 실측 최대 처리량의 80% (나머지 20% 는 순간 몰림 · 재시도 몫)
FIRST_SEC, FOLLOW_SEC = 112.5, 7.7     # 무료 서버: 새 일정 첫 읽기 · 이어지는 질문 (RAG 세션 실측)
GPU_HOUR = 163000 / 24                  # GPU 1대 시간당 최대 처리 — RTX A4000 실측 하루 약 16.3만 건(올라마 Gemma E4B QAT · 동시 8, RAG 세션 2026-10-07). 앞 판은 RTX 2000 Ada 10.4만(동시 4)
GPU_WON = 255500                        # GPU 1대 월 비용(원) — RunPod RTX A4000 시큐어 $0.25 × 730시간 × 1,400원(16 vCPU · 62GB · 디스크 100GB, 앱도 같이 올림, 2026-10-07 사용자 포드)
NEW_SHARE = 0.2                         # 새 일정 첫 질문 비율(가정)
PEAK_SHARE = 0.15                       # 가장 몰리는 한 시간의 몫(가정)
UTIL = 0.8                              # 피크 시간 목표 가동률
API = {"Luna": 0.25, "Sol": 4.93}
_BASE = [2, 1, 1, 1, 1, 2, 4, 7, 9, 10, 10, 11, 12, 11, 10, 10, 11, 13, 15, 16, 14, 10, 6, 3]


def _profile():
    lo, hi = 0.5, 6.0
    for _ in range(60):
        k = (lo + hi) / 2
        w = [b ** k for b in _BASE]
        if max(w) / sum(w) < PEAK_SHARE:
            lo = k
        else:
            hi = k
    t = sum(w)
    return [x / t for x in w]


PROFILE = _profile()


def free_only_cap():
    """무료 서버만으로 가장 몰리는 시간까지 버티는 하루 질문 수(새 일정은 등록할 때 미리 읽어 둔다)."""
    return UTIL * 3600 / (PEAK_SHARE * (NEW_SHARE * FIRST_SEC + (1 - NEW_SHARE) * FOLLOW_SEC))


def _hour_api(L, g):
    N, F = NEW_SHARE * L, (1 - NEW_SHARE) * L
    budget = UTIL * 3600
    f_free = min(F, budget / FOLLOW_SEC)
    n_free = min(N, max(0.0, budget - f_free * FOLLOW_SEC) / FIRST_SEC)
    N2, F2 = N - n_free, F - f_free
    G = g * UTIL * GPU_HOUR
    n_gpu = min(N2, G)
    f_gpu = min(F2, G - n_gpu)
    return (N2 - n_gpu) + (F2 - f_gpu)


def best(D, won):
    # 무료 서버 시간을 이어지는 질문(7.7초)에 먼저 쓰고 남는 시간으로 새 일정을 미리 읽는다(112.5초) → GPU → 그래도 넘치면 API.
    # 시간대마다 따로 계산해서, 피크에만 넘치는 몫은 API 가 받고 한가한 시간에는 서버가 다 받는다.
    out = None
    for g in range(0, 12):
        api = sum(_hour_api(D * w, g) for w in PROFILE)
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
