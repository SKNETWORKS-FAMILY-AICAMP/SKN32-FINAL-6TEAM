"""계획 읽기 다양한 입력 시험지 — 정답 · 채점기 점검(`eval/intake_diverse`). 모델 · DB · 네트워크를 쓰지 않는다."""
import json
from pathlib import Path

from eval.intake_diverse.run_current import adapt, oracle
from eval.intake_diverse.score import FIELDS, score_all, score_case

CASES = [json.loads(line) for line in (Path(__file__).resolve().parents[1] / "intake_diverse" / "cases.jsonl")
         .read_text(encoding="utf-8").splitlines() if line.strip()]


def test_gold_places_are_verbatim_substrings_of_the_input():
    assert len(CASES) == 69
    for case in CASES:
        for item in case["gold"]["items"]:
            assert item["place"] in case["source_text"], (case["case_id"], item["place"])


def test_oracle_scores_full_marks_on_every_field():
    result = score_all(CASES, {c["case_id"]: {**oracle(c), "error": None} for c in CASES})
    for key, (hit, total) in result["totals"]["전체"].items():
        if key == "tamper":
            assert hit == 0
        elif total:
            assert hit == total, key


def test_a_failed_read_counts_every_gold_field_wrong():
    case = next(c for c in CASES if c["case_id"] == "A01")
    got = score_case(case, {"error": "boom"})
    assert got["items"][0] == 0 and got["items"][1] > 0
    assert got["moves"] == [0, 1] and got["requests_exact"] == [0, 1]
    assert set(got) == set(FIELDS)


def test_adapter_reads_claim_rows_into_the_neutral_shape():
    rows = [{"field": "items[0].title", "value": "광장시장 빈대떡"}, {"field": "items[0].starts_at", "value": "12:30"},
            {"field": "items[0].date", "value": "2026-10-22"}, {"field": "items[0].kind", "value": "dining"},
            {"field": "trip.party_size", "value": 2}, {"field": "trip.plan_request", "value": True},
            {"field": "trip.ask_first_day", "value": True}]
    pred = adapt(rows)
    assert pred["items"] == [{"title": "광장시장 빈대떡", "date": "2026-10-22", "start": "12:30", "end": None, "kind": "dining", "place_name": None}]
    assert pred["requests"] == ["plan_ask", "register"] and pred["missing"] == ["first_day_date"] and pred["trip"] == {"party_size": 2}
