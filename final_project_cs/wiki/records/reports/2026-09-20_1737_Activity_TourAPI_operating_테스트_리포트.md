---
type: report
title: Activity — TourAPI operating 배선의 정식 단위 테스트 추가
status: done
domain: travel
---

# Activity — TourAPI operating 배선의 정식 단위 테스트 추가

## 1. 작업 목표

이전 세션에서 배선한 `activity.py`의 TourAPI `operating` 처리(운영시간 원문을 근거·안내 문구로만 쓰고 `feasible` 판정에는 안 쓰는 동작)에 정식 pytest 파일을 추가한다. API 키·DB·네트워크 없이 검증 가능해야 한다.

## 2. 실제 수행 내용

신규 파일: `tests/unit/travel/test_activity_tour_operating.py` (`test_activity_weather.py`와 같은 패턴 — `FakeTools`로 `ReadToolbox`/DB/네트워크를 전부 우회)

- `test_operating_text_is_surfaced_in_the_answer` — 원문이 answer·decisions·evidence(`tool:activity:read.place.operating`)에 실리는지
- `test_operating_text_never_flips_feasibility` — ★핵심 회귀 가드. 휴무를 시사하는 원문(`"오늘은 임시휴무입니다"`)이 와도 `feasible`이 `True`로 유지되고 "불가"·"휴무로 인해" 같은 파생 단정 문구가 안 생기는지
- `test_no_operating_info_does_not_claim_it_was_checked` — `operating`이 아예 없을 때(신원 미해소 등) 아무 말도 안 만드는지
- `test_operating_present_but_empty_does_not_claim_it_was_checked` — 소스는 응답했지만 쓸 필드가 없을 때 "확인했다"고 말하지 않는지

`wiki/teams/activity.md` "판정 순서" 절에 테스트 추가 사실과 핵심 회귀 가드의 의미를 기록.

## 3. 검증 방법과 결과

```bash
python -m pytest tests/unit/travel/test_activity_tour_operating.py -v
# → 4 passed

python -m pytest tests/unit/travel -q
# → 122 passed (기존 118건 + 신규 4건, 회귀 없음)
```

## 4. 미해결 이슈·다음 작업 제안

- 이 테스트는 `activity.py`의 로직만 본다. `read_tools.py`의 `_fill_operating()`이 실제 DB·TourAPI 클라이언트와 맞물려 도는지 보는 더 아래 단계 테스트(`ReadToolbox(travel=FakeTravel())` 수준)는 아직 정식 파일이 없다 — 이전 세션의 즉석 스크립트로만 확인했다.
- 실제 서비스 키로 하는 end-to-end 확인은 여전히 안 했다(키가 없음).

## 참조

- `tests/unit/travel/test_activity_tour_operating.py`
- `tests/unit/travel/test_activity_weather.py`(참고한 기존 패턴)
- `wiki/teams/activity.md`
- 이전 리포트: `2026-09-20_1718_...`(배선 작업)
