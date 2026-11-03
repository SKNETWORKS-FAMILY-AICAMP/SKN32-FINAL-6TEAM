---
type: report
title: ST4F-746 아침 이동 읽기 복구 독립 검토
status: draft
domain: travel
---

2026-10-29 Codex 독립 검토. **기능 후보는 이번 제한 시험에서 타당하며 릴리스는 HOLD입니다.** 원본과 다른 보안 스캐너로 얻은 통과를 원본 보안 관문 통과로 사용할 수 없습니다. 통합·커밋·push·배포·운영 DB 변경·보안 완화·자료 삭제는 모두 0건입니다.

## 검토 결과

1. **보안 HOLD 유지:** 원본 `tests/security/test_no_infra_in_tracked_files.py`의 불변 `find_leaks`로 후보 CS 추적 파일을 다시 검사하면 10,871개 중 텍스트 9,674개에서 4개 파일, 탐지 10건이 나옵니다. 경로별 건수는 scanner 자체 1, Activity fallback 2, Activity text evidence 1, social_links 6입니다. 실제 인프라 유출로 모두 확정한 것은 아니며 예외의 타당성은 별도 검토 대상입니다. 이번 검토에서 예외나 탐지 기준을 바꾸지 않았습니다.
2. **원래 결함은 실DB/API에서 재현됩니다:** 보존된 `registered_moves.before.py`의 `recover_for_routes`만 프로세스 메모리에서 사용했습니다. 실제 접수→확인→등록 후 PG의 해당 아침 이동 행을 제거하고 GET하면 HTTP 200이지만 아침 이동이 없습니다. 최신 원본 키/구형 키 없는 데이터 두 경우 모두 같은 실패입니다. 후보에서는 동일 DB 절차로 복구되고 반복 GET의 이동 ID가 같으며 저장 행은 복구 전과 같습니다. 기준 전체 코드를 되돌린 시험은 아니며 아침 복구 함수의 전후 비교입니다.
3. **여행·고객 경계:** 서로 다른 고객이 같은 숙소·목적지·날짜로 실제 여행을 등록해도 항목 ID 집합은 겹치지 않았고 첫 여행의 읽기 복구 ID가 둘째 여행에 나타나지 않았습니다. 양방향 다른 고객 GET은 404였습니다. 임의 고객/여행에 대한 `load_trip_review`는 None, 없는 여행 GET은 404입니다. SQL은 tenant/customer/trip/status로 연결된 확정 접수를 고르며 요청에서 받은 다른 접수 ID를 사용하지 않습니다. 같은 고객의 여행 두 개는 비회원 1개 제한으로 시험하지 못했습니다. 구형 값 매칭의 안전성은 이 SQL 소유권 경계를 전제로 합니다.
4. **시간대·숙소 매칭:** UTC로 저장된 목적지가 전날이어도 서울 날짜로 아침 이동을 생성했습니다. 숙소 source_id와 index 각각 불일치, 체크아웃 날짜 변경, 좌표 변경, 목적지 날짜 변경, 숙소 end_date 누락, 구형 중복 매칭을 거절했습니다. 기존 이동 보존·반복 복구 멱등성·입력 불변성도 확인했습니다. 추가 복구 코드는 `_match`를 완화하지 않습니다. 시간대 없는 timestamp는 이번 시험 범위 밖입니다.

## 실행 증거

기존 격리 후보 `C:/_proj/final_workspace/scratch/teamflow-continue-20261029/repo/final_project_cs`와 기존 `st4f746_review` DB/PG55495를 재사용했습니다. 새 checkout·DB·전체 데이터 사본은 만들지 않았습니다. 테스트별 subprocess 제한은 240초이며 실제 실행은 모두 그 안에서 끝났습니다. pytest cache/bytecode 생성을 끄고 Git 조회는 격리 후보에서 `GIT_OPTIONAL_LOCKS=0`으로 수행했습니다. 원본 Git은 실행하지 않았습니다.

모든 새 runner·시험·로그·XML·해시·스캐너 집계는 [독립 증거 폴더](../../../../scratch/st4f746-morning-independent-20261029/)에 있습니다. 실행 명령은 루트에서 `python scratch/st4f746-morning-independent-20261029/run.py <단계>`입니다. DB fixture·장소·모델·이동 제공자는 여행 시험 대역이며 저장소와 SQL은 실제 PostgreSQL, API는 실제 FastAPI TestClient입니다. 외부 지도 정확도·실LLM·브라우저·운영 배포는 검증하지 않았습니다. fixture 날짜 상수 이름과 달리 실제 실행 일정은 2027-03-14~15이며 예보 범위 밖 경고가 있습니다. 정확한 실행 날짜는 로그를 따릅니다.

