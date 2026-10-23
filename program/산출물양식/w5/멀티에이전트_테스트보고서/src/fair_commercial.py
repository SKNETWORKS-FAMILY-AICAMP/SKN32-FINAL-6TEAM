"""상용 AI(Claude · Codex)를 「자기가 낸 문제」에서 빼고 B · C 채점으로 다시 비교한다 (2026-10-06 사용자 지시).

사용자: 「상용 ai api 랑 비교한 자료에서 클로드랑 코덱스는 각각 자기가 만든 테스트에서는 참여 못하게 하고 B, C 테스트에서 비교하게 했어야 해」.
- mix8~11 은 Codex 가 쓴 문제 → Codex 모델(Luna · Sol · Astra)은 빼고 Claude 모델 · 로컬 모델만 비교
- mix12 는 Claude 가 쓴 문제 → Claude 모델(Opus · Fable)은 빼고 Codex 모델 · 로컬 모델만 비교
- 채점: B = 한 문장에 항목 둘을 묻는 질문(복수 항목 질의)은 말한 항목 중 하나라도 맞으면 정답, 나머지는 정답 항목(또는 「없음」)을 맞혀야 정답
         C = 모델이 낸 항목 집합이 정답 집합과 완전히 같아야 정답(복수 항목 질의는 두 항목을 모두 내야 정답)
- 새 모델 호출 없음. 저장된 문제별 풀이만 다시 센다(program/scripts/plan_qa_bench/c_scoring_all.py 와 같은 파일 · 같은 정의).
- 남는 치우침: 복수 항목 질의의 정답 집합(gold_sets)과 파인튜닝 E4B 의 학습 자료는 Claude 가 만들었다 — 표에 적는다.
결과: ../_재료/fair_commercial.json
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

B = Path(__file__).resolve().parents[5] / "program/scripts/plan_qa_bench"
OUT = Path(__file__).resolve().parents[1] / "_재료" / "fair_commercial.json"
SETS = ["mix8", "mix9", "mix10", "mix11", "mix12"]
GS = json.load(open(B.parents[2] / "datasets/core/pointing/testset/itinerary_questions_v1/gold_sets.json", encoding="utf-8"))
FX = {s: json.load(open(B.parents[2] / f"datasets/core/pointing/testset/itinerary_questions_v1/{s}.json", encoding="utf-8"))["sets"][s] for s in SETS}
KEYS = [(s, i) for s in SETS for i in range(len(FX[s]["qs"]))]
GSET = {k: frozenset(GS[k[0]][str(k[1])]) for k in KEYS}
COMP = {k for k in KEYS if FX[k[0]]["qs"][k[1]]["type"] == "compound_intent"}
SUB = {"codex_made": [k for k in KEYS if k[0] != "mix12"], "claude_made": [k for k in KEYS if k[0] == "mix12"]}


def score(picks, keys):
    b = c = 0
    for k in keys:
        ps = frozenset(picks.get(k) or [])
        c += ps == GSET[k]
        b += bool(ps & GSET[k]) if k in COMP else ps == GSET[k]
    return {"B": b, "C": c, "n": len(keys), "comp": sum(1 for k in keys if k in COMP)}


def fnum(x):
    return None if x in ("", None) else int(float(x))


# 한 항목만 내는 로컬 모델
rows = list(csv.DictReader(open(B / "results/export/per_question.csv", encoding="utf-8-sig")))
SINGLE = defaultdict(dict)
for r in rows:
    if r["set"] in SETS:
        SINGLE[r["model"]][(r["set"], int(r["q_index"]))] = fnum(r["pick"])


def find(prefix):
    c = [m for m in SINGLE if m.startswith(prefix)]
    assert len(c) == 1, (prefix, c)
    return c[0]


def as_set(d):
    return {k: ([] if d.get(k) is None else [d[k]]) for k in KEYS}


MODELS = []  # (이름, 종류, 출제 관계 메모, picks)
E4BT = {}
for s in SETS:
    ev = json.load(open(B / f"results/_pull/distill_eval/eval_r16e2_{s}.json", encoding="utf-8"))
    for i, p in enumerate(ev["r16e2#lora"]["picks"]):
        E4BT[(s, i)] = None if p == "ERR" else p
MODELS.append(("Gemma 4 E4B 파인튜닝(약 4B, 로컬)", "local_ft", "학습 자료를 Claude 가 만듦", as_set(E4BT)))
for lab, pre in (("Gemma 4 26B-A4B(파인튜닝 없음, 로컬)", "Gemma 4 26B"), ("Qwen3.8 27B(파인튜닝 없음, 로컬)", "Qwen3.8 27B")):
    MODELS.append((lab, "local", "", as_set(SINGLE[find(pre)])))
for tag, lab in (("claude_opus_5_5", "Claude Opus 5.5(상용)"), ("claude_fable_5_1", "Claude Fable 5.1(상용)")):
    d = {}
    for s in SETS:
        rr = json.load(open(B / f"results/claude_{tag}_{s}_multi.json", encoding="utf-8"))["rows"]
        for i in range(len(FX[s]["qs"])):
            d[(s, i)] = rr[str(i)].get("picks") or []
    MODELS.append((lab, "claude", "mix12 · 정답 집합 출제자", d))
for m, lab in (("gpt-6-luna", "Codex Luna(상용)"), ("gpt-6-sol", "Codex Sol(상용)"), ("gpt-6-astra", "Codex Astra(상용)")):
    d = {}
    for s in SETS:
        rr = json.load(open(B / f"results/codexcli_{m}_{s}_multi.json", encoding="utf-8"))["rows"]
        for i in range(len(FX[s]["qs"])):
            d[(s, i)] = rr[str(i)].get("picks") or []
    MODELS.append((lab, "codex", "mix8~11 출제자", d))

res = {"codex_made": [], "claude_made": []}
for name, kind, note, picks in MODELS:
    for sub in res:
        if (sub == "codex_made" and kind == "codex") or (sub == "claude_made" and kind == "claude"):
            continue  # 자기가 낸 문제에서는 빠진다
        sc = score(picks, SUB[sub])
        res[sub].append({"model": name, "kind": kind, "note": note, **sc})
for sub in res:
    res[sub].sort(key=lambda r: (-r["B"], -r["C"]))
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
for sub, lab in (("codex_made", "mix8~11(Codex 출제) — Codex 모델 제외"), ("claude_made", "mix12(Claude 출제) — Claude 모델 제외")):
    print("##", lab)
    for r in res[sub]:
        print(f"  {r['model']:<36} B {r['B']}/{r['n']} = {100 * r['B'] / r['n']:.1f}%   C {r['C']}/{r['n']} = {100 * r['C'] / r['n']:.1f}%   {r['note']}")
