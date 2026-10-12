"""Export PostgreSQL structure without reading customer rows or changing the DB.

Run inside the cs project environment (PYTHONPATH points to final_project_cs).
Output contains schema metadata only; connection settings are never exported.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

OLD_TABLES = ["orders", "order_items", "shipments", "returns", "products"]


def collect(dsn: str) -> dict:
    with psycopg.connect(
        dsn.replace("postgresql+psycopg://", "postgresql://", 1),
        connect_timeout=8, row_factory=dict_row,
        options="-c default_transaction_read_only=on -c statement_timeout=15000",
    ) as conn:
        def query(sql):
            return conn.execute(sql).fetchall()

        scope = "n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'"
        tables = query(f"""SELECT n.nspname AS schema, c.relname AS name,
            c.relkind AS kind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE {scope} AND c.relkind IN ('r','p','v','m','f') ORDER BY 1,2""")
        columns = query(f"""SELECT n.nspname AS schema,c.relname AS table_name,
            a.attnum AS position,a.attname AS name,format_type(a.atttypid,a.atttypmod) AS type,
            a.attnotnull AS not_null FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE {scope} AND c.relkind IN ('r','p','v','m','f')
            AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3""")
        constraints = query(f"""SELECT n.nspname AS schema,c.relname AS table_name,
            k.conname AS name,k.contype AS type,k.convalidated AS validated,
            pg_get_constraintdef(k.oid,true) AS definition
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE {scope} ORDER BY 1,2,3""")
        indexes = query(f"""SELECT n.nspname AS schema,c.relname AS table_name,
            ic.relname AS name,i.indisunique AS unique,i.indisvalid AS valid
            FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid
            JOIN pg_class ic ON ic.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE {scope} ORDER BY 1,2,3""")
        routines = query(f"""SELECT n.nspname AS schema,p.proname AS name,
            p.prosrc ~* '\\m(orders|order_items|shipments|returns|products)\\M' AS legacy_token_hit
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE {scope} AND NOT EXISTS (SELECT 1 FROM pg_depend d
                WHERE d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.deptype='e')
            ORDER BY 1,2""")
        triggers = query(f"""SELECT n.nspname AS schema,c.relname AS table_name,t.tgname AS name,
            t.tgenabled AS enabled,p.proname AS function_name
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid
            WHERE {scope} AND NOT t.tgisinternal ORDER BY 1,2,3""")
        old_columns = [c for c in columns if c['name'] in ('order_id','order_item_id','shipment_id','sku','product_id','return_id')]
        return {
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "transaction_read_only": conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'],
            "scope": "All non-system schemas; tables, views, columns, constraints, indexes, non-extension routines and triggers. No business rows.",
            "tables": tables, "columns": columns, "constraints": constraints,
            "indexes": indexes, "routines": routines, "triggers": triggers,
            "legacy_exact_table_names_checked": OLD_TABLES,
            "legacy_tables": [t for t in tables if t['name'] in OLD_TABLES],
            "legacy_columns": old_columns,
            "legacy_routine_candidates": [r for r in routines if r['legacy_token_hit']],
            "limits": ["Different names or business values inside JSON/rows require a separate semantic/data audit.",
                       "SQL-file presence does not prove application in this environment."],
        }


if __name__ == '__main__':
    from app.core.settings import get_settings
    try:
        print(json.dumps(collect(get_settings().database_url), ensure_ascii=False, default=str))
    except Exception as exc:
        print(json.dumps({"error_type": type(exc).__name__, "sqlstate": getattr(exc,'sqlstate',None),
                          "captured_at_utc": datetime.now(timezone.utc).isoformat()}))
        raise SystemExit(1)
