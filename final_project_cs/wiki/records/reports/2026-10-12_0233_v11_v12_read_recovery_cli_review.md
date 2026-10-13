# 읽기 중단 복구와 두 경계 보완의 실제 검토 기록

중단된 사실 읽기를 같은 업무로 복구하는 후보를 실제 두 모델로 검토했고, 이후 확인한 일정 판 혼합과 보조 조회 롤백 문제를 새 후보에서 보완했습니다. 최종 후보는 격리된 실제 PostgreSQL·HTTP 회귀 474개를 통과했습니다. 이 결과는 운영 고객 DB 확인이나 배포 완료를 뜻하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| v11 실제 두 모델 검토 | 완료 | 2/2 = 100% |
| 두 지적 재현·최소 보완 | 완료 | 2/2 = 100% |
| v12 격리 후보 회귀 | 통과 | 474/474 = 100% |
| v12 실제 두 모델 마감 검토 | 완료 | 2/2 = 100% |

## 후보와 보장 범위

[v11 후보](../../../legacy/deployment_candidates/2026-10-12_015017_plugin_v11/)는 위치에 의존하지 않는 신규 사실 질문의 해석·원래 시각·선택 항목·일정 판을 저장하여 같은 업무로 복구합니다. 위치 좌표는 저장하지 않으며 위치 의존 중단 질문은 복구 대상에서 제외합니다. 업무 변경 계획·답변 이력·실행 중인 팀이 있는 업무는 읽기 복구로 우회하지 않습니다. 이미 저장된 구형 답의 호환도 분류 중인 명백한 사실 읽기로 제한했습니다.

별도 질문 연결 보완은 최신 답변과 다른 옛 질문의 숫자 선택지를 암묵적으로 소비하지 않게 합니다. 명시한 업무·토큰, 같은 재개 사건 재전송, 기존 대화 기록이 없는 경우의 호환은 유지했습니다. 실제 검증은 [읽기 복구 단위시험](../../../legacy/deployment_candidates/2026-10-12_022208_plugin_v12/tests/unit/travel/test_fact_read_recovery.py), [읽기 복구 HTTP시험](../../../legacy/deployment_candidates/2026-10-12_022208_plugin_v12/tests/e2e/test_fact_read_recovery_web.py), [질문 연결 단위시험](../../../legacy/deployment_candidates/2026-10-12_022208_plugin_v12/tests/unit/travel/test_implicit_reply_recency.py), [질문 연결 HTTP시험](../../../legacy/deployment_candidates/2026-10-12_022208_plugin_v12/tests/e2e/test_reply_recency_web.py)에 있습니다.

## 실제 v11 모델 검토와 보존한 실패

| 모델 | 실제 canonicalModel | 직접 합성 단위시험 | 메타데이터·원문 |
|---|---|---|---|
| Opus 5.5 | `claude-opus-5-5` | 91/91 = 100%, 5.81초 | [메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v11-read-recovery-final-2026-10-12_0212-model-metadata.json) · [도구 원문](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v11-read-recovery-final-2026-10-12_0212-review.jsonl) |
| Sonnet 5.5 | `claude-sonnet-5-5` | 91/91 = 100%, 8.69초 | [메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v11-read-recovery-final-2026-10-12_0212-model-metadata.json) · [직접 시험 출력](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v11-read-recovery-final-2026-10-12_0212-test-output.json) |

두 실행은 종료코드0·`is_error=false`·권한 거절0입니다. Opus의 시험은 백그라운드 작업 출력 파일을 Read로 확인했으므로 Bash 결과 요약만으로 통과를 확정하지 않고 위 도구 원문에 있는 `91 passed`·`PYTEST_EXIT=0`까지 확인했습니다. 모델은 실제 DB·HTTP 시험을 직접 수행하지 않았습니다.

