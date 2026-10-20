"""대체 후보 1순위 판정 평가 — 사례 만들기 · 실행(가짜 LLM) · 채점 갈래(M1~M8) · 전환 기준. DB · 외부 호출 없이."""
from __future__ import annotations

import asyncio
import csv
import json
from types import SimpleNamespace

import pytest

from eval.alternative_pick import build, run, score

IDS = ["a1", "b2", "c3"]


def case(case_id="X-01", *, text="실내로 바꿔 주세요", survey=None, acceptable=("b2",), forbidden=("c3",),
         stratum="B", quiet=False, claims=()):
    return {"case_id": case_id, "kind": "alternative_pick", "split": "holdout", "stratum": stratum,
            "inputs": {"origin": "경복궁", "at": "2026-11-16T14:00:00+09:00",
                       "candidates": [{"id": i, "title": f"장소{i}", "code_reason": "1.0km", "distance_km": 1.0,
                                       "class": "HS010100"} for i in IDS],
                       "preference": {"survey": survey or {}, "customer_text": text}},
            "acceptable": list(acceptable), "forbidden": list(forbidden), "expects_code_order": quiet,
            "forbidden_claims": list(claims), "rationale": "", "label_by": "사람", "text_by": "writer"}


def answer(order, used=True, reason="실내 시설이라 먼저 보여 드려요"):
    async def ask(_body):
        return SimpleNamespace(output={"order": order, "used_preference": used, "reason": reason}, model="m",
                               latency_ms=100, input_tokens=10, output_tokens=5, reasoning_tokens=0)
    return ask


def observe(c, ask, variant="base", repeat=1, order=None):
    return asyncio.run(run.observe(c, variant, repeat, order or IDS, ask, timeout=1.0))


# ── 사례 만들기 ───────────────────────────────────────────

def test_smoke_build_covers_all_cards_with_inputs_only_hash(tmp_path):
    cards = build.load_cards()
    cases = build.build(cards, smoke=True)
    assert len(cases) == len(cards) == 80
    assert all(c["inputs"]["preference"]["customer_text"] for c in cases)
    manifest = build.write(cases, tmp_path / "c.jsonl", {"smoke": True})
    relabeled = [{**c, "acceptable": []} for c in cases]
    assert build.inputs_digest(relabeled) == manifest["inputs_sha256"]       # 라벨만 바뀌면 입력 해시는 같다
    assert build.load_cases(tmp_path / "c.jsonl")[1]["sha256"] == manifest["sha256"]


def test_label_numbers_become_candidate_ids_and_missing_cards_stop():
    card = build.load_cards()[0]
    ids = [c["id"] for c in card["candidates"]]
    labels = {card["card_id"]: {"acceptable": ["2", "3"], "forbidden": ["1"]}}
    [c] = build.build([card], smoke=False, texts={card["card_id"]: "아무 데나"}, labels=labels, labeler="갑")
    assert c["acceptable"] == ids[1:] and c["forbidden"] == ids[:1] and c["split"] == "holdout"
    with pytest.raises(SystemExit):
        build.build([card], smoke=False, texts={}, labels=labels, labeler="갑")


def test_tampered_dataset_is_refused(tmp_path):
    path = tmp_path / "c.jsonl"
    build.write([case()], path, {})
    path.write_text(path.read_text(encoding="utf-8").replace("경복궁", "창덕궁"), encoding="utf-8")
    with pytest.raises(SystemExit):
        build.load_cases(path)


# ── 실행 ──────────────────────────────────────────────────

def test_no_cue_is_not_called_like_production():
    row = observe(case(text=""), answer(IDS))
    assert row["status"] == "not_called" and row["applied"] is None


def test_timeout_and_error_are_call_failures():
    async def slow(_body):
        await asyncio.sleep(5)

    async def boom(_body):
        raise RuntimeError("no active prompt registered")

    assert observe(case(), slow)["status"] == "llm_timeout"
    row = observe(case(), boom)
    assert row["status"] == "llm_error" and "RuntimeError" in row["error"]


