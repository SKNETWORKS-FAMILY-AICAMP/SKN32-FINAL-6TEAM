# 관리자 예약 OFF / 로컬 실행기 비DB 누적 정식이력 통합

확인 시각: 2026-10-25T06:39:19.622253+09:00. 통합 담당: 이 격리 작업. 다음 새 독립검토는 부모 담당이며 아직 수행하지 않았습니다.

## 결론

검토 수락 admin tree `fc35fb10321789fdd720f3740eb13595a97183f2`를 누적 commit `26bd740f81176cf59bef8210c1cc62f98f024cdd` 위에 내용 기반 3-way 통합했습니다. integration commit `607776d147a8ccdd923eec348f8f0c335892b3c4`, 검증 제품 tree `d2e72812a00113d9b50ca0395bd5fc854d61abfe`. 단독 33/33 = 100% 경로는 수락 admin blob과 정확히 같으며, 겹침은 wiki 3경로뿐입니다. 양쪽 추가 기록·링크 누락 0. 현재 live/private env 또는 개인 설정을 복사하지 않았습니다.

| 실제 새 실행 | 결과 |
|---|---|
| launcher 전체 cmd/PowerShell 대역 | 18/18 = 100%, 서비스·socket 실행 없음 |
| 관리자 Vitest | 41/41 = 100% |
| core 예약/계약 | 141/141 = 100% |
| 기존 비DB + core 단일 영향 시험 | 997/1004 = 99.30%, 원문상충 3실패 + bind 4차단 유지 |
| 관리자 lint/typegen/tsc 전후/webpack 전체 build | 개별 종료 코드 모두 0, 정적 생성·trace 포함 |

core와 기존 965 XML의 exact identity 합집합을 새 단일 XML과 비교했습니다. 중복 합산하지 않았고 과거 7실패 identity와 동일합니다. 시험 전후 추적 입력 hash 변경 0. 기능 코드·시험 assertion은 수락 tree 그대로입니다.

## 병합·검증 경위

최초 read-tree -m은 내용 병합을 하지 않아 wiki index/handoff 3경로를 stage1/2/3으로 남겨 assert 실패했습니다. 제품 충돌 또는 prior merge-clean의 반증이 아닙니다. 실패 기록과 별도 index를 보존하고 새 후보 object-only merge-tree로 내용 병합했습니다. ours/theirs 전체선택 없이 양쪽 추가 line 및 실제 tree 링크 존재를 검사했습니다. exact byte/33경로 hash/정역 patch/tree/whitespace와 원본 fingerprint는 외부 FINAL.json·검증 JSON을 참조합니다.

시험 wrapper 최초 실행은 Python `-m pytest`의 module 토큰을 marker 식으로 잘못 치환해 pytest 수집 전 실패했고, XML 부재를 무조건 파싱한 2차 오류가 원인을 가렸습니다. 원래 stdout/stderr와 raw child 종료 코드를 별도 재현 보존하고, marker의 두 번째 `-m`만 수정·XML 존재부터 기록하도록 wrapper를 바로잡아 `combined-02` 새 prefix로 재실행했습니다. UUID 보조파일과 hostname metadata guard도 유지했습니다. 시험 삭제·분모 축소는 없습니다.

754건 `combined-02` 실행에서는 계약 디렉터리와 그 내부 2파일의 중복 선택으로 contract 250건이 수집 누락됐습니다(의도 subset 아님). 추가 실패 1건은 `test_public_booking_default_then_explicit_on_then_current_off_persists`: 공개 `/v1/web/features`는 startup guard의 `demo` tenant를 읽고 fixture의 관리자 쓰기는 `booking-test` tenant를 썼습니다. 동일 source·정확한 node에서 demo 1/1 실패 → booking-test 1/1 통과를 대조했습니다. 제품·assertion·auth 경계는 변경하지 않았고 합성 환경 tenant만 원래 core runner와 맞췄습니다. 중복 file selector는 상위 디렉터리에 포함되는 것을 검산한 뒤 제거하고 `combined-03`에서 기존965/core141의 exact 합집합을 다시 실행했습니다. 754/8fail 기록과 선택 누락 inventory는 보존했습니다.

기존 날짜 기준 누적 whitespace HOLD·strict-budget 미수락은 그대로 남습니다. 원문상충 3실패 또는 bind 4차단을 통과로 변환하지 않았습니다. 원격 최신/CI 재조회는 이번 오프라인 범위 밖입니다.

## 반영/실행 경계

**실제 서비스 실행과 인증된 예약 OFF 저장 → fresh GET은 DB 소유 세션 인계 대기입니다.** 현재 서비스의 예약 OFF 적용/DB 저장 성공을 주장하지 않습니다. 원본 final_workspace/파이널스페이스 및 기존 실행 중 후보에 쓰지 않았고, 새 scratch repo만 통합·시험했습니다. DB·모델·외부 API·서비스 시작·원본 적용·push·배포는 하지 않았습니다.

## 근거 및 다음 인계

작업 산출물: `final_admin_non_db_integration/repo`, `INTEGRATION.json`, `admin-path-manifest.json`, `wiki-merge-verification.json`, `nodeid-closure.json`, `core-results.json`, `combined-03-results.json`, `admin-execution.json`, `source-preservation.json`, `FINAL.json`.

부모는 최종 HEAD/tree/patch manifest로 새 독립검토를 진행합니다. DB 준비 인계 뒤 별도 승인된 실행 세션에서 실제 앱·로그인·revision-aware OFF 저장/재조회가 필요합니다. 테스트 통과율은 제품 전체 완성도나 운영 적용률이 아닙니다.
