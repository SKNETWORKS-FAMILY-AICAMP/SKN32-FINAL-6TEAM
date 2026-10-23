-- 035  이 가게는 어디서 확인하는가
-- 작성 2026-09-23.
--
-- 024 가 미뤄 둔 표다. 024 의 map_links 는 상호와 구 이름으로 만든 검색 주소를 준다.
-- 검색 주소는 동명 가게가 섞이고, 가게가 휴무를 올리는 곳(인스타)으로는 데려가지 못한다.
-- 여기에는 사람이 열어 보고 「이 가게가 맞다」고 한 링크를 둔다.
--
-- 링크만 저장한다.
--   링크 너머의 내용 — 게시물, 리뷰, 영업시간 — 은 저장하지 않는다. 읽지도 않는다.
--   약관을 따질 것이 링크 한 줄뿐이게 하려는 것이다.
--
-- 다섯 가지.
--   naver_place   https://map.naver.com/p/entry/place/{숫자}
--   google_place  https://www.google.com/maps/place/…  또는  https://www.google.com/maps?cid={숫자}
--   instagram     https://www.instagram.com/{계정}/     게시물 주소가 아니라 계정이다.
--                                                       공지는 계속 바뀌고 계정은 남는다.
--   tripadvisor   https://www.tripadvisor.co.kr/Restaurant_Review-g…-d….html  (.com 도 받는다)
--   homepage      http(s) 이면서 위 넷의 도메인이나 단축 주소가 아닌 것
--
-- 단축 주소는 받지 않는다. naver.me, maps.app.goo.gl 같은 것.
--   눌러서 쓰는 데는 문제가 없다. 그러나 모양만으로는 어느 가게인지, 지도인지조차
--   알 수 없어서 아래의 모양 검사와 중복 검사가 모두 무력해진다.
--   붙여 넣을 때 scripts/dining/place_link.py 가 한 번 따라가 긴 주소로 바꿔 넣는다.
--
-- 모양 규칙은 external_ref_url_ok 한 곳에만 둔다. 적재 도구도 넣기 전에 이것을 부른다.
-- 파이썬과 SQL 에 따로 두면 언젠가 어긋난다.
--
-- 상태 셋.
--   candidate  넣었지만 아무도 열어 보지 않았다. 사용자에게 나가지 않는다.
--   valid      사람이 열어 보고 이 가게가 맞다고 했다. 누가, 언제를 반드시 남긴다.
--   dead       열어 보니 죽었거나 다른 가게다. 지우지 않고 남긴다 — 같은 링크를 또 넣지 않도록.
--
-- 알림은 건드리지 않는다(032). 링크는 경고가 이미 나갈 때 함께 주는 확인 수단이다.

BEGIN;

INSERT INTO dining.dn_source
    (source_code, display_name, source_kind, storage_mode, production_allowed, note)
VALUES
    ('link_manual', '운영자 확인 가게 링크', 'operator', 'link_only', true,
     'URL 만 저장한다. 링크 너머의 내용은 저장하지 않는다')
ON CONFLICT (source_code) DO UPDATE
   SET display_name = EXCLUDED.display_name,
       source_kind = EXCLUDED.source_kind,
       storage_mode = EXCLUDED.storage_mode,
       production_allowed = EXCLUDED.production_allowed,
       note = EXCLUDED.note;


-- ──────────────────────────────────────────────────────────────
-- 주소 모양
-- ──────────────────────────────────────────────────────────────
--
-- 이 함수를 고치면 앞으로 넣는 행에만 걸린다. 이미 있는 행은 다시 검사하지 않는다.
-- 규칙을 좁혔다면 SELECT … WHERE NOT external_ref_url_ok(kind, url) 로 걸리는 행을 따로 본다.

