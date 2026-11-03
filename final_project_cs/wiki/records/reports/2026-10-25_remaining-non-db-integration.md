---
type: report
title: 잔여 비DB 3후보 최소 통합·회귀 검증
status: scoped-verification
domain: travel
---

# 잔여 비DB 3후보 최소 통합

확인 UTC: 2026-10-24T19:51:28.840913+00:00. 원본이나 이전 공유 후보가 아닌 새 scratch/remaining_non_db_integration/repo에만 통합했습니다. 코드 통합 3/3 = 100.0%, 읽기전용 독립 검토에서 확인된 F1/F2 수정 2/2 = 100.0%입니다. **전체 GREEN·운영 반영·수정판 독립 승인 완료는 아닙니다.**

## 기준과 재사용

- 최신 팀 develop를 안전 Git 진입점으로 새 후보에 fetch: `325ba25d88c91ce97da61f2bda635e5888fe3b40`. 날짜·고객시간 2커밋이 누적된 기준 HEAD `635cb3424c75f6621bf75430766f27083dfaa00e`, tree `b5bfeeaf30426f9183bfba12f800434287d339b7`. incoming ancestor 확인0:2입니다. 날짜·고객시간 변경은 유지했습니다.
- root/sub AGENTS·CLAUDE·RULE, wiki·README 및 guguroute/review 스킬을 확인했습니다. 루트 RULE, 홈 .codex/AGENTS 및 .claude/CLAUDE는 없으며 창작하지 않았습니다. 지시 파일은 수정하지 않았습니다.
- remaining_patches_independent_review의 최종 REVIEW/verdict/patch-scope를 회수했습니다. 이전 local132/부속1157 분류를 재조사하지 않았고 종류모름 B안4경로는 후속 확정 결정에 따라 복원하지 않았습니다. 별도 운영결정 보류7건은 이번3후보 분모가 아닙니다.
- 3패치 모두 정확한 최신 누적 기준에서 forward-check0/reverse-check1로 아직 미포함이었습니다. shared 결과tree와 UUID 결과tree는 기존 독립 검토와 정확히 같습니다. initial changes.patch·UUIDv2·깨진 historical initial은 사용하지 않았습니다. 기계 충돌0건이며 semantic repair와 역사편집정책 조정은 별도입니다.

## 후보별 처분

|후보|기존 최종 검토|새 후보 처분|
|---|---|---|
|shared-followup|F1/P1 불필요 유료 dispatch, F2/P2 caller 실패 후 loser 재시도 재현|설정·비스트리밍 변경만 유지하고 경쟁조건을 최소 수정. 원본7probe 그대로 RED2→GREEN0. F2 지연된 worker 첫 dispatch도 추가 RED→GREEN으로 차단|
|UUIDv3|고정 tick·8병렬 충돌 회귀 PASS|2경로 그대로 적용; fake CLI 4/4 재실행|
|historical v2|1032 저장행 대조·generator PASS, 역사서술 정책 별도|generator·generated report는 적용, 기존10-07 서술·표를 바꾸는 hunks는 미적용하고 두 원문 끝에 새 날짜 보충만 추가. [정정 근거](2026-10-25_remaining-historical-correction.md)|

F1은 admission 전후 queued local을 확인하고 API 미사용 breaker permit을 반환합니다. F2는 모든 caller 종료의 finally settlement와 새 provider attempt 직전 cancellation 확인입니다. 기존 stream/image/warm·기본0·caller context/budget·늦은 health 반영 계약을 유지합니다. 새 기능은 만들지 않았습니다.

## 실제 실행과 분모

|최종 집합|결과|해석|
|---|---|---|
|관련 회귀(영구 독립probe7 + 지연worker1 포함)|327/331 = 98.79%|수집오류0·건너뜀0, 소켓 bind 차단4, rc1 유지|
|architecture·contract·security|607/607 = 100.0%|문서 포함 최종 index를 대상으로 마지막에 재실행, scanner coverage 별도|
|UUID|4/4 = 100.0%|실모델 호출 없음|
|저장자료·generator·안전가드|3/3 = 100.0%|저장행 good 재집계·LF동등, 독립 재채점 아님|
|중복 제외 위4집합 합집합|941/945 = 99.58%|차단4/945 = 0.42%, 신규 회귀 실패0|
|별도 원본 독립probe 재실행|7/7 = 100.0%|영구7시험과 의미 중복이므로945에 더하지 않음|

