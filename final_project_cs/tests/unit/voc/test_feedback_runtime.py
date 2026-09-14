from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.application.feedback_job import run_daily_feedback
from app.infrastructure.db.session import get_connection


def test_real_cases_trigger_voc_surge_and_boundary_does_not():
    report_date = date(2026, 8, 12)
    tenant = "test_voc_runtime_" + uuid4().hex
    customer = uuid4()
    with get_connection() as conn:
        try:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)", (tenant, "VOC runtime"))
                    cur.execute("INSERT INTO customers (customer_id,tenant_id,external_id) VALUES (%s,%s,%s)", (customer, tenant, "voc-runtime"))
                    for index in range(6):
                        cur.execute("""INSERT INTO customer_cases (tenant_id,customer_id,status,subject,intent,issue_code,sentiment,created_at)
                                       VALUES (%s,%s,'running',%s,'billing','runtime_surge','negative',%s)""",
                                    (tenant, customer, f"today-{index}", datetime(2026, 8, 12, 12, index, tzinfo=timezone.utc)))
                    for index in range(2):
                        cur.execute("""INSERT INTO customer_cases (tenant_id,customer_id,status,subject,intent,issue_code,sentiment,created_at)
                                       VALUES (%s,%s,'running',%s,'billing','runtime_surge','negative',%s)""",
                                    (tenant, customer, f"prior-{index}", datetime(2026, 8, 10, 12, index, tzinfo=timezone.utc)))
            with conn.transaction():
                alert_report = run_daily_feedback(conn, report_date=report_date, tenant_id=tenant)
            assert alert_report["alerts"]

            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
                    # today=4 is below the minimum-count condition (5).
                    for index in range(4):
                        cur.execute("""INSERT INTO customer_cases (tenant_id,customer_id,status,subject,intent,issue_code,sentiment,created_at)
                                       VALUES (%s,%s,'running',%s,'billing','runtime_boundary','negative',%s)""",
                                    (tenant, customer, f"boundary-today-{index}", datetime(2026, 8, 12, 12, index, tzinfo=timezone.utc)))
                    for index in range(7):
                        cur.execute("""INSERT INTO customer_cases (tenant_id,customer_id,status,subject,intent,issue_code,sentiment,created_at)
                                       VALUES (%s,%s,'running',%s,'billing','runtime_boundary','negative',%s)""",
                                    (tenant, customer, f"boundary-prior-{index}", datetime(2026, 8, 10, 12, index, tzinfo=timezone.utc)))
            with conn.transaction():
                boundary_report = run_daily_feedback(conn, report_date=report_date, tenant_id=tenant)
            assert not boundary_report["alerts"]
        finally:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM outbox WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM feedback_analytics_reports WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM customers WHERE tenant_id=%s", (tenant,))
                    cur.execute("DELETE FROM tenants WHERE tenant_id=%s", (tenant,))
