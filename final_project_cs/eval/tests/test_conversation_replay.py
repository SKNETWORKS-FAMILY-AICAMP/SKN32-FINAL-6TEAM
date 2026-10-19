# -*- coding: utf-8 -*-
"""실제 여행 대화 재생 시험 도구(`eval/conversation_replay`) — 합성 예시 3개로 채점 · 갈림 · 녹화 · 판정 규칙을 시험한다. DB · 모델 없이 돈다."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from eval.conversation_replay import compile as C
from eval.conversation_replay import episodes as E
from eval.conversation_replay import recorder as R
from eval.conversation_replay import stats
from eval.conversation_replay.conditions import FAIL, PASS, UNKNOWN, evaluate
from eval.conversation_replay.patterns import answer_shape, claims_done, fail_types, fact_values
from eval.conversation_replay.runner import Harness
from eval.conversation_replay.score import score_episode
from eval.conversation_replay.state import Item, TripView

EX = Path(__file__).resolve().parents[1] / "conversation_replay" / "examples"


@pytest.fixture(scope="module")
def eps():
    return {e["episode_id"]: e for e in E.load(EX / "synthetic.jsonl")}


@pytest.fixture(scope="module")
def compiled(eps):
    rows = {json.loads(x)["episode_id"]: json.loads(x) for x in (EX / "synthetic_compiled.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    return {k: C.compile_episode(ep, rows.get(k)) for k, ep in eps.items()}


def _turn(text, answer, *, view, saved, role="새 요청", choices=None, mode="A", open_question=None):
    from eval.conversation_replay.patterns import is_open_question

    return {"customer": text, "role": role, "answer": answer, "saved": saved, "view_after": view.as_dict(), "choices": choices or [],
            "open_question": is_open_question(answer, choices) if open_question is None else open_question, "mode": mode,
            "seconds": 1.0, "evidence": "", "fail_types": fail_types(answer)}


def _start(ep):
    return TripView.from_dict(ep["start"])


def _without(view, seq):
    v = copy.deepcopy(view)
    v.items = [i for i in v.items if i.seq != seq]
    v.version += 1
    return v


def _replace(view, seq, *, place, indoor):
    v = copy.deepcopy(view)
    old = v.by_seq(seq)
    new = Item(item_id=old.item_id + "-new", seq=seq, kind=old.kind, title=place, place=place, start=old.start, end=old.end,
               indoor=indoor, replaces=old.item_id)
    v.items = [new if i.seq == seq else i for i in v.items]
    v.lineage[new.item_id] = old.item_id
    v.version += 1
    return v


def test_every_example_condition_is_compiled_none_is_left_for_people(compiled):
    for c in compiled.values():
        left = [x["text"] for x in c["end"] + c["forbidden"] if x["by"] == "none"]
        assert left == [], left


def test_remove_request_done_and_completion_claim_matches_the_save(eps, compiled):
    ep = eps["S1-remove-dinner"]
    start = _start(ep)
    end = _without(start, 2)
    res = {"start": start.as_dict(), "end": end.as_dict(), "turns": [_turn("저녁 빼줘", "저녁 일정을 뺐어요.", view=end, saved=True)]}
    s = score_episode(res, compiled[ep["episode_id"]], ep)
    assert s["done"]["verdict"] == PASS, s["done"]
    assert s["false_done"] == {"opportunities": 1, "fail": 0, "unknown": 0, "turns": []}
    assert s["wrong_save"]["opportunities"] == 1 and s["wrong_save"]["fail"] == 0


def test_replacing_instead_of_removing_is_a_wrong_save(eps, compiled):
    ep = eps["S1-remove-dinner"]
    start = _start(ep)
    end = _replace(start, 2, place="합성식당 라", indoor=True)
    res = {"start": start.as_dict(), "end": end.as_dict(),
           "turns": [_turn("저녁 빼줘", "요청하신 대로 합성식당 라(으)로 바꿨습니다.", view=end, saved=True)]}
    s = score_episode(res, compiled[ep["episode_id"]], ep)
    assert s["wrong_save"]["fail"] == 1 and "다른 식당으로 교체 금지" in s["wrong_save"]["cases"][0]["failed"]
    assert s["done"]["verdict"] == FAIL


def test_saying_done_without_a_new_version_is_a_false_completion(eps, compiled):
    ep = eps["S1-remove-dinner"]
    start = _start(ep)
    res = {"start": start.as_dict(), "end": start.as_dict(), "turns": [_turn("저녁 빼줘", "저녁 일정을 뺐어요.", view=start, saved=False)]}
    s = score_episode(res, compiled[ep["episode_id"]], ep)
    assert s["false_done"]["fail"] == 1
    assert s["done"]["verdict"] == FAIL           # 끝 상태(seq=2 없음) 미충족 + 「저장된 변경과 완료 답변 일치」 위반


def test_rain_to_outdoor_replacement_is_a_condition_violation(eps, compiled):
    ep = eps["S3-rain-indoor"]
    start = _start(ep)
    end = _replace(start, 2, place="다른 합성공원", indoor=False)
    res = {"start": start.as_dict(), "end": end.as_dict(),
           "turns": [_turn("비 와요. 공원 산책 실내로 바꿔주세요", "다른 합성공원(으)로 바꿨어요.", view=end, saved=True)]}
    s = score_episode(res, compiled[ep["episode_id"]], ep)
    assert s["condition"]["opportunities"] == 1 and s["condition"]["verdict"] == FAIL
    assert s["wrong_save"]["fail"] == 1 and s["done"]["verdict"] == FAIL


def test_unknown_indoor_is_not_counted_as_pass(eps, compiled):
    ep = eps["S3-rain-indoor"]
    start = _start(ep)
    end = _replace(start, 2, place="실내외 모르는 곳", indoor=None)
    res = {"start": start.as_dict(), "end": end.as_dict(), "turns": [_turn("비 와요", "실내외 모르는 곳으로 바꿨어요.", view=end, saved=True)]}
    s = score_episode(res, compiled[ep["episode_id"]], ep)
    assert s["condition"]["verdict"] == UNKNOWN and s["done"]["verdict"] == UNKNOWN


def test_short_answer_diverges_when_the_bot_did_not_ask_this_time(eps, compiled):
    ep = eps["S2-short-answer"]
    start = _start(ep)
    h = Harness(rec=R.Recorder(cassette=Path("unused.jsonl")), customer=None, turn_cap=4)
    asked = _turn("점심 다른 데로", "어느 곳으로 바꿀까요? 1) 가 2) 나 번호로 골라 주세요.", view=start, saved=False,
                  choices=[{"label": "가"}, {"label": "나"}])
    changed = _turn("점심 다른 데로", "점심을 합성식당 마(으)로 바꿨어요.", view=_replace(start, 1, place="합성식당 마", indoor=True), saved=True)
    assert h._diverges(ep, 1, asked, start, [asked], compiled[ep["episode_id"]]) is None
    assert h._diverges(ep, 1, changed, start, [changed], compiled[ep["episode_id"]]).startswith("b)")


def test_repeat_after_the_request_is_already_reflected_diverges(eps, compiled):
    ep = eps["S3-rain-indoor"]
    start = _start(ep)
    h = Harness(rec=R.Recorder(cassette=Path("unused.jsonl")), customer=None, turn_cap=4)
    end = _replace(start, 2, place="합성미술관", indoor=True)
    done = _turn("비 와요. 공원 산책 실내로 바꿔주세요", "합성미술관으로 바꿨어요.", view=end, saved=True)
    assert h._diverges(ep, 1, done, start, [done], compiled[ep["episode_id"]]).startswith("c)")
    assert h._finished(start, [done], compiled[ep["episode_id"]])      # 일찍 끝남 — 남은 원문을 보내지 않는다


def test_same_question_after_a_valid_answer_is_counted(eps, compiled):
    ep = eps["S2-short-answer"]
    start = _start(ep)
    q = "되돌릴까요? 네/아니요로 답해 주세요."
    res = {"start": start.as_dict(), "end": start.as_dict(),
           "turns": [_turn("되돌려", q, view=start, saved=False), _turn("ㅇㅇ", q, view=start, saved=False, role="직전 봇 질문의 답")]}
    s = score_episode(res, compiled[ep["episode_id"]], ep)
    assert s["repeat_question"] == {"opportunities": 1, "fail": 1, "turns": [1]}


def test_model_error_answer_counts():
    assert "모델 오류" in fail_types("지금 요청을 해석하지 못했어요(해석 모델 응답 오류) — 일정은 바꾸지 않았어요.")
    assert claims_done("요청하신 대로 백년옥으로 바꿨습니다") and not claims_done("일정은 바꾸지 않았어요. 바꿨던 안은 그대로예요")
    assert answer_shape("2", 3) == "number" and answer_shape("5", 3) is None and answer_shape("ㅇㅇ") == "yes"
    assert ("time", "09:00") in fact_values("운영시간은 09:00~18:00 이에요") and fact_values("10:30 경복궁 일정이에요") == []


def test_condition_language_basics(eps):
    start = _start(eps["S1-remove-dinner"])
    end = _without(start, 2)
    kw = dict(start=start, end=end, answers=["저녁을 뺐어요"], saves=1)
    assert evaluate({"op": "absent", "match": {"name": "합성식당 가"}}, **kw) == PASS
    assert evaluate({"op": "unchanged", "match": {"seq": [1, 3]}}, **kw) == PASS
    assert evaluate({"op": "count", "eq": 2}, **kw) == PASS
    assert evaluate({"op": "answer", "any": ["뺐어요"]}, **kw) == PASS
    assert evaluate({"op": "manual"}, **kw) == UNKNOWN
    assert evaluate({"op": "answer_judge", "criterion": "뺐다고 말함"}, **kw) == UNKNOWN
    assert evaluate({"op": "answer_judge", "criterion": "뺐다고 말함"}, **kw, judge=lambda c, a: PASS) == PASS
    assert C.validate({"op": "field", "match": {"seq": 1}, "field": "colour", "eq": 1})
    assert C.validate({"op": "time", "match": {"seq": 1}, "start": "13:00", "end": "14:30"}) is None


def test_judgement_rules_match_the_plan():
    assert abs(stats.tolerance(150) - 0.0716) < 0.0005 and stats.tolerance(10_000) == 0.05
    assert stats.zero_needed() == 299
    v = stats.rate_verdict("x", "잘못된 저장", "zero", 0, 120)
    assert v["verdict"] == "표본 부족"
    assert stats.rate_verdict("x", "잘못된 저장", "zero", 1, 400)["verdict"] == "불합격"
    p = stats.paired({str(i): i < 50 for i in range(150)}, {str(i): i < 80 for i in range(150)}, reps=2000)
    assert p["b"] == 30 and p["c"] == 0 and p["improved"] and p["mcnemar_p"] < 0.001
    assert stats.fix_absolute(0.05, kind="fail_ceiling")["value"] is None
    assert abs(stats.fix_absolute(0.4, kind="done_floor")["value"] - 0.5) < 1e-9


def test_recorder_records_then_replays_and_never_keeps_the_key(tmp_path):
    cas = tmp_path / "c.jsonl"
    rec = R.Recorder(cassette=cas, mode="record", rules=R.default_rules(llm_hosts={"127.0.0.1:11435"}))
    sent = []

    def send(url):
        sent.append(url)
        return 200, {"content-type": "application/json"}, b'{"ok": 1}'

    url = "https://apis.data.go.kr/B551011/KorService2/searchKeyword2?serviceKey=SECRET&keyword=%EA%B2%BD%EB%B3%B5%EA%B6%81"
    assert rec.handle("GET", url, None, send)[2] == b'{"ok": 1}'
    assert "SECRET" not in cas.read_text(encoding="utf-8")
    again = R.Recorder(cassette=cas, mode="replay", rules=R.default_rules(llm_hosts=set()), live_on_miss=False)
    assert again.handle("GET", url.replace("SECRET", "OTHER"), None, send)[0] == 200 and len(sent) == 1
    with pytest.raises(ConnectionError):
        again.handle("GET", "https://apis.data.go.kr/other", None, send)
    assert again.summary()["by_rule"]["public"]["replayed"] == 1


def test_recorder_stops_at_the_paid_budget(tmp_path):
    rules = R.default_rules(llm_hosts=set())
    for r in rules:
        if r.name == "llm_paid":
            r.budget = 1
    rec = R.Recorder(cassette=tmp_path / "c.jsonl", mode="replay", rules=rules)
    ok = lambda url: (200, {}, b"{}")  # noqa: E731
    rec.handle("POST", "https://api.openai.com/v1/chat/completions", b"{}", ok)
    with pytest.raises(R.BudgetExceeded):
        rec.handle("POST", "https://api.openai.com/v1/chat/completions", b"{}", ok)
    token = R.pause()                       # 시험 도구 자신의 호출(고객 역할 · 판정 모델)은 예산 밖
    try:
        rec.handle("POST", "https://api.openai.com/v1/chat/completions", b"{}", ok)
    finally:
        R.resume(token)


def test_turn_cap_is_p95_plus_two(eps):
    real = [{"set": "real", "script": [{}] * n} for n in [1] * 90 + [2] * 6 + [5] * 4]
    assert E.turn_cap(real) == 4
