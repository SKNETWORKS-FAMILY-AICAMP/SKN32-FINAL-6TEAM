# Composer 적용 → customer-runtime 반영 계약 설계 검토

검토 기준: 2026-08-19 로컬 프로세스·컨테이너 분리 상태. 이 문서는 코드 변경안이 아니라, 현재 코드가 보장하는 사실과 반영 계약의 선택지를 검토한 기록이다. AWS의 ALB, ECS 등 특정 배포 구현은 전제로 삼지 않는다.

## 1. 지금 코드가 실제로 하는 일

### 1.1 Composer `apply`의 쓰기와 동시성

`acop_composer/service.py:103-113`의 `apply_candidate()`는 후보를 검증한 뒤 `base_revision`과 현재 파일의 revision이 다르면 `RevisionConflict`를 발생시킨다. 잠금 안에서 현재 설정을 읽고 비교하는 부분은 `acop_composer/service.py:114-123`이다. 후보를 임시 파일에 완성한 뒤 `os.replace(staged, target)`으로 교체하므로, 대상 파일은 반쪽 YAML이 아니라 교체 전 또는 교체 후 상태가 된다(`acop_composer/service.py:124-142`). 다만 `_WRITE_LOCK`은 프로세스 내부 `threading.Lock`일 뿐이고 여러 인스턴스·워커를 잠그지 않는다는 사실도 같은 파일의 `38-41`에 명시돼 있다.

HTTP `POST /composer/apply`는 위 작업이 끝난 뒤 감사 이벤트를 append하고, 성공 응답은 `{"revision": applied.revision, "applied": true}`뿐이다(`acop_composer/api.py:92-118`). 따라서 현재 `applied: true`는 “Composer가 자신이 바라보는 대상 파일을 교체했다”는 뜻이지, customer-runtime이 그 revision을 로드했다는 뜻은 아니다. 감사 기록 실패 시에는 파일 적용 후에도 500을 반환할 수 있다는 별도 비원자성도 있다(`acop_composer/api.py:107-117`).

### 1.2 canonical loader와 mtime 캐시

설정 내용의 revision은 파일 mtime이나 git commit이 아니라 정규화한 선언 내용의 SHA-256 앞 12자리로 계산된다(`acop_basement/core/project_config.py:76-91`). 파일을 읽을 때 `ProjectConfig.model_validate()` 후 `compute_revision()`을 실행한다(`acop_basement/core/project_config.py:114-126`).

`load_project_config()`는 파일의 `st_mtime_ns`를 구해 `_cached_load(path, mtime_ns)`에 넘긴다(`acop_basement/core/project_config.py:181-194`). 그러므로 같은 프로세스가 같은 경로를 다시 호출하면 mtime이 바뀐 뒤에는 새 cache key로 읽게 된다. 이것은 “다음 호출부터 새 값을 읽는다”는 의미이지, 파일 변경만으로 기존 객체나 기존 조립을 교체한다는 의미는 아니다. 파일이 사라지거나 잘못되면 `ProjectConfigError`를 내며 기본값으로 축소하지 않는다(`acop_basement/core/project_config.py:186-194`).

### 1.3 customer-runtime의 조립 시점과 요청 처리

customer-runtime의 실행 대상은 `acop_basement.presentation.api.app:app`이다(`Dockerfile.customer:14-15`, `docker/compose.yml:2-10`). 모듈 import 시 `app = create_app()`가 실행된다(`acop_basement/presentation/api/app.py:19-31`, `75`). `controller`가 주입되지 않은 일반 경로에서는 이 시점에 `composition.build_controller()`를 호출한다(`acop_basement/presentation/api/app.py:26-31`).

`build_controller()`는 한 번의 조립 안에서 설정을 읽고(`app/composition.py:173-180`), 그 동일한 `config` 객체를 `build_registry()`, `build_team_executor()`, `build_broker()`에 전달한다(`app/composition.py:181-192`). 각 함수는 호출될 때 config가 없을 경우에만 `load_project_config()`를 다시 부르지만, controller 조립 경로에서는 이미 읽은 객체를 전달받는다(`app/composition.py:111-116`, `143-151`, `154-170`). 즉 현재 런타임은 요청마다 네 builder를 다시 호출하지 않는다. 조립된 `controller`와 `classifier`는 router 생성 시 캡처된다(`acop_basement/presentation/api/app.py:32-36`); 실제 요청에서 `controller.run_case()`와 `controller.resume()`를 사용하는 코드도 `acop_basement/presentation/api/cases.py:72-75`, `111-112`, `144-149`에 있다. 따라서 `lru_cache`의 mtime 갱신만으로 이미 떠 있는 customer-runtime의 Team registry, executor, broker, controller가 바뀌지는 않는다.

