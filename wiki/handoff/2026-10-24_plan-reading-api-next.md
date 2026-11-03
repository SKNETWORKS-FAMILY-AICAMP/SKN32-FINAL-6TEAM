---
type: guide
title: 계획 읽기 복원 검증과 실제 API 연결 인계
status: draft
domain: travel
---

# 계획 읽기 복원 체크포인트

## 한 일·검증

부모가 2026-10-24 현재 코드로 격리 runner를 재실행해 계획 읽기·intake·작성기 관련 unit 285/285 = 100%, exit 0을 직접 확인했습니다. 실행 로그는 현재 프로필 cache/scratch/plan-reading/parent-final-green.log입니다. DB·앱 네트워크 접속을 차단했으며 실제 공급자·API·DB·화면·운영 검증이 아닙니다.

신규 intake agent_read/fact_check/fragments/gaps/prefill 및 pipeline/review/llm_spans의 선별 통합만 완료했습니다. 기존 운영시간 입력과 조회 tail을 보존했습니다. 정상 API→process는 기존 reader로 남아 있으므로 고객 입구 활성화 완료가 아닙니다. 책임과 실패 정책을 코드보다 먼저 기록한 계약은 아래 링크를 따릅니다.

## 정상 입구 연결 결과

[부모303/303 재실행과 미적용DB 전제](../records/reports/2026-10-24_plan-reading-api-parent-checkpoint.md). 실제 API handler→process→stream 어댑터 로컬 연결은 완료했지만 I/O는 대역입니다. 다음 새 child에 계획서 최종 응대 연결을, 별도 child에 공급자 독립 검토를 넘겼습니다. DB 실제 적용·운영 배포는 승인하지 않았습니다.

## 최종 응대·공급자 독립검토 후속

[부모318/318·공급자안전미완료](../records/reports/2026-10-24_plan-response-safety-checkpoint.md). 새child에취소/절대deadline/매시도예산/정확출처/원문외부차단/905준비검사를TDD로넘겼습니다. 운영활성화보류입니다.

## 공급자 안전 수정 후속

[부모398/402실행·4HTTP차단·API동시변경감지](../records/reports/2026-10-24_reader-safety-parent-checkpoint.md). 새readonly child에원안전결함범위독립확인을인계했습니다. 외부fallbackfalse이며실transport취소/DBdriver한계를남깁니다.

## 독립 확인에서 다시 열린 결함

stream 생략 하위 read_source → agent_read → 일반 structured 경로에서 외부 기본 차단과 strict reader_budget을 우회하는 반례를 독립 대역으로 재현했습니다. 정상 process API는 stream을 검증·주입하므로 그 입구에서 곧바로 재현됐다는 뜻은 아닙니다. 기존25/25 통과와 별개로 결함을 열고, 새 child에 정확반례 RED→최소수정→정상입구 회귀를 넘겼습니다. 상세는 [부모 체크포인트 추가 기록](../records/reports/2026-10-24_reader-safety-parent-checkpoint.md)을 따릅니다.

## stream 생략 반례 수정 부모 확인

[cs TDD 수정·350고유범위](../../final_project_cs/wiki/records/reports/2026-10-25_reader-stream-policy-omission-tdd.md). 부모도 새출력폴더에서409개를재실행해405통과/4HTTPbind차단,실행중1297hash동일을확인했습니다. 새child에모든백엔드후속을포함한중복제거단일통합검증을넘겼으며실DB/모델/화면승인은남습니다.

## 다음 절·경계

새 child는 명시적으로 기존 설정·모델 제공자·process 및 API에 새 읽기 경로를 연결하고, 성공·실패·미설정 경계를 실제 정상 입구 unit으로 검증합니다. 이전 순수 경계를 테스트만 통과한 채 전체 완료로 보고하지 않습니다. 기존 모델명·임계값을 새 하드코딩으로 대체하지 않습니다. SQL 파일 추가는 가능하나 DB 실제 적용·서비스/모델 호출·운영 배포·커밋·푸시는 하지 않습니다. 필요한 운영값과 승인 미확정은 보고합니다.

동시 작업: 다른 child가 conversation 날씨 후속을, 또 다른 child가 response 작성기와 trip_api 메시지 응답 투영을 수정합니다. 이 절은 intake/process·trip_api 접수 구간·필요 공급자/설정/마이그레이션만 소유하며 메시지 _web_view·conversation·response/writing.py를 수정하지 않습니다. 최신 파일 재열람과 부분 패치로 변경을 보존합니다.

## 관계

- [순수 경계 복원 결과·실패로그·제한](../../final_project_cs/wiki/records/reports/2026-10-24_plan-reading-restoration.md)
- [복원 계약](../../final_project_cs/wiki/external/plan-reading-restoration.md)
- [라이팅 전체 진행 인계](2026-10-24_travel-writing-implementation.md)
