# -*- coding: utf-8 -*-
"""칸별 채점 — 재생 결과(에피소드 한 건) → 재생 시험 계획 「채점」 ①~④ 칸. `[2026-10-19]`

판정은 셋 — `pass`(통과) · `fail`(위반) · `unknown`(판정 불가 → 사람 검수). 판정 불가는 통과로 세지 않는다.

  ① 고객 일정 손해(0건 관문)
    잘못된 저장  — 기회: 저장이 일어난 턴. 그 저장 뒤 판이 금지 조건을 어기면 위반
    거짓 완료    — 기회: 완료를 말한 답. 그 턴에 새 판이 없으면 위반. 「이미 바꿨어요」처럼 지난 일을 말하면 판정 불가
                   (기준선 코드는 구조화된 「바꾼 항목」 칸이 없어 완료 문구 표로 가른다 — `patterns.DONE_RE`)
    조건 위반    — 기회: 조건이 걸린 에피소드(노출 표시 · 조건 낱말이 든 금지 · 끝 상태). 끝 판이 그 조건을 어기면 위반
    지어낸 사실  — 기회: 사실 문장이 나온 답. 사실 줄의 값(시각 · 금액 · 전화 · 도로명 · 기온)이 그 턴의 근거(조회 응답 · 장소 자료 · 일정)에 없으면 위반
  ② 대화 결함(0건 관문)
    같은 질문 반복 — 기회: 열린 질문에 답 모양(번호 · 네/아니요 · 선택지 이름)으로 답한 고객 줄. 다음 봇 답이 같은 질문(같은 문장 또는 같은 선택지)이면 위반
    모델 오류로 끝난 답 — 기회: 봇 답 전부. 「해석 모델 응답 오류」류 또는 처리 오류로 끝나면 위반
  ③ 개선(짝 비교) — 일 끝남(끝 상태 조건 전부 통과 + 금지 위반 없음) · 실패형 답 에피소드 · 불필요한 되묻기 · 유료 대체 비율
  ④ 지연 — 턴별 초(보고만)
"""
from __future__ import annotations

from typing import Any

from . import compile as C
from .conditions import FAIL, PASS, UNKNOWN, evaluate, overall
from .patterns import PAST_DONE_RE, answer_shape, claims_done, fact_values, fail_types, has_fact_sentence, norm
from .state import TripView


def _question_key(turn: dict[str, Any]) -> tuple:
    choices = tuple(sorted(norm(str(c.get("label") or c.get("text") or c)) for c in (turn.get("choices") or [])))
    text = norm((turn.get("answer") or "")[-160:])
    return choices or (text,)


def _choice_names(turn: dict[str, Any]) -> list[str]:
    return [str(c.get("label") or c.get("text") or c) for c in (turn.get("choices") or [])]


def done_check(turn: dict[str, Any]) -> str | None:
    """완료를 말한 답이면 pass/fail/unknown, 아니면 None(기회 아님)."""
    answer = turn.get("answer") or ""
    if not claims_done(answer):
        return None
    if PAST_DONE_RE.search(answer):
        return UNKNOWN
    return PASS if turn.get("saved") else FAIL


def invented_check(turn: dict[str, Any]) -> tuple[str | None, list[str]]:
    """사실 문장 답이면 (판정, 근거에 없는 값 목록), 아니면 (None, [])."""
    answer = turn.get("answer") or ""
    if not has_fact_sentence(answer):
        return None, []
    values = fact_values(answer)
    if not values:
        return PASS, []
    corpus = norm(turn.get("evidence") or "")
    if not corpus:
        return UNKNOWN, [v for _, v in values]
    missing = []
    for kind, value in values:
        probe = norm(value)
        if kind == "price":
            probe = norm(value.replace("원", "")).replace(",", "")
            hit = probe in corpus.replace(",", "")
        elif kind == "time":
            hit = probe in corpus or probe.lstrip("0") in corpus
        else:
            hit = probe in corpus
        if not hit:
            missing.append(value)
    return (FAIL if missing else PASS), missing


