---
type: report
title: Activity — 재난문자 가데이터 배선과 등급 판정 함수 구현
status: done
domain: travel
---

# Activity — 재난문자 가데이터 배선과 등급 판정 함수 구현

## 1. 작업 목표

사용자가 "재난문자 API 가데이터도 추가하고 판정하는 함수 만들어줘"를 요청. TourAPI operating/휴무 요일 대조 때와 같은 구조로 — `read.disaster` 도구 신설, `activity.py`에 판정 함수 추가, `FakeTools` 기반 가데이터 테스트 — 구현했다.

## 2. 실제 수행 내용

### `app/infrastructure/travel/base.py`
- `TravelSources`에 `disaster: Any | None = None` 슬롯 추가(클라이언트는 여전히 없음 — 슬롯만 먼저 둠)
- `build_travel_sources()`에 `unavailable["disaster"]` 추가 — "키 문제가 아니라 클라이언트 자체가 없다"고 다른 `unavailable` 항목들과 원인을 구분해 명시

### `app/tools/read_tools.py`
- `disaster()` 도구 신설(`weather()`와 같은 패턴 — lat/lng/at을 받아 `self.travel.disaster.near(...)`에 위임, 좌표 없으면 `None`)
- `_travel_tools()`에 `"read.disaster": self.disaster` 등록

### `app/modules/travel_ops/activity.py`
- manifest: `allowed_tools`에 `"read.disaster"`, `knowledge_scope`에 `"disaster"` 추가
- `_check_feasible()`: `read.disaster`를 날씨와 달리 **weather_sensitive 여부와 무관하게 항상** 호출(재난은 실내외 안 가림). `disaster_blocks` 결과를 `weekday_match`와 함께 `feasible` 계산에 합침
- `_disaster_blocks(messages)`: **"위급재난" 등급 하나만** 판정을 막는다(긴급재난·안전안내는 근거로만 전함) — "몇 단계부터 막을지" 미확보를 가장 보수적인 선택으로 닫음
- `_disaster_note(messages, blocks)`: 사실만 전한다. 막힐 때는 "지역·주제 관련성은 확인하지 않았다"는 캐비앗을 **반드시** 붙인다 — `_disaster_blocks`가 등급만 보고 재해구분·수신지역은 안 보기 때문

### `tests/unit/travel/test_activity_disaster.py` (신규, 5건)
- `test_critical_disaster_blocks_feasibility_with_caveat` — 위급재난 1건 → `feasible: False` + 캐비앗·경고 필수
- `test_lower_grade_messages_are_surfaced_but_do_not_block` — 긴급재난·안전안내 → 안 막음
- `test_no_disaster_messages_says_none_confirmed` — 빈 목록은 "없다"고 정직하게
- `test_no_disaster_source_does_not_claim_it_was_checked` — 소스 `None`(현재 실제 상태) → 조용히 넘어감
- `test_disaster_tool_is_not_even_declared_in_the_fake_when_omitted` — 옛 테스트 호환(`read.disaster` 키 없어도 안 죽음)

`wiki/teams/activity.md` 갱신: "재난문자 등급 대조 — `check_feasible` 배선" 절 신설, manifest 코드 블록 갱신, "걸리는 것" 표 갱신, "재난문자API는 코드 0줄" 서술을 "클라이언트는 없지만 배선·판정 함수는 있다"로 정정.

## 3. 검증 방법과 결과

```bash
python -m py_compile app/modules/travel_ops/activity.py app/tools/read_tools.py app/infrastructure/travel/base.py

python -m pytest tests/unit/travel/test_activity_disaster.py -v      # 5 passed
python -m pytest tests/unit/travel -q                                # 137 passed (기존 132 + 신규 5)
python -m pytest tests/contract tests/architecture -q \
  --ignore=tests/contract/test_declared_refs_are_savable.py          # 258 passed, 4 failed(전부 기존 무관 이슈)
```

manifest에 `read.disaster`를 추가했음에도 기존 `FakeTools` 기반 테스트들이 전부 그대로 통과했다 — `FakeTools.call()`이 dict에 없는 도구 이름에 `None`을 돌려주는 방식이라(예외 아님), `"read.disaster"` 키가 없는 옛 테스트들도 자연히 "모름"으로 처리돼 하위 호환이 저절로 됐다.

## 4. 미해결 이슈·다음 작업 제안

- 재난문자API 실제 클라이언트(`self.travel.disaster`의 구현체)는 여전히 없다 — TourAPI(`tour_api.py`, 313줄)와 달리 완전히 새로 만들어야 한다.
- `_disaster_blocks`가 지역(`RCPTN_RGN_NM`)·재해구분(`DST_SE_NM`)을 전혀 안 본다 — 등급만 보고 막기 때문에, 활동 장소와 무관한 지역의 위급재난 문자로도 잘못 막힐 수 있다. 캐비앗 문구로 한계는 알리지만 근본 해결은 아니다.
- `watch_observations`(016)를 통한 배경 감시와 이번 `check_feasible` 실시간 판정은 서로 다른 경로다 — 둘을 합칠지는 별도 결정 필요.

## 참조

- `app/infrastructure/travel/base.py`, `app/tools/read_tools.py`, `app/modules/travel_ops/activity.py`
- `tests/unit/travel/test_activity_disaster.py`
- `wiki/teams/activity.md`
- 이전 리포트: `2026-09-20_1918_...`(휴무 요일 대조 — 같은 구조의 첫 사례)
