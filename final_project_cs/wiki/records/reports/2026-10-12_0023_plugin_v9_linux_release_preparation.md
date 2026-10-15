# 최종 최소 후보 v9 — Linux 검증 및 운영 반영 준비

생성: 2026-10-12 00:23 KST. 이 문서는 운영 반영을 실행한 기록이 아닙니다.

최종 후보의 격리 Linux 시험과 새 이미지 검증이 통과했습니다. x600 서버의 cs 프로젝트 API·worker는 기존 이미지로 계속 실행 중입니다. 운영 HTTP 쓰기시험은 외부 알림 차단 전제가 충족되지 않아 이번 승인 범위에서 분리해야 합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 최종 후보 격리 시험 | 통과 | 388/388 = 100% |
| 이미지 내부 소스 해시 | 일치 | 51/51 = 100% |
| 패키지 버전 상속 | 일치 | 8/8 = 100% |
| 운영 API·worker 교체 | 미실행 | 0/2 = 0% |

## 무엇을 검증했는가

운영 기준 사본 404개 파일 위에 이번 플러그인 가용성·대기·답변 재개·같은 요청 복구에 필요한 변경 51개(파이썬 49개, YAML 2개)만 선택 이식했습니다. 현재 개발 작업 트리 전체를 가져오지 않았습니다. 기존 requirements와 DB 변경 SQL 85개는 바이트 단위로 같습니다. 스키마 변경·패키지 설치는 없습니다.

최종 후보는 [v9 보존본](../../../legacy/deployment_candidates/2026-10-12_001736_plugin_v9/)이며 [파일별 변경·SHA256 manifest](../../../legacy/deployment_candidates/2026-10-12_001736_plugin_v9/release-manifest.json)와 [최소 변경 diff](../../../legacy/deployment_candidates/2026-10-12_001736_plugin_v9/runtime-overlay-v9.diff)를 함께 보존했습니다. 최종 manifest SHA256은 `4cb44cf6d25fa06cc0cdc8a98a2176f5c720093daa30df291b798fa3a5b87b45`입니다. 원본 기준 사본과 앞선 후보는 덮어쓰지 않았습니다.

Linux Python 3.12.15·pytest 8.4.2에서 별도 일회용 앱 컨테이너·PostgreSQL 컨테이너를 만들었습니다. 내부 전용 네트워크와 tmpfs 합성 DB만 사용하고 운영 DB·볼륨·환경값·고객 데이터를 연결하거나 복사하지 않았습니다. 모델·지도 호출은 합성 대역이며 외부 통신은 차단했습니다. 시험 종료 후 전용 컨테이너·네트워크 잔류는 0개였습니다.

- 최종 v9: **388/388 통과**, 실패 0, 건너뜀 0, 39.56초. 기존 anyio 별칭 사용 경고 1개가 있습니다. [원문 로그](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-isolated-linux-db-full-v1.log), [실제 시험별 결과·해시 JSON](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-isolated-linux-verification-v1.json).
- v8 당시: **384/384 통과**, 40.07초. 마지막 ROUTED 경합 관문과 추가 4건 이전 판입니다. [v8 결과](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v8-isolated-linux-verification-v1.json).
- v7 당시: 382개 수집 중 **355 통과·24 실패·3 건너뜀**. 무관한 대화 기능을 함수 전체 복사하면서 누락 의존성이 생긴 실패이며, v8에서 필요한 구간만 이식해 수정했습니다. [실패 원문](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v7-isolated-linux-db-full-v1.log). 반복 시험 횟수를 합쳐 최종 분모를 늘리지 않았습니다.

최종 집합에는 실제 HTTP 대기→답변→중복 단일 적용, 암묵 답변 상관관계, 다른 여행·사용자 격리, 초기 요청 동시 생성, VALID_INPUT 저장 직후 중단 복구, 담당 부재 503, 실행 중 다른 필수 담당 부재 후 같은 요청 재시도, 감시 업무 회복, 과거 일정 전체 복원 성공·오래된 복원 거부가 포함됩니다. 마지막 경합 수정은 준비 중 다른 실행이 먼저 진행되면 HTTP 409로 거부하고 승자 결과를 보존합니다.

AST 대조는 새 내부 import 119/119 해석 성공, 새 미정의 호출 이름 0개입니다. 동적 import 1곳은 정적 검사만으로 의미를 증명하지 못하며 별도 조립 시험으로 확인했습니다. [선택 변경·import 대조 결과](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-ast-closure-v1.json).

## 새 검증 이미지

새 고유 태그 `tripilot-plugin-validated:20261012-001923-v9` 하나만 제작했습니다. 실제 이미지 ID는 `sha256:9f14e94f2f0acfee4a20a8dde2fac6d9d2f154be69cccf7f9b98b6368e574bed`입니다. 기존 태그·compose·환경값·운영 컨테이너는 변경하지 않았습니다.

