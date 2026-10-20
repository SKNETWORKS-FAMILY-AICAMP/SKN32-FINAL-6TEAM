# -*- coding: utf-8 -*-
"""평가 공통 점수 — 정밀도 · 재현율 · F1 · macro-F1 · pass@k / pass^k. `[2026-10-19]`

★분모를 숨기지 않는다 — 비율마다 분자(num) · 분모(den)를 같이 낸다. F1 도 분수다: 2·TP / (2·TP + FP + FN).
★예측 실패(None)는 그 정답 칸의 놓침(FN)으로 센다 — 분모에서 빼지 않는다(`travel_classification.replay` 와 같은 원칙).
★macro-F1 은 칸마다 F1 을 내서 평균한다 — 큰 칸(예: confirm_request)에 끌린 정확도가 작은 칸의 틀림을 가리지 못하게 한다.
★pass@k 는 k 판 중 한 번이라도 통과, pass^k 는 k 판 모두 통과다. 운영은 매번 맞아야 하므로 pass^k 를 주로 본다.
  과제 하나를 n 판 돌려 c 판 통과했을 때 — pass@k = 1 − C(n−c, k) / C(n, k) · pass^k = C(c, k) / C(n, k) (과제 평균).
"""
from __future__ import annotations

from collections import defaultdict
from math import comb
from typing import Any, Hashable, Iterable, Mapping, Sequence


def ratio(num: int, den: int) -> dict[str, Any]:
    return {"num": num, "den": den, "rate": round(num / den, 3) if den else None}


def prf(tp: int, fp: int, fn: int) -> dict[str, dict[str, Any]]:
    """정밀도(낸 것 중 맞음) · 재현율(내야 할 것 중 냄) · F1(둘의 조화평균)."""
    return {"precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn), "f1": ratio(2 * tp, 2 * tp + fp + fn)}


def f_beta(tp: int, fp: int, fn: int, beta: float) -> float | None:
    """beta > 1 이면 재현율을 무겁게 본다 — F2 는 빠뜨림이 쓸데없는 것보다 나쁠 때 쓴다."""
    b2 = beta * beta
    den = (1 + b2) * tp + b2 * fn + fp
    return round((1 + b2) * tp / den, 3) if den else None


def per_label(pairs: Iterable[tuple[Hashable, Hashable | None]]) -> dict[str, Any]:
    """(정답, 예측) 쌍 → 칸마다 정밀도 · 재현율 · F1, 그리고 macro-F1 · 정확도.

    칸은 정답이나 예측에 나온 것 모두다 — 예측에만 나온 칸은 F1 0 으로 평균을 끌어내린다(지어낸 라벨도 벌점).
    단일 라벨 분류에서 micro-F1 은 정확도와 같아 따로 내지 않는다.
    """
    tp: dict[Hashable, int] = defaultdict(int)
    fp: dict[Hashable, int] = defaultdict(int)
    fn: dict[Hashable, int] = defaultdict(int)
    labels: set[Hashable] = set()
    n = hit = 0
    for expected, predicted in pairs:
        n += 1
        labels.add(expected)
        if predicted == expected:
            tp[expected] += 1
            hit += 1
            continue
        fn[expected] += 1
        if predicted is not None:
            labels.add(predicted)
            fp[predicted] += 1
    by_label = {str(label): prf(tp[label], fp[label], fn[label]) for label in sorted(labels, key=str)}
    f1s = [scores["f1"]["rate"] for scores in by_label.values() if scores["f1"]["rate"] is not None]
    return {"accuracy": ratio(hit, n), "macro_f1": round(sum(f1s) / len(f1s), 3) if f1s else None, "labels": by_label}


def pass_at_k(n: int, c: int, k: int) -> float:
    """n 판 중 c 판 통과 — k 판을 뽑았을 때 하나라도 통과할 확률."""
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """n 판 중 c 판 통과 — k 판을 뽑았을 때 모두 통과할 확률."""
    return comb(c, k) / comb(n, k)


def pass_k(outcomes: Mapping[Hashable, Sequence[bool]], k: int | None = None) -> dict[str, Any] | None:
    """과제마다 판별 통과 여부 → 과제 평균 pass@k · pass^k. k 를 안 주면 가장 적게 돈 과제의 판 수다.

    k 판보다 적게 돈 과제는 빼고 `skipped` 로 센다(조용히 빼지 않는다).
    """
    trials = {key: list(values) for key, values in outcomes.items() if values}
    if not trials:
        return None
    k = k or min(len(values) for values in trials.values())
    usable = [values for values in trials.values() if len(values) >= k]
    if not usable:
        return {"k": k, "tasks": 0, "skipped": len(trials), "pass_at_k": None, "pass_hat_k": None,
                "all_trials_pass": ratio(0, 0)}
    at = [pass_at_k(len(v), sum(v), k) for v in usable]
    hat = [pass_hat_k(len(v), sum(v), k) for v in usable]
    return {"k": k, "tasks": len(usable), "skipped": len(trials) - len(usable),
            "pass_at_k": round(sum(at) / len(at), 3), "pass_hat_k": round(sum(hat) / len(hat), 3),
            "all_trials_pass": ratio(sum(all(v) for v in usable), len(usable))}