| 단계 | 실제 결과 | 판정 |
|---|---|---|
| unit | 20/20 = 100% | 기존 의미 시험 9 + 후보 회귀 6 + 독립 경계 5 |
| timezone | 2/2 = 100% | 전날 UTC → 다음 날 서울 날짜, 최신/구형 |
| db | 2/2 = 100% | 실제 등록·SQL 누락·읽기 복구·DB 불변·stale 거절 |
| cross-db-v2 | 1/1 = 100% | 실제 두 고객/두 여행·양방향 404·ID 불교차 |
| cross-db 초기 구성 | 0/1 = 0% | 두 번째 비회원 여행 생성이 guest_trip_limit 403으로 거절됨. 시험 구성 한계이며 로그/XML 보존 |
| baseline-db | 0/2 = 0% | 수정 전 함수가 실제 DB 누락 아침 이동을 복구하지 못함 |
| baseline-api | 0/2 = 0% | 수정 전 API 200 응답에 누락 이동 없음, 기대한 실패 재현 2/2 = 100% |
| omit 변이 | 14/20 = 70%, 6실패 | 아침 복구 제거를 검출 |
| overwrite 변이 | 18/20 = 90%, 2실패 | 기존 이동 앞 중복 삽입을 검출 |

변이 검출은 2/2 = 100%입니다. 두 변이는 별도 프로세스 메모리에만 적용했으며 후보 파일을 수정하지 않았습니다. 최초 scanner 실행은 시스템 Python에 pytest가 없어 ModuleNotFoundError로 끝났고, 구성된 시험 interpreter로 실행한 scan-v2가 성공했습니다. 관문·전체 회귀는 이번에 재실행하지 않았습니다. 이전 계약367/367·보안125/125·DoD26/26은 이전 후보 환경 결과입니다.

## 스캐너·XML 불일치와 보존

`strict-diagnostic.json`의 원본 scanner raw SHA256은 `ab4c349e5f614a7d1f25932d354ea9c472fd9471619f4a6832bce8bb9f12ff94`, 후보는 `3d3ac186596e0d7ca1a33d1c0f85a9e0f7fc80e532b1dff68f0b01f7642a135d`입니다. 후보에는 공개 주소 예외가 있습니다. 이전 scope-comparison의 후보 SHA와 현재 raw SHA도 같지 않으므로 그 수치를 현재 raw-byte 동일성 증거로 쓰지 않습니다. 전체 repo 추적 수와 CS만 센 수 역시 다른 범위입니다. 이번 진단은 원본 detector + 후보 CS 추적 파일이라는 범위를 고정했습니다.

이전 XML을 독립 파싱하면 review/security.xml은 **124/125 = 99.2%**이며 실패 원인은 Git subprocess WinError 5입니다. 이후 review/security-v3.xml과 morning/security.xml은 각각 **125/125 = 100%**입니다. 후자의 통과는 후보 scanner 기준이므로 원본 detector 진단 4파일과 모순되지 않습니다. 어느 XML도 고치거나 재생성하지 않았습니다.

[independent-audit.json](../../../../scratch/st4f746-morning-independent-20261029/independent-audit.json)은 이전 보호 대상 **335/335 = 100%**, 이전 XML **344/344 = 100%**의 실제 SHA256 일치를 재검산합니다. 이 두 집합은 겹치므로 더하지 않습니다. 새 세션이 보호한 이전 증거/후보 XML/scanner/구현은 [preservation.json](../../../../scratch/st4f746-morning-independent-20261029/preservation.json)의 **422/422 = 100%**가 불변입니다. 한글이 `?`로 손상된 기존 보고·인계는 보존했고 새 문서로 보완했습니다.

루트/CS AGENTS·RULE·CLAUDE, wiki 역할·Mobility·웹 접수·여행 조회 계약과 호출부를 읽었습니다. 이전 coord 79개 및 현재 NOTICE 80개를 읽어 후보가 반환된 상태와 HOLD를 확인했습니다. 현재 coord 원문은 로컬 private 증거에 보관했습니다. 다른 작업자에게 메시지를 보내거나 tracker를 변경하지 않았습니다.

## 인계

아침 복구 후보의 제한 검토는 완료했습니다. 보안 scanner 차이의 승인·정합성 해결, 최신 원격 통합 및 그 환경의 필수 관문·운영 수락은 남아 있습니다. 이번 필수 관문 재실행은 **0/3 = 0%**이며 기능 시험 성공으로 대신하지 않습니다. HOLD를 풀거나 push하지 않습니다.

PG55495는 처음에 중지된 상태였고 이번 실행 후 다시 정상 중지했습니다. DB는 **15,834,135 bytes**이며 그대로 보존했습니다. disk_guard inventory는 등록 0건, 미등록 관리 폴더 0건, 여유 **182,920,646,656 bytes**를 보고했습니다. 이 기존 scratch 후보는 ledger 등록 대상이 아니어서 반환 명령으로 설정을 바꾸지 않았습니다. 새 파일별 크기·총량은 증거 폴더 `sizes-final.json`에 남깁니다. 대형 산출물·삭제는 없습니다.
