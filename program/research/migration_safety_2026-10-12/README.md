# SQL 적용·배포 안전 후속 작업 — 2026-10-12

SQL 묶음의 전체 롤백과 이미지 누락 차단을 로컬에서 수정·검증했습니다. **25개 wiki 검토와 분리한 새 후속 작업**입니다. 이미 삭제된 과거 5표를 다시 삭제하지 않았습니다. 커밋·푸시·x600 서버 배포·실제 업무 DB 변경은 하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 관련 코드·계약 시험 | 통과 | 62/62 = 100% |
| 독립 PostgreSQL 실행 시험 | 통과 | 11/11 = 100% |
| 실제 Docker 배포 | 이번 범위 밖 | 0/1 = 0% |

## 무엇을 고쳤나

1. [SQL 실행기](../../../final_project_cs/app/infrastructure/db/migrate.py)와 [문법 해석기](../../../final_project_cs/app/infrastructure/db/migration_sql.py)는 전체 파일을 먼저 검사합니다. PostgreSQL 문법 해석기 `pglast==7.20`으로 파일을 감싼 옵션 없는 BEGIN/COMMIT만 실행 문자열에서 공백 처리합니다. 디스크 원문·문자열·중첩 주석·달러 인용 함수 본문을 다시 쓰지 않습니다. 중간 커밋·롤백·savepoint·트랜잭션 옵션은 변경 전에 거부합니다. 중첩 호출은 savepoint로 지원하며 최종 커밋은 호출자가 결정합니다.
2. [기본 API Dockerfile](../../../final_project_cs/deploy/Dockerfile.api)은 DB에 연결하지 않고 이미지 자체를 검사합니다. [배포 검사기](../../../final_project_cs/deploy/migration_safe_deploy.py)는 이미지 자체와 Compose 마운트 적용 후 실행기·제외 목록·SQL 해시가 같은지 요구합니다. 오래된 이미지 또는 오래된 마운트가 있으면 DB 적용 전에 멈춥니다. 별도 `-f`로 과거 추가 설정을 빠뜨려도 새 이미지 자체에 안전장치가 들어갑니다. 검사기를 건너뛴 임의의 Docker 명령까지 차단하는 호스트 전역 장치는 아닙니다.
3. [자동 배포 경로](../../../final_project_cs/deploy/auto_deploy.sh)와 [수동 배포 경로](../../../final_project_cs/deploy/server_up.sh)는 실제 실행 중 이미지 ID와 최종 Compose 구성을 먼저 보관합니다. 앱 교체·복구 모두 확인한 ID를 고정하며 빌드·SQL 작업·기동에 시간 제한을 둡니다. 부분 실패·시간 초과·관찰 중 재시작 때 이전 ID로 복구하고 다시 검사합니다. 복구 이미지에는 별도 보관 태그를 붙여 기존 앱 태그 정리가 지우지 못하게 했습니다. DB 컨테이너는 재생성하지 않습니다.

자동 배포의 sparse checkout·변경 감지에는 Dockerfile이 실제로 COPY하는 `knowledge`도 포함했습니다. 이 경로 누락은 코드 대조로 찾은 위험이며 이번에 실제 Docker 빌드 실패로 재현한 원인은 아닙니다.

## 실행 근거와 한계

최종 선택 시험은 [코드·계약 62개](focused-results-v3.xml)와 독립 DB 11개, 합계 73/73입니다. 배포 제어 모의 시험 16개는 앞의 62개에 포함되므로 중복 합산하지 않습니다. [집계](summary.json)는 원본 XML에서 계산했습니다.

[최종 산출물 검사](validation.json)는 이번 문서의 링크·형식·Python 문법·역사 SQL 보존을 확인합니다. 흐름도는 스킬 정적 검사와 별도 임시 Chrome 프로필의 실제 렌더링으로 확인했습니다. [전체 wiki 검사](wiki-check-final.json)의 위반 4건은 다른 공유 작업 문서의 상태값·메타데이터·링크 문제이며 이번 수정 문서의 위반은 0건입니다. 그 문서는 수정하지 않았습니다. 첫 wiki 검사 중 공유 검사기 자체의 일시적 구문 오류가 있었고, 파일이 정상화된 뒤 재시도한 결과를 보관했습니다.

