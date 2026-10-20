# -*- coding: utf-8 -*-
"""평가 공통 점수(`eval/stats/scores.py`) — 정밀도 · 재현율 · F1 · macro-F1 · pass@k / pass^k. `[2026-10-19]`

★지키려는 것
 ①비율마다 분자 · 분모가 같이 나온다 — F1 도 2·TP / (2·TP + FP + FN) 분수로 낸다
 ②예측 실패(None)는 정답 칸의 놓침(FN)이다 — 분모에서 빠지지 않고, 어느 칸의 FP 도 되지 않는다
 ③macro-F1 은 작은 칸을 틀리면 정확도보다 크게 떨어진다 — 큰 칸에 끌린 정확도를 드러낸다
 ④pass^k 는 k 판 모두 통과, pass@k 는 한 번이라도 통과다 — 75% 과제를 3판 돌리면 pass^3 ≈ 42%

재현:

    python -m pytest tests/unit/eval/test_eval_scores.py -v
"""
from __future__ import annotations

import pytest

from eval.stats.scores import f_beta, pass_at_k, pass_hat_k, pass_k, per_label, prf


def test_prf_gives_each_rate_as_a_fraction():
    got = prf(tp=8, fp=2, fn=4)
    assert got["precision"] == {"num": 8, "den": 10, "rate": 0.8}
    assert got["recall"] == {"num": 8, "den": 12, "rate": 0.667}
    assert got["f1"] == {"num": 16, "den": 22, "rate": 0.727}                 # 2·8 / (2·8 + 2 + 4)


def test_prf_with_nothing_to_score_has_no_rate():
    assert prf(0, 0, 0)["f1"] == {"num": 0, "den": 0, "rate": None}
    assert prf(0, 3, 0)["precision"]["rate"] == 0.0 and prf(0, 3, 0)["recall"]["rate"] is None


def test_f2_weights_recall_more_than_f1_does():
    # 같은 오류 수라도 빠뜨림(FN)이 많으면 F2 가 더 떨어진다
    assert f_beta(8, fp=0, fn=4, beta=2) < f_beta(8, fp=4, fn=0, beta=2)
    assert f_beta(8, 2, 4, beta=1) == prf(8, 2, 4)["f1"]["rate"]
    assert f_beta(0, 0, 0, beta=2) is None


def test_per_label_counts_a_failure_as_a_miss_not_as_a_false_alarm():
    got = per_label([("ok", "ok"), ("ok", None), ("bad", "bad")])
    assert got["accuracy"] == {"num": 2, "den": 3, "rate": 0.667}
    assert got["labels"]["ok"]["recall"] == {"num": 1, "den": 2, "rate": 0.5}
    assert got["labels"]["ok"]["precision"] == {"num": 1, "den": 1, "rate": 1.0}
    assert got["labels"]["bad"]["f1"]["rate"] == 1.0 and "None" not in got["labels"]


def test_macro_f1_drops_when_a_small_label_is_always_wrong():
    # 큰 칸 9개는 다 맞고 작은 칸 1개를 큰 칸으로 — 정확도 90% 인데 macro-F1 은 절반쯤이다
    pairs = [("confirm", "confirm")] * 9 + [("other", "confirm")]
    got = per_label(pairs)
    assert got["accuracy"]["rate"] == 0.9
    assert got["labels"]["other"]["f1"]["rate"] == 0.0
    assert got["macro_f1"] == pytest.approx((18 / 19 + 0.0) / 2, abs=1e-3)


def test_a_label_only_predicted_still_enters_the_macro_average():
    got = per_label([("a", "a"), ("a", "z")])
    assert set(got["labels"]) == {"a", "z"} and got["labels"]["z"]["f1"]["rate"] == 0.0
    assert got["macro_f1"] == pytest.approx((2 / 3) / 2, abs=1e-3)


def test_pass_estimators_match_the_definitions():
    assert pass_hat_k(3, 3, 3) == 1.0 and pass_hat_k(3, 2, 3) == 0.0
    assert pass_at_k(3, 1, 3) == 1.0 and pass_at_k(3, 0, 3) == 0.0
    assert pass_hat_k(4, 3, 2) == pytest.approx(3 / 6)                       # C(3,2) / C(4,2)
    assert pass_at_k(4, 1, 2) == pytest.approx(1 - 3 / 6)                    # 1 − C(3,2) / C(4,2)


def test_pass_k_averages_over_tasks_and_uses_the_fewest_trials_by_default():
    got = pass_k({"t1": [True, True, True], "t2": [True, False, True], "t3": [False, False, False]})
    assert got["k"] == 3 and got["tasks"] == 3 and got["skipped"] == 0
    assert got["pass_hat_k"] == 0.333 and got["pass_at_k"] == 0.667
    assert got["all_trials_pass"] == {"num": 1, "den": 3, "rate": 0.333}


def test_pass_k_skips_tasks_with_fewer_trials_than_k_and_says_so():
    got = pass_k({"t1": [True, True, True], "t2": [True]}, k=3)
    assert got["tasks"] == 1 and got["skipped"] == 1 and got["pass_hat_k"] == 1.0
    assert pass_k({}) is None


def test_pass_hat_k_falls_well_below_the_single_run_rate():
    # 4판 중 3판 성공 — 한 판 성공률은 75% 인데 세 판 모두 통과할 확률은 C(3,3)/C(4,3) = 25%
    assert pass_at_k(4, 3, 1) == pytest.approx(0.75) == pass_hat_k(4, 3, 1)
    assert pass_hat_k(4, 3, 3) == pytest.approx(1 / 4)


def test_code_version_hashes_content_not_line_endings(tmp_path, monkeypatch):
    from eval.stats import provenance

    monkeypatch.setattr(provenance, "ROOT", tmp_path)
    (tmp_path / "a.py").write_bytes(b"x = 1\r\n")
    first = provenance.code_version(["a.py"])
    (tmp_path / "a.py").write_bytes(b"x = 1\n")
    assert provenance.code_version(["a.py"])["files"] == first["files"]
    (tmp_path / "a.py").write_bytes(b"x = 2\n")
    assert provenance.code_version(["a.py"])["bundle"] != first["bundle"]
