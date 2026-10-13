# v10 운영 변경 결합의 실제 CLI 검토 기록

최신 운영 채팅 문맥 기능과 Team 실행 변경을 결합한 v10을 실제 두 모델로 검토했습니다. 결합 자체의 새 결함으로 확정한 항목과, 기존 중단 복구·질문 연결의 부족을 구분합니다. 이 기록은 v10에 한정하며 후속 v11의 시험 결과로 재사용하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 실제 두 모델 검토 | 완료 | 2/2 = 100% |
| 보충 합성 단위시험 | 각 모델 통과 | 각 50/50 = 100% |
| 두 관찰의 좁은 함수 재현 | 완료 | 2/2 = 100% |

## 범위와 실행 환경

대상은 [v10 후보](../../../legacy/deployment_candidates/2026-10-12_012943_plugin_v10/)와 그 안의 세 방향 차이입니다. 운영 기준 406개에 변경 51개를 결합했고 나머지 361개 해시가 같다는 후보 담당의 근거를 전제로, 직접 충돌한 여행 대화 처리와 대기·재개 경계를 검토했습니다. 운영 고객 DB와 외부 지도·모델 서비스는 시험 대상으로 연결하지 않았습니다.

모델은 읽기 검토와 명시적 합성 설정을 사용하는 고정 단위시험만 수행했습니다. 모델이 DB·HTTP 회귀를 실행한 것으로 쓰지 않습니다. 후보 담당의 별도 Linux 414/414 결과는 모델이 직접 실행한 50개와 분모가 다릅니다.

## 실제 모델과 직접 시험

| 모델 | 확인한 canonicalModel | 보충 직접 시험 | 원문 근거 |
|---|---|---|---|
| Opus 5.5 | `claude-opus-5-5` | 50/50 = 100% | [opus-v10-threeway-2026-10-12_0143-model-metadata.json](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v10-threeway-2026-10-12_0143-model-metadata.json) · [opus-v10-threeway-2026-10-12_0143-test-output.json](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v10-threeway-2026-10-12_0143-test-output.json) |
| Sonnet 5.5 | `claude-sonnet-5-5` | 50/50 = 100% | [sonnet-v10-threeway-2026-10-12_0143-model-metadata.json](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v10-threeway-2026-10-12_0143-model-metadata.json) · [sonnet-v10-threeway-2026-10-12_0143-test-output.json](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v10-threeway-2026-10-12_0143-test-output.json) |

두 보충 실행 모두 CLI 종료코드0·`is_error=false`를 확인했습니다. 보충 Opus의 직접 출력은 50개 통과(4.63초), Sonnet은 50개 통과(5.17초)입니다. 두 결과를 파일로 확인하기 전 한때 Opus 확인 중 상태였으며, 확인 뒤에만 각 50/50로 확정했습니다.

첫 고정 실행은 두 모델 모두 40개 통과·10개 설정 준비 오류였습니다. 후보에 환경파일을 넣지 않은 상태에서 Settings의 필수 합성 값이 없던 오류이며, 제품 시험 실패나 50개 통과로 세지 않았습니다. 원문을 남기고 고정 실행기에 합성 설정만 추가하여 각 50개를 다시 실행했습니다.

- 최초 원문: [opus-v10-threeway-2026-10-12_0134-test-output.json](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v10-threeway-2026-10-12_0134-test-output.json) · [sonnet-v10-threeway-2026-10-12_0134-test-output.json](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v10-threeway-2026-10-12_0134-test-output.json).
- 실행기: [v10-threeway-2026-10-12_0140-unit-v2.py](../evidence/2026-10-11_1936_team_plugin_implementation/v10-threeway-2026-10-12_0140-unit-v2.py).
- 독립 검토 결론: [opus-v10-threeway-2026-10-12_0143-result.txt](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v10-threeway-2026-10-12_0143-result.txt) · [sonnet-v10-threeway-2026-10-12_0143-result.txt](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v10-threeway-2026-10-12_0143-result.txt).
- 직접 읽은 파일과 도구 기록: 위 모델 메타데이터와 [opus-v10-threeway-2026-10-12_0143-review.jsonl](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v10-threeway-2026-10-12_0143-review.jsonl) · [sonnet-v10-threeway-2026-10-12_0143-review.jsonl](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v10-threeway-2026-10-12_0143-review.jsonl).

## 입력 해시와 도구 범위 한계

각 첫·보충 감사의 입력 935개에 대해 시작·끝 SHA256을 저장했고 변화0개를 확인했습니다. v10 제품 소스는 변경하지 않았습니다.

- 보충 해시 차이: [opus-v10-threeway-2026-10-12_0143-sha256-diff.json](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v10-threeway-2026-10-12_0143-sha256-diff.json) · [sonnet-v10-threeway-2026-10-12_0143-sha256-diff.json](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v10-threeway-2026-10-12_0143-sha256-diff.json). 시작·끝 목록은 같은 접두의 `start-sha256.json`·`end-sha256.json`에 있습니다.
- 보충 시작 목록: [opus-v10-threeway-2026-10-12_0143-start-sha256.json](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v10-threeway-2026-10-12_0143-start-sha256.json) · [sonnet-v10-threeway-2026-10-12_0143-start-sha256.json](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v10-threeway-2026-10-12_0143-start-sha256.json).
- 보충 끝 목록: [opus-v10-threeway-2026-10-12_0143-end-sha256.json](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v10-threeway-2026-10-12_0143-end-sha256.json) · [sonnet-v10-threeway-2026-10-12_0143-end-sha256.json](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-v10-threeway-2026-10-12_0143-end-sha256.json).

