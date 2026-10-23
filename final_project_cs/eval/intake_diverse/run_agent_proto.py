# -*- coding: utf-8 -*-
"""읽기 에이전트 **시제품** 재기 — 모델 한 번 호출로 계획서를 통째로 읽어 확인 화면용 계획(중립 모양)을 낸다. `[2026-10-16 사용자 지시]`

    python -m eval.intake_diverse.run_agent_proto --backend ollama --base <Ollama 주소> --model tripilot-pointer:e4b-ft --out <폴더>
    python -m eval.intake_diverse.run_agent_proto --backend llama --base <llama-server 주소> --label winnow-e4b-oos --out <폴더>

★제품 코드가 아니다 — 새 구조(입구 하나 → 모델 하나가 이해 · 분류 → 코드 사실 검사)의 「이해 · 분류」 한 단계만 흉내 낸 것.
★지켜 둔 선: **원문에 글자 그대로 없는 조각은 버린다**(`ground`). 장소 · 이동의 출발/도착 · 이동/조건/성향의 근거 조각 · 시각/날짜의 근거 조각이
  원문의 부분 문자열이 아니면 그 값을 쓰지 않는다. 시각 · 날짜 **값**(HH:MM · YYYY-MM-DD)은 모델이 문맥으로 정한다(「1시쯤 점심」→ 13:00) —
  근거 조각이 원문에 있을 때만 받는다.
★출력 틀은 JSON 스키마로 강제한다(Ollama `format` · llama-server `json_schema`) · 온도 0 · 생각 끔.
★지시문의 예는 시험지와 겹치지 않는 장소로 썼다. 성향 · 조건 · 요청 말 목록은 시험지 정답과 같은 어휘다(같은 사람이 정했다 — 보고서에 적는다).
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
from zoneinfo import ZoneInfo

import httpx

HERE = Path(__file__).resolve().parent
KST = ZoneInfo("Asia/Seoul")
WEEKDAY = "월화수목금토일"
MODES = ["taxi", "subway", "bus", "transit", "walk", "car", "bike", "cablecar"]
PREFS = ["prefer_taxi", "avoid_taxi", "avoid_walking", "prefer_walking", "prefer_transit", "kid_friendly", "elderly_friendly",
         "late_start", "slow_pace", "avoid_stairs", "food_focus", "night_view", "nice_restaurants"]
REQUESTS = ["register", "plan_ask", "question", "correction"]
MISSING = ["first_day_date", "lodging_name", "booked_place_name"]
COND = re.compile(r"^(if_rain_indoor|if_rain_skip|finish_by:\d{2}:\d{2}|start_after:\d{2}:\d{2})$")
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")

S = {"type": "string"}
NS = {"type": ["string", "null"]}
NI = {"type": ["integer", "null"]}
SCHEMA = {
    "type": "object", "required": ["items", "moves", "conditions", "preferences", "requests", "missing", "trip"],
    "properties": {
        "items": {"type": "array", "items": {"type": "object",
                  "required": ["place_quote", "day", "date", "date_quote", "start", "end", "time_quote", "kind"],
                  "properties": {"place_quote": S, "day": NI, "date": NS, "date_quote": NS, "start": NS, "end": NS,
                                 "time_quote": NS, "kind": {"enum": ["activity", "dining", "lodging"]}}}},
        "moves": {"type": "array", "items": {"type": "object", "required": ["mode", "scope", "day", "from_quote", "to_quote", "quote"],
                  "properties": {"mode": {"enum": MODES}, "scope": {"enum": ["segment", "day", "all"]}, "day": NI,
                                 "from_quote": NS, "to_quote": NS, "quote": S}}},
        "conditions": {"type": "array", "items": {"type": "object", "required": ["code", "quote"], "properties": {"code": S, "quote": S}}},
        "preferences": {"type": "array", "items": {"type": "object", "required": ["code", "quote"],
                        "properties": {"code": {"enum": PREFS}, "quote": S}}},
        "requests": {"type": "array", "items": {"enum": REQUESTS}},
        "missing": {"type": "array", "items": {"enum": MISSING}},
        "trip": {"type": "object", "required": ["party_size", "days", "nights"],
                 "properties": {"party_size": NI, "days": NI, "nights": NI}}}}

SYSTEM = """You read a traveller's message (usually Korean; it may be a list, a paragraph, CSV, JSON, a pasted table or several chat messages) and output the plan to show on a confirmation screen, as JSON matching the schema.

