-- 303  관광공사 목록에서 내려간 활동 장소 — 지우지 않고 표시만 한다(끝난 축제 · 폐업 · 비공개). 작성 2026-10-12.
-- scripts/activity/refresh_places.py 가 매일 밤 목록과 맞춘다 — 목록에 없으면 내려간 시각을 적고, 다시 나타나면 비운다.
-- 대체 후보 조회(db_search/place_candidates.py)는 표시된 장소를 후보로 내지 않는다.

ALTER TABLE activity.ac_place ADD COLUMN IF NOT EXISTS delisted_at timestamptz;

COMMENT ON COLUMN activity.ac_place.delisted_at IS
    '관광공사 목록에서 내려간 시각(처음 알아챈 때). NULL 이면 목록에 있다. 축제는 다음 해에 다시 올라올 수 있어 지우지 않는다.';
