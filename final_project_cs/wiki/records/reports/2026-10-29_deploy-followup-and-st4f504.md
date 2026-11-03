---
type: report
title: x600 ST4F-711 배포 읽기 검증과 ST4F-504 격리 재검증
status: draft
domain: travel
impl_scope: cs
---

# x600 배포 확인과 ST4F-504 후속 검증

2026-10-29 02:18~02:25 KST 확인입니다. 루트 AGENTS·CLAUDE(루트 RULE 없음), cs AGENTS·CLAUDE·RULE, 양쪽 wiki 목차·인계 목차·ST4F-711 백엔드 보고서와 관련 호출부를 확인했습니다. `_coord`의 T·S3·R·V·ST4F711 NOTICE를 읽고 별도 `Codex-deploy-followup-20261029-NOTICE.md`에 경계를 게시했습니다. 다른 세션에 응답을 받았다고 주장하지 않습니다.

## 배포와 고객 입구

SSH에서 읽은 x600 배포 장부 `deployed_sha`는 `217da9ad07d16374b2401924418b7115f81769ab`, `current_tag`와 API의 `ACOP_DEPLOYMENT_VERSION`은 `217da9ad07`입니다. API·웹·관리자 컨테이너가 healthy이고 worker는 실행 중입니다(worker health 판정은 제공되지 않았습니다). 웹 이미지 ID는 [실측 JSON](../evidence/2026-10-29_deploy-followup-and-st4f504/x600.json)에 있습니다.

최종 문서 tip `3dd9bd70c9d1c598f70faad69cf755141cc4a041`과 소스 `217da9ad07` 사이 배포 입력(app·config·knowledge·prompts·scripts·deploy·web·admin·requirements.txt)의 Git 객체가 **9/9 = 100%** 일치합니다. `auto_deploy.sh`는 해당 입력 fingerprint가 같으면 재빌드를 생략합니다. 따라서 실행 SHA를 `3dd9bd70`이라고 바꾸어 보고하지 않습니다. **소스 217da9ad07 배포 확인, 문서 tip까지 제품 입력 동일 확인**입니다. 현재 원격 tip을 새로 검증한 결과와도 구분합니다. 이전 양쪽 push 확인은 [기존 최종 증거](../evidence/2026-10-29_st4f711-backend-gates/final-push-result.json)를 따릅니다.

| x600에서 공개 도메인으로 보낸 요청 | 실측 | 기대와 일치 |
|---|---|---|
| GET `/health` | 200 | 예 |
| GET `/` | 200 | 예 |
| GET `/start` | 200 | 예 |
| 인증 없이 GET `/v1/web/trips` | 401 | 예 |

입구 확인은 **4/4 = 100%**입니다. [원시 상태 코드](../evidence/2026-10-29_deploy-followup-and-st4f504/x600-public-get.log). 인증·쿠키·고객 토큰 없이 GET만 보냈습니다. 이 PC의 Python 직접 요청(`/health`, `/`, `/register`, `/api/health`)은 403으로 차단됐습니다. `/register`·`/api/health`를 제품의 유효한 경로로 판정하지 않았으며, 이 결과로 전체 공개 접근 성공을 주장하지 않습니다. 403 원인은 미확정입니다.

고객 등록·접수·인증된 여행 조회·실패 뒤 화면 복귀는 이번 운영 검증에서 실행하지 않았습니다. 서버 접근 로그 같은 통상 관측 기록은 생길 수 있으나 고객 업무 쓰기 요청, 수동 배포, 설정 변경은 0입니다.

## ST4F-711 종결 판단

[백엔드 관문 보고서](2026-10-29_st4f711-backend-gates.md)의 필수 **3/3 = 100%**, PG 동시성 **41/41 = 100%**, 웹 **1,224/1,224 = 100%**는 기존 실행 증거입니다. 이번에 다시 돌렸다고 보고하지 않습니다. 이번 실측은 배포 SHA와 공개 GET 입구의 미확인을 보완했습니다.