Today is {today} ({weekday}). Resolve relative dates from today: 내일/낼 = today+1, 모레/내일모레 = today+2, 토욜/토요일 = the coming Saturday, 담주 월욜/다음주 월요일 = Monday of next week, 다음 달 5일 = the 5th of next month. A year-less date means the next such date from today.

Rules
- Apply corrections made later in the message ("A 말고 B", "순서 바꿀래", "빼고", "날짜 틀렸다"): output only the final plan.
- items: one per place/activity/meal stop the traveller will do. place_quote = the place words copied EXACTLY from the message (keep typos, spacing and language; no times, verbs or particles). Never make items from transport lines (택시로 이동), conditions, headers, or places named only inside a question.
- day: 1-based day number. date: YYYY-MM-DD or null. date_quote: the exact text that states that date (a header line is fine) or null.
- start/end: 24h HH:MM or null. Use PM when the context means it (점심 1시 → 13:00, 저녁 6시 → 18:00, 3시 체크인 → 15:00, afternoon 2~6시 → 14:00~18:00). time_quote: the exact clock text, e.g. "1시쯤". 오전/점심/저녁 without a clock time → null.
- kind: dining for meals, cafes, food, drinks; lodging for hotel stay/check-in/check-out; otherwise activity.
- moves: transport the traveller states. scope "all" = whole trip (다 지하철로, 웬만하면 택시), "day" = one day (set day), "segment" = between two stops (from_quote/to_quote = their place_quote, null if unknown). quote = exact transport words.
- conditions: code if_rain_indoor (비 오면 실내), if_rain_skip (비 오면 빼기), finish_by:HH:MM (몇 시까지 끝/돌아가기), start_after:HH:MM; quote = exact words.
- preferences: only codes from the schema list; quote = exact words.
- requests: register (gives stops to put on the schedule), plan_ask (asks us to plan, fill, or recommend), question (asks something), correction (changes something said earlier in the message).
- missing: facts only the traveller knows that we need: first_day_date (no date, or vague like 10월 말/주말), lodging_name (hotel/숙소 without a name), booked_place_name (says it is booked but gives no name).
- trip: party_size, days, nights only if stated.

