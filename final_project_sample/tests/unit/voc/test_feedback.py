from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from acop_basement.application.feedback_job import is_surge, run_daily_feedback
from acop_basement.infrastructure.db.session import get_connection
from app.modules.customer_ops.feedback import ClassificationFailed, classify


def test_classifier_returns_all_four_fields_from_injected_llm():
    result = classify(
        "결제가 실패했어요",
        lambda _: {"sentiment": "negative", "intent": "billing", "issue_code": "payment_failed", "severity": "high"},
    )
    assert result.sentiment == "negative"
    assert result.intent == "billing"
    assert result.issue_code == "payment_failed"
    assert result.severity == "high"


@pytest.mark.parametrize("missing", ["sentiment", "intent", "issue_code", "severity"])
def test_classifier_fails_when_any_field_is_missing(missing):
    value = {"sentiment": "neutral", "intent": "other", "issue_code": "other", "severity": "low"}
    value.pop(missing)
    with pytest.raises(ClassificationFailed):
        classify("문의", lambda _: value)


def test_surge_boundary_requires_both_conditions():
    assert not is_surge(5, 4)  # ratio passes; absolute difference fails
    assert not is_surge(6, 4.1)  # absolute difference passes; ratio fails
    assert is_surge(7, 4.0)  # exactly on both boundaries: alert
    assert is_surge(8, 4.0)


def test_batch_is_tenant_scoped_and_idempotent():
    report_date = date(2026, 8, 12)
    tenant = "voc_test_" + uuid4().hex
    other_tenant = "voc_other_" + uuid4().hex
    with get_connection() as conn:
        try:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.executemany("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", [(tenant, "voc"), (other_tenant, "other")])
                    customers = []
                    for t in (tenant, other_tenant):
                        cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) RETURNING customer_id", (t, uuid4().hex))
                        customers.append(cur.fetchone()[0])
                    for t, customer in zip((tenant, other_tenant), customers):
                        cur.execute(
                            """INSERT INTO customer_cases (tenant_id,customer_id,status,subject,intent,issue_code,sentiment,created_at)
                               VALUES (%s,%s,'running','voc','billing','payment_failed','negative',%s)""",
                            (t, customer, datetime(2026, 8, 12, 12, tzinfo=timezone.utc)),
                        )
            with conn.transaction():
                first = run_daily_feedback(conn, report_date=report_date, tenant_id=tenant)
            with conn.transaction():
                second = run_daily_feedback(conn, report_date=report_date, tenant_id=tenant)
            assert first["metrics"]["totals"]["today"] == 1
            assert second["metrics"] == first["metrics"]
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM feedback_analytics_reports WHERE tenant_id=%s", (tenant,))
                assert cur.fetchone()[0] == 1
                cur.execute("SELECT count(*) FROM feedback_analytics_reports WHERE tenant_id=%s", (other_tenant,))
                assert cur.fetchone()[0] == 0
        finally:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM outbox WHERE tenant_id IN (%s,%s)", (tenant, other_tenant))
                    cur.execute("DELETE FROM feedback_analytics_reports WHERE tenant_id IN (%s,%s)", (tenant, other_tenant))
                    cur.execute("DELETE FROM case_events WHERE tenant_id IN (%s,%s)", (tenant, other_tenant))
                    cur.execute("DELETE FROM customer_cases WHERE tenant_id IN (%s,%s)", (tenant, other_tenant))
                    cur.execute("DELETE FROM customers WHERE tenant_id IN (%s,%s)", (tenant, other_tenant))
                    cur.execute("DELETE FROM tenants WHERE tenant_id IN (%s,%s)", (tenant, other_tenant))
