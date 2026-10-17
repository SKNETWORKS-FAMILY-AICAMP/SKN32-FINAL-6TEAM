---
type: record
title: 새 예시의 최초 숙소 추천과 수정 화면 즉시 표시
status: implementation_verified
domain: travel
date: 2026-10-17
---

# 새 예시의 최초 숙소 추천과 수정 화면 즉시 표시

저장된 계획은 양일 같은 호텔로 정상이었지만, 예시를 새로 불러오면 처음 자동으로 채우는 경로에서 숙소가 빠졌다. 수정 화면도 수정 접수의 전체 검사 응답이 오기 전까지 기존 일정을 지우고 로딩 화면을 보였다. 구현·격리 검증은 마쳤으며 최종 운영 반영과 화면 검증은 커밋푸시 담당 세션의 배포 뒤 확인한다.

## 원인과 수정

- 최초 채우기가 이름 없는 미정 호텔까지 `lodging_name → ask_customer`로 보냈다. 미정 숙소를 기존 숙소 자동 추천에 연결하고, 예약·고정 숙소의 이름은 고객 질문으로 유지했다. 공통 숙소 연결은 기존 검증·저장 경로를 사용한다. 고객이 입력하지 않은 조식 끝 시각만 검증된 추천으로 채우고 입력한 시각은 보존한다.
- 접수 조회는 채우기 완료 전 상태를 읽기로 표시했지만 실시간 진행은 DB의 내부 완료 상태를 읽어 먼저 끝났다. 둘이 같은 공개 상태 계산을 사용하도록 고쳤다. 채우는 중에도 생존 표시·실패 확정·중단 감지를 유지한다.
- 공통 숙소의 여러 날짜가 이동 계산 몫 하나를 소진했다. 앞 후보가 한 날짜에만 맞을 때 뒤 후보까지 검증할 여유가 부족할 수 있었다. 기존 시간 상한을 날짜별로 적용하며 고객이 고른 이동 수단과 같은 질문의 기억을 유지한다. 실제 새 접수에서 숙소 미정이 남았고, 뒤의 읽기 전용 재계산에서는 세 번째 호텔이 양일에 맞았다. 시간 한도 결함은 호출당 6초를 모의한 회귀 시험으로 구별해 확인했다. 특정 호텔·좌표를 코드에 고정하지 않았다.
- 수정 화면은 기존 여행의 장소·시각·지도를 즉시 표시한다. 수정 접수 응답 전에는 검사 통과를 만들지 않고 변경·완료를 막는다. 준비 중 취소도 접수가 만들어지면 닫아서 다음 수정에 남지 않게 한다. 지난 일정·잠금·예약·판 충돌의 판단은 응답과 기존 API가 계속 맡는다.

## 검증

| 확인 범위 | 결과 | 조건 |
|---|---|---|
| 숙소·빈칸 단위 시험 | 27/27 통과 | 느린 첫 이동 계산의 날짜별 예산 포함 |
| 관련 HTTP·계약·보안 회귀 | 438/438 통과 | 최신 통합 사본에 변경을 3방향 병합, 격리 DB·mock 자료 |
| Git 의존 검사 | 이번 격리 묶음에서 미실행 | 검사 이미지에 Git 도구가 없어 `test_api_key_file.py`, `test_no_infra_in_tracked_files.py` 두 파일 제외. 커밋푸시 담당의 최종 통합 검사 대상 |
| 수정 화면 단위 시험 | 5/5 통과 | 저장된 값 즉시 표시, 검사·판 번호를 지어내지 않음 |
| 수정 전환 mock 서버 시험 | 3/3 통과 | 375·1280px, 응답을 잡아 둔 상태에서 1초 안에 기존 일정·취소 표시, 변경 비활성, 준비 중 취소 |
| 공개 웹 후보 | 802/802 통과 | lint·typecheck·전체 단위 시험·build 성공. 최종 배포 전 후보 |
| 첫 API 후보 이미지 | 34/34 통과 | 최종 날짜별 예산·SSE 후속 전의 중간 판이며 최종 검증으로 합산하지 않음 |

주요 명령:

```text
pytest tests/unit/travel/test_intake_gaps.py tests/unit/travel/test_intake_shared_lodging.py -q
pytest tests/unit/travel/test_intake_gaps.py tests/unit/travel/test_intake_shared_lodging.py tests/e2e/test_intake_lodging_recommendation.py tests/e2e/test_intake_prefill.py tests/e2e/test_intake_progress_events.py tests/e2e/test_trip_reopen.py tests/contract tests/security --ignore=tests/contract/test_api_key_file.py --ignore=tests/security/test_no_infra_in_tracked_files.py -q
playwright test trip-edit-opening-20261017.spec.ts
npm run lint && npm run typecheck && npm run test && npm run build
```

mock 서버 시험 3/3 (화면 반응): 응답 지연·변경 차단·준비 중 취소. 최종 실제 화면 확인과 구분한다.

실서버 확인 (서버 응답): 했음. 공개 서비스의 기존 저장 계획 양일 숙소 동일, 새 예시 최초 추천 실패와 읽기 전용 후보·적합성 재계산을 확인했다. 최종 수정판의 새 예시 자동 추천·수정 모드 화면은 배포 뒤 확인할 항목이다.

## 반영 범위와 보존

최신 사용자 지시로 추가 수정은 개인·팀 `role-manager`에만 우선 반영하고 추가 `develop` 반영은 보류한다. 배포는 별도의 커밋푸시 담당 세션이 실행한다. 지시 전에 중간 숙소 처리 수정판을 운영 API·worker에 적용한 이력이 있으나 최종 완료로 표시하지 않는다. 이번 작업에서 운영 DB 스키마 변경·마이그레이션 SQL은 실행하지 않았다. 시험 접수는 기존 API를 사용했고 저장 결과는 읽기 전용으로 조회했다.

기존 파일은 `_backup/2026-10-17_mobile-lodging-edit/`, 후속 수정 전은 `_backup/2026-10-17_mobile-lodging-edit-r2/`에 보존했다. 백업·개인 실행 스크립트·접속 구성은 커밋하지 않는다. 변경 담당자가 검토를 겸했으며 독립 검토 완료로 표시하지 않는다.
