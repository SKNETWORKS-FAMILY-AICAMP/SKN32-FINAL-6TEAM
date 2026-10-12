-- 231  이 집은 어떤 결의 식사인가 (음식 결)
-- 작성 2026-10-12.
--
-- 대표 분류(214 category)는 어느 나라 음식인가 한 칸이라 너무 크다. 고깃집과 백반집이 둘 다 한식이라
-- 고깃집이 문을 닫으면 가까운 백반집이 「비슷한 곳」으로 골라졌다. 이름에 「갈비」 같은 메뉴 말이 없으면
-- 대체 순위(`meal_likeness`)가 둘을 가르지 못한다(영업 중 1,884곳 중 이름으로 메뉴를 아는 곳 354곳, 2026-10-12).
--
-- 결 한 칸. 큰 분류 아래에서 「어떤 식사인가」.
--   고기구이 · 국물요리 · 면 · 해산물 · 한상차림 · 분식 · 닭요리 · 족발·보쌈 · 초밥 · 돈가스·튀김 · 덮밥 ·
--   중식요리 · 이탈리안 · 버거·샌드위치 · 브런치 · 아시아요리 · 베이커리·디저트 · 커피·차 · 술집 ·
--   뷔페 · 코스·다이닝  `[2026-10-12 사용자]`
-- 결은 나라를 말하지 않는다. 라멘과 냉면은 둘 다 면이고, 큰 분류(일식 · 한식)가 둘을 가른다.
-- 비교하는 쪽(`meal_likeness`)이 큰 분류가 다르다고 알면 같은 결로 보지 않는다.
--
-- 207 의 cuisine_tags 와 다르다. 그것은 여러 태그를 붙이는 SQL 안의 유사도이고 지금 대체 순위는 쓰지 않는다.
-- 결은 한 곳에 하나다 — 「같은 결인가」가 설명이 된다(「같은 고깃집이라 골랐어요」).
--
-- 무엇을 먼저 보는가 — 214 와 같다.
--   1  대표메뉴(firstmenu)  가게가 스스로 내세운 것
--   2  가게 이름
--   3  취급메뉴(treatmenu)  곁들이 메뉴가 많아 가장 잘 틀린다
-- 한 문장 안에서는 아래 칸의 순서가 이긴다. 겹치는 낱말 때문이다.
--   갈비탕은 국물요리다 — 국물요리를 고기구이보다 먼저 본다
--   생선구이는 해산물이다 — 해산물을 고기구이보다 먼저 본다
--   등심돈까스는 돈가스다 — 돈가스를 고기구이보다 먼저 본다
--   삼계탕 · 닭갈비는 닭요리다 — 닭요리를 국물요리 · 고기구이보다 먼저 본다
--   쌀국수는 아시아요리다 — 아시아요리를 면보다 먼저 본다
--   회덮밥 · 장어덮밥은 해산물이다 — 해산물을 덮밥보다 먼저 본다
--   「정식」 · 「전통주」는 넣지 않는다 — 「각시정식」(보쌈집) · 「전통주 페어링」(코스 식당)처럼 결을 말하지 않는다
--   곱창전골은 국물요리다(전골) — 알고 둔다
--   뷔페는 맨 앞이다 — 형식이 메뉴보다 먼저다. 무한리필은 뷔페로 보지 않는다(무한리필 고깃집은 고기구이)
--
-- 코스·다이닝은 낱말이 아니라 **마지막 근거**다 — 「코스요리」 · 「런치코스」만 적힌 곳. 세 칸 어디에서든 무엇의 코스인지
-- 보이면 그 결이 먼저다: 대표메뉴의 결 → 이름의 결 → 취급메뉴의 결 → 대표메뉴 · 이름 · 취급메뉴의 코스.
--   (마구로센 「코스 메뉴」 / 취급 「오토로초밥」 → 초밥 · 아리차이 「코스요리」 / 취급 「매정탁」 → 코스·다이닝)
--   ☆대표메뉴의 코스를 취급메뉴의 결보다 앞에 두는 판도 쟀다(2026-10-12) — 23곳이 결을 잃었고 그중 13곳은 취급메뉴의 결이
--     맞았다(초밥 오마카세 · 이탈리안 코스 · 중식 코스). 틀린 쪽(동해도 「생선매운탕」 → 국물요리, 로얄앤코하우스 → 해산물)은
--     사람 검수로 고친다.
-- 안 걸리면 NULL 이다. 모르는 것을 지어내지 않는다 — 결을 모르면 비교는 큰 분류로 내려간다.
--
-- 사람이 고친 값(manual)은 규칙을 다시 돌려도 덮지 않는다(214 와 같다).