Example
Message: 모레 11시 낙성대공원 산책하고 택시로 샤로수길 가서 1시에 점심, 비 오면 공원은 빼 줘. 저녁은 알아서 추천해 줘
Output: {{"items":[{{"place_quote":"낙성대공원","day":1,"date":"{ex_date}","date_quote":"모레","start":"11:00","end":null,"time_quote":"11시","kind":"activity"}},{{"place_quote":"샤로수길","day":1,"date":"{ex_date}","date_quote":"모레","start":"13:00","end":null,"time_quote":"1시","kind":"dining"}}],"moves":[{{"mode":"taxi","scope":"segment","day":1,"from_quote":"낙성대공원","to_quote":"샤로수길","quote":"택시로"}}],"conditions":[{{"code":"if_rain_skip","quote":"비 오면 공원은 빼 줘"}}],"preferences":[],"requests":["register","plan_ask"],"missing":[],"trip":{{"party_size":null,"days":null,"nights":null}}}}"""


def system_for(today: date) -> str:
    from datetime import timedelta

    return SYSTEM.format(today=today.isoformat(), weekday=WEEKDAY[today.weekday()] + "요일", ex_date=(today + timedelta(days=2)).isoformat())


#: `[2026-10-16]` 지시문 2판 — 1판은 예가 「성향 없음」 하나뿐이라 모델이 성향을 거의 안 냈다(가르친 E4B 69건 중 1건 · Winnow 0건).
#: 성향 말마다 뜻풀이를 붙이고 성향 · 조건 · 빠진 값이 든 예를 하나 더 둔다. ★뜻풀이 · 예의 문장은 시험지 문장과 겹치지 않게 다른 말로 썼다
#: (같은 사람이 시험지 정답 어휘를 정했으니 어휘는 맞춰져 있다 — 보고서에 적는다).
PREF_GLOSS = """- preferences meanings (use only when the traveller says it about themselves): prefer_taxi = wants to ride taxis; avoid_taxi = does not want taxis;
  avoid_walking = walking is hard or unwanted (오래 걷기 힘들다, 다리가 아프다); prefer_walking = wants to go on foot; prefer_transit = wants subway/bus;
  kid_friendly = travelling with children; elderly_friendly = travelling with older people or someone with limited mobility;
  late_start = wants to start the day late; slow_pace = wants a relaxed, light schedule (느긋하게, 몇 군데만); avoid_stairs = wants to avoid stairs/slopes;
  food_focus = wants the trip built around good food; night_view = wants night views; nice_restaurants = wants restaurants with atmosphere."""

EXAMPLE2 = """
Example 2
Message: 어르신 모시고 다음 주 금요일 하루 다녀요. 오래 걷기 힘드셔서 이동은 택시로 하고 저녁 7시 전에는 숙소 들어가려고요. 점심은 을지로 노포, 오후엔 서울숲인데 비 오면 실내로 바꿔 주세요.
Output: {{"items":[{{"place_quote":"을지로 노포","day":1,"date":"{ex_fri}","date_quote":"다음 주 금요일","start":null,"end":null,"time_quote":null,"kind":"dining"}},{{"place_quote":"서울숲","day":1,"date":"{ex_fri}","date_quote":"다음 주 금요일","start":null,"end":null,"time_quote":null,"kind":"activity"}}],"moves":[{{"mode":"taxi","scope":"all","day":null,"from_quote":null,"to_quote":null,"quote":"이동은 택시로"}}],"conditions":[{{"code":"finish_by:19:00","quote":"저녁 7시 전에는 숙소 들어가려고요"}},{{"code":"if_rain_indoor","quote":"비 오면 실내로 바꿔 주세요"}}],"preferences":[{{"code":"elderly_friendly","quote":"어르신 모시고"}},{{"code":"avoid_walking","quote":"오래 걷기 힘드셔서"}},{{"code":"prefer_taxi","quote":"이동은 택시로"}}],"requests":["register"],"missing":["lodging_name"],"trip":{{"party_size":null,"days":1,"nights":null}}}}"""


def system_for_v2(today: date) -> str:
    from datetime import timedelta

    next_monday = today + timedelta(days=7 - today.weekday())
    base = SYSTEM.replace("- preferences: only codes from the schema list; quote = exact words.",
                          "- preferences: only codes from the schema list; quote = exact words.\n" + PREF_GLOSS)
    return (base + EXAMPLE2).format(today=today.isoformat(), weekday=WEEKDAY[today.weekday()] + "요일",
                                    ex_date=(today + timedelta(days=2)).isoformat(), ex_fri=(next_monday + timedelta(days=4)).isoformat())


class OllamaBackend:
    def __init__(self, base: str, model: str, num_ctx: int) -> None:
        self.base, self.model, self.num_ctx = base.rstrip("/"), model, num_ctx

    def ask(self, system: str, user: str) -> str:
        payload = {"model": self.model, "stream": False, "think": False, "format": SCHEMA, "keep_alive": "30m",
                   "options": {"temperature": 0, "num_ctx": self.num_ctx, "num_predict": 2048},
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        r = httpx.post(f"{self.base}/api/chat", json=payload, timeout=300)
        r.raise_for_status()
        return r.json()["message"]["content"]


class LlamaBackend:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def ask(self, system: str, user: str) -> str:
        payload = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                   "temperature": 0, "max_tokens": 2048, "chat_template_kwargs": {"enable_thinking": False},
                   "response_format": {"type": "json_schema", "json_schema": {"name": "plan", "schema": SCHEMA}}}
        r = httpx.post(f"{self.base}/v1/chat/completions", json=payload, timeout=300)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class CodexBackend:
    """Codex CLI(구독)로 문제마다 한 번 — 저장소의 `program/scripts/eval_kit/codex_percall.call`(JSON 스키마 강제 · 읽기 전용 · 대화 저장 안 함)을 쓴다.
    ★CLI 한 번이 도구를 갖춘 에이전트 세션 하나라 시간은 API 직접 호출보다 길다 — 「CLI 기준」으로만 읽는다. 추론 강도는 CLI 전역 설정값."""

    def __init__(self, model: str, helper: str) -> None:
        import sys as _sys

        _sys.path.insert(0, helper)
        from codex_percall import call  # noqa: E402

        self.model, self._call = model, call

    def ask(self, system: str, user: str) -> str:
        prompt = f"{system}\n\n---\nMessage:\n{user}\n\n위 지시대로 JSON 한 개로만 답하라. 파일을 만들거나 명령을 실행하지 마라."
        value, _seconds, err = self._call(self.model, prompt, SCHEMA, timeout=300, retries=1)
        if value is None:
            raise RuntimeError(f"codex 호출 실패: {err}")
        return json.dumps(value, ensure_ascii=False)


def ground(raw: dict[str, Any], text: str) -> tuple[dict[str, Any], dict[str, int]]:
    """모델 답 → 중립 예측. ★원문에 글자 그대로 없는 조각은 버린다(그 값을 쓰지 않는다). 버린 수를 센다."""
    dropped = {"item": 0, "time": 0, "date": 0, "move": 0, "move_end": 0, "condition": 0, "preference": 0}

    def here(q: Any) -> bool:
        return isinstance(q, str) and bool(q.strip()) and q in text

    items = []
    for it in raw.get("items") or []:
        if not here(it.get("place_quote")):
            dropped["item"] += 1
            continue
        start, end = it.get("start"), it.get("end")
        if (start or end) and not here(it.get("time_quote")):
            dropped["time"] += 1
            start = end = None
        start = start if isinstance(start, str) and HHMM.match(start) else None
        end = end if isinstance(end, str) and HHMM.match(end) else None
        when = it.get("date")
        if when and not (here(it.get("date_quote")) and isinstance(when, str) and ISO.match(when)):
            dropped["date"] += 1
            when = None
        items.append({"title": it["place_quote"], "day": it.get("day"), "date": when, "start": start, "end": end,
                      "kind": it.get("kind") or "activity", "place_name": None})
    moves = []
    for m in raw.get("moves") or []:
        if not here(m.get("quote")):
            dropped["move"] += 1
            continue
        ends = {}
        for key in ("from_quote", "to_quote"):
            value = m.get(key)
            if value and not here(value):
                dropped["move_end"] += 1
                value = None
            ends[key] = value
        moves.append({"mode": m.get("mode"), "scope": m.get("scope"), "day": m.get("day"), "from": ends["from_quote"], "to": ends["to_quote"]})
    conditions = []
    for c in raw.get("conditions") or []:
        if here(c.get("quote")) and COND.match(str(c.get("code") or "")):
            conditions.append({"code": c["code"], "target": None})
        else:
            dropped["condition"] += 1
    preferences = []
    for p in raw.get("preferences") or []:
        if here(p.get("quote")) and p.get("code") in PREFS:
            preferences.append(p["code"])
        else:
            dropped["preference"] += 1
    trip = {k: v for k, v in (raw.get("trip") or {}).items() if k in ("party_size", "days", "nights") and isinstance(v, int)}
    return ({"items": items, "moves": moves, "conditions": conditions, "preferences": sorted(set(preferences)),
             "requests": sorted({r for r in raw.get("requests") or [] if r in REQUESTS}),
             "missing": sorted({m for m in raw.get("missing") or [] if m in MISSING}), "trip": trip}, dropped)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["ollama", "llama", "codex"], required=True)
    parser.add_argument("--base", default="")
    parser.add_argument("--codex-helper", default=str(HERE.parents[2] / "program" / "scripts" / "eval_kit"),
                        help="codex_percall.py 가 있는 폴더(저장소 루트의 program/scripts/eval_kit)")
    parser.add_argument("--model", default="tripilot-pointer:e4b-ft")
    parser.add_argument("--label", default="")
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--prompt", choices=["v1", "v2"], default="v1", help="v2 = 성향 뜻풀이 + 성향 · 조건이 든 예 하나 더")
    parser.add_argument("--out", required=True)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args(argv)

    from .report import render
    from .score import score_all

    cases = [json.loads(x) for x in (HERE / "cases.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    if args.only:
        cases = [c for c in cases if c["case_id"] in set(args.only)]
    backend = (OllamaBackend(args.base, args.model, args.num_ctx) if args.backend == "ollama" else
               CodexBackend(args.model, args.codex_helper) if args.backend == "codex" else LlamaBackend(args.base))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = {"started_kst": datetime.now(KST).isoformat(timespec="seconds"), "backend": args.backend,
            "model": args.model if args.backend in ("ollama", "codex") else args.label, "num_ctx": args.num_ctx, "prompt": args.prompt}
    preds: dict[str, dict[str, Any]] = {}
    drops_total: dict[str, int] = {}
    with (out / "raw.jsonl").open("w", encoding="utf-8") as raw_file:
        for case in cases:
            today = date.fromisoformat(case["today"])
            started = time.perf_counter()
            error, raw, answer = None, {}, ""
            try:
                answer = backend.ask((system_for_v2 if args.prompt == "v2" else system_for)(today), case["source_text"])
                raw = json.loads(answer)
                if not isinstance(raw, dict):
                    raise ValueError("JSON 객체가 아니다")
            except Exception as exc:          # noqa: BLE001 — 읽기 실패는 엄격 계수로 센다
                error = f"{type(exc).__name__}: {exc}"[:300]
            seconds = time.perf_counter() - started
            pred, drops = ground(raw, case["source_text"]) if not error else ({}, {})
            for k, v in drops.items():
                drops_total[k] = drops_total.get(k, 0) + v
            preds[case["case_id"]] = {**pred, "case_id": case["case_id"], "error": error, "seconds": round(seconds, 2),
                                      "model_calls": 1, "model_seconds": round(seconds, 2), "dropped": drops}
            raw_file.write(json.dumps({"case_id": case["case_id"], "answer": answer, "error": error}, ensure_ascii=False) + "\n")
            raw_file.flush()
            print(f"{case['case_id']} {seconds:5.1f}s 항목 {len(pred.get('items') or [])} 버림 {sum(drops.values())}" + (f" 오류 {error}" if error else ""), flush=True)
    meta.update({"finished_kst": datetime.now(KST).isoformat(timespec="seconds"), "dropped_not_verbatim": drops_total})
    (out / "predictions.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in preds.values()) + "\n", encoding="utf-8")
    result = score_all(cases, preds)
    result["meta"] = meta
    (out / "scores.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "scores.md").write_text(render(result, cases, preds) + f"\n원문에 없어 버린 조각: {json.dumps(drops_total, ensure_ascii=False)}\n", encoding="utf-8")
    print((out / "scores.md").read_text(encoding="utf-8")[:2500])
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.exit(main())
