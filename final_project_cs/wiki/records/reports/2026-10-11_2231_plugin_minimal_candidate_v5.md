최종 후보는 운영 기준 사본에서 필요한 코드만 이식했으며 선택한 로컬 회귀 시험 327개를 통과했습니다. 운영 반영은 실행하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 운영 기준 사본 보존 | SHA256 일치 | 404/404 = 100% |
| 후보 변경 파일 묶음 | 해시 일치 | 50/50 = 100% |
| 후보 기능 회귀 | Windows 통과 | 327/327 = 100% |
| 대상 DB 구조 대조 | READ ONLY 일치 | 197/197 = 100% |
| 운영 이미지 문법 확인 | Linux 통과 | 48/48 = 100% |
| 실제 운영 반영 | 미실행 | 0/1 = 0% |

작성: 2026-10-11T22:31:57.757563+09:00

## 후보의 범위

기준은 기존 cs 프로젝트 API 컨테이너에서 읽기 복사한 실제 배포 코드입니다. 해당 사본은 원형을 보존했습니다. 전체 작업 트리의 차이를 이번 작업이라고 간주하지 않았습니다.

플러그인 설치·활성 상태와 고정된 계산 제공자를 확인하는 관문, 대화의 대기·답변 재개, 동일 업무의 단일 적용, 요청·반복 작업의 같은 구성 판 유지, A2A 마감·취소 및 실패 감사가 들어갑니다. HTTP 등록·계획 생성·식당 연결·지도 경로와 읽기 도구도 담당 팀 관문을 통과합니다. 중첩 이동 계산의 담당 불가 오류를 어림값으로 바꾸지 않습니다. 반복 작업의 상태 있는 초기화는 성공 후 보존하고 실패 때 재시도합니다.

운영 사본에 없던 필수 대화 선행 변경도 포함했습니다. 답변을 전달하는 대화 진입 함수, AppliedAction의 실제 질문 응답 필드, 질문을 반환하는 두 적용 함수입니다. 혼합 변경 파일은 해당 함수·예외 경계만 이식했습니다.

새로운 감시 이력(228), 서비스 개선 자료 보관(229), 예보 제안(059), 시나리오 제안 범위(227), 출발 직전 재검사, CaseEngine의 시나리오 service_overrides 변경은 제외했습니다. 기존 SQL 85개와 requirements.txt는 운영 사본과 바이트 단위로 같습니다. 새 SQL 실행은 필요하지 않습니다.

- [최종 후보](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5) — 운영 기준에 최소 변경을 이식한 별도 사본입니다.
- [설치 대상 50개 파일](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/release-overlay) — 48개 Python과 2개 YAML만 담습니다. 시험·문서·DB·환경 파일은 들어가지 않습니다.
- [해시 manifest](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/release-manifest.json) — 운영 기준 및 후보 SHA256, 신규 파일, 제외 범위입니다.
- [검토용 차이](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/runtime-overlay.diff) — 전체 작업 트리와 분리한 실제 후보 차이입니다.
- [원본 보존본](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_baselines/2026-10-11_214932) — 404개 파일 해시가 수집 때와 모두 같습니다.
- [이전 통과 후보](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_221806_plugin_v4) — 후속 수정 전 후보를 덮어쓰지 않았습니다.

## 실행 근거와 확인 범위

분모 327은 아래 17개 시험 파일의 개별 수집 항목 수입니다. 건너뜀·실패는 0개입니다. 69.82초에 통과했습니다. 후보 폴더를 실행 위치와 PYTHONPATH로 사용했습니다. 실제 FastAPI 처리·Controller·등록 Team·SQL을 거치되 모델 응답과 외부 제공자는 합성 시험 대역으로 통제했습니다. 실사용 LLM·외부 지도 API 정확도 검증은 아닙니다.

| 시험 파일 | 통과 |
|---|---|
| [test_plugin_availability.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/unit/core/test_plugin_availability.py) | 45/45 = 100% |
| [test_plugin_composition_runtime.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/unit/test_plugin_composition_runtime.py) | 27/27 = 100% |
| [test_plugin_read_boundaries.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/unit/travel/test_plugin_read_boundaries.py) | 10/10 = 100% |
| [test_plugin_worker_availability.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/unit/travel/test_plugin_worker_availability.py) | 26/26 = 100% |
| [test_plugin_unavailable.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/integration/controller/test_plugin_unavailable.py) | 33/33 = 100% |
| [test_conversation_resume.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/integration/controller/test_conversation_resume.py) | 19/19 = 100% |
| [test_unknown_route_availability.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/integration/controller/test_unknown_route_availability.py) | 5/5 = 100% |
| [test_case_state_table.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/contract/test_case_state_table.py) | 23/23 = 100% |
| [test_candidate_packaging.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/unit/test_candidate_packaging.py) | 2/2 = 100% |
| [test_web_conversation_resume.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/e2e/test_web_conversation_resume.py) | 9/9 = 100% |
| [test_conversation_work.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/unit/travel/test_conversation_work.py) | 45/45 = 100% |
| [test_trip_api_plugin_boundaries.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/unit/travel/test_trip_api_plugin_boundaries.py) | 36/36 = 100% |
| [test_intake_resolve_dining.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/unit/travel/test_intake_resolve_dining.py) | 11/11 = 100% |
| [test_plugin_unavailable_propagation.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/unit/travel/test_plugin_unavailable_propagation.py) | 9/9 = 100% |
| [test_dining_read_tool_availability.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/unit/travel/test_dining_read_tool_availability.py) | 22/22 = 100% |
| [test_catalog_state_plugin.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/integration/dining/test_catalog_state_plugin.py) | 3/3 = 100% |
| [test_query_scope.py](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/deployment_candidates/2026-10-11_222547_plugin_v5/tests/security/test_query_scope.py) | 2/2 = 100% |

