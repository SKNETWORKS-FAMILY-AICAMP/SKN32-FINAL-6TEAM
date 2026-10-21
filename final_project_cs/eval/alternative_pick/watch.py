# -*- coding: utf-8 -*-
"""감시 경로 사례 — 동결된 holdout(`cases.jsonl`, 고객 요청 경로)에서 고객 문장만 뺀 판. `[2026-10-19]`

★왜 따로 만드나: 감시 루프가 연 Case 는 고객 문장이 없다. 전에는 Case 제목(`[감시] 경복궁 — closure`)이 고객 문장 자리로
  들어갔고, 10-19 에 고쳐 고객이 답한 말만 넘긴다(`alternative_order.customer_words`). 그래서 감시 경로에서 LLM 이 받는 것은
  「설문(+ 고객 답)」이다. holdout 80 은 고객 문장이 있는 경로만 잰다.
★동결본은 고치지 않는다 — 같은 후보 · 설문으로 `customer_text=None` 인 사례를 새로 만든다(`case_id` 뒤에 `-W`).
★운영과 같은 기준으로 나눈다(`alternative_order.preference_inputs(survey, None)`):
  - `not_called` — 취향 칸이 하나도 없다. 운영도 LLM 을 부르지 않고 코드 순서다 → 사례에서 뺀다(수만 매니페스트에).
  - (10-19 판에만) `rule` — 넘기는 칸이 우선순위(`priority`)뿐이었다. 규칙 라벨(셋 다 허용 · 위험 없음 · 코드 순서 유지 기대)로
    33건을 쟀고(동결 `cases_watch.jsonl` · 실행 20261019T144241Z), 4/99 가 우선순위를 취향으로 읽어 순서를 바꿨다.
    `[2026-10-20 사용자 결정]` 운영이 우선순위를 LLM 에 넘기지 않게 됐다(`alternative_order.SURVEY_FIELDS`) — 이제 이 사례는
    `not_called` 다. 그래서 지금 만드는 판에는 `rule` 이 없다.
  - `human` — 테마 · 실내외 · 세부 테마 같은 취향 설문이 있다. 고객 문장 판의 라벨을 그대로 쓸 수 없다(충돌 C 는 정답이
    설문 쪽으로 바뀌고, 설문 단서 B 도 작성자 문장에 단서가 섞였다 — L-38 「비 온다는데」) → 사람 라벨(`situation_cards_watch` 묶음).
★입력이 같은 사례(후보 순서 · 설문이 같음)는 첫 것만 둔다 — 같은 것을 두 번 재면 사례 단위 신뢰구간이 좁아진다.
"""
from __future__ import annotations

import json
from typing import Any

from app.domains.travel_ops.instances.activity import alternative_order

SUFFIX = "-W"


def kind_of(survey: dict[str, Any] | None) -> str:
    return "not_called" if alternative_order.preference_inputs(survey, None) is None else "human"


def signature(case: dict) -> str:
    return json.dumps([[c["id"] for c in case["inputs"]["candidates"]], case["inputs"]["preference"]["survey"]],
                      ensure_ascii=False, sort_keys=True)


def variants(chat_cases: list[dict]) -> tuple[list[dict], dict[str, Any]]:
    """고객 문장 판 사례 → (감시 판 사례 — 라벨은 아직 비움, 나눈 수 · 뺀 사례)."""
    out: list[dict] = []
    seen: dict[str, str] = {}
    skipped: dict[str, list[str]] = {"not_called": [], "duplicate": []}
    for case in chat_cases:
        kind = kind_of(case["inputs"]["preference"]["survey"])
        if kind == "not_called":
            skipped["not_called"].append(case["case_id"])
            continue
        sig = signature(case)
        if sig in seen:
            skipped["duplicate"].append(f"{case['case_id']}={seen[sig]}")
            continue
        seen[sig] = case["case_id"]
        out.append({
            **case, "case_id": case["case_id"] + SUFFIX, "path": "watch", "watch_kind": kind,
            "from_case": case["case_id"],
            "inputs": {**case["inputs"], "preference": {**case["inputs"]["preference"], "customer_text": None}},
            "acceptable": [], "forbidden": [], "no_fit": False, "expects_code_order": False,
            # 고객 문장이 없으니 문장에서 나온 금지 주장(E)도 없다
            "forbidden_claims": [], "text_by": "none(감시)", "label_by": None,
        })
    counts = {"variants": len(out), "human": len(out),
              "not_called": len(skipped["not_called"]), "duplicate": len(skipped["duplicate"])}
    return out, {**counts, "skipped": skipped}


def label(cases: list[dict], human: dict[str, dict] | None, labeler: str) -> list[dict]:
    """사람 라벨(번호 → id). 빠지면 멈춘다."""
    missing = [c["case_id"] for c in cases if c["case_id"] not in (human or {})]
    if missing:
        raise SystemExit(f"감시 판 사람 라벨이 없는 사례 {len(missing)}건: {', '.join(missing[:10])} — "
                         "`python -m eval.human_review export situation_cards_watch` 로 시트를 낸다")
    out = []
    for case in cases:
        ids = [c["id"] for c in case["inputs"]["candidates"]]
        entry = human[case["case_id"]]
        out.append({**case, "acceptable": [ids[int(n) - 1] for n in entry.get("acceptable", [])],
                    "forbidden": [ids[int(n) - 1] for n in entry.get("forbidden", [])],
                    "no_fit": bool(entry.get("no_fit")), "label_by": labeler})
    return out