def test_shuffle_plan_is_seeded_and_moves_first_place():
    cases = [case(f"X-{i:02d}") for i in range(10)]
    plan = run.shuffle_plan(cases, n_cases=4, n_shuffles=2, seed=7)
    assert plan == run.shuffle_plan(cases, n_cases=4, n_shuffles=2, seed=7)
    assert len(plan) == 4 and all(len(v) == 2 and all(p[0] != IDS[0] for p in v) for v in plan.values())
    assert len(run.jobs(cases, repeats=3, plan=plan)) == 10 * 3 + 4 * 2


def test_run_appends_and_resume_skips_done(tmp_path):
    results = tmp_path / "results.jsonl"
    todo = run.jobs([case()], repeats=2, plan={})
    asyncio.run(run.run(todo[:1], answer(IDS, used=False, reason=""), timeout=1, concurrency=2, results=results))
    left = [j for j in todo if (j[0]["case_id"], j[1], j[2]) not in run.done_keys(results)]
    assert len(left) == 1 and left[0][2] == 2


# ── 채점 ──────────────────────────────────────────────────

def test_judge_branches():
    c = case()
    good = score.judge(c, observe(c, answer(["b2", "a1", "c3"])))
    assert (good["served_outcome"], good["usage"], good["dangerous"]) == ("correct", "valid", False)

    partial = score.judge(c, observe(c, answer(["b2"])))                       # 빠진 후보를 코드가 뒤에 붙임
    assert partial["usage"] == "corrected" and partial["served_first"] == "b2"

    no_reason = score.judge(c, observe(c, answer(["c3", "a1", "b2"], used=False, reason="")))
    assert no_reason["usage"] == "discarded" and no_reason["served_first"] == "a1"   # 버려서 코드 순서

    danger = score.judge(c, observe(c, answer(["c3", "a1", "b2"])))
    assert danger["dangerous"] and danger["served_dangerous"]

    # 범위 이탈 — 원답은 위험, 보정 후는 고객에게 안 나감
    outside = score.judge(c, observe(c, answer(["lotte", "b2"])))
    assert outside["raw_outside"] and outside["dangerous"] and not outside["served_dangerous"]
    assert outside["served_first"] == "b2" and outside["usage"] == "corrected"


def test_reason_flags_banned_words_card_claims_and_won():
    c = case(claims=("한적",))
    assert score.flags("입장료 3,000원이라 한적해요", c) == ["…원", "입장료", "한적"]
    assert score.flags("실내 시설이라 비를 피할 수 있어요", c) == []


def summary_for(rows_by_case, extra_conditions=None, reasons=None):
    cases = {c["case_id"]: c for c, _ in rows_by_case}
    rows = [r for _, rs in rows_by_case for r in rs]
    conditions = {"split": ["holdout"], "smoke": False, "dry_run": False, **(extra_conditions or {})}
    return score.summarize(cases, rows, conditions, reasons, n_boot=200)


