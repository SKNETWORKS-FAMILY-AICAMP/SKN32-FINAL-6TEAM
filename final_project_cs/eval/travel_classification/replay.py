# -*- coding: utf-8 -*-
"""여행 인라인 분류 재생 시험 — **실제 모델**로 정답 표기된 문장을 돌려 정확도 · 틀림 갈래 · 지연을 잰다. `[2026-10-03]`

    python -m eval.travel_classification.replay eval/datasets/travel_golden.jsonl
    python -m eval.travel_classification.replay eval/datasets/travel_golden.jsonl --repeats 3

★서버 코드(`app.modules.travel_ops.feedback.classify` — 지시문 · 어휘 검증 · 한 번 되묻기)를 그대로 부른다. 제공자는 설정이 정한다(Ollama 주소가 있으면 Ollama, 없으면 OpenAI).
★정답 자료는 쇼핑몰 시절 것이 아니다 — `eval/datasets/travel_golden.jsonl`(72) · `travel_holdout.jsonl`(24). 라벨은 **사람 검수 전 초안**이다(`label_by`).
★holdout 은 **프롬프트를 고치는 데 쓰지 않는다**(만지는 순간 holdout 이 아니다). 프롬프트·어휘를 다듬을 때는 golden 으로만 보고, holdout 은 마지막에 한 번 잰다.

무엇을 세나(분모는 모두 「자료 건수」다 — 실패(`failed`)도 틀린 것으로 센다. 분모에서 빼면 성공률이 부풀려진다):
    intent · issue_code · both    정확히 같음
    case_type                      issue_code 의 접두가 같음 — **팀이 갈리는 축**이다
    wrong_team                     접두가 달라 **엉뚱한 팀**으로 가는 것(가장 위험) — 기대 `other` 에 팀을 붙인 것도 센다
    unrouted                       기대는 팀이 있는데 `other` 로 답해 escalate 되는 것(안전한 쪽의 틀림)
    failed                         분류를 완성하지 못함(`ClassificationFailed` — 목록 밖 라벨 · 빈 라벨 · 제공자 실패)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.application.routing import case_type_of

KST = ZoneInfo("Asia/Seoul")
REPORT_DIR = Path(__file__).resolve().parent / "reports"


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def run(rows: list[dict[str, Any]], classify: Callable[[str], Any], *, repeats: int = 1,
        clock: Callable[[], float] = time.perf_counter) -> dict[str, Any]:
    """`classify(문장)` → `.intent .issue_code .sentiment .severity` 를 가진 값. 실패하면 예외."""
    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    for row in rows:
        for _ in range(repeats):
            started = clock()
            entry = {"case_id": row["case_id"], "expected": {k: row[f"expected_{k}"] for k in ("intent", "issue_code", "sentiment", "severity")}}
            try:
                got = classify(row["message"])
                entry["predicted"] = {k: getattr(got, k) for k in ("intent", "issue_code", "sentiment", "severity")}
            except Exception as exc:                  # noqa: BLE001 — 실패를 세어 남긴다(조용히 빼지 않는다)
                entry["failed"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            latencies.append(clock() - started)
            results.append(entry)
    return summarize(results, latencies)


def _case_type(code: str) -> str:
    return case_type_of(code)


def summarize(results: list[dict[str, Any]], latencies: list[float]) -> dict[str, Any]:
    n = len(results)
    failed = [r for r in results if "failed" in r]
    done = [r for r in results if "predicted" in r]
    hit = Counter()
    wrong_team, unrouted = [], []
    confusion: Counter[tuple[str, str]] = Counter()
    per_code: dict[str, list[int]] = defaultdict(lambda: [0, 0])          # code → [맞음, 전체]
    for r in results:
        want = r["expected"]
        per_code[want["issue_code"]][1] += 1
        if "predicted" not in r:
            continue
        got = r["predicted"]
        for key in ("intent", "issue_code", "sentiment", "severity"):
            hit[key] += got[key] == want[key]
        hit["both"] += got["intent"] == want["intent"] and got["issue_code"] == want["issue_code"]
        same_team = _case_type(got["issue_code"]) == _case_type(want["issue_code"])
        hit["case_type"] += same_team
        per_code[want["issue_code"]][0] += got["issue_code"] == want["issue_code"]
        if got["issue_code"] != want["issue_code"]:
            confusion[(want["issue_code"], got["issue_code"])] += 1
        if not same_team:
            # 접두가 없는 `other` 로 답한 것은 escalate 라 엉뚱한 팀으로 가지 않는다 — 안전한 쪽의 틀림
            (unrouted if got["issue_code"] == "other" else wrong_team).append(r["case_id"])
    pct = lambda value: round(value / n, 3) if n else None                     # noqa: E731
    ordered = sorted(latencies)
    return {
        "cases": n, "failed": len(failed),
        "intent": pct(hit["intent"]), "issue_code": pct(hit["issue_code"]), "both": pct(hit["both"]),
        "case_type": pct(hit["case_type"]), "sentiment": pct(hit["sentiment"]), "severity": pct(hit["severity"]),
        "wrong_team": len(wrong_team), "wrong_team_cases": wrong_team, "unrouted": len(unrouted),
        "per_issue_code": {code: f"{ok}/{total}" for code, (ok, total) in sorted(per_code.items())},
        "top_confusions": [{"expected": e, "predicted": p, "count": c} for (e, p), c in confusion.most_common(8)],
        "failures": [{"case_id": r["case_id"], "error": r["failed"]} for r in failed][:10],
        "p50": round(statistics.median(ordered), 2) if ordered else None,
        "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 2) if ordered else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="여행 인라인 분류 재생 시험")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--repeats", type=int, default=1, help="같은 문장을 몇 번 돌리나(모델은 매번 조금 다르다 — 편차를 보려면 2 이상)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    from app.core.settings import get_settings
    from app.modules.travel_ops.feedback import classify

    settings = get_settings()
    provider = "ollama:" + settings.ollama_model if (settings.ollama_base_url or "").strip() else "openai:" + str(settings.llm_model)
    rows = load(args.dataset)
    report = {"dataset": args.dataset.name, "provider": provider, "repeats": args.repeats,
              "at": datetime.now(KST).isoformat(timespec="seconds"), "summary": run(rows, classify, repeats=args.repeats)}
    out = args.out or REPORT_DIR / f"report_{args.dataset.stem}_{datetime.now(KST):%Y%m%d_%H%M}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"\n제공자 {provider} · 보고서 {out}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
