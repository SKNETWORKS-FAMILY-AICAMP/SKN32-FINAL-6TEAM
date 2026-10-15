# 배포 후보 v5 — 실제 Opus 5.5 읽기 감사

분리한 배포 후보에서 함수 이식 누락과 재개·재시도 경계의 위험을 추가로 찾았습니다. 이 기록은 정적 감사이며 실행 재현·제품 수정·운영 배포를 하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 실제 Opus 읽기 감사 | 끝 | 1/1 = 100% |
| 후보 변경 파일 해시 대조 | 동일 | 50/50 = 100% |
| 감사 입력 해시 대조 | 동일 | 2/2 = 100% |
| 지적 실행 재현 | 이번 범위 제외 | 0/7 = 0% |

## 대상과 실제 실행

대상은 [후보 v5](../../../legacy/deployment_candidates/2026-10-11_222547_plugin_v5/)의 `release-manifest.json`, `runtime-overlay.diff`, 해당 후보 소스입니다. 현재 작업 폴더의 제품 구현과 운영 환경을 혼합하여 검토하지 않았습니다. 요청 모델·초기 모델·최종 `canonicalModel`은 모두 `claude-opus-5-5`, `is_error=false`, CLI 종료 코드 0입니다.

사용 가능한 도구와 실제 호출 도구는 Read·Grep·Glob뿐입니다. 도구 호출 113회, Read 요청 49회, 성공한 Read 경로는 서로 다른 32개입니다. 큰 diff를 읽던 두 요청은 토큰 한도 때문에 실패했고 더 작은 구간으로 다시 읽었습니다. 권한 거절은 0건입니다. 변경 diff는 전체 구간을 나눠 읽었으나 50개 파일의 전후 문맥을 전부 직접 읽었다는 뜻은 아닙니다. 정확한 파일·offset·limit는 아래 모델 메타데이터에 보존했습니다.

모델은 후보 디렉터리 전체 grep 중 `release-overlay/.../mcp_server.py`의 주석 한 줄을 보았다고 명시했습니다. 해당 파일을 Read로 열지는 않았습니다. 이 범위 유입도 감추지 않고 원문에 보존했습니다.

## 추가 지적과 확인 수준

Opus가 다음 7건을 확정 결함으로 분류했습니다. 아래 표의 판단은 그 결과를 그대로 실행 증명으로 승격하지 않고, 후보 소스 대조와 추가 확인 조건을 구분한 것입니다. 부모 작업에 원문과 위치를 먼저 전달했으며 임의로 수정하지 않았습니다.

| 지적 | 후보 위치 | 확인한 조건·남은 확인 |
|---|---|---|
| 접수 복원 호출 인자 불일치 | `entry/trip_api.py:1438-1440`, `components/intake/pipeline.py:472-473` | 호출은 `item=`을 항상 전달하지만 대상 함수는 받지 않습니다. 소스의 서명 불일치는 재확인했습니다. 실제 HTTP 재현은 하지 않았습니다. |
| 대기 업무가 사실 질문·새 요청을 가져감 | `components/conversation/trip_messages.py:317-325`, `case_dispatch.py:107-120` | 재개를 사실 질문 처리보다 먼저 시도합니다. 자동 선택 정책과 사용자 구분 수단을 검토해야 하며 모델의 반복 질문 예는 실행하지 않았습니다. |
| 만료 뒤 첫 입력이 401 | `application/controller.py:853-865`, `entry/trip_api.py:1045-1046` | 만료 상태 전이 뒤 ControllerError가 반환됩니다. 새 입력 처리·화면 복구는 실행 미확인입니다. |
| 비활성 담당의 대기 업무가 채팅을 막음 | `application/controller.py:854,872` | 기존 담당 관문이 재배분보다 먼저입니다. 해당 업무 거절은 계약상 의도이므로 독립 질문까지 막는 범위를 별도로 확인해야 합니다. |
| 감시 업무의 실행 중 불가 뒤 자동 재시도 누락 | `components/watch/trip_watch_cases.py:177-185,349-356` | TeamUnavailable 때 상태를 보존하고, RUNNING은 후속 회차의 재시도 조건에 없습니다. 소스 조건을 재확인했습니다. 실제 회차 복구는 미확인입니다. |
| 답변 저장과 실행 시작 사이 RESUMING 복구 공백 | `application/controller.py:833-850,924-931` | 답변 커밋 뒤 실행 전 중단될 수 있고 동일 요청 재실행 분기는 RUNNING만 다룹니다. 소스 조건을 재확인했습니다. 중단 주입 시험은 하지 않았습니다. |
| 실패 요청의 동일 번호 재전송이 duplicate 응답 | `components/conversation/trip_messages.py:302-316` | Case 상태와 실행 여부에 관계없이 기록 존재로 중복 응답합니다. 소스 조건을 재확인했습니다. 실제 실패·재전송 시험은 하지 않았습니다. |

