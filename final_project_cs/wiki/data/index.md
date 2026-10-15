---
type: guide
title: 여행 데이터 안내
description: 여행 일정·장소·예약·감시·요식 데이터와 SQL 적용 문서의 입구
status: draft
tags: [data, documentation]
domain: travel
---

# 여행 데이터 안내

여행 업무 데이터의 기준은 현재 SQL 파일과 실행 중인 DB의 조회 결과를 구분해서 확인합니다.

| 알고 싶은 것 | 정본 |
|---|---|
| 여행 데이터의 역할과 관계 | [스키마 안내](schema/index.md) |
| SQL 파일 목록·실행 순서·적용 주의 | [SQL 적용 안내](migrations.md) |
| 고객별 데이터 격리 | [테넌트 격리](tenancy.md) |
| 실제 SQL | [SQL 폴더](../../app/infrastructure/db/migrations/) |
| 현재 여행 안내 검색 자료 | [적재 명세](../../knowledge/current-travel/manifest.json) · [Oracle ARM 적용 범위](../records/reports/2026-10-12_0454_arm-search-model-repair.md) |

주요 데이터는 여행·일정 판본·일정 항목, 장소 목록, 예약, 접수·대화, 사용자 인증, 항로 지킴이 관측·변경 기록, 요식 데이터입니다. Case·Action·Outbox는 공통 업무 상태와 실행 기록을 담당합니다.

2026-10-11 디스크에서 SQL 실행 대상 파일 **89개**, `pending/` 파일 **1개**를 확인했습니다. 이것은 적용 완료 수나 운영 DB 테이블 수가 아닙니다. 이번 문서 정정에서는 로컬 개발 DB와 x600 서버의 cs 프로젝트 DB를 조회하거나 변경하지 않았습니다.

쇼핑몰 데이터는 현재 여행 시험·평가·시연에 쓰지 않습니다. [D-023](../../../wiki/decisions/D-023-no-commerce-assets-in-use.md)의 2026-10-06 작업은 로컬 개발 DB에 한정됐으며, 그때 x600 서버의 cs 프로젝트 DB는 변경하지 않았습니다. 이후 상태는 해당 환경에서 다시 확인해야 합니다.

## 이전 문서

2026-10-11 정정 전 본문은 [보존본](_backup/2026-10-11_193844_current-facts/index.md)에 있습니다. 이전 측정·실험 결과를 현재 제품의 완료 증거로 사용하지 않습니다.

## 관계

- [문서 작성 표준](../../../wiki/governance/document-standard.md) — 정본·근거·이력 분리 규칙

## 확인 범위

[실측 2026-10-11 작업 트리] 파일 수·입력 행 수·현재 경로는 [변경·계수 기록](../../../program/research/wiki_review_2026-10-11/applied-current-facts-v3.json)에 남겼습니다. 배포 상태나 DB 적용 완료 수가 아닙니다.
