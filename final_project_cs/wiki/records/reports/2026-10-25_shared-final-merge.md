---
type: report
title: 공유소유 9구간 의미병합·격리 회귀
status: draft
domain: travel
---

# 공유소유 9구간 — 격리 후보 완료, 원본 적용 HOLD

[실측] R1–R7 reader/F3와 D1–D2 관리자 Diagnostics 연결 **9/9 = 100%**를 새 `scratch/shared_final_merge/repo`에서 결합했습니다. 전체 제품이나 원본 반영 완료율이 아닙니다. 원본 제품/규칙/실행중 서비스/DB/모델/예약 OFF 값은 변경하지 않았습니다. 원본 문서는 아래 CAS 백업 절에 한정합니다.

## 고정 입력과 소유권
- 팀 기준 pin `6c34589b4e34dede82e566d43b3757e127a5d5d9`, baseline tree `fb69acb1a74603bdd79cddae7176f94630a027c6`, 기존 reviewed tree `f7b680f791fe3a2e28e1151ba92513a2363b48c6`를 선행 입력으로 사용했습니다. 이번에 fetch·설치·서비스 실행을 반복하지 않았습니다.
- 라이팅 후보 pin `325ba25d88c91ce97da61f2bda635e5888fe3b40`의 현재 정확 바이트를 읽어 의존 closure를 대조했습니다. `cas-manifest.json`, `dependency-comparison.json`, `owner-current-documents.json` 참조. V10 완료는 그 보고서 범위이며 shared hunk 소유권 해제/원본 적용 승인 문서는 없습니다. **원본 llm_failover/connected 및 라이팅 소유 의존 경로는 전부 HOLD**입니다.
- 관리자 기존 실저장 완료 `false/override revision1, audit1`은 기존 완료 문서로만 확인했습니다. 이번에 로그인/PATCH/DB 접속·5433 구성 변경·서비스 재기동을 하지 않았습니다.

## 실제 결합
- reader 전용 strict 예산과 SDK 매시도 authorizer/absolute deadline/외부 기본거부/API-only/provenance를 재사용하고 F3 pending/consumed/slot/publication/dispatch-claim/settled를 결합했습니다. reader_json을 포함한 모든 reader는 hedge와 busy overflow 대상에서 제외됩니다. 일반 nonstream structured 정책은 writer AST와 같습니다.
- 원본에 이미 있던 정책 생략 fail-closed, 안전한 legacy reader_json, 정상 process의 명시 stream 주입, schema-readiness 및 reading.agent 재조회 투영을 보존했습니다. 최신 CHECK의 `trip`을 제거하지 않았습니다.
- 원본/라이팅 차이에서 드러난 SDK terminal EOF/refusal/length 및 reader 지정 stream 출력 상한을 원본 계약대로 복원했습니다. 비스트림 일반 structured 상한은 변경하지 않았습니다.
- DiagnosticsPanel은 기존 본체·gateway/API·정책/권한·해결판 audit를 그대로 쓰고 import/JSX만 연결했습니다. BookingModeFields와 service 필터·revision/사유/재조회 흐름을 유지했습니다. 중복 subsystem 구현은 없습니다.
- 이미 존재한 native tokenizer, llm_spans, response plan/writing, diagnostics replay worker 등 필요한 누락 의존만 재사용했습니다. 기존 SQL 파일만 보존했으며 migration 실행은 없습니다.

