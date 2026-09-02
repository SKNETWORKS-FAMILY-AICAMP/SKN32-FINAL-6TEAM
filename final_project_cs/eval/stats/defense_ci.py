"""방어 지표 5종의 95% 신뢰구간을 **케이스 단위 부트스트랩**으로 낸다.

★DoD-28 은 "스키마 준수율·근거 정합률·기권 지표의 **분모와 CI 를 기록**"
  하라고 요구한다(계획서 v8 §27 항목 28). 분모는 처음부터 기록해 왔지만
  **CI 는 기록된 적이 없었다**(2026-09-02 실측: 증거 문서와 지표 JSON
  둘 다에 신뢰구간이 없다). 이 스크립트가 그 빠진 절반을 채운다.

★**케이스를 재표집한다. 필드가 아니다.** `근거 정합률`의 분모 702 는
  60 케이스에 걸친 **필드 수**다. 필드를 독립 표본으로 보고 이항 CI 를
  씌우면 구간이 실제보다 훨씬 좁게 나온다 — 같은 케이스 안의 필드들은
  서로 상관이 있기 때문이다(한 케이스가 통째로 틀리면 그 케이스의 필드가
  다 같이 틀린다). 그래서 표본 단위를 케이스로 두고 다시 세는
  cluster bootstrap 을 쓴다.

★계산은 `eval/defense_metrics.py::score()` 를 **그대로 재사용**한다.
  여기서 비율을 다시 구현하면 기록된 수치와 미세하게 어긋날 수 있고,
  그러면 CI 가 어느 점추정치의 구간인지 알 수 없게 된다.

    python -m eval.stats.defense_ci --input eval/reports/2026-08-28_golden_defense_input.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

from eval.defense_metrics import score

ROOT = Path(__file__).resolve().parents[2]

METRICS = ("grounding_match", "grounding_excess", "proper_abstention",
           "over_abstention", "schema_compliance")


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _ratios(rows: list[dict]) -> dict[str, float | None]:
    report = score(rows).as_dict()
    return {name: report[name]["ratio"] for name in METRICS}


def bootstrap_ci(rows: list[dict], *, iterations: int, seed: int,
                 alpha: float = 0.05) -> dict[str, dict]:
    rng = random.Random(seed)
    point = _ratios(rows)
    samples: dict[str, list[float]] = {name: [] for name in METRICS}

    for _ in range(iterations):
        resampled = [rows[rng.randrange(len(rows))] for _ in range(len(rows))]
        for name, value in _ratios(resampled).items():
            # ★분모가 0 이 된 재표집은 그 지표에서 **버린다**(0 으로 세지 않는다).
            #   0 으로 채우면 "측정 못 함"이 "0%" 로 둔갑해 구간이 아래로 끌린다.
            if value is not None:
                samples[name].append(value)

    out: dict[str, dict] = {}
    lower_q, upper_q = alpha / 2, 1 - alpha / 2
    for name in METRICS:
        values = sorted(samples[name])
        if point[name] is None or not values:
            out[name] = {"point": point[name], "ci95": None,
                         "note": "분모 0 — 이 데이터셋으로는 측정할 수 없다"}
            continue
        # ★nearest-rank 백분위는 0-based 로 `ceil(q*n) - 1` 이다. 처음엔 상한을
        #   `int(q*n)` 으로 써서 한 칸 위 값을 집었다(2026-09-02 Codex 교차검증에서
        #   지적, 계산으로 확인: n=10000·q=0.975 면 정답 9749 인데 9750 을 집었다).
        #   n 이 크면 차이가 작지만 틀린 건 틀린 것이고, 표본이 작을수록 커진다.
        lower = values[max(0, math.ceil(lower_q * len(values)) - 1)]
        upper = values[min(len(values) - 1, max(0, math.ceil(upper_q * len(values)) - 1))]
        out[name] = {
            "point": round(point[name], 4),
            "ci95": [round(lower, 4), round(upper, 4)],
            "resamples_used": len(values),
        }
    return out


def main() -> int:
    # ★Windows 콘솔 기본 코드페이지(cp949)가 한글 문장부호를 못 찍어 죽는다.
    #   이 저장소에서 전에도 같은 것에 걸렸다(judge agreement 도구, 2026-08-18).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="방어 지표 95% CI (케이스 단위 부트스트랩)")
    parser.add_argument("--input", default="eval/reports/2026-08-28_golden_defense_input.jsonl")
    parser.add_argument("--output", default=None)
    parser.add_argument("--iterations", type=int, default=10000,
                        help="기존 eval/stats/bootstrap.py 와 같은 10,000 회가 기본")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    path = ROOT / args.input if not Path(args.input).is_absolute() else Path(args.input)
    rows = _load(path)
    result = {
        "input": args.input,
        "cases": len(rows),
        "iterations": args.iterations,
        "seed": args.seed,
        "resample_unit": "case",
        "metrics": bootstrap_ci(rows, iterations=args.iterations, seed=args.seed),
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        out_path = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"\n기록: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
