# -*- coding: utf-8 -*-
"""「흐름 한 칸」 실제 모델 측정 — 스위치는 **이 프로세스에서만** 켠다(설정 파일은 그대로). `[2026-10-16]`

    python -m eval.runners.dining_flow_slot_live            # 실제 모델 호출(비용 발생) · 결과 eval/reports/2026-10-16_dining_flow_slot_live.json

★무엇을 재나: 규칙 1위가 그대로인가 · 모델이 둘째 칸에 고른 안이 기대에 맞나 · 서버 확인(인용 · 후보 안)을 통과하나 · 걸린 시간.
★사례: 취향 12건(`dining_alternatives_pref_v1` — 기대 = 취향에 맞는 곳) + 흐름 3건(이 파일 — 취향 문장 없이, 점심과 같은 결이 아닌 곳).
  흐름 3건은 이 측정을 위해 만든 합성 사례다 — 정답지로 검증된 평가 자료가 아니다. 한 번씩만 돌린다(반복 · 분산은 재지 않는다).
★조립: `composition._dining_meal_picker()` 가 흐름 선택기를 꽂는지 먼저 확인하고, 측정은 같은 모델 설정으로 만든 채팅에 기록용 감싸개를 씌워 돌린다.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve()
OUT = HERE.parents[1] / "reports" / "2026-10-16_dining_flow_slot_live.json"

FLOW_CASES = [
    {"id": "FL-001", "why": "점심 삼겹살(고기구이) — 저녁 갈비집이 닫음. 둘째 칸은 고기구이가 아닌 곳",
     "path": "closed_on_day",
     "items": [{"seq": 1, "kind": "dining", "title": "점심", "place": "L", "start": "12:00", "end": "13:00"},
               {"seq": 2, "kind": "dining", "title": "저녁", "place": "O", "start": "18:00", "end": "19:00"}],
     "meal": 2,
     "places": [{"key": "L", "name": "돼지마당 삼겹살", "at": [-800, 0], "cuisine": ["한식", "삼겹살"], "category": "한식", "style": "고기구이"},
                {"key": "O", "name": "명동 갈비집", "at": [0, 0], "cuisine": ["한식", "갈비"], "category": "한식", "style": "고기구이"},
                {"key": "A", "name": "숯불갈비 본가", "at": [120, 0], "cuisine": ["한식", "갈비"], "category": "한식", "style": "고기구이"},
                {"key": "B", "name": "할머니 잔치국수", "at": [200, 0], "cuisine": ["한식", "국수"], "category": "한식", "style": "면요리"},
                {"key": "C", "name": "바다 생선구이", "at": [250, 0], "cuisine": ["한식", "생선구이"], "category": "한식", "style": "한상차림"}],
     "expect": {"not_style": "고기구이"}},
    {"id": "FL-002", "why": "점심 국밥(국물요리) — 저녁 순댓국집이 닫음. 둘째 칸은 국물요리가 아닌 곳",
     "path": "closed_on_day",
     "items": [{"seq": 1, "kind": "dining", "title": "점심", "place": "L", "start": "12:00", "end": "13:00"},
               {"seq": 2, "kind": "dining", "title": "저녁", "place": "O", "start": "18:00", "end": "19:00"}],
     "meal": 2,
     "places": [{"key": "L", "name": "시장 돼지국밥", "at": [-800, 0], "cuisine": ["한식", "국밥"], "category": "한식", "style": "국물요리"},
                {"key": "O", "name": "원조 순댓국", "at": [0, 0], "cuisine": ["한식", "순댓국"], "category": "한식", "style": "국물요리"},
                {"key": "A", "name": "뼈해장 감자탕", "at": [120, 0], "cuisine": ["한식", "감자탕"], "category": "한식", "style": "국물요리"},
                {"key": "B", "name": "손칼국수 집", "at": [200, 0], "cuisine": ["한식", "칼국수"], "category": "한식", "style": "면요리"},
                {"key": "C", "name": "전주 비빔밥", "at": [250, 0], "cuisine": ["한식", "비빔밥"], "category": "한식", "style": "한상차림"}],
     "expect": {"not_style": "국물요리"}},
    {"id": "FL-003", "why": "점심 파스타(양식) — 저녁 피자집이 닫음. 둘째 칸은 양식이 아닌 곳",
     "path": "closed_on_day",
     "items": [{"seq": 1, "kind": "dining", "title": "점심", "place": "L", "start": "12:00", "end": "13:00"},
               {"seq": 2, "kind": "dining", "title": "저녁", "place": "O", "start": "18:00", "end": "19:00"}],
     "meal": 2,
     "places": [{"key": "L", "name": "트라토리아 파스타", "at": [-800, 0], "cuisine": ["양식", "파스타"], "category": "양식", "style": "양식"},
                {"key": "O", "name": "화덕 피자", "at": [0, 0], "cuisine": ["양식", "피자"], "category": "양식", "style": "양식"},
                {"key": "A", "name": "수제버거 하우스", "at": [120, 0], "cuisine": ["양식", "버거"], "category": "양식", "style": "양식"},
                {"key": "B", "name": "골목 한식 백반", "at": [200, 0], "cuisine": ["한식", "백반"], "category": "한식", "style": "한상차림"},
                {"key": "C", "name": "스시 오마카세", "at": [250, 0], "cuisine": ["일식", "초밥"], "category": "일식", "style": "초밥"}],
     "expect": {"not_style": "양식"}},
]


class Recorder:
    """채팅 감싸개 — 보낸 것 · 받은 것 · 걸린 시간을 남긴다(키 값은 남기지 않는다)."""

    def __init__(self, inner):
        self.inner, self.calls = inner, []

    def structured(self, system, user, schema, *, num_predict=160):
        started = time.perf_counter()
        try:
            answer = self.inner.structured(system, user, schema, num_predict=num_predict)
            self.calls.append({"user": json.loads(user), "answer": answer, "seconds": round(time.perf_counter() - started, 2)})
            return answer
        except Exception as exc:                               # noqa: BLE001 — 기록하고 그대로 올린다(선택기가 규칙으로 돌아간다)
            self.calls.append({"user": json.loads(user), "error": f"{type(exc).__name__}: {exc}"[:300],
                               "seconds": round(time.perf_counter() - started, 2)})
            raise


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    from app import composition
    from app.core import settings as settings_module
    from app.core.settings import get_guardrails, get_settings
    from app.domains.travel_ops.components.planning import meal_pick
    from eval.runners import dining_alternatives as runner

    import hashlib
    config = HERE.parents[2] / "config" / "guardrails.yaml"
    config_before = hashlib.sha256(config.read_bytes()).hexdigest()
    model_setting = str(get_guardrails().get("travel.dining.meal_pick.model") or "openai:gpt-6-luna")
    # ★스위치 — 이 프로세스에서만 켠다(가드레일 파일은 읽기만)
    settings_module.dining_meal_pick = lambda: {"model": model_setting}
    wired = composition._dining_meal_picker()
    assert wired is not None and wired.__qualname__.startswith("make_flow_picker"), wired

    kind, _, model = model_setting.partition(":")
    assert kind == "openai", model_setting
    from app.infrastructure.llm_failover import OpenAIChat
    chat = Recorder(OpenAIChat(api_key=get_settings().openai_api_key, model=model, timeout=30.0))
    runner._PICK["picker"] = meal_pick.make_flow_picker(chat)

    cases = runner.load_cases(runner.DATASET.with_name("dining_alternatives_pref_v1.jsonl")) + FLOW_CASES
    rows = []
    for case in cases:
        trip, items, places = runner.build(case)
        before = len(chat.calls)
        result = runner.plan(case, trip, items, places)
        meal = next(i for i in items if i.seq == case["meal"])
        by_id = {p["place_id"]: k for k, p in places.items()}
        if not hasattr(result, "replacements"):
            rows.append({"id": case["id"], "result": type(result).__name__, "status": getattr(result, "status", None)})
            continue
        new = result.replacements[meal.item_id]
        alts = new.detail.get("alternates") or []
        first = by_id.get(str(new.place["place_id"]))
        slot2 = by_id.get(str(alts[0].get("place_id"))) if alts else None
        styles = {k: (p.get("attributes") or {}).get("style") for k, p in places.items()}
        record = new.detail.get("meal_pick")
        called = len(chat.calls) > before
        expect = case.get("expect") or {}
        if "accept" in expect:
            hit = slot2 in expect["accept"] or first in expect["accept"]          # 고객이 고를 셋 중 앞 두 칸에 있나
        else:
            hit = slot2 is not None and styles.get(slot2) != expect["not_style"]
        rows.append({"id": case["id"], "why": case.get("why"), "preference": case.get("preference"),
                     "rule_first": first, "slot2": slot2, "slot2_note": alts[0].get("note") if alts else None,
                     "slots": [first] + [by_id.get(str(a.get("place_id"))) for a in alts],
                     "called": called, "by": (record or {}).get("by", "rule"), "failure": (record or {}).get("failure"),
                     "expect": expect, "hit": hit,
                     "model_answer": chat.calls[-1].get("answer") if called else None,
                     "model_error": chat.calls[-1].get("error") if called else None,
                     "seconds": chat.calls[-1]["seconds"] if called else 0})
        print(f"{case['id']:8} 1={first} 2={slot2} by={(record or {}).get('by','rule'):13} hit={hit} "
              f"{(alts[0].get('note') or '')[:60] if alts else ''}", flush=True)

    def pct(a, b):
        return f"{a}/{b} = {a / b:.1%}" if b else f"{a}/0"
    pref = [r for r in rows if r["id"].startswith("DP")]
    flow = [r for r in rows if r["id"].startswith("FL")]
    llm = [r for r in rows if r.get("by") == "llm"]
    summary = {"at": datetime.now().isoformat(timespec="seconds"), "model": model_setting, "cases": len(rows),
               "called": pct(sum(bool(r.get("called")) for r in rows), len(rows)),
               "llm_accepted": pct(len(llm), sum(bool(r.get("called")) for r in rows)),
               "fallback": [{"id": r["id"], "failure": r.get("failure"), "error": r.get("model_error")}
                            for r in rows if r.get("by") == "rule_fallback"],
               "preference_hit": pct(sum(bool(r.get("hit")) for r in pref), len(pref)),
               "flow_hit": pct(sum(bool(r.get("hit")) for r in flow), len(flow)),
               "seconds_avg": round(sum(r.get("seconds", 0) for r in llm) / len(llm), 2) if llm else None,
               "repeats": 1, "note": "흐름 3건은 이 측정용 합성 사례 · 각 1회",
               "config_unchanged": hashlib.sha256(config.read_bytes()).hexdigest() == config_before}
    OUT.write_text(json.dumps({"summary": summary, "rows": rows, "calls": chat.calls}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("report:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