`mount_ui(app)`가 별도로 설정을 읽는 것은 앱 구성 시점뿐이다(`acop_basement/presentation/ui/__init__.py:27-35`). 이것도 요청마다 runtime 조립을 갱신하는 경로가 아니다.

### 1.4 현재 두 컨테이너의 파일 경계

현재 Compose는 `app-customer`를 `Dockerfile.customer`로, `app-admin`을 `Dockerfile`로 별도 빌드·기동한다(`docker/compose.yml:1-10`, `17-31`). 두 Dockerfile은 각각 자신의 이미지에 `config/`를 COPY한다(`Dockerfile.customer:8-10`, `Dockerfile:8-11`). Compose에서 두 서비스가 공유하는 것은 DB뿐이며, 설정 파일용 공유 volume이나 설정 저장소는 선언돼 있지 않다(`docker/compose.yml:33-57`). 따라서 현재 형태에서 admin 컨테이너 안의 `config/project.yaml`을 `apply`해도 customer 컨테이너의 파일은 바뀌지 않는다. 이 사실 때문에 “mtime 폴링”과 “재기동” 모두 설정 전달 경로가 먼저 있어야 한다.

`/introspection`은 현재 런타임이 자기 조립 상태를 내는 표면이다(`acop_basement/presentation/api/app.py:58-65`). `snapshot()`은 설정을 읽고 조립한 `config.revision`을 `config_revision`으로 반환한다(`acop_basement/introspection/contract.py:36-62`). 다만 `snapshot()`도 요청 시 `load_project_config()` 및 registry/executor builder를 다시 호출하는 관찰용 경로일 뿐(`acop_basement/introspection/contract.py:47-53`), 실제 요청 처리에 쓰는 이미 조립된 controller를 교체하지 않는다.

## 2. 후보 3종 비교

아래 표의 “정확도”는 현재 코드 그대로의 정확도가 아니라, 설정 전달 경로와 런타임 조립 교체를 추가했을 때의 계약상 정확도까지 구분한 것이다.

| 후보 | 정확도 | 지연 | 추가 복잡도 | 실패 시 동작 | 현재 구조에서의 판정 |
|---|---|---|---|---|---|
| 1. customer-runtime 폴링 | 파일이 customer-runtime이 실제로 읽는 동일한 저장소에 있고, 변경 감지 후 전체 composition을 새로 만들어 성공한 경우에만 정확하다. `load_project_config()`를 주기적으로 호출하는 것만으로는 기존 controller가 바뀌지 않는다. | 주기 `N`초라면 보통 0~`N`초 + 재조립 시간. | 백그라운드 감시, 동일 설정 저장소/volume, revision별 atomic swap, 재조립 실패 시 기존 런타임 보존 또는 프로세스 비정상 상태 표시, 다중 인스턴스 일관성까지 필요하다. 현재 mtime cache는 호출 시 새 값을 읽게 해 주지만 폴링 루프나 재조립 기능은 제공하지 않는다(`acop_basement/core/project_config.py:181-194`, `app/composition.py:173-192`). | 새 설정 파싱·조립 실패를 명확히 기록하고 active revision을 옛 revision으로 표시해야 한다. 조용히 옛 controller를 계속 쓰면 실패가 은폐된다. | 현재 Compose에서는 admin과 customer가 별도 이미지의 파일을 가지므로 그대로는 동작하지 않는다(`Dockerfile.customer:8-10`, `Dockerfile:8-11`, `docker/compose.yml:2-31`). |
| 2. admin-triggered 신호 | `apply` 성공 후 target runtime에 revision을 지정해 reload를 요청하고, runtime이 검증·재조립한 뒤 active revision을 반환할 때 가장 빠르고 명시적이다. 단순 HTTP 호출만 추가하고 재조립 결과를 확인하지 않으면 정확하지 않다. | 정상 시 apply 후 왕복 시간 + 재조립 시간. 신호 전송 실패나 runtime unavailable이면 즉시 알 수 있다. | 내부 전용 reload API 또는 프로세스 신호, 인증·권한, 네트워크 경계, timeout/retry/idempotency, 동시 reload 직렬화, 현재/desired revision 상태가 필요하다. 현재 `create_app()`에는 reload route가 없고(`acop_basement/presentation/api/app.py:55-73`), Composer 인증도 현재는 Composer API 자체의 JWT scope 보호에 한정된다(`acop_composer/auth.py:53-77`). | apply와 reload는 서로 다른 실패 지점이다. apply 후 신호 실패를 500 또는 `pending`으로 명확히 반환하고, 재조회로 확인 가능해야 한다. runtime이 새 조립에 실패하면 옛 active revision을 유지하되 상태를 `reload_failed`로 공개해야 한다. | 별도 컨테이너에서도 내부 HTTP라면 구현 가능하지만, 현재는 공유 설정 경로와 reload 계약이 없다. 프로세스 신호는 컨테이너 간 일반 해법이 아니다. |
| 3. 재기동 요구 | 재기동이 실제로 읽을 동일한 최신 설정 artifact/store를 갖는다는 전제에서 정확하다. 현재처럼 두 컨테이너에 config가 이미지로 복사된 상태에서는 admin apply 후 customer 재기동만으로는 반영되지 않는다. | 수동/자동 재기동을 시작할 때까지 지연. 반영 시점이 예측 가능하다. | reload 로직은 없지만, 설정 배포 artifact 또는 공유 저장소, 재기동 절차, desired/active revision 확인 방법, apply 응답의 명시적 안내가 필요하다. | 반영 전에는 old active revision을 계속 사용한다. 이를 정상처럼 숨기지 말고 apply 결과를 `runtime not reloaded`로 드러내며 운영자가 확인·재기동해야 한다. | 현재 단계에서 가장 작은 운영 계약이지만, “재기동하면 된다”는 문구만으로는 부족하다. 설정 전달 경로를 함께 정의해야 한다. |

