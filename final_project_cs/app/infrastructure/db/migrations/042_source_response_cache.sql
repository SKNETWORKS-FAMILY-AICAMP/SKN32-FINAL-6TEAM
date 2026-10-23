-- 042 — 바깥 소스 응답 공유 캐시. `[2026-10-03 사용자 — 「3분마다 받은 걸 저장해 두고 그 사이엔 그걸 쓰자」]`
--
-- ★왜. 소스 응답 캐시(`travel/cache.py`)는 **프로세스 안 메모리**라, 일꾼이 회차마다 새 프로세스(`--once`)를 띄우는 지금은 틱 사이에 재사용이 없고 고객 요청 경로(API 프로세스)와도
--   공유되지 않는다(측정: `wiki/records/reports/2026-10-03_감시_외부호출_측정_리포트.md`). 한 번 받은 공공 API 응답을 이 표에 두면 **어느 프로세스든** 유지 시간 안에서는 다시 안 부른다.
-- ★공개 소스 응답만 담는다(기상 · 대기질 · 특보 · 지진 · 재난문자 · 교통 · 공휴일) — 허용 소스는 코드(`DbResponseCache.SHARED_SOURCES`)가 정한다. 고객이 쓴 검색어가 담기는 소스는 안 넣는다.
-- ★열쇠는 요청의 **해시**만 둔다 — 요청 인자에는 서비스 키가 들어 있어 원문을 두지 않는다. 담는 것은 응답 본문(공개 데이터) · 처음 받아 온 시각 · 만료 시각이다.
-- ★실패한 응답은 담지 않는다(메모리 캐시와 같은 규칙). 만료된 줄은 쓰는 쪽이 이따금 지운다.

CREATE TABLE IF NOT EXISTS source_response_cache (
    key_hash   text PRIMARY KEY,
    source     text NOT NULL,
    payload    jsonb NOT NULL,
    fetched_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_source_response_cache_expiry ON source_response_cache (expires_at);
