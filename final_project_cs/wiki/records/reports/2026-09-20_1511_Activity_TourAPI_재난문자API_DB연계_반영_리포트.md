---
type: report
title: Activity — TourAPI·재난문자API 연동과 제안 DB 스키마를 activity.md에 반영
status: done
domain: travel
---

# Activity — TourAPI·재난문자API 연동과 제안 DB 스키마를 activity.md에 반영

## 1. 작업 목표

`wiki/teams/Activity_모듈_스펙.md`(TourAPI·재난문자API 신규 연동 스펙)와 `wiki/teams/데이터베이스_저장소_설계_v2.md`(제안 DB 스키마)를 `wiki/teams/activity.md`에 반영한다.

## 2. 실제 수행 내용

변경 파일: `wiki/teams/activity.md`

1. "② 감시 소스" 표 — "운영 공지" 출처 미확보를 **닫힘**으로 정정(TourAPI·재난문자API로 확정). "기상청 초단기예보" 행에 날씨 조회가 현재 구현 범위 밖(9절로 이동)이라는 정정 추가.
2. "③ 재계획 후보" 절 — `activity.propose_change`가 분류 경로에서 애초에 선택되지 않는다는 사실(`registry.py:115~119`) 추가. 기존에 있던 "LLM 후보 생성 없음"과는 별개의 문제로 명시.
3. 신규 섹션 "## TourAPI · 재난문자API 연동 (확정)" 추가 — 판정 순서(정원→TourAPI→재난문자API), 조회 시점·재검토 주기(TourAPI D-1/당일, 재난문자 3시간 전부터 5분 폴링), 사용 필드·DB 연계 표, 미확보 항목(실패 처리·판정 기준·Case 상태 저장 여부·캐시 공유).
4. 신규 섹션 "## 알려진 결함 — 코드 실측" 추가 — `Activity_모듈_스펙.md`가 정리한 기존 코드 결함 6건을 file:line과 함께 옮김.
5. manifest 절에 `allowed_tools`·`knowledge_scope`가 신규 연동과 어긋난다는 미확보 정정 추가.
6. 신규 섹션 "## 데이터 저장 — 제안 스키마" 추가 — `activities`·`tour`·`disaster` 테이블 요약. **실제 마이그레이션(`app/infrastructure/db/migrations/`, 13개 파일)에 이 세 테이블이 없다는 사실을 직접 확인해 대조 표시**(대신 `places`·`place_catalog`·`watch_observations`·`watch_changes`가 이미 있음).
7. "## 걸리는 것" 표 — "운영 변경 정보 출처" 항목을 닫힘으로 정정, "기상 조건 임계값" 항목에 범위 밖 정정 추가, 신규 미확보 5건 추가(실패 처리·판정 기준·저장 여부·스키마 충돌·manifest 어긋남).
8. "## 관계" 절에 두 원본 문서와 `../data/migrations.md` 링크 추가.

## 3. 검증 방법과 결과

문서 반영 작업. 실제 마이그레이션 테이블 목록과의 대조는 이전 세션에서 `psql \dt`로 직접 확인한 결과(26개 테이블, `activities`/`tour`/`disaster` 없음)를 근거로 썼다. 코드 실행 검증은 해당 없음.

## 4. 미해결 이슈·다음 작업 제안

- `allowed_tools`·`knowledge_scope`를 신규 연동에 맞게 바꿀지는 Contract-first 원칙(RULE.md §3.5)에 따라 **코드보다 문서 결정이 먼저다.**
- 제안 DB 스키마(`activities`/`tour`/`disaster`)를 그대로 마이그레이션할지, 기존 `places`/`watch_observations` 계열에 흡수할지 결정 필요.
- TourAPI·재난문자API 실패 처리가 기존 결함(정보 부재를 성립으로 넘기는 패턴)을 반복하지 않도록 설계 시점에 확인 필요.

## 참조

- `wiki/teams/activity.md` (이번 수정 대상)
- `wiki/teams/Activity_모듈_스펙.md`
- `wiki/teams/데이터베이스_저장소_설계_v2.md`
- `app/infrastructure/db/migrations/` (실제 스키마 대조)
