---
type: report
title: 공유 9구간 원본 안전 반영 완료
status: draft
domain: travel
---

# 공유 9구간 — 원본 완료 9/9 = 100%

[실측] 대상은 `C:/_proj/final_workspace`입니다. R1–R7 reader/F3 7구간을 현재 원본 의미병합으로 반영했고, D1–D2 Diagnostics import/render 2구간은 원본에 이미 있어 덮어쓰지 않고 실제 렌더 회귀로 확인했습니다. 신규 통합7 + 기존 보존2 = **9/9 = 100%**입니다. 격리 후보만 완성한 이전 HOLD는 이 범위에서 해소됐습니다. 제품 전체·현재 실행중 서비스 교체 완료라는 뜻은 아닙니다.

## 실제 변경 파일
- `final_project_cs/app/core/settings.py`
- `final_project_cs/app/infrastructure/llm_failover.py`
- `final_project_cs/app/infrastructure/model_stream.py`
- `final_project_cs/app/infrastructure/native_context_tokenizer.py`
- `final_project_cs/app/infrastructure/ollama_chat.py`

새 파일은 `native_context_tokenizer.py` 하나이며 다른 4개는 현재 바이트 백업 후 쓰기전용 공유잠금/CAS를 통과했습니다. 원본 시험·규칙·connected/source-policy/gateway·pipeline·DB migration 파일은 수정하지 않았습니다.

## 4way·현재소스 최소 의미병합

- 라이팅 V10 완료 인계 `2026-10-25_v10-local-service-release.md`와 이후 root/sub wiki/handoff를 읽었습니다. V10의 완료 범위를 전체 라이팅 품질 완료로 확대하지 않았습니다. 공유 경로와 지명 의존은 이전 원본/라이팅 snapshot 이후 바이트가 같았고, 원본 쓰기 시 Windows CreateFile 공유모드가 동시 쓰기를 배제했습니다. 관측된 동시변경·소유 충돌 경로0입니다. 명시 해제 문장이 없다는 이유만으로 전부 멈추지 않았습니다.
- 팀 pin `6c34589b4e34dede82e566d43b3757e127a5d5d9`, 라이팅 pin `325ba25d88c91ce97da61f2bda635e5888fe3b40`, accepted tree `b9bb174021ced6ef3db23e72de0a2d5ce1483e8d`, 현재 원본, 최종 proposal을 파일별 hash/원문으로 대조했습니다. 직접 combined patch를 원본에 적용하지 않았습니다.
- 최초 좁은 splice는 원본에 반영하지 않고 `first-splice-not-for-application`에 보존했습니다. 필요한 기존 writer/provider/tokenizer 구현은 accepted donor에서 재사용했습니다. 실제 현재소스 회귀로 드러난 일반 OpenAI structured 스키마·출력예산 계약, direct OpenAI reader fail-closed 표시, local stream 키워드 호환은 원본에서 보존했습니다. reader stream strict SDK 매시도 예산/absolute deadline과 F3 publication/claim routine은 유지했습니다. 새 대체 모듈 구현은 없습니다.
- `threeway/*/merged`는 백업 current/base와 최종 proposal의 exact 3way 결과이며 모든 파일이 최종 반영 바이트와 같습니다. `restore-manifest.json`, `fourway.json`, `dependencies.json`, `compatibility-disposition.json`, `exact-original-forward.patch` 참조. accepted tree 자체와 원본 현재소스 병합 결과의 hash를 같은 것으로 주장하지 않습니다.

## 실제 원본 회귀

