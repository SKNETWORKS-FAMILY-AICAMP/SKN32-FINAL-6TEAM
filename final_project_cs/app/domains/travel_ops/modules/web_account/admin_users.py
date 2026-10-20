"""운영자 전용 사용자 페이지와 저장된 여행 대화 조회."""
from __future__ import annotations

from datetime import UTC, datetime

from psycopg import sql

from app.application import admin_service
from app.core.redaction import masked

USER_PAGE_SIZE = 50
MESSAGE_PAGE_SIZE = 20
SORT_COLUMNS = {
    "id": "id", "status": "blocked", "chat": "chat", "web": "web",
    "trips": "trip_count", "inquiries": "inquiry_count", "lastUsed": "last_used",
}


def read(conn, tenant: str, default_limit: int, kind: str, **options) -> dict:
    if kind == "users":
        return users(conn, tenant, default_limit, **options)
    customer = options.pop("user_id")
    admin_service.require_customer(conn, tenant, str(customer))
    if kind == "conversations":
        return conversations(conn, tenant, customer)
    return messages(conn, tenant, customer, **options)


def users(conn, tenant: str, default_limit: int, *, page: int = 1, q: str = "",
          match: str = "contains", status: str = "all", quick: str = "all",
          sort: str = "lastUsed", direction: str = "desc") -> dict:
    day = datetime.now(UTC).astimezone(admin_service.KST).date().isoformat()
    default_limit = admin_service.record(conn, tenant, "settings", "limits").get("chatLimit", default_limit)
    # Aggregate before sorting/paging so records outside the snapshot's 500 rows remain reachable.
    base = sql.SQL("""
        WITH usage AS (
            SELECT who, COALESCE(sum(used) FILTER(WHERE action='message'),0) AS chat,
                   COALESCE(sum(used),0) AS web, jsonb_object_agg(action,used) AS paths
            FROM (SELECT who,action,sum(used) AS used FROM web_usage
                  WHERE tenant_id=%s AND who_kind='key' AND period=%s GROUP BY who,action) u
            GROUP BY who
        ), activity AS (
            SELECT customer_id,max(last_used_at) AS last_used FROM (
                SELECT customer_id,last_used_at FROM web_user_keys WHERE tenant_id=%s
                UNION ALL SELECT customer_id,last_used_at FROM web_sessions WHERE tenant_id=%s
            ) a GROUP BY customer_id
        ), base AS (
            SELECT c.customer_id::text AS id,c.created_at,a.last_used,
                COALESCE((p.value->>'blocked')::boolean,false) AS blocked,
                COALESCE(u.chat,0) AS chat,COALESCE(u.web,0) AS web,u.paths,
                CASE WHEN p.value->>'exceptionPeriod'='today' AND
                    (p.value->>'exceptionDay') IS DISTINCT FROM %s THEN NULL
                    ELSE (p.value->>'exceptionLimit')::bigint END AS exception_limit,
                p.value->>'exceptionPeriod' AS exception_period,
                (SELECT count(*) FROM trips t WHERE t.tenant_id=c.tenant_id
                    AND t.customer_id=c.customer_id) AS trip_count,
                (SELECT count(*) FROM admin_records r WHERE r.tenant_id=c.tenant_id
                    AND r.kind='inquiry' AND r.customer_id=c.customer_id) AS inquiry_count
            FROM customers c LEFT JOIN activity a ON a.customer_id=c.customer_id
                LEFT JOIN usage u ON u.who=c.customer_id::text
                LEFT JOIN admin_records p ON p.tenant_id=c.tenant_id AND p.kind='user'
                    AND p.id=c.customer_id::text
            WHERE c.tenant_id=%s
        ) SELECT * FROM base WHERE (CASE WHEN %s='exact' THEN id=lower(%s) ELSE strpos(lower(id),lower(%s))>0 END)
          AND (%s='all' OR blocked=(%s='blocked'))
          AND (%s!='limit' OR (COALESCE(exception_limit,%s)>0 AND chat>=COALESCE(exception_limit,%s)))
          AND (%s!='inquiry' OR inquiry_count>0)
    """)
    params = (tenant, f"day:{day}", tenant, tenant, day, tenant, match, q, q,
              status, status, quick, default_limit, default_limit, quick)
    with conn.cursor() as cur:
        # Both count and page use one MVCC snapshot, including empty or out-of-range pages.
        query = sql.SQL("""WITH filtered AS ({}), totals AS (SELECT count(*) AS total FROM filtered),
            paged AS (SELECT * FROM filtered ORDER BY {} {} NULLS LAST,id ASC
                LIMIT %s OFFSET LEAST(%s,GREATEST(0,((SELECT total FROM totals)-1)/%s)*%s))
            SELECT totals.total,COALESCE(jsonb_agg(to_jsonb(paged) ORDER BY {} {} NULLS LAST,paged.id ASC)
                FILTER(WHERE paged.id IS NOT NULL),'[]'::jsonb) FROM totals LEFT JOIN paged ON true
            GROUP BY totals.total""").format(base, sql.Identifier(SORT_COLUMNS[sort]), sql.SQL(direction.upper()),
                                              sql.Identifier("paged", SORT_COLUMNS[sort]), sql.SQL(direction.upper()))
        cur.execute(query, (*params, USER_PAGE_SIZE, (page-1)*USER_PAGE_SIZE, USER_PAGE_SIZE, USER_PAGE_SIZE))
        total, rows = cur.fetchone()
        ids = [row["id"] for row in rows]
        cur.execute("SELECT t.customer_id,t.trip_id,t.title,t.status,count(i.item_id) FROM trips t "
                    "LEFT JOIN itinerary_items i ON i.tenant_id=t.tenant_id AND i.trip_id=t.trip_id "
                    "AND i.version=t.latest_version WHERE t.tenant_id=%s AND t.customer_id=ANY(%s::uuid[]) "
                    "GROUP BY t.customer_id,t.trip_id,t.title,t.status ORDER BY t.trip_id", (tenant, ids))
        trips = {}
        for customer, tid, title, trip_status, places in cur.fetchall():
            trips.setdefault(str(customer), []).append({"id": str(tid), "title": title, "status": trip_status, "places": places})
    return {"users": [{"id": r["id"], "blocked": r["blocked"], "issuedAt": r["created_at"],
                       "lastUsed": r["last_used"] or "사용 기록 없음", "chat": int(r["chat"]), "web": int(r["web"]),
                       "exceptionLimit": r["exception_limit"],
                       "exceptionPeriod": r["exception_period"] if r["exception_limit"] is not None else None,
                       "trips": trips.get(r["id"], []), "inquiryCount": r["inquiry_count"],
                       "paths": [{"path": a, "count": int(n)} for a, n in (r["paths"] or {}).items()]} for r in rows],
            **pagination(total, page, USER_PAGE_SIZE)}