빌드 문맥은 소스 51개 + 공식 공개 토크나이저 파일 1개 + Dockerfile 1개, 총 **53개 명시 파일**입니다. 운영 소스 통복사나 비밀 파일은 들어가지 않았습니다. [빌드 문맥 manifest](../../../legacy/release_build_contexts/2026-10-12_001923-manifest.json).

첫 시도에서는 BuildKit이 기준 imageID를 외부 태그로 해석해 registry metadata 확인을 시도했고 실패했습니다. 해당 실패를 [v1 로그](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-isolated-image-build-v1.log)에 보존했습니다. 기준 이미지의 기존 로컬 태그가 보존 ID와 같은지 전후 확인한 두 번째 시도는 성공했습니다. `--pull=false`로 추가 이미지 다운로드는 없었습니다. 빌드의 `--network none`은 RUN 단계에 적용되므로 metadata 네트워크 시도 횟수까지 0이라고 주장하지 않습니다.

새 이미지의 명시 소스 51/51 해시, 패키지 8/8 버전, 시작 명령·entrypoint·작업 폴더·사용자·볼륨 선언 5/5 상속을 확인했습니다. 공식 `cl100k_base` 파일의 SHA256은 `223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7`이며 1,681,126바이트입니다. 비루트·읽기 전용·네트워크 차단 프로세스에서 첫 토큰 계산 3개가 성공했고 실제 계측한 연결 시도는 0회입니다. 이 결과는 모델 생성 품질 검증이 아닙니다.

[빌드·검증 원문](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-isolated-image-build-v2.log), [51개 해시·8개 버전·캐시 검증 결과](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-isolated-image-verification-v1.json).

## 운영 적용 전에 확인할 것

00:18 KST 읽기 전용 재확인에서 운영 API·worker 2/2 이미지 ID가 원본 기준과 같았습니다. [재확인 결과](../evidence/2026-10-11_1936_team_plugin_implementation/deployed-baseline-image-recheck-before-v9-build.json). 00:31 KST 재확인에서도 같은 원본 ID가 2/2 유지됐습니다. 실제 교체 직전 다시 대조하고 달라졌으면 적용을 중단합니다. 현재 배포 선언의 환경 파일 입력과 실행 구성을 읽어 검증했으며, 운영 값은 공개 출력하거나 파일로 저장하지 않았습니다.

현재 디스크의 배포 선언을 그대로 재실행하면 실행 중 환경과 다른 값이 한 키에서 나타납니다. 원래 배포할 때의 과거 CLI 명령은 이 결과만으로 복원했다고 주장하지 않습니다. API 시작 명령이 선언에 없던 차이는 이미지 기본 명령을 적용하면 기존 실행 명령과 같았으며 실제 명령 변경은 아니었습니다.

현재 실행 중인 API·worker의 기존 환경 72개씩·명령·entrypoint를 원격 Python 메모리에서만 유지한 stdin 변경안을 읽기 전용으로 resolve했습니다. 기존 환경 144/144가 보존되고 명령·작업 폴더·사용자·마운트·네트워크·재시작 정책·포트·읽기 전용/권한 설정도 두 프로세스 모두 일치했습니다. 새 이미지가 추가하는 공개 캐시 환경 이름 1개만 의도된 추가입니다. 비밀 원값은 stdout·파일·명령줄 인자에 담지 않았으며 운영 변경도 없습니다. 이 검증한 메모리 변경안이 실제 적용 계획이고, 디스크 선언만 그대로 재실행하는 계획은 사용하지 않습니다. [읽기 전용 구성 보존 결과](../evidence/2026-10-11_1936_team_plugin_implementation/deployed-preserving-stdin-release-preconditions-v5.json), [YAML 해시·마운트 대조](../evidence/2026-10-11_1936_team_plugin_implementation/deployed-compose-yaml-release-preconditions-v3.json). 앞선 v3의 추가 CLI env-file 불필요 추정은 v4에서 미확인으로 정정했고, v5는 과거 명령 재구성 대신 현재 실제 실행 구성 보존을 증명합니다.

1. 새 이미지의 파일·의존성·설정 상속을 최종 manifest와 대조합니다. 운영 환경변수·두 YAML의 기존 값 및 비밀값을 덮어쓰지 않습니다. 후보의 두 YAML에는 이번 기능에 필요한 계약·guardrail 차이가 있으므로 기존 값은 전부 보존됐고 의도한 추가는 여섯 담당의 필수 여부·능력·훅 선언과 마감 정리 시간 두 항목입니다. 운영 두 YAML 해시는 원본 기준과 같고, 두 파일 및 새 캐시를 가리는 마운트는 없습니다. [기존 YAML 값 보존·추가 목록](../evidence/2026-10-11_1936_team_plugin_implementation/candidate-v9-yaml-preservation-and-intended-additions.json).
2. 별도 운영 승인 후 API·worker 둘만 같은 새 이미지로 재생성합니다. DB·web 컨테이너는 교체하지 않고 SQL을 실행하지 않습니다. 잠깐의 프로세스 재기동이 있습니다.
3. 새 프로세스의 건강 응답, 활성 담당 구성, 실제 구성 revision, worker 다음 회차와 오류 기록을 확인합니다. 건강 응답 200만으로 대기·재개가 검증됐다고 하지 않습니다. 운영에서 실제 대기·답변·중복 쓰기를 할지는 아래 안전 전제를 먼저 충족해야 합니다.
4. 검증 실패 시 API·worker 둘을 원본 이미지로 함께 되돌려 시작합니다. 원본 이미지에 포함된 두 YAML 및 기존 배포 설정을 함께 복원·대조합니다. DB는 역변환하지 않습니다. 이미 완료된 고객 일정이나 발송 기록은 자동으로 되돌리거나 지우지 않습니다.