### 후보 1의 `lru_cache` 활용 판단

mtime 기반 cache key는 파일을 읽는 호출의 중복을 줄이고, 변경 이후 호출에서 새 `ProjectConfig`를 얻는 데는 활용할 수 있다(`acop_basement/core/project_config.py:181-194`). 그러나 현재 runtime은 기동 시 controller를 조립하고 그 객체를 router가 계속 사용한다(`acop_basement/presentation/api/app.py:26-36`, `app/composition.py:173-192`). 따라서 폴링은 cache를 우회하는 별도 raw-file 감시만을 뜻하지 않는다. 감지 후 새 config로 registry/executor/broker/controller를 다시 만들고 요청 경계에서 원자적으로 교체하는 별도 설계가 필수다. 단순히 `load_project_config()`를 부르는 루프를 추가하는 것은 반영 계약이 아니다.

## 3. 반영 상태를 조용히 감추지 않는 방법

현재 `/introspection`은 이미 `config_revision`을 내보내므로, customer-runtime이 실제로 어떤 설정을 관찰하는지 확인하는 기반은 있다(`acop_basement/presentation/api/app.py:63-65`, `acop_basement/introspection/contract.py:59-72`). 그러나 현재 구현의 `snapshot()`은 매 요청마다 파일을 읽고 새 registry/executor를 만들어 관찰 결과를 계산한다(`acop_basement/introspection/contract.py:47-53`). 이 값만으로는 “실제 case 요청을 처리 중인 controller의 active revision”을 증명할 수 없다. 또한 `/health`는 현재 `{"status": "ok"}`만 반환한다(`acop_basement/presentation/api/app.py:55-56`).

따라서 이번 계약에는 다음 상태를 구분해 노출해야 한다.

- `desired_revision`: Composer가 적용한 중앙/공유 설정의 revision. 현재 `POST /composer/apply` 응답의 revision은 Composer가 적용한 값일 뿐이다(`acop_composer/api.py:107-118`).
- `active_revision`: customer-runtime이 현재 요청 처리에 사용하는 composition이 성공적으로 조립된 revision.
- `reload_state`: 최소 `active`, `pending_restart` 또는 `pending_reload`, `reload_failed`처럼 반영 여부를 나타내는 명시적 상태.
- 실패 시 `error` 또는 마지막 실패 시각·대상 revision. 값을 생략하지 말아야 한다는 introspection의 기존 원칙과도 맞는다(`acop_basement/introspection/contract.py:38-43`).

후보 3을 채택하는 동안에는 최소한 `/introspection` 또는 별도 운영 확인 표면이 `active_revision`과 `pending_restart`를 제공하고, apply 성공 응답 또는 운영 기록에 “customer-runtime은 아직 반영되지 않음”을 포함해야 한다. 후보 1·2를 나중에 채택할 때에는 reload 완료 응답의 revision이 `active_revision`과 일치하는지까지 확인해야 한다. 불일치인데 HTTP 200과 `status: ok`만 보이는 상태는 허용하지 않는다.

revision의 비교값으로 mtime을 외부 계약에 쓰면 안 된다. mtime은 loader cache key일 뿐이고, 실제 구성 동일성은 `ProjectConfig.compute_revision()`의 내용 기반 값이다(`acop_basement/core/project_config.py:83-91`).

## 4. 반대 의견과 위험

지금 폴링 또는 reload API를 만들지 않는 편이 나은 이유는 실제 배포 운영 경계가 아직 관찰되지 않았기 때문이다. 현재 문서도 AWS 분리와 customer-runtime 반영 방법을 미정의로 남겼고(`docs/plans/2026-08-18_Composer_배포_경계_분리_계획.md:120-125`), Docker 검증도 정적 확인까지만 했다고 기록한다(`docs/plans/2026-08-18_Composer_배포_경계_분리_계획.md:103-118`). 운영에서 설정 파일을 shared volume으로 둘지, 관리 API가 별도 control plane을 통해 배포할지, 재기동을 누가 수행할지는 아직 이 저장소의 사실이 아니다.

