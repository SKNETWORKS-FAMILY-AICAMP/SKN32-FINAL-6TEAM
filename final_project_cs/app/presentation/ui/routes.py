from __future__ import annotations

import html
import json
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import app.core.settings as settings_module
from app import composition
from app.infrastructure.graphstore.sql_adapter import SqlGraphAdapter
from app.infrastructure.llm.openai import OpenAITeamLLM
from app.infrastructure.messaging.outbox import OutboxBrokerAdapter
from app.infrastructure.db.session import get_connection
from app.core.remote_team.executor import LocalTeamExecutor
from app.infrastructure.rag import retriever as rag_retriever
from app.presentation.security import _development_key, masked
from app.presentation.ui import theme

router = APIRouter(prefix="/ui", tags=["operations-ui"])
ops_router = APIRouter(tags=["operations-ui"])


def _safe(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _json(value: Any) -> str:
    return _safe(json.dumps(value or {}, ensure_ascii=False, default=str, indent=2))


def _page(title: str, body: str, *, current: str = "", lede: str = "") -> HTMLResponse:
    return HTMLResponse(theme.page(title, body, current=current, lede=lede))


def _legacy_page(title: str, body: str) -> HTMLResponse:
    nav = "<nav><a href='/ui/cases'>Cases</a><a href='/ui/approvals'>Approvals</a><a href='/ui/voc'>VOC</a><a href='/ui/admin'>Admin</a></nav>"
    return HTMLResponse(f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_safe(title)}</title><style>body{{font-family:system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#172033;background:#f7f8fb}}nav{{display:flex;gap:1rem;margin-bottom:2rem}}a{{color:#155eef}}.card{{background:white;border:1px solid #dfe3eb;border-radius:12px;padding:1rem;margin:.8rem 0;box-shadow:0 2px 8px #1822300d}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{text-align:left;padding:.7rem;border-bottom:1px solid #e7eaf0;vertical-align:top}}th{{font-size:.8rem;color:#5c667a}}code,pre{{white-space:pre-wrap;word-break:break-word}}.muted{{color:#667085}}.badge{{display:inline-block;background:#eef4ff;color:#174ea6;border-radius:99px;padding:.2rem .6rem;font-size:.8rem}}button{{padding:.5rem .8rem;border:0;border-radius:7px;background:#155eef;color:white;cursor:pointer}}button:disabled{{background:#aab2c0;cursor:not-allowed}}.danger{{background:#b42318}}.evidence{{border-left:3px solid #12b76a;padding-left:.7rem;margin:.5rem 0}}</style></head><body>{nav}<h1>{_safe(title)}</h1>{body}</body></html>")


def _tenant() -> str:
    return settings_module.get_settings().tenant_id


def _cases() -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id, status, intent, issue_code, sentiment, owner_team_id, version, updated_at FROM customer_cases WHERE tenant_id=%s ORDER BY updated_at DESC", (_tenant(),))
        keys = ("case_id", "status", "intent", "issue_code", "sentiment", "owner_team", "version", "updated_at")
        return [dict(zip(keys, row)) for row in cur.fetchall()]


def _case(case_id: UUID) -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT case_id, status, subject, intent, issue_code, sentiment, owner_team_id, version, state_json, updated_at FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (_tenant(), case_id))
        row = cur.fetchone()
        if row is None:
            return None
        data = dict(zip(("case_id", "status", "subject", "intent", "issue_code", "sentiment", "owner_team", "version", "state_json", "updated_at"), row))
        cur.execute("SELECT event_id, aggregate_version, event_type, payload_json, actor_type, actor_id, created_at FROM case_events WHERE tenant_id=%s AND case_id=%s ORDER BY aggregate_version", (_tenant(), case_id))
        data["events"] = [dict(zip(("event_id", "aggregate_version", "event_type", "payload", "actor_type", "actor_id", "created_at"), r)) for r in cur.fetchall()]
        data["trace_identity"] = {"case_id": str(data["case_id"]), "subject": data["subject"], "status": data["status"], "version": data["version"]}
        if data["events"]:
            data["events"][0]["payload"] = {"trace_case": data["trace_identity"], **(data["events"][0]["payload"] or {})}
        data["evidence"] = [{"source_type": "case_event", "source_id": str(e["event_id"]), "claim": e["event_type"]} for e in data["events"]]
        return data


def _actions() -> list[dict[str, Any]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT action_id, case_id, action_type, arguments_json, idempotency_key, status, created_at FROM action_requests WHERE tenant_id=%s AND status IN ('proposed','pending_approval') ORDER BY created_at", (_tenant(),))
        rows = [dict(zip(("action_id", "case_id", "action_type", "arguments", "idempotency_key", "status", "created_at"), r)) for r in cur.fetchall()]
        for row in rows:
            proposal_evidence = (row["arguments"] or {}).get("evidence", [])
            row["evidence"] = proposal_evidence if isinstance(proposal_evidence, list) else []
        return rows


def _voc() -> dict[str, Any] | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT period_start, period_end, metrics_json, alerts_json, created_at FROM feedback_analytics_reports WHERE tenant_id=%s ORDER BY created_at DESC LIMIT 1", (_tenant(),))
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(("period_start", "period_end", "metrics", "alerts", "created_at"), row))


def _unknown_outbox() -> list[dict[str, Any]]:
    """Return unresolved unknown messages for the current tenant."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT message_id, topic, payload_json, attempts, last_error, available_at, locked_at "
            "FROM outbox WHERE tenant_id=%s AND status='unknown' AND resolved_at IS NULL "
            "ORDER BY available_at, message_id", (_tenant(),))
        keys = ("message_id", "topic", "payload", "attempts", "last_error", "available_at", "locked_at")
        return [dict(zip(keys, row)) for row in cur.fetchall()]


def _admin_snapshot() -> dict[str, Any]:
    """Read-only projection of the composition and tenant-scoped operations state."""
    tenant = _tenant()
    registry = composition.build_registry()
    settings = settings_module.get_settings()
    guardrails = settings_module.get_guardrails().as_dict()
    # These are the concrete objects assembled by the composition boundary.
    # SqlGraphAdapter only needs a connection when a graph operation is called;
    # the admin page intentionally does not execute graph queries.
    executor = LocalTeamExecutor(registry)
    broker = OutboxBrokerAdapter(get_connection)
    graph = SqlGraphAdapter(None, tenant_id=tenant)
    llm = OpenAITeamLLM()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM knowledge_documents WHERE tenant_id=%s", (tenant,))
        document_count = cur.fetchone()[0]
        cur.execute("""SELECT count(*) FROM knowledge_chunks kc
                       JOIN knowledge_documents kd ON kd.document_id=kc.document_id
                       WHERE kd.tenant_id=%s""", (tenant,))
        chunk_count = cur.fetchone()[0]
        cur.execute("SELECT status, count(*) FROM customer_cases WHERE tenant_id=%s GROUP BY status ORDER BY status", (tenant,))
        case_statuses = dict(cur.fetchall())
        cur.execute("SELECT status, count(*) FROM outbox WHERE tenant_id=%s GROUP BY status ORDER BY status", (tenant,))
        outbox_statuses = dict(cur.fetchall())
    return {
        "manifests": registry.manifests(),
        "ports": [
            ("TeamExecutorPort", type(executor).__name__),
            ("MessageBrokerPort", type(broker).__name__),
            ("GraphStorePort", type(graph).__name__),
            ("Vector 검색", f"{rag_retriever.__name__}.{rag_retriever.search_policy.__name__}"),
            ("LLM", type(llm).__name__),
        ],
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_key": "sk-****" if settings.openai_api_key else "없음",
        "guardrails": guardrails,
        "document_count": document_count,
        "chunk_count": chunk_count,
        "case_statuses": case_statuses,
        "outbox_statuses": outbox_statuses,
    }


def _admin_value(value: Any) -> str:
    return _json(value) if isinstance(value, (dict, list, tuple)) else _safe(value)


@router.get("/admin", response_class=HTMLResponse)
def admin() -> HTMLResponse:
    data = _admin_snapshot()
    cases_by_status = data["case_statuses"]
    outbox_by_status = data["outbox_statuses"]

    # ★unknown 은 "돈이 나갔는지 모르는" 상태다. 숫자 하나로 크게 띄운다.
    unknown_n = outbox_by_status.get("unknown", 0)
    dead_n = outbox_by_status.get("dead_letter", 0)
    overview = "<div class='grid'>" + "".join((
        theme.stat("Agent Team", len(data["manifests"])),
        theme.stat("지식 문서", data["document_count"]),
        theme.stat("지식 청크", data["chunk_count"]),
        theme.stat("Case", sum(cases_by_status.values())),
        theme.stat("outbox unknown", unknown_n, tone="critical" if unknown_n else "",
                   hint="사람이 provider 를 조회해야 합니다" if unknown_n else ""),
        theme.stat("dead letter", dead_n, tone="critical" if dead_n else ""),
    )) + "</div>"

    team_rows = [
        "<tr>"
        f"<td class='mono'>{_safe(m.team_id)}</td>"
        f"<td>{_safe(m.display_name)}</td>"
        f"<td>{theme.pill('active' if m.active else 'cancelled', label='active' if m.active else 'inactive')}</td>"
        f"<td>{_safe(', '.join(m.capabilities))}</td>"
        f"<td>{_safe(', '.join(m.allowed_tools))}</td>"
        f"<td>{_safe(', '.join(m.knowledge_scope))}</td>"
        f"<td class='mono'>{_safe(m.max_steps)}</td>"
        f"<td class='mono'>{_safe(m.implementation_revision)}</td>"
        "</tr>" for m in data["manifests"]]
    teams = theme.card(
        "Agent Team Modules",
        theme.table(("team_id", "이름", "상태", "capabilities", "allowed_tools",
                     "knowledge_scope", "max_steps", "revision"), team_rows),
        subtitle="Registry 가 실제로 들고 있는 것")

    port_rows = [f"<tr><td class='mono'>{_safe(p)}</td><td class='mono'>{_safe(impl)}</td></tr>"
                 for p, impl in data["ports"]]
    ports = theme.card(
        # ★엔티티를 직접 넣지 않는다 — theme.card() 가 esc() 를 하므로 이중 이스케이프된다
        #   ("Ports &amp;amp; Adapters" 로 화면에 떴다).
        "Ports & Adapters",
        theme.table(("Port", "현재 구현"), port_rows)
        + theme.kv_table((("LLM provider", data["llm_provider"]),
                          ("LLM model", data["llm_model"]),
                          ("API key", data["llm_key"]))),
        subtitle="교체점 — 구현을 바꿔 끼우는 자리")

    # ★가드레일을 JSON 덩어리로 던지지 않는다. 평평하게 펴서 읽을 수 있게 만든다.
    guard = theme.card("Guardrails", theme.kv_table(_flatten(data["guardrails"])),
                       subtitle="config/guardrails.yaml 단일 출처")

    health = theme.card(
        "상태 분포",
        "<h3>Case status</h3>" + theme.distribution(cases_by_status)
        + "<h3>Outbox status</h3>" + theme.distribution(outbox_by_status),
        subtitle="tenant 범위")

    return _page("Basement Admin", overview + teams + ports + guard + health,
                 current="/ui/admin", lede="tenant 범위 읽기 전용 뷰입니다. 여기서는 아무것도 바꾸지 않습니다.")


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """중첩 dict 를 `a.b.c` 키로 펴서 표에 넣을 수 있게 한다."""
    out: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, sub in value.items():
            out.extend(_flatten(sub, f"{prefix}.{key}" if prefix else str(key)))
    else:
        out.append((prefix, value))
    return out


@router.get("/cases", response_class=HTMLResponse)
def cases() -> HTMLResponse:
    rows = _cases()
    if not rows:
        return _page("Case 목록", theme.empty_state(
            "표시할 Case가 없습니다.",
            hint="`python -m scripts.seed_demo_cases` 로 시연용 Case 를 만들 수 있습니다."),
            current="/ui/cases")

    # ★사람이 손대야 하는 건수를 맨 위에 세운다. 목록을 훑어 세게 하지 않는다.
    needs_human = sum(1 for r in rows if theme.tone_of(r["status"]) == "warn")
    critical = sum(1 for r in rows if theme.tone_of(r["status"]) == "critical")
    in_flight = sum(1 for r in rows if theme.tone_of(r["status"]) == "active")
    done = sum(1 for r in rows if theme.tone_of(r["status"]) == "done")
    summary = "<div class='grid'>" + "".join((
        theme.stat("전체", len(rows)),
        theme.stat("승인 대기", needs_human, tone="warn" if needs_human else "",
                   hint="사람이 결정해야 합니다" if needs_human else ""),
        theme.stat("에스컬레이션", critical, tone="critical" if critical else "",
                   hint="지금 확인이 필요합니다" if critical else ""),
        theme.stat("진행 중", in_flight),
        theme.stat("종결", done, tone="done" if done else ""),
    )) + "</div>"

    body_rows = [
        "<tr>"
        f"<td><a class='mono' href='/ui/cases/{r['case_id']}'>{_safe(masked(r['case_id']))}</a></td>"
        f"<td>{theme.pill(r['status'])}</td>"
        f"<td>{_safe(r['intent']) or '<span class=muted>미분류</span>'}</td>"
        f"<td>{_safe(r['issue_code']) or '<span class=muted>—</span>'}</td>"
        f"<td>{_safe(r['sentiment']) or '<span class=muted>—</span>'}</td>"
        f"<td>{_safe(r['owner_team']) or '<span class=muted>미배정</span>'}</td>"
        f"<td class='mono'>v{_safe(r['version'])}</td>"
        f"<td class='muted'>{_safe(r['updated_at'])}</td>"
        "</tr>" for r in rows]
    listing = theme.table(
        ("case", "status", "intent", "issue_code", "sentiment", "owner_team", "version", "updated_at"),
        body_rows)
    return _page("Case 목록", summary + theme.card(None, listing),
                 current="/ui/cases",
                 lede="분류 실패는 빈칸이 아니라 '미분류'로 적습니다 — 추정으로 채우지 않습니다.")


@router.get("/cases/{case_id}", response_class=HTMLResponse)
def case_detail(case_id: UUID) -> HTMLResponse:
    data = _case(case_id)
    if data is None:
        return _page("Case 상세", theme.empty_state("Case를 찾을 수 없습니다."), current="/ui/cases")

    state = data["state_json"] or {}
    # ★degraded 를 숨기지 않는다. 축소된 근거로 만든 답이면 화면이 먼저 말한다.
    banner = ""
    if state.get("degraded"):
        omissions = state.get("omissions") or []
        banner = theme.notice(
            "이 Case 의 ContextPack 은 축소됐습니다(degraded). 빠진 것: "
            + (", ".join(str(o) for o in omissions) or "기록 없음"), tone="critical")

    facts = theme.kv_table((
        ("status", data["status"]),
        ("version", f"v{data['version']}"),
        ("intent", data["intent"] or "미분류"),
        ("issue_code", data["issue_code"] or "미분류"),
        ("sentiment", data["sentiment"] or "미분류"),
        ("owner_team", data["owner_team"] or "미배정"),
        ("updated_at", data["updated_at"]),
    ))
    head = theme.card(
        "요약", f"<p>{theme.pill(data['status'])}</p>" + facts,
        subtitle=f"{len(data['events'])}개 이벤트")
    evidence = theme.card("Evidence", theme.evidence_block(data["evidence"], masker=masked),
                          subtitle="각 주장이 무엇에 근거하는지")
    raw = theme.card(None, theme.details("state_json 원문", f"<pre>{_json(state)}</pre>"))
    link = ("<div class='actions'>"
            f"<a href='/ui/cases/{case_id}/trace'><button>Trace 타임라인 보기</button></a></div>")
    return _page("Case 상세", banner + head + evidence + raw + link, current="/ui/cases")


@router.get("/cases/{case_id}/trace", response_class=HTMLResponse)
def trace(case_id: UUID) -> HTMLResponse:
    data = _case(case_id)
    if data is None:
        return _page("Trace", theme.empty_state("Case를 찾을 수 없습니다."), current="/ui/cases")

    items = "".join(
        "<li class='tl'>"
        f"<div class='tl__head'><span class='tl__v'>v{theme.esc(e['aggregate_version'])}</span>"
        f"{theme.pill(e['event_type'], label=e['event_type'])}</div>"
        f"<p class='tl__meta'>{_safe(masked(e['actor_id']))} "
        f"({_safe(e['actor_type'])}) · {_safe(e['created_at'])}</p>"
        f"<pre>{_json(e['payload'])}</pre></li>"
        for e in data["events"])
    timeline = f"<ul class='timeline'>{items}</ul>" if items else theme.empty_state("이벤트 없음")
    note = theme.notice(
        "이 타임라인은 append-only case_events 입니다. 수정·삭제 기능은 제공하지 않습니다.",
        tone="info")
    return _page("Trace · append-only timeline",
                 note + theme.card(None, timeline), current="/ui/cases",
                 lede=f"case {case_id}")


@router.get("/approvals", response_class=HTMLResponse)
def approvals() -> HTMLResponse:
    rows = _actions()
    if not rows:
        return _page("Approval", theme.empty_state("대기 중인 승인 요청이 없습니다."),
                     current="/ui/approvals")

    blocked = sum(1 for r in rows if not r["evidence"])
    summary = "<div class='grid'>" + "".join((
        theme.stat("대기 중", len(rows), tone="warn"),
        theme.stat("근거 없어 잠김", blocked, tone="critical" if blocked else "",
                   hint="승인할 수 없습니다" if blocked else ""),
    )) + "</div>"

    cards = []
    for r in rows:
        evidence = r["evidence"]
        args = r["arguments"] or {}
        # ★근거가 없으면 버튼을 잠근다. 그리고 **왜 잠겼는지 적는다** —
        #   이유를 안 적으면 운영자가 UI 결함으로 오해한다 (2026-08-14 에 실제로 그랬다).
        disabled = " disabled" if not evidence else ""
        lock_note = theme.notice(
            "근거가 없어 승인·거절이 잠겼습니다. 확정 답변에는 Evidence 가 필요합니다.",
            tone="critical") if not evidence else ""

        facts = theme.kv_table((
            ("case", masked(r["case_id"])),
            ("action", masked(r["action_id"])),
            ("risk_level", args.get("risk_level") or "미지정"),
            ("idempotency_key", masked(r["idempotency_key"])),
        ))
        cards.append(theme.card(
            r["action_type"],
            facts
            + "<h3>rationale evidence</h3>"
            + theme.evidence_block(evidence, masker=masked)
            + lock_note
            + theme.details("arguments 원문", f"<pre>{_json(args)}</pre>")
            + f"<form class='actions' method='post' action='/ui/approvals/{r['case_id']}/{r['action_id']}'>"
              f"<button name='decision' value='approved'{disabled}>승인</button>"
              f"<button class='ghost' name='decision' value='rejected'{disabled}>거절</button></form>",
            subtitle=str(r["status"]),
            tone="critical" if not evidence else "warn"))

    return _page("Approval", summary + "".join(cards), current="/ui/approvals",
                 lede="승인은 되돌릴 수 없습니다. 근거를 먼저 읽고 누르십시오.")


@router.post("/approvals/{case_id}/{action_id}")
async def approve(request: Request, case_id: UUID, action_id: UUID) -> RedirectResponse:
    form = await request.form()
    decision = str(form.get("decision", "rejected"))
    settings = settings_module.get_settings()
    token = _development_key("action:approve", settings.secret_key)
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url=str(request.base_url).rstrip("/")) as client:
        response = await client.post(f"/v1/cases/{case_id}/actions/{action_id}/approve", headers={"Authorization": f"Bearer {token}"}, json={"decision": decision, "approver_id": "ui-operator"})
    # ★두 분기가 같은 응답을 내고 있었다 — 승인이 실패해도 운영자는 목록으로 돌아올 뿐
    #   무엇이 잘못됐는지 알 수 없었다. 승인은 되돌릴 수 없는 행위인데 실패를 삼키면
    #   "눌렀으니 됐겠지" 로 넘어간다 (CLAUDE.md §3 — 조용한 스킵을 만들지 않는다).
    if response.is_error:
        detail = _safe(response.text[:400]) or f"HTTP {response.status_code}"
        return _page("Approval 실패", (
            f"<p class='card'><strong>승인이 처리되지 않았습니다.</strong> "
            f"HTTP {response.status_code}</p><pre class='card'>{detail}</pre>"
            "<p><a href='/ui/approvals'>승인 목록으로</a></p>"))
    return RedirectResponse("/ui/approvals", status_code=303)


@router.get("/ops/outbox", response_class=HTMLResponse)
def outbox() -> HTMLResponse:
    rows = _unknown_outbox()
    if not rows:
        return _page("Outbox · unknown", theme.empty_state(
            "미해결 unknown 메시지가 없습니다.",
            hint="unknown은 자동 재실행되지 않으며, 사람이 확인한 근거만 기록할 수 있습니다."),
            current="/ops/outbox")
    cards = []
    for row in rows:
        message_id = row["message_id"]
        facts = theme.kv_table((
            ("message_id", masked(message_id)), ("topic", row["topic"]),
            ("attempts", row["attempts"]), ("last_error", row["last_error"] or "—"),
            ("available_at", row["available_at"]), ("locked_at", row["locked_at"] or "—"),
        ))
        form = (f"<form method='post' action='/ops/outbox/{message_id}'>"
                "<label class='field'>확인 근거 (필수)"
                "<input name='note' required minlength='1' placeholder='하류 시스템 조회 결과와 확인 근거를 적으세요'></label>"
                "<div class='actions'>"
                "<button name='resolution' value='confirmed_delivered'>배달 완료 확인</button>"
                "<button class='ghost' name='resolution' value='confirmed_not_delivered'>미배달 확인</button>"
                "</div></form>")
        cards.append(theme.card("unknown 메시지", facts + theme.details(
            "payload_json", f"<pre>{_json(row['payload'])}</pre>") + form,
            subtitle="자동 재실행 없음 · 확인 기록만 저장", tone="critical"))
    return _page("Outbox · unknown", "".join(cards), current="/ops/outbox",
                 lede="하류 시스템을 직접 확인한 뒤, 근거와 결론을 기록하십시오. 이 화면은 메시지를 재발행하지 않습니다.")


@router.post("/ops/outbox/{message_id}")
async def resolve_outbox(request: Request, message_id: UUID):
    form = await request.form()
    token = _development_key("action:approve", settings_module.get_settings().secret_key)
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url=str(request.base_url).rstrip("/")) as client:
        response = await client.post(
            f"/v1/outbox/{message_id}/resolve",
            headers={"Authorization": f"Bearer {token}"},
            json={"resolution": str(form.get("resolution", "")), "note": str(form.get("note", "")),
                  "resolved_by": "ui-operator"},
        )
    if response.is_error:
        return _page("Outbox 처리 실패", theme.card(
            "처리되지 않았습니다", f"<p>HTTP {response.status_code}</p><pre>{_safe(response.text[:400])}</pre>"),
            current="/ops/outbox")
    return RedirectResponse("/ops/outbox", status_code=303)


# The customer-facing operations navigation uses /ui; keep the historical
# operator URL as a first-class alias without duplicating its implementation.
ops_router.add_api_route("/ops/outbox", outbox, methods=["GET"], response_class=HTMLResponse)
ops_router.add_api_route("/ops/outbox/{message_id}", resolve_outbox, methods=["POST"])


@router.get("/voc", response_class=HTMLResponse)
def voc() -> HTMLResponse:
    report = _voc()
    if report is None:
        return _page("VOC 일일 리포트", "<p class='card'>리포트 없음</p>")
    metrics = report["metrics"]
    counts = metrics.get("intent_issue_count") or {}
    today = counts.get("today") or {}
    prior = counts.get("prior_7_days") or {}

    # ★intent → {issue: n} 이 중첩돼 있다. 파이썬 dict 를 그대로 찍으면
    #   `{'charged_after_cancellation': 1}` 처럼 나온다 — 읽으라고 만든 화면이 아니게 된다.
    #   (intent, issue) 로 펴서 한 줄에 하나씩 낸다.
    def _pairs(bucket: dict) -> dict[tuple[str, str], int]:
        flat: dict[tuple[str, str], int] = {}
        for intent, issues in (bucket or {}).items():
            if isinstance(issues, dict):
                for issue, n in issues.items():
                    flat[(str(intent), str(issue))] = n
            else:
                flat[(str(intent), "—")] = issues
        return flat

    today_flat, prior_flat = _pairs(today), _pairs(prior)
    count_rows = []
    for intent, issue in sorted(set(today_flat) | set(prior_flat)):
        # ★"데이터 없음" 과 "미분류" 는 다른 사실이다.
        #   미분류 = 분류가 실패했다 / 없음 = 그 기간에 건이 없었다.
        #   전에는 둘 다 "미분류" 로 찍어 **없는 실패를 있는 것처럼 보고했다.**
        t = today_flat.get((intent, issue))
        p = prior_flat.get((intent, issue))
        count_rows.append(
            f"<tr><th>{_safe(intent)}</th><td>{_safe(issue)}</td>"
            f"<td class='mono'>{_safe(t) if t is not None else '<span class=muted>없음</span>'}</td>"
            f"<td class='mono'>{_safe(p) if p is not None else '<span class=muted>없음</span>'}</td></tr>")
    count_table = theme.table(("intent", "issue_code", "오늘", "직전 7일"), count_rows,
                              empty="집계된 분류가 없습니다")
    alerts = report["alerts"] or []
    if alerts:
        alert_items = alerts if isinstance(alerts, list) else [alerts]
        alert_text = "".join(f"<li>{_safe(a if isinstance(a, str) else json.dumps(a, ensure_ascii=False, default=str))}</li>" for a in alert_items)
        alert_card = theme.card("급증 alert", f"<ul>{alert_text}</ul>", tone="critical",
                                subtitle="즉시 확인이 필요한 변화")
    else:
        alert_card = theme.card("급증 alert", theme.notice("탐지된 급증이 없습니다.", tone="info"),
                                subtitle="v5 §14-3 급증식 기준")

    # ★비율도 dict 로 오면 그대로 찍혔다 — {"today":0.5,"prior_7_days":0.0}.
    #   오늘과 직전 7일은 **비교하라고 있는 숫자**다. 나란히 세운다.
    def _ratio(name: str, key: str) -> str:
        raw = metrics.get(key)
        if not isinstance(raw, dict):
            return theme.stat(name, raw if raw is not None else "미집계")
        now, before = raw.get("today"), raw.get("prior_7_days")
        hint = f"직전 7일 {before:.0%}" if isinstance(before, (int, float)) else "직전 7일 데이터 없음"
        worse = isinstance(now, (int, float)) and isinstance(before, (int, float)) and now > before
        return theme.stat(name, f"{now:.0%}" if isinstance(now, (int, float)) else "미집계",
                          tone="warn" if worse else "", hint=hint)

    totals = metrics.get("totals") or {}
    summary = ("<div class='grid'>"
               + theme.stat("오늘 건수", totals.get("today", "미집계"),
                            hint=f"직전 7일 {totals.get('prior_7_days', '—')}건")
               + _ratio("부정 비율", "negative_ratio")
               + _ratio("미해결 비율", "unresolved_ratio")
               + "</div>"
               + theme.card("집계 기간",
                            theme.kv_table((("기간", f"{report['period_start']} ~ {report['period_end']}"),))))
    counts_card = theme.card("intent / issue count", count_table,
                             subtitle="건이 없는 칸은 0 이 아니라 '없음' 으로 적습니다")
    return _page("VOC 일일 리포트", summary + counts_card + alert_card,
                 current="/ui/voc", lede="분류·이슈 변화와 급증 신호를 확인합니다.")
