---
type: report
title: 신규 계획 전체 과거 날짜 가드 독립 후보
status: draft
domain: travel
---

# 2026-10-25 전체 과거 날짜 가드 — 독립 hotfix 후보

## 확정 계약

신규 등록할 일정 항목이 비어 있지 않고, 모든 항목의 시작·종료 달력 날짜가 제품의 기존 서울 시간 기준 오늘보다 엄격히 앞설 때만 이 가드로 거절합니다. 일부 과거 + 오늘/미래, 오늘만, 미래만은 **이 가드에서 차단하지 않으며** 기존 운영시간·이동·필수정보 검사는 그대로 유지합니다. 날짜 미정/빈 목록을 전체 과거로 추정하지 않습니다. 숙박·야간 일정은 실제 종료 날짜가 오늘/미래이면 차단하지 않습니다. 시각이 지났더라도 날짜가 오늘이면 이 가드의 거절 대상이 아닙니다. 원문 날짜·일정 삭제/자동 이동은 하지 않습니다.

## 독립 변경

- `itinerary_checks.all_dates_before_today`: 기존 `seoul`·`KST` 변환과 주입 가능한 `now` 사용. 새로운 timezone/수치/설정 없음.
- `intake.review`: 공개 검사 항목에 `bad` 날짜 안내를 추가하고 `ready=false`. 캐시를 돌려줄 때도 현재 날짜로 다시 검사합니다. 확정 접수와 등록 여행 reopen은 신규 등록 검사를 적용하지 않습니다.
- `trip_api._create_trip`: 기존 멱등 키 조회 뒤 **새 여행 생성 분기만** 공통 날짜 가드로 검사합니다. 기존 API 오류 `itinerary_infeasible`와 `all_dates_in_past` 위반, 안내 “모든 일정이 오늘 이전이에요. 여행 날짜를 확인해주세요”를 반환합니다. confirm·API 등록은 같은 생성 함수를 사용하므로 저장된 review의 ready 값으로 우회하지 못합니다.
- 텍스트/첨부 모두 읽힌 값 이후의 같은 review 단계를 사용합니다. 업로드 제한·명시고정·시간 읽기·Comment9·alias·파일첨부 구현 변경은 포함하지 않습니다.

## 검증과 한계

최신 팀 develop `34a92cb4d8a0cf5966e0578c64455dd313c775dc`에서 새 격리 clone을 만들었습니다. 제품 clock은 변경하지 않았고 시험 clock만 고정했습니다. 원본 작업 폴더·AGENTS/CLAUDE·런타임 서버·공유 고객 DB·모델 호출은 변경하지 않았습니다.

helper RED→GREEN, 공개 review RED→GREEN, 정상 `/v1/trips` endpoint의 새 여행 쓰기 경계 진입 RED→가드 422 GREEN을 보존했습니다. 좁은 검증에는 여러 과거 날짜·혼합 날짜·빈/미정·종료일 오늘/미래·UTC/서울 자정·캐시·confirmed/reopen 제외·기존 생성 멱등 반환이 포함됩니다. 증거는 세션 scratch `allpast-hotfix-20261025-2005`의 JUnit/log에 있습니다.

전체 develop 관문·보안 스캔·실DB·confirm 정상 호출의 최종 상태와 commit/push 여부는 별도 `REPORT_KO.md`/`PUSH_MANIFEST.json`을 확인해야 합니다. 이 문서는 운영 반영 완료를 뜻하지 않습니다. 선행 `gh auth status`는 미인증, 개인 원격 조회는 인증 오류여서 4대상 원격 반영이 차단되어 있습니다. 공개 팀 최신 develop의 기존 CI는 성공으로 조회했습니다.
