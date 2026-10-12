# -*- coding: utf-8 -*-
"""activity_total_data.csv 의 `indoor_outdoor` 칸을 LLM 으로 판정해 채운다 — 실내 · 실외 · 복합 · 모름.

사용(OpenAI 키를 가진 사람이 실행한다. 최종 실행 위치: final_project_cs):
    python -m app.domains.travel_ops.instances.activity.data_processing.fill_indoor_outdoor --limit 40   # 시험
    python -m app.domains.travel_ops.instances.activity.data_processing.fill_indoor_outdoor              # 전체
    # 실패한 묶음만 다시 — 이번 프롬프트 버전으로 아직 판정하지 않은 행만, 작은 묶음으로
    python -m app.domains.travel_ops.instances.activity.data_processing.fill_indoor_outdoor --pending --batch 5

★`[2026-10-10 사용자]` 관광공사 분류 코드 규칙(`csv_places.weather_sensitive_from_lclssystm2`)을 **쓰지 않는다.**
  모델에는 장소 이름 · 주소 · 개요(overview)만 준다. 개요가 빈 행은 이름과 모델의 기본 지식으로 판정한다.
★멘토 피드백(10-08) — 실내외는 처음 한 번만 LLM 으로 판정해 적재하고 그 뒤로는 저장된 값을 쓴다. 이 스크립트가 그 적재다.
★출처 칸 `indoor_outdoor_source` 에 모델 · 프롬프트 버전 · 판정 날짜를 남긴다(`llm:<모델>:<프롬프트>:<날짜>`).
  `human:` 으로 시작하는 값(사람이 고친 것)은 덮어쓰지 않는다. 다른 값은 다시 판정한다.
★`[2026-10-10 사용자]` **실내 · 실외는 여행자 입장에서 판단한다** — 건물이 있느냐가 아니라 여행자가 실제로 시간을 보내는 곳이
  실내인지 실외인지. (전통 사찰 · 궁궐 · 유적 · 공원 = 실외, 다층 건물 안 법당 = 실내.)
★값은 `indoor` · `outdoor` · `mixed`(실내와 실외가 모두 포함된 곳 — `[2026-10-10 사용자]` 「복합」) · 빈칸(모름)이다.
  모르면 모른다 — `unknown` 은 빈칸으로 남긴다. 추정으로 채우지 않는다.
★20곳씩 묶어 한 번에 묻는다. 돌아온 id 묶음이 보낸 것과 다르면 그 묶음은 버리고 다시 묻는다(최대 3회).
  끝내 못 받은 묶음은 그대로 두고 센다 — 조용히 넘기지 않는다. 받은 것까지는 CSV 에 반영한다.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

CSV_PATH = Path(__file__).resolve().parent / "activity_total_data.csv"
PROMPT_VERSION = "indoor_outdoor.v3"   # v2: 복합(mixed) 추가 · v3: 여행자 입장에서 판단
BATCH = 20
WORKERS = 3
RETRIES = 3

PROMPT = """너는 서울의 여행 장소가 실내인지 실외인지 판정한다. 목적: 비 · 바람 · 폭염 · 미세먼지 같은 날씨가 이 장소에서의 활동에 영향을 주는가.

★여행자 입장에서 판단한다. 건물이 있느냐가 아니라, 여행자가 그곳을 찾아가 실제로 시간을 보내는 곳(둘러보기 · 관람 · 체험 · 걷기)이 주로 실내인지 실외인지를 본다.
  예: 전통 사찰은 법당이 건물이어도 여행자는 경내를 걸으며 둘러보므로 `outdoor`. 궁궐 · 유적 · 공원도 `outdoor`. 여러 층 건물 안에 법당이 있는 도심 사찰은 `indoor`.

입력은 JSON 목록이다. 항목마다 `id`(장소 식별자) · `title`(장소 이름) · `address`(주소) · `overview`(관광공사 개요, 빈 글자일 수 있다).

항목마다 하나를 고른다.
- `indoor`: 활동이 주로 건물 안에서 이루어진다(매장 · 백화점 · 박물관 전시실 · 공연장 · 실내 체험관 · 찜질방 등).
- `outdoor`: 활동이 주로 바깥에서 이루어진다(공원 · 산 · 궁궐 · 거리 · 시장 골목 · 야외 체험 · 야외 축제 등).
- `mixed`: 실내 공간과 실외 공간이 모두 활동의 중요한 부분이다(실내 전시관과 야외 정원이 함께 있는 박물관 · 실내외 놀이시설이 있는 테마파크 · 실내외에서 함께 열리는 행사 등).
- `unknown`: 개요와 네가 아는 지식으로도 실내 · 실외 · 복합 중 무엇인지 정할 수 없다.