시험 DB는 운영 사본의 SQL 85개만 새 빈 로컬 DB에 적용했습니다. 고객·운영 데이터를 복사하지 않았습니다. 기존 개발 DB의 예보·시나리오 관련 UNIQUE 변경 때문에 발생했던 보호 식당 질문 실패는 그 DB를 후보 검증에 재사용하지 않고 분리해 해결했습니다. 운영 SQL을 임의로 고치거나 후보에 다른 기능을 섞지 않았습니다.

worker 시험에서 미포함 예보 함수의 monkeypatch에 raising=False를 주고, 미포함 감시 이력 래퍼 mock만 제거했습니다. 담당 불가·회차 격리·중복 적용 방지 등의 결과 assertion은 유지했습니다. 신규 워밍 캐시 보존·초기화 실패 재시도 시험 2개도 포함합니다.

운영 DB는 READ ONLY 트랜잭션으로 public의 지정 13개 표 구조만 확인했습니다. 140개 열, 36개 제약, 상태 enum 2종의 21개 값이 후보 합성 DB와 동일합니다(197 = 140+36+21). pending_changes는 실제로 4열 UNIQUE이며 proposal_scope 열은 없습니다. DB 행은 읽지 않았습니다. 이 대조는 해당 13개 표와 2개 enum 범위이며 모든 DB 객체를 검증한 뜻은 아닙니다.

로컬 PC에서는 Docker 명령 및 표준 설치 바이너리가 확인되지 않았고, WSL은 미설치 안내와 종료 코드 1을 반환했습니다. 따라서 기능 회귀는 Windows Python 3.12.7에서 실행했습니다. 별도로 기존 운영 이미지의 Linux Python 3.12.15에서 후보 48개 Python 소스를 stdin으로 전달해 해시 확인 후 compile만 수행했습니다. 앱 소스를 실행·import하거나 운영 파일을 바꾸지 않았습니다. 이 결과는 Linux 기능 E2E 통과를 뜻하지 않습니다.

- [최종 검증 JSON](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/candidate-v5-verification.json) — 시험별 수와 해시, 보존·환경 범위입니다.
- [327개 회귀 로그](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/candidate-plugin-v5-combined-v1.log) — 최종 동일 후보의 실행 기록입니다.
- [운영 DB 구조 원본](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/deployed-schema-metadata-v1.json) — table_name이 포함된 구조 정의만 보존했습니다.
- [구조 대조](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/candidate-deployed-schema-comparison-v1.json) — 대상 범위가 모두 일치했습니다.
- [운영 Linux 문법 확인](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/candidate-v5-operating-linux-compile-v1.json) — 48개 해시 및 compile 결과입니다.
- [로컬 Linux 가용성](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/local-linux-runtime-availability.json) — 설치를 변경하지 않고 확인한 결과입니다.

## 실제 반영 전 남은 단계

1. 기존 운영 이미지 ID와 일치하는 이미지를 기반으로 overlay만 더한 이미지를 격리 빌드하고, Linux 환경에서 합성 DB를 사용하는 API·worker 기능 시험을 실행해야 합니다. Dockerfile.overlay는 이 목적의 초안이며 아직 빌드하지 않았습니다. 기존 이미지의 prompts·문구 자료·시작 명령을 상속합니다. 일반 Python 이미지에 이 후보만 복사하는 방식으로 바꾸면 빠지는 자산이 있으므로 그대로 재빌드하지 않습니다.
2. 실제 worker 컨테이너의 이미지·실행 설정과 운영 API의 설정을 비교하고 같은 후보로 일관되게 교체할 배포·롤백 절차를 확정해야 합니다. API에서 읽은 코드·패키지를 worker에서도 확인했다고 확대하지 않습니다. 운영 환경의 실제 모델·외부 제공자를 연결한 새 버전 기능 smoke도 별도입니다.
3. 반영 후에는 담당 팀 비활성 상태의 503·대기 답변 토큰 보존, 재활성 후 같은 답변의 단일 일정 변경, worker 다음 회차 실행과 구성 revision을 실제 새 프로세스에서 확인해야 합니다. /health는 단순 응답이며 /ready는 기존 404라 이들만으로 기능 성공을 판단하지 않습니다.

롤백 기준은 보존한 운영 이미지와 기존 project.yaml·guardrails.yaml을 함께 복원하는 것입니다. 이번 후보는 SQL 변경을 포함하지 않으므로 SQL 역변환을 만들지 않았습니다. 실제 운영 파일·프로세스를 변경하지 않았기 때문에 현재 되돌릴 운영 변경도 없습니다.

커밋·푸시·배포·재시작·운영 DB 쓰기는 하지 않았습니다. baseline/candidate는 로컬 보존용이며 현재 gitignore에 자동 제외되지 않으므로 전체 추가 대상에 넣지 않아야 합니다.