- [독립 DB 결과](db-runtime-result.json), [11개 시험 원본](db-results-v2.xml), [종료 확인](cluster-stop.json): 이번 작업 폴더에서 별도 PostgreSQL 16.15 EE 1.3.13 demo·pgvector 0.8.2를 실행했습니다. 기존 로컬 개발 DB·x600 서버의 cs 프로젝트 DB에 SQL을 실행하지 않았습니다. 무작위 이름의 시험 DB는 모두 정리했고 인스턴스도 종료했습니다. 운영의 PostgreSQL 17 Docker 이미지와 같은 빌드가 아닙니다.
- 실제 DB에서 기존 구현의 `RELEASE SAVEPOINT can only be used in transaction blocks` 오류와 앞선 표의 커밋을 재현했습니다. 새 구현에서는 모든 현재 SQL 뒤 강제 오류, 기존 행 변경, 중첩 성공 뒤 호출자 롤백, 중첩 실패 뒤 호출자 작업 보존, 사전 거부, 빈 DB·데이터 있는 DB의 반복 실행을 확인했습니다. 반복 적용 뒤 여행 표·최종 이유 값·기존 행은 유지되고 정확한 과거 5표 이름은 재생성되지 않았습니다.
- [배포 제어 시험](../../../final_project_cs/tests/unit/core/test_migration_safe_deploy.py)은 상태를 가진 Docker 제어 모의 시험입니다. 실제 Docker Engine·Compose 빌드·앱 기동·x600 서버 장애 복구 시험은 하지 않았습니다. 이 PC의 기본 PATH에 Docker CLI가 없고 WSL도 설치되지 않은 상태로 조회됐습니다. 운영에서 늦게 끝나는 Docker daemon 요청·외부 강제 종료·여러 배포 도구의 경합은 재현하지 않은 위험입니다.
- 표·행 변경의 롤백을 검증했습니다. PostgreSQL sequence 번호 소비나 외부 함수의 별도 부수효과까지 되돌린다는 계약은 아닙니다. 성공한 SQL은 앱 이미지 복구로 되돌리지 않습니다. 파괴적인 SQL에는 별도 복원 계획이 필요합니다.
- 이전 배포에서 다른 태그를 선택했다가 원래 이미지로 복구한 사실은 [기존 배포 기록](../sql_retirement_2026-10-12/deployment-result.json)·[최종 상태](../sql_retirement_2026-10-12/deployment-final.json)에 근거합니다. 긴 대기의 세부 원인은 이번 작업에서 실제 Docker 계측으로 재현하지 않았습니다. 태그와 실행 중 이미지가 다를 때의 잘못된 복구 선택은 모의 시험으로 재현했습니다.

고객 흐름 시험은 하지 않았습니다. API 건강 검사나 컨테이너 실행 상태만으로 여행 접수·판정·알림이 정상이라고 주장하지 않습니다.

## 재실행 명령

cs 프로젝트 폴더에서 다음 시험을 실행합니다. `pglast==7.20`은 [의존성 목록](../../../final_project_cs/requirements.txt)에 추가했습니다. 이번 환경은 전역 설치 대신 이 작업 폴더의 Git 제외 `_deps`를 PYTHONPATH에 넣었습니다.

```powershell
python -m pytest tests/unit/core/test_current_migration_plan.py tests/unit/core/test_migration_atomic_sql.py tests/unit/core/test_migration_safe_deploy.py tests/contract/test_team_contract.py tests/contract/test_core_isolation.py tests/architecture/test_engine_accepts_travel_policies.py -q
```

독립 DB 준비·실행은 워크스페이스 루트의 [다운로드 스크립트](prepare_postgres.py)와 [격리 실행 스크립트](run_isolated_db.py)를 사용했습니다. 바이너리 출처·다운로드 해시는 [목록](runtime-downloads.json)에 있습니다. 새 결과 이름·새 임시 경로를 정해 이전 시험 기록을 백업한 뒤 재실행합니다. 기존 업무 DB 주소로 시험 환경변수를 대체하지 않습니다.

## 배포안 — 검토용, 실행하지 않음