**전체 종결은 보류합니다.** LB-09 당시 입력·URL·요청 원본을 확보하지 못해 현재 수정 결함과 동일 원인인지 알 수 없습니다. 이번 GET 확인도 운영에서 실패 뒤 복귀 동작을 증명하지 않습니다. 기존 격리 브라우저 시험은 모형 API였다는 한계를 유지합니다. 운영 인수 전체 분모는 모릅니다. TeamFlow 상태 변경은 하지 않았습니다.

## ST4F-504 이어서 검증

기존 TeamFlow 스냅샷(688건)의 ST4F-504는 `test_concurrent_duplicate_replies_have_single_team_execution`의 develop `928b7ff1` 불안정 실패를 다룹니다. 현재 이슈 상태를 새로 조회한 것은 아닙니다. 다른 세션의 T·S3 담당 파일을 피하고, 기존 검증 clone을 읽어 새 고유 scratch에 필요한 코드·시험을 복사했습니다. 원본 코드 변경은 없습니다.

새 PostgreSQL 16.15 클러스터를 loopback `55493/st4f504`로 만들고 제품 마이그레이션을 실행했습니다. Python 3.12.15·pytest 8.4.2, 기존 deps와 Composer 패키지를 읽어 사용했습니다. 합성 여행 fixture·대역 Team을 쓰며 실제 모델·외부 공급자를 호출하지 않았습니다. fixture 정리는 이 새 시험 DB의 자체 생성 행에만 적용됩니다.

| 실행 | 결과 |
|---|---|
| 현재 재개 시험 파일 | **19/19 = 100%**, 실패·오류·건너뜀 0 |
| 같은 동시 답장 시험을 서로 다른 fixture로 30회 실행 | **30/30 = 100%**, 실패·오류·건너뜀 0 |

첫 실행은 필수 합성 설정 4개 누락으로 마이그레이션 전에 실패했습니다. 설정만 추가하고 다시 실행했으며 최초 로그는 보존했습니다. 같은 nodeid를 명령에 30번 적은 첫 시도는 pytest가 1건만 수집했습니다. 이를 30회로 세지 않고 별도 매개변수 probe로 **실제 30개 testcase**를 확인했습니다. 파일 19건과 반복 30건은 같은 동작이 겹치므로 독립 보장 49개라고 해석하지 않습니다.

현재 `_resume`은 토큰 검증·소비 시 행 잠금을 쓰고, 중복 재개 경로의 `ActiveRunError`·`StateConflict`를 처리합니다. 이 코드를 읽은 사실과 이번 통과만으로 10-15 실패의 원인을 특정하지 않습니다. 역사적 develop의 코드·환경·부하와 대조가 남아 있으므로 **ST4F-504는 미재현, 종결 보류**입니다. 제품 수정·커밋·push는 0입니다.

실행: `python test504.py`로 준비·전체 파일 검증, `python repeat504.py`로 매개변수 30회 probe. 준비 스크립트의 최초 DB 생성은 v1 실행 로그에, 설정 보완 뒤 실행은 v2 로그에 남았습니다. [시험 요약과 입력 객체](../evidence/2026-10-29_deploy-followup-and-st4f504/summary.json) · [전체 파일 로그](../evidence/2026-10-29_deploy-followup-and-st4f504/504-file-v2.log) · [30회 로그](../evidence/2026-10-29_deploy-followup-and-st4f504/504-repeated30-v2.log).

## 보존과 다음 작업

새 scratch: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/deploy-followup-20261029-v1`. 실패·성공 로그, JUnit XML, 복사 코드, PG data를 보존합니다. 자체 PG만 정상 종료했고 55493 연결 거부를 확인했습니다. 다른 세션 프로세스·자료 변경, 파일 삭제는 0입니다. 기존 지침·기록은 덮지 않았습니다.

다음 담당자는 ST4F-711 운영 복귀 동작을 쓰기 없는 증거로 더 확인하거나, 승인된 시험 계정 범위에서 검증할 수 있습니다. LB-09는 원본 확보 전 원인을 붙이지 않습니다. ST4F-504는 역사적 develop에서 같은 probe를 실행해 현재 결과와 비교해야 합니다. T·S3 변경을 통합하려면 최신 원격과 그 NOTICE를 다시 확인합니다.

[증거 manifest](../evidence/2026-10-29_deploy-followup-and-st4f504/manifest.json).
