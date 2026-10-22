# -*- coding: utf-8 -*-
"""대체 후보 1순위 판정 채점 — 실행 기록(results.jsonl)과 사례로 계획서 M1~M9 · 전환 기준을 낸다. 외부 호출 없음.

    python -m eval.alternative_pick.score eval/reports/alternative_pick/<run>                      # summary.json
    python -m eval.alternative_pick.score eval/reports/alternative_pick/<run> --export-reasons     # 이유 검사 시트
    python -m eval.alternative_pick.score eval/reports/alternative_pick/<run> --reasons 채운시트.csv  # M5 확정

★두 기준으로 잰다(계획서 1-2):
  - **보정 후(served)** — 고객 화면에 나가는 1순위. 실패 · 폐기면 코드 순서 1순위다. M1 · M3 · M4 · M7 의 기준.
  - **모델 원답(raw)** — 모델이 `order[0]` 에 적은 것. 후보 밖 장소면 위험 오답(범위 이탈 F 를 두 번 잰다).
  M2(위험 오답) = 보정 후 1순위가 금지 목록에 있음 **또는** 원답 1순위가 후보 밖. 서비스 기준(보정 후만)도 따로 적는다.
★기준선(M3) = 코드 순서 1순위. 결정적이라 사례마다 한 번 센다. M3 은 사례 단위로 짝지은 차이의 군집 부트스트랩이다.
★M5 는 사람 확인 전에는 확정하지 않는다 — 금지어 자동 표시 + 표시 안 된 것 무작위 20건을 시트로 내고(`--export-reasons`),
  채운 시트를 넣어야(`--reasons`) 값이 나온다. 그 전에는 전환 기준에서 「확인 전」이다.
★전환 기준(계획서 §5)은 holdout · 사람 라벨일 때만 판정한다. smoke · 초안 라벨이면 「참고」로만 적는다.
★`[2026-10-19 사용자 결정 A안]` **안전 지표로 판정한다** — 화면이 후보 3곳을 다 보여 주고 고객이 고르므로 LLM 순서는 결과를 거의 바꾸지
  않는다. 전환 기준은 M2 · M5 · M6b · M6e 뿐이고 M1 · M3 · M7 · M8 은 참고값이다(M3 은 전환 기준에서 뺐다).
  M1 참고값도 **골라야 하는 사례**(허용 답이 후보 일부)로 따로 낸다 — 셋 다 허용 · 「없음」 사례는 무엇을 골라도 맞거나 틀려 1순위
  능력을 재지 못한다(라벨 절반이 셋 다 허용이었다).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from eval.activity_judge.metrics import _pct, call_cost, cluster_bootstrap

from .build import load_cases

CALL_FAILED = ("llm_timeout", "llm_error")
#: 입력에 없는 사실의 자동 표시(계획서 §4-3) — 사람 확인 대상을 고르는 데만 쓴다. 맞으면 지어냄이라는 뜻이 아니다.
BANNED = ("요금", "입장료", "무료", "유료", "가격", "저렴", "비싸", "혼잡", "붐비", "붐빔", "한적", "조용", "사람이 적",
          "후기", "리뷰", "평점", "별점", "인기", "유명", "SNS", "맛집", "웨이팅", "대기")
WON = re.compile(r"\d[\d,]*\s*원")
REVIEW_SAMPLE = 20
VERDICT_COL = "판정(근거 있음 / 지어냄)"
GROUNDED, FABRICATED = "근거 있음", "지어냄"
#: ★`[2026-10-20 사용자 결정 — 완화안]` 지어냄을 둘로 나눈다(`docs/activity/대체 후보 판정 — 허용 기준과 성능 향상 테스트 계획.md` 1-3).
#:  심각 = 입력과 반대되는 말(거리 · 분류 · 고객 문장을 거꾸로) 또는 금지 사실(요금 · 혼잡 · 후기 · 평점 · 인기).
#:  경미 = 입력에 없는 장소 특성 추측 · 취향 부합 해석. 단계 없이 「지어냄」 만 적힌 판정은 「단계 미정」으로 판정을 미룬다.
FAB_SEVERE, FAB_MILD = "지어냄(심각)", "지어냄(경미)"
VERDICTS = (GROUNDED, FAB_SEVERE, FAB_MILD, FABRICATED)
TARGETS = {"M1": 0.85, "M6b": 0.98, "M7": 0.90, "M8": 0.90, "M5_mild": 0.05, "timeout": 0.01}


def discriminating(case: dict) -> bool:
    """골라야 하는 사례 — 허용 답이 후보의 **일부**다(1순위 능력을 잴 수 있다)."""
    return 0 < len(case["acceptable"]) < len(case["inputs"]["candidates"])


def ratio(num: int, den: int) -> dict[str, Any]:
    return {"num": num, "den": den, "pct": round(100 * num / den, 1) if den else None}


def first_raw(output: Any) -> str | None:
    if isinstance(output, dict) and isinstance(output.get("order"), list) and output["order"]:
        return str(output["order"][0])
    return None


def usage(row: dict) -> str:
    """M6 갈래 — `valid`(규칙 그대로) · `corrected`(코드가 고쳐 씀) · `discarded`(코드가 버림) · `failed`(호출 실패)
    · `not_called`(단서 없어 운영도 안 부름, 호출 수에서 뺀다)."""
    if row["status"] == "not_called":
        return "not_called"
    if row["status"] in CALL_FAILED:
        return "failed"
    if row["applied"] is None:
        return "discarded"
    pool = row["pool"]
    raw = [str(x) for x in row["output"]["order"]]
    kept = list(dict.fromkeys(x for x in raw if x in pool))
    return "corrected" if row["applied"]["dropped"] or len(kept) < len(pool) else "valid"


def flags(reason: str, case: dict) -> list[str]:
    words = [w for w in (*BANNED, *case.get("forbidden_claims", [])) if w and w in reason]
    if WON.search(reason):
        words.append("…원")
    return sorted(set(words))


def judge(case: dict, row: dict) -> dict:
    """관측 하나의 판정."""
    pool = row["pool"]
    served = row["applied"]["ids"] if row["applied"] else pool
    raw = first_raw(row["output"])
    acceptable, forbidden = set(case["acceptable"]), set(case["forbidden"])
    raw_outside = raw is not None and raw not in pool

    def outcome(first: str | None) -> str:
        if first is None:
            return "no_answer"
        if first in acceptable:
            return "correct"
        if first in forbidden or first not in pool:
            return "dangerous"
        return "suboptimal"

    reason = (row["applied"] or {}).get("reason") or ""
    code_first = case["inputs"]["candidates"][0]["id"]
    return {
        "served_first": served[0], "served_outcome": outcome(served[0]), "raw_first": raw,
        "raw_outcome": outcome(raw), "raw_outside": raw_outside,
        "dangerous": served[0] in forbidden or raw_outside, "served_dangerous": served[0] in forbidden,
        # ★`[2026-10-19 사용자 결정 M2-1]` 하드 위험 — 후보 밖(원답) · 하드 조건 위반(`forbidden_hard`, 그 시각에 못 가는 곳)
        "hard_dangerous": raw_outside or served[0] in set(case.get("forbidden_hard") or []),
        # ★`[M2-2]` LLM 이 새로 만든 위험 — 코드 순서였으면 위험이 아니었는데 LLM 순서 때문에 위험이 됨
        "new_danger": served[0] in forbidden and code_first not in forbidden,
        "kept_order": served == pool, "usage": usage(row), "llm_first": served[0] if row["applied"] else None,
        "reason": reason, "flags": flags(reason, case) if reason else [],
    }


def load_results(run_dir: Path) -> tuple[list[dict], dict]:
    conditions = json.loads((run_dir / "conditions.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    return rows, conditions


def load_reasons(path: Path) -> dict[tuple[str, str, int], str]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        out = {}
        for r in csv.DictReader(fh):
            verdict = (r.get(VERDICT_COL) or "").strip()
            if verdict and verdict not in VERDICTS:
                raise SystemExit(f"{r['사례']} {r['변형']} r{r['회차']}: 판정은 {' / '.join(f'「{v}」' for v in VERDICTS[:3])}")
            if verdict:
                out[(r["사례"], r["변형"], int(r["회차"]))] = verdict
    return out


def reason_rows(cases: dict[str, dict], rows: list[dict], seed: int = 7) -> list[dict]:
    """M5 사람 확인 대상 — 자동 표시된 이유 전부 + 표시 안 된 이유 무작위 20건."""
    written = []
    for row in rows:
        j = judge(cases[row["case_id"]], row)
        if j["reason"]:
            written.append((row, j))
    flagged = [x for x in written if x[1]["flags"]]
    plain = [x for x in written if not x[1]["flags"]]
    sample = random.Random(seed).sample(plain, min(REVIEW_SAMPLE, len(plain)))
    out = []
    for row, j in [*flagged, *sorted(sample, key=lambda x: (x[0]["case_id"], x[0]["variant"], x[0]["repeat"]))]:
        case = cases[row["case_id"]]
        cands = {c["id"]: c for c in case["inputs"]["candidates"]}
        out.append({
            "사례": row["case_id"], "변형": row["variant"], "회차": row["repeat"],
            "고객 문장": case["inputs"]["preference"]["customer_text"] or "",
            "설문": json.dumps(case["inputs"]["preference"]["survey"], ensure_ascii=False),
            "후보(보낸 순서)": " / ".join(f"{cands[i]['title']}({cands[i]['class']} · {cands[i]['code_reason']})"
                                     for i in row["pool"]),
            "1순위": cands.get(j["served_first"], {}).get("title", j["served_first"]),
            "이유": j["reason"], "자동 표시": ", ".join(j["flags"]), VERDICT_COL: "", "메모": "",
        })
    return out


def export_reasons(run_dir: Path, cases: dict[str, dict], rows: list[dict]) -> Path:
    out = run_dir / "reasons_review.csv"
    if out.exists():
        raise SystemExit(f"{out} 이(가) 이미 있다 — 덮어쓰지 않는다")
    data = reason_rows(cases, rows)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(data[0]) if data else ["사례", "변형", "회차", VERDICT_COL])
        w.writeheader()
        w.writerows(data)
    return out


def summarize(cases: dict[str, dict], rows: list[dict], conditions: dict,
              reasons: dict[tuple[str, str, int], str] | None = None, *, n_boot: int = 10000, seed: int = 7) -> dict:
    judged = [(row, cases[row["case_id"]], judge(cases[row["case_id"]], row)) for row in rows]
    base = [x for x in judged if x[0]["variant"] == "base"]
    out: dict[str, Any] = {"conditions": conditions, "observations": len(rows), "base_observations": len(base),
                           "cases": len({r["case_id"] for r, _, _ in base})}

    # M1 · M2 · M3 · 묶음별
    out["M1_served"] = _accuracy(base, "served_outcome", n_boot, seed)
    out["M1_raw"] = _accuracy(base, "raw_outcome", n_boot, seed)
    picking = [x for x in base if discriminating(x[1])]
    out["M1_discriminating"] = _accuracy(picking, "served_outcome", n_boot, seed)
    case_of = {r["case_id"]: c for r, c, _ in base}
    out["M1_excluded_cases"] = {
        "all_acceptable": sum(len(c["acceptable"]) == len(c["inputs"]["candidates"]) for c in case_of.values()),
        "no_fit": sum(not c["acceptable"] for c in case_of.values()),
        "discriminating": sum(discriminating(c) for c in case_of.values())}
    out["M2_dangerous"] = ratio(sum(j["dangerous"] for _, _, j in base), len(base))
    out["M2_raw_outside"] = ratio(sum(j["raw_outside"] for _, _, j in base), len(base))
    out["M2_served_only"] = ratio(sum(j["served_dangerous"] for _, _, j in base), len(base))
    out["M2_hard"] = ratio(sum(j["hard_dangerous"] for _, _, j in base), len(base))
    out["M2_new_danger"] = ratio(sum(j["new_danger"] for _, _, j in base), len(base))
    # 코드 순서 위험률 — 같은 관측 수로 맞춰 견준다(사례마다 코드 1순위는 하나라 회차만큼 같은 값)
    out["M2_code_order"] = ratio(sum(c["inputs"]["candidates"][0]["id"] in c["forbidden"] for _, c, _ in base), len(base))
    baseline, delta = _baseline(base, n_boot, seed)
    out["baseline_code_order"] = baseline
    out["M3_llm_minus_code"] = delta
    out["by_stratum"] = _by_stratum(base)
    out["by_path"] = _by_path(base)

    # M4 단서 없음 → 코드 순서 유지
    quiet = [x for x in base if x[1]["expects_code_order"]]
    out["M4_keep_code_order"] = ratio(sum(j["kept_order"] for _, _, j in quiet), len(quiet))

    # M5 이유 근거율
    out["M5_reason_grounded"] = _grounding(judged, reasons)

    # M6 — 호출 수 기준(단서 없어 안 부른 것은 뺀다), 모든 변형
    called = [x for x in judged if x[2]["usage"] != "not_called"]
    n_called = len(called)
    count = defaultdict(int)
    for _, _, j in called:
        count[j["usage"]] += 1
    out["M6a_valid"] = ratio(count["valid"], n_called)
    out["M6b_used"] = ratio(count["valid"] + count["corrected"], n_called)
    out["M6c_corrected"] = ratio(count["corrected"], n_called)
    out["M6d_discarded"] = ratio(count["discarded"], n_called)
    out["M6e_call_failed"] = ratio(count["failed"], n_called)
    # ★`[2026-10-20 완화안]` 사용률은 원래 판(운영 입력 모양)으로, 호출 실패는 설정 오류 · 시간 초과로 나눠 판정한다
    base_called = [x for x in called if x[0]["variant"] == "base"]
    out["M6b_base"] = ratio(sum(x[2]["usage"] in ("valid", "corrected") for x in base_called), len(base_called))
    out["M6e_config_error"] = ratio(sum(r["status"] == "llm_error" for r, _, _ in called), n_called)
    out["M6e_timeout"] = ratio(sum(r["status"] == "llm_timeout" for r, _, _ in called), n_called)
    out["not_called"] = ratio(len(judged) - n_called, len(judged))
    errors = defaultdict(int)
    for r, _, _ in called:
        if r["status"] in CALL_FAILED:
            errors[f"{r['status']}: {(r.get('error') or '').split(':')[0]}"] += 1
    out["call_failures"] = dict(errors)

    # M7 반복 일관성 — 보정 후 1순위가 모든 회차에서 같은 사례
    firsts: dict[str, list[str]] = defaultdict(list)
    for r, _, j in base:
        firsts[r["case_id"]].append(j["served_first"])
    multi = {k: v for k, v in firsts.items() if len(v) > 1}
    out["M7_consistent"] = ratio(sum(len(set(v)) == 1 for v in multi.values()), len(multi))

    # M8 위치 편향 — 섞은 판의 LLM 1순위가 원래 판(1회차) LLM 1순위와 같은가
    out["M8_position_stable"] = _position(judged)

    # M9 지연 · 비용
    lat = [r["latency_ms"] for r, _, _ in called if r.get("latency_ms") is not None and r["status"] == "ok"]
    out["M9"] = {"latency_ms": {"p50": _pct(lat, 0.5), "p95": _pct(lat, 0.95), "n": len(lat)},
                 "cost_usd_total": round(sum(call_cost(r) for r, _, _ in called), 6),
                 "cost_usd_per_call_mean": round(sum(call_cost(r) for r, _, _ in called) / n_called, 6) if n_called else None,
                 "pricing": "eval.activity_judge.metrics 의 gpt-5.4-nano 요율 — 다른 모델이면 추정이 틀린다"}
    out["gate"] = _gate(out, conditions, cases)
    return out


def _accuracy(base: list[tuple], key: str, n_boot: int, seed: int) -> dict[str, Any]:
    per_case: dict[str, list[float]] = defaultdict(list)
    counts = defaultdict(int)
    for r, _, j in base:
        counts[j[key]] += 1
        per_case[r["case_id"]].append(1.0 if j[key] == "correct" else 0.0)
    if not per_case:
        return {"num": 0, "den": 0, "pct": None}
    mean, lo, hi = cluster_bootstrap(per_case, n=n_boot, seed=seed)
    return {**ratio(counts["correct"], len(base)), "ci95": [round(lo, 4), round(hi, 4)], "mean_of_cases": round(mean, 4),
            "outcomes": dict(counts)}


def _baseline(base: list[tuple], n_boot: int, seed: int) -> tuple[dict, dict]:
    code_ok: dict[str, float] = {}
    delta: dict[str, list[float]] = defaultdict(list)
    for r, case, j in base:
        code_first = case["inputs"]["candidates"][0]["id"]
        code_ok[r["case_id"]] = 1.0 if code_first in case["acceptable"] else 0.0
        delta[r["case_id"]].append((1.0 if j["served_outcome"] == "correct" else 0.0) - code_ok[r["case_id"]])
    if not code_ok:
        return {"num": 0, "den": 0, "pct": None}, {"value": None}
    bm, blo, bhi = cluster_bootstrap({k: [v] for k, v in code_ok.items()}, n=n_boot, seed=seed)
    dm, dlo, dhi = cluster_bootstrap(delta, n=n_boot, seed=seed)
    code_danger = sum(case["inputs"]["candidates"][0]["id"] in case["forbidden"]
                      for case in {r["case_id"]: c for r, c, _ in base}.values())
    return ({**ratio(int(sum(code_ok.values())), len(code_ok)), "ci95": [round(blo, 4), round(bhi, 4)],
             "dangerous": ratio(code_danger, len(code_ok))},
            {"value": round(dm, 4), "ci95": [round(dlo, 4), round(dhi, 4)], "paired_cases": len(code_ok)})


def _by_stratum(base: list[tuple]) -> dict[str, Any]:
    groups: dict[str, list[tuple]] = defaultdict(list)
    for x in base:
        groups[x[1]["stratum"]].append(x)
    out = {}
    for s, items in sorted(groups.items()):
        cases = {r["case_id"]: c for r, c, _ in items}
        out[s] = {"cases": len(cases),
                  "M1_served": ratio(sum(j["served_outcome"] == "correct" for _, _, j in items), len(items)),
                  "M2_dangerous": ratio(sum(j["dangerous"] for _, _, j in items), len(items)),
                  "suboptimal": ratio(sum(j["served_outcome"] == "suboptimal" for _, _, j in items), len(items)),
                  "baseline": ratio(sum(c["inputs"]["candidates"][0]["id"] in c["acceptable"] for c in cases.values()),
                                    len(cases))}
    return out


def path_of(case: dict) -> str:
    """`[2026-10-19]` 사례 경로 — 고객 요청(`chat`, 동결 holdout 은 칸이 없다) · 감시(`watch:rule` · `watch:human`)."""
    path = case.get("path") or "chat"
    return f"{path}:{case['watch_kind']}" if path == "watch" else path


def _by_path(base: list[tuple]) -> dict[str, Any]:
    groups: dict[str, list[tuple]] = defaultdict(list)
    for x in base:
        groups[path_of(x[1])].append(x)
    out = {}
    for path, items in sorted(groups.items()):
        quiet = [x for x in items if x[1]["expects_code_order"]]
        picking = [x for x in items if discriminating(x[1])]
        out[path] = {"cases": len({r["case_id"] for r, _, _ in items}),
                     "M1_discriminating": ratio(sum(j["served_outcome"] == "correct" for _, _, j in picking), len(picking)),
                     "M2_dangerous": ratio(sum(j["dangerous"] for _, _, j in items), len(items)),
                     "M4_keep_code_order": ratio(sum(j["kept_order"] for _, _, j in quiet), len(quiet)),
                     "not_called": ratio(sum(j["usage"] == "not_called" for _, _, j in items), len(items))}
    return out


def _grounding(judged: list[tuple], reasons: dict | None) -> dict[str, Any]:
    written = [(r, j) for r, _, j in judged if j["reason"]]
    flagged = [(r, j) for r, j in written if j["flags"]]
    out: dict[str, Any] = {"reasons_written": len(written), "auto_flagged": ratio(len(flagged), len(written))}
    if not written:
        out.update(status="no_reasons", note="고객에게 나간 이유가 없다 — 지어낼 문장이 없었다")
        return out
    if reasons is None:
        out.update(status="pending", note="사람 확인 전 — --export-reasons 로 시트를 내고 채운 뒤 --reasons 로 넣는다")
        return out
    key = lambda r: (r["case_id"], r["variant"], r["repeat"])  # noqa: E731
    unreviewed_flagged = [r for r, _ in flagged if key(r) not in reasons]
    verdicts = [reasons.get(key(r)) for r, _ in written]
    fabricated = sum(str(v).startswith(FABRICATED) for v in verdicts)
    reviewed = sum(key(r) in reasons for r, _ in written)
    out.update(reviewed=reviewed, fabricated=fabricated, **ratio(len(written) - fabricated, len(written)),
               severe=ratio(verdicts.count(FAB_SEVERE), len(written)), mild=ratio(verdicts.count(FAB_MILD), len(written)),
               unclassified=verdicts.count(FABRICATED),
               unreviewed_flagged=len(unreviewed_flagged),
               status="pending" if unreviewed_flagged else "reviewed",
               note=f"표시 안 되고 표본에도 안 든 {len(written) - reviewed}건은 사람이 보지 않았다(근거 있음으로 셈)")
    return out


def _position(judged: list[tuple]) -> dict[str, Any]:
    ref = {r["case_id"]: j["llm_first"] for r, _, j in judged if r["variant"] == "base" and r["repeat"] == 1}
    shuffled = [(r, j) for r, _, j in judged if r["variant"].startswith("shuffle")]
    comparable = [(r, j) for r, j in shuffled if ref.get(r["case_id"]) is not None]
    same = sum(j["llm_first"] == ref[r["case_id"]] for r, j in comparable)
    by_case: dict[str, list[bool]] = defaultdict(list)
    for r, j in comparable:
        by_case[r["case_id"]].append(j["llm_first"] == ref[r["case_id"]])
    return {**ratio(sum(all(v) for v in by_case.values()), len(by_case)), "unit": "사례(섞은 판 모두 같음)",
            "observations": ratio(same, len(comparable)),
            "excluded": len(shuffled) - len(comparable),
            "note": "LLM 1순위 = 코드가 쓴 답의 1순위. 원래 판이나 섞은 판이 폐기 · 실패면 비교에서 뺀다(excluded)"}


def _gate(out: dict, conditions: dict, cases: dict[str, dict]) -> dict[str, Any]:
    final = (conditions.get("split") == ["holdout"] and not conditions.get("smoke")
             and not conditions.get("dry_run")
             and all(c["label_by"] not in ("auto-tag-draft", "card-draft") for c in cases.values()))
    m5 = out["M5_reason_grounded"]
    # ★`[2026-10-19 사용자 결정 M2-1 + M2-2]` 「M2 = 0」 을 셋으로 나눴다 — 10-19 에 위험을 「명시 조건 위반까지」 넓혀 원래 0건 기준이
    #   겨냥한 안전 문제(못 가는 곳 · 후보 밖)와 선호 위반이 섞였기 때문이다. 하드 위험은 0건 그대로, 선호 위반은
    #   「켜도 지금(코드 순서)보다 나빠지지 않음」 으로 본다. 원래 기준 값(`M2_dangerous`)도 계속 낸다.
    # ★`[2026-10-20 사용자 결정 — 완화안]` 결과(holdout v2 · 감시 v2)를 본 뒤 바꾼 기준이다(계획서 5절). 하한(하드 위험 · 새 위험 ·
    #   설정 오류 · 심각한 지어냄 = 0)은 그대로, 사용률은 원래 판, 시간 초과 ≤ 1%, 경미한 지어냄 ≤ 5%(이유 쓴 답 수 기준).
    #   10-19 판 기준(M5 = 100% · M6b 전체 ≥ 98% · M6e = 0)도 `checks_before` 로 같이 낸다.
    if m5["status"] in ("pending",) or m5.get("unclassified"):
        severe_ok = mild_ok = None
    elif m5["status"] == "no_reasons":
        severe_ok = mild_ok = True
    else:
        severe_ok = m5["severe"]["num"] == 0
        mild_ok = m5["mild"]["num"] <= TARGETS["M5_mild"] * m5["mild"]["den"]
    timeout = out["M6e_timeout"]
    checks = {
        "M2 하드 = 0": out["M2_hard"]["num"] == 0,
        "M2 새 위험 = 0": out["M2_new_danger"]["num"] == 0,
        "M2 ≤ 코드 순서": out["M2_dangerous"]["num"] <= out["M2_code_order"]["num"],
        "설정 오류 = 0": out["M6e_config_error"]["num"] == 0,
        "시간 초과 ≤ 1%": timeout["den"] > 0 and timeout["num"] <= TARGETS["timeout"] * timeout["den"],
        "M5 심각 = 0": severe_ok,
        "M5 경미 ≤ 5%": mild_ok,
        "M6b 원래 판 ≥ 98%": out["M6b_base"]["den"] > 0
                            and out["M6b_base"]["num"] / out["M6b_base"]["den"] >= TARGETS["M6b"],
    }
    checks_before = {
        "M5 = 100%": (None if m5["status"] == "pending"
                      else m5["status"] == "no_reasons" or m5.get("num") == m5.get("den")),
        "M6b ≥ 98%": out["M6b_used"]["den"] > 0 and out["M6b_used"]["num"] / out["M6b_used"]["den"] >= TARGETS["M6b"],
        "M6e = 0": out["M6e_call_failed"]["num"] == 0,
    }
    if not checks["설정 오류 = 0"]:
        verdict = "환경 먼저 — 설정 오류(프롬프트 등록 · 키)가 있어 판정하지 않는다"
    elif None in checks.values():
        verdict = "확인 전 — M5 사람 확인(지어냄 심각 · 경미 구분 포함)이 남았다"
    else:
        verdict = "전환 가능" if all(checks.values()) else "shadow 유지"
    return {"final": final, "checks": checks, "checks_before": checks_before, "criteria": "2026-10-20 완화안",
            "verdict": verdict if final else f"참고만 — holdout · 사람 라벨 · 실호출이 아니다 ({verdict})"}


def report_lines(s: dict) -> list[str]:
    def r(x: dict) -> str:
        return f"{x['num']}/{x['den']} = {x['pct']}%" if x.get("den") else "분모 0"

    m3 = s["M3_llm_minus_code"]
    ex = s["M1_excluded_cases"]
    lines = [
        f"사례 {s['cases']} · 관측 {s['observations']}(원래 판 {s['base_observations']})",
        "── 전환 기준(안전) ──",
        f"M2 하드 위험 {r(s['M2_hard'])} · LLM 이 새로 만든 위험 {r(s['M2_new_danger'])} · "
        f"위험 오답 {r(s['M2_dangerous'])} vs 코드 순서 {r(s['M2_code_order'])}",
        f"   (원답 후보 밖 {r(s['M2_raw_outside'])} · 보정 후만 {r(s['M2_served_only'])} · 원래 기준 「M2 = 0」 "
        f"{'통과' if s['M2_dangerous']['num'] == 0 else '미달'})",
        f"M5 이유 근거율 {s['M5_reason_grounded']['status']} · 자동 표시 {r(s['M5_reason_grounded']['auto_flagged'])}"
        + (f" · {r(s['M5_reason_grounded'])} · 심각 {r(s['M5_reason_grounded']['severe'])} · "
           f"경미 {r(s['M5_reason_grounded']['mild'])} · 단계 미정 {s['M5_reason_grounded']['unclassified']}"
           if "severe" in s["M5_reason_grounded"] else ""),
        f"M6 유효 {r(s['M6a_valid'])} · 사용 {r(s['M6b_used'])}(원래 판 {r(s['M6b_base'])}) · 보정 {r(s['M6c_corrected'])} · "
        f"폐기 {r(s['M6d_discarded'])} · 호출 실패 {r(s['M6e_call_failed'])}(설정 오류 {r(s['M6e_config_error'])} · "
        f"시간 초과 {r(s['M6e_timeout'])}) · 안 부름 {r(s['not_called'])}",
        "── 참고(A안 — 순서가 결과를 거의 바꾸지 않는다) ──",
        f"M1 골라야 하는 사례 {r(s['M1_discriminating'])} · CI {s['M1_discriminating'].get('ci95')} "
        f"(사례 {ex['discriminating']} · 뺀 사례: 셋 다 허용 {ex['all_acceptable']} · 없음 {ex['no_fit']})",
        f"M1 전체(부풀려짐) {r(s['M1_served'])} · 원답 {r(s['M1_raw'])} · 기준선(코드 순서) {r(s['baseline_code_order'])}",
        f"M3 LLM − 코드 {m3.get('value')} · CI {m3.get('ci95')}",
        f"M4 단서 없을 때 순서 유지 {r(s['M4_keep_code_order'])}",
        f"M7 반복 일관 {r(s['M7_consistent'])} · M8 위치 안정 {r(s['M8_position_stable'])}",
        f"M9 지연 p50 {s['M9']['latency_ms']['p50']}ms · p95 {s['M9']['latency_ms']['p95']}ms · 비용 ${s['M9']['cost_usd_total']}",
        "묶음별: " + " · ".join(f"{k} {v['M1_served']['num']}/{v['M1_served']['den']}(기준선 {v['baseline']['num']}/{v['baseline']['den']})"
                              for k, v in s["by_stratum"].items()),
        "경로별: " + " · ".join(f"{k} 사례 {v['cases']} · M1 {r(v['M1_discriminating'])} · M2 {r(v['M2_dangerous'])} · "
                              f"M4 {r(v['M4_keep_code_order'])}" for k, v in s["by_path"].items()),
        f"전환 기준({s['gate']['criteria']}): {s['gate']['verdict']} — {s['gate']['checks']}",
        f"   10-19 판 기준: {s['gate']['checks_before']}",
    ]
    return lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--export-reasons", action="store_true", help="M5 사람 확인 시트(reasons_review.csv)를 쓴다")
    parser.add_argument("--reasons", type=Path, help="채운 이유 확인 시트")
    parser.add_argument("--cases", type=Path, help="기본은 실행 조건의 cases_file(라벨을 고친 판으로 다시 채점할 때)")
    args = parser.parse_args(argv)

    rows, conditions = load_results(args.run_dir)
    case_list, manifest = load_cases(args.cases or Path(conditions["cases_file"]))
    if manifest["inputs_sha256"] != conditions["inputs_sha256"]:
        raise SystemExit("사례 입력이 실행 때와 다르다 — 이 실행 기록으로 채점하지 않는다")
    cases = {c["case_id"]: c for c in case_list}
    if args.export_reasons:
        print(f"→ {export_reasons(args.run_dir, cases, rows)}")
        return
    reasons = load_reasons(args.reasons) if args.reasons else None
    summary = summarize(cases, rows, {**conditions, "labels_sha256": manifest["sha256"],
                                      "labeler": manifest.get("labeler")}, reasons)
    (args.run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\n".join(report_lines(summary)))
    print(f"\n→ {args.run_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
