동일 운영 이미지의 일회용 격리 컨테이너에서 최종 후보의 합성 기능 시험 175개가 모두 통과했습니다. 기존 운영 앱·DB·파일에는 연결하거나 변경하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| Registry·구성·HTTP 기능 | Linux 통과 | 108/108 = 100% |
| worker·읽기·오류 전파 | Linux 통과 | 67/67 = 100% |
| 최종 후보 해시 보존 | 일치 | 50/50 = 100% |
| 운영 기준 사본 보존 | 일치 | 404/404 = 100% |

작성: 2026-10-11T22:45:59.684455+09:00

## 실행한 범위

실제 운영 API와 같은 이미지 ID를 사용했지만, 기존 컨테이너 안에서 pytest를 실행하지 않았습니다. 새 일회용 컨테이너를 만들어 명시한 공개 코드·설정·시험 파일만 stdin으로 전달했습니다. 운영 사본 404개와 후보 변경 50개를 결합한 제품 소스는 두 실행 모두 동일합니다. 첫 묶음은 시험 보조 파일을 합쳐 419개, 둘째 묶음은 423개 파일의 SHA256을 컨테이너 안에서 모두 검증한 뒤 실행했습니다. 환경 파일·DB 데이터·키 파일은 payload에 없습니다.

Linux Python 3.12.15, 기존 이미지에 이미 설치된 pytest·의존성을 사용했습니다. 이미지 빌드·패키지 설치·코드 수정은 하지 않았습니다. 최종 v5 원보고서·후보·운영 사본을 덮어쓰지 않았습니다.

| 합성 시험 | 첫 묶음 | 둘째 묶음 |
|---|---|---|
| Registry·A2A 가용성 | 45/45 | — |
| 고정 구성·교체·문맥 복원 | 27/27 | — |
| 실제 HTTP 입구 가용성 | 36/36 | — |
| worker 초기화·다음 회차·격리 | — | 26/26 |
| 담당 불가 오류의 중첩 전파 | — | 9/9 |
| 읽기 입구·미설치 구현 import 경계 | — | 10/10 |
| 식당 읽기 도구 관문 | — | 22/22 |

분모 175는 서로 겹치지 않는 pytest 항목 108+67개입니다. 첫 실행은 3.46초, 둘째 실행은 1.98초에 통과했고 실패·건너뜀은 없습니다. 첫 실행에 Starlette의 AnyIO 별칭 사용 중단 예고 경고 1건이 있었습니다. 기능 실패는 아니며 의존성 교체 작업으로 확대하지 않았습니다.

모델·외부 제공자·DB 연결은 시험 대역으로 통제했습니다. HTTP 시험은 실제 FastAPI 요청 처리 코드에 TestClient로 접근하며 SQL·지도 계산 진입 호출 여부는 합성 객체가 기록합니다. worker의 pointer 워밍 시험은 실제 캐시·스레드 동작을 쓰되 HTTP 응답 함수만 합성 응답으로 바꿉니다. 읽기 시험은 DB 접근 시 실패하는 객체 또는 호출 기록용 context manager를 사용합니다. 깨끗한 하위 프로세스의 비활성 Team import 차단 시험도 Linux에서 실행했습니다.

## 실제 격리 조건

네트워크 none, 루트 파일 시스템 read-only, 쓰기는 256MiB /tmp tmpfs로 제한했습니다. 운영 볼륨과 환경값을 전달하지 않았고, 프로세스의 상속 환경을 비운 후 합성 설정만 넣었습니다. DB 주소도 연결 불가능한 로컬 1번 포트의 합성 값이며 DB 의존 integration 시험은 선택하지 않았습니다. 이 작업에서는 로컬 DB pytest도 추가 실행하지 않았습니다.

CPU 1개분, 메모리 512MiB(추가 swap 없음), 프로세스 128개로 제한했고 모든 capability를 제거했습니다. 비특권 UID 65534와 no-new-privileges를 사용했습니다. 둘째 실행 안에서 실제 UID·CapEff=0·NoNewPrivs=1·루트 read-only·인터페이스 lo만 존재·cgroup CPU/메모리/pids 상한을 확인하고 assertion으로 검사했습니다.

두 컨테이너는 --rm으로 종료 시 삭제되도록 실행했습니다. 이름을 지정한 둘째 컨테이너는 종료 후 별도 조회에서 잔류 없음도 확인했습니다. 기존 운영 컨테이너를 재시작·재설정하거나 그 파일을 고치지 않았습니다.

- [Linux 검증 JSON](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/candidate-v5-isolated-linux-verification-v1.json) — 시험별 분모·실행 환경·격리 실측·해시 보존 근거입니다.
- [핵심 기능 108개 로그](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/candidate-v5-isolated-linux-v1.log) — Registry·구성·실제 HTTP 처리 결과입니다.
- [worker·경계 67개 로그](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/candidate-v5-isolated-linux-boundaries-v1.log) — 실제 격리 확인과 후속 기능 결과입니다.
- [첫 명시 파일 목록](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/isolated_linux_checks/2026-10-11_224132/payload-manifest.json) — 전달한 419개 파일 해시입니다.
- [둘째 명시 파일 목록](C:/Users/playdata2/Documents/final_workspace/final_project_cs/legacy/isolated_linux_checks/2026-10-11_224400/payload-manifest.json) — 전달한 423개 파일 해시입니다.
- [보존한 v5 원보고서](C:/Users/playdata2/Documents/final_workspace/final_project_cs/wiki/records/reports/2026-10-11_2231_plugin_minimal_candidate_v5.md) — Windows 327개·대상 DB 구조 대조·최소 후보 범위입니다.

## 여전히 구분해야 할 것

이번 결과는 Linux에서 실제 기능 코드가 실행된 합성 unit/HTTP 시험입니다. 운영 데이터가 연결된 새 버전 E2E나 실제 모델·지도 API 성능 검증으로 확대하지 않습니다. 운영 API·worker에 후보를 설치하지 않았으므로 실제 반영은 여전히 미실행입니다. Linux에서 DB가 연결된 대화 재개·단일 일정 변경·운영 worker 설정의 기능 확인은 별도 격리 환경과 반영 절차가 필요합니다.