추측성 자동화의 위험은 다음과 같다.

- admin의 파일을 customer가 보지 못하는 현재 Compose 구조에서 폴링을 구현하면, 감시는 정상 동작해도 영원히 변경을 관찰하지 못한다.
- reload 도중 일부 요청은 옛 registry, 일부 요청은 새 registry를 보게 되면 요청 단위 일관성이 깨질 수 있다. 새 composition의 모든 builder가 성공한 뒤에만 교체해야 한다.
- admin이 apply 후 customer에 신호를 보냈다고만 기록하면, 네트워크 단절·인증 실패·재조립 실패를 “적용 성공” 뒤에 숨길 수 있다.
- 재기동을 자동화하지 않은 채 `apply`를 성공으로만 표시하면, customer-runtime이 옛 설정으로 계속 처리하는 상태가 정상처럼 보인다.
- `snapshot()`이 자체적으로 config를 다시 읽는다는 사실을 active runtime의 증명으로 오해하면 안 된다. 관찰용 재조립 결과와 실제 요청 경로의 composition을 분리해 확인해야 한다.

반대 의견을 반영하면, 지금은 자동 반영 메커니즘을 운영 계약으로 확정하기보다 “적용된 desired revision과 실행 중 active revision이 다를 수 있으며, 그 상태를 숨기지 않는다”는 계약부터 확정하는 편이 안전하다. 실제 배포 대상과 설정 전달 경로가 정해지면 후보 1·2 중 하나를 선택해 실측할 수 있다.

## 5. 권고

### 결론

지금은 후보 3, 즉 **재기동/재배포 요구를 명시하는 계약만 채택하고 후보 1(폴링)과 후보 2(admin-triggered reload)는 보류**한다. 다만 현재 Compose의 독립 파일을 그대로 둔 채 “customer-runtime을 재기동하면 admin의 apply가 반영된다”고 쓰지는 않는다. 재기동 전에 customer가 읽을 설정 artifact/store를 동일한 최신 revision으로 배포하는 절차가 함께 있어야 한다.

### 지금 채택할 최소 범위

1. `apply`의 의미를 “Composer가 대상 설정을 원자적으로 교체하고 revision을 확정함”으로 한정한다. customer-runtime 반영 완료를 의미하지 않는다고 문서화한다. 원자 교체와 base revision 검사는 이미 `acop_composer/service.py:103-142`에 있다.
2. apply 성공 결과와 운영 확인 표면에 `desired_revision`, `active_revision`, `pending_restart`를 구분해 표시한다. 현재 `/health`는 status만 내고(`acop_basement/presentation/api/app.py:55-56`), introspection에는 `config_revision`만 있으므로(`acop_basement/introspection/contract.py:59-62`) active/desired 의미를 추가로 계약화해야 한다.
3. 재기동/재배포 절차는 “customer-runtime이 최신 설정 artifact를 읽은 뒤 기동하고, 기동 후 active revision을 확인한다”로 정의한다. 현재처럼 이미지별 `config/` COPY인 경우에는 admin 컨테이너 파일을 customer가 자동으로 읽지 못한다는 제한을 절차에 명시한다(`Dockerfile.customer:8-10`, `Dockerfile:8-11`).
4. 설정 파싱·조립 실패는 fail-fast로 남긴다. loader가 파일 부재·스키마 오류를 `ProjectConfigError`로 내는 현재 성격을 유지하고(`acop_basement/core/project_config.py:114-130`), 옛 active revision을 새 revision인 것처럼 표시하지 않는다.

### 후보 1·2를 재검토할 트리거

- 실제 배포에서 customer와 Composer가 동일한 durable config store 또는 명시적 config artifact 전달 경로를 사용하기로 결정된 때.
- customer-runtime을 재기동하지 않고도 설정 변경을 반영해야 한다는 SLO/운영 요구가 생긴 때.
- 단일 인스턴스가 아닌 여러 runtime 인스턴스의 active revision을 모두 확인·수렴시킬 필요가 생긴 때.
- reload 실패, 동시 apply, 요청 중 composition 교체를 포함한 운영 실측 시나리오와 검증 환경이 마련된 때.

그때의 선택 기준은 다음과 같다. 반영 지연을 수초 수준으로 허용하고 runtime이 동일한 설정 저장소를 읽을 수 있으면 폴링을 검토한다. 즉시 반영과 apply 후 결과 확인이 필요하고 내부 네트워크·인증 경계를 운영할 수 있으면 admin-triggered reload를 검토한다. 어느 경우든 `active_revision` 확인 없이는 성공으로 간주하지 않는다.
