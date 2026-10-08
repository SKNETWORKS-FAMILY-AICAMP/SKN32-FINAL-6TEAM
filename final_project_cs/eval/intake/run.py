# -*- coding: utf-8 -*-
"""계획 읽기 평가 실행기 — 설계서 §7 지표 여섯. (평가셋: `python -m eval.intake.build`)

    python -m eval.intake.run                     # 60건 전부 · 실제 받아쓰기(gemma)·모델·관광공사·카카오
    python -m eval.intake.run --only paste,xlsx   # 형식만 골라서

★실제 처리 흐름을 그대로 탄다 — `intake.sources.to_text` → `intake.pipeline.read_source` → `intake.assemble`.
  DB 에 접수 행을 만들지 않는다(조립에 필요한 원본 모양만 만든다). 우리 장소 표·별칭은 `demo` 테넌트의 공용 행을 읽는다.
★관광공사·카카오 응답은 **이 실행 안에서만** 메모리에 담는다(같은 이름을 두 번 부르지 않게 — 관광공사 몰림 한도).
  파일로 남기지 않는다(약관, 설계서 §4-5·§4-6).
★지표(분자/분모)
    항목 재현율     찾은 정답 항목 / 정답 항목
    값 변조         원문(사람이 쓴 글)에 글자 그대로 없는 제목·예약번호 / 뽑은 제목·예약번호
                    ★`[2026-10-06 사용자 지시]` 셋으로 나눈다 — 받아쓰기가 두 번 다르게 읽어 **「확인 필요」로 표시된 변조**(`tampering_flagged_by_check`) ·
                    다른 까닭으로 이미 확인 필요였던 변조(`tampering_flagged_other`) · **표시 없이 새어 나간 변조**(`tampering_leaked` — 고객이 확정 값으로 보는 것).
                    전체 변조(`tampering`)는 전과 같은 정의라 이전 실행(12/350)과 견줄 수 있다. 표시한 것 가운데 변조가 아니었던 것도 센다(`differs_precision`).
    시각 정확도     맞은 시각 / 원문에 시각이 있는 정답 항목
    장소 1위 정확도 맞게 고른 장소 / 정답 장소가 있는 짝지은 항목
    근거 없는 값    근거가 빈 값 / 뽑은 값 전체
    처리 시간       받아쓰기한 원본의 초(p50 · p95)
★짝짓기: 같은 날짜 안에서 제목이 정답 제목을 포함하거나 정답 제목에 포함되는 것(정규화 비교). 못 짝지으면 재현 실패.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import statistics
import time
import uuid

from .build import CASES, TODAY

REPORTS = Path(__file__).resolve().parents[1] / "reports"


class Memo:
    """조회 결과를 이 실행 안에서만 담는다. `misses` 는 원래 어댑터 것을 그대로 보인다(막힘 판정에 쓴다)."""

    def __init__(self, inner, method: str) -> None:
        self.inner, self.method, self.store, self.calls = inner, method, {}, 0

    @property
    def misses(self):
        return getattr(self.inner, "misses", {})

    def __getattr__(self, name):
        if name in ("find", "search"):
            def call(*args, **kwargs):
                key = (name, args, tuple(sorted(kwargs.items())))
                if key not in self.store:
                    self.calls += 1
                    self.store[key] = getattr(self.inner, name)(*args, **kwargs)
                return self.store[key]
            return call
        return getattr(self.inner, name)


def _norm(text: str | None) -> str:
    from app.domains.travel_ops.components.intake.places import normalize

    return normalize(text or "")


def run(only: set[str] | None = None) -> dict:
    from app.core.settings import get_settings
    from app.infrastructure.db.session import get_connection
    from app.infrastructure.ollama_chat import from_settings
    from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget, kakao_caps
    from app.domains.travel_ops.ports.data_sources.kakao_local import KakaoLocal
    from app.domains.travel_ops.components.intake.assemble import assemble, collect
    from app.domains.travel_ops.components.intake.pipeline import _our_places, differs_by_line, load_aliases, read_source
    from app.domains.travel_ops.components.intake.sources import to_text

    settings = get_settings()
    chat = from_settings(settings)
    place_source = build_travel_sources(settings).place
    # ★평가 실행 한 번이 관광공사를 수십 번 부른다 — 몰림 허용 30 으로는 뒤쪽이 「막힘」이 된다(첫 실행에서 봤다).
    #   이 실행에서만 몰림 200 · 하루 합계는 설정값(`rate_tour_api_per_day`) 그대로 지킨다(`interval_for`)
    from app.domains.travel_ops.ports.data_sources.ratelimit import RateLimiter, interval_for
    per_day = settings.rate_tour_api_per_day
    place_source._limiter = RateLimiter(intervals={"tour_api": interval_for(per_day, burst=200)},
                                        bursts={"tour_api": 200})
    tour = Memo(place_source, "find")
    kakao = Memo(KakaoLocal(api_key=settings.kakao_rest_api_key,
                            budget=CallBudget(connection_factory=get_connection, caps=kakao_caps())), "search")
    with get_connection() as conn:
        # ★고객 번호 없이 부른다 — 기본값(seed) 별칭만 읽는다(고객이 고친 별칭은 그 고객의 접수에만 쓰는 규칙, 마이그레이션 038). 이 줄이 옛 두 인자 모양이라 2026-09-30 뒤로 평가 실행이 TypeError 로 죽어 있었다
        ours, aliases = _our_places(conn, "demo"), load_aliases(conn, "demo", None)

    rows_out, seconds, leaked = [], [], []
    totals = dict(gold=0, found=0, extracted=0, tampered=0, timed=0, time_ok=0, placed=0, place_ok=0,
                  values=0, no_evidence=0, place_blocked=0,
                  tampered_flagged_by_check=0, tampered_flagged_other=0, tampered_leaked=0,
                  flagged_by_check=0, differ_lines=0, transcribed_lines=0)
    for folder in sorted(p for p in CASES.iterdir() if p.is_dir()):
        gold = json.loads((folder / "gold.json").read_text(encoding="utf-8"))
        if only and gold["format"] not in only:
            continue
        started = time.perf_counter()
        sources, claims, errors, transcripts = [], [], [], []
        for position, source in enumerate(gold["inputs"]):
            sid = f"s{position}"
            unlike = []
            try:
                if source["kind"] == "text":
                    text, took = source["text"], 0.0
                else:
                    got = to_text((folder / source["name"]).read_bytes(), filename=source["name"], see=chat.see)
                    text, took, unlike = got.text, got.seconds, got.differs
                    if got.transcribed_pages:
                        seconds.append(took)
                        totals["differ_lines"] += len(unlike)
                        totals["transcribed_lines"] += len([ln for ln in text.splitlines() if ln.strip()])
                        transcripts.append({"source": sid, "text": text, "differs": unlike, "missing": got.missing})
            except Exception as exc:                  # noqa: BLE001 — 실패는 세어 남긴다(조용한 스킵 금지)
                errors.append(f"{sid}: {type(exc).__name__}: {exc}"[:200])
                continue
            sources.append({"source_id": sid, "position": position, "transcript": text})
            for row in read_source(text, chat=chat, tour=tour, kakao=kakao, our_places=ours, today=TODAY,
                                   aliases=aliases, differs=differs_by_line(unlike)):
                claims.append({"source_id": sid, **row})
        built = assemble(intake_id="eval", revision=1, sources=sources, claims=claims)
        predicted = built.body["items"]
        places = {p["key"]: p for p in built.body["places"]}
        original = "\n".join(gold["lines"])
        # 변조 — 뽑은 제목·예약번호가 사람이 쓴 원문에 글자 그대로 있나. ★세 갈래로 나눈다(위 머리말): 받아쓰기 비교가 표시한 것 · 다른 까닭으로 확인 필요였던 것 · 표시 없이 새어 나간 것
        def tally(value, claim):
            totals["extracted"] += 1
            review = bool(claim and claim.get("needs_review"))
            by_check = bool(claim and (claim.get("evidence") or {}).get("transcription_differs"))
            totals["flagged_by_check"] += by_check
            if value not in original:
                totals["tampered"] += 1
                if by_check:
                    totals["tampered_flagged_by_check"] += 1
                elif review:
                    totals["tampered_flagged_other"] += 1
                else:
                    totals["tampered_leaked"] += 1
                    leaked.append({"case": gold["case_id"], "value": value})

        for row in collect(sources=sources, claims=claims).rows:
            if not (row["date"] and row["start"]):
                continue                                  # 조립이 일정으로 싣지 않는 줄(날짜·시각 없음) — 변조 분모에 안 넣는다(전과 같다)
            tally(row["title"] or "(제목 없음)", (row["claims"].get("title") or {}))
            if row["booking_no"]:
                tally(row["booking_no"], (row["claims"].get("booking_no") or {}))
        # 근거 — 값마다 근거가 붙었나
        for claim in claims:
            totals["values"] += 1
            if not claim.get("evidence"):
                totals["no_evidence"] += 1
            if claim["field"].endswith(".place") and (claim.get("evidence") or {}).get("blocked"):
                totals["place_blocked"] += 1          # 조회가 막혀 못 정한 장소 — 「없음」과 따로 센다
        # 짝짓기
        free = list(range(len(predicted)))
        case_rows = []
        for want in gold["items"]:
            totals["gold"] += 1
            key = _norm(want["title"])
            match = next((i for i in free if predicted[i]["starts_at"][:10] == want["date"]
                          and (key in _norm(predicted[i]["title"]) or _norm(predicted[i]["title"]) in key)
                          and _norm(predicted[i]["title"])), None)
            if match is None and want["place"]:
                # ★제목이 오독돼도(받아쓰기) 같은 날·같은 시각에 **정답 장소를 맞게 골랐으면** 찾은 항목이다.
                #   제목이 원문과 다른 것은 「값 변조」가 따로 센다 — 오독을 숨기지 않는다
                match = next((i for i in free if predicted[i]["starts_at"][:10] == want["date"]
                              and (want["start"] is None or predicted[i]["starts_at"][11:16] == want["start"])
                              and predicted[i]["place"]
                              and _norm(want["place"]) in _norm(places.get(predicted[i]["place"], {}).get("name"))),
                             None)
            got = predicted[match] if match is not None else None
            if match is not None:
                free.remove(match)
                totals["found"] += 1
            time_ok = place_ok = None
            if got and want["start"]:
                totals["timed"] += 1
                time_ok = got["starts_at"][11:16] == want["start"]
                totals["time_ok"] += time_ok
            if got and want["place"]:
                totals["placed"] += 1
                name = places.get(got["place"], {}).get("name") if got["place"] else None
                place_ok = bool(name) and (_norm(name) == _norm(want["place"]) or _norm(want["place"]) in _norm(name))
                totals["place_ok"] += place_ok
            case_rows.append({"want": want, "found": got is not None,
                              "got": {"title": got["title"], "start": got["starts_at"][11:16],
                                      "place": places.get(got["place"], {}).get("name") if got and got["place"] else None}
                              if got else None, "time_ok": time_ok, "place_ok": place_ok})
        rows_out.append({"case": gold["case_id"], "format": gold["format"], "defect": gold["defect"],
                         "seconds": round(time.perf_counter() - started, 1), "errors": errors,
                         "problems": [p.code for p in built.problems], "items": case_rows, "transcripts": transcripts})
        print(f"{gold['case_id']:12} found {sum(r['found'] for r in case_rows)}/{len(case_rows)} "
              f"{'ERR ' + errors[0][:60] if errors else ''}", flush=True)

    def pct(a, b):
        return f"{a}/{b} = {a / b:.1%}" if b else f"{a}/0"
    q = sorted(seconds)
    summary = {
        "run_id": uuid.uuid4().hex[:8], "at": datetime.now().isoformat(timespec="seconds"),
        "model": settings.ollama_model, "today": TODAY.isoformat(), "synthetic": True,
        "cases": len(rows_out), "item_recall": pct(totals["found"], totals["gold"]),
        "tampering": pct(totals["tampered"], totals["extracted"]),
        "tampering_flagged_by_check": pct(totals["tampered_flagged_by_check"], totals["extracted"]),
        "tampering_flagged_other": pct(totals["tampered_flagged_other"], totals["extracted"]),
        "tampering_leaked": pct(totals["tampered_leaked"], totals["extracted"]),
        "differs_precision": pct(totals["tampered_flagged_by_check"], totals["flagged_by_check"]),
        "differ_lines": pct(totals["differ_lines"], totals["transcribed_lines"]),
        "leaked": leaked,
        "time_accuracy": pct(totals["time_ok"], totals["timed"]),
        "place_top1": pct(totals["place_ok"], totals["placed"]),
        "no_evidence": pct(totals["no_evidence"], totals["values"]),
        "transcribe_seconds": {"n": len(q), "p50": round(statistics.median(q), 1) if q else None,
                               "p95": round(q[max(0, int(len(q) * 0.95) - 1)], 1) if q else None},
        "calls": {"tour_api": tour.calls, "kakao": kakao.calls},
        "totals": totals,
    }
    by_format = {}
    for row in rows_out:
        f = by_format.setdefault(row["format"], {"gold": 0, "found": 0, "place": 0, "place_ok": 0})
        for it in row["items"]:
            f["gold"] += 1
            f["found"] += it["found"]
            if it["place_ok"] is not None:
                f["place"] += 1
                f["place_ok"] += it["place_ok"]
    summary["by_format"] = {k: {"recall": pct(v["found"], v["gold"]), "place_top1": pct(v["place_ok"], v["place"])}
                            for k, v in by_format.items()}
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"intake_eval_{summary['run_id']}.json"
    out.write_text(json.dumps({"summary": summary, "cases": rows_out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("report:", out)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    run({s for s in args.only.split(",") if s} or None)
