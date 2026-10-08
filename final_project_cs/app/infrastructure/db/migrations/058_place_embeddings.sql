-- 058 — 관광공사 목록 장소의 임베딩(1024차원, bge-m3). `[2026-10-07 사용자 결정 — uiux 전달]`
--
-- ★왜. 후보를 고를 때 분류 나무(규칙)가 못 가르는 **취향의 가까움**(일정에 담은 곳들과 이름 · 종류가 얼마나 닮았나)과, 분류가 비어 있는 장소의 **분류 추정**(가장 닮은 목록 장소들의 분류 투표)에
--   쓴다. 목록 장소마다 **한 번 만들어 저장**한다(`scripts/embed_place_catalog.py`, 기본은 건수만 세는 dry-run). 요청 자리에서 장소를 임베딩하지 않는다.
-- ★임베딩 글은 장소 이름 + 관광공사 종류 이름뿐이다(주소 · 소개글 · 사진 없음 — 창작물을 모델에 먹이지 않는다). `text_sha` 가 바뀌면(이름이 바뀌면) 다시 만든다.
-- ★모델 이름을 같이 둔다 — 다른 모델로 바꾸면 벡터가 섞이지 않게 `model` 이 열쇠에 든다.
-- ☆재실행해도 안전하다. 벡터가 비어 있는 DB(확장 없음)에서는 이 표가 안 만들어져도 후보 고르기는 규칙만으로 돈다.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS place_embeddings (
    tenant_id  text NOT NULL,
    content_id text NOT NULL,
    model      text NOT NULL,
    text_sha   text NOT NULL,
    embedding  vector(1024) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, content_id, model)
);