v11 최초 격리 회귀는 463개 통과·5개 실패였습니다. 다섯 요청 모두 실제409였으나 시험이 내부 예외 문구를 공개 응답으로 기대한 오류였습니다. 공통 오류 처리기를 바꾸지 않고 고정된 공개 `state_conflict` 문구와 상태 불변·계산 재실행0을 검증하도록 시험만 정정했습니다. [최초 실패 로그](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v11-full-linux-v1.log)와 [정정 후 468/468 로그](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v11-full-linux-v2.log)를 모두 보존했습니다.

v11 모델 검토 중 위 HTTP 기대와 후보 설명 문서 두 파일이 바뀌었습니다. 제품 소스는 바뀌지 않았으나 전체 입력이 완전히 고정됐다고 쓰지 않습니다. [Opus 해시 차이](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v11-read-recovery-final-2026-10-12_0212-sha256-diff.json)와 [Sonnet 해시 차이](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v11-read-recovery-final-2026-10-12_0212-sha256-diff.json)에 실제 두 파일과 시작·끝 해시가 있습니다.

## 두 정적 지적을 재현한 뒤 보완

1. 저장한 일정 판과 입구 판이1이어도 실행 중 재조회가2이면 새 일정으로 답할 수 있었습니다. [수정 전 재현](../evidence/2026-10-11_1936_team_plugin_implementation/v11-read-version-gap-before.log)은 실제 복구·분류·상태 리듀서를 사용했지만 SQL·커밋은 메모리 대역입니다. 실제 DB 경합 시험으로 쓰지 않습니다.
2. 상세 부가정보 조회 부품이 같은 연결을 롤백하면 아직 커밋하지 않은 분류·담당 지정과 잠금이 풀려 완료 전이가 실패했습니다. [수정 전 재현](../evidence/2026-10-11_1936_team_plugin_implementation/v11-read-component-rollback-before-v2.log)은 부품의 rollback seam과 실제 상태 리듀서로 `InvalidTransition`을 확인했습니다. 실제 누락 테이블을 만든 시험은 아닙니다. 첫 재현의 메모리 projection 형식 오류도 [최초 로그](../evidence/2026-10-11_1936_team_plugin_implementation/v11-read-component-rollback-before.log)에 보존했습니다.

새 [v12 후보](../../../legacy/deployment_candidates/2026-10-12_022208_plugin_v12/)의 제품 변경은 [대화 처리 함수](../../../legacy/deployment_candidates/2026-10-12_022208_plugin_v12/app/domains/travel_ops/components/conversation/trip_messages.py:711) 세 구간뿐입니다. 문맥 조회와 답변용 재조회가 저장한 판과 같은지 각각 대조하고, 상세 부가정보만 별도 읽기 연결에서 조회합니다. 같은 연결의 savepoint로 내부 전체 rollback을 막는다고 가정하지 않습니다.

새 단위3개와 HTTP3개를 추가했습니다. HTTP의 두 경합은 다른 실제 DB 연결의 `append_version`으로 판을 변경하고409·원래 업무 상태 불변·팀 실행 기록0을 확인합니다. 나머지 HTTP는 보조 조회 연결을 실제 rollback하는 seam으로200·완료 상태·네 전이 각1회·팀 실행 기록0을 검증합니다. 스키마를 삭제하지 않았습니다.

## v12 직접 검증과 두 모델 마감 검토

| 확인 | 결과 | 근거 |
|---|---|---|
| Codex 고정 합성 단위 | 94/94 = 100%, 9.77초 | [직접 실행 로그](../evidence/2026-10-11_1936_team_plugin_implementation/v12-read-boundary-unit-v1.log) |
| 격리 Linux 전체 후보 | 474/474 = 100%, 55.84초 | [실제 PostgreSQL·HTTP 포함 로그](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v12-full-linux-v1.log) |
| 실제 Opus 5.5 직접 단위 | 94/94 = 100%, 2.94초 | [메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v12-read-boundary-closing-2026-10-12_0227-model-metadata.json) · [시험 출력](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v12-read-boundary-closing-2026-10-12_0227-test-output.json) |
| 실제 Sonnet 5.5 직접 단위 | 94/94 = 100%, 3.73초 | [메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v12-read-boundary-closing-2026-10-12_0227-model-metadata.json) · [시험 출력](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v12-read-boundary-closing-2026-10-12_0227-test-output.json) |

