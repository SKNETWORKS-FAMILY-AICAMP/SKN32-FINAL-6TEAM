---
type: guide
title: 결정·구현·검증·환경 반영 상태 표시
description: 문서 검토와 제품 변경을 구분하고 환경별 확인 시각·근거를 연결한다
status: draft
domain: travel
impl_scope: cs — 현재 SQL 환경 예시와 제품의 상태 표시 대상이며 sample 실행을 추정하지 않는다
---

# 결정·구현·검증·환경 반영 상태 표시

문서 검토, 결정 채택, 구현, 실행 검증, 환경 반영을 각각 표시합니다. 결정이 확정돼도 구현·배포 완료를 뜻하지 않습니다. 현재 주요 대상은 [자동 적용 목록](implementation-inventory.generated.md)에 있고, 확인하지 않은 구현·환경은 `unverified`로 표시합니다.

## 머리말과 본문을 함께 읽기

| 위치 | 항목 | 의미 |
|---|---|---|
| 머리말 | `status: draft / stable / deprecated` | 문서 검토 상태. draft는 결정 취소·미구현을 뜻하지 않음 |
| 머리말 | `decision_status: accepted` | 명시적 결정이 채택됨. 근거·결정일은 본문에 연결 |
| 머리말 | `implementation_status: planned / partial / implemented / unverified` | 해당 개정 요구의 구현 범위. 코드 존재만으로 승격하지 않음 |
| 머리말 | `validation_status: unverified / partial / verified` | 해당 변경의 실행 검증. 실패·건너뜀·남은 필수 시험은 본문에 기록 |
| 머리말 | `verified_at` | 시간대가 있는 실행 검증 시각. 문서를 편집한 시각과 구분 |
| 머리말 | `supersedes` | 명시적으로 대체한 문서·절의 참조. 파일 날짜만으로 대체를 추론하지 않음 |
| 본문 | 환경·상태·확인 시각·근거 | 로컬 작업 트리, 로컬 개발 DB, x600 서버의 cs 프로젝트 코드·DB를 구분 |

`verified_at`의 예시는 `2026-10-12T03:08:44+09:00`입니다. `supersedes`는 실제로 대체하기로 한 문서 경로와 절을 적고 본문에도 클릭할 수 있는 링크·이유를 둡니다. 결정일·문서 수정일·시험 시각·배포 시각은 서로 대신하지 않습니다.

기존 `implemented-local`·`implemented-partial`은 검사 경고로 구분하며 새 표준 값으로 채택하지 않습니다. 해당 기능 담당자가 현재 범위를 확인한 뒤 정규 값과 환경별 표로 옮깁니다. 초안의 선택 필드를 모두 필수로 바꾸거나 일괄 승격하지 않습니다.

## 적용·검사의 범위

[검사기](../../program/scripts/check_wiki.py)는 현재·생성 문서에 기존 형식 규칙과 구현·검증 상태 값, 시간대 포함 시각 형식을 검사합니다. 기록은 기본 검사에서 제외하고 `--include-records`일 때 링크 낡음 통계만 냅니다. 백업·이관·숨김 폴더는 제외하며 시험 코드의 백업 표식도 현재 집계에서 제외합니다.

새 필드가 없는 초안은 위반으로 처리하지 않고 자동 목록의 미적용 필드로 남깁니다. 결정 근거의 진실성·상태와 코드의 의미 일치·시험 통과·배포·리뷰어 승인은 자동 판정하지 않습니다. `--check`는 [생성기](../../program/scripts/build_wiki_catalogs.py)의 출력 일치만 확인합니다.

상태를 갱신할 때 해당 개정의 범위와 본문 환경별 표를 먼저 확인합니다. 일부 단위 시험 통과를 전체 기능의 `verified`로 확대하지 않습니다. 기능별 병렬 구현 문서는 담당자가 결과를 받은 뒤 갱신합니다. 최종 기능 결과의 접합은 통합 담당 범위입니다.

## SQL 예시의 현재 확인 결과

아래는 이번 세션에서 DB를 새로 조회한 결과가 아니라 **2026-10-12 기존 실행 기록을 다시 읽어 확인한 결과**입니다. 옛 안내의 “양쪽 DB에 옛 표가 남음 / x600 제외 규칙 없음”은 2026-10-11 조사 시점의 상태이며 현재 상태로 인용하지 않습니다. [정리 전 조사](../../program/research/sql_review_2026-10-11/index.html#sql)는 그대로 보존합니다.

| 환경·범위 | 기록에서 확인한 상태 | 원 실행 시각(KST) | 근거 |
|---|---|---|---|
| 로컬 개발 DB·정확히 지정한 옛 표 5개 | 삭제 후 조회에서 5개 중 잔존 0개 | 2026-10-12 03:08:44 | [원 조회](../../program/research/sql_retirement_2026-10-12/local-audit-only.json), [요약](../../program/research/sql_retirement_2026-10-12/summary.json) |
| x600 서버의 cs 프로젝트 DB·같은 표 5개 | 삭제 후 조회에서 5개 중 잔존 0개 | 2026-10-12 03:07:49 | [원 조회](../../program/research/sql_retirement_2026-10-12/deployed-verify.json), [요약](../../program/research/sql_retirement_2026-10-12/summary.json) |
| x600 서버의 cs 프로젝트 API·worker 코드 | 실행 대상 81개·역사 보존 4개를 구분한 적용 기록과 파일 해시 있음 | 요약에 독립 probe 시각 미표시 | [적용 결과](../../program/research/sql_retirement_2026-10-12/deployment-final.json) |
| 이후 SQL 실행 원자성·향후 배포 안전 개선 | 별도 SQL 담당 구현·격리 시험 진행. 이번 조사에서 운영 반영 미확인 | unverified | [담당 작업 자료](../../program/research/migration_safety_2026-10-12/) |

정확한 표 이름과 스키마 의존을 확인한 범위입니다. 다른 이름·JSON 내부 업무값 전수 감사, 제품 전체 인수 시험을 뜻하지 않습니다. 작업 트리의 SQL 파일 수는 자동 목록에서 읽고 과거 기록의 파일 수·DB 적용 수와 섞지 않습니다. 로컬 업무 DB 전체 SQL 재실행은 자동 승인 검토에서 거절돼 격리 복원 DB 재실행으로 검증한 기록입니다.

## 관계

- [머리말 규격](front-matter.md) — 기존 OKF 메타데이터
- [문서 표준](document-standard.md) — 현재 규칙·근거·기록 구분
- [리뷰 정책](review-policy.md) — 문서 승격과 독립 검토
- [후속 구현·검증 결과](../../program/research/baseline_completion_2026-10-12/tasks/wiki/report.md) — 현재 검사·미적용 목록·한계·백업
- [상태 기록 흐름도](../../program/research/baseline_completion_2026-10-12/tasks/wiki/state-recording.html) — 근거 확인과 미확인 표시
