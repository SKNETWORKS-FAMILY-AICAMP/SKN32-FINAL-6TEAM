"""분류가 비어 있는 장소(우리 장소 표의 활동 행)의 분류를 한 번 채워 저장한다. `[2026-10-07 사용자 결정 — uiux 전달]`

    python -m scripts.fill_place_classes                    # 기본: 센 값과 결정 표본만 본다(dry-run)
    python -m scripts.fill_place_classes --apply [--limit N] [--no-embedding]

★두 길 — ①이름이 같은 목록 항목이 있으면 그 분류(`name_match`) ②없으면 임베딩 투표로 **짐작**(`estimated`, `place_embeddings` 가 채워져 있어야 한다 — 먼저 `scripts.embed_place_catalog`).
  짐작한 값은 늘 `estimated` 로 적고 후보 이유 문장에 「관광공사 분류」라고 쓰지 않는다. 투표가 갈리거나 닮은 정도가 낮으면 모른다고 둔다(`unknown`).
★목록의 분류(`source_content_type_id`)가 있는 행은 건드리지 않는다. 저장은 `places.attributes.inferred_class` 한 칸. 출력에는 건수와 장소 이름 표본(공개 장소 이름)만 낸다.
"""
from __future__ import annotations

import argparse

from app.core.settings import get_settings
from app.domains.travel_ops.components.intake import class_fill, embeddings
from app.domains.travel_ops.components.places.catalog_pool import _catalog_tenants
from app.infrastructure.db.session import get_connection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="실제로 저장한다(안 주면 세기만)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-embedding", action="store_true", help="이름 일치만 한다(모델 서버를 안 부른다)")
    args = parser.parse_args()
    tenants = _catalog_tenants(get_settings().tenant_id)
    embed = None if args.no_embedding else embeddings.ollama_embedder()
    with get_connection() as conn:
        result = class_fill.fill_places(conn, tenants, embed, limit=args.limit, dry_run=not args.apply)
    print({"mode": "apply" if args.apply else "dry_run", **{k: v for k, v in result.items() if k != "decisions"}})
    for name, lcls, grade in result["decisions"]:
        print("  ", name, lcls, grade)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