BEGIN;

ALTER TABLE dining.dn_place
    ADD COLUMN IF NOT EXISTS style        text,
    ADD COLUMN IF NOT EXISTS style_method text;

ALTER TABLE dining.dn_place DROP CONSTRAINT IF EXISTS dn_place_style_chk;
ALTER TABLE dining.dn_place ADD CONSTRAINT dn_place_style_chk CHECK (
    style IS NULL OR style IN
        ('고기구이', '국물요리', '면', '해산물', '한상차림', '분식', '닭요리', '족발·보쌈', '초밥', '돈가스·튀김',
         '덮밥', '중식요리', '이탈리안', '버거·샌드위치', '브런치', '아시아요리', '베이커리·디저트', '커피·차', '술집',
         '뷔페', '코스·다이닝'));

ALTER TABLE dining.dn_place DROP CONSTRAINT IF EXISTS dn_place_style_method_chk;
ALTER TABLE dining.dn_place ADD CONSTRAINT dn_place_style_method_chk CHECK (
    style_method IS NULL OR style_method IN ('rule', 'manual'));

-- 214 와 다르다 — 결은 규칙이 못 정하면 NULL 이 정상이라 style 이 비어도 method 는 있을 수 있다.
-- manual 인데 style 이 비면 「사람이 보고 결이 없다고 정했다」는 뜻이다.

COMMENT ON COLUMN dining.dn_place.style IS
    '음식 결(고기구이 · 국물요리 …). NULL 은 근거가 없다는 뜻이다. 큰 분류(category) 아래에서 비교한다.';
COMMENT ON COLUMN dining.dn_place.style_method IS
    'rule 은 classify_style 이 붙인 값이다. manual 은 사람이 고친 값이며 규칙이 덮지 않는다.';


