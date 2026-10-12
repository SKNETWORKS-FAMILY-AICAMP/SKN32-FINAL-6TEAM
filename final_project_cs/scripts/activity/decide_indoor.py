"""활동 장소 실내외를 한 번 정해 저장한다 — `activity.ac_indoor`(301). `[2026-10-12]` D-CS-015 개정 2 · 구현 계획 1.8.

    기본      관광공사 분류(`weather_from_class`)로 정해지는 곳만 저장한다 — 모델을 부르지 않는다
    --model   분류로 못 정한 곳을 판정 LLM(실내외, 인용 검증)으로 한 번 정해 저장한다 — OpenAI 를 부른다(호출당 약 $0.0002)
              `travel.activity_judge.budget` 과 상관없이 이 스크립트가 부르는 수는 `--limit` 로 묶는다.
이미 줄이 있는 장소는 건너뛴다(고객 · 운영자 · 앞서 정한 값을 덮지 않는다).

사용법
    python scripts/activity/decide_indoor.py                     분류로만
    python scripts/activity/decide_indoor.py --model --limit 30  모델로 30곳만(사람 확인용 표본)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for path in (ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def model_judge(connection_factory):
    """판정 LLM 의 실내외 판정 → `indoor_store.IndoorJudge` 모양. 인용이 없거나 모름이면 `None`."""
    from app.domains.travel_ops.instances.activity.judge import JudgeContext, LLMJudge, prompt_key, requests
    from app.infrastructure.llm.openai_responses import OpenAIResponsesJudgeLLM

    llm = LLMJudge(OpenAIResponsesJudgeLLM(connection_factory=connection_factory))

    def judge(name, lcls2):
        verdict = asyncio.run(llm.judge(JudgeContext(capability="activity.decide_indoor"),
                                        requests.weather_sensitive(name, lcls2)))
        if verdict.value not in ("outdoor", "indoor") or not verdict.quotes:
            return None
        return {"outdoor": verdict.value == "outdoor", "quote": verdict.quotes[0],
                "model": verdict.metrics.get("model") or "unknown", "prompt_version": prompt_key(verdict.kind)}
    return judge


def run(conn, *, judge=None, limit: int | None = None) -> dict[str, int]:
    from app.domains.travel_ops.instances.activity import indoor_store

    with conn.cursor() as cur:
        cur.execute("SELECT p.content_id, p.name_ko, p.lcls1, p.lcls2 FROM activity.ac_place p "
                    "WHERE NOT EXISTS (SELECT 1 FROM activity.ac_indoor i WHERE i.content_id = p.content_id) "
                    "ORDER BY p.content_id")
        rows = cur.fetchall()
    out = {"asked": 0, "class": 0, "llm": 0, "unknown": 0}
    for content_id, name, lcls1, lcls2 in rows:
        if judge is not None and limit is not None and out["llm"] + out["unknown"] >= limit:
            break
        out["asked"] += 1
        with conn.transaction():
            found = indoor_store.decide(conn, content_id, name=name, lcls1=lcls1, lcls2=lcls2, judge=judge)
        out[found["decided_by"] if found else "unknown"] += 1
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", action="store_true", help="분류로 못 정한 곳을 판정 LLM 으로(OpenAI 를 부른다)")
    parser.add_argument("--limit", type=int, default=None, help="--model 일 때 모델을 부를 장소 수 상한")
    args = parser.parse_args()
    import psycopg
    from load_places import dsn

    with psycopg.connect(dsn(), autocommit=True) as conn:
        judge = None
        if args.model:
            from app.infrastructure.db.session import get_connection

            judge = model_judge(get_connection)
        result = run(conn, judge=judge, limit=args.limit)
        with conn.cursor() as cur:
            cur.execute("SELECT decided_by, count(*) FROM activity.ac_indoor GROUP BY 1 ORDER BY 1")
            totals = dict(cur.fetchall())
    print(f"이번: 대상 {result['asked']:,} → 분류 {result['class']:,} · 모델 {result['llm']:,} · 모름 {result['unknown']:,}")
    print("저장된 줄:", totals)


if __name__ == "__main__":
    main()