def test_summary_counts_and_gate():
    better = case("B-01")                       # 코드 1순위 a1 은 허용 밖 — LLM 이 b2 로 올리면 개선
    quiet = case("A-01", text="아무 데나요", acceptable=IDS, forbidden=(), stratum="A", quiet=True)
    rows = [
        (better, [observe(better, answer(["b2", "a1", "c3"]), repeat=r) for r in (1, 2, 3)]
         + [observe(better, answer(["b2", "c3", "a1"]), variant="shuffle-1", order=["c3", "b2", "a1"])]),
        (quiet, [observe(quiet, answer(IDS, used=False, reason=""), repeat=r) for r in (1, 2, 3)]),
    ]
    s = summary_for(rows)
    assert s["M1_served"]["num"] == 6 and s["M1_served"]["den"] == 6
    assert s["baseline_code_order"]["num"] == 1 and s["M3_llm_minus_code"]["value"] == 0.5
    assert s["M4_keep_code_order"] == {"num": 3, "den": 3, "pct": 100.0}
    assert s["M6b_used"]["num"] == 7 and s["M6e_call_failed"]["num"] == 0
    assert s["M7_consistent"]["num"] == 2
    assert s["M8_position_stable"]["num"] == 1 and s["M8_position_stable"]["den"] == 1
    assert s["M5_reason_grounded"]["status"] == "pending"
    assert s["gate"]["checks"]["M5 심각 = 0"] is None and s["gate"]["verdict"].startswith("확인 전")
    assert s["gate"]["checks_before"]["M5 = 100%"] is None

    keys = {("B-01", "base", r): score.GROUNDED for r in (1, 2, 3)} | {("B-01", "shuffle-1", 1): score.GROUNDED}
    s2 = summary_for(rows, reasons=keys)
    assert s2["M5_reason_grounded"]["status"] == "reviewed" and s2["M5_reason_grounded"]["pct"] == 100.0
    assert s2["gate"]["final"] is True and s2["gate"]["checks"]["M2 하드 = 0"] and s2["gate"]["checks"]["설정 오류 = 0"]
    # A안(10-19) — M3 은 참고값이라 전환 기준에 없다. 안전 지표만 넘으면 전환 가능
    assert "M3 하한 > 0" not in s2["gate"]["checks"] and s2["gate"]["verdict"] == "전환 가능"
    # M1 참고값 — 셋 다 허용(quiet)은 골라야 하는 사례에서 빠진다
    assert s["M1_discriminating"]["num"] == 3 and s["M1_discriminating"]["den"] == 3
    assert s["M1_excluded_cases"] == {"all_acceptable": 1, "no_fit": 0, "discriminating": 1}


def test_relaxed_gate_allows_mild_reasons_shuffle_discards_and_rare_timeouts():
    """`[2026-10-20 완화안]` 심각한 지어냄 0 · 경미 ≤ 5% · 원래 판 사용률 · 시간 초과 ≤ 1% · 설정 오류 0."""
    c = case("B-01")

    async def slow(_body):
        await asyncio.sleep(5)

    base = [observe(c, answer(["b2", "a1", "c3"]), repeat=r) for r in range(1, 101)]
    shuffled = observe(c, answer(["b2", "a1", "c3"], used=False, reason=""), variant="shuffle-1", order=["c3", "b2", "a1"])
    timed_out = observe(c, slow, repeat=101)
    rows = [(c, [*base, shuffled, timed_out])]
    mild = {("B-01", "base", r): (score.FAB_MILD if r <= 5 else score.GROUNDED) for r in range(1, 101)}
    s = summary_for(rows, reasons=mild)
    checks = s["gate"]["checks"]
    assert s["M6b_base"]["num"] == 100 and s["M6b_base"]["den"] == 101 and s["M6d_discarded"]["num"] == 1   # 섞은 판 폐기는 원래 판에 안 든다
    assert checks["시간 초과 ≤ 1%"] and checks["M5 경미 ≤ 5%"] and checks["M5 심각 = 0"]
    assert checks["M6b 원래 판 ≥ 98%"] and s["gate"]["verdict"] == "전환 가능"
    assert s["gate"]["checks_before"]["M5 = 100%"] is False and s["gate"]["checks_before"]["M6e = 0"] is False

    severe = {**mild, ("B-01", "base", 1): score.FAB_SEVERE}
    assert summary_for(rows, reasons=severe)["gate"]["verdict"] == "shadow 유지"
    unsorted = {**mild, ("B-01", "base", 1): score.FABRICATED}                    # 단계 없는 「지어냄」 — 판정 미룸
    assert summary_for(rows, reasons=unsorted)["gate"]["verdict"].startswith("확인 전")

    async def broken(_body):
        raise RuntimeError("no active prompt registered")

    s3 = summary_for([(c, [*base, observe(c, broken, repeat=102)])], reasons=mild)
    assert s3["gate"]["verdict"].startswith("환경 먼저")


