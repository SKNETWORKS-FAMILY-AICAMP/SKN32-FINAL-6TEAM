-- 028 — 고객 계획 읽기: 접수 · 원본 · 읽은 값 (설계서 §6, 2026-09-27)
--
-- ★★왜. 고객이 어떤 모양으로 올리든(붙여 넣은 글 · 채팅 문장 · PDF · 사진 · docx · xlsx) 읽어서
--   확인 화면을 거쳐 `_create_trip` 한 곳으로 등록한다. 설계서:
--   `program/plan/A-COP_고객계획_읽기_설계_2026-09-26.md` (triPilot : RAG 세션).
-- ★원칙 — **값 하나 = 행 하나**, 값마다 근거(원문의 줄·글자 범위, 또는 조회 결과)를 들고 다닌다.
--   모델이 낸 글자를 값으로 쓰지 않는다(`method` 가 그 출처를 말한다).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS trip_intakes (
    intake_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    text NOT NULL,
    customer_id  uuid NOT NULL REFERENCES customers,
    -- reading 읽는 중 · review 확인 화면 대기 · confirmed 등록됨 · fatal 읽지 못함
    status       text NOT NULL DEFAULT 'reading' CHECK (status IN ('reading', 'review', 'confirmed', 'fatal')),
    -- ★고객이 고칠 때마다 +1 — 낡은 확인 화면으로 등록하지 못하게(등록 request_id = intake_id + revision)
    revision     integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
    fatal_code   text,
    fatal_detail text,
    stage        text,                   -- 화면에 보일 진행 단계(받아쓰는 중 · 규칙으로 읽는 중 …)
    trip_id      uuid,                   -- 등록되면
    received_at  timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_intakes_customer_idx ON trip_intakes (tenant_id, customer_id, received_at DESC);

CREATE TABLE IF NOT EXISTS intake_sources (
    source_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    intake_id    uuid NOT NULL REFERENCES trip_intakes ON DELETE CASCADE,
    tenant_id    text NOT NULL,
    position     integer NOT NULL,       -- 접수 안의 순서(0 = 입력칸 글)
    kind         text NOT NULL,          -- text · pdf · docx · xlsx · image · chat
    filename     text,
    sha256       text NOT NULL,
    size_bytes   integer NOT NULL,
    -- ★원본 파일은 DB 에 두지 않는다 — 저장 위치만(보관 기한 뒤 지운다). 입력칸 글은 받아쓴 글과 같다
    storage_path text,
    transcript   text,                   -- 줄 번호를 매길 글(받아쓴 글 · 파서가 뽑은 글)
    transcribed  boolean NOT NULL DEFAULT false,   -- 비전 받아쓰기로 만든 글인가
    missing_json jsonb NOT NULL DEFAULT '[]'::jsonb,   -- 누락 검사가 찾은, 받아쓰기에 없던 줄
    seconds      double precision,
    -- `[추정]` 30일 — 개인정보 정책 검토 전 임시값(설계서 §6)
    keep_until   timestamptz NOT NULL DEFAULT (now() + interval '30 days'),
    UNIQUE (intake_id, position)
);

CREATE TABLE IF NOT EXISTS intake_claims (
    claim_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    intake_id    uuid NOT NULL REFERENCES trip_intakes ON DELETE CASCADE,
    tenant_id    text NOT NULL,
    revision     integer NOT NULL,
    source_id    uuid REFERENCES intake_sources ON DELETE CASCADE,
    field        text NOT NULL,          -- 예: trip.party_size · items[3].starts_at
    value_json   jsonb,
    -- rule 규칙 · llm_span 모델이 가리킨 원문 조각 · lookup 조회 · customer 고객이 고침
    method       text NOT NULL CHECK (method IN ('rule', 'llm_span', 'lookup', 'customer')),
    evidence     jsonb NOT NULL,         -- 근거 — 원문 (줄, 시작, 끝, 글) 또는 조회 출처
    needs_review boolean NOT NULL DEFAULT false,
    note         text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS intake_claims_intake_idx ON intake_claims (intake_id, revision);
