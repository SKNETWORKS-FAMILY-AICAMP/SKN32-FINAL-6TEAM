---
type: report
title: reader 스트림 정책 생략 우회 1건 TDD 폐쇄
status: draft
domain: travel
---

# reader 스트림 정책 생략 우회 — 독립 재현 1건만 수정

2026-10-25 KST / 최종 실행 2026-10-24T15:13:07Z. **원래 하위 reader 우회 반례를 실패 RED로 재현한 뒤 `agent_read.py` 4줄 추가로 차단했습니다. 요청 경계 고유 350/350 통과, 공급자 확장 포함 405/409 통과·HTTP bind 정책 차단 4실패입니다. 제품 전체 완료·실환경 검증·배포 승인이 아닙니다.**

## 결함과 최소 수정

- 원보고서: [6개 안전 보완 당시 기록](2026-10-24_reader-provider-safety.md). 당시 25/25 GREEN은 이번 반례의 폐쇄 증거가 아니었습니다.
- 정확한 반례는 `pipeline.read_source('김여행', agent=FailoverChat(...), agent_mode='on', today=...)`에 `reading_stream`을 생략하는 것입니다. 순수 local 대역은 `OllamaError`, paid 대역은 `{'items': []}`, global reserve는 True, strict reader reserve는 False입니다. RED는 **local 1회 → paid 1회, global reserve 1회, strict reserve 0회, paid user 원문 `김여행`**을 관찰했습니다. HTTP/모델/DB를 실제로 부르지 않았습니다.
- 기존 `agent_read.read`는 stream=None이면 일반 `chat.structured()`를 선택했습니다. 일반 업무 failover는 reader 전용 외부 기본 거부/엄격 예산 경계가 아니므로 안전 정책이 적용되지 않았습니다. 정상 `process`는 검증된 stream 정책을 주입하므로 즉시 정상 API 누수를 재현한 것은 아니고, 허용된 하위 reader 경계 결함입니다.
- [안전 계약](../../external/plan-reading-restoration.md)의 「스트림 정책 생략 우회 폐쇄 계약」을 코드보다 먼저 추가했습니다. reader 전용 `reader_json` 인터페이스를 가진 wrapper에서 stream=None은 호출 전 RuntimeError로 거부합니다. pipeline은 기존 계약대로 `IntakeRejected.code=reading_model_failed`로 올리며 줄 reader로 조용히 전환하지 않습니다. local/paid/global/strict/legacy 호출 모두 0회입니다.
- 일반 업무 `FailoverChat.structured()` 정책·구현은 바꾸지 않았습니다. 명시적 off의 안전한 줄 읽기, 비wrapper legacy structured 호환, on/shadow 명시 실패를 각각 고정했습니다. reader 외부 기본값 false 및 strict reserve 의무는 그대로입니다. 고급 확장·새 공급자·새 정책값은 추가하지 않았습니다.

## TDD 및 정확한 분모