def test_no_fit_case_is_out_of_m1_but_still_counts_for_m2():
    no_fit = case("N-01", text="궁궐로 바꿔 주세요", acceptable=(), forbidden=("c3",))
    picked = case("P-01", acceptable=("b2",), forbidden=())
    rows = [(no_fit, [observe(no_fit, answer(["c3", "a1", "b2"]))]),
            (picked, [observe(picked, answer(["a1", "b2", "c3"]))])]
    s = summary_for(rows)
    assert s["M1_excluded_cases"] == {"all_acceptable": 0, "no_fit": 1, "discriminating": 1}
    assert s["M1_discriminating"]["den"] == 1 and s["M1_discriminating"]["num"] == 0
    assert s["M2_dangerous"]["num"] == 1                                         # 「없음」 사례도 위험은 센다
    # 코드 1순위(a1)는 위험이 아닌데 LLM 이 c3 으로 올렸다 → 새로 만든 위험 · 코드 순서보다 나쁨
    assert s["M2_new_danger"]["num"] == 1 and s["M2_code_order"]["num"] == 0
    assert not s["gate"]["checks"]["M2 새 위험 = 0"] and not s["gate"]["checks"]["M2 ≤ 코드 순서"]
    assert s["gate"]["checks"]["M2 하드 = 0"]


def test_m2_split_hard_new_and_code_order():
    # 코드 1순위가 이미 위험(a1) — LLM 도 못 고침: 위험이지만 새로 만든 것은 아니고 코드 순서보다 나쁘지 않다
    same = case("S-01", acceptable=("b2",), forbidden=("a1",))
    fixed = case("F-01", acceptable=("b2",), forbidden=("a1",))
    outside = case("O-01", acceptable=("b2",), forbidden=())
    hard = {**case("H-01", acceptable=("b2",), forbidden=("c3",)), "forbidden_hard": ["c3"]}
    rows = [(same, [observe(same, answer(["a1", "b2", "c3"]))]),
            (fixed, [observe(fixed, answer(["b2", "a1", "c3"]))]),
            (outside, [observe(outside, answer(["lotte", "b2"]))]),
            (hard, [observe(hard, answer(["b2", "a1", "c3"]))])]
    s = summary_for(rows)
    assert s["M2_dangerous"]["num"] == 2 and s["M2_code_order"]["num"] == 2         # same(a1) + 후보 밖 / same · fixed
    assert s["M2_new_danger"]["num"] == 0
    assert s["M2_hard"]["num"] == 1                                                 # 후보 밖 원답은 하드 위험
    assert not s["gate"]["checks"]["M2 하드 = 0"] and s["gate"]["checks"]["M2 ≤ 코드 순서"]
    hard_hit = summary_for([(hard, [observe(hard, answer(["c3", "a1", "b2"]))])])
    assert hard_hit["M2_hard"]["num"] == 1                                          # 하드 조건 위반 후보를 1순위로


def test_build_carries_no_fit_from_labels():
    card = build.load_cards()[0]
    labels = {card["card_id"]: {"acceptable": [], "forbidden": [], "no_fit": True}}
    [c] = build.build([card], smoke=False, texts={card["card_id"]: "궁궐로"}, labels=labels, labeler="갑")
    assert c["acceptable"] == [] and c["no_fit"] is True


def test_call_failures_block_the_gate_and_drafts_are_reference_only():
    c = case()

    async def boom(_body):
        raise RuntimeError("no active prompt registered")

    s = summary_for([(c, [observe(c, boom)])])
    assert s["M6e_call_failed"]["num"] == 1 and s["gate"]["verdict"].startswith("환경 먼저")
    draft = {**c, "label_by": "auto-tag-draft"}
    s2 = summary_for([(draft, [observe(draft, answer(["b2", "a1", "c3"]))])], {"smoke": True, "split": ["smoke"]})
    assert s2["gate"]["verdict"].startswith("참고만")


