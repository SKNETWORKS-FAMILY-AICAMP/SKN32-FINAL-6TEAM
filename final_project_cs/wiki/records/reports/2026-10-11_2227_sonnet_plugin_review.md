# 실제 Sonnet 5.5 후속 감사와 보완 근거

실제 Claude Sonnet 5.5가 최신 후속 변경을 검토하고 고정 16개 pytest 파일의 259건을 직접 실행했습니다. 이후 발견 지적을 보완한 코드는 별도로 167건을 실행해 확인했습니다. 두 판은 같은 소스가 아니며, 259건 통과로 이후 수정을 검증했다고 주장하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 실제 Sonnet 후속 직접 회귀 | 통과 | 259/259 = 100% |
| 감사 시작·끝 해시 동일 | 동일 | 30/30 파일 = 100% |
| 지적 보완 후 로컬 회귀 | 통과 | 167/167 = 100% |

해시 분모는 아래 JSON의 실제 항목 수를 기준으로 확인합니다. 시험 집합은 겹치므로 서로 더하지 않습니다.

## 실제 모델·실행 증거

[모델 메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-followup-model-metadata.json)는 requested_model과 canonicalModel 모두 `claude-sonnet-5-5`, is_error=false, CLI 종료코드 0, permission_denials=[]입니다. 다른 모델로 대체하지 않았습니다.

[프롬프트](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-followup-prompt.txt), [고정 runner](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-followup-pytest.py), [전체 JSONL](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-followup-review.jsonl), [시험 원문](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-followup-tests.json), [감사 결과 원문](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-followup-result.txt)을 보존했습니다. Bash는 해당 고정 runner 명령 하나만 허용했고 Read/Glob/Grep을 사용했습니다. 직접 실행 결과는 259 passed in 32.35s, PYTEST_EXIT=0입니다.

[시작 SHA256](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-followup-start-sha256.json)과 [끝 SHA256](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-followup-end-sha256.json)의 [차이](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-followup-sha256-diff.json)는 빈 객체입니다. 이 해시 집합이 감사의 고정 범위이며 저장소 전체가 아닙니다.

그 이전 실제 Sonnet 감사는 [첫 모델 메타데이터](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-model-metadata.json)와 [첫 시험 원문](../evidence/2026-10-11_1936_team_plugin_implementation/sonnet-post-opus-tests.json)의 179건입니다. 이전 결과를 후속 변경의 통과 근거로 재사용하지 않습니다.

## 지적을 실제로 보완한 범위

Sonnet은 blocker를 찾지 못했으나 default_engine이 바인딩 없는 non-standalone의 TeamUnavailable을 None으로 바꿀 가능성을 지적했습니다. 실제 호출에서 None을 재현했고 해당 예외만 재전파하도록 수정했습니다. 일반 예외의 기존 독립 실행 정책은 유지합니다.

저장된 접수 검사 결과가 None인 경로선 GET은 새 계산을 하지 않는 순수 조회입니다. Mobility가 꺼지거나 없더라도 200과 빈 목록을 돌려주며 제공자 호출은 0회가 되게 보완했습니다.

이름 조회·계획 생성·식당 UID 연결의 HTTP 시험 공백도 채웠습니다. disabled/not_installed/load_failed 각각에서 실제 편집/계획 생성/등록 HTTP 처리기가 필수 Dining 관문을 타는지 9건을 확인했습니다. 이름 조회는 합성 접수 저장 경계에서 실제 places.resolve를 실행하며, 전체 접수 DB 쓰기 검증을 뜻하지 않습니다. 계획 생성과 UID 연결은 DB 연결 전에 필수 제공자를 확인합니다. 식사 항목이 없지만 UID를 연결하는 요청도 포함합니다.

[보완 후 회귀](../evidence/2026-10-11_1936_team_plugin_implementation/trip-api-gates-v4.log)는 신규 HTTP 경계 총36건과 관련 기존131건을 합쳐 167 passed in 7.72s입니다. [ruff](../evidence/2026-10-11_1936_team_plugin_implementation/trip-api-gates-lint-v4.log) 8파일과 [대상 diff 공백 검사](../evidence/2026-10-11_1936_team_plugin_implementation/trip-api-gates-diffcheck-v4.log)도 통과했습니다. [보완 소스 SHA256](../evidence/2026-10-11_1936_team_plugin_implementation/trip-api-gates-sha256-v4.json)은 Sonnet 직접 검토가 끝난 후의 소스입니다.

중간 v3의 UID 연결 3건 실패는 사전 관문 코드 삽입이 빠진 실제 구현 누락을 새 HTTP 시험이 검출한 것입니다. 이를 수정했고 실패 로그도 보존했습니다. [패치 전 백업](../../../legacy/team_plugin_lifecycle/2026-10-11_2222_sonnet_followup_gates/)이 있습니다.

## 검토 한계와 다른 작업의 결과

재생 서비스는 대본의 시간·노선을 고정하는 오케스트레이션 시험이며 실제 사고 반영이나 이동 정확도의 근거가 아닙니다. disruptions 미반영과 1200m 정책 고정 등의 한계를 정확도 개선으로 해석하지 않습니다. Sonnet은 Watcher/Desk 표 일치와 이전 모든 계약을 전부 다시 읽지 않았다고 명시했습니다.

감사 중 전체 시나리오 v2는147/148이며 알림 시험 1건이 실패 상태였습니다. 이후 부모 작업자가 시험의 모든 대안 통제 전제를 고치고 전체 시나리오 v3 148/148 및 watch_batch9/9를 별도로 확인했습니다. 해당 fixture 수정은 이미 종료한 Sonnet 감사에 포함하지 않습니다. 제품 코드 변경은 없습니다. 전체 시나리오 통과를 이동 정확도로 부르지 않습니다.

실서버 확인(서버 응답): x600 서버의 cs 프로젝트 서버 요청은 하지 않았습니다. 고객 데이터·키·접속 정보·실제 데이터셋은 감사에 제공하지 않았습니다. 259 묶음에는 개발 DB 의존 합성 integration 시험이 있고, 167 후속 묶음은 합성 unit/HTTP 처리기 시험입니다. mock 서버 화면 반응 시험을 시행한 것은 아닙니다. 커밋·푸시·배포도 하지 않았습니다.

초기 광범위 Bash 허용 요청은 자동 승인 검토에서 거절됐습니다. 이유는 외부 CLI가 비밀 파일 읽기·수정·전송을 실행할 수 있는 범위였습니다. 고정 합성 pytest runner 한 명령만 허용하는 안전한 방식으로 좁혀 실제 검토를 완료했습니다. 후속 호출에는 권한 거절이 없었습니다.
