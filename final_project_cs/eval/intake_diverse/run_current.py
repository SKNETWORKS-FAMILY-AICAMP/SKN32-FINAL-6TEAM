# -*- coding: utf-8 -*-
"""지금 구조 재기 — `components/intake/pipeline.read_source` 전체 흐름(규칙 → 남은 줄 모델 → 날짜 → 장소)을 시험지에 돌리고 채점한다.

    python -m eval.intake_diverse.run_current --ollama <x600 과 같은 구성의 Ollama 주소> --model tripilot-pointer:e4b-ft --num-ctx 8192 \
        --kakao-key-file ../.env.apikeys --out <결과 폴더>
    python -m eval.intake_diverse.run_current --oracle --out <폴더>      # 채점기 점검: 정답을 그대로 예측으로 넣으면 모든 칸이 100% 여야 한다
    python -m eval.intake_diverse.run_current --no-model --out <폴더>    # 모델 없이(규칙만)

★x600 서버와 같게 둔 것: 남은 줄 모델(`OllamaChat` · think=false · 온도 0 · JSON · num_ctx 8192 · 같은 모델 파일), 카카오 장소 찾기.
★x600 서버와 다른 것(DB 를 쓰지 않는다): 관광공사 조회(`tour`) · 우리 장소 목록(`our_places`) · 지명 사전(`areas`) · 식당 원장(`dining`) · 고객 별칭 없음.
  그래서 「찾은 장소」 칸은 x600 서버보다 낮게 나올 수 있다. 읽기 칸(항목 · 시각 · 날짜 · 변조 · 요청)은 이것들과 상관없다.
★여러 메시지는 줄바꿈으로 이어 한 접수로 넣는다(지금 접수 입구가 글 하나를 받기 때문).
★카카오 호출은 이 실행 안에서만 세는 상한(`--kakao-cap`, 기본 2,000회)을 둔다 — 서버의 하루 예산 표(DB)를 쓰지 않으므로 대신 막는다.
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

HERE = Path(__file__).resolve().parent
KST = ZoneInfo("Asia/Seoul")
ITEM = re.compile(r"^items\[(\d+)\]\.(\w+)$")

_DUMMY_ENV = {   # 읽기 흐름은 DB · OpenAI 를 부르지 않는다 — 설정 객체가 만들어지게만 채운다(값이 이미 있으면 그대로)
    "ACOP_DATABASE_URL": "postgresql://eval@127.0.0.1:1/none", "ACOP_OPENAI_API_KEY": "sk-none", "ACOP_LLM_MODEL": "none",
    "ACOP_EMBEDDING_MODEL": "none", "ACOP_TENANT_ID": "eval", "ACOP_SECRET_KEY": "eval-secret-key-eval-secret-key-0000",
    "ACOP_COMPOSER_JWT_SECRET": "eval-jwt-secret-eval-jwt-secret-0000", "ACOP_COMPOSER_ISSUER_SECRET": "eval-iss-secret-eval-iss-secret-0000"}


class TimedChat:
    """모델 호출 시간 · 횟수를 센다. 겉모양(`json`)은 `OllamaChat` 그대로."""

    def __init__(self, inner: Any) -> None:
        self.inner, self.calls, self.seconds, self.log = inner, 0, 0.0, []

    def json(self, system: str, user: str) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            out = self.inner.json(system, user)
            self.log.append({"user": user, "answer": out})
            return out
        except Exception as exc:          # noqa: BLE001 — 기록만 하고 그대로 던진다(read_source 가 이 단계만 건너뛴다)
            self.log.append({"user": user, "error": f"{type(exc).__name__}: {exc}"[:300]})
            raise
        finally:
            self.calls += 1
            self.seconds += time.perf_counter() - started


class RunBudget:
    """카카오 호출 상한 — 이 실행 안에서만 센다(`CallBudget.try_reserve` 와 같은 겉모양)."""

    def __init__(self, cap: int) -> None:
        self.cap, self.used = cap, 0

    def try_reserve(self, meter: str) -> bool:
        if self.used >= self.cap:
            return False
        self.used += 1
        return True


def adapt(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """지금 구조의 값 줄(`intake_claims` 모양) → 채점기의 중립 모양."""
    items: dict[int, dict[str, Any]] = {}
    trip: dict[str, Any] = {}
    requests, missing, fields = set(), set(), set()
    for row in rows:
        field, value = str(row.get("field") or ""), row.get("value")
        m = ITEM.match(field)
        fields.add(re.sub(r"\[\d+\]", "[]", field))
        if m:
            item = items.setdefault(int(m.group(1)), {})
            key = m.group(2)
            if key == "title":
                item["title"] = value
            elif key == "starts_at":
                item["start"] = value
            elif key == "ends_at":
                item["end"] = value
            elif key == "date":
                item["date"] = value
            elif key == "kind":
                item["kind"] = value
            elif key == "place" and isinstance(value, dict):
                item["place_name"] = value.get("name")
                item.setdefault("place_kind", value.get("kind"))
        elif field in ("trip.party_size", "trip.days", "trip.nights"):
            trip[field.split(".")[1]] = value
        elif field == "trip.plan_request" and value:
            requests.add("plan_ask")
        elif field == "trip.ask_first_day" and value:
            missing.add("first_day_date")
    out_items = []
    for index in sorted(items):
        it = items[index]
        kind = it.get("kind") or (it.get("place_kind") if it.get("place_kind") in ("dining", "lodging") else None) or "activity"
        out_items.append({"title": it.get("title"), "date": it.get("date"), "start": it.get("start"), "end": it.get("end"),
                          "kind": kind, "place_name": it.get("place_name")})
    if any(i.get("title") for i in out_items):
        requests.add("register")
    return {"items": out_items, "moves": [], "conditions": [], "preferences": [], "requests": sorted(requests),
            "missing": sorted(missing), "trip": trip, "fields_seen": sorted(fields)}


def oracle(case: dict[str, Any]) -> dict[str, Any]:
    g = case["gold"]
    return {"items": [{"title": i["place"], "date": i["date"], "start": i["start"], "end": i["end"], "kind": i["kind"],
                       "place_name": (i["canon"] or [None])[0]} for i in g["items"]],
            "moves": g["moves"], "conditions": g["conditions"], "preferences": g["preferences"], "requests": g["requests"],
            "missing": g["missing"], "trip": g["trip"]}


def _now(case: dict[str, Any]) -> datetime:
    received = (case.get("provenance") or {}).get("first_received_kst")
    if received:
        return datetime.fromisoformat(received).replace(tzinfo=KST)
    return datetime.fromisoformat(case["today"] + "T10:00:00").replace(tzinfo=KST)


def _kakao_key(path: str | None) -> str:
    if os.environ.get("ACOP_KAKAO_REST_API_KEY"):
        return os.environ["ACOP_KAKAO_REST_API_KEY"]
    if not path:
        return ""
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("ACOP_KAKAO_REST_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--ollama", default="")
    parser.add_argument("--model", default="tripilot-pointer:e4b-ft")
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--kakao-key-file")
    parser.add_argument("--kakao-cap", type=int, default=2000)
    parser.add_argument("--no-model", action="store_true")
    parser.add_argument("--no-kakao", action="store_true")
    parser.add_argument("--oracle", action="store_true")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--rescore", action="store_true", help="모델을 다시 부르지 않고 --out 의 predictions.jsonl 을 다시 채점한다")
    args = parser.parse_args(argv)
    for key, value in _DUMMY_ENV.items():
        os.environ.setdefault(key, value)

    from .score import score_all

    cases = [json.loads(line) for line in (HERE / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.only:
        cases = [c for c in cases if c["case_id"] in set(args.only)]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    preds: dict[str, dict[str, Any]] = {}
    meta: dict[str, Any] = {"started_kst": datetime.now(KST).isoformat(timespec="seconds"), "args": {k: v for k, v in vars(args).items() if k != "kakao_key_file"}}

    if args.rescore:
        preds = {p["case_id"]: p for p in (json.loads(x) for x in (out / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if x.strip())}
        old = out / "scores.json"
        if old.exists():
            meta = json.loads(old.read_text(encoding="utf-8")).get("meta", meta)
        meta["rescored_kst"] = datetime.now(KST).isoformat(timespec="seconds")
    elif args.oracle:
        preds = {c["case_id"]: {**oracle(c), "case_id": c["case_id"], "error": None, "seconds": 0} for c in cases}
    else:
        from app.domains.travel_ops.components.intake.pipeline import read_source

        chat = None
        if not args.no_model:
            from app.infrastructure.ollama_chat import OllamaChat

            chat = TimedChat(OllamaChat(base_url=args.ollama, model=args.model, timeout=120.0, keep_alive="30m", num_ctx=args.num_ctx))
        kakao, budget = None, RunBudget(args.kakao_cap)
        key = "" if args.no_kakao else _kakao_key(args.kakao_key_file)
        if key:
            from app.domains.travel_ops.ports.data_sources.kakao_local import KakaoLocal

            kakao = KakaoLocal(api_key=key, budget=budget)
        meta.update({"model": None if chat is None else args.model, "num_ctx": args.num_ctx, "kakao": kakao is not None})
        with (out / "rows.jsonl").open("w", encoding="utf-8") as raw:
            for case in cases:
                before_calls, before_secs, before_kakao = (chat.calls, chat.seconds, budget.used) if chat else (0, 0.0, budget.used)
                started = time.perf_counter()
                error, rows = None, []
                try:
                    rows = read_source(case["source_text"], chat=chat, tour=None, kakao=kakao, our_places=[],
                                       today=date.fromisoformat(case["today"]), now=_now(case))
                except Exception as exc:              # noqa: BLE001 — 읽기 실패는 엄격 계수로 센다
                    error = f"{type(exc).__name__}: {exc}"[:300]
                seconds = time.perf_counter() - started
                pred = {**adapt(rows), "case_id": case["case_id"], "error": error, "seconds": round(seconds, 2),
                        "model_calls": (chat.calls - before_calls) if chat else 0,
                        "model_seconds": round((chat.seconds - before_secs), 2) if chat else 0.0,
                        "kakao_calls": budget.used - before_kakao}
                preds[case["case_id"]] = pred
                raw.write(json.dumps({"case_id": case["case_id"], "rows": rows, "error": error}, ensure_ascii=False, default=str) + "\n")
                raw.flush()
                print(f"{case['case_id']} {seconds:5.1f}s 모델 {pred['model_calls']}회 {pred['model_seconds']}s 카카오 {pred['kakao_calls']} "
                      f"항목 {len(pred['items'])}" + (f" 오류 {error}" if error else ""), flush=True)
        if chat is not None:
            (out / "model_log.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in chat.log) + "\n", encoding="utf-8")
        meta["kakao_calls"] = budget.used
    meta.setdefault("finished_kst", datetime.now(KST).isoformat(timespec="seconds"))
    (out / "predictions.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in preds.values()) + "\n", encoding="utf-8")
    result = score_all(cases, preds)
    result["meta"] = meta
    (out / "scores.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    from .report import render

    (out / "scores.md").write_text(render(result, cases, preds), encoding="utf-8")
    print((out / "scores.md").read_text(encoding="utf-8")[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
