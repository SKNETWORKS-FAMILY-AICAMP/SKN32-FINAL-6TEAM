-- 302  활동 장소 원문이 바뀌었는지 알아채기 — 관광공사 목록의 수정 시각(D-CS-015 개정 2 「원문 바뀜 알아채기」)
-- 작성 2026-10-12. scripts/activity/refresh_places.py 가 채운다.
--   처음 본 장소는 기준점으로만 적고, 다음부터 이 값과 목록의 modifiedtime 이 다르면 그 장소만 운영시간 · 휴무를 다시 받는다.

ALTER TABLE activity.ac_place ADD COLUMN IF NOT EXISTS source_modified_at text;
ALTER TABLE activity.ac_place ADD COLUMN IF NOT EXISTS source_checked_at timestamptz;

COMMENT ON COLUMN activity.ac_place.source_modified_at IS
    '관광공사 목록의 modifiedtime(원문 그대로, 14자리). 브랜드 매장(OY…)은 비어 있다 — 관광공사에 없다.';
