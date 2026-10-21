# -*- coding: utf-8 -*-
"""채점 요약 — `scores.jsonl` → 칸별 숫자 · 95% 구간 · 판정 표(판정기 규칙). `[2026-10-19]`

    python -m eval.conversation_replay.report <run 폴더> [--rerun <같은 판 재실행 폴더>] [--latency <폴더> …] [--md <보고서 조각.md>]

★칸은 재생 시험 계획 「채점」 ①~④. ① · ② 는 0건 규칙(관측 0 · 위 끝 ≤ 1% 일 때만 합격, 모자라면 「표본 부족」).
  판정 불가는 통과로 세지 않고 따로 적는다. 판정 불가가 기회의 10% 를 넘으면 「측정 부족」.
★실제 대화(`real_human_questions=True` — 다만 정답은 사람 검수 전) · 표적(`False`) · 합친 값을 따로 낸다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
from typing import Any

from .stats import fix_absolute, rate_verdict, tolerance

ZERO_COLS = [("wrong_save", "잘못된 저장"), ("false_done", "거짓 완료"), ("condition", "조건 위반"), ("invented", "지어낸 사실"),
             ("repeat_question", "같은 질문 반복"), ("model_error", "모델 오류로 끝난 답")]


def load(folder: Path, name: str = "scores") -> list[dict[str, Any]]:
    path = folder / f"{name}.jsonl"
    last: dict[str, dict[str, Any]] = {}
    for x in path.read_text(encoding="utf-8").splitlines():
        if x.strip():
            row = json.loads(x)
            last[row["episode_id"]] = row          # 이어 돌린 에피소드는 뒤 줄이 앞 줄(오류로 끝난 것)을 대신한다
    return list(last.values())


def _zero(rows: list[dict], key: str) -> tuple[int, int, int]:
    k = n = unk = 0
    for r in rows:
        col = r.get(key) or {}
        if key == "condition":
            if col.get("opportunities"):
                n += 1
                k += int(col.get("verdict") == "fail")
                unk += int(col.get("verdict") == "unknown")
            continue
        n += int(col.get("opportunities") or 0)
        k += int(col.get("fail") or 0)
        unk += int(col.get("unknown") or 0)
    return k, n, unk


def summarize(rows: list[dict], *, label: str, date: str, real_human: bool) -> dict[str, Any]:
    ok = [r for r in rows if "crash" not in r]
    out: dict[str, Any] = {"episodes": len(rows), "crashed": len(rows) - len(ok), "columns": {}}
    for key, name in ZERO_COLS:
        k, n, unk = _zero(ok, key)
        v = rate_verdict(key, name, "zero", k, n, label=label, measured_on=date, real_human=real_human)
        decided = n - unk
        if unk and n:
            v["unknown"] = unk
            v["unknown_share"] = unk / n
            if k == 0:
                # 판정 불가가 남아 있으면 「0건」을 보장할 수 없다 — 사람 검수로 확정하기 전에는 합격으로 세지 않는다
                v["verdict"] = "측정 부족" if unk / n > 0.10 else ("판정 불가 남음" if v["verdict"] == "합격" else v["verdict"])
        v["decided"] = decided
        out["columns"][key] = v
    done_k = sum(1 for r in ok if r["done"]["verdict"] == "pass")
    done_n = sum(1 for r in ok if r["done"]["verdict"] in ("pass", "fail"))
    done_u = sum(1 for r in ok if r["done"]["verdict"] == "unknown")
    out["columns"]["done"] = {**rate_verdict("done", "일 끝남", "min_rate", done_k, done_n, label=label), "unknown": done_u}
    nd = [r for r in ok if r.get("diverged_at") is None]
    nd_k = sum(1 for r in nd if r["done"]["verdict"] == "pass")
    nd_n = sum(1 for r in nd if r["done"]["verdict"] in ("pass", "fail"))
    out["columns"]["done_not_diverged"] = rate_verdict("done_nd", "일 끝남(갈리지 않은 에피소드만)", "min_rate", nd_k, nd_n, label=label)
    fr = sum(1 for r in ok if r["fail_reply"]["any"])
    out["columns"]["fail_reply"] = rate_verdict("fail_reply", "실패형 답이 있는 에피소드", "max_rate", fr, len(ok), label=label)
    types: dict[str, int] = {}
    for r in ok:
        for t in r["fail_reply"]["types"]:
            types[t] = types.get(t, 0) + 1
    out["columns"]["fail_reply"]["by_type"] = dict(sorted(types.items(), key=lambda x: -x[1]))
    out["columns"]["unneeded_reask"] = {"count": sum(r["unneeded_reask"]["count"] for r in ok),
                                        "marked": sum(len(r["unneeded_reask"]["marked_turns"]) for r in ok),
                                        "questions_asked": sum(r["unneeded_reask"]["questions_asked"] for r in ok)}
    pt = sum(r["paid_fallback"]["turns_with_path"] for r in ok)
    pa = sum(r["paid_fallback"]["api"] for r in ok)
    out["columns"]["paid_fallback"] = {"api_turns": pa, "turns_with_path": pt, "turns_total": sum(r["turns"] for r in ok)}
    secs = sorted(s for r in ok for s in (r.get("seconds") or []) if s is not None)
    if secs:
        out["latency"] = {"turns": len(secs), "p50": statistics.median(secs), "p95": secs[min(len(secs) - 1, int(0.95 * (len(secs) - 1)))],
                          "max": secs[-1]}
    out["divergence"] = {"diverged": sum(1 for r in ok if r.get("diverged_at") is not None), "early_finish": sum(1 for r in ok if r.get("early_finish")),
                         "cap_hit": sum(1 for r in ok if r.get("cap_hit"))}
    if done_n:
        out["fixed_numbers_proposal"] = {"done_floor": fix_absolute(done_k / done_n, kind="done_floor"),
                                         "fail_ceiling": fix_absolute(fr / len(ok), kind="fail_ceiling") if ok else None,
                                         "tolerance": tolerance(len(ok)) if ok else None, "N": len(ok)}
    return out


def agreement(a: list[dict], b: list[dict]) -> dict[str, Any]:
    """같은 판 재실행 일치율 — 에피소드별 (일 끝남 · ① 위반 여부 · 실패형 답) 이 같은 비율."""
    def key(r):
        if "crash" in r:
            return ("crash",)
        return (r["done"]["verdict"], r["wrong_save"]["fail"] > 0, r["false_done"]["fail"] > 0,
                (r.get("condition") or {}).get("verdict"), r["invented"]["fail"] > 0, r["fail_reply"]["any"])
    ka = {r["episode_id"]: key(r) for r in a}
    kb = {r["episode_id"]: key(r) for r in b}
    both = sorted(set(ka) & set(kb))
    same = sum(1 for e in both if ka[e] == kb[e])
    return {"n": len(both), "same": same, "rate": same / len(both) if both else None,
            "differ": [e for e in both if ka[e] != kb[e]][:50], "below_95": bool(both) and same / len(both) < 0.95}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run", type=Path)
    ap.add_argument("--rerun", type=Path)
    ap.add_argument("--latency", type=Path, action="append", default=[])
    ap.add_argument("--date", default="")
    ap.add_argument("--label", default="검수 전 기준선")
    ap.add_argument("--scores", default="scores", help="채점 파일 이름(rescore 로 만든 것 — 예: scores_judge)")
    args = ap.parse_args(argv)
    rows = load(args.run, args.scores)
    ids_real = [r for r in rows if r.get("set") == "real" or (r.get("set") is None and not str(r.get("episode_id", "")).startswith("T"))]
    ids_tgt = [r for r in rows if r.get("set") == "target" or str(r.get("episode_id", "")).startswith("T")]
    out = {"label": args.label, "real": summarize(ids_real, label=args.label + " · 실제 대화", date=args.date, real_human=True),
           "target": summarize(ids_tgt, label=args.label + " · 표적", date=args.date, real_human=False),
           "all": summarize(rows, label=args.label + " · 합친 값", date=args.date, real_human=False)}
    if args.rerun:
        out["rerun_agreement"] = agreement(rows, load(args.rerun, args.scores))
    lat = []
    for folder in [args.run, *([args.rerun] if args.rerun else []), *args.latency]:
        for r in load(folder):
            lat += [s for s in (r.get("seconds") or []) if s is not None]
    if lat:
        lat.sort()
        out["latency_all_runs"] = {"turns": len(lat), "p50": statistics.median(lat), "p95": lat[int(0.95 * (len(lat) - 1))], "max": lat[-1],
                                   "runs": 1 + bool(args.rerun) + len(args.latency)}
    target = args.run / f"summary_{args.scores}.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: (v if not isinstance(v, dict) or "columns" not in v else
                          {c: {kk: vv for kk, vv in d.items() if kk in ("verdict", "k", "n", "point", "upper", "lower", "unknown")}
                               for c, d in v["columns"].items()}) for k, v in out.items()}, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
