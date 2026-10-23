---
type: guide
title: SQL 파일과 적용 방식
description: 89개 실행 대상과 1개 보류 파일, 실제 실행기의 동작 및 환경 확인 범위
status: draft
tags: [data, documentation]
domain: travel
---

# SQL 파일과 적용 방식

2026-10-11 현재 SQL 실행 대상 파일은 **89개**, 보류 폴더의 SQL은 **1개**입니다. 이 숫자는 디스크에서 센 파일 수이며 DB 적용 수가 아닙니다.

## 실행기가 실제로 하는 일

[migrate.py](../../../app/infrastructure/db/migrate.py)의 `apply_all(conn)`은 `migrations/*.sql`을 **파일명 정렬**로 읽고 하나의 SQL 문자열로 합쳐 **한 트랜잭션**에서 실행합니다. `pending/` 하위 파일은 이 glob에 포함되지 않습니다.

이 모듈은 파일별 적용 이력표를 확인해서 이미 적용한 파일을 건너뛰는 방식이 아닙니다. Alembic 기반이라고 안내하지 않습니다. 모든 SQL의 재실행 안전성을 일괄 보장하지 않으며, `IF NOT EXISTS` 문구만 보고 안전하다고 판단하지 않습니다.

## 환경별 확인 범위

| 대상 | 확인된 근거 | 이번 정정에서 확인한 것 |
|---|---|---|
| 작업 트리 | 아래 SQL 파일·실행기 | 파일 수·이름·실행 범위 확인 |
| 로컬 개발 DB | [D-023](../../../../wiki/decisions/D-023-no-commerce-assets-in-use.md)의 2026-10-06 쇼핑몰 5표 제거 기록 | DB 접속·DDL 실행 안 함 |
| x600 서버의 cs 프로젝트 DB | D-023의 2026-10-06 작업에서는 변경하지 않음 | 현재 스키마·적용 여부 확인 안 함 |

과거 적용 기록은 날짜와 환경을 붙여 인용합니다. 오늘의 적용 완료를 말하려면 해당 DB의 테이블·열·제약을 읽어서 SQL과 대조해야 합니다. 이 문서 정정으로 DB를 변경하지 않았습니다.

## 보류 SQL과 재실행 주의

[015_drop_commerce_domain.sql](../../../app/infrastructure/db/migrations/pending/015_drop_commerce_domain.sql)은 `pending/`에 있으므로 전체 실행기의 대상이 아닙니다. D-023에 따르면 2026-10-06 로컬 개발 DB에는 이 파일을 별도로 적용했습니다. **보류 폴더에 있다는 사실과 어느 환경에 별도 적용했는지는 다른 정보입니다.**

초기 SQL에는 쇼핑몰 표 생성 정의가 남아 있어 전체 실행기를 다시 돌리면 제거한 표를 재생성할 수 있습니다. 기존 환경에 전체 실행기를 무작정 재실행하지 않습니다. 대상 환경·변경 파일·의존 순서·복구 자료·회귀 확인을 정한 뒤 적용합니다. 이번 작업은 문서 정정이며 SQL 적용 승인이 아닙니다.

같은 번호의 새 파일을 만들지 않도록 목록을 확인합니다. 이미 공유한 SQL의 의미를 소급 변경하지 않고 새 변경 파일로 남깁니다. 적용 결과와 검증 기록은 환경별로 보관합니다.

## 실행 대상 전체 목록

[자동 생성 SQL 목록](../../data/migration-inventory.generated.md)에서 실행 대상과 보류 파일을 확인합니다. `python program/scripts/build_wiki_catalogs.py`로 갱신하고 `--check`로 변경 누락을 검사합니다. 파일명 목록을 이 안내에 중복 유지하지 않습니다.

## 관련 문서

- [스키마 역할 안내](../../data/schema/index.md)
- [로컬 개발 환경 안내](../../operations/local-setup.md)
- [멱등성 계약](../../actions/idempotency.md)


## 이전 문서

2026-10-11 정정 전 본문은 [보존본](../../data/_backup/2026-10-11_193844_current-facts/migrations.md)에 있습니다. 이전 측정·실험 결과를 현재 제품의 완료 증거로 사용하지 않습니다.

## 관계

- [문서 작성 표준](../../../../wiki/governance/document-standard.md) — 정본·근거·이력 분리 규칙

## 확인 범위

[실측 2026-10-11 작업 트리] 파일 수·입력 행 수·현재 경로는 [변경·계수 기록](../../../../program/research/wiki_review_2026-10-11/applied-current-facts-v3.json)에 남겼습니다. 배포 상태나 DB 적용 완료 수가 아닙니다.
