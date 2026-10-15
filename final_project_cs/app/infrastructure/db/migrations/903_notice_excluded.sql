-- 「기타」 재난 문자 중 여행 영향이 없다고 보고 일정 감시에 보내지 않은 문자 기록 `[2026-10-13 사용자 결정]`.
-- 규칙과 모델(2차 확인)이 둘 다 「영향 없음」이라 한 문자를 버리지 않고 남겨, 관리자 웹앱에서 무슨 사안이 몇 번 왔는지 본다.
-- 재난 문자는 공공 자료라 테넌트로 나누지 않는다. 고객 정보는 없다(본문 · 수신지역 · 재해구분만).
CREATE TABLE IF NOT EXISTS notice_excluded_messages (
    serial text PRIMARY KEY,                 -- 재난 문자 일련번호(API 의 SN). 같은 문자는 한 번만 센다
    text_hash text NOT NULL,                 -- 본문 sha256 — 같은 본문이 여러 번(여러 지역 · 여러 시각) 온 것을 묶는다
    body text NOT NULL,
    kind text NOT NULL,                      -- 재해구분 원값(「기타」)
    step text NOT NULL,                      -- 긴급단계 원값
    regions jsonb NOT NULL,                  -- 수신지역 목록
    sent_at timestamptz NOT NULL,            -- 문자 생성 시각
    judged_by text NOT NULL CHECK (judged_by IN ('rule', 'rule+model')),   -- 영향 없음을 누가 냈나(모델이 꺼져 있으면 rule)
    prompt_version text,                     -- 모델 지시문 판(모델이 판정에 참여했을 때)
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS notice_excluded_messages_hash_idx ON notice_excluded_messages (text_hash);
CREATE INDEX IF NOT EXISTS notice_excluded_messages_sent_idx ON notice_excluded_messages (sent_at DESC);
