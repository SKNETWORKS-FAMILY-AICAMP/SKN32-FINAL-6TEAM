"""관광공사 목록 장소의 임베딩을 만들어 `place_embeddings` 에 저장한다. `[2026-10-07 사용자 결정 — uiux 전달]` 마이그레이션 058

    python -m scripts.embed_place_catalog                  # 기본: 만들 건수만 센다(dry-run) — 아무것도 안 쓴다
    python -m scripts.embed_place_catalog --apply --limit 500

★임베딩 글 = 장소 이름 + 관광공사 종류 이름뿐이다(주소 · 소개글 · 사진 없음). 쇼핑 · 음식 가지(SH · FD)는 만들지 않는다(취향 · 분류 추정에 안 쓴다 — 약국 · 편의점 4,440곳을 만들지 않는다).
★모델은 설정 `ollama_embedding_model`(bge-m3, 1024차원) — Ollama `/api/embed` 를 부른다. 모델 서버에 닿지 않으면 **예외로 멈춘다**(빈 벡터를 쓰지 않는다).
★이미 만든 것은 건너뛴다(이름이 바뀌면 다시). 출력에는 건수만 낸다.
"""
from __future__ import annotations

import argparse

from app.core.settings import get_settings
from app.domains.travel_ops.components.intake import embeddings
from app.domains.travel_ops.components.places.catalog_pool import _catalog_tenants
from app.infrastructure.db.session import get_connection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="실제로 만들어 저장한다(안 주면 건수만 센다)")
    parser.add_argument("--limit", type=int, default=None, help="이번에 만들 최대 건수")
    args = parser.parse_args()
    tenants = _catalog_tenants(get_settings().tenant_id)
    with get_connection() as conn:
        result = embeddings.fill_catalog(conn, tenants, embeddings.ollama_embedder() if args.apply else (lambda texts: []),
                                         limit=args.limit, dry_run=not args.apply)
    print({"mode": "apply" if args.apply else "dry_run", **result, "model": embeddings.model_name()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
