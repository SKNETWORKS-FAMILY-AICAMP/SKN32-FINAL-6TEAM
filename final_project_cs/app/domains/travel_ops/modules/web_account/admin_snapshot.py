"""Read measured operations data; absent measurements are null."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from app.application import admin_service as service


def snapshot(conn, tenant: str, default_chat_limit: int) -> dict:
    now = datetime.now(UTC)
    stamp = now.isoformat()
    def rows(sql, params=(tenant,)):
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    policies = {r["id"]: r for r in service.records(conn, tenant, "user")}
    limits = service.record(conn, tenant, "settings", "limits")
    day = "day:" + now.astimezone(service.KST).date().isoformat()
    usage_rows = rows("SELECT who,action,sum(used) FROM web_usage WHERE tenant_id=%s AND who_kind='key' AND period=%s GROUP BY who,action", (tenant,day))
    usage_map = {}
    for customer,action,count in usage_rows:
        usage_map.setdefault(customer,{})[action] = int(count)
    trip_rows = rows("SELECT t.customer_id,t.trip_id,t.title,t.status,count(i.item_id) FROM trips t LEFT JOIN itinerary_items i ON i.trip_id=t.trip_id AND i.version=t.latest_version AND i.tenant_id=t.tenant_id WHERE t.tenant_id=%s GROUP BY t.trip_id,t.customer_id,t.title,t.status")
    trips_map = {}
    for customer,tid,title,status,count in trip_rows:
        trips_map.setdefault(str(customer),[]).append({"id":str(tid),"title":title,"status":status,"places":count})
    customers = rows("SELECT c.customer_id,c.created_at,x.last_used FROM customers c LEFT JOIN (SELECT customer_id,max(last_used_at) AS last_used FROM (SELECT customer_id,last_used_at FROM web_user_keys WHERE tenant_id=%s UNION ALL SELECT customer_id,last_used_at FROM web_sessions WHERE tenant_id=%s) k GROUP BY customer_id) x ON x.customer_id=c.customer_id WHERE c.tenant_id=%s ORDER BY c.created_at DESC LIMIT 500", (tenant,tenant,tenant))
    users = []
    for uid, issued, last in customers:
        uid = str(uid)
        user = policies.get(uid,{})
        expired = user.get("exceptionPeriod") == "today" and user.get("exceptionDay") != now.astimezone(service.KST).date().isoformat()
        counts = usage_map.get(uid,{})
        users.append({"id":uid,"blocked":bool(user.get("blocked")),"issuedAt":issued.isoformat(),"lastUsed":last.isoformat() if last else "사용 기록 없음","chat":counts.get("message",0),"web":sum(counts.values()),"exceptionLimit":None if expired else user.get("exceptionLimit"),"exceptionPeriod":None if expired else user.get("exceptionPeriod"),"trips":trips_map.get(uid,[]),"paths":[{"path":a,"count":n} for a,n in counts.items()]})
    apis = []
    from app.core.settings import get_settings
    kst = now.astimezone(service.KST)
    kst_sources = set(get_settings().source_rate_limits())
    caps_map = {meter:(daily,monthly) for meter,daily,monthly in rows("SELECT meter,daily,monthly FROM admin_api_caps", ())}
    for meter, periods in rows("SELECT meter,jsonb_object_agg(period,jsonb_build_object('used',used,'cap',cap,'failed',failed,'rejected',rejected)) FROM external_call_budget WHERE period IN (%s,%s,%s,%s) GROUP BY meter", (f"day:{now:%Y-%m-%d}", f"month:{now:%Y-%m}", f"day:{kst:%Y-%m-%d}", f"month:{kst:%Y-%m}")):
        if meter.endswith(":over_free"):
            continue
        local = kst if meter in kst_sources and not meter.startswith(("google_","kakao_")) else now
        day, month = periods.get(f"day:{local:%Y-%m-%d}"), periods.get(f"month:{local:%Y-%m}")
        caps = [caps_map[meter]] if meter in caps_map else []
        apis.append({"id": meter, "name": meter, "adapter": meter, "connection": "계측 기록 있음", "metering": "호출 전 DB 예약", "used": day["used"] if day else None, "monthlyUsed": month["used"] if month else None, "dailyCap": min(day["cap"], caps[0][0]) if day and caps else day["cap"] if day else None, "monthlyCap": min(month["cap"], caps[0][1]) if month and caps else month["cap"] if month else None, "free": None, "watch": None, "chat": None, "paid": None, "cost": None, "budgetTimezone": "Asia/Seoul" if local is kst else "UTC", "watches": "감시/채팅 별도 계측 없음"})
    approvals = [{"id": f"{r[0]}:{r[1]}", "userId": str(r[2]), "trip": r[3], "request": r[4], "evidence": json.dumps(r[5], ensure_ascii=False, default=str), "at": r[6].isoformat(), "status": "대기"} for r in rows("SELECT a.case_id,a.action_id,c.customer_id,c.subject,a.action_type,a.arguments_json,a.created_at FROM action_requests a JOIN customer_cases c ON c.case_id=a.case_id AND c.tenant_id=a.tenant_id WHERE a.tenant_id=%s AND a.status IN ('proposed','pending_approval') ORDER BY a.created_at LIMIT 500")]
    delegations = [{"id": str(r[0]), "userId": str(r[0]), "scope": r[2] or "위임 규정 범위", "active": r[1] is None} for r in rows("SELECT customer_id,revoked_at,note FROM delegations WHERE tenant_id=%s")]
    outbox = [{"id": str(r[0]), "topic": r[1], "attempts": r[2], "error": r[3] or "", "status": "unknown", "resolution": r[4], "resolvedBy": r[5], "note": r[6]} for r in rows("SELECT message_id,topic,attempts,last_error,resolution,resolved_by,resolution_note FROM outbox WHERE tenant_id=%s AND status='unknown' ORDER BY available_at LIMIT 500")]
    audit = [{"id": str(r[0]), "at": r[1].isoformat(), "actor": r[2], "action": r[3], "target": r[4], "before": json.dumps(r[5], ensure_ascii=False, default=str), "after": json.dumps(r[6], ensure_ascii=False, default=str), "reason": r[7]} for r in rows("SELECT id,at,actor,action,target,before_value,after_value,reason FROM admin_audit WHERE tenant_id=%s ORDER BY seq DESC LIMIT 500")]
    size, connections = rows("SELECT pg_database_size(current_database()),(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database())", ())[0]
    limits = service.record(conn, tenant, "settings", "limits")
    maintenance = service.record(conn, tenant, "settings", "maintenance") or {"enabled": False, "message": "", "messageEn": "", "endsAt": ""}
    if maintenance["enabled"] and datetime.fromisoformat(maintenance["endsAt"]).replace(tzinfo=service.KST) <= now:
        maintenance["enabled"] = False
    daily = [{"day": r[0].removeprefix("day:"), "watch": None, "chat": int(r[1])} for r in rows("SELECT period,sum(used) FILTER(WHERE action='message') FROM web_usage WHERE tenant_id=%s AND who_kind='all' AND period LIKE 'day:%%' GROUP BY period ORDER BY period DESC LIMIT 14") if r[1] is not None]
    llm_rows = rows("SELECT l.model,l.provider,count(*),sum(l.input_tokens),sum(l.output_tokens),sum(l.cost_microusd),avg(l.latency_ms) FROM llm_calls l JOIN agent_runs a ON a.run_id=l.run_id WHERE a.tenant_id=%s AND l.created_at >= %s GROUP BY l.model,l.provider", (tenant,datetime.combine(kst.date(),datetime.min.time(),tzinfo=service.KST)))
    llm = [{"model":r[0],"calls":r[2],"input":r[3],"output":r[4],"cost":float(r[5])/1000000 if r[5] is not None else None,"latency":float(r[6]) if r[6] is not None else None,"local":r[1] in ("local","local_ft")} for r in llm_rows]
    return {"live": True, "measurements":{"requests":"unavailable","llm":"tenant-attributed-only"}, "clock": stamp, "users": users, "apis": apis, "chatLimit": limits.get("chatLimit", default_chat_limit), "watchRules": limits.get("watchRules", []), "inquiries": service.records(conn, tenant, "inquiry"), "templates": service.records(conn, tenant, "template"), "notices": service.records(conn, tenant, "notice"), "maintenance": maintenance, "audit": audit, "approvals": approvals, "delegations": delegations, "outbox": outbox, "server": {"checkedAt": stamp, "checks": [{"name": "DB 연결", "status": "정상", "detail": "실제 조회 성공"}, {"name": "외부 API", "status": "미확인", "detail": "실제 제공처 재호출하지 않음"}, {"name": "알림 채널", "status": "미확인", "detail": "배달 결과 별도 확인 필요"}], "cpu": None, "memory": None, "disk": None, "uptime": None, "dbSize": f"{size:,} bytes", "dbConnections": connections, "slowQueries": None, "lastWatch": None, "watchFailures": None, "restarts": None}, "requests": [], "llm": llm, "daily": daily}
