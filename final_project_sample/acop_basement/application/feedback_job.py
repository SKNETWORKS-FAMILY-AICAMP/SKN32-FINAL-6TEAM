"""Tenant-scoped daily S-VOC analytics job."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from psycopg import Connection
from psycopg.types.json import Json

from acop_basement.core.transition import OutboxMessage


def _count(rows: list[tuple[str, str]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for intent, issue in rows:
        result.setdefault(intent, {}).setdefault(issue, 0)
        result[intent][issue] += 1
    return result


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def is_surge(today: int, avg7: float) -> bool:
    """§4 verbatim: both the ratio and absolute-difference conditions apply."""
    return today >= max(5, 1.5 * avg7) and today - avg7 >= 3


def run_daily_feedback(conn: Connection, *, report_date: date, tenant_id: str) -> dict[str, Any]:
    """Upsert one report for one tenant and publish alerts transactionally.

    ★`voc` 모듈이 꺼져 있으면 리포트를 쓰지 않고 실패한다. 배치가 조용히 돌면
      꺼 놓은 화면에 데이터만 쌓인다. 모듈을 빼면 그것을 부르는 경로도 함께
      빠져야 한다(`RULE.md` §3.2 — 신호 없는 축소는 폴백이다).
    """
    from acop_basement.application.config_source import load_active_config

    load_active_config().require_module("voc", "daily feedback analytics job")
    start = report_date - timedelta(days=7)
    with conn.cursor() as cur:
        cur.execute(
            """SELECT intent, issue_code, sentiment, status, created_at::date
               FROM customer_cases
               WHERE tenant_id=%s AND created_at >= %s AND created_at < %s + 1
                 AND intent IS NOT NULL AND issue_code IS NOT NULL AND sentiment IS NOT NULL""",
            (tenant_id, start, report_date),
        )
        rows = cur.fetchall()
    today_rows = [(i, c, s, st) for i, c, s, st, d in rows if d == report_date]
    prior_rows = [(i, c, s, st) for i, c, s, st, d in rows if start <= d < report_date]
    today_counts = _count([(i, c) for i, c, _, _ in today_rows])
    prior_counts = _count([(i, c) for i, c, _, _ in prior_rows])
    today_total, prior_total = len(today_rows), len(prior_rows)
    metrics = {
        "intent_issue_count": {"today": today_counts, "prior_7_days": prior_counts},
        "negative_ratio": {"today": _ratio(sum(s == "negative" for _, _, s, _ in today_rows), today_total),
                            "prior_7_days": _ratio(sum(s == "negative" for _, _, s, _ in prior_rows), prior_total)},
        "unresolved_ratio": {"today": _ratio(sum(st not in {"resolved", "cancelled"} for _, _, _, st in today_rows), today_total),
                              "prior_7_days": _ratio(sum(st not in {"resolved", "cancelled"} for _, _, _, st in prior_rows), prior_total)},
        "totals": {"today": today_total, "prior_7_days": prior_total},
    }
    alerts: list[dict[str, Any]] = []
    for intent, issues in today_counts.items():
        for issue, today in issues.items():
            avg7 = prior_counts.get(intent, {}).get(issue, 0) / 7
            # §4: today >= max(5, 1.5*avg7) AND today - avg7 >= 3
            if is_surge(today, avg7):
                alerts.append({"intent": intent, "issue_code": issue, "today": today, "avg7": avg7})
    report = {"tenant_id": tenant_id, "period_start": start.isoformat(), "period_end": report_date.isoformat(), "metrics": metrics, "alerts": alerts}
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO feedback_analytics_reports
               (tenant_id, period_start, period_end, metrics_json, alerts_json)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (tenant_id, period_start, period_end) DO UPDATE SET
                 metrics_json=EXCLUDED.metrics_json, alerts_json=EXCLUDED.alerts_json""",
            (tenant_id, start, report_date, Json(metrics), Json(alerts)),
        )
        for alert in alerts:
            cur.execute(
                """INSERT INTO outbox (tenant_id, topic, dedupe_key, payload_json)
                   VALUES (%s,%s,%s,%s) ON CONFLICT (tenant_id,topic,dedupe_key) DO NOTHING""",
                (tenant_id, "feedback.alert", f"{tenant_id}:{start}:{report_date}:{alert['intent']}:{alert['issue_code']}", Json(report | {"alert": alert})),
            )
    return report
