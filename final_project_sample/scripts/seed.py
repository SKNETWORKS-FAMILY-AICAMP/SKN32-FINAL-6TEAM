"""Deterministic demo fixtures for the S-DB contract and customer scenarios."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid5

from acop_basement.infrastructure.db.repository import create_case
from acop_basement.infrastructure.db.session import get_connection

DEMO = "demo"
NAMESPACE = UUID("00000000-0000-0000-0000-000000000001")


def stable(name: str) -> UUID:
    return uuid5(NAMESPACE, name)


def at(day: date, hour: int = 12) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=timezone.utc)


def ensure_customer(conn, external_id: str, email_hash: str) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO customers (tenant_id, external_id, email_hash)
               VALUES (%s,%s,%s)
               ON CONFLICT (tenant_id, external_id)
               DO UPDATE SET email_hash=EXCLUDED.email_hash
               RETURNING customer_id""",
            (DEMO, external_id, email_hash),
        )
        return cur.fetchone()[0]


def ensure_case(conn, customer_id: UUID, subject: str) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT case_id FROM customer_cases WHERE tenant_id=%s AND customer_id=%s AND subject=%s",
            (DEMO, customer_id, subject),
        )
        row = cur.fetchone()
    return row[0] if row else create_case(conn, tenant_id=DEMO, customer_id=customer_id, subject=subject)


def main() -> None:
    today = date(2026, 8, 12)
    with get_connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenants (tenant_id,name) VALUES (%s,%s) "
                "ON CONFLICT (tenant_id) DO UPDATE SET name=EXCLUDED.name",
                (DEMO, "Nimbus"),
            )
        customers = [
            ensure_customer(conn, f"cust_{n:02d}", f"sha256:demo-cust-{n:02d}")
            for n in range(1, 11)
        ]

        # Exactly one deterministic subscription and entitlement per customer.
        plans = ["Free", "Pro", "Business", "Pro", "Business", "Free", "Pro", "Business", "Free", "Pro"]
        ended = {1: today - timedelta(days=8), 4: today - timedelta(days=6), 7: today - timedelta(days=4)}
        subscriptions: list[UUID] = []
        with conn.cursor() as cur:
            for n, customer_id in enumerate(customers, 1):
                subscription_id = stable(f"subscription:cust_{n:02d}")
                subscriptions.append(subscription_id)
                ended_at = at(ended[n], 9) if n in ended else None
                cur.execute(
                    """INSERT INTO subscriptions
                       (subscription_id,tenant_id,customer_id,plan,status,started_at,ended_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (subscription_id) DO UPDATE SET
                       tenant_id=EXCLUDED.tenant_id, customer_id=EXCLUDED.customer_id,
                       plan=EXCLUDED.plan, status=EXCLUDED.status,
                       started_at=EXCLUDED.started_at, ended_at=EXCLUDED.ended_at""",
                    (subscription_id, DEMO, customer_id, plans[n - 1], "cancelled" if ended_at else "active",
                     at(today - timedelta(days=30 + n)), ended_at),
                )

        # Three payments per customer, spread over the recent 14-day window.
        with conn.cursor() as cur:
            for n, (customer_id, subscription_id) in enumerate(zip(customers, subscriptions), 1):
                for payment_no in range(1, 4):
                    payment_id = stable(f"payment:cust_{n:02d}:{payment_no}")
                    paid_day = today - timedelta(days=((n * 2 + payment_no) % 14))
                    # Customer 01 has a payment after its cancellation timestamp.
                    if n == 1 and payment_no == 3:
                        paid_day = today - timedelta(days=2)
                    cur.execute(
                        """INSERT INTO payments
                           (payment_id,tenant_id,customer_id,subscription_id,amount_cents,status,paid_at)
                           VALUES (%s,%s,%s,%s,%s,'succeeded',%s)
                           ON CONFLICT (payment_id) DO UPDATE SET
                           tenant_id=EXCLUDED.tenant_id, customer_id=EXCLUDED.customer_id,
                           subscription_id=EXCLUDED.subscription_id, amount_cents=EXCLUDED.amount_cents,
                           status=EXCLUDED.status, paid_at=EXCLUDED.paid_at""",
                        (payment_id, DEMO, customer_id, subscription_id, 4900 + n * 100, at(paid_day, 10 + payment_no)),
                    )

        with conn.cursor() as cur:
            for n, (customer_id, subscription_id) in enumerate(zip(customers, subscriptions), 1):
                entitlement_plan = "Free" if n == 2 else plans[n - 1]
                cur.execute(
                    """INSERT INTO entitlements (entitlement_id,tenant_id,customer_id,plan,source,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (entitlement_id) DO UPDATE SET
                       tenant_id=EXCLUDED.tenant_id, customer_id=EXCLUDED.customer_id,
                       plan=EXCLUDED.plan, source=EXCLUDED.source, updated_at=EXCLUDED.updated_at""",
                    (stable(f"entitlement:cust_{n:02d}"), DEMO, customer_id, entitlement_plan,
                     "mock_stale_projection" if n == 2 else "mock", at(today, 8)),
                )

        # Three incidents, including the entitlement synchronization failure.
        incident_specs = [(2, "Entitlement mismatch: Pro subscription served as Free"),
                          (5, "Payment reconciliation delayed"), (8, "Subscription renewal webhook delayed")]
        with conn.cursor() as cur:
            for n, summary in incident_specs:
                case_id = ensure_case(conn, customers[n - 1], summary)
                cur.execute(
                    """INSERT INTO incidents (incident_id,tenant_id,customer_id,case_id,summary,status,created_at)
                       VALUES (%s,%s,%s,%s,%s,'open',%s)
                       ON CONFLICT (incident_id) DO UPDATE SET
                       tenant_id=EXCLUDED.tenant_id, customer_id=EXCLUDED.customer_id,
                       case_id=EXCLUDED.case_id, summary=EXCLUDED.summary,
                       status=EXCLUDED.status, created_at=EXCLUDED.created_at""",
                    (stable(f"incident:{n}"), DEMO, customers[n - 1], case_id, summary, at(today, 7)),
                )
    print("Seeded demo: 10 customers, 10 subscriptions, 30 payments, 10 entitlements, 3 incidents")


if __name__ == "__main__":
    main()