규칙:
- 개요가 있으면 개요를 먼저 본다. 개요가 비었으면 장소 이름과 네가 그 장소에 대해 아는 지식으로 판정한다.
- 체인 매장(올리브영 · 다이소 · 무신사 등)은 매장이므로 `indoor` 다.
- 확신이 없으면 `unknown` 이다. 그럴듯한 추정으로 채우지 않는다.
- 입력의 모든 `id` 에 대해 정확히 하나씩, 같은 `id` 로 답한다. `reason` 은 한국어 한 구절."""

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {"id": {"type": "string"},
                       "verdict": {"type": "string", "enum": ["indoor", "outdoor", "mixed", "unknown"]},
                       "reason": {"type": "string"}},
        "required": ["id", "verdict", "reason"]}}},
    "required": ["items"],
}


def _row_id(index: int, row: dict[str, str]) -> str:
    """contentid 가 겹치거나 빈 행이 있어도 묶음 안에서 가를 수 있게 줄 번호를 붙인다."""
    return f"{index}:{(row.get('contentid') or '').strip()}"


def _ask(client: Any, model: str, batch: list[tuple[str, dict[str, str]]]) -> dict[str, str]:
    items = [{"id": rid, "title": r.get("title", ""), "address": r.get("addr1", ""),
              "overview": (r.get("overview") or "")[:1200]} for rid, r in batch]
    wanted = {rid for rid, _ in batch}
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = client.responses.create(
                model=model, instructions=PROMPT, input=json.dumps(items, ensure_ascii=False),
                text={"format": {"type": "json_schema", "name": "indoor_outdoor", "strict": True, "schema": SCHEMA}})
            got = {it["id"]: it["verdict"] for it in json.loads(response.output_text)["items"]}
            if set(got) != wanted:
                raise ValueError(f"id 불일치 — 보냄 {len(wanted)} · 받음 {len(got)} · 겹침 {len(wanted & set(got))}")
            return got
        except Exception as exc:  # noqa: BLE001 — 다시 묻고, 끝내 실패하면 위로 올려 센다
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"묶음 실패: {last}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None, help="앞에서부터 이만큼만 판정한다(시험용)")
    parser.add_argument("--pending", action="store_true",
                        help="이번 프롬프트 버전으로 아직 판정하지 않은 행만 판정한다(실패한 묶음 다시 돌리기)")
    parser.add_argument("--batch", type=int, default=BATCH, help=f"한 번에 묻는 장소 수(기본 {BATCH})")
    args = parser.parse_args(argv)

    from openai import OpenAI

    from app.core.settings import get_settings
    settings = get_settings()
    model = settings.activity_judge_model
    client = OpenAI(api_key=settings.openai_api_key, timeout=90)
    source = f"llm:{model}:{PROMPT_VERSION}:{date.today().isoformat()}"

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for col in ("indoor_outdoor", "indoor_outdoor_source"):
        if col not in fieldnames:
            fieldnames.append(col)

    targets = [(_row_id(i, r), r) for i, r in enumerate(rows)
               if not (r.get("indoor_outdoor_source") or "").startswith("human:")]
    if args.pending:
        done_prefix = f"llm:{model}:{PROMPT_VERSION}:"
        targets = [(rid, r) for rid, r in targets if not (r.get("indoor_outdoor_source") or "").startswith(done_prefix)]
    if args.limit is not None:
        targets = targets[:args.limit]
    batches = [targets[i:i + args.batch] for i in range(0, len(targets), args.batch)]
    by_id = dict(targets)

    counts: Counter[str] = Counter()
    failed: list[str] = []
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_ask, client, model, b): b for b in batches}
        for done, future in enumerate(as_completed(futures), 1):
            try:
                verdicts = future.result()
            except Exception as exc:  # noqa: BLE001 — 센다. 그 묶음의 칸은 건드리지 않는다
                failed.append(str(exc))
                counts["묶음 실패 행"] += len(futures[future])
                continue
            for rid, verdict in verdicts.items():
                row = by_id[rid]
                row["indoor_outdoor"] = "" if verdict == "unknown" else verdict
                row["indoor_outdoor_source"] = source
                counts[verdict] += 1
            if done % 20 == 0:
                print(f"  {done}/{len(batches)} 묶음 · {time.monotonic() - started:.0f}초", flush=True)

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    CSV_PATH.write_bytes(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))

    print(f"판정 {len(targets)}곳 · {dict(counts)} · 출처 {source} · {time.monotonic() - started:.0f}초")
    for message in failed[:5]:
        print("  실패:", message, file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
