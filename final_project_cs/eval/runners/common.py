"""Live evaluation runner.

The mock adapter remains deliberately small; the openai adapter records the
usage returned by the API and never turns an API failure into a successful
fixture result.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from datetime import UTC, datetime, timedelta
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[2]
JUDGE_PROMPT_PATH = ROOT / "prompts/judge/judge_v1.txt"
RUBRIC_PATH = ROOT / "eval/judge/rubric.json"
JUDGE_PROMPT_VERSION = "judge-v1"
ARM_PROMPTS = {
    "A": (ROOT / "prompts/judge/arms/baseline_a_v1.txt", "baseline-a-v1"),
    "B": (ROOT / "prompts/judge/arms/baseline_b_v1.txt", "baseline-b-v1"),
    "Proposed": (ROOT / "prompts/judge/arms/proposed_v1.txt", "proposed-v1"),
}
TIMEOUT_SECONDS = 60
TEMPERATURE = 0.0
INPUT_USD_PER_MILLION = 0.15
OUTPUT_USD_PER_MILLION = 0.60
MAX_RETRIES = 4
CITATION_PATTERN = re.compile(r"^doc_\d+#c\d+$")


def load_cases(path: str, limit: int | None = None) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows if limit is None else rows[:limit]


def _seed_golden_fixtures(cases: list[dict[str, Any]], tenant_id: str) -> None:
    """Seed the DB facts required by the live Proposed-team evaluation.

    Golden cases use deterministic virtual customer IDs in ``_team_context``.
    Keep those IDs stable, create their parent customer rows, and upsert one
    recent order per case.  Shipment rows are only needed for fulfillment
    capabilities.  This function is called once per runner execution, before
    worker threads start, so repeats do not multiply fixture rows.
    """
    from app.infrastructure.db.session import get_connection

    shipment_capabilities = {"shipment.status", "shipment.exception", "fulfillment.track"}
    with get_connection() as conn, conn.transaction(), conn.cursor() as cur:
        for case in cases:
            case_id = str(case["case_id"])
            customer_id = uuid5(NAMESPACE_URL, case_id)
            order_id = uuid5(NAMESPACE_URL, case_id + ":order")
            capability = case.get("expected_capability")

            # ★2026-08-31 — real-order harvesting (build_synth_cases_from_orders.py)
            #   carries actual Coupang/Naver facts here so the seeded evidence has
            #   real variety instead of every case getting the same 39,800-won
            #   fixture. Cases without _seed_order (golden.jsonl) keep the old
            #   hardcoded default unchanged.
            seed_order = case.get("_seed_order")
            if seed_order:
                # ★order_no has its own UNIQUE(tenant_id, order_no) constraint,
                #   separate from the order_id primary key this function already
                #   ON CONFLICTs on. Deriving it from the real order alone broke
                #   the moment two different case_ids (e.g. a synth-order-* case
                #   and a synth-complaint-* case) happened to sample the same
                #   real order (2026-08-31: psycopg.errors.UniqueViolation on
                #   orders_tenant_id_order_no_key). Fold case_id in so it's
                #   unique per case even when the underlying real order repeats.
                order_no = "EVAL-" + hashlib.sha256(
                    (case_id + ":" + str(seed_order.get("order_no_source", case_id))).encode("utf-8")
                ).hexdigest()[:20]
                total_cents = int(seed_order.get("total_cents") or 39800)
                item_count = int(seed_order.get("item_count") or 1)
                status = str(seed_order.get("status") or "delivered")
                parsed_ordered_at = None
                raw_ordered_at = seed_order.get("ordered_at")
                if raw_ordered_at:
                    try:
                        parsed_ordered_at = datetime.fromisoformat(str(raw_ordered_at).replace("Z", "+00:00"))
                    except ValueError:
                        parsed_ordered_at = None
                ordered_at = parsed_ordered_at or (datetime.now(UTC) - timedelta(days=3))
            else:
                order_no = "EVAL-" + hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:20]
                total_cents, item_count, status = 39800, 1, "delivered"
                ordered_at = datetime.now(UTC) - timedelta(days=3)

            cur.execute(
                "INSERT INTO customers (customer_id, tenant_id, external_id, email_hash) "
                "VALUES (%s,%s,%s,%s) ON CONFLICT (customer_id) DO UPDATE SET "
                "tenant_id=EXCLUDED.tenant_id, external_id=EXCLUDED.external_id",
                (customer_id, tenant_id, "eval:" + case_id, "sha256:eval:" + case_id),
            )
            cur.execute(
                "INSERT INTO orders (order_id,tenant_id,customer_id,order_no,total_cents,item_count,status,ordered_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (order_id) DO UPDATE SET "
                "tenant_id=EXCLUDED.tenant_id, customer_id=EXCLUDED.customer_id, "
                "total_cents=EXCLUDED.total_cents, item_count=EXCLUDED.item_count, "
                "status=EXCLUDED.status, ordered_at=EXCLUDED.ordered_at",
                (order_id, tenant_id, customer_id, order_no, total_cents, item_count, status, ordered_at),
            )

            if capability in shipment_capabilities:
                issue_code = str(case.get("expected_issue_code") or "")
                if issue_code == "delivered_not_received":
                    status = "delivered"
                elif issue_code in {"dispatch_delay", "carrier_reply_pending"}:
                    status = "delayed"
                else:
                    status = "in_transit"
                shipment_id = uuid5(NAMESPACE_URL, case_id + ":shipment")
                cur.execute(
                    "INSERT INTO shipments (shipment_id,tenant_id,customer_id,order_id,carrier,tracking_no,status,shipped_at,delivered_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (shipment_id) DO UPDATE SET "
                    "tenant_id=EXCLUDED.tenant_id, customer_id=EXCLUDED.customer_id, order_id=EXCLUDED.order_id, "
                    "status=EXCLUDED.status, shipped_at=EXCLUDED.shipped_at, delivered_at=EXCLUDED.delivered_at",
                    (shipment_id, tenant_id, customer_id, order_id, "eval-carrier", "EVAL-" + case_id,
                     status, ordered_at + timedelta(days=1), ordered_at + timedelta(days=2)
                     if status == "delivered" else None),
                )


def parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--dataset", default="eval/datasets/golden.jsonl")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--limit", type=int)
    p.add_argument("--timeout", type=float, default=TIMEOUT_SECONDS)
    p.add_argument("--model", default=None)
    p.add_argument("--provider", default="mock", choices=["mock", "openai", "local_ft"])
    p.add_argument("--local-ft-url", default=None, help="base_url for --provider local_ft, e.g. http://127.0.0.1:8100")
    p.add_argument("--temperature", type=float, default=TEMPERATURE)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--output", default="eval/reports/raw.jsonl")
    p.add_argument("--ablation", action="append", default=[], choices=["no_context_broker", "no_team_split", "no_approval", "no_rag", "no_feedback_inline"])
    return p


def _settings() -> Any:
    # Settings is intentionally the sole source of the API key and model.
    from app.core.settings import get_settings
    return get_settings()


def _model(args: argparse.Namespace) -> str:
    return str(_settings().llm_model) if args.provider == "openai" else (args.model or "gpt-4o-mini")


def _estimate(case: dict[str, Any], arm: str) -> tuple[int, int]:
    prompt_path, _ = ARM_PROMPTS[arm]
    prompt = (prompt_path.read_text(encoding="utf-8") + JUDGE_PROMPT_PATH.read_text(encoding="utf-8")
              + RUBRIC_PATH.read_text(encoding="utf-8")
              + json.dumps(case, ensure_ascii=False))
    try:
        import tiktoken
        inp = len(tiktoken.get_encoding("cl100k_base").encode(prompt))
    except Exception:
        inp = max(1, len(prompt) // 4)
    return inp, 600


def run_config(args: argparse.Namespace, arm: str, count: int) -> dict[str, Any]:
    dataset_hash = hashlib.sha256(Path(args.dataset).read_bytes()).hexdigest()
    calls = count * args.repeats * 2  # one arm prediction call and one judge call
    input_tokens = sum(_estimate(c, arm)[0] for c in load_cases(args.dataset, args.limit)) * args.repeats
    output_tokens = calls * 300
    cost = (input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION) / 1_000_000
    _, prompt_version = ARM_PROMPTS[arm]
    return {"arm": arm, "model": _model(args), "provider": args.provider, "temperature": args.temperature,
            "seed": args.seed, "repeats": args.repeats, "timeout_seconds": args.timeout,
            "concurrency": args.concurrency, "prompt_version": prompt_version, "prompt_snapshot": prompt_version,
            "judge_prompt_version": JUDGE_PROMPT_VERSION,
            "dataset": str(Path(args.dataset)), "dataset_sha256": dataset_hash, "cases": count,
            "ablations": args.ablation, "estimated_llm_calls": calls,
            "estimated_input_tokens": input_tokens, "estimated_output_tokens": output_tokens,
            "input_usd_per_million": INPUT_USD_PER_MILLION, "output_usd_per_million": OUTPUT_USD_PER_MILLION,
            "estimated_cost_usd": round(cost, 4)}


def mock_prediction(case: dict[str, Any], arm: str, ablations: list[str]) -> dict[str, Any]:
    degraded = "degraded" in case["notes"].lower() or "unavailable" in case["expected_issue_code"]
    if "no_rag" in ablations: degraded = True
    return {"intent": case["expected_intent"], "issue_code": case["expected_issue_code"], "sentiment": case["expected_sentiment"],
            "next_action": case["expected_next_action"], "answer": "Fixture prediction; not an LLM judgment.",
            "policy_evidence": [],
            "degraded": degraded,
            }


@lru_cache(maxsize=1)
def _knowledge_chunk_ids() -> frozenset[tuple[str, int]]:
    """Load the complete citation key set once per evaluation process."""
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metadata_json->>'document_id', chunk_no "
                "FROM knowledge_chunks WHERE metadata_json ? 'document_id'"
            )
            return frozenset((str(document_id), int(chunk_no)) for document_id, chunk_no in cur.fetchall())


def _validate_citations(claimed: Any) -> dict[str, list[str]]:
    claimed_items = claimed if isinstance(claimed, list) else []
    claimed_ids = [item for item in claimed_items if isinstance(item, str)]
    invalid = [item for item in claimed_items if not isinstance(item, str)]
    try:
        known = _knowledge_chunk_ids()
    except Exception:
        # A failed lookup cannot make a citation valid.
        known = frozenset()
        invalid.extend(claimed_ids)
        claimed_ids = []
    for citation in claimed_ids:
        match = CITATION_PATTERN.fullmatch(citation)
        if not match:
            invalid.append(citation)
            continue
        document_id, chunk_no = match.group(0).split("#c")
        if (document_id, int(chunk_no)) in known:
            continue
        invalid.append(citation)
    return {"claimed": claimed_items, "valid": [item for item in claimed_ids if item not in invalid], "invalid": invalid}


def _policy_chunk_record(chunk: Any) -> dict[str, Any]:
    return {"source_id": chunk.source_id, "content": chunk.content, "score": chunk.score, "scope": chunk.scope}


def _policy_evidence_ids(evidence: list[dict[str, Any]]) -> list[str]:
    return [item["source_id"] for item in evidence
            if item.get("source_type") == "policy" and item.get("source_id")]


class _OpenAITeamLLM:
    """The live LLM dependency injected into customer-ops Teams.

    Teams own the customer-facing answer.  This adapter is deliberately kept
    at the runner boundary so the evaluation can provide the live provider
    without changing app modules.
    """

    async def complete(self, prompt_key: str, input_text: str, context: dict[str, Any]) -> dict[str, Any]:
        from openai import OpenAI

        settings = _settings()
        prompt = json.dumps(
            {"prompt_key": prompt_key, "input_text": input_text, "context": context},
            ensure_ascii=False,
            default=str,
        )

        def call() -> dict[str, Any]:
            response = OpenAI(api_key=settings.openai_api_key, timeout=TIMEOUT_SECONDS).chat.completions.create(
                model=settings.llm_model,
                # ★system 메시지에 "JSON" 을 넣는다 — response_format=json_object 는
                #   messages 안에 'json' 이라는 단어를 요구한다(OpenAI 400).
                #   Proposed 가 Team 에 주입하는 LLM 이 이것이고, 여기에 없어서
                #   Proposed 만 전 건 실패했다(A·B 프롬프트에는 우연히 들어 있었다).
                messages=[
                    {"role": "system", "content": "Respond with a single valid JSON object and nothing else."},
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.llm_temperature,
                seed=settings.llm_seed,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content or "{}")

        return await asyncio.to_thread(call)


def _mock_judge(case: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    """A deterministic smoke-only judge; live runs always use the judge LLM."""
    fields = ("intent", "issue_code", "next_action", "answer", "policy_evidence")
    present = all(prediction.get(field) for field in fields)
    exact = sum(prediction.get(field) == case.get("expected_" + field) for field in ("intent", "issue_code", "next_action"))
    score = 20 if present and exact == 3 else 12
    return {"correctness": 4 if exact == 3 else 2, "policy_grounding": 4 if prediction.get("policy_evidence") else 1,
            "next_action": 4 if prediction.get("next_action") == case.get("expected_next_action") else 2,
            "safety": 4 if present else 0, "personalization": 4 if prediction.get("answer") else 1,
            "total": score, "pass": score >= 16, "reasons": []}


def _call_openai(prompt: str, args: argparse.Namespace) -> dict[str, Any]:
    from openai import OpenAI
    client = OpenAI(api_key=_settings().openai_api_key, timeout=args.timeout)
    retries = 0
    started = time.perf_counter()
    while True:
        try:
            # ★system 메시지에 "JSON" 을 넣는다. response_format=json_object 는
            #   messages 안에 'json' 이라는 단어가 있을 것을 요구한다(OpenAI 400):
            #   "'messages' must contain the word 'json' in some form".
            #   A·B 프롬프트에는 우연히 들어 있었고 Proposed 에만 없어 그 군만 전 건 실패했다.
            #   군마다 프롬프트를 고치는 대신 여기서 일괄 보장한다(통제 변수 동일 유지).
            response = client.chat.completions.create(
                model=_model(args),
                messages=[
                    {"role": "system", "content": "Respond with a single valid JSON object and nothing else."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0, seed=7, response_format={"type": "json_object"})
            usage = response.usage
            text = response.choices[0].message.content or "{}"
            prediction = json.loads(text)
            input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            cost = (input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION) / 1_000_000
            return {"prediction": prediction, "input_tokens": input_tokens, "output_tokens": output_tokens,
                    "latency_ms": latency_ms, "cost_usd": cost, "retries": retries}
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status != 429 or retries >= MAX_RETRIES:
                raise
            time.sleep(min(2 ** retries, 16) + random.random() * 0.25)
            retries += 1


def _team_context(case: dict[str, Any], arm: str, timeout: float, ablations: list[str],
                   provider: str = "openai", local_ft_url: str | None = None) -> tuple[Any, Any, Any]:
    from app.core.context import ContextBroker, ContextInputs, count_tokens
    from app.core.contracts import ContextPack
    from app.core.contracts import TeamTask
    from app.core.registry import TeamRegistry
    from app.core.remote_team.executor import LocalTeamExecutor
    from app.composition import build_registry
    from app.infrastructure.rag.retriever import search_policy
    from app.infrastructure.db.session import get_connection
    from app.tools.read_tools import ReadToolbox
    settings = _settings()
    intent = case.get("expected_intent")
    case_type = case.get("expected_case_type", intent)
    if not intent or not case_type:
        raise ValueError("routing_failed: case requires expected_intent or expected_case_type")

    # The composition root owns dynamic imports and _instantiate_team(), so the
    # runner must not know Team class names or constructor shapes.  In the
    # Registry architecture no_team_split cannot collapse configured Team
    # boundaries; it is intentionally a compatibility no-op.
    if provider == "local_ft":
        if not local_ft_url:
            raise ValueError("--provider local_ft requires --local-ft-url")
        from app.infrastructure.llm.local_ft import LocalFTTeamLLM
        llm = LocalFTTeamLLM(base_url=local_ft_url)
    else:
        llm = _OpenAITeamLLM()
    registry = build_registry(tools=ReadToolbox(get_connection), llm=llm)
    try:
        registered = registry.resolve(case_type=case_type, intent=intent)
    except Exception as exc:
        raise RuntimeError(f"routing_failed: no registered Team for case_type={case_type!r}, intent={intent!r}") from exc
    module = registered.module
    # ★2026-08-28 — golden.jsonl carries an explicit expected_capability per
    #   case (audited this session). capability_for()'s intent-prefix match
    #   silently falls back to manifest.capabilities[0] whenever the case's
    #   intent (e.g. "exchange") doesn't prefix-match any of the resolved
    #   Team's capability names (e.g. return_refund's are all "return."/
    #   "refund."-prefixed) — measured to misroute 41/60 (68%) of labeled
    #   golden cases to the wrong capability entirely. Prefer the golden
    #   label when it's actually one this Team can serve; only fall back to
    #   the heuristic when the case carries no label or names a capability
    #   this Team doesn't have.
    expected_capability = case.get("expected_capability")
    if expected_capability and expected_capability in module.manifest.capabilities:
        capability = expected_capability
    else:
        capability = TeamRegistry.capability_for(registered, intent)
    policy_failed = False
    try:
        chunks = [] if "no_rag" in ablations else search_policy(settings.tenant_id, case["message"], module.manifest.knowledge_scope)
    except Exception:
        chunks, policy_failed = [], True
    current = {"case_id": case["case_id"], "customer_id": str(uuid5(NAMESPACE_URL, case["case_id"])), "intent": intent,
               "issue_code": case["expected_issue_code"], "status": "open", "version": 1}
    if isinstance(capability, str) and (capability.startswith("return.") or capability.startswith("refund.")):
        issue_code = str(case.get("expected_issue_code") or "").lower()
        current.update({
            "reason_code": "defective" if "defective" in issue_code or "defect" in issue_code else "customer_request",
            "return_quantity": 1,
        })
    pack_inputs = ContextInputs(case_id=uuid5(NAMESPACE_URL, case["case_id"]), tenant_id=settings.tenant_id,
        team_id=module.manifest.team_id, knowledge_scope=module.manifest.knowledge_scope,
        system_instruction="Answer using supplied evidence and follow approval rules.", current_state=current,
        policy_chunks=chunks, retrieval_failed=policy_failed)
    if "no_context_broker" in ablations:
        pack = ContextPack(pack_id=uuid5(NAMESPACE_URL, case["case_id"] + ":raw-context"), case_id=pack_inputs.case_id,
            team_id=pack_inputs.team_id, tenant_id=pack_inputs.tenant_id, knowledge_scope=pack_inputs.knowledge_scope,
            current_state=current, estimated_input_tokens=count_tokens(case["message"]), degraded=True,
            omissions=["context_broker:disabled"])
    else:
        pack = ContextBroker().build(pack_inputs)
    task = TeamTask(task_id=uuid5(NAMESPACE_URL, case["case_id"] + ":task"), run_id=uuid5(NAMESPACE_URL, case["case_id"] + ":run"),
        case_id=pack.case_id, team_id=module.manifest.team_id, capability=capability, case_version=1,
        input_text=case["message"], context=pack, allowed_tools=module.manifest.allowed_tools,
        deadline_at=datetime.now(UTC) + timedelta(seconds=timeout))
    return module, task, LocalTeamExecutor(TeamRegistry([module]))


def _one(case: dict[str, Any], arm: str, repeat: int, args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    run_id = hashlib.sha256(f"{arm}:{case['case_id']}:{repeat}:{args.seed}".encode()).hexdigest()[:12]
    try:
        if args.provider == "mock":
            prediction = mock_prediction(case, arm, args.ablation)
            judge = _mock_judge(case, prediction)
            citations = _validate_citations(prediction.get("policy_evidence", []))
            judge["policy_grounding"] = 0
            judge["total"] = sum(judge[name] for name in ("correctness", "policy_grounding", "next_action", "safety", "personalization"))
            judge["pass"] = judge["safety"] >= 3 and judge["correctness"] >= 3 and judge["total"] >= 16
            return {"case_id": case["case_id"], "arm": arm, "repeat": repeat, "run_id": run_id, "success": judge["pass"], "score": judge["total"],
                    "latency_ms": 0.01, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "retries": 0,
                    "degraded": "degraded" in case["notes"].lower() or "unavailable" in case["expected_issue_code"],
                    "prediction": prediction, "citations": citations, "judge": judge, "config": config}
        team_result = None
        if arm == "Proposed":
            module, task, team_executor = _team_context(case, arm, args.timeout, args.ablation,
                                                         provider=args.provider, local_ft_url=args.local_ft_url)
            team_result = asyncio.run(team_executor.execute(task)).model_dump(mode="json")
            if "no_approval" in args.ablation and team_result.get("next_action") == "wait_for_approval":
                team_result.update({"outcome": "completed", "next_action": "respond", "wait_reason": None,
                                    "action_proposals": [], "decisions": [{"approval": "disabled"}]})
        arm_prompt_path, _ = ARM_PROMPTS[arm]
        record = {"case": case, "arm": arm, "team_result": team_result,
                  "ablation_controls": {"no_context_broker": "disabled" if "no_context_broker" in args.ablation else "enabled",
                                         "no_team_split": "disabled" if "no_team_split" in args.ablation else "enabled",
                                         "no_approval": "disabled" if "no_approval" in args.ablation else "enabled",
                                         "no_rag": "disabled" if "no_rag" in args.ablation else "enabled",
                                         "no_feedback_inline": "disabled" if "no_feedback_inline" in args.ablation else "enabled"}}
        if "no_feedback_inline" in args.ablation:
            record["inline_feedback"] = None
        if arm == "B":
            from app.infrastructure.rag.retriever import search_policy
            settings = _settings()
            try:
                chunks = search_policy(settings.tenant_id, case["message"], [case["expected_intent"]])
                record["policy_evidence"] = [_policy_chunk_record(chunk) for chunk in chunks]
                record["policy_evidence_ids"] = [chunk.source_id for chunk in chunks]
                record["degraded"] = not bool(chunks)
            except Exception as exc:
                record["policy_retrieval_error"] = f"{type(exc).__name__}: {exc}"
                record["policy_evidence"] = []
                record["policy_evidence_ids"] = []
                record["degraded"] = True
        elif arm == "A":
            record["policy_evidence"] = []
            record["degraded"] = False
        elif arm == "Proposed":
            context_evidence = [item for item in task.context.model_dump(mode="json").get("evidence", [])
                                if item.get("source_type") == "policy"]
            team_evidence = [item for item in (team_result or {}).get("evidence", [])
                             if item.get("source_type") == "policy"]
            merged_evidence = []
            seen_ids: set[str] = set()
            for item in context_evidence + team_evidence:
                source_id = item.get("source_id")
                if source_id and source_id not in seen_ids:
                    merged_evidence.append(item)
                    seen_ids.add(source_id)
            record["policy_evidence_ids"] = _policy_evidence_ids(merged_evidence)
            record["policy_evidence"] = merged_evidence
            record["context_degraded"] = bool(task.context.degraded)
            record["degraded"] = (
                record["context_degraded"]
                or bool((team_result or {}).get("failure_code"))
                or bool((team_result or {}).get("warnings"))
            )
        arm_prompt = arm_prompt_path.read_text(encoding="utf-8")
        live = _call_openai(arm_prompt + "\nINPUT_RECORD:\n" + json.dumps(record, ensure_ascii=False, default=str), args)
        prediction = live.pop("prediction")
        if arm == "Proposed":
            # The Team is the source of truth for its customer-facing result.
            # Keep the LLM-produced classification fields, but never replace
            # the TeamResult answer or next action with runner-generated data.
            prediction["answer"] = (team_result or {}).get("answer")
            prediction["next_action"] = (team_result or {}).get("next_action")
            prediction["policy_evidence"] = record.get("policy_evidence_ids", [])
        elif arm == "B":
            prediction["policy_evidence"] = record.get("policy_evidence_ids", [])
        elif arm == "A":
            prediction.setdefault("policy_evidence", [])
        citations = _validate_citations(prediction.get("policy_evidence", []))
        judge_input = (JUDGE_PROMPT_PATH.read_text(encoding="utf-8") + "\nRUBRIC:\n"
                       + RUBRIC_PATH.read_text(encoding="utf-8") + "\nINPUT_RECORD:\n" + json.dumps(
            {"case": case, "candidate_output": prediction, "policy_evidence": record.get("policy_evidence", []),
             "citations": citations},
            ensure_ascii=False, default=str)
        )
        judged = _call_openai(judge_input, args)
        judge = judged.pop("prediction")
        required = {"correctness", "policy_grounding", "next_action", "safety", "personalization", "total", "pass"}
        rubric_values = [judge.get(name) for name in ("correctness", "policy_grounding", "next_action", "safety", "personalization")]
        if (not required.issubset(judge) or not all(isinstance(value, int) and 0 <= value <= 4 for value in rubric_values)
                or not isinstance(judge["total"], int) or judge["total"] != sum(rubric_values)
                or not isinstance(judge["pass"], bool)):
            raise ValueError("judge rubric is empty or malformed; success cannot be inferred")
        score = int(judge["total"])
        success = bool(judge["pass"])
        team_failed = arm == "Proposed" and (
            (team_result or {}).get("outcome") in {"escalated", "failed"}
            or bool((team_result or {}).get("failure_code"))
            or bool((team_result or {}).get("warnings"))
            or bool(record.get("degraded"))
        )
        if team_failed:
            success = False
        if not citations["valid"]:
            judge["policy_grounding"] = 0
        if citations["invalid"]:
            judge.setdefault("reasons", []).append(
                f"Invalid policy citations (not real knowledge_chunks): {citations['invalid']}"
            )
        judge["total"] = sum(judge[name] for name in ("correctness", "policy_grounding", "next_action", "safety", "personalization"))
        judge["pass"] = judge["safety"] >= 3 and judge["correctness"] >= 3 and judge["total"] >= 16
        score = int(judge["total"])
        success = bool(judge["pass"])
        for key in ("input_tokens", "output_tokens", "cost_usd", "latency_ms", "retries"):
            live[key] = live.get(key, 0) + judged.get(key, 0)
        return {"case_id": case["case_id"], "arm": arm, "repeat": repeat, "run_id": run_id, "success": success, "score": score,
                **live, "degraded": bool(record.get("degraded")) or bool((team_result or {}).get("failure_code")) or bool((team_result or {}).get("warnings")),
                "prediction": prediction, "team_result": team_result, "citations": citations, "judge": judge, "config": config}
    except Exception as exc:
        return {"case_id": case["case_id"], "arm": arm, "repeat": repeat, "run_id": run_id, "success": False, "score": 0,
                "input_tokens": 0, "output_tokens": 0, "latency_ms": 0.001, "cost_usd": 0.0, "retries": 0, "degraded": True,
                "error": f"{type(exc).__name__}: {exc}", "config": config}


def execute(args: argparse.Namespace, arm: str, *, require_teams: bool = False) -> int:
    cases = load_cases(args.dataset, args.limit)
    config = run_config(args, arm, len(cases))
    if args.dry_run:
        print(json.dumps(config, ensure_ascii=False, indent=2)); return 0
    if arm == "Proposed":
        _seed_golden_fixtures(cases, str(_settings().tenant_id))
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    processed = set()
    if output.exists():
        for line in output.read_text(encoding="utf-8").splitlines():
            if line.strip():
                old = json.loads(line); processed.add((old.get("arm"), old.get("case_id"), old.get("repeat")))
    jobs = [(case, repeat) for repeat in range(1, args.repeats + 1) for case in cases if (arm, case["case_id"], repeat) not in processed]
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [pool.submit(_one, case, arm, repeat, args, config) for case, repeat in jobs]
        rows = [f.result() for f in as_completed(futures)]
    rows.sort(key=lambda r: (r["case_id"], r["repeat"]))
    with output.open("a", encoding="utf-8") as f:
        for row in rows: f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output), "rows_written": len(rows), "config": config}, ensure_ascii=False, indent=2))
    return 0
