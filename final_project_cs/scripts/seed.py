"""Idempotent demo data seed for the commerce domain."""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid5

from app.infrastructure.db.session import get_connection

DEMO = "demo"
NAMESPACE = UUID("00000000-0000-0000-0000-000000000001")

# Demo products cover the legacy catalog and pricing/status edge cases.
CATALOG = [
    ("SKU-TEE-01", "Basic cotton T-shirt", 19_900, "active"),
    ("SKU-CUP-02", "Insulated tumbler", 24_500, "active"),
    ("SKU-BAG-03", "Canvas bag", 32_000, "active"),
    ("SKU-SHO-04", "Leather shoes", 89_000, "active"),
    ("SKU-CAP-05", "Seasonal cap", 100, "discontinued"),
]
CARRIERS = ["CJ Logistics", "Lotte Global", "Hanjin"]


def stable(name: str) -> UUID:
    return uuid5(NAMESPACE, name)


def at(day: date, hour: int = 12) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=timezone.utc)


def load_catalog() -> list[tuple[str, str, int, str]]:
    """Read the canonical 9-row history and add the five demo products."""
    data_path = (Path(__file__).resolve().parents[2] / "datasets" / "commerce"
                 / "coupang_order_history" / "processed" / "orders.jsonl")
    products: list[tuple[str, str, int, str]] = []
    seen_names: set[str] = set()
    for line in data_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        product = json.loads(line)["product"]
        name = str(product["name"])
        if name in seen_names:
            continue
        seen_names.add(name)
        products.append((f"SKU-CPG-{len(products) + 1:02d}", name,
                         int(round(float(product["unit_price"]))), "active"))
    return products + CATALOG


def ensure_customer(conn, external_id: str, email_hash: str) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO customers (tenant_id, external_id, email_hash) VALUES (%s,%s,%s) "
            "ON CONFLICT (tenant_id, external_id) DO UPDATE SET email_hash=EXCLUDED.email_hash "
            "RETURNING customer_id",
            (DEMO, external_id, email_hash),
        )
        return cur.fetchone()[0]


def main() -> None:
    today = date(2026, 8, 16)
    catalog = load_catalog()
    with get_connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenants (tenant_id,name) VALUES (%s,%s) "
                "ON CONFLICT (tenant_id) DO UPDATE SET name=EXCLUDED.name",
                (DEMO, "Nimbus Mall"),
            )
            for sku, name, unit, status in catalog:
                cur.execute(
                    "INSERT INTO products (tenant_id,sku,name,unit_cents,status) VALUES (%s,%s,%s,%s,%s) "
                    "ON CONFLICT (tenant_id,sku) DO UPDATE SET name=EXCLUDED.name, "
                    "unit_cents=EXCLUDED.unit_cents, status=EXCLUDED.status, updated_at=now()",
                    (DEMO, sku, name, unit, status),
                )
            cur.execute(
                "SELECT sku, name, unit_cents FROM products WHERE tenant_id=%s AND status='active' ORDER BY sku",
                (DEMO,),
            )
            products = cur.fetchall()

        customers = [ensure_customer(conn, f"cust_{n:02d}", f"sha256:demo-cust-{n:02d}")
                     for n in range(1, 11)]
        orders: list[tuple[UUID, UUID, int, int]] = []
        with conn.cursor() as cur:
            for n, customer_id in enumerate(customers, 1):
                for seq in range(1, 4):
                    order_id = stable(f"order:cust_{n:02d}:{seq}")
                    sku, name, unit = products[(n + seq) % len(products)]
                    quantity = 1 + ((n + seq) % 3)
                    status = ["delivered", "shipped", "paid"][seq - 1]
                    ordered = today - timedelta(days=((n * 2 + seq) % 14))
                    cur.execute(
                        "INSERT INTO orders (order_id,tenant_id,customer_id,order_no,total_cents,item_count,status,ordered_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (order_id) DO UPDATE SET "
                        "total_cents=EXCLUDED.total_cents,item_count=EXCLUDED.item_count,status=EXCLUDED.status,ordered_at=EXCLUDED.ordered_at",
                        (order_id, DEMO, customer_id, f"ORD-{n:02d}{seq:02d}", unit * quantity,
                         quantity, status, at(ordered, 10)),
                    )
                    cur.execute(
                        "INSERT INTO order_items (order_item_id,tenant_id,order_id,sku,name,quantity,unit_cents) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (order_item_id) DO UPDATE SET "
                        "sku=EXCLUDED.sku,name=EXCLUDED.name,quantity=EXCLUDED.quantity,unit_cents=EXCLUDED.unit_cents",
                        (stable(f"item:cust_{n:02d}:{seq}"), DEMO, order_id, sku, name, quantity, unit),
                    )
                    orders.append((order_id, customer_id, unit * quantity, quantity))

        with conn.cursor() as cur:
            for idx, (order_id, customer_id, _total, _quantity) in enumerate(orders, 1):
                cur.execute("SELECT status, ordered_at FROM orders WHERE order_id=%s", (order_id,))
                status, ordered_at = cur.fetchone()
                if status == "paid":
                    continue
                shipped = ordered_at + timedelta(days=1)
                delivered = shipped + timedelta(days=2) if status == "delivered" else None
                cur.execute(
                    "INSERT INTO shipments (shipment_id,tenant_id,customer_id,order_id,carrier,tracking_no,status,shipped_at,delivered_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (shipment_id) DO UPDATE SET "
                    "status=EXCLUDED.status,delivered_at=EXCLUDED.delivered_at",
                    (stable(f"shipment:{order_id}"), DEMO, customer_id, order_id,
                     CARRIERS[idx % len(CARRIERS)], f"TRK{idx:09d}",
                     "delivered" if delivered else "in_transit", shipped, delivered),
                )

        with conn.cursor() as cur:
            normal_order, normal_customer, _total, normal_quantity = orders[6]
            cur.execute(
                "INSERT INTO returns (return_id,tenant_id,customer_id,order_id,reason_code,quantity,status) "
                "VALUES (%s,%s,%s,%s,'size_mismatch',%s,'requested') ON CONFLICT (return_id) DO UPDATE SET quantity=EXCLUDED.quantity",
                (stable("return:normal"), DEMO, normal_customer, normal_order, max(1, normal_quantity - 1)),
            )
            over_order, over_customer, _total, over_quantity = orders[9]
            cur.execute(
                "INSERT INTO returns (return_id,tenant_id,customer_id,order_id,reason_code,quantity,status) "
                "VALUES (%s,%s,%s,%s,'defective',%s,'requested') ON CONFLICT (return_id) DO UPDATE SET quantity=EXCLUDED.quantity",
                (stable("return:over"), DEMO, over_customer, over_order, over_quantity + 2),
            )

    with get_connection() as conn, conn.cursor() as cur:
        counts = {}
        for table in ("products", "customers", "orders", "order_items", "shipments", "returns"):
            cur.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=%s", (DEMO,))
            counts[table] = cur.fetchone()[0]
    print(counts)


if __name__ == "__main__":
    main()
