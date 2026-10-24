---
type: report
title: 고객 운영시간 P1 격리 후속 수정
description: 완료 SSE 보존과 고객 항목 휴무의 tenant 전파 차단
status: draft
domain: travel
---

# 계약·RED 확인

수정 담당은 P1 수정 에이전트이며 별도 독립 재검토 예정입니다. 기존 전달물·원본·서비스·실DB는 수정하지 않습니다. 신규 `customer_hours_integration_02`는 고객시간 결과 tree `95d256feff83211d2d239c2079b73c2e9bd4f1e4`에서 전체 18,993개 파일을 Git blob 및 기존 사본 바이트와 대조했습니다.

독립 재현 두 건을 변경 없이 새 delivery에 복사하여 실행: **0/2 = 0% 통과, 2 assertion 실패, 오류 0**. 실제 원인은 완료 Feed 공개 필드 누락 및 `_closed_places`의 고객 출처 무구분입니다. 정식 `tests/unit/travel/test_intake_customer_hours_p1.py`에 두 재현과 완료/confirmed·재연결, activity/dining×다른고객/같은고객 다른여행/같은여행 다른항목을 편입했습니다. 수정 전 **0/10 = 0% 통과, 실패10, 오류0**. 메모리 SQLite에서 실제 INSERT/SELECT를 실행하며 `%s` placeholder만 `?`로 변환했습니다.

구현 전 현재 API 계약에 필드 보존·휴무 소비 범위를 명시했습니다. SSE 최소 보완은 기존 완료 item의 두 필드 보존이고, 새벽 최소 보완은 공용 제외 SELECT에서 고객 출처만 분리하는 것입니다. 원래 해당 항목의 판정·기록·대체 요청과 공식 출처 우선·공식 휴무 공유를 유지합니다.

실행 증거는 profile scratch `customer_hours_delivery_02`에 보존합니다. 최초 RED·각 중간 실패는 덮어쓰지 않습니다. 전체 DoD의 기존 startup guard 승인 만료를 우회하지 않으며, 실서비스 DB·운영 E2E·배포 완료를 주장하지 않습니다.

## 최종 실행 — 2026-10-24 10:15 UTC 확인

| 묶음 | 실제 결과 | 근거 |
|---|---|---|
| 정식 P1 회귀 | 10/10 = 100% | `formal-green.xml` |
| 변경 없는 독립 재현 | 2/2 = 100% | `independent-green.xml` |
| 고객시간 기능 | 50/50 = 100% | `feature.xml` |
| 영향 backend 회귀 | 1040/1040 = 100% | `regression.xml` |
| architecture/contract/security | 607/607 = 100% | `gates.xml`; `not live and not db`, 기존 29 deselected |
| 날짜 위험·명시 장소 검색 | 46/46 = 100% | `date-search.xml` |
| 웹 전체 Vitest | 1159/1159 = 100% | `web.xml` |
| Ruff F/E9·TypeScript·ESLint·Next build | 각각 exit 0 | 각 실행 로그 |

모든 위 GREEN 실행의 실패/오류/skip은 0입니다. 기능·P1 시험은 영향 회귀에 포함되므로 합산하지 않습니다. 최종 명령·자식 exit·XML 집계는 `final-results.json`이며 `final-code-hashes.json`의 동일 코드/시험 바이트를 실행 후 대조했습니다. SSE만 수정한 중간 실행은 3통과/7실패였고 새벽 SQL 수정 후 10통과입니다. 기대 완화·검사 삭제·전역 폴백은 없습니다.

제품 코드는 두 파일뿐이며 동작 변경은 완료 item의 두 필드 복사와 `_closed_places`의 고객 출처 제외입니다. NULL 출처 조건은 기존 기록의 조회 의미를 그대로 유지하기 위한 것이며 새로운 정보 폴백이 아닙니다. 신규 SQL 시험은 해당 고객 항목의 판정·저장·대체 요청을 실제 `_apply_verdict`로 실행하고, 실제 INSERT/SELECT 결과 및 다른 항목 무영향·공식 휴무 제외 전달을 확인합니다. 계획 생성과 apply_or_ask 저장은 경계 대역이며 실 PostgreSQL 트랜잭션 E2E가 아닙니다.

의존성은 기존 사본에서 새 사본으로 확장길이 경로를 사용해 복제했으며 27,011파일 바이트 해시 누락/상이0입니다. Python 보안 scanner는 extended cwd와 fail-closed plugin을 유지했습니다. 최종 문서와 인덱스까지 포장 후 같은 607 관문을 `final-gates-results.json`으로 재실행하여 전달 범위를 검사합니다. 패치 두 종류의 적용 재구성 tree, 전체 tracked 접근·blob 대조, 변경 allowlist, 개별 SHA256 및 기존 통합본 불변 확인은 `delivery-manifest.json`에 있습니다.

## 포장 중 실패와 수정

첫 포장에서는 이전 고객시간 tree 기준 공백 검사가 통과했지만 날짜 tree 기준 합본 검사에서 현재 API 계약 문서 16번째 빈 줄의 CRLF를 trailing whitespace로 검출했습니다(exit 2). 추가된 빈 줄만 LF로 고치고 **두 기준 모두** 공백 검사를 다시 수행합니다. 제품/시험 해시는 변하지 않았으며 검사 설정·기대값은 바꾸지 않았습니다. 최초 실패는 delivery `package-initial-failure.log`에 보존했습니다.

## 남은 제약

별도 독립 재검토 전입니다. 전체 DoD, 실DB 기반 새벽 scenario/인증 E2E, 외부 제공처 및 운영 브라우저는 미실행입니다. 웹 결과는 단위·SSR 부품 및 빌드 검증이지 실제 고객 화면 E2E가 아닙니다. 이전 guard 승인 만료를 재시도하거나 우회하지 않았습니다. 원본·기존 전달물·기존 독립리뷰는 수정하지 않았고 커밋·push·서비스·배포를 하지 않았습니다. 수정 전 바이트는 새 delivery `backups/`에 보존했습니다.