94개는 읽기 복구30·질문 연결14·기존 단위50이며 실제 DB 없이 합성 설정으로 실행했습니다. 474개는 후보 담당이 격리 Linux·실제 PostgreSQL·HTTP까지 포함해 실행한 별도 집합입니다. 반복 실행 수를 고유 시험 수처럼 더하지 않습니다. 격리 실행은 운영 DB·볼륨·환경을 전달하지 않았고 내부 네트워크와 임시 DB만 사용했습니다.

두 마감 모델의 canonical은 각각 `claude-opus-5-5`·`claude-sonnet-5-5`, 종료코드0·`is_error=false`·권한 거절0입니다. 지정 고정 실행 명령만 Bash 각1회 수행했고, [정확 명령 훅](../evidence/2026-10-11_1936_team_plugin_implementation/v12-read-boundary-exact-command-hook.py)의 [허용·거절 사전검증](../evidence/2026-10-11_1936_team_plugin_implementation/v12-exact-hook-preflight.json)은3/3입니다. 각944개 입력 시작·끝 해시 변경0을 확인했습니다. [Opus 해시 차이](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v12-read-boundary-closing-2026-10-12_0227-sha256-diff.json) · [Sonnet 해시 차이](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v12-read-boundary-closing-2026-10-12_0227-sha256-diff.json).

두 모델은 이번 두 경계 변경에서 새 확정 결함을 찾지 못했습니다. [Opus 결론](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v12-read-boundary-closing-2026-10-12_0227-result.txt) · [Sonnet 결론](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v12-read-boundary-closing-2026-10-12_0227-result.txt). Opus는 완료된474개 로그를 읽었지만 DB·HTTP를 직접 실행하지 않았습니다. Sonnet은 그 로그를 확인하지 않았습니다. 직접 읽은 파일과 범위는 각 메타데이터에 기록돼 있습니다.

## 한계와 보존

특정 시점의 같은 일정 판으로 답한 뒤 새 판이 생기는 일반적인 읽기 시차까지 전역 잠금으로 막는 변경은 하지 않았습니다. 일정 판이 이미 달라진 중단 읽기는409로 거절하며 기존 입력은 보존합니다. 공개 오류는 기존 고정 문구이므로 내부의 「새 요청 번호」 안내가 그대로 HTTP에 나온다고 주장하지 않습니다. 좌표 보관·업무 실행 관문·업무 적용 재실행 정책은 바꾸지 않았습니다.

474개 결과는 릴리스의 모든 별도 관문이 통과했다는 뜻이 아닙니다. [별도 필수 관문 최초 로그](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v12-required-linux-v1.log)는447개 통과·3개 실패·3개 제외를 보존하고 있습니다. 해당 관문 분류·후속 결과와 이미지·운영 교체 확인은 후보·배포 담당의 기록을 따릅니다. 이 하위 작업은 운영 교체를 수행하지 않았습니다.

v11 제품·이미지·감사 원형을 보존하고 v12에서만 수정했습니다. [수정 직전 백업](../../../legacy/deployment_candidates/2026-10-12_022208_plugin_v12/_backup/2026-10-12_0223_read_boundaries/), [최종 핵심 소스 해시](../evidence/2026-10-11_1936_team_plugin_implementation/v12-core-final-source-sha256.json), [제품52개 해시 대조](../evidence/2026-10-11_1936_team_plugin_implementation/v12-core-final-runtime52-sha256.json)에 보존 상태가 있습니다. 마지막 manifest SHA256은 `ca7e302485dd9db116ec57dfe13713dd82da9c51e3d2648b691d20e42130853b`입니다. 이 보고서는 새 파일이며 과거 기록을 덮어쓰지 않았습니다.
