# -*- coding: utf-8 -*-
"""판정 규칙 — 프로젝트 판정기(`eval/commercial_criteria.py`)를 그대로 쓰고, 짝 비교 · 허용폭만 더한다. `[2026-10-19]`

재생 시험 계획 「판정 규칙」:
  - 비율 하한/상한 · 0건은 판정기 규칙 그대로(Wilson · Clopper-Pearson).
  - 기준선과 비교하는 칸은 **짝 비교** — 같은 에피소드의 (기준선 실패 · 새 판 성공) 수와 그 반대 수로 차이를 낸다.
    차이의 95% 구간은 짝 부트스트랩(에피소드를 다시 뽑기), McNemar 정확 검정 p 를 함께 적는다. 아래 끝 > 0 이면 개선.
  - 퇴보 없음: 짝 차이 95% 아래 끝 ≥ −허용폭. 허용폭 = max(5%p, 1.96 × √(0.2 ÷ N)) — 0.2 는 우리가 고른 가정 어긋남 비율.
"""
from __future__ import annotations

import math
import random
from typing import Any

from eval.commercial_criteria import Criterion, Measurement, judge, wilson, zero_upper

TOL_DISAGREE = 0.2      # 우리가 고른 값 — 기준선과 비교판의 판정이 갈리는 에피소드 비율 가정
TOL_FLOOR = 0.05        # 우리가 고른 값 — 허용폭 바닥 5%p


def tolerance(n: int) -> float:
    """허용폭 = max(5%p, 1.96 · √(0.2 / N))."""
    if n <= 0:
        raise ValueError("N 은 1 이상")
    return max(TOL_FLOOR, 1.959963984540054 * math.sqrt(TOL_DISAGREE / n))


def rate_verdict(key: str, name: str, kind: str, k: int, n: int, *, threshold: float | None = None, label: str = "",
                 measured_on: str = "", condition: str = "", source: str = "", real_human: bool = False,
                 note: str = "") -> dict[str, Any]:
    """판정기 규칙으로 한 칸 판정. `kind` — min_rate · max_rate · zero. 기준이 아직 없으면(`threshold=None` 이고 zero 아님) 숫자 · 구간만."""
    if kind != "zero" and threshold is None:
        out: dict[str, Any] = {"criterion": name, "kind": kind, "k": k, "n": n, "label": label, "verdict": "기준 없음(보고만)"}
        if n:
            lo, hi = wilson(k, n)
            out.update({"point": k / n, "lower": lo, "upper": hi})
        else:
            out["verdict"] = "측정 없음"
        return out
    crit = Criterion(key, name, kind, threshold, "재생 시험 계획", "계획서")
    m = Measurement(key, label, k, n, measured_on, condition, source, real_human_questions=real_human, note=note) if n else None
    return judge(crit, m)


def mcnemar_exact(b: int, c: int) -> float:
    """McNemar 정확 검정(양쪽) — 갈린 짝 b(기준선 실패 · 새 판 성공) · c(그 반대)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def paired(base: dict[str, bool], new: dict[str, bool], *, reps: int = 10000, seed: int = 20261019,
           higher_is_better: bool = True) -> dict[str, Any]:
    """짝 비교 — 두 판 모두 판정이 있는 에피소드만. 차이 = 새 판 비율 − 기준선 비율(좋아지면 +가 되게 `higher_is_better` 로 부호를 맞춘다).
    `b` = 기준선 거짓 · 새 판 참인 짝 수, `c` = 그 반대."""
    keys = sorted(set(base) & set(new))
    n = len(keys)
    if n == 0:
        return {"n": 0, "verdict": "측정 없음"}
    sign = 1 if higher_is_better else -1
    pairs = [(bool(base[k]), bool(new[k])) for k in keys]
    b = sum(1 for x, y in pairs if (not x) and y)      # 기준선 0 → 새 판 1
    c = sum(1 for x, y in pairs if x and not y)
    diff = sign * (b - c) / n
    rng = random.Random(seed)
    boots = []
    for _ in range(reps):
        s = 0
        for _ in range(n):
            x, y = pairs[rng.randrange(n)]
            s += int(y) - int(x)
        boots.append(sign * s / n)
    boots.sort()
    lo, hi = boots[int(0.025 * reps)], boots[min(reps - 1, int(0.975 * reps))]
    tol = tolerance(n)
    return {"n": n, "base_rate": sum(x for x, _ in pairs) / n, "new_rate": sum(y for _, y in pairs) / n,
            "b": b, "c": c, "diff": diff,
            "diff_lower": lo, "diff_upper": hi, "mcnemar_p": mcnemar_exact(b, c), "tolerance": tol,
            "improved": lo > 0, "no_regression": lo >= -tol, "disagree_rate": (b + c) / n,
            "tolerance_basis_exceeded": (b + c) / n > TOL_DISAGREE}


def zero_needed(upper: float = 0.01, alpha: float = 0.05) -> int:
    """0건으로 「위 끝 ≤ upper」를 보이는 데 필요한 기회 수(≈ 299)."""
    n = 1
    while zero_upper(n, alpha) > upper:
        n += 1
    return n


def fix_absolute(base_point: float, *, kind: str) -> dict[str, Any]:
    """「숫자 고정 순서」 — 일 끝남 절대 하한 = 기준선 점추정 + 10%p, 실패형 절대 상한 = 기준선 점추정 − 10%p(0 이하면 쓰지 않음)."""
    if kind == "done_floor":
        return {"rule": "기준선 점추정 + 10%p", "value": min(1.0, base_point + 0.10)}
    if kind == "fail_ceiling":
        v = base_point - 0.10
        if v <= 0:
            return {"rule": "기준선 점추정 − 10%p", "value": None,
                    "note": "0 이하 — 절대 상한을 쓰지 않고 짝 차이 아래 끝 > 0 만으로 판정"}
        return {"rule": "기준선 점추정 − 10%p", "value": v}
    raise ValueError(kind)