증거 기본 경로 `B`:

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/reader-stream-omission-20261024T151000`

| 관측 | 실제 결과 | 증거(B 기준) |
|---|---:|---|
| 원 반례, 제품 변경 전 RED | 0/1, failure 1, exit 1 | `red/20261024T151105_625453Z/pytest.log`, `result.xml`, `node-results.json` |
| 동일 반례, 최소 수정 직후 GREEN | 1/1, failure 0, exit 0 | `green/20261024T151131_076218Z/` |
| 최종 단일 실행: 이전 정상 입구/관련 318 nodeid | 318/318 = 100% | `verification.json`의 `prior_318`, missing=[] |
| 같은 실행: 이전 안전 25 nodeid | 25/25 = 100% | `prior_safety_25`, missing=[] |
| 같은 실행: 새 회귀/보호 계약 7 nodeid | 7/7 = 100% | `new_policy_regression`, missing=[] |
| 위 요청 경계 고유 nodeid 합집합 | 350/350 = 100% | set으로 중복 제거, 과거 실행 통과 수 합산 아님 |
| 같은 실행: 공급자 회귀 | 55/59, failed 4 | `provider_59` |
| 전체 25파일 고유 nodeid | **405/409 = 99.022%, failed 4, exit 1** | `full-final/20261024T151307_393179Z/` |
| 최종 JUnit | tests=409, failures=4, errors=0, skipped=0 | 위 `result.xml`, testcase 수 프로그램 검산 |

최종 collection 오류/deselect/skip 0입니다. 기존 402 nodeid와 318 nodeid 전부 존재를 set으로 대조했습니다. 신규 7개에는 정확 반례, on/shadow fallback 금지 2개, 직접 reader 거부, 명시 off 호환, 비wrapper legacy 호환, 일반 업무 structured 정책 유지가 포함됩니다.

최초 확장 실행 `full/20261024T151224_881083Z/`은 404 passed/5 failed였습니다. 추가 off 보호시험의 순수 대역 응답을 `lines`로 잘못 작성하여 실제 계약 `spans must be a list`에 걸린 1건입니다. fixture만 `{'spans': []}`로 바로잡고 최종 전체를 다시 실행했습니다. 이 오류는 제품 RED로 세지 않으며, 원 반례 시험 본문과 생산 코드는 이때 바꾸지 않았습니다. 최초 로그도 덮어쓰지 않았습니다.

### HTTP 차단 4건 — 별도 미검증 분모 유지

아래는 실제 서비스 시작이 허용되지 않아 runner가 bind에서 차단한 실패 4/4입니다. 허용/skip/deselect로 통과시키지 않았으며 전체 409 분모에도 남겼습니다.

- `tests/unit/infrastructure/test_llm_failover.py::test_http_a_closed_port_goes_to_the_api_quickly`
- `tests/unit/infrastructure/test_llm_failover.py::test_http_a_slow_server_times_out_and_goes_to_the_api`
- `tests/unit/infrastructure/test_llm_failover.py::test_http_a_503_server_is_retried_once_then_goes_to_the_api`
- `tests/unit/infrastructure/test_llm_failover.py::test_http_a_healthy_server_answers_locally_and_the_api_is_not_touched`

## 실행 명령

기존 `reader-safety/final_verify.py`와 `writing-integration-prep/run_integrated.py`를 먼저 읽었습니다. 전자는 기존 manifest/log를 덮어쓰므로 직접 실행하지 않고 동일 목록 생성 규칙을 고유 manifest로 재사용했습니다. 후자는 변경 없이 아래 명령으로 재사용했습니다.

```bash
PY=C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/travel-writing-s1-venv/Scripts/python.exe
RUNNER=C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/writing-integration-prep/run_integrated.py
B=C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/reader-stream-omission-20261024T151000
"$PY" "$RUNNER" --manifest "$B/red-manifest.json" --output "$B/red"
# 위 RED를 확인한 뒤에만 생산 코드 4줄 추가
"$PY" "$RUNNER" --manifest "$B/red-manifest.json" --output "$B/green"
# 보호 계약 7개까지 추가, fixture shape 보완 후 최종 단일 실행
"$PY" "$RUNNER" --manifest "$B/full-manifest.json" --output "$B/full-final"
"$PY" "$B/aggregate.py"
git -C C:/_proj/final_workspace diff --check -- final_project_cs/app/domains/travel_ops/components/intake/agent_read.py final_project_cs/tests/unit/travel/test_reader_stream_policy_required.py final_project_cs/wiki/external/plan-reading-restoration.md
```

runner는 Python 3.12.15/pytest 8.4.2이며 합성 unit 설정만 사용합니다. network connect/connect_ex/create_connection/bind/listen/sendto와 psycopg 연결을 차단하고 stdlib socketpair의 정확 code-object 예외만 유지합니다. 사전 차단 검사를 통과했고 최종 시험 중 차단은 bind 4회뿐입니다. 최종 1,297개 app/tests/config snapshot hash 전후 동일, changed_paths=[]입니다. runner의 `final_stable_evidence=false`는 그대로이며 부모 전체 통합 완료로 승격하지 않습니다.

## 변경 파일·백업·한계

변경은 아래 4파일뿐입니다(다른 작업의 dirty 변경을 자기 변경으로 집계하지 않습니다).

1. `app/domains/travel_ops/components/intake/agent_read.py` — stream 누락 시 정책 wrapper 거부 4줄 추가.
2. `tests/unit/travel/test_reader_stream_policy_required.py` — 새 순수 대역 회귀 7 nodeid.
3. `wiki/external/plan-reading-restoration.md` — 코드 전 보호 계약 명시.
4. `wiki/records/reports/2026-10-25_reader-stream-policy-omission-tdd.md` — 이 고유 보고서.

수정 전 생산 코드/안전 계약 바이트 백업은 `B/agent_read.py`, `B/plan-reading-restoration.md`, 해시는 `B/backup-hashes.json`입니다. 자기 생산 변경만의 diff는 `B/owned-production.diff`, 최종 생산 SHA256은 `de912431a627a629406e58012524b05ecfd1e9bf259a680258ac335c903ca10b`입니다. 두 대상은 작업 시작 당시 untracked이므로 Git diff만으로 변경을 주장하지 않고 백업 대비 diff로 검증했습니다. 초기 Python subprocess Git 조회는 WinError 5로 거절되어 직접 terminal Git으로 조회했고 백업은 이미 생성되어 보존했습니다. 루트 RULE.md는 존재하지 않아 cs/RULE.md를 적용했습니다.

`trip_api.py`, response/plan, frontend, llm_failover, 배포/DB 설정, root wiki/handoff는 수정하지 않았습니다. root 현황/인계 연결은 부모 소유입니다. commit/push하지 않았습니다. 실제 모델·유료 API·DB·HTTP 앱서비스를 사용하지 않았으며 실DB strict 예산 저장, migration, 모델 품질, 운영 전달/배포는 검증하지 않았습니다. 이미 blocking인 transport의 강제 취소 불가, 동기 DB driver timeout 한계는 여전히 남습니다. 이번 결함의 로컬 폐쇄에 추가 사용자 결정은 필요 없고, 운영 변경은 별도 승인 대상입니다.
