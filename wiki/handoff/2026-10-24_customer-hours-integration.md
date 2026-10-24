---
type: handoff
title: 고객 운영시간 최신팀 격리 통합
description: 날짜위험 패치를 보존한 고객 일정 한정 운영시간과 독립검토 경계
status: draft
domain: travel
---

# 부모 독립리뷰 인계

- 신규 통합본: profile scratch `customer_hours_integration_01`.
- 기준: 팀 `325ba25d88c91ce97da61f2bda635e5888fe3b40` + 날짜위험 tree `4bbbe3bf671cfaccc49a77247697cad09e6d0dc0`.
- 산출물: scratch `customer_hours_delivery_01/changes.patch`, `delivery-manifest.json`, `manifest.json`, `scope-disposition.json`, `verified-code-hashes.json`, `verified-results.json`, `verified-*.xml/log`, `dependencies-verification.json`.
- 입력 검증→hours claim→검토/SSE→웹 편집/저장/표시→등록 detail→TripStore/새벽/교체를 연결했습니다. 새 팀의 등록 여행 재개 경로(`reopen.py`)와 웹 데이터 매핑(`from-review.ts`)은 26후보 밖이지만 실제 caller여서 manifest에 먼저 추가했습니다.
- 공식 출처가 우선하며, 고객값은 이 항목 detail와 읽기용 장소 보기에만 존재합니다. Google unknown/unmatched만 고객 판정으로 보충합니다. source failure/deferred를 성공으로 바꾸지 않습니다. 날짜 cache/deferred, 최신 검색/add-search/check:false는 보존합니다.
- 검증: 기능 40/40 = 100%; 영향 backend 1030/1030 = 100%; architecture/contract/security 607/607 = 100%; 웹 1159/1159 = 100%. 기능은 backend 묶음에 포함됩니다. Ruff F/E9, tsc, eslint, Next build 각각 exit 0. 최종 실행은 동일 코드 해시와 개별 자식 returncode/XML로 확인했습니다.
- 원본/기존 검증사본에 쓰지 않았으며 앱·서비스·실DB·배포·push를 실행하지 않았습니다. UI는 React SSR 부품 및 실제 편집 모델 검증이지 운영 브라우저 e2e가 아닙니다.
- 남은 검증: 부모 독립리뷰; 승인된 격리DB 기반 e2e/실제 인증·트랜잭션; 전체 `scripts.verify_dod_v11`(하위프로세스 안전 startup guard 작성 승인이 만료되어 중단, 우회 없음). 이 항목들은 통과로 주장하지 않습니다.
- 기존 지도 unknown 전용 필터/바로가기 스타일은 최소 통합에 수입하지 않았습니다. 기존 「직접 고치기」로 편집합니다.
- 최초 부분 의존성 복사, 잘못된 endpoint 시험 응답 경로, UNC cwd의 Node startup/prerender 오류를 숨기지 않고 로그에 남겼습니다. 최종 검증에서는 해결했습니다.

자세한 [격리 통합 기록](../../final_project_cs/wiki/records/reports/2026-10-24_customer-hours-integration.md)을 참조하십시오. 패치는 **날짜위험 tree 위에 적용하는 고객시간 차분**이며 원본에 역복사하지 않습니다.
