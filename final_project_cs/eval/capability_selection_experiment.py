"""capability 선택을 **LLM 에게 시키면 키워드보다 나은가**를 측정한다.

★기준선이 있어서 이 실험이 가능하다 —
  `docs/reports/2026-09-03_S-CAPABILITY-SELECTION-측정_리포트.md` 가 지금
  방식(이름 매칭 + 키워드 훅)의 golden 라벨 대비 정확도를 **41.7%(25/60)** 로
  쟀다. 그 전에는 수치 자체가 없어서 무엇과 비교할지도 없었다.

재설계 선택지가 셋이었다(같은 리포트).

    A 분류 라벨 세분화        intent 어휘를 늘린다 — 분류기·계약까지 건드린다
    B 매니페스트 선언 확장     default_capability 같은 선언을 더 정교하게
    C 짧은 LLM 판단           이 스크립트가 재는 것

C 를 먼저 재는 이유: **사람 감사 없이 지금 잴 수 있는 유일한 선택지**다.
A·B 는 어느 쪽이 맞는지 알려면 라벨 감사(`scripts/make_capability_audit_form.py`)
결과가 먼저 있어야 한다.

★**이 실험은 채택 결정이 아니다.** LLM 이 이기더라도 비용·지연·비결정성이
  따라온다(Case 마다 호출이 하나 더 는다). 그 판단에 쓸 **수치**를 만드는 것이
  이 스크립트의 전부다.

★공정하게 재려고 지킨 것:
  - 같은 60건, 같은 라벨로 비교한다
  - LLM 에게 **그 팀이 실제로 가진 capability 목록만** 준다. 없는 것을 고르면
    그건 시스템이 못 쓰는 답이므로 오답으로 센다
  - `temperature=0`·`seed` 고정
  - 라벨을 프롬프트에 넣지 않는다(당연하지만 적어 둔다)

    python -m eval.capability_selection_experiment --limit 5    # 먼저 소량으로
    python -m eval.capability_selection_experiment
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROMPT = """고객 문의를 읽고, 이 팀이 가진 기능(capability) 중 어느 것으로 처리해야 하는지 하나만 고르십시오.

고객 문의:
{message}

이 팀이 가진 기능(이 중에서만 고릅니다):
{capabilities}

판단 기준:
- 고객이 **무엇을 해 달라고** 하는지를 봅니다. 규칙을 묻는 문의와 실행을 요청하는 것은 다릅니다.
- 자격이나 조건을 묻는 문의라면 확인·조회 계열 기능입니다.
- 실제로 신청·취소·변경을 해 달라는 것이라면 그 실행 계열 기능입니다.
{tiebreak}
JSON 하나만 반환하십시오: {{"capability": "고른 기능 이름"}}"""

#: ★첫 실행에 이 줄을 넣었다가 **결과를 한쪽으로 몰았다**(2026-09-03).
#:  둘 다 틀린 21건 중 13건이 "라벨=request/calculate, LLM=check_eligibility" 로
#:  한 방향이었다 — 프롬프트가 만든 편향이지 모델의 판단이 아니었다.
#:  그래서 이 줄의 유무를 옵션으로 두고 둘 다 잰다. 실험 설계가 결과를 만들면
#:  그건 측정이 아니다.
SAFE_TIEBREAK = "- 애매하면 되돌릴 수 있는 쪽(조회·확인)을 고릅니다.\n"


async def _ask(client_factory, message: str, capabilities: list[str], model: str,
               tiebreak: str) -> str | None:
    from openai import OpenAI

    def call() -> str | None:
        client: OpenAI = client_factory()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Respond with a single valid JSON object and nothing else."},
                {"role": "user", "content": PROMPT.format(
                    message=message, tiebreak=tiebreak,
                    capabilities="\n".join(f"- {c}" for c in capabilities))},
            ],
            temperature=0.0, seed=7, response_format={"type": "json_object"},
        )
        try:
            return json.loads(response.choices[0].message.content or "{}").get("capability")
        except json.JSONDecodeError:
            return None

    return await asyncio.to_thread(call)


async def run(dataset: Path, limit: int | None, model: str, *, safe_tiebreak: bool) -> dict:
    from app.composition import build_registry
    from app.core.registry import TeamRegistry
    from app.core.settings import get_settings
    from openai import OpenAI

    settings = get_settings()
    if not settings.openai_api_key.strip():
        raise SystemExit("OpenAI API key 가 없다.")

    registry = build_registry()
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    labeled = [r for r in rows if r.get("expected_capability")]
    if limit:
        labeled = labeled[:limit]

    def client_factory() -> OpenAI:
        return OpenAI(api_key=settings.openai_api_key, timeout=60.0)

    tiebreak = SAFE_TIEBREAK if safe_tiebreak else ""
    results, heuristic_hits, llm_hits, invalid = [], 0, 0, 0
    for row in labeled:
        intent = row.get("expected_intent")
        try:
            entry = registry.resolve(case_type=intent or "", intent=intent)
        except Exception:
            continue
        capabilities = list(entry.manifest.capabilities)
        label = row["expected_capability"]
        heuristic = TeamRegistry.capability_for(entry, intent, input_text=row["message"])
        chosen = await _ask(client_factory, row["message"], capabilities, model, tiebreak)

        # ★팀이 못 가진 기능을 고르면 시스템이 쓸 수 없는 답이다 — 오답으로 센다.
        offered = chosen in capabilities
        if not offered:
            invalid += 1
        heuristic_hits += heuristic == label
        llm_hits += bool(offered and chosen == label)
        results.append({"case_id": row["case_id"], "intent": intent,
                        "team_id": entry.manifest.team_id, "label": label,
                        "heuristic": heuristic, "llm": chosen,
                        "llm_offered": offered,
                        "heuristic_ok": heuristic == label,
                        "llm_ok": bool(offered and chosen == label)})

    n = len(results)
    return {
        "model": model, "n": n, "safe_tiebreak": safe_tiebreak,
        "heuristic": {"hits": heuristic_hits, "rate": round(heuristic_hits / n, 4) if n else None},
        "llm": {"hits": llm_hits, "rate": round(llm_hits / n, 4) if n else None,
                "invalid_capability": invalid},
        "cases": results,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="capability 선택: 키워드 대 LLM")
    parser.add_argument("--dataset", default="eval/datasets/golden.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-safe-tiebreak", action="store_true",
                        help="'애매하면 조회 쪽' 지시를 뺀다 — 그 지시가 만드는 편향을 재려고")
    args = parser.parse_args()

    from app.core.settings import get_settings
    model = args.model or get_settings().llm_model
    report = asyncio.run(run(ROOT / args.dataset, args.limit, model,
                             safe_tiebreak=not args.no_safe_tiebreak))

    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, ensure_ascii=False, indent=2))
    h, l = report["heuristic"], report["llm"]
    if report["n"]:
        print(f"\n키워드 {h['hits']}/{report['n']} = {h['rate']:.1%}"
              f"   ·   LLM {l['hits']}/{report['n']} = {l['rate']:.1%}"
              f"   (팀에 없는 기능을 고른 것 {l['invalid_capability']}건)")
    if args.output:
        out = ROOT / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"기록: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
