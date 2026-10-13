from score_misanswer_frozen import score


def test_failures_and_missing_decisions_remain_in_denominator():
    pool = [{"src": "일상 대화(AI Hub)", "label": "chitchat", "q": q} for q in ("정상", "실패", "대기")]
    result = score(pool, {"정상": {"action": "other", "item": "none"}, "실패": {"error": "timeout"}})["unrelated_conversation"]
    assert result["denominator"] == 3
    assert (result["completed"], result["failed"], result["unfinished"], result["unresolved"]) == (1, 1, 1, 2)


def test_duplicate_rows_and_policy_recognition_are_not_source_correctness():
    row = {"src": "합성 A", "label": "answerable", "q": "취소 규정", "gold": ["cancellation"]}
    result = score([row, dict(row)], {row["q"]: {"action": "ask_policy", "item": "none"}},
                   {row["q"]: {"sources": ["weather"]}})["answerable_policy"]
    assert result["denominator"] == 2 and result["recognized_policy"] == 2
    assert result["correct_policy_source"] == 0