- `runs/original-final-CRLF-frozen`: **208/212 = 98.1132%**, product assertion 실패0·error0·skip0, bind 정책 차단4·pytest exit1을 유지했습니다. JUnit212/고유 nodeid212/실제 원본 app 모듈193개 경로·hash와 source/config/tests 전후 동결을 검산했습니다. reader strict budget/deadline/default-deny/API-only/provenance·SDK retry·정상 intake/재조회·F3 양순서/slot/settlement·Diagnostics 권한/CLI 원문 시험을 포함합니다.
- 기존 패키지 테스트와 외부 검증 시험을 혼합할 때 나온 최초 collection mismatch는 실패 로그를 보존하고 `--import-mode=importlib`로 runner만 보정했습니다. 원본 pyc·시험·생산 코드를 삭제/수정하지 않았습니다.
- 관리자 **2/2 = 100%**: 원본 admin src 전체의 동일 hash 사본에 accepted Diagnostics SSR 시험을 실행했습니다. 실 DiagnosticsPanel + OFF 표시·실패/재조회 독립 컨트롤을 확인했습니다. 최초 `.test.ts` 한정 harness collection0도 보존하고 별도 `.tsx` 포함 설정으로 실행했습니다. 원본 admin 소스는 전후 같고 네트워크/bind는 차단했습니다. 과거 후보43/43·build6gate를 이번 원본 실행으로 재사용하지 않습니다.
- 기존 원문 scheduler 모순probe3의 별도 실패는 `shared_final_merge/runs/raw-final`에 그대로 보존합니다. 이번212에 합산하거나 GREEN으로 바꾸지 않았습니다. provider-entry Event 성공과 paid==[]를 함께 요구하는 해당 원문은 제품 assertion 실패와 구분합니다.

## 보존·복원·경계

- 원본 app/config/tests/scripts/admin src 및 launcher/규칙 **1639개** 사전 hash 중 기존 변경은 승인된 기존4파일 외 전부 동일합니다. 새 native tokenizer1개만 추가했습니다. 모든 metadata backup과 실제 index/HEAD/refs/flags byte/readback이 일치합니다. 스테이징·reset·stash·sparse/flag 변경·기존 패치 삭제0입니다.
- `backup/bytes`, `backup/metadata`, `restore-manifest.json`이 복원 정본입니다. 기존파일 복원은 현재가 기록된 postimage일 때만 해당 preimage를 CAS 복원합니다. 새 파일은 자동 삭제하지 않으며 별도 삭제 승인이 필요합니다. 백업의 모든 hash를 검산했습니다.
- 최종 whitespace 검사 원문은 `whitespace-final-v2/*/default.log`, 새 space/tab0·원본 EOF/줄끝 보존은 `whitespace-final-v2.json`과 `newline-preservation.json`입니다. failover 원본의 CRLF 및 EOF suffix를 복구한 마지막 바이트로 212건을 다시 동결 실행했습니다. 초기 LF 적용 기록은 보존했으며 최종 manifest는 CRLF postimage입니다. 별도 scratch에서 exact 원본 patch 정역검사/실적용4단계와 모든 파일 pre/post hash 왕복을 확인했습니다(`final-patch-roundtrip.json`).
- 서비스 시작/재시작/빌드 artifact 교체·DB 연결/설치/마이그레이션/설정 PATCH·실모델/외부 API·push/배포0입니다. 이전 관리자 OFF `false/override revision1/audit1` 저장 완료값은 건드리지 않았고 재저장하지 않았습니다. 현재 serving artifact가 새 원본 코드를 로드했다는 주장은 하지 않습니다.
- bool reservation 환불·엄격 금전한도·이미 시작된 SDK/transport 물리취소/과금방지 보장은 여전히 미제공입니다. bind4는 차단 상태로 남습니다. 추가 소유 인계/사용자 결정 필요0입니다.

## 증거 위치

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/shared_original_apply/`

- `verification.json` · `nine-hunk-disposition.json` · `apply-verification.json`
- `runs/original-final-CRLF-frozen/result.json` · `result.xml` · `nodeids.json` · `loaded-modules.json`
- `admin-final.json` · `admin-final.xml` · `admin-input.json`
- [이전 후보 보고](2026-10-25_shared-final-merge.md) — 당시 HOLD 기록이며 이 보고서가 원본 적용 현재 결론입니다.
