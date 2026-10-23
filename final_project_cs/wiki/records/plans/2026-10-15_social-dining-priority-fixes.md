# SNS 링크 일정 반영 우선 결함 3건 수정 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** 식이 조건·고객의 실제 지점 선택·지역을 포함한 식당 검색을 함께 보존한다.

**Architecture:** 생성 조건은 기존 revision별 intake claim으로 보관하고 조립·최종 확정·SNS 검증에서 읽는다. 장소 병합은 서로 다른 지점명과 모순된 좌표를 우회하지 않는다. 검색은 기존 query 계약을 유지하면서 이름과 지역·지점 힌트를 분리하고, 기존 자유 검색의 명확한 지역 앞/뒤 표기도 보완한다.

**Tech Stack:** 기존 Python/FastAPI/psycopg/pytest. 신규 패키지·DB 스키마 없음.

**Spec:** 사용자 승인한 우선순위 1~3 묶음 수정. 결함 근거: [기능 검토](../reports/2026-10-15_social-dining-review.md), 현재 계약: [SNS 링크](../../external/social-dining-links.md).

## Global Constraints

- tenant/customer와 현재 revision 경계, 실패 시 일정 미변경, 명시적 적용·최종 확정 경로 유지.
- v2 추출 프롬프트·모델·수집 경로·통지·업체 거래·DB 운영 데이터는 변경하지 않는다.
- 기존 dirty 작업을 보존한다. `_backup/2026-10-15_social-dining-fixes/`에 덮어쓰기 전 사본을 둔다. 커밋·푸시·배포는 이번 범위에 없다.
- 이전 worktree 생성은 Windows 긴 캐시 경로 때문에 실패했다. 이번 작은 수정은 파일 담당을 나누고 현재 작업 폴더에서 수행한다.
- 아래 구현 방식은 승인된 수정 목표를 달성하기 위한 담당자의 판단이다.

## Review Focus

- 생성 직후·링크 미리보기·적용·최종 확정에서 같은 식이 조건이 유지되어야 한다.
- 저장 설문의 일부만 응답해도 다른 영역의 생성 조건이 없어지면 안 된다.
- 같은 건물의 본점/별관과 이름이 비슷한 다른 가게를 합치면 안 된다.
- 지점명이 없는 제공자 결과가 서로 다른 지점 후보를 하나로 연결하면 안 된다.
- 지역을 포함한 검색과 기존 상호 자체에 지역이 들어간 검색을 모두 보존해야 한다.

### Task 1: 생성 조건 보존

**Files:** `social_dining_plan.py`, `assemble.py`, `trip_api.py`, 신규 `test_social_dining_constraints.py`.

**Interfaces:** `trip.constraints` claim → assemble body.constraints. `_intake_survey(..., base=None)`는 생성 조건을 바탕으로 저장 답과 최종 요청을 영역별로 합친다. `social_dining._dietary_requirements`는 현재 revision claim을 추가로 읽는다.

- [x] 조건 유실과 부분 설문 덮어쓰기에 대한 실패 시험 확인.
- [x] 기존 claim/조립 경로로 저장·확정 조건 복원.
- [x] preview/apply의 조건 근거 읽기와 확인 불가 시 보류 시험.

### Task 2: 지점 선택 보호

**Files:** `social_dining.py`, 신규 `test_social_dining_identity.py`, 기존 지점 병합 회귀 시험.

**Interfaces:** `_same_place(a,b)`는 명시적 지점 충돌과 위치 모순을 우회하지 않는다. 지점 없는 결과가 본점/별관 둘 다와 겹치면 제공자 중복으로 합치지 않는다.

- [x] 같은 주소의 본점/별관 선택 변경·먼 좌표·지점 없는 중간 후보 실패 시험.
- [x] 실제 동일 지점의 제공자 중복은 유지하되 모순된 후보를 분리.
- [x] 고객 선택·식사 미리보기·명시 적용 후 실제 저장 장소 확인.

### Task 3: 이름·지역·지점 검색 분리

**Files:** `candidates.py`, `social_dining.py`, 신규 검색 시험.

**Interfaces:** `candidates.search(..., query, name_hint=None, area_hint=None, branch_hint=None)`. DB는 이름 힌트, 외부 검색은 전체 query, 지역은 기존 AreaIndex 또는 주소 근거로 확인한다. 기존 raw query는 정확한 상호 검색 우선, 결과가 없을 때 명확한 앞/뒤 지역만 보완한다.

- [x] SNS 이름+지역, 중복 지점, 기존 웹 앞/뒤 서울 검색, 지역 포함 실제 상호의 실패 시험.
- [x] 기존 query 호출자 호환과 지역 불일치·미확인 후보 처리.
- [x] 세 수정을 통합해 관련 회귀 시험과 독립 코드 검토 수행.

검증 결과·남은 범위는 별도 날짜 보고서와 wiki 로그에 남긴다. 나머지 수집 범위·GET 제안 복구·v2 누락 개선은 이 수정으로 완료 처리하지 않는다.

최종 검증: 관련 **176/176 = 100%**, 이동 제외 여행 단위 **4,055/4,055 = 100%**. 전체 실행에서 남은 이동 실패 15건과 초기 DB 설정 문제는 [수정·검증 보고](../reports/2026-10-15_social-dining-priority-fixes.md)에 구분한다.
