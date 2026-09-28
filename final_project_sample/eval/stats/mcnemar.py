"""McNemar test over discordant paired binary outcomes."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


def exact_two_sided(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n))


def _configured_exact_threshold():
    path = Path(__file__).resolve().parents[2] / "config" / "guardrails.yaml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 25
    match = re.search(r"^\s*mcnemar_exact_threshold:\s*(\d+)\s*$", text, re.MULTILINE)
    return int(match.group(1)) if match else 25


def mcnemar_result(b, c, exact_threshold=None):
    threshold = _configured_exact_threshold() if exact_threshold is None else exact_threshold
    n = b + c
    if n < threshold:
        statistic = float(abs(b - c))
        if n == 0:
            p_value = 1.0
        else:
            try:
                from scipy.stats import binomtest
                p_value = float(binomtest(b, n=n, p=0.5, alternative="two-sided").pvalue)
            except ImportError:
                p_value = exact_two_sided(b, c)
        method = "exact binomial"
    else:
        statistic = float((abs(b - c) - 1) ** 2 / n) if n else 0.0
        try:
            from scipy.stats import chi2
            p_value = float(chi2.sf(statistic, df=1))
        except ImportError:
            p_value = math.erfc(math.sqrt(statistic / 2.0))
        method = "chi-square continuity-corrected"
    assert 0.0 <= p_value <= 1.0
    return statistic, p_value, method


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line.strip()]
    # Preserve the established report convention: b = y-only success,
    # c = x-only success. The statistic and p-value are symmetric in b/c.
    b = sum(not bool(row.get("x_success", row.get("b_success", False))) and
            bool(row.get("y_success", row.get("a_success", False))) for row in rows)
    c = sum(bool(row.get("x_success", row.get("b_success", False))) and
            not bool(row.get("y_success", row.get("a_success", False))) for row in rows)
    statistic, p_value, method = mcnemar_result(b, c)
    print(f"discordant_b={b}; discordant_c={c}; discordant_total={b+c}; "
          f"statistic={statistic:.6f}; method={method}; p_value={p_value:.12g}")


if __name__ == "__main__":
    main()
