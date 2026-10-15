---
type: report
title: 로컬 개발 DB 합성 후보 스키마 준비
status: verified
domain: travel
---

# 로컬 개발 DB 합성 후보 스키마 준비

동의 철회에 필요한 합성 후보 표 두 개를 로컬 개발 DB에 추가했습니다. 기존 고객 행과 원격 DB는 변경하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 대상·누락 확인 | 완료 | 1/1 = 100% |
| 기존 SQL 229 적용 | 완료 | 1/1 = 100% |
| 실패한 동의 철회 재검증 | 통과 | 2/2 = 100% |

## 적용 범위

기존 [229_service_improvement.sql](../../../app/infrastructure/db/migrations/229_service_improvement.sql)만 단일 트랜잭션으로 실행했습니다. 두 표와 관련 함수가 모두 없음을 적용 전에 확인했습니다. 새 표 2개, 열 12개, 제약 7개, 트리거 1개, 인덱스 1개를 적용 후 확인했고 새 표의 행은 각각 0개였습니다. 기존 소스 SQL은 수정하지 않았습니다. 기존 객체 덮어쓰기가 없어서 백업 대상 원본 객체도 없었습니다.

`intake_test_scenarios` 표(230)는 이미 존재했습니다. 이번 범위에서는 다른 SQL 파일의 적용 여부를 전수 대조하지 않았습니다. 현재 실행기는 파일별 적용 이력표 없이 전체 SQL을 다시 실행합니다. public 스키마에서 migration/schema-version 이름의 후보 표도 찾지 못했으므로 파일별 적용 목록을 주장하지 않습니다. 전체 실행기는 재실행하지 않았습니다.

## 검증과 운영 반영 구분

- 로컬 개발 DB 합성 시험: `test_consents.py::test_withdrawing_a_required_item_stops_the_app_again`, `test_an_agent_key_follows_its_owner_and_cannot_record_consent` 2/2 통과, 6.84초.
- mock 서버 시험: 사용하지 않았습니다.
- 실서버 확인(서버 응답): 로컬 개발 DB에 연결한 cs 프로젝트 API TestClient 경로를 확인했습니다. x600 서버의 cs 프로젝트 API·DB는 확인하거나 변경하지 않았습니다.
- 운영 배포 시 이 기능에는 229의 두 표·함수·트리거·인덱스가 필요합니다. 운영 DB의 현재 적용 여부는 미확인입니다. 운영에서는 먼저 대상 객체 유무를 대조하고 필요한 변경만 적용해야 합니다.

## 실행 증거

- [적용 전 객체 확인](../evidence/2026-10-11_1936_team_plugin_implementation/local-db-schema-before-229.json)
- [적용 후 객체·SQL 해시](../evidence/2026-10-11_1936_team_plugin_implementation/local-db-schema-after-229.json)
- [동의 철회 시험 로그](../evidence/2026-10-11_1936_team_plugin_implementation/local-db-consents-after-229.log)

접속 문자열·비밀번호·고객 행은 증거에 기록하지 않았습니다.
