# -*- coding: utf-8 -*-
"""개발 DB 에서 **기준 데이터만** 떠서 서버 DB 에 넣을 SQL 한 파일(gzip)을 만든다. `[2026-10-03]`

    python deploy/export_reference_data.py --out reference_data.sql.gz

★무엇을 뜨고 무엇을 안 뜨나(사용자 결정 2026-10-03 「통으로」를 **사용자 데이터만 빼고** 지켰다):
  뜬다   장소 목록(관광공사) · 영업시간 · 정책 지식 문서와 조각(임베딩 포함) · 활성 프롬프트 · 요식 원장(`dining` 스키마 전체) · 공용 장소(여행에 안 묶인 `places`) · 기본 테넌트 한 행
  안 뜬다 고객 · 여행 · 일정 · 채팅 기록 · 접수 · Case · 바깥함 · 사용자 키 · 프로필(복구 이메일 · 암호화된 디스코드 웹훅) · 외부 호출 기록 · 테스트가 남긴 테넌트 371개
  ☆이유: 개발 DB 에 개인정보라고 할 것이 **없다고 단정하지 않았다** — 실제로 복구 이메일 칸 · 암호화된 웹훅 칸 · 사용자 키 해시 · 채팅 7천 행이 있다. 공개 서버에는 추천 품질을 만드는 **기준 데이터**만 필요하다.
★서버 DB 의 표 구조는 이 파일이 아니라 **마이그레이션**(`python -m app.infrastructure.db.migrate`)이 만든다 — 이 파일은 데이터만 넣는다.
★외래키 검사는 넣는 동안만 끈다(`session_replication_role = replica`, 서버 DB 의 슈퍼유저로 넣는다).
"""
from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path

CS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CS_ROOT))

import psycopg  # noqa: E402

from app.core.settings import get_settings  # noqa: E402
from app.infrastructure.db.session import database_dsn  # noqa: E402

#: (표, 거르는 조건). 조건 `{tenant}` 는 기본 테넌트로 채운다. 순서 = 부모 → 자식(외래키 검사를 꺼도 읽기 쉽게).
PUBLIC_TABLES: list[tuple[str, str | None]] = [
    ("tenants", "tenant_id = '{tenant}'"),
    ("prompts", None),
    ("knowledge_documents", "tenant_id = '{tenant}'"),
    ("knowledge_chunks", "document_id IN (SELECT document_id FROM knowledge_documents WHERE tenant_id = '{tenant}')"),
    ("place_catalog", "tenant_id = '{tenant}'"),
    ("catalog_hours", "tenant_id = '{tenant}'"),
    ("source_sync_state", "tenant_id = '{tenant}'"),
    # ★`place_aliases` 는 뺀다 — 고객이 쓴 말을 배운 별칭(`source=customer`)이라 사용자 데이터다(서버에 가면 제약 위반으로 적재도 막혔다)
    ("cancellation_terms", "tenant_id = '{tenant}'"),
    ("places", "tenant_id = '{tenant}' AND trip_scope IS NULL"),
]


def copy_out(cur, table: str, where: str | None, out) -> int:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
                (table.split(".")[0] if "." in table else "public", table.split(".")[-1]))
    columns = [row[0] for row in cur.fetchall()]
    query = f"SELECT {', '.join(columns)} FROM {table}" + (f" WHERE {where}" if where else "")
    quoted = ", ".join(f'"{c}"' for c in columns)
    # ★마이그레이션이 기본 행(요식 출처 코드 · 기본 테넌트 등)을 이미 넣는다 — 같은 키가 겹치므로 **넣기 전에 그 표를 비운다**(빈 DB 에 처음 넣을 때만 쓰는 파일이다. 외래키 검사는 위에서 껐다)
    out.write(f"DELETE FROM {table};\n".encode("utf-8"))
    out.write(f"COPY {table} ({quoted}) FROM STDIN;\n".encode("utf-8"))
    rows = 0
    with cur.copy(f"COPY ({query}) TO STDOUT") as copy:
        for chunk in copy:
            out.write(bytes(chunk))
    out.write(b"\\.\n\n")
    cur.execute(f"SELECT count(*) FROM ({query}) q")
    rows = cur.fetchone()[0]
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    tenant = get_settings().tenant_id
    counts: dict[str, int] = {}
    with psycopg.connect(database_dsn()) as conn, conn.cursor() as cur, gzip.open(args.out, "wb") as out:
        out.write(b"SET client_encoding = 'UTF8';\nSET session_replication_role = replica;\nBEGIN;\n\n")
        for table, where in PUBLIC_TABLES:
            counts[table] = copy_out(cur, table, where.format(tenant=tenant) if where else None, out)
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'dining' AND table_type = 'BASE TABLE' ORDER BY 1")
        for (name,) in cur.fetchall():
            counts[f"dining.{name}"] = copy_out(cur, f"dining.{name}", None, out)
        out.write(b"COMMIT;\nANALYZE;\n")
    for name, rows in counts.items():
        print(f"{name:34s} {rows:>7,}행")
    print(f"합계 {sum(counts.values()):,}행 → {Path(args.out).name} (기본 테넌트 '{tenant}' 만)")


if __name__ == "__main__":
    main()