추가 라이브러리는 무료이며 새 계정·키는 0개입니다. 새 API 이미지 1개를 만들어 API·worker가 함께 사용하고 웹은 기존 이미지로 유지하는 방식을 추천합니다. 기존 API·worker의 실행 중 이미지 ID가 다르면 후보 생성기가 중단하므로 각각의 변경을 보존할 별도 후보 검토가 필요합니다. 소요 시간은 이번에 실제 Docker 빌드를 하지 않아 실측하지 않았습니다.

다른 채팅의 미커밋 코드가 섞인 전체 앱 이미지를 바로 배포하지 않습니다. [SQL 안전장치 전용 Dockerfile](../../../final_project_cs/deploy/Dockerfile.migration-safety)은 현재 실행 이미지를 기준으로 Python 파일 3개·실행 계획 1개·문법 해석기 의존성만 추가하며 기존 SQL 파일은 COPY하지 않습니다. 그 이미지의 SQL 해시가 이번 시험 입력과 다르면 해당 이미지로 PostgreSQL 17 격리 시험을 다시 해야 합니다.

아래 명령은 **향후 별도 배포 승인 후** Linux 배포 기계의 기존 Compose 폴더에서 실행할 절차입니다. 접속 명령·실제 경로·계정·키는 공용 문서에 넣지 않습니다. `$source_dir`은 검토한 변경 파일이 있는 cs 소스 폴더, `$helper`는 그 폴더의 배포 검사기 절대 경로, `$safety_state`는 새 비공개 회차 폴더입니다. 예: `state/migration-safety-20261012-01`. 스냅샷 파일에는 환경값이 포함되므로 공개 저장소·공용 보고서에 붙이지 않습니다.

| 단계 | 실행·확인 | 끝나면 보일 것 |
|---|---|---|
| 기존 실행 보관 | 아래 `snapshot` | `baseline.json`, `recovery.compose.json` |
| 후보 빌드 | 기존 API의 전용 보관 태그와 ID가 일치하는지 확인 후 전용 Dockerfile 빌드 | 새 이미지 ID·내장 안전 manifest |
| 후보 파일 준비 | 아래 `prepare` | `candidate.plan.json` — 이전 3파일 마운트만 제거하고 다른 설정·웹 이미지 유지 |
| DB 변경 전 검토 | 아래 `check`, SQL 해시 대조·격리 시험·DB 복구 자료 확인 | 안전 계약·회귀 시험 모두 통과 |
| 승인된 적용 | 아래 `migrate`, `rollout` | 같은 이미지 ID·건강 상태·관찰 중 재시작 없음 |

```sh
python3 "$helper" snapshot --state-dir "$safety_state"
# baseline.json의 tripilot-api.recovery_tag를 base_tag에 읽습니다.
base_tag=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tripilot-api"]["recovery_tag"])' "$safety_state/baseline.json")
base_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tripilot-api"]["image"])' "$safety_state/baseline.json")
test "$(docker image inspect --format '{{.Id}}' "$base_tag")" = "$base_id"
docker build --pull=false --build-arg "BASE_IMAGE=$base_tag" -f "$source_dir/deploy/Dockerfile.migration-safety" -t tripilot-api:migration-safety-20261012 "$source_dir"
api_image_id=$(docker image inspect --format '{{.Id}}' tripilot-api:migration-safety-20261012)
python3 "$helper" prepare --state-dir "$safety_state" --api-image "$api_image_id"
candidate="$safety_state/candidate.plan.json"
python3 "$helper" check --state-dir "$safety_state" -f "$candidate"
```

`candidate.plan.json`과 `recovery.compose.json`을 비공개로 대조합니다. 기존 코드 3파일 마운트 제거·API/worker 이미지 ID 변경 이외의 변경이 없는지 확인합니다. 후보 이미지를 직접 읽는 manifest와 Compose로 읽는 manifest가 같아야 합니다. 이미지 manifest의 `historical`은 정확한 4파일, `current_count`는 기대 입력 수, SQL SHA-256은 시험한 입력과 같아야 합니다. 이 명령은 DB에 연결하지 않습니다. 후보 이미지의 PostgreSQL 17 격리 회귀와 DB 백업·복원 확인을 마친 후에만 다음 단계로 갑니다.

```sh
python3 "$helper" migrate --state-dir "$safety_state" -f "$candidate" --timeout 180
python3 "$helper" rollout --state-dir "$safety_state" -f "$candidate" --timeout 240 --settle 30
```

