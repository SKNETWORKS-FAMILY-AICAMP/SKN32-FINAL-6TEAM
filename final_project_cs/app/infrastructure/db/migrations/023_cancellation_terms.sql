-- 023 — 취소 조건을 **구조화해서** 둔다 (결함 「정책 청크에서 수치를 못 꺼낸다」)
--
-- ★★왜. `activity.check_cancelable` 이 취소 기한·위약금율을 **RAG 청크에서** 꺼내려 했다.
--   `_policy_hours`·`_penalty_rate` 가 `isinstance(chunk, dict)` 로 거르는데 RAG 가 주는
--   것은 `PolicyChunk` 라 **항상 거짓**이다 — 즉 어떤 코퍼스를 넣어도 두 값이 언제나
--   `None` 이었고, 제품이 약속한 「지금 취소하면 얼마인가」가 한 번도 답해진 적이 없다
--   (`wiki/records/reports/debugs/2026-09-22_정책청크에서_수치를_못_꺼낸다.md`).
--
-- ★고른 길은 ①「구조화 정책을 따로 둔다」다. 남은 둘을 왜 버렸나 —
--   ② `PolicyChunk` 에 칸을 더하면 Context Broker·Evidence 까지 계약이 번진다.
--   ③ 산문에서 LLM 이 뽑게 하면 **판정에 생성이 끼어든다**(「판정은 코드」와 부딪힌다).
--   RAG 는 그대로 **문장 근거**를 대고, 수치는 이 표가 댄다. 둘의 몫이 갈린다.
--
-- ★★**취소 조건은 전역 규정이 아니라 「이 예약의 조건」이다.** 같은 테넌트 안에서도
--   업체마다 다르고 상품마다 다르다. 그래서 한 줄짜리 설정이 아니라 **범위를 가진 표**다.
--   찾는 순서 —  ① 그 예약(`booking`)  → ② 그 공급자(`supplier`)  → ③ 그 종류(`kind`)
--   v11 결정 15 「값마다 대체 소스를 둔다」를 이 표가 데이터로 구현한다. 셋 다 없으면
--   **모름**이고, 모름이면 금액을 만들지 않는다(지어내지 않는다).
--
-- ★`source` 는 의무다. 「어디서 온 값인가」가 없으면 시연용 Mock 과 실제 업체 약관이
--   섞이고, 섞이는 순간 고객에게 지어낸 금액을 말하게 된다.
--
-- ☆번호 015·018 은 건너뛴다(`pending/015_drop_commerce_domain.sql` · 018 은 결번).
-- ☆재실행해도 안전하다.

CREATE TABLE IF NOT EXISTS cancellation_terms (
    term_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     text NOT NULL,
    -- booking / supplier / kind — 위에서부터 좁은 범위다
    scope_type    text NOT NULL,
    -- scope_type 에 따라 booking_id · supplier 이름 · kind 이름이 들어간다
    scope_id      text NOT NULL,
    -- 시작 몇 시간 전까지 취소할 수 있나
    cancel_deadline_hours numeric NOT NULL,
    -- {"24": 0.5, "48": 0.3} — 「남은 시간이 이 값보다 적으면 이 율」
    penalty_by_hours jsonb NOT NULL DEFAULT '{}'::jsonb,
    -- ★어디서 온 값인가. 시연용이면 그렇게 적는다
    source        text NOT NULL,
    observed_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, scope_type, scope_id)
);

-- ★값이 셋뿐이라는 것을 DB 가 지킨다. 오타가 들어오면 조회가 조용히 0건이 되는 게
--   아니라 **삽입이 실패한다** — 조용히 0건이면 「조건이 없다」로 읽혀 모름이 된다.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cancellation_terms_scope_type_check') THEN
        ALTER TABLE cancellation_terms ADD CONSTRAINT cancellation_terms_scope_type_check
            CHECK (scope_type IN ('booking', 'supplier', 'kind'));
    END IF;
END $$;

-- ★음수 기한·1 을 넘는 율은 판정을 뒤집는다. 들어오기 전에 막는다.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cancellation_terms_deadline_check') THEN
        ALTER TABLE cancellation_terms ADD CONSTRAINT cancellation_terms_deadline_check
            CHECK (cancel_deadline_hours >= 0);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS cancellation_terms_lookup_idx
    ON cancellation_terms (tenant_id, scope_type, scope_id);
