"""새로 가르친 모델 · 한 줄 시험 · 구조 비교를 A · B · C 로 다시 채점한다 (새 모델 호출 없음, 저장된 결과만 읽음).

채점 정의는 program/scripts/plan_qa_bench/c_scoring_all.py 와 같다.
  A = 요청 둘에서 먼저 말한 항목 · B = 요청 둘에서 말한 항목 중 하나라도 · C = 고른 집합이 정답 집합과 정확히 같음
  한 항목만 내는 모델은 요청 둘(66)의 C 가 0 이라 「C 전체 = 요청 둘 제외 정답 / 835」가 된다.
읽기 실패(빈 응답)는 각 원 보고서처럼 틀린 것으로 센다(정답이 「없음」이어도 맞음으로 세지 않는다).
결과: ../_재료/c_scoring_new.json
"""
import json
from pathlib import Path

B = Path(__file__).resolve().parents[5] / "program/scripts/plan_qa_bench"
OUT = Path(__file__).resolve().parents[1] / "_재료" / "c_scoring_new.json"
SETS = ["mix8", "mix9", "mix10", "mix11", "mix12"]
GS = json.load(open(B / "fixtures/gold_sets.json", encoding="utf-8"))
FX = {s: json.load(open(B / f"fixtures/{s}.json", encoding="utf-8"))["sets"][s] for s in SETS}
KEYS = [(s, i) for s in SETS for i in range(len(FX[s]["qs"]))]
GSET = {(s, i): frozenset(GS[s][str(i)]) for s, i in KEYS}
GOLD = {(s, i): FX[s]["qs"][i]["gold"] for s, i in KEYS}
COMP = {k for k in KEYS if FX[k[0]]["qs"][k[1]]["type"] == "compound_intent"}
FAIL = "__fail__"


def score(picks):
    """picks: {key: list[int] | FAIL} → dict"""
    c_all = c_non = c_comp = a = b = 0
    for k in KEYS:
        p = picks.get(k)
        if p == FAIL:
            continue
        ps = frozenset(p or [])
        hit = ps == GSET[k]
        c_all += hit
        if k in COMP:
            c_comp += hit
            a += bool(p) and p[0] == GOLD[k]
            b += bool(ps & GSET[k])
        else:
            c_non += hit
    return {"C_all": c_all, "non769": c_non, "A66": a, "B66": b, "C66": c_comp}


def single(d):
    return {k: (FAIL if v == FAIL else ([] if v is None else [v])) for k, v in d.items()}


res = {}
# 1) 같은 방법으로 가르친 모델(HF 4비트 + 어댑터, GPU 서버 B)
for tag, lab in (("r16e2", "가르친 E4B"), ("e4bs2", "가르친 E4B 시드 2"), ("winnow_e4b", "가르친 Winnow-E4B(Jev 계열)"), ("e2b", "가르친 Gemma 4 E2B"), ("kanana2_3b", "가르친 Kanana-2-3B")):
    for side, pre in (("lora", ""), ("base", "가르치기 전 ")):
        d = {}
        for s in SETS:
            ev = json.load(open(B / f"results/_pull/distill_eval/eval_{tag}_{s}.json", encoding="utf-8"))
            e = ev[f"{tag}#{side}"]
            errs = set(e.get("_error_idx", []) or [])
            for i, p in enumerate(e["picks"]):
                d[(s, i)] = FAIL if (i in errs or p == "ERR") else p
        if tag in ("e2b", "kanana2_3b", "e4bs2") and side == "base":
            continue
        res[pre + lab] = score(single(d))
        if side == "lora":
            res[pre + lab]["_picks"] = d
# 2) 한 줄 시험 변형(GPU 서버 C 실제 호출)
for f, lab in (("chain_e4b_only", "한 줄: 가르친 E4B 단독(GGUF)"), ("chain_rules_e4b", "한 줄: 규칙 → 가르친 E4B"), ("chain_no_jev", "한 줄: 규칙 → ML → 가르친 E4B"),
               ("chain_full", "한 줄: 전체, 수정 판(Winnow-E4B 학습 없음)"), ("chain_full_v1", "한 줄: 전체, 사전 등록 판(Winnow-E4B 학습 없음)")):
    tr = json.load(open(B / f"results/_pull/chain/{f}.json", encoding="utf-8"))
    d = {(t["set"], t["qi"]): (FAIL if (t.get("ended") == "e4b" and t.get("fail")) else t.get("pick")) for t in tr}
    res[lab] = score(single(d))
# 3) 두 가르친 모델로 짠 구조(전문가 단계는 저장 결과)
off = json.load(open(B / "results/chain_experts_offline.json", encoding="utf-8"))
for k, v in off.items():
    d = {tuple([x.split(":")[0], int(x.split(":")[1])]): p for x, p in v.items()}
    res["구조: " + k] = score(single(d))
# 4) 요청 둘을 알아보는 규칙으로 집합 모델과 이어 붙이기(c_scoring_all.py §5 와 같은 규칙: 이름 조각 3글자 이상이 항목 2개 이상)


def lcs(a, b):
    best, prev = 0, [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def named(k):
    job = FX[k[0]]
    q = "".join(job["qs"][k[1]]["q"].split())
    return sum(1 for it in job["items"] if any(len(n) >= 2 and lcs(q, n) >= 3 for n in ["".join(str(it.get(f, "")).split()) for f in ("title", "place")]))


F3 = {k: named(k) for k in KEYS}
MULTI = {}
for tag, lab in (("claude_opus_5_5", "Claude Opus 5.5"), ("claude_fable_5_1", "Claude Fable 5.1")):
    d = {}
    for s in SETS:
        rr = json.load(open(B / f"results/claude_{tag}_{s}_multi.json", encoding="utf-8"))["rows"]
        for i in range(len(FX[s]["qs"])):
            d[(s, i)] = rr[str(i)].get("picks") or []
    MULTI[lab] = d
d = {}
for s in SETS:
    pk = json.load(open(B / f"results/_pull/multi/llm_{s}_multi_out.json", encoding="utf-8"))["gemma4:12b#multi"]["picks"]
    for i, p in enumerate(pk):
        d[(s, i)] = p
MULTI["Gemma 12B 둘 다 찾기"] = d
for base_lab in ("가르친 E4B", "가르친 Winnow-E4B(Jev 계열)"):
    bp = res[base_lab]["_picks"]
    for lab, md in MULTI.items():
        hy = {k: (md[k] if F3[k] >= 2 else (FAIL if bp[k] == FAIL else ([] if bp[k] is None else [bp[k]]))) for k in KEYS}
        res[f"이어 붙이기: {base_lab} + {lab}"] = score(hy)
for v in res.values():
    v.pop("_picks", None)
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(f'{"방식":<60} C전체/835  769  A/66 B/66 C/66')
for k, v in res.items():
    print(f'{k:<60} {v["C_all"]:>4} ({100 * v["C_all"] / 835:4.1f}%) {v["non769"]:>4} {v["A66"]:>4} {v["B66"]:>4} {v["C66"]:>4}')