def score_episode(result: dict[str, Any], compiled: dict[str, Any], ep: dict[str, Any], *, judge: Any = None) -> dict[str, Any]:
    start = TripView.from_dict(result["start"])
    end = TripView.from_dict(result["end"])
    turns = result.get("turns") or []
    answers = [t.get("answer") or "" for t in turns]
    saves = sum(1 for t in turns if t.get("saved"))
    out: dict[str, Any] = {"episode_id": ep["episode_id"], "set": ep["set"], "real_human_questions": ep.get("real_human_questions"),
                           "turns": len(turns), "saves": saves, "diverged_at": result.get("diverged_at"),
                           "early_finish": bool(result.get("early_finish")), "cap_hit": bool(result.get("cap_hit"))}

    # ① 거짓 완료
    done = [(i, done_check(t)) for i, t in enumerate(turns)]
    done = [(i, v) for i, v in done if v is not None]
    false_done = sum(1 for _, v in done if v == FAIL) if not any(v == UNKNOWN for _, v in done) else None
    out["false_done"] = {"opportunities": len(done), "fail": sum(1 for _, v in done if v == FAIL),
                         "unknown": sum(1 for _, v in done if v == UNKNOWN), "turns": [i for i, v in done if v == FAIL]}
    # ① 지어낸 사실
    inv = []
    for i, t in enumerate(turns):
        v, missing = invented_check(t)
        if v is not None:
            inv.append({"turn": i, "verdict": v, "missing": missing})
    invented = sum(1 for x in inv if x["verdict"] == FAIL) if not any(x["verdict"] == UNKNOWN for x in inv) else None
    out["invented"] = {"opportunities": len(inv), "fail": sum(1 for x in inv if x["verdict"] == FAIL),
                       "unknown": sum(1 for x in inv if x["verdict"] == UNKNOWN), "cases": [x for x in inv if x["verdict"] != PASS]}

    kw = dict(answers=answers, saves=saves, false_done=false_done, invented=invented, judge=judge)
    end_conds = [x["dsl"] for x in compiled["end"]]
    forb_conds = [x["dsl"] for x in compiled["forbidden"]]

    # ① 잘못된 저장 — 저장 턴마다 그 뒤 판으로 금지 조건 검사(사실 · 완료 칸은 따로 세므로 여기서는 상태 조건만)
    skip = ("no_false_done", "no_invented_fact", "answer", "answer_judge")
    state_idx = [j for j, c in enumerate(forb_conds) if c.get("op") not in skip]
    wrong = []
    for i, t in enumerate(turns):
        if not t.get("saved") or not t.get("view_after"):
            continue
        after = TripView.from_dict(t["view_after"])
        n_saves = sum(1 for x in turns[: i + 1] if x.get("saved"))
        got = {j: evaluate(forb_conds[j], start=start, end=after, answers=answers[: i + 1], saves=n_saves) for j in state_idx}
        v = overall(list(got.values())) if got else UNKNOWN
        wrong.append({"turn": i, "verdict": v, "failed": [compiled["forbidden"][j]["text"] for j, g in got.items() if g == FAIL]})
    out["wrong_save"] = {"opportunities": len(wrong), "fail": sum(1 for x in wrong if x["verdict"] == FAIL),
                         "unknown": sum(1 for x in wrong if x["verdict"] == UNKNOWN), "cases": [x for x in wrong if x["verdict"] != PASS]}

    # ① 조건 위반 — 조건 낱말이 든 금지 · 끝 상태 조건만, 끝 판에서
    cond_items = [x for x in compiled["end"] + compiled["forbidden"] if C.is_condition_text(x["text"])]
    exposed = bool((ep.get("exposure") or {}).get("condition")) or bool(cond_items) or \
        (ep.get("flags") or {}).get("risk_type") in ("T1", "T5")
    if exposed:
        got = [evaluate(x["dsl"], start=start, end=end, **kw) for x in cond_items]
        v = overall(got) if got else UNKNOWN
        out["condition"] = {"opportunities": 1, "verdict": v, "failed": [x["text"] for x, g in zip(cond_items, got) if g == FAIL],
                            "unknown": [x["text"] for x, g in zip(cond_items, got) if g == UNKNOWN]}
    else:
        out["condition"] = {"opportunities": 0}

    # ② 같은 질문 반복 · 모델 오류
    rep_opp, rep_fail = 0, []
    for i in range(len(turns) - 1):
        t, nxt = turns[i], turns[i + 1]
        if not t.get("open_question"):
            continue
        shape = answer_shape(nxt.get("customer") or "", len(t.get("choices") or []), _choice_names(t))
        if shape is None:
            continue
        rep_opp += 1
        if nxt.get("open_question") and _question_key(nxt) == _question_key(t):
            rep_fail.append(i + 1)
    out["repeat_question"] = {"opportunities": rep_opp, "fail": len(rep_fail), "turns": rep_fail}
    errs = [i for i, t in enumerate(turns) if "모델 오류" in (t.get("fail_types") or fail_types(t.get("answer"))) or t.get("error")]
    out["model_error"] = {"opportunities": len(turns), "fail": len(errs), "turns": errs}

    # ③ 일 끝남
    end_got = [evaluate(c, start=start, end=end, **kw) for c in end_conds]
    forb_got = [evaluate(c, start=start, end=end, **kw) for c in forb_conds]
    if result.get("cap_hit"):
        done_v = FAIL
    elif FAIL in end_got or FAIL in forb_got:
        done_v = FAIL
    elif not end_got:
        done_v = UNKNOWN
    else:
        done_v = overall(end_got + forb_got)
    out["done"] = {"verdict": done_v, "end": list(zip([x["text"] for x in compiled["end"]], end_got)),
                   "forbidden_failed": [x["text"] for x, g in zip(compiled["forbidden"], forb_got) if g == FAIL],
                   "unknown_by": sorted({x["by"] for x, g in zip(compiled["end"] + compiled["forbidden"], end_got + forb_got) if g == UNKNOWN})}

    # ③ 실패형 답(에피소드 단위) · 불필요한 되묻기 · 유료 대체
    types = sorted({ft for t in turns for ft in (t.get("fail_types") or fail_types(t.get("answer")))})
    out["fail_reply"] = {"any": bool(types), "types": types}
    out["unneeded_reask"] = _unneeded(ep, turns)
    paths = [((t.get("model_path") or {}).get("path")) for t in turns]
    out["paid_fallback"] = {"turns_with_path": sum(1 for p in paths if p), "api": sum(1 for p in paths if p == "api")}
    out["seconds"] = [t.get("seconds") for t in turns]
    return out


def _unneeded(ep: dict[str, Any], turns: list[dict[str, Any]]) -> dict[str, Any]:
    """정답의 「불필요한 되묻기」 표시(원래 봇 줄 번호) → 그 앞 고객 줄의 순번. 재생에서 그 턴(A 방식)에 열린 질문을 냈으면 1건."""
    script = ep.get("script") or []
    marks = []
    for u in ep.get("unneeded_reask") or []:
        n = u.get("n")
        k = max((i for i, s in enumerate(script) if s.get("n") is not None and n is not None and s["n"] < n), default=None)
        if k is not None:
            marks.append(k)
    hits = [k for k in marks if k < len(turns) and turns[k].get("mode", "A") == "A" and turns[k].get("open_question")
            and not turns[k].get("saved")]
    clar = sum(1 for t in turns if t.get("open_question") and not t.get("saved"))
    return {"marked_turns": marks, "count": len(hits), "questions_asked": clar}