CREATE OR REPLACE FUNCTION dining.external_ref_url_ok(p_kind text, p_url text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT coalesce(CASE p_kind
        WHEN 'naver_place' THEN
            p_url ~ '^https://map\.naver\.com/p/entry/place/[0-9]+$'
        WHEN 'google_place' THEN
            p_url ~ '^https://www\.google\.com/maps/place/[^?#[:space:]]+$'
            OR p_url ~ '^https://www\.google\.com/maps\?cid=[0-9]+$'
        WHEN 'instagram' THEN
            p_url ~ '^https://www\.instagram\.com/[a-z0-9._]{1,30}/$'
            AND p_url !~ '^https://www\.instagram\.com/(p|reel|reels|stories|explore|tv|accounts)/$'
        WHEN 'tripadvisor' THEN
            p_url ~ '^https://www\.tripadvisor\.(co\.kr|com)/Restaurant_Review-g[0-9]+-d[0-9]+-[^?#[:space:]]*\.html$'
        WHEN 'homepage' THEN
            p_url ~ '^https?://[^/[:space:]]+\.[^/[:space:]]+(/[^[:space:]]*)?$'
            -- 다른 kind 의 자리이거나 단축 주소면 홈페이지가 아니다
            AND p_url !~* '^https?://([^/]*\.)?(naver\.com|naver\.me|google\.[a-z.]+|goo\.gl|instagram\.com|instagr\.am|tripadvisor\.[a-z.]+|bit\.ly|tinyurl\.com)(/|$)'
        ELSE false
    END, false)
$fn$;

COMMENT ON FUNCTION dining.external_ref_url_ok IS
    'kind 마다 받는 주소 모양. 단축 주소는 어느 kind 로도 통과하지 못한다.';


-- ──────────────────────────────────────────────────────────────
-- 표
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dining.dn_external_ref (
    ref_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    place_uid    uuid NOT NULL REFERENCES dining.dn_place(place_uid),
    kind         text NOT NULL,
    url          text NOT NULL,
    source_code  text NOT NULL DEFAULT 'link_manual' REFERENCES dining.dn_source(source_code),
    status       text NOT NULL DEFAULT 'candidate',
    entered_by   text NOT NULL,
    entered_at   timestamptz NOT NULL DEFAULT now(),
    verified_by  text,
    verified_at  timestamptz,
    retired_at   timestamptz,
    note         text,
    CONSTRAINT dn_external_ref_kind_chk CHECK (kind IN
        ('naver_place', 'google_place', 'instagram', 'tripadvisor', 'homepage')),
    CONSTRAINT dn_external_ref_status_chk CHECK (status IN ('candidate', 'valid', 'dead')),
    CONSTRAINT dn_external_ref_url_chk CHECK (dining.external_ref_url_ok(kind, url)),
    -- 확인했다고 하려면 누가 언제 확인했는지가 있어야 한다.
    CONSTRAINT dn_external_ref_valid_chk CHECK (
        status <> 'valid' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL))
);

COMMENT ON TABLE dining.dn_external_ref IS
    '사람이 확인한 가게 전용 링크. 링크만 저장하며 링크 너머의 내용은 저장하지 않는다.';
COMMENT ON COLUMN dining.dn_external_ref.status IS
    'candidate 는 사용자에게 나가지 않는다. valid 만 나간다. dead 는 지우지 않고 남긴다.';

-- 한 가게의 한 kind 에 살아 있는 확인 링크는 하나다.
CREATE UNIQUE INDEX IF NOT EXISTS dn_external_ref_one_valid_idx
    ON dining.dn_external_ref (place_uid, kind)
    WHERE status = 'valid' AND retired_at IS NULL;

-- 한 링크는 한 가게만 가리킨다. 두 곳에 같은 링크가 붙었다면 하나는 틀린 것이다.
CREATE UNIQUE INDEX IF NOT EXISTS dn_external_ref_one_place_idx
    ON dining.dn_external_ref (kind, url)
    WHERE retired_at IS NULL;


-- ──────────────────────────────────────────────────────────────
-- map_links 에 확인 링크를 더한다
-- ──────────────────────────────────────────────────────────────
--
-- 024 의 naver, google, phone, kind 는 그대로 둔다. 이미 읽는 쪽이 있다(024 명절,
-- 026 확인 요청, 031 시험 갈래). kind='search' 는 계속 naver, google 이 검색 주소라는 뜻이다.
--
-- 확인 링크는 place_links 아래에 따로 모은다. 있으면 검색 주소보다 그쪽을 먼저 쓴다.
-- 어느 것을 먼저 보여 줄지는 화면이 정한다. 여기서 검색 주소를 덮어쓰면
-- 그 주소가 검색인지 가게인지를 kind 한 칸으로 말할 수 없게 된다.

CREATE OR REPLACE FUNCTION dining.map_links(p_place_uid uuid)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
    SELECT jsonb_strip_nulls(jsonb_build_object(
        'naver',  'https://map.naver.com/p/search/' || dining.urlencode(q.text),
        'google', 'https://www.google.com/maps/search/?api=1&query='
                  || dining.urlencode(q.text),
        'phone',  (SELECT phone FROM dining.dn_place WHERE place_uid = p_place_uid),
        'kind',   'search',
        'place_links', (SELECT jsonb_object_agg(r.kind, r.url ORDER BY r.kind)
                          FROM dining.dn_external_ref r
                         WHERE r.place_uid = p_place_uid
                           AND r.status = 'valid'
                           AND r.retired_at IS NULL)
    ))
    FROM (SELECT dining.search_query(p_place_uid) AS text) q
    WHERE q.text IS NOT NULL AND q.text <> ''
$$;

COMMENT ON FUNCTION dining.map_links IS
    'naver, google 은 검색 주소다(kind=search). place_links 는 사람이 확인한 가게 링크이며 있으면 그쪽을 먼저 쓴다.';

COMMIT;
