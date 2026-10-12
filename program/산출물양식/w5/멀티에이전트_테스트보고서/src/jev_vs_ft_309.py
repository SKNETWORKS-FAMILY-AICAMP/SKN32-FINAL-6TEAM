"""Jev(유료 API) 직접 짚기와 가르친 E4B 를 같은 문제로 짝지어 비교한다 (새 모델 호출 없음, 저장된 결과만 읽음).

범위: mix8 + mix9 중 요청 둘(compound_intent)을 뺀 309문제 — Jev 는 mix8 · mix9 에서만 호출했다(§17 · §47 · §51).
읽는 것: results/jev_out_mix{8,9}.json(Jev 1.13.0, 2026-10-03 호출) · results/_pull/distill_eval/eval_r16e2_mix{8,9}.json(가르친 E4B, 2026-10-06)
         · fixtures/mix{8,9}.json(정답 · 유형). 결과: ../_재료/jev_vs_ft_309.json
"""
import json
from math import comb
from pathlib import Path

B = Path(__file__).resolve().parents[5] / "program/scripts/plan_qa_bench"
OUT = Path(__file__).resolve().parents[1] / "_재료" / "jev_vs_ft_309.json"


def jev_picks(w):
    rows = json.load(open(B / f"results/jev_out_{w}.json", encoding="utf-8"))[w]["rows"]
    out = []
    for r in rows:
        pr = r["probs"]
        k = max(pr, key=pr.get) if pr else "none"
        out.append(int(k.split("_")[1]) if k.startswith("item_") else None)
    return out


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    p = sum(comb(n, k) for k in range(0, min(b, c) + 1)) / 2 ** n * 2
    return min(1.0, p)


res = {"sets": {}, "note": "요청 둘(compound_intent) 제외. Jev 는 확률이 가장 큰 선택지(none 포함)를 답으로 본다(eval_final_all.py 와 같은 방식)."}
tot = {"n": 0, "jev": 0, "ft": 0, "base": 0, "jev_only": 0, "ft_only": 0, "jev_wrong_item": 0, "ft_wrong_item": 0}
for w in ("mix8", "mix9"):
    qs = json.load(open(B / f"fixtures/{w}.json", encoding="utf-8"))["sets"][w]["qs"]
    jp = jev_picks(w)
    ev = json.load(open(B / f"results/_pull/distill_eval/eval_r16e2_{w}.json", encoding="utf-8"))
    fp, bp = ev["r16e2#lora"]["picks"], ev["r16e2#base"]["picks"]
    s = {"n": 0, "jev": 0, "ft": 0, "base": 0}
    for i, q in enumerate(qs):
        if q["type"] == "compound_intent":
            continue
        g = q["gold"]
        f = fp[i] if isinstance(fp, list) else fp[str(i)]
        bb = bp[i] if isinstance(bp, list) else bp[str(i)]
        jo, fo = jp[i] == g, f == g
        s["n"] += 1; s["jev"] += jo; s["ft"] += fo; s["base"] += (bb == g)
        tot["jev_only"] += jo and not fo
        tot["ft_only"] += fo and not jo
        tot["jev_wrong_item"] += (not jo) and jp[i] is not None
        tot["ft_wrong_item"] += (not fo) and f is not None
    res["sets"][w] = s
    for k in ("n", "jev", "ft", "base"):
        tot[k] += s[k]
tot["p_mcnemar"] = mcnemar(tot["jev_only"], tot["ft_only"])
res["total"] = tot
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