| 실패 | 처리 | 확인할 결과 |
|---|---|---|
| 구성 hash 불일치 | 앱 변경 전 중단, 현재 파일과 실행 구성 대조 | 현재 구성을 보존할 수 있을 때 새 회차 시작 |
| native safety import 실패 | 오래된 이미지·누락 의존성, 새 이미지 재빌드 | 이미지 자체 `check` 통과 |
| Compose manifest 불일치 | 오래된 마운트가 이미지 코드를 덮음, 후보 파일 대조 | 내장 파일과 마운트 후 파일 해시 동일 |
| SQL 시간 초과·실패 | 이름을 붙인 SQL 작업 컨테이너 정리, 자동 재시도 금지 | 업무 DB 적용 결과 확인 후 재개 판단 |
| 앱 부분 실패·시간 초과·재시작 | 저장한 ID와 구성으로 자동 복구 후 검사 | `exact-image recovery verified` — 앱 복구이며 SQL 역적용 아님 |
| 복구도 실패 | 자동 성공 처리 금지, 비공개 실행 로그로 수동 대응 | 모든 앱의 이전 ID·건강·재시작 관찰을 직접 확인 |

수동 복구 명령은 `python3 "$helper" recover --state-dir "$safety_state" --timeout 240 --settle 30`입니다. 후보·복구 모두 앱 3개만 바꾸고 DB 컨테이너·볼륨은 삭제·재생성하지 않습니다. 명령 결과가 불확실하면 반복 실행으로 성공을 추정하지 않습니다. systemd의 강제 kill·전원 차단처럼 복구 코드를 실행할 기회가 없는 경우에는 이 수동 절차가 필요합니다.

배포가 성공하면 기본 Compose에도 검토한 후보 설정을 승격하고, 새 안전 검사기를 사용하는 배포 스크립트를 설치한 뒤 자동 배포를 재개합니다. 기존 3파일 마운트가 남은 옛 기본 구성으로 다시 기동하지 않도록 최종 `docker compose config`와 API/worker 내장 manifest를 재확인합니다. 이미지·마운트·건강 확인 후 별도 시험 여행의 접수→판정→계획 링크→알림을 실행해 고객 흐름을 확인합니다. 이번 작업은 여기까지 실행하지 않았습니다.

## 보존·백업

[수정 전 파일 백업 목록](backups.json)과 [추가 시험 파일 백업](../../../final_project_cs/tests/integration/db/_backup/2026-10-12_migration_safety/)을 보관했습니다. [중간 산출물 백업](_backup/)도 남겼습니다. [SQL 시작 해시](sql-before.json)·[최종 보존 검사](source-validation.json)를 대조합니다. 역사 보존 4파일은 시작 바이트가 유지됩니다. 작업 도중 다른 공유 변경으로 식당 SQL 한 파일의 해시가 달라져 되돌리지 않고 별도로 기록했습니다. 이 작업에서는 SQL 파일을 쓰지 않았습니다.

초기 실행의 단위 시험 임시 폴더 오류(15 통과·3 오류), 배포 검사 코드의 파일 열기 오류(4 통과·8 실패), 기존 로컬 개발 DB 연결 시간 초과(10 건너뜀)는 원본 XML에 보존했습니다. 고친 뒤 새 이름의 결과를 생성했고 실패·건너뜀을 이전 실행에서 지우지 않았습니다. 최종 실행 분모와 과거 시도 분모를 섞지 않습니다.

## 외부 근거

[pglast API](https://pglast.readthedocs.io/en/v7/api.html)의 PostgreSQL 구문 트리·토큰 위치를 사용합니다. [PostgreSQL의 문자열·중첩 주석 규칙](https://www.postgresql.org/docs/16/sql-syntax-lexical.html)을 단순 정규식으로 대체하지 않습니다. [Compose config](https://docs.docker.com/reference/cli/docker/compose/config/)의 최종 구성·hash 출력과 [Compose up](https://docs.docker.com/reference/cli/docker/compose/up/)의 wait·pull·no-deps 옵션을 사용합니다. 실제 설치된 Compose 버전의 옵션 호환성과 hash는 배포 전 검사에서 확인해야 합니다.
