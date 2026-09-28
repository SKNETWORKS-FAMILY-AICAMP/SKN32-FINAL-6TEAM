-- 034  이 집은 무슨 집인가
-- 작성 2026-09-23.
--
-- 대표 분류 한 칸. 한식, 중식, 일식, 양식, 카페디저트, 기타, 미상.
--
-- 027 의 cuisine_tags 와는 축이 다르다.
--   cuisine_tags  고기, 국물, 면 … 조리 형태이며 여럿 붙는다. 유사도에 쓴다.
--   category      어느 나라 음식인가이며 하나만 붙는다. 거르고 보여 주는 데 쓴다.
-- 하나로 합치지 않는다. 대체 후보 로직이 cuisine_tags 에 매달려 있다.
--
-- 기타와 미상은 다르다.
--   기타  분류했는데 여섯 칸 밖이다. 쌀국수, 팟타이.
--   미상  판단할 근거가 없다. 메뉴 칸이 비었거나 「코스요리」뿐이다.
-- 둘을 뭉치면 규칙을 고쳐야 할 곳과 자료를 더 받아야 할 곳을 가를 수 없다.
-- 모르는 것을 기타로 떨어뜨리지 않는다.
--
-- 무엇을 먼저 보는가.
--   1  대표메뉴(firstmenu)  가게가 스스로 내세운 것이다. 여기서 나면 끝이다.
--   2  가게 이름            「호랑이 초밥」의 대표메뉴는 「호랑이모듬」이라 안 걸린다.
--                           보조메뉴에 짬뽕이 있어 3 으로 가면 중식이 된다.
--   3  취급메뉴(treatmenu)  마지막이다. 곁들이 메뉴가 많아 가장 잘 틀린다.
--
-- 한 문장 안에서는 칸의 순서가 이긴다. 기타, 중식, 일식, 양식, 한식, 카페디저트.
-- 한식을 뒤에 두는 것은 탕, 구이, 찜 같은 짧은 낱말이 넓게 걸리기 때문이다.
-- 탕수육이 한식이 되지 않으려면 중식이 먼저 봐야 한다.
--
-- 표본 200곳에 맞춘 규칙이다. 서울 전체로 넓히면 다시 맞춰야 한다.
-- 규칙은 이 함수에만 둔다. 고친 뒤 refresh_category 를 부르면 된다.
--
-- 200곳에서 알고도 두는 것.
--   만두는 한식이다. 개성만두, 이북만두 집이 딤섬 집보다 많다.
--   회는 한식이다. 숙성회, 물회. 참치 집이 여기로 온다.
--   오프트는 한식이다. 대표메뉴가 떡볶이다. 뇨끼도 팔지만 대표를 따른다.
--   커리는 기타지만 베이커리는 아니다. 타코는 기타지만 타코야키는 아니다.

BEGIN;

ALTER TABLE dining.dn_place
    ADD COLUMN IF NOT EXISTS category        text,
    ADD COLUMN IF NOT EXISTS category_method text;

ALTER TABLE dining.dn_place DROP CONSTRAINT IF EXISTS dn_place_category_chk;
ALTER TABLE dining.dn_place ADD CONSTRAINT dn_place_category_chk CHECK (
    category IS NULL OR category IN
        ('한식', '중식', '일식', '양식', '카페디저트', '기타', '미상'));

-- 사람이 고친 값은 규칙을 다시 돌려도 덮지 않는다.
ALTER TABLE dining.dn_place DROP CONSTRAINT IF EXISTS dn_place_category_method_chk;
ALTER TABLE dining.dn_place ADD CONSTRAINT dn_place_category_method_chk CHECK (
    category_method IS NULL OR category_method IN ('rule', 'manual'));

ALTER TABLE dining.dn_place DROP CONSTRAINT IF EXISTS dn_place_category_pair_chk;
ALTER TABLE dining.dn_place ADD CONSTRAINT dn_place_category_pair_chk CHECK (
    (category IS NULL) = (category_method IS NULL));

COMMENT ON COLUMN dining.dn_place.category IS
    '대표 분류. 미상은 근거가 없다는 뜻이고 기타는 여섯 칸 밖이라는 뜻이다. NULL 은 아직 돌리지 않았다는 뜻이다.';
COMMENT ON COLUMN dining.dn_place.category_method IS
    'rule 은 classify_category 가 붙인 값이다. manual 은 사람이 고친 값이며 규칙이 덮지 않는다.';

CREATE INDEX IF NOT EXISTS dn_place_category_idx ON dining.dn_place (category);


-- ──────────────────────────────────────────────────────────────
-- 낱말 하나로 칸 하나
-- ──────────────────────────────────────────────────────────────
--
-- 근거가 없으면 NULL 이다. 미상으로 바꾸는 것은 부르는 쪽이 한다.
-- 1, 2, 3 을 차례로 보려면 「안 걸렸다」와 「미상」이 구분되어야 한다.

