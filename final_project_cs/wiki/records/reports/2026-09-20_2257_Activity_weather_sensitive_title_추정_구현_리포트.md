---
type: report
title: Activity — weather_sensitive를 장소명 키워드로 추정하는 로직 구현
status: done
domain: travel
---

# Activity — weather_sensitive를 장소명 키워드로 추정하는 로직 구현

## 1. 작업 목표

이전 세션에서 "`weather_sensitive`는 TourAPI가 안 주고, `places`에 실제로 값을 쓰는 프로덕션 경로도 없어서 실 데이터에서 검증 불가"라는 걸 확인했다. 사용자가 "title 값 기준으로 실내·실외 판별 알고리즘을 새로 작성"하라고 구체적인 키워드 예시(실외: 옥상·광장·공원·거리·운동장 / 실내: 층·홀·실내·전시실)를 주고 결정했다.

## 2. 실제 수행 내용

### `app/modules/travel_ops/activity.py`

- `_weather_sensitive_from_title(name)` classmethod 신설 — 사용자가 준 키워드 그대로 매칭. 실외/실내 둘 다 걸리면(예: "○○공원 전시홀") 억지로 고르지 않고 `None`. 단서가 없어도 `None`. 층수 표기("1F"·"3층"·"B1")는 정규식으로 별도 처리
- `_check_feasible()` 수정: `place.get("weather_sensitive")`가 `None`일 때만(**DB 확정값이 있으면 이름을 아예 안 본다**) 이 함수를 호출해 대체
- 추정을 썼으면 **항상 공개**한다 — 근거(`activity.weather_sensitive_from_title`) 추가, 경고("실내·실외를 장소명으로 추정해 날씨를 조회했다 — DB에 확인된 값이 아니다") 추가, `decisions.weather.weather_sensitive_guessed_from_title`에 `true`

### `tests/unit/travel/test_activity_weather_sensitive_guess.py` (신규, 17건)

- 사용자가 준 키워드 예시 전부를 `@pytest.mark.parametrize`로 검증(옥상·광장·공원·거리·운동장 → True, 층·홀·실내·전시실 → False, 단서 없음 → None)
- 상충 케이스("○○공원 3층 전시홀") → `None`
- DB 확정값이 있으면 이름을 절대 안 본다(`read.weather` 미호출 확인)
- DB가 모를 때만 추정하고, 추정 사실이 근거·경고·decisions에 남는지
- 단서가 없는 장소("경복궁")는 DB가 몰라도 기상을 억지로 안 부르는지

## 3. 검증 방법과 결과

```bash
python -m py_compile app/modules/travel_ops/activity.py

# 사용자가 준 예시 즉석 확인
python -c "... ActivityTeam._weather_sensitive_from_title('서울숲 공원')"  # → True
# 서울숲 공원→True, 3층 전시실→False, 옥상 전망대→True, 실내 클라이밍짐→False,
# B1 푸드코트→False, 경복궁→None(단서 없음, 억지 추정 안 함)

python -m pytest tests/unit/travel/test_activity_weather_sensitive_guess.py -v   # 17 passed
python -m pytest tests/unit/travel tests/unit/core tests/contract tests/architecture -q \
  --ignore=tests/contract/test_declared_refs_are_savable.py
# → 582 passed, 3 skipped, 5 failed(전부 기존 무관 이슈)
```

`wiki/teams/activity.md` "① 검증 규칙" 절에 `weather_sensitive` 전용 서브섹션 신설, "걸리는 것" 표에 "완화"로 갱신(완전히 닫히지 않았음을 명시 — 키워드에 안 걸리는 장소는 여전히 모름, 근본 원인인 `places` 쓰기 경로 부재는 그대로).

## 4. 미해결 이슈·다음 작업 제안

- 키워드 목록은 사용자가 준 예시 그대로다 — 실제 TourAPI 장소명 표본으로 재현율(recall)을 측정하지 않았다.
- 근본 원인(TourAPI가 실내/실외를 안 주고 `places` 쓰기 경로가 없다는 것) 자체는 안 고쳤다 — 이 추정은 완화책이지 해결책이 아니다.
- `contenttypeid`/신분류체계 대분류(레포츠·자연관광 vs 문화시설 등)로 보강하는 방법은 검토하지 않았다 — 이름 키워드만 썼다.

## 참조

- `app/modules/travel_ops/activity.py`
- `tests/unit/travel/test_activity_weather_sensitive_guess.py`
- `wiki/teams/activity.md`
- 이전 리포트: `2026-09-20_2200_...`(일정 제출 capability)
