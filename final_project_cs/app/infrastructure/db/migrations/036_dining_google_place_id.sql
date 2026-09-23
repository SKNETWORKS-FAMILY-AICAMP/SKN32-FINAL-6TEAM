-- 036  구글 place_id 를 둘 자리
-- 작성 2026-09-23.
--
-- 035 의 google_place 링크(https://www.google.com/maps?cid=…)는 사람이 누르는 주소다.
-- 변동 확인(Place Details)은 cid 가 아니라 place_id 로 부른다. 그래서 둘을 함께 둔다.
--
-- place_id 만 저장한다.
--   구글 약관이 기한 없이 저장해도 된다고 한 것은 place_id 뿐이다. 이름, 주소, 영업시간 같은
--   구글 쪽 내용은 저장하지 않는다. 비교에 쓰고 버린다(scripts/dining/google_link.py).
--
-- 칸 이름을 google_place_id 로 하지 않고 provider_id 로 둔다.
--   네이버 플레이스 번호도 같은 자리에 들어갈 수 있다. kind 가 어느 곳의 id 인지 말한다.

BEGIN;

ALTER TABLE dining.dn_external_ref ADD COLUMN IF NOT EXISTS provider_id text;

COMMENT ON COLUMN dining.dn_external_ref.provider_id IS
    '그 kind 의 제공자가 쓰는 가게 id. google_place 면 place_id. 제공자의 다른 내용은 저장하지 않는다.';

-- 한 id 는 한 가게만 가리킨다. url 의 중복 검사(035)와 같은 이유다.
CREATE UNIQUE INDEX IF NOT EXISTS dn_external_ref_one_provider_id_idx
    ON dining.dn_external_ref (kind, provider_id)
    WHERE provider_id IS NOT NULL AND retired_at IS NULL;

COMMIT;
