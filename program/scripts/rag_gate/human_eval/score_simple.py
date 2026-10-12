# -*- coding: utf-8 -*-
"""사람 평가(v3 HTML — 맞다 / 중간 / 틀리다 / 모름)에서 내려받은 CSV 를 센다. `[2026-10-06]`

    python score_simple.py 사람평가_A.csv                 한 사람 결과
    python score_simple.py 사람평가_A.csv 사람평가_B.csv   두 사람 결과 + 평가자끼리 일치도

세는 것
  ① 시스템 답이 맞다고 본 비율 — 종류별(규정 질문 답 · 알림 번역) · 층별. 「맞다」 1점 · 「중간」 0.5점 · 「틀리다」 0점으로 평균도 낸다(모름은 뺀다).
  ② Claude 예상과 사람 판정의 일치 — ★사람이 Claude 의견을 보고 정했으므로 독립 일치도가 아니다(부풀 수 있다). 다르게 고른 행을 따로 보여 준다.
  ③ 두 사람이면 평가자끼리 일치도 — 선형 가중 카파(맞다 > 중간 > 틀리다 순서). 모름은 둘 중 한 쪽이라도 모름이면 뺀다.
★비워 둔 행은 센 분모에서 뺀다 — 분모를 항상 같이 적는다. 표본 35개 · 질문과 알림은 합성이라 일반화하지 않는다.
"""
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8")
ORDER = ["맞다", "중간", "틀리다"]
POINT = {"맞다": 1.0, "중간": 0.5, "틀리다": 0.0}
key = {k["id"]: k for k in json.load(open(os.path.join(HERE, "human_eval_key.json"), encoding="utf-8"))}


def read(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    assert rows and "사람 판정" in rows[0], f"{path}: v3 HTML 에서 내려받은 CSV 가 아니다(「사람 판정」 열이 없다)"
    return {r["id"]: r for r in rows}


def wkappa(a, b):
    n = len(a)
    if n < 2:
        return None
    o = collections.Counter(zip(a, b))
    ca, cb = collections.Counter(a), collections.Counter(b)
    w = lambda i, j: abs(ORDER.index(i) - ORDER.index(j)) / (len(ORDER) - 1)
    num = sum(w(i, j) * o[(i, j)] / n for i in ORDER for j in ORDER)
    den = sum(w(i, j) * ca[i] * cb[j] / (n * n) for i in ORDER for j in ORDER)
    return None if den == 0 else 1 - num / den


def report(name, rows):
    done = {i: r for i, r in rows.items() if r["사람 판정"] in ORDER + ["모름"]}
    print(f"\n## 평가자 {name} — 답한 행 {len(done)}/{len(rows)}")
    if not done:
        print("아직 평가 없음 — 점수를 만들어 내지 않는다.")
        return done
    by = collections.defaultdict(list)
    for i, r in done.items():
        by[r["종류"]].append(r["사람 판정"])
        by["(전체)"].append(r["사람 판정"])
    print("| 종류 | 행 수 | 맞다 | 중간 | 틀리다 | 모름 | 평균 점수(모름 제외, 0~1) |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for k in sorted(by, key=lambda x: (x != "(전체)", x)):
        c = collections.Counter(by[k])
        pts = [POINT[v] for v in by[k] if v in POINT]
        print(f"| {k} | {len(by[k])} | {c['맞다']} | {c['중간']} | {c['틀리다']} | {c['모름']} | {sum(pts) / len(pts):.2f} ({len(pts)}행) |" if pts else f"| {k} | {len(by[k])} | 0 | 0 | 0 | {c['모름']} | — |")
    layer = collections.defaultdict(list)
    for i, r in done.items():
        if r["사람 판정"] in POINT:
            layer[(key[i]["종류"], key[i]["층"])].append(POINT[r["사람 판정"]])
    print("\n층별 평균 점수 — 층은 표본을 뽑을 때 나눈 이름이다(평가자에게는 보이지 않았다)")
    print("| 종류 | 층 | 행 수 | 평균 점수 |")
    print("|---|---|---:|---:|")
    for (k, s), v in sorted(layer.items()):
        print(f"| {k} | {s} | {len(v)} | {sum(v) / len(v):.2f} |")
    judged = [r for r in done.values() if r["사람 판정"] in ORDER]
    same = [r for r in judged if r["사람 판정"] == r["Claude 예상"]]
    print(f"\nClaude 예상과 같은 판정: {len(same)}/{len(judged)} (모름 제외 · 사람이 Claude 의견을 보고 정했으므로 독립 일치도가 아니다)")
    diff = [r for r in judged if r["사람 판정"] != r["Claude 예상"]]
    if diff:
        print("다르게 고른 행:")
        for r in diff:
            memo = f" — 메모: {r['사람 메모']}" if r.get("사람 메모") else ""
            print(f"- {r['id']} ({r['종류']}): 사람 {r['사람 판정']} / Claude {r['Claude 예상']}{memo}")
    return done


paths = sys.argv[1:]
if not paths:
    sys.exit("사용: python score_simple.py 사람평가_A.csv [사람평가_B.csv]")
res = [(os.path.basename(p), report(os.path.basename(p), read(p))) for p in paths]
if len(res) == 2:
    (na, da), (nb, db) = res
    both = [i for i in da if i in db and da[i]["사람 판정"] in ORDER and db[i]["사람 판정"] in ORDER]
    print(f"\n## 평가자끼리 일치 — 둘 다 맞다/중간/틀리다로 답한 행 {len(both)}")
    if both:
        a, b = [da[i]["사람 판정"] for i in both], [db[i]["사람 판정"] for i in both]
        k = wkappa(a, b)
        exact = sum(1 for x, y in zip(a, b) if x == y)
        print(f"- 완전 일치 {exact}/{len(both)}" + (f" · 선형 가중 카파 {k:.2f}" if k is not None else " · 카파 계산 불가(한쪽이 한 가지로만 답함)"))
        print("- 다르게 고른 행: " + (", ".join(f"{i}({da[i]['사람 판정']}/{db[i]['사람 판정']})" for i in both if da[i]["사람 판정"] != db[i]["사람 판정"]) or "없음"))