## 단일 동결 회귀와 분모
- backend/reader/동시성/정상 intake·재조회/고객시간/진단 권한: **216/220 = 98.1818%**, product assertion 실패0·error0·skip0, **bind 정책 차단4 유지, pytest exit1**. `runs/final-05/result.xml`, `result.json`, `nodeids.json`, before/after manifest가 실제 같은 실행입니다. 과거1121 수치와 합산하거나 대체하지 않습니다.
- 기존 모순 scheduler 원문3건은 바꾸지 않고 별도 재실행하여 **0/3, failure3, exit1**를 보존했습니다(`runs/raw-final`). paid_called Event는 paid 함수 안에서만 설정되므로 wait 성공과 paid==[]의 동시 요구가 모순입니다. 기존 독립 유효 schedule `test_llm_f3_acceptance.py` 3건과 claim/publication 양순서는 위220에 포함되어 통과했습니다. 원문3건을 GREEN/skip/xfail로 바꾸지 않았습니다.
- 전체 실제 backend 증거 node 합집합은 **216/223 = 96.8610%**, 총 실패7(정책4/모순probe3)입니다. 이는 별도 두 실행 합집합이며 단일223 실행이라고 주장하지 않습니다.
- 관리자 **43/43 = 100%**, JSON/JUnit 각각43. lint/typegen/tsc/unit/전체 webpack build/후속 tsc **6/6 exit0**. 관련 실제 SSR 연결 반례는 premerge RED2 → current GREEN2입니다. src/config/lock 입력 전후 동결 일치. 실제 browser/service/설정저장 수락의 재실행은 아닙니다.
- 최초 collection 누락, 누락 의존, 구 fixture SQL/stream/공개 projection 차이의 실패를 고유 run별로 보존했습니다. fixture는 canonical CHECK/fetchone, reopen 열·source position·catalog 빈 결과와 새 DiagnosticsPanel mock만 명시 보완했고 핵심 assertion은 유지했습니다.

## 복원 가능한 적용 순서
1. 새 격리 index/후보에 정확 pin `6c34589b4e34dede82e566d43b3757e127a5d5d9`를 준비합니다. 원본에는 직접 적용하지 않습니다.
2. `01-reviewed-forward.patch` → `02-shared-forward.patch` 순서로만 적용합니다. 또는 대안인 `combined-forward.patch` 하나만 사용합니다. 둘을 혼용하지 않습니다.
3. 각 단계 manifest/tree와 apply-check를 대조하고 이 보고서의 고정 회귀를 재실행합니다. 정역 patch의 object-index 왕복 및 byte manifest는 `patch-roundtrip.json`에 있습니다.
4. 되돌릴 때 `02-shared-reverse.patch` → `01-reviewed-reverse.patch`; combined 경로는 `combined-reverse.patch`만 사용합니다. 이는 새 격리 index에서 검증한 복원이며 원본 reset/stash/clean이나 새파일 자동삭제 권한이 아닙니다.
5. 원본 shared 적용 조건: 라이팅 소유자 완료/해제 확인, 현재 HEAD/index/refs/flags 및 정확 바이트 CAS 재대조, 4way 의존 closure 검토와 해당 hunk 승인. drift면 재병합하고 source 전체를 복사하지 않습니다. 실행중 artifact 교체는 별도 승인입니다.

## 보존·한계
원본 시작 CAS snapshot/실제 index/HEAD/refs/flags는 `shared_final_merge`에 보존했습니다. 최종 shared 바이트 및 metadata drift0입니다. documentation-only 반영은 사전 bytes 백업과 즉시 CAS를 통과한 경로만 `documentation-cas.json`에 기록합니다. 원본 제품 변경0입니다.

동기 예산 DB 지연·이미 진행중인 transport/SDK 강제취소·bool reservation 환불/엄격 금전한도·물리 유료 과금방지 보장은 미제공입니다. 실DB schema/예산저장·실모델·실브라우저·배포/push는 수행하지 않았습니다. 기본/`cr-at-eol` 검사는 둘 다 exit2입니다. 기본 검사의 CRLF 경고에는 이전 reviewed 6파일뿐 아니라 라이팅에서 가져온 CRLF 시험도 포함됩니다. `cr-at-eol` 뒤 남는 EOF 빈줄4파일은 원본/라이팅 donor와 마지막 newline suffix가 정확히 같음을 대조했습니다(`inherited-eof-classification.json`). 새 실제 space/tab 오류0이며, EOF/CRLF를 숨기려고 동결 시험 바이트를 정규화하지 않았습니다.

## 관계
- [원본 최소 통합 기록](2026-10-25_original-minimal-integration.md)
- [기존 V10 수락 범위](2026-10-25_v10-local-service-release.md)
- [관리자 OFF 실저장 완료](2026-10-25_admin-db-handoff-connection.md)