def test_export_reasons_sheet_and_read_back(tmp_path):
    c = case(claims=("후기",))
    rows = [observe(c, answer(["b2", "a1", "c3"], reason="후기가 좋아요")),
            observe(c, answer(["b2", "a1", "c3"]), repeat=2)]
    path = score.export_reasons(tmp_path, {c["case_id"]: c}, rows)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        sheet = list(csv.DictReader(fh))
    assert [r["자동 표시"] for r in sheet] == ["후기", ""]                  # 표시된 것 먼저, 그다음 무작위 표본
    sheet[0][score.VERDICT_COL] = score.FABRICATED
    sheet[1][score.VERDICT_COL] = score.GROUNDED
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(sheet[0]))
        w.writeheader()
        w.writerows(sheet)
    got = score.load_reasons(path)
    m5 = summary_for([(c, rows)], reasons=got)["M5_reason_grounded"]
    assert (m5["num"], m5["den"], m5["fabricated"]) == (1, 2, 1)
    with pytest.raises(SystemExit):
        score.export_reasons(tmp_path, {c["case_id"]: c}, rows)              # 덮어쓰지 않는다


def test_dry_run_end_to_end(tmp_path):
    cases = build.build(build.load_cards(), smoke=True)[:6]
    results = tmp_path / "results.jsonl"
    plan = run.shuffle_plan(cases, n_cases=2, n_shuffles=2, seed=7)
    n = asyncio.run(run.run(run.jobs(cases, repeats=2, plan=plan), run.dry_run_ask(), timeout=1, concurrency=3,
                            results=results))
    assert n == 6 * 2 + 2 * 2
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
    s = score.summarize({c["case_id"]: c for c in cases}, rows, {"split": ["smoke"], "smoke": True}, n_boot=100)
    assert s["M3_llm_minus_code"]["value"] == 0.0                          # 받은 순서 그대로 = 기준선
    assert s["M8_position_stable"]["num"] == 0                              # 받은 순서를 따르면 섞을 때마다 바뀐다


# ── `[2026-10-19]` 감시 경로 판 — 고객 문장 없이 설문만 ───────────────────────────────────

def test_watch_variants_split_by_what_production_sends_and_drop_duplicates():
    from eval.alternative_pick import watch

    chat = [case("X-01", survey={}), case("X-02", survey={"priority": ["mobility"]}),       # 우선순위만 — 10-20 부터 안 부름
            case("X-03", survey={"theme": "자연", "priority": ["activity"]}),
            case("X-04", text="다른 데로", survey={"theme": "자연", "priority": ["activity"]})]  # X-03 과 입력이 같다
    cases, counts = watch.variants(chat)

    assert [c["case_id"] for c in cases] == ["X-03-W"] and cases[0]["watch_kind"] == "human"
    assert cases[0]["inputs"]["preference"]["customer_text"] is None and cases[0]["path"] == "watch"
    assert counts["skipped"] == {"not_called": ["X-01", "X-02"], "duplicate": ["X-04=X-03"]}


def test_watch_labels_need_people():
    from eval.alternative_pick import watch

    cases, _ = watch.variants([case("X-03", survey={"theme": "자연"})])
    with pytest.raises(SystemExit):
        watch.label(cases, {}, "합의")                                                    # 사람 라벨이 빠졌다
    [labeled] = watch.label(cases, {"X-03-W": {"acceptable": ["3"], "forbidden": ["1"]}}, "합의")
    assert labeled["acceptable"] == ["c3"] and labeled["forbidden"] == ["a1"] and labeled["label_by"] == "합의"


def test_watch_variants_of_the_frozen_holdout_and_their_label_sheet():
    from eval.alternative_pick import watch
    from eval.human_review import adapters

    chat, _ = build.load_cases(build.DATASET)
    cases, counts = watch.variants(chat)
    # ★10-19 판은 54(규칙 33 + 사람 21). 10-20 우선순위를 넘기지 않게 된 뒤 우선순위만 있던 33 + 중복 2 는 안 부름이 됐다
    assert (counts["variants"], counts["human"], counts["not_called"], counts["duplicate"]) == (21, 21, 59, 0)
    bundle = adapters.build("situation_cards_watch")
    assert sorted(it.id for it in bundle.items) == sorted(c["case_id"] for c in cases)
    assert "고객 문장" not in bundle.context_columns