def conversations(conn, tenant: str, customer) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT t.trip_id,t.title,count(c.turn_id),min(c.created_at),max(c.created_at) "
                    "FROM trips t JOIN trip_chat_turns c ON c.tenant_id=t.tenant_id AND c.trip_id=t.trip_id "
                    "WHERE t.tenant_id=%s AND t.customer_id=%s GROUP BY t.trip_id,t.title "
                    "ORDER BY max(c.created_at) DESC,t.trip_id", (tenant, customer))
        rows = cur.fetchall()
    return {"conversations": [{"id": str(tid), "title": title, "total": count,
                               "firstAt": first.isoformat(), "lastAt": last.isoformat()}
                              for tid, title, count, first, last in rows]}


def messages(conn, tenant: str, customer, *, trip_id, page: int = 1) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM trips WHERE tenant_id=%s AND customer_id=%s AND trip_id=%s", (tenant, customer, trip_id))
        if cur.fetchone() is None:
            raise admin_service.AdminServiceError(404, "이 사용자의 여행을 찾을 수 없습니다.")
        cur.execute("SELECT count(*) FROM trip_chat_turns WHERE tenant_id=%s AND trip_id=%s", (tenant, trip_id))
        meta = pagination(cur.fetchone()[0], page, MESSAGE_PAGE_SIZE)
        cur.execute("SELECT turn_id,role,text,created_at FROM trip_chat_turns WHERE tenant_id=%s AND trip_id=%s "
                    "ORDER BY turn_id ASC LIMIT %s OFFSET %s", (tenant, trip_id, MESSAGE_PAGE_SIZE, (meta["page"]-1)*MESSAGE_PAGE_SIZE))
        rows = cur.fetchall()
    return {"messages": [{"id": str(tid), "role": role, "text": masked(text), "at": at.isoformat()}
                         for tid, role, text, at in rows], **meta}


def pagination(total: int, page: int, size: int) -> dict:
    pages = max(1, (total+size-1)//size)
    return {"total": total, "page": min(page, pages), "pageSize": size, "pages": pages}
