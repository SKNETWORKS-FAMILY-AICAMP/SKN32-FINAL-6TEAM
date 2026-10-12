"""JevBench 보드 순위와 우리 일정 항목 매칭 시험 순위가 같은 방향인지 다시 계산한다 (2026-10-07).

왜: 연구 문서 §81-4 의 「순위상관 지능 +0.89(14개)」는 계산 스크립트 없이 적힌 값이었다. 발표 · 보고서에
「외부 벤치마크와 순위가 맞는다 → 우리 시험이 엉뚱한 것을 재지 않는다(수렴 타당도)」 근거로 쓰려면 다시 계산할 수 있어야 한다.

방법
- 보드: JevBench v1.6.0(2026-10-06 06:00 KST 내려받은 사본 research/jevbench_v1.6.0_순위_2026-10-06.tsv) 의 지능 · choice · noul · 헤드라인 열.
- 우리: results/export/per_question.csv 에서 학습하지 않은 원본 모델의 단독 풀이만. 모든 모델이 푼 같은 문제(mix8 · mix9,
  복수 항목 질의 compound_intent 제외)로 정확도를 낸다 — 모델마다 푼 세트가 달라 생기는 차이를 없앤다.
- 짝: 이름과 변형(양자화 · 판)이 보드와 맞는 것만. 맞는지 애매한 것은 MAYBE 로 따로 두고 넣은 경우 · 뺀 경우를 둘 다 낸다.
- 스피어만 순위상관 + 95% 구간(Fisher z, 표준오차 sqrt(1.06/(n-3))) + 부트스트랩 2,000회 구간.
"""
from __future__ import annotations

import csv
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TSV = ROOT / "research" / "jevbench_v1.6.0_순위_2026-10-06.tsv"
PQ = Path(__file__).resolve().parent / "results" / "export" / "per_question.csv"
OUT = Path(__file__).resolve().parent / "results" / "jevbench_rank_check.txt"

# 우리 모델 이름 → 보드 key (변형이 맞는 것)
SURE = {
    "Winnow-12B Q8": "winnow-12b",
    "Cygnet(얼린 Gemma-4-12B-it 글자 읽기, 8비트)": "cygnet",
    "Plumb-4B v5 Q8": "plumb-4b",
    "lev(Interfaze, Qwen3.5-4B + LoRA)": "lev",
    "JevK5 4B v0.3 Q8": "jevk5-v0.3-4b",
    "Hopper 4B(Qwen3.5-4B + LoRA r16)": "hopper",
    "Imajev-4B": "imajev-4b-rtx5090-a2",
    "Malkuth-4B": "malkuth-4b",
    "Manchego v2.1(4B)": "manchego-v21-v15",
    "Decider-35B-A3B bf16": "decider-35b-a3b",
    "Nimble-9B-v3 Q8": "nimble-9b",
    "Decider-2B": "decider-2b",
    "Kev-4B Q8": "kev-4b",
    "Jev 직접 (유료)": "jev-1.13.0",
}
# 변형이 다를 수 있는 것(넣은 경우 · 뺀 경우 둘 다 낸다)
MAYBE = {
    "Jev-Omni 묶음 읽기(20개 이하씩)": "jev-omni",          # 우리는 선택지를 20개 이하로 묶어 읽음
    "Decider-4B (자체 라이브러리)": "decider-4b-v2",         # 판 번호 미확인
    "OpenJev 26B Q4_K_M": "openjev-thinking",                # 보드는 BF16 · 생각 켬
}
SETS = {"mix8", "mix9"}
COLS = ("intel", "choice_s", "noul_s", "score")


def load_board():
    rows = {}
    with TSV.open(encoding="utf-8") as f:
        lines = [ln for ln in f if not ln.startswith("#")]
    for r in csv.DictReader(lines, delimiter="\t"):
        rows[r["key"]] = r
    return rows


def load_ours():
    per = defaultdict(dict)
    with PQ.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["set"] in SETS and r["q_type"] != "compound_intent":
                per[r["model"]][(r["set"], r["q_index"])] = r["correct"] == "1"
    return per


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    rk = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            rk[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return rk


def spearman(x, y):
    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den


def fisher_ci(r, n):
    z, se = math.atanh(max(min(r, 0.999999), -0.999999)), math.sqrt(1.06 / (n - 3))
    return math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)


def boot_ci(x, y, b=2000, seed=7):
    rnd = random.Random(seed)
    n, vals = len(x), []
    for _ in range(b):
        idx = [rnd.randrange(n) for _ in range(n)]
        xs, ys = [x[i] for i in idx], [y[i] for i in idx]
        if len(set(xs)) > 1 and len(set(ys)) > 1:
            vals.append(spearman(xs, ys))
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    board, ours = load_board(), load_ours()
    pairs = {**SURE, **MAYBE}
    common = None
    for m in pairs:
        if m in ours:
            common = set(ours[m]) if common is None else common & set(ours[m])
    out = [f"# JevBench v1.6.0 보드 순위 ↔ 우리 일정 항목 매칭 순위 (mix8 · mix9 공통 {len(common)}문제, 복수 항목 질의 제외)", ""]
    table = []
    for m, key in pairs.items():
        if m not in ours or key not in board:
            out.append(f"빠짐: {m} → {key} (우리 {'있음' if m in ours else '없음'} · 보드 {'있음' if key in board else '없음'})")
            continue
        acc = sum(ours[m][q] for q in common) / len(common)
        table.append((m, key, acc, board[key], m in MAYBE))
    out.append("")
    out.append("| 모델 | 보드 순위 | 지능 | choice | noul | 헤드라인 | 우리 정확도 | 변형 |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for m, key, acc, b, maybe in sorted(table, key=lambda t: -t[2]):
        out.append(f"| {m} | {b['rank']} | {b['intel']} | {b['choice_s']} | {b['noul_s']} | {b['score']} | {acc * 100:.1f}% | {'애매' if maybe else '같음'} |")
    for label, rows in (("변형이 같은 것만", [t for t in table if not t[4]]), ("애매한 것까지", table)):
        n = len(rows)
        out.append("")
        out.append(f"## {label} (n={n})")
        y = [t[2] for t in rows]
        for c, name in zip(COLS, ("지능", "choice", "noul", "헤드라인")):
            x = [float(t[3][c]) for t in rows]
            r = spearman(x, y)
            lo, hi = fisher_ci(r, n)
            blo, bhi = boot_ci(x, y)
            out.append(f"- {name}: ρ = {r:+.2f} (Fisher 95% {lo:+.2f} ~ {hi:+.2f} · 부트스트랩 {blo:+.2f} ~ {bhi:+.2f})")
    text = "\n".join(out)
    OUT.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