CREATE OR REPLACE FUNCTION dining.category_of_text(p_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT CASE
        WHEN t IS NULL OR t = '' THEN NULL
        WHEN t ~ '쌀국수|분짜|반미|팟타이|똠얌|(?<!베이)커리|케밥|타코(?!야키)|부리또|나시고렝|월남쌈'
            THEN '기타'
        WHEN t ~ '짬뽕|짜장|탕수육|마라|양장피|딤섬|샤오롱|유린기|꿔바로우|깐풍|중화|훠궈|우육면|전가복|유산슬|팔보채'
            THEN '중식'
        WHEN t ~ '텐동|카츠|가츠|돈까스|돈가스|스시|초밥|사시미|규동|오마카세|소바|우동|라멘|이자카야|야키토리|사케|텐푸라|가라아게|마끼|마키|타코야키|오코노미'
            THEN '일식'
        WHEN t ~ '피자|핏짜|파스타|스파게티|리조또|라자냐|뇨끼|스테이크|버거|샌드위치|브런치|오믈렛|샐러드|봉골레|까르보나라|마르게리|마리나라|파니니|비스트로|트러플|브렉퍼스트'
            THEN '양식'
        WHEN t ~ '한식|한우|갈비|삼겹|목살|곱창|대창|막창|족발|보쌈|불고기|비빔|국밥|해장|설렁|설농|곰탕|찌개|전골|탕|찜|김치|된장|냉면|국수|국시|메밀|수제비|백반|정식|떡볶이|순대|구이|사찰|회(?!관)|횟집|게장|닭|만두|미역|전복|낙지'
            THEN '한식'
        WHEN t ~ '커피|에스프레소|아메리카노|라떼|라테|케이크|디저트|베이글|빵|깜빠뉴|바게트|포카치아|크루아상|와플|빙수|단팥|팥죽|티하우스|찻집|녹차|말차|밀크티|애프터눈|도넛|쿠키|마카롱|카놀리|젤라또|아이스크림|에이드|스콘|타르트|카스테라|베이커리|카페|까페|cafe'
            THEN '카페디저트'
    END
    FROM (SELECT lower(btrim(p_text)) AS t) s
$fn$;

COMMENT ON FUNCTION dining.category_of_text IS
    '문장 하나에서 칸 하나. 안 걸리면 NULL 이며 미상이 아니다.';


-- ──────────────────────────────────────────────────────────────
-- 한 곳의 대표 분류
-- ──────────────────────────────────────────────────────────────
--
-- 메뉴가 적힌 원문 중 가장 최근에 받은 것을 본다.
--
-- 「가장 최근 원문」이 아니다. 한 곳에 원문이 여럿 붙는다. 운영자 영업시간 확인,
-- 인허가 대조, 비건 목록 등재 — 어느 것에도 메뉴 칸이 없다. 이런 원문이 새로
-- 붙을 때마다 대표메뉴를 잃고 분류가 조용히 뒤집히면 안 된다.
--
-- 027 은 LIMIT 1 만 걸어 어느 원문을 볼지 정해지지 않는다. 여기서는 정한다.

CREATE OR REPLACE FUNCTION dining.classify_category(p_place_uid uuid)
RETURNS text
LANGUAGE sql
STABLE
AS $fn$
    WITH src AS (
        SELECT sr.raw_json ->> 'firstmenu' AS firstmenu,
               sr.raw_json ->> 'treatmenu' AS treatmenu
        FROM dining.dn_source_record sr
        JOIN dining.dn_load_meta lm ON lm.load_id = sr.load_id
        WHERE sr.place_uid = p_place_uid
          AND (sr.raw_json ? 'firstmenu' OR sr.raw_json ? 'treatmenu')
        ORDER BY lm.fetched_at DESC, sr.record_id
        LIMIT 1
    )
    SELECT coalesce(
        dining.category_of_text((SELECT firstmenu FROM src)),
        dining.category_of_text(p.name_ko),
        dining.category_of_text((SELECT treatmenu FROM src)),
        '미상')
    FROM dining.dn_place p
    WHERE p.place_uid = p_place_uid
$fn$;

COMMENT ON FUNCTION dining.classify_category IS
    '대표메뉴, 가게 이름, 취급메뉴 순으로 본다. 어디서도 안 걸리면 미상이다. 없는 장소는 NULL 이다.';


-- ──────────────────────────────────────────────────────────────
-- 다시 돌리기
-- ──────────────────────────────────────────────────────────────
--
-- 규칙을 고쳤거나 새로 적재했을 때 부른다. 사람이 고친 값은 건드리지 않는다.
-- 바뀐 곳의 수를 돌려준다. 0 이면 규칙을 고쳐도 결과가 같다는 뜻이다.

CREATE OR REPLACE FUNCTION dining.refresh_category()
RETURNS integer
LANGUAGE sql
AS $fn$
    WITH upd AS (
        UPDATE dining.dn_place p
        SET category        = dining.classify_category(p.place_uid),
            category_method = 'rule'
        WHERE p.category_method IS DISTINCT FROM 'manual'
          AND p.category IS DISTINCT FROM dining.classify_category(p.place_uid)
        RETURNING 1
    )
    SELECT count(*)::integer FROM upd
$fn$;

COMMENT ON FUNCTION dining.refresh_category IS
    'manual 이 아닌 곳을 규칙으로 다시 채운다. 바뀐 곳의 수를 돌려준다.';


-- 이미 적재된 곳을 채운다.
SELECT dining.refresh_category();

COMMIT;
