# -*- coding: utf-8 -*-
"""여행 인라인 분류 평가 자료와 재생 시험 도구. `[2026-10-03]`

☆왜: 평가 자료(golden 72 · holdout 24)가 쇼핑몰 문장(주문 · 배송 · 반품 · 교환)이었다 — 여행 분류 정확도는 재지 못했다. 여행 문장으로 새로 만들었다.

★지키려는 것
 ①자료의 라벨이 **서버 어휘**(`feedback.INTENTS` · `ISSUE_CODES` …)에 있고, `other` 는 의도와 코드가 한 쌍이며, 쇼핑몰 낱말이 섞이지 않는다 — 검사기가 이것을 **실제로 잡는다**(깨뜨려 본다)
 ②재생 시험은 실패(`failed`)를 **틀린 것으로 센다** — 분모에서 빼면 성공률이 부풀려진다
 ③엉뚱한 팀으로 가는 것(`wrong_team`)과 `other` 로 답해 escalate 되는 것(`unrouted`)을 가른다 — 앞쪽이 위험하다

재현:

    python -m pytest tests/unit/eval/test_travel_classification_eval.py -v
"""
from __future__ import annotations

import copy

import pytest

from eval.travel_classification.replay import load, run
from scripts import verify_travel_eval_datasets as verify


@pytest.fixture(scope="module")
def data():
    return load(verify.GOLDEN), load(verify.HOLDOUT)


def test_the_shipped_datasets_pass_the_checker(data):
    golden, holdout = data
    assert verify.check(golden, holdout) == []


def test_the_checker_catches_a_commerce_sentence_an_unknown_label_and_a_broken_other_pair(data):
    golden, holdout = copy.deepcopy(data[0]), data[1]
    golden[0]["message"] = "주문번호를 잊어버렸는데 가입한 전화번호로 조회할 수 있을까요?"
    golden[1]["expected_issue_code"] = "order_lookup_by_phone"
    golden[2]["expected_intent"] = "other"                                         # 코드는 activity_ 인데 의도만 other
    found = "\n".join(verify.check(golden, holdout))
    assert "쇼핑몰 시절 낱말" in found and "서버 어휘에 없다" in found and "한 쌍이다" in found


def test_the_checker_catches_overlap_and_thin_coverage(data):
    golden, holdout = copy.deepcopy(data[0]), copy.deepcopy(data[1])
    holdout[0]["message"] = golden[5]["message"]
    golden = [row for row in golden if row["expected_issue_code"] != "flight_other"]
    found = "\n".join(verify.check(golden, holdout))
    assert "같은 문장" in found and "golden 커버리지 부족: flight_other" in found


# ── 재생 시험 ─────────────────────────────────────────────────────

class _Got:
    def __init__(self, intent, issue_code, sentiment="neutral", severity="low"):
        self.intent, self.issue_code, self.sentiment, self.severity = intent, issue_code, sentiment, severity


def _oracle(rows):
    by_message = {row["message"]: row for row in rows}
    return lambda text: _Got(*(by_message[text][f"expected_{k}"] for k in ("intent", "issue_code", "sentiment", "severity")))


def test_a_perfect_classifier_scores_everything(data):
    rows = data[0]
    summary = run(rows, _oracle(rows))
    assert summary["cases"] == 72 and summary["failed"] == 0 and summary["wrong_team"] == 0 and summary["unrouted"] == 0
    assert summary["both"] == summary["case_type"] == summary["intent"] == 1.0


def test_a_failure_counts_as_wrong_and_stays_in_the_denominator(data):
    rows = data[0][:10]
    oracle = _oracle(rows)

    def flaky(text):
        if text == rows[0]["message"]:
            raise RuntimeError("provider down")
        return oracle(text)

    summary = run(rows, flaky)
    assert summary["cases"] == 10 and summary["failed"] == 1
    assert summary["both"] == 0.9 and "provider down" in summary["failures"][0]["error"]


def test_wrong_team_and_unrouted_are_told_apart(data):
    dining = next(r for r in data[0] if r["expected_issue_code"] == "dining_hours")
    mobility = next(r for r in data[0] if r["expected_issue_code"] == "mobility_other")
    answers = {dining["message"]: _Got("incident_report", "mobility_missed_or_disrupted"),        # 식당 문제를 이동 팀으로
               mobility["message"]: _Got("other", "other")}                                      # 이동 문의를 어디에도 안 붙임(escalate)
    summary = run([dining, mobility], lambda text: answers[text])
    assert summary["wrong_team"] == 1 and summary["wrong_team_cases"] == [dining["case_id"]]
    assert summary["unrouted"] == 1 and summary["case_type"] == 0.0
    assert summary["top_confusions"][0]["expected"] in ("dining_hours", "mobility_other")


def test_repeats_multiply_the_denominator(data):
    rows = data[0][:5]
    summary = run(rows, _oracle(rows), repeats=3)
    assert summary["cases"] == 15 and summary["both"] == 1.0