위 도메인 경로는 모두 후보의 `app/domains/travel_ops/` 아래입니다. 재개 기능 전체가 실패한다고 일반화하지 않습니다. 문제 조건이 없는 정상·대기·답변 재개와 이미 적용한 변경의 중복 차단에 대한 기존 시험 증거는 별도입니다.

## 기존 증거와 이번 감사의 한계

부모가 전한 로컬 후보 327건, 동일 이미지 Linux 합성 175건, SQL 85개·requirements 바이트 동일, 대상 DB 메타데이터 197개 일치는 이번 CLI가 직접 검증하지 않았습니다. 이번에 시험을 다시 실행하지 않았습니다. 외부 서비스·실제 고객 값·비밀 파일·DB·운영 접속도 사용하지 않았습니다. 후보가 실제 운영에서 동작한다는 판정이나 배포 승인이 아닙니다.

worker 성공 1회 초기화·실패 재시도·독립 작업 유지, 요청 계산 표 고정, Team 관문, A2A 식별자·async transport·취소 예산은 모델이 읽은 범위에서 추가 결함을 지적하지 않았습니다. 소스 전체나 실제 실행에 대한 무결함 보장은 아닙니다.

## 근거

- [감사 프롬프트](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-prompt.txt), [허용·거절 설정](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-permissions.json)
- [실제 CLI JSONL](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-review.jsonl), [모델 최종 원문](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-result.txt)
- [모델·Read 구간·도구 오류 메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-model-metadata.json), [CLI 종료](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-cli-exit.json)
- [시작 해시](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-start-sha256.json), [종료 해시](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-end-sha256.json), [차이 0건](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-sha256-diff.json)

## 별도 Codex 정적 보충: 사전 거절 보장의 범위

일반 Case 메시지 입구에는 `resume_prepare`가 없습니다. 기존·최종 담당과 capability의 관문은 답변 저장 전에 확인하지만, 활성 Dining 업무가 실행 중 실제로 요구하는 Mobility 계산까지 일괄 사전 검증하지는 않습니다. 이 경우 답변·event 식별자를 저장한 뒤 필수 계산 불가로 실패할 수 있습니다. 입력 손실이라고 단정할 근거는 없으며, RUNNING·활성 run 없음·동일 event 조건에서 기존 입력으로 재실행할 수 있는 코드 경계와 실제 실행 확인을 구분합니다.

이 질문은 이미 실행 중이던 Opus 호출에 추가 주입하지 않았습니다. [별도 정적 검토 원문](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-generic-resume-boundary-note.md)은 Codex의 검토입니다. 부모 승인으로 [현재 가용성 계약](../../teams/team-contract/plugin-availability.md)의 광범위한 사전 보장 문구만 정정했습니다. 코어의 도메인 의존성이나 새 전체 사전 검사를 추가하지 않았습니다.

원본은 [계약 백업](../../teams/team-contract/_backup/2026-10-11_231032_resume_guarantee_scope/plugin-availability.md)에 보존했습니다. [문구 차이](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-contract-scope.patch)와 [UTF-8·공백 확인](../evidence/2026-10-11_1936_team_plugin_implementation/opus-v5-readonly-2026-10-11_225348-contract-verification.json)을 남겼습니다. 이 문서 정정은 후보 50개 소스 밖의 변경이며 Opus가 정정 계약을 검토했다고 주장하지 않습니다. 실행 확인은 부모의 별도 작업입니다.