def test_scores_are_split_by_path():
    from eval.alternative_pick import watch

    chat = case("C-01")
    [taste] = watch.label(watch.variants([case("Q-01", survey={"theme": "자연"})])[0],
                          {"Q-01-W": {"acceptable": ["2"], "forbidden": []}}, "합의")
    rule = {**case("R-01", text=None, acceptable=IDS, forbidden=(), quiet=True), "path": "watch", "watch_kind": "rule"}
    s = summary_for([(chat, [observe(chat, answer(["b2", "a1", "c3"]))]),
                     (taste, [observe(taste, answer(["b2", "a1", "c3"]))]),
                     (rule, [observe(rule, answer(IDS, used=False, reason=""))])])        # 10-19 동결본의 규칙 사례 모양
    assert set(s["by_path"]) == {"chat", "watch:human", "watch:rule"}
    assert s["by_path"]["watch:human"]["M1_discriminating"]["num"] == 1
    assert s["by_path"]["chat"]["M1_discriminating"]["num"] == 1


def test_retry_failed_drops_only_call_failures_and_records_them(tmp_path):
    rows = [observe(case("X-01"), answer(IDS, used=False, reason="")),
            {**observe(case("X-01"), answer(IDS), repeat=2), "status": "llm_timeout", "applied": None, "output": None},
            observe(case("X-02"), answer(["c3", "a1", "b2"], used=False, reason=""))]          # 폐기 — 답은 받았다
    (tmp_path / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (tmp_path / "conditions.json").write_text("{}", encoding="utf-8")

    assert run.drop_failed(tmp_path) == ["X-01/base/r2:llm_timeout"]
    assert run.done_keys(tmp_path / "results.jsonl") == {("X-01", "base", 1), ("X-02", "base", 1)}
    assert json.loads((tmp_path / "conditions.json").read_text(encoding="utf-8"))["retried"][0]["observations"] == \
        ["X-01/base/r2:llm_timeout"]
    assert len(list(tmp_path.glob("results.before_retry_*.jsonl"))) == 1
    assert run.drop_failed(tmp_path) == []


def test_runner_can_send_class_names_and_pick_a_prompt_file():
    sent = []

    async def ask(body):
        sent.append(body)
        return SimpleNamespace(output={"order": IDS, "used_preference": False, "reason": ""}, model="m",
                               latency_ms=1, input_tokens=1, output_tokens=1, reasoning_tokens=0)

    c = case()
    asyncio.run(run.observe(c, "base", 1, IDS, ask, 1.0))
    asyncio.run(run.observe(c, "base", 2, IDS, ask, 1.0, with_class_name=True))
    assert "class_name" not in sent[0]["candidates"][0]
    assert sent[1]["candidates"][0]["class_name"] == "역사관광 > 역사유적지 > 고궁"
    assert "distance_km" in run.prompt_text("alternative_order.v3.md") and run.prompt_text("없는판.md") is None


def test_dev_picks_half_of_each_stratum_and_labels_by_rule():
    from eval.alternative_pick import dev

    cards = build.load_cards()
    picked = dev.pick(cards)
    assert len(picked) == 40 and len({c["card_id"] for c in picked}) == 40
    counts = {s: sum(c["stratum"] == s for c in picked) for s in dev.TARGET}
    assert counts == dev.TARGET
    card = next(c for c in cards if c["preference_target"]["attribute"] == "history")
    shown = [{"id": "x", "class": "HS010100", "title": "궁"}, {"id": "y", "class": "VE030100", "title": "공원"}]
    assert dev.label(card, shown, lambda c: {"history"} if c["class"].startswith("HS") else set()) == (["x"], False)