도구 범위 이탈을 숨기지 않습니다. 최초 Sonnet이 시도한 추가 쉘 탐색은 CLI에서 거절됐습니다. 보충 Opus는 명시한 단위 실행기 외 후보 폴더의 `ls`를 실제 한 번 실행했습니다. 출력은 파일 이름 목록이며 환경값·키·고객 파일 내용이 출력되지는 않았지만, 지정 명령만 허용한다는 의도에는 어긋납니다. 해당 도구 출력과 모델의 자체 보고를 보존했습니다. 따라서 v10 감사 전체에 대해 「Bash는 지정 실행기만 실행했다」고 주장하지 않습니다. 후속 v11은 정확한 명령을 비교하는 PreToolUse 훅을 추가했고, 다른 명령과 연결 명령 거절을 [v11-exact-hook-preflight.json](../evidence/2026-10-11_1936_team_plugin_implementation/v11-exact-hook-preflight.json)에서 3/3 확인했습니다.

## 좁은 재현과 후속 보완 이유

실제 모델의 정적 관찰에서 읽기 요청의 중단 복구와 숫자 답 연결 경계를 별도로 추적했습니다.

1. 사실 질문이 CLASSIFIED 직후 중단되면 v10의 business 실행계획 재시도 관문에 걸려 같은 요청이409를 반복합니다. 실제 함수·실제 상태 리듀서를 쓰되 SQL·커밋은 메모리 대역으로 재현했으며, DB 내구성·프로세스 강제 종료 시험이 아닙니다. [v10-read-retry-crosscheck-2026-10-12_0150.py](../evidence/2026-10-11_1936_team_plugin_implementation/v10-read-retry-crosscheck-2026-10-12_0150.py) · [v10-read-retry-crosscheck-2026-10-12_0150.log](../evidence/2026-10-11_1936_team_plugin_implementation/v10-read-retry-crosscheck-2026-10-12_0150.log).
2. 앞서 대기한 업무 선택지가 있을 때 새 사실 답의 숫자를 이전 업무가 소비하는 경계를 `resume_pending` 실제 함수로 확인했습니다. Controller 대역은 호출만 기록했으며 일정 적용을 재현한 것이 아닙니다. 같은 원문에 함수·한계가 기록돼 있습니다.

읽기 재전송의 비교는 [read-retry-threeway-fastpath-2026-10-12_0152.py](../evidence/2026-10-11_1936_team_plugin_implementation/read-retry-threeway-fastpath-2026-10-12_0152.py)로 최신 운영 기준·v9·v10을 각각 불러 확인했습니다. v9와 v10 모두 저장된 업무 계획이 없는 읽기를409로 거절했고, 최신 운영 기준은 같은 업무의 실행을 복구하지 않은 채 중복 응답을 반환했습니다. 저장된 답이 있으면 최신 운영 기준은 답을 반환했습니다. 따라서 v10의 세 방향 결합에서 새로 도입된 회귀로 단정하지 않습니다.

- 비교 원문: [read-retry-threeway-fastpath-2026-10-12_0152-newbase.log](../evidence/2026-10-11_1936_team_plugin_implementation/read-retry-threeway-fastpath-2026-10-12_0152-newbase.log) · [read-retry-threeway-fastpath-2026-10-12_0152-v9.log](../evidence/2026-10-11_1936_team_plugin_implementation/read-retry-threeway-fastpath-2026-10-12_0152-v9.log) · [read-retry-threeway-fastpath-2026-10-12_0152-v10.log](../evidence/2026-10-11_1936_team_plugin_implementation/read-retry-threeway-fastpath-2026-10-12_0152-v10.log).

이 두 부족은 이번 작업의 같은 업무 복구·새 질문 분리 요구와 연결되므로, 새 후보 v11에서 별도 보완합니다. 위치 좌표를 저장하는 방식으로 복구 범위를 늘리지 않습니다. 이 보고서의 모델 50개·메모리 재현을 v11 실제 HTTP 통과 근거로 바꾸어 쓰지 않습니다.

## 보존 상태

v10 제품·감사 원문은 그대로 보존했습니다. 새 보고서이므로 덮어쓴 이전 판은 없습니다. 최초 보충 Opus 프롬프트 변경 전 원본은 [백업](../evidence/2026-10-11_1936_team_plugin_implementation/_backup/2026-10-12_0146_opus_followup_scope/)에 있습니다. 실제 v11 구현 백업은 [후보의 원본 두 파일](../../../legacy/deployment_candidates/2026-10-12_015017_plugin_v11/_backup/2026-10-12_0158_read_recovery/)에 별도로 보존했습니다.