실제 현재 baseline도 새 baseline_current에 완전재구성하여18996 blob 전부 검사했습니다. **정확한 같은4 nodeid를 현재 실행해4/4 차단 재현**, 같은 시험함수 AST동일 확인, 공통 기존회귀313개도 현재 실행309pass/4차단입니다. 과거319/323만으로 동등하다고 가정하지 않았습니다. `current-baseline-comparison.json`에 정확한 id·원인·실행명령과 공통결과 비교를 남깁니다.

4개 nodeid:
- `tests/unit/infrastructure/test_llm_failover.py::test_http_a_closed_port_goes_to_the_api_quickly`
- `tests/unit/infrastructure/test_llm_failover.py::test_http_a_slow_server_times_out_and_goes_to_the_api`
- `tests/unit/infrastructure/test_llm_failover.py::test_http_a_503_server_is_retried_once_then_goes_to_the_api`
- `tests/unit/infrastructure/test_llm_failover.py::test_http_a_healthy_server_answers_locally_and_the_api_is_not_touched`

네 건 모두 후보/현재baseline에서 `RuntimeError: remaining DoD safety guard: service/socket bind denied`이고 실제 HTTP 전송 전 bind에서 막혔습니다. 테스트 기대 assertion이 실행됐다는 뜻이 아닙니다. 서비스 기동 금지 제약으로 **미검증 유지**하며 DB 문제라고 분류하지 않습니다. 신규회귀는 없지만 전체 회귀 PASS라고 바꾸지 않습니다.

## 한계·남은 것

1. 위 소켓시험4개는 허가 범위 밖이라 미검증입니다. 가드를 풀거나 서비스/DB를 띄우지 않았습니다.
2. 수정된 shared의 새 독립 리뷰 0/1 = 0.0%는 부모/별도 reviewer 확인이 필요합니다. 원래 독립 검토는 원본 결함을 확인한 것이지 수정판 승인서가 아닙니다.
3. boolean budget interface에는 refund가 없어 admission 도중 local 완료면 API dispatch0이어도 예약1이 남을 수 있습니다. 회수·과금 API를 신규 설계하지 않았으며 hard monetary/attempt cap·이미 실행한 SDK 물리취소·엄격 SLA를 보장하지 않습니다. max_inflight는 soft busy 임계치입니다.
4. 역사자료의1031행 동일은 저장행 바이트 대조이며 정답성 확인이 아닙니다. 당시 재호출 chronology는 이번 검증하지 않았습니다.
5. DB설치·접속복구·마이그레이션·서비스/모델/외부API·push·배포0. admin3300/ops8070에는 제어 명령을 보내지 않았습니다. 예약OFF 코드 후보·기존 가동을 변경하지 않았고 DB 실저장 확인 보류도 그대로입니다.

## 보존·전달

산출물은 새 scratch/remaining_non_db_integration에만 있습니다. `remaining-non-db.patch`는635cb 기준 누적 대안이며 기존3패치와 다시 연속 적용하지 않습니다. `shared-review-fix.patch`는 shared-followup 이후 shared영역 수정만이며 누적patch와 대안입니다. 정·역 독립 index tree/전체 blob/SHA256·기존 후보3패치 해시는 FINAL.json/manifest.json으로 확인합니다. 양wiki·인계·보고는 이 새 후보에서만 갱신했고 원본으로 역복사하지 않았습니다. 테스트 실행의 실제 rc1도 보존했습니다.


## Ruff 재검증·최종4차 동결

최초 finalize는 실제 Ruff F401 세 건(glob·statistics·fmt_ratio 미사용)으로 rc1이었습니다. 현재 baseline635cb에서도 같은3건을 실행재현했습니다. 신규 도입0건이지만 검사비활성화 없이 새 후보의 해당 미사용 import만 제거했습니다. 원래 실패ruff.log/json·현재baseline JSON을 보존하고 전체 변경Python F,E9를 다시 실행합니다. 저장입력은 그대로이고 generator의 import정리만 새 SHA256에 반영하여 실제 보고 재생성을 재검증했습니다. 최종 근거는 *repeatfinal4 로그/JUnit, final4-inputs.json, ruff-final.json입니다. 공통 소켓차단4건의 rc1은 정상 통과로 바꾸지 않습니다.


최초 seal의 whitespace 실패는 세 index에 새로 추가한 CRLF6줄이었습니다. 원래 baseline bytes를 정확한 prefix로 유지하고 추가행만 LF로 바꿨습니다. 실패log·바이트해시를 보존하고 최종 문서 게이트를 다시 실행했습니다. 최종 코드·시험·generator 입력은 final4와 같으며 final5-inputs.json으로 대조합니다.
