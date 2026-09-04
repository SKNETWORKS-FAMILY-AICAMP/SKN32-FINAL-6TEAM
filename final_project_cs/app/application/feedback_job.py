"""Tenant-scoped daily S-VOC analytics job."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from psycopg import Connection
from psycopg.types.json import Json

from app.core.transition import OutboxMessage


def _count(rows: list[tuple[str, str]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for intent, issue in rows:
        result.setdefault(intent, {}).setdefault(issue, 0)
        result[intent][issue] += 1
    return result


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def is_surge(today: int, avg7: float) -> bool:
    """§4 verbatim: both the ratio and absolute-difference conditions apply.

    ★수치는 가드레일에서 읽는다. 전에는 5·1.5·3 이 여기 박혀 있어
      `feedback_analytics.surge_*` 를 고쳐도 판정이 안 바뀌었다 —
      급증 기준을 조정한 줄 알게 되는 종류다(2026-09-03).
    """
    from app.core.settings import get_guardrails

    g = get_guardrails()
    min_count = float(g.get("feedback_analytics.surge_min_count"))
    ratio = float(g.get("feedback_analytics.surge_ratio"))
    min_delta = float(g.get("feedback_analytics.surge_min_delta"))
    return today >= max(min_count, ratio * avg7) and today - avg7 >= min_delta


def run_daily_feedback(conn: Connection, *, report_date: date, tenant_id: str) -> dict[str, Any]:
    """Upsert one report for one tenant and publish alerts transactionally.

    ★**집계·급증 탐지는 코어 1 소유다** — `voc` 모듈 소관이 아니다.

      v8 §7 재판정이 VOC 를 **관측층과 판단층**으로 나눴다. 집계와 급증 탐지는
      코어 1 이 갖고, VOC Team 은 그 결과를 받아 "왜 늘었고, 누가 받아야 하고,
      진짜 알릴 일인가" 를 판단하는 껍데기로 남는다. §16 도 "Feedback Analytics
      집계 배치" 를 코어 1 책임으로 적는다.

      ★그래서 2026-09-01 에 `require_module("voc", ...)` 를 뺐다. 인라인 분류와
      **똑같은 범주 오류**였다 — 상시 관측 기능을 선택 계층에 매달아 둔 것이다.
      `voc: false` 는 판단층(Team)과 화면을 끈다는 뜻이지 관측을 멈추라는 뜻이
      아니다.

      ★대가는 정직하게 적는다: `voc` 를 꺼도 `feedback_analytics_reports` 는
      계속 쌓인다. "꺼 놓은 화면에 데이터가 쌓인다" 는 말은 맞다. 다만 관측을
      멈추면 나중에 판단층을 켰을 때 **그동안의 시계열이 비어 있다.** 급증은
      과거 7일 평균과 견주는 것이라 공백은 되돌릴 수 없다. 둘 중 후자가 더 나쁘다.
    """
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