복원 조건은 프로세스 기동 실패, 필수 담당 조립 실패, 새로운 5xx 증가, 구성 revision 불일치, worker 회차 실패, 합성 검증에서 중복 적용·입력 유실 발생입니다. 단일 프로세스만 먼저 복원한 상태를 완료로 간주하지 않습니다.

## 운영 HTTP 합성 쓰기를 아직 승인 범위에 넣지 않는 이유

현재 HTTP 인증은 운영 tenant 설정에 고정되어 있습니다. 설정을 바꾸지 않고 별도 합성 tenant를 HTTP로 선택할 수 없습니다. 기존 tenant 안의 새 합성 사용자·여행은 만들 수 있으나, 연락처를 연결하지 않는 것만으로 외부 알림 0회를 보장할 수 없습니다.

00:22 KST 읽기 전용 확인에서 API·worker 모두 고객별 알림 스위치가 꺼져 있고, 배포된 기존 알림 코드는 이때 운영자 발행기로 넘깁니다. 후보 v9는 이 기존 알림 파일을 변경하지 않습니다. 고객 행·연락처·환경 원값을 읽지 않고 분기와 참/거짓만 확인했습니다. [안전 전제 결과](../evidence/2026-10-11_1936_team_plugin_implementation/deployed-synthetic-smoke-notice-preconditions-v1.json).

따라서 이번 운영 승인은 **API·worker 이미지 교체·재기동과 읽기 전용 확인**까지로 분리하는 것이 안전합니다. 실제 운영 HTTP의 질문→“30분이요”→같은 요청 재전송은 외부 발행 차단 방법을 검증하고 별도 승인 범위에 넣은 뒤 수행합니다. 운영 합성 사용자·여행·답변·정리 작업은 아직 한 건도 실행하지 않았습니다.

이후 운영 합성 쓰기가 승인되면 고유 합성 사용자/여행/Case/request ID만 개인 실행 장부로 관리하고, 그 소유권을 매 요청 확인합니다. 변경 전후 일정 판·적용 장부를 읽어 적용 1회와 중복 추가 적용 0회를 확인합니다. 정리는 소유권 확인을 하는 기존 여행 삭제 경로로 해당 합성 여행만 삭제하고, 키·합성 계정 정리는 정확한 생성 ID와 의존 행을 세어 별도 트랜잭션으로 처리합니다. 기존 고객·다른 여행·공용 장소·DB 표 전체 삭제는 범위 밖입니다. 알림 발송 후 삭제는 이미 나간 외부 발송을 취소하지 못하므로 사전 차단을 대신하지 못합니다.

## 확인하지 않은 범위

- 운영 이미지 교체 후 실제 고객 경로와 운영 브라우저 E2E는 아직 미실행입니다.
- 운영 HTTP 합성 쓰기와 합성 데이터 정리는 미실행이며 안전 전제 미충족입니다.
- 지도·모델 실호출 성능 및 전체 서비스 무결함을 388개 합성 시험으로 보장하지 않습니다.
- 기존 운영 web 정적 산출물은 대기 상태·명시 재개 토큰 전송 지원이 확인되지 않았습니다. 기존 request_id/message 방식의 암묵 재개는 후보의 실제 HTTP 시험으로 검증했으나 운영 web과 동일한 브라우저 동작이라고 부르지 않습니다.

문서 최종 보완 전 사본: [백업](./_backup/2026-10-12_0026_before_final_image_tag/2026-10-12_0023_plugin_v9_linux_release_preparation.md). 운영 절차의 실제 명령·인프라 값은 git 밖 비공개 실행계획에만 보존했습니다. 승인 후 실행 범위는 API·worker 이미지 교체·재기동, 읽기 전용 확인, 실패 시 두 이미지 동시 복원으로 한정합니다.

운영 구성 전제 보완 전 문서 사본: [백업](./_backup/2026-10-12_0033_before_compose_precondition_results/2026-10-12_0023_plugin_v9_linux_release_preparation.md). 추가 제품 소스 수정·재빌드는 하지 않았습니다.
