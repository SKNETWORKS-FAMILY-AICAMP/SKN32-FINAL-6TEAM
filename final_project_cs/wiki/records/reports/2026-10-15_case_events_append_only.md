---
type: report
title: case_events 추가 전용 DB 잠금
description: 사건 기록 표 case_events 를 DB 트리거로 「추가만」 지키게 한 마이그레이션 904 와 정리 경로 · 시험 변경
status: done
tags: [core, db]
domain: travel
---

# case_events 추가 전용 DB 잠금 (2026-10-15)

`[사용자 지시 2026-10-15 · 작업: 「Teamflow」 세션 · 커밋: 커밋 세션]`

## 결론
사건 기록 표 `case_events` 는 코어 규칙상 「추가만」 하는 표인데 DB 잠금이 없었다(원격 role-manager · develop 둘 다 확인). 동의 기록 표(046)와 같은 방식으로 마이그레이션 `904_case_events_append_only.sql` 을 더했다.

- UPDATE 는 늘 거절한다.
- DELETE · TRUNCATE 는 그 트랜잭션에서 `SET LOCAL app.case_events_purge = 'on'` 을 켠 정리 작업만 허용한다.
- 이미 있는 행은 검사하지 않는다(앞으로의 변경만 막는다). INSERT 는 막지 않는다.

## 바꾼 곳
- 앱 정리 경로 4곳이 같은 트랜잭션에서 스위치를 켠다: 여행 삭제(`trip_delete.purge_cases`) · 시나리오 정리(`case_engine.cleanup_tenant`) · 스크립트 `cleanup_test_residue.py` · `try_case.py`.
- 시험 16개 파일이 정리할 때 같은 스위치를 켜고, 공용 보조 `tests/helpers/case_events_purge.py` 를 새로 뒀다. 새 시험 `tests/integration/db/test_case_events_append_only.py`.
- 커밋 세션 확인: 원격 최신 판의 앱 · 스크립트 · 배포 폴더에서 `case_events` 를 지우거나 고치는 곳은 위 4곳뿐이다(시험 코드는 검색 범위 밖). `case_events` 의 외래 키는 연쇄 삭제가 없다.

## 시험
- 전용 임시 DB, CI main 순서: 마이그레이션 전체 적용 · 재적용 통과 · `test_migrations_rerun` 통과 · 새 시험 통과 · 바뀐 시험 파일 18개 통과 · architecture + migration 계약 197 통과 · `tests/contract` 347 통과 · ruff F·E9 통과.
- 삭제 경로 관련 추가 시험 약 25개 파일 중 `test_unattended_operations.py` 20개만 건너뜀(이유 미확인).
- 못 돌림: 실제 LLM 키가 필요한 live 시험 1개, 전체 병렬 실행(메모리 부족).
- 코덱스 검토(스테이징 차이, 읽기 전용): 문제 없음.

## 운영 영향 · 확인하지 않은 것
- x600 서버의 cs 프로젝트 DB 에는 다음 자동 배포 때 904 가 적용된다. 그 뒤로 DB 에 직접 `DELETE` · `UPDATE` 를 치는 수동 작업은 스위치 없이는 거절된다.
- 실서버 확인 안 함(배포 뒤 여행 삭제가 실제로 되는지 한 번 볼 것).