-- ──────────────────────────────────────────────────────────────
-- 문장 하나에서 결 하나
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION dining.style_of_text(p_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT CASE
        WHEN t IS NULL OR t = '' THEN NULL
        WHEN t ~ '뷔페|부페|buffet|샐러드바'
            THEN '뷔페'
        WHEN t ~ '쌀국수|분짜|반미|팟타이|똠얌|(?<!베이)커리|카레|케밥|타코(?!야키)|부리또|나시고렝|월남쌈|탄두리|후무스|홈무스|팔라펠|쿠스쿠스'
            THEN '아시아요리'
        WHEN t ~ '스시|초밥|오마카세'
            THEN '초밥'
        WHEN t ~ '돈까스|돈가스|카츠|가츠|텐동|텐푸라|덴뿌라|가라아게'
            THEN '돈가스·튀김'
        WHEN t ~ '피자|핏짜|파스타|스파게티|리조또|라자냐|뇨끼|봉골레|까르보나라|마르게리|마리나라'
            THEN '이탈리안'
        WHEN t ~ '버거|샌드위치|파니니|핫도그'
            THEN '버거·샌드위치'
        WHEN t ~ '브런치|오믈렛|베네딕트|팬케이크|브렉퍼스트|샐러드'
            THEN '브런치'
        WHEN t ~ '삼계탕|백숙|닭한마리|닭갈비|찜닭|닭볶음탕|닭도리|치킨|통닭|닭강정|닭꼬치|야키토리|닭곰탕'
            THEN '닭요리'
        WHEN t ~ '국밥|해장국|설렁탕|설농탕|곰탕|감자탕|뼈해장|순대국|순댓국|육개장|추어탕|갈비탕|도가니|찌개|전골|내장탕|선지|순두부|청국장|매운탕|해신탕|대구탕|곰치국|알탕|동태탕|우거지|샤브|샤부|스키야키|만두국|떡국'
            THEN '국물요리'
        WHEN t ~ '냉면|막국수|밀면|칼국수|국수|국시|수제비|메밀|소바|우동|라멘|라면|짜장|짬뽕|우육면|탕면|쫄면|면가|도삭면'
            THEN '면'
        WHEN t ~ '탕수육|딤섬|샤오롱|마라|훠궈|양장피|유린기|꿔바로우|깐풍|팔보채|유산슬|전가복|북경오리|베이징덕|동파육|멘보샤|깐쇼'
            THEN '중식요리'
        WHEN t ~ '물회|횟집|사시미|회(?!관|식|원|사|장|기)|골뱅이|홍어|조개|낙지|쭈꾸미|주꾸미|문어|장어|굴비|굴(?!비)|전복|해물|생선|게장|대게|킹크랩|꽃게|아구|아귀|복어|방어|광어|우럭|갈치|고등어|과메기|멍게|해산물|새우|쉬림프|랍스터|오징어|가리비|홍합|복집'
            THEN '해산물'
        WHEN t ~ '규동|덮밥|돈부리|사케동|카이센동|오야코동'
            THEN '덮밥'
        WHEN t ~ '족발|보쌈|수육'
            THEN '족발·보쌈'
        WHEN t ~ '한우|갈비|삼겹|목살|항정|가브리|차돌|등심|안심|살치|꽃살|안창|갈매기살|곱창|대창|막창|양구이|숯불|고기|양꼬치|스테이크|바비큐|바베큐|브리스킷|불고기|육회|육사시미|소금구이|석쇠|껍데기|오겹|슈하스코|프라임 립|프라임립'
            THEN '고기구이'
        WHEN t ~ '한정식|백반|불백|기사식당|쌈밥|보리밥|비빔밥|솥밥|돌솥|가정식|한상|사찰|정찬|수라상|밥상'
            THEN '한상차림'
        WHEN t ~ '분식|떡볶이|김밥|라볶이|순대|어묵|오뎅|튀김'
            THEN '분식'
        WHEN t ~ '베이커리|빵|케이크|디저트|빙수|도넛|도나스|도너츠|마카롱|크루아상|베이글|와플|젤라또|젤라토|아이스크림|타르트|스콘|쿠키|카스테라|깜빠뉴|바게트|단팥|티라미수|까눌레|카눌레|카놀리|에끌레어|에클레어|애플파이|크라상|포카치아|요거트'
            THEN '베이커리·디저트'
        WHEN t ~ '커피|에스프레소|아메리카노|라떼|라테|티하우스|찻집|말차|녹차|밀크티|카페|까페|cafe|쌍화차|대추차|생강차|오미자|유자차|티룸|아이스티|에이드|스무디'
            THEN '커피·차'
        WHEN t ~ '막걸리|와인바|맥주|호프|이자카야|하이볼|포차|위스키|칵테일|사케'
            THEN '술집'
    END
    FROM (SELECT lower(btrim(p_text)) AS t) s
$fn$;

COMMENT ON FUNCTION dining.style_of_text IS
    '문장 하나에서 결 하나. 안 걸리면 NULL 이다. 코스·다이닝은 여기서 내지 않는다(course_of_text).';


CREATE OR REPLACE FUNCTION dining.course_of_text(p_text text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $fn$
    SELECT CASE WHEN lower(coalesce(p_text, '')) ~ '코스|course|테이스팅|tasting|다이닝|dining' THEN '코스·다이닝' END
$fn$;

COMMENT ON FUNCTION dining.course_of_text IS
    '「코스요리」 · 「런치코스」 · 「OO 다이닝」이면 코스·다이닝. 무엇의 코스인지는 style_of_text 가 먼저 본다.';


-- ──────────────────────────────────────────────────────────────
-- 한 곳의 결 — 214 classify_category 와 같은 원문을 같은 순서로 본다
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION dining.classify_style(p_place_uid uuid)
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
        dining.style_of_text((SELECT firstmenu FROM src)),
        dining.style_of_text(p.name_ko),
        dining.style_of_text((SELECT treatmenu FROM src)),
        dining.course_of_text((SELECT firstmenu FROM src)),
        dining.course_of_text(p.name_ko),
        dining.course_of_text((SELECT treatmenu FROM src)))
    FROM dining.dn_place p
    WHERE p.place_uid = p_place_uid
$fn$;

COMMENT ON FUNCTION dining.classify_style IS
    '대표메뉴, 가게 이름, 취급메뉴 순으로 본다. 무엇의 코스인지 모르는 코스는 코스·다이닝. 어디서도 안 걸리면 NULL 이다.';


-- ──────────────────────────────────────────────────────────────
-- 다시 돌리기 — 규칙을 고쳤거나 새로 적재했을 때. 사람이 고친 값은 건드리지 않는다
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION dining.refresh_style()
RETURNS integer
LANGUAGE sql
AS $fn$
    WITH upd AS (
        UPDATE dining.dn_place p
        SET style        = dining.classify_style(p.place_uid),
            style_method = 'rule'
        WHERE p.style_method IS DISTINCT FROM 'manual'
          AND (p.style IS DISTINCT FROM dining.classify_style(p.place_uid) OR p.style_method IS NULL)
        RETURNING 1
    )
    SELECT count(*)::integer FROM upd
$fn$;

COMMENT ON FUNCTION dining.refresh_style IS
    'manual 이 아닌 곳을 규칙으로 다시 채운다. 바뀐 곳의 수를 돌려준다.';

-- 이미 적재된 곳을 채운다.
SELECT dining.refresh_style();

COMMIT;
