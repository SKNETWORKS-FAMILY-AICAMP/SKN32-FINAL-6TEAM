# Composer 쓰기 채널 계약

★2026-08-29 정정 — **v3(토글 전용)는 "전체 대체 계약"이 아니다.** 2026-08-19에
이 문서가 v3를 "채택 확정된 목표 계약"이라고 적었으나, 그 뒤 사용자 요구가
"등록된 항목을 켜고 끄기"보다 넓다는 것이 확인됐다 — 운영 화면에서 Team·모듈
**인스턴스를 이름과 설정만 입력해 만들고 지우는 것**이 실제 요구다
(`program/plan/A-COP_Composer_범위재검토.md`, Codex 교차검증). 토글만으로는
그 요구를 충족할 수 없다.

지금 이 저장소의 계약 지형은 셋이다.

| 계약 | 지위 | 엔드포인트 |
|---|---|---|
| **카탈로그 기반 CRUD** | ★**정본 관리 계약**(2026-08-28 구현) | `GET /composer/catalog`, `POST /composer/changes` |
| 토글 | 보조 명령. v3 §2.2 이름 그대로, 저장 경로는 CRUD 와 공유 | `POST /composer/toggle` |
| v2 전체 선언 적용 | 호환·bulk migration 경로. 제거하지 않는다 | `GET /composer/current`, `POST /composer/validate`, `POST /composer/apply` |

셋 다 **같은** 저장·revision·감사 경로를 쓴다(`acop_composer.service` 의
`_WRITE_LOCK` → 임시파일 → `os.replace()`). 같은 일을 하는 코드를 두 벌
만들지 않는다.

아래 §0(v3 원문)은 **UI·cs 가 부를 엔드포인트 이름과 payload 를 맞추기 위한
계약 사본**으로 계속 유효하다. 다만 "이것이 Composer 전체를 대체한다"는 지위만
철회한다. `acop_composer.service`(`read_current`/`validate_candidate`/
`apply_candidate`)가 `config/project.yaml`(또는 주입된 대체 경로)을 검증·저장하는
v2의 **유일한** 통로다. `GET /composer/current`, `POST /composer/validate`,
`POST /composer/apply`(`acop_composer.api`)가 이 서비스를 HTTP로 노출하고,
`acop_composer.auth`가 `/auth/token`을 담당한다(2026-08-19 이전엔 이 경로가
`app.composer_staging.composer_service` 등 다른 위치에 있었다 — 지금은 전부
`acop_composer` 패키지 안에 있다, `docs/handoff/15`).

## §0. v3 토글 계약 (엔드포인트 이름·payload 계약. sample 구현 완료)

아래는 `program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md` §2 를 그대로
옮긴 **계약 원문**이다 — cs 와 `final_project_ui` 가 각자 구현할 때 어긋나지
않도록 여기 한 곳에 canonical 사본을 둔다. 이 절 자체를 수정하려면 원본 설계
문서를 먼저 고치고 여기에 반영한다 — 반대 방향(여기를 먼저 고치는 것)은
하지 않는다.

★**구현 상태(2026-08-29)**: `POST /composer/toggle` 은 sample 에 구현돼 있다
(`acop_composer/api.py`). `/changes` 의 `enable`/`disable` 과 **같은 저장·
revision·감사 경로**를 공유하고, 감사 이벤트만 `composer.toggle` 로 구분된다.
응답에는 v3 가 정한 필드에 더해 `activation_state` 를 함께 낸다 — 저장됐다고
이미 떠 있는 런타임이 그 설정으로 도는 것이 아니기 때문이다(아래 "배포 경계"
절 참고).

★소유권: 2026-08-28 에 `A-COP_Composer_소유권_정정.md` 와
`final_project_ui/CLAUDE.md` §0.3 이 정정됐다 — **sample 이 UI 가 가져다 쓸
Composer 판단·요청 로직을 만든다.** 이전 판의 "sample 은 이 설계의 구현
대상이 아니다" 는 더 이상 유효하지 않다.

**책임 분배**(원문 §3):

| 프로젝트 | v3 책임 | 하지 않는 것 |
|---|---|---|
| `final_project_ui` | 등록 ID·현재 상태를 introspection에서 읽고, 화면에서 판단하며, 최소 토글 요청을 인증해 전송 | Core 계약 모델 import·복제, 대상 파일 직접 쓰기, 대상 Python import |
| `final_project_cs`(릴리즈 대상) | 등록 ID 확인 → flag 원자적 변경 → 감사 로그를 수행하는 최소 endpoint만 보유하거나 향후 제거 | Composer 화면·판단 로직·전체 선언 검증·Composer 관련 공용 파일 보유 |
| `final_project_sample` | pip 배포용 basement 소스, Team 모듈 예제 라이브러리(`examples/`), **그리고 UI가 가져다 쓸 Composer 판단·요청 로직**을 만든다 | 대상 제품의 Team 도메인 구현 |

### 대상이 제공하는 것 (introspection 확장)

기존 read-only introspection 응답을 확장해 등록 항목의 ID와 현재 상태를 낸다.

```json
{
  "contract_version": "introspection.v3",
  "config_revision": "<content-hash>",
  "registered_ids": {
    "modules": ["vector_rag", "graph_store", "a2a_executor", "mcp", "voc", "ops_ui"],
    "teams": ["order_shipping", "return_exchange"],
    "ports": ["team_executor", "message_broker", "graph_store"]
  },
  "modules": {"vector_rag": {"enabled": true}},
  "teams": {"order_shipping": {"active": true}},
  "ports": {"team_executor": {"active": true}}
}
```

### UI가 보내는 요청 — `POST /composer/toggle`

```json
{
  "target_type": "module",
  "target_id": "vector_rag",
  "active": false,
  "base_revision": "<config_revision>",
  "reason": "운영 점검 중 임시 비활성화"
}
```

`target_type`은 `module`·`team`·`port` 중 하나이고 `target_id`는 응답의
`registered_ids`에 있어야 한다. 인증은 읽기는 기존 introspection/Composer
read scope, 쓰기는 `composer:write`를 재사용한다.

### 대상이 처리하는 것 (4단계로 한정)

1. `target_type`·`target_id`를 현재 등록 목록과 대조 — 없으면 거부(422).
2. `base_revision`이 현재 `config_revision`과 다르면 `409 revision_conflict`.
3. 해당 등록 항목의 flag만 원자적으로 바꾼다. 전체 `ProjectConfig`를 재구성
   하지 않는다. 기존 v2의 `os.replace()`·백업 안전장치를 재사용한다.
4. 요청자·대상 종류·대상 ID·이전/새 상태·revision·사유·결과를 append-only
   감사 로그(v2와 같은 `var/audit/composer_events.jsonl` 형식 재사용)에 남긴다.

성공 응답: `{"target_type": "...", "target_id": "...", "active": bool,
"config_revision": "<new-hash>", "audit_id": "..."}`.

### 명시적으로 안 되는 것

새 `implementation_ref` 임의 제출·registry 등록, 등록 목록 자체의 추가/삭제,
`ProjectConfig`/`TeamManifest`/`ContextPack` 구조 변경, 전체 선언 덮어쓰기,
UI의 대상 검증 모델 복제. 이 작업들은 코드/배포 변경이 필요한 별도 작업이며
v3 토글의 범위가 아니다.

### 실행 순서 (원문 §6, 진행 상태 2026-08-29)

1. ~~대상 endpoint 계약을 확정한다~~ — 완료(2026-08-19).
2. introspection 응답에 `registered_ids` 확장 — **미착수.** cs 의
   `app/introspection/contract.py` 가 `contract_version`·`config_revision`·
   `modules`·`ports`·`teams` 는 내지만 `registered_ids` 는 없다(2026-08-24
   실측). sample 은 카탈로그를 `GET /composer/catalog` 로 따로 낸다 — 두
   경로를 하나로 맞출지는 UI 착수 때 정한다.
3. `final_project_cs` 에 최소 endpoint 구현 — **cs 에는 이미 독자 구현이
   있다**(`app/presentation/api/composer.py`, `/toggle` 포함). 다만 sample
   패키지를 pip 로 쓰는 것이 아니라 v2 계약을 따로 재구현한 포크다
   (2026-08-24 실측). 통합 여부는 별도 결정 사항.
4. `final_project_ui` 에 토글 화면·판단·요청 어댑터 구현 — **미착수.**
   호출할 서버 쪽은 sample 에 준비됐다(`/catalog`·`/changes`·`/toggle`).
5~8. 기존 v2 Composer 화면/코드 정리, 릴리즈 대상에서 물리적 제거 확인,
   최종 명명 대조 — 미착수. ★단 v2 엔드포인트 자체는 **제거하지 않기로**
   정리됐다(문서 상단 표) — bulk migration 경로로 남긴다.

---

## v2 — 전체 선언 검증·적용 계약 (지금 실제로 도는 것)

★왜 필요한가 — `/ui/composer` HTML 폼은 `composer_ui` 모듈로 끌 수 있다(릴리스 시
끈다, [[12_introspection_계약]]이 설명하는 것과 같은 이유로 개발자 전용 화면이다).
그런데 Composer는 basement에 남는 **유일한 쓰기 기능**이다 — `final_project_ui`
는 read-only 원칙을 지키므로 대상 저장소 파일을 직접 못 쓴다. 릴리스 이후에도
외부 개발 콘솔이 모듈을 켜고 끄려면 HTML 페이지와 무관하게 사는 쓰기 채널이 있어야
한다. 이 세 엔드포인트는 **`composer_ui` 토글과 무관하게 항상 등록된다**.

Codex 교차검증(`docs/reports/2026-08-17_S-COMPOSER-WRITE-CHANNEL_검토.md`)이
지적한 고정 임시 파일명 충돌, revision 확인 누락, 비원자적 교체 문제는
`composer_service.py`에서 고쳤다. 이 계약 v2에서는 릴리스 후 콘솔 연결을 전제로
인증 계층, 세분화된 scope, 영속 audit, 구현체 allowlist까지 확정한다.

## 인증과 신뢰 경계

### 계층 1 — 사설망(VPN/SSH 터널) 접근

`final_project_ui`와 대상 제품의 Composer API는 사설망 안에서만 통신한다.
공개 인터넷에 이 API를 노출하지 않는다. VPN/SSH 터널은 필요한 네트워크 경계이지
인증 자체를 대체하지 않는다.

### 계층 2 — 실행 시 발급하는 단명 토큰

모든 Composer 요청은 `Authorization: Bearer <token>`을 요구한다. 토큰은 고정 API
키가 아니라 15~60분 TTL의 서명된 JWT이며, 최소한 다음 claim을 가진다.

```json
{"sub": "final_project_ui", "aud": "final_project_sample",
 "scope": ["composer:read", "composer:validate"],
 "iat": 0, "exp": 0, "jti": "..."}
```

`final_project_ui`는 연결할 때마다 `/auth/token` 발급 절차를 통해 새 토큰을 받고,
만료되면 재발급받는다. access token을 코드나 설정 파일에 고정하지 않는다. 토큰은
실행 시점의 별도 채널(예: VPN 내부에서 수행하는 운영자 인증/일회성 발급 절차 또는
환경변수 주입)로 전달하며, 로그·화면·저장소에 남기지 않는다.

우리 규모에서의 구현 선택은 **HMAC 서명 JWT + 간단한 `/auth/token` 발급 엔드포인트**다.
서버만 보유하는 JWT signing secret은 환경변수/실행 환경 secret으로 주입하고,
발급 엔드포인트는 VPN 내부에서 별도의 운영자 확인 또는 짧은 유효기간의 발급
credential을 요구한다. signing secret과 access token을 혼동하지 않는다. secret이
노출되면 즉시 교체하고 기존 토큰 TTL을 짧게 유지한다.

이 방식은 별도 IdP 없이 구현할 수 있고 6명·10주 일정에 맞는다. self-signed 내부 CA와
mTLS는 더 강한 workload identity를 주지만 인증서 발급·배포·회전·폐기 운영을 새로
맡아야 하므로 이번 프로젝트에는 과하다. 운영 환경으로 확대할 때는 OIDC 또는 mTLS로
교체할 수 있도록 claim의 `sub`/`aud`/`scope` 검증 경계는 서비스에 둔다.

### Scope

릴리스 후 외부 콘솔이 붙는 시나리오가 확정됐으므로 세 동작의 권한을 분리한다.
`composer:write` 하나로 모두 허용하면 조회 전용 도구나 검증 자동화가 실제 적용
권한까지 갖게 되어 최소 권한 원칙을 지킬 수 없다.

| 엔드포인트 | 필수 scope | 파일/구성 변경 |
|---|---|---|
| `GET /composer/current` | `composer:read` | 없음 |
| `POST /composer/validate` | `composer:validate` | 없음 |
| `POST /composer/apply` | `composer:write` | 있음 |

발급 토큰은 필요한 scope만 가진다. 예를 들어 상태 표시용 콘솔은 `composer:read`,
검증 화면은 `composer:read` + `composer:validate`, 실제 적용 작업은 명시적으로
`composer:write`를 받아야 한다. `composer:write`가 read/validate를 암묵적으로
허용하지는 않는다.

## 엔드포인트

### `GET /composer/current`

`composer:read`를 요구한다. 현재 파일의 `revision`과 `config`(선언 전체,
`revision` 필드 제외)를 낸다. `apply`를 보내기 전 `base_revision`을 여기서 얻는다.

### `POST /composer/validate`

`composer:validate`를 요구한다.

```json
{"config": {...}}
```

후보 선언을 **canonical loader**(`load_project_config`)로 검증만 한다.
**파일을 바꾸지 않는다.** 활성 Team의 구현체는 요청의 임의 Python 경로를 import하지
않고, 대상 제품이 제공하는 **구현체 registry의 ID**로만 선택한다. 요청의
`implementation_ref`는 registry에 등록된 ID인지 확인하고, registry가 해당 ID에
연결한 사전 등록 callable/모듈만 로드한다. registry 밖의 모듈명·경로·클래스명은
422로 거부한다. 따라서 원격 요청 문자열이 `importlib.import_module`의 입력이 되는
경로를 두지 않는다. registry 변경은 대상 제품 릴리스에 포함된 코드 변경이다.

응답: `{"valid": true, "errors": [], "revision": "..."}` 또는
`{"valid": false, "errors": ["..."]}`.

### `POST /composer/apply`

`composer:write`를 요구한다.

```json
{"config": {...}, "base_revision": "...", "reason": "..."}
```

검증을 통과하고 `base_revision`이 **현재 파일의 revision과 일치할 때만** 원자적으로
쓴다.

- **revision 불일치 → `409 revision_conflict`**(`current_revision` 포함).
  요청 자체는 유효했고 그 사이 파일이 바뀐 것이므로 400이 아니다.
- **검증 실패 → `422 invalid_declaration`**.
- 쓰기는 프로세스 내 lock(`_WRITE_LOCK`) 아래서 임시 파일에 전부 쓴 뒤
  `os.replace()`로 교체한다. 임시 파일명은 요청마다 `uuid4()`를 섞는다.
- 성공 시 이전 파일을 `.yaml.bak`으로 백업하고 새 `revision`을 낸다.
- 성공한 apply마다 아래 audit event를 append한 뒤 성공 응답을 반환한다. audit
  기록 실패는 성공으로 숨기지 않고 명시적 오류로 처리한다.

## Audit 영속 로그

`.yaml.bak`은 직전 상태 복구용일 뿐 이력·행위자 기록이 아니므로 audit의 근거로
사용하지 않는다. MVP에서는 `case_events`와 같은 append-only 원칙을 적용해 대상
제품의 별도 파일 `var/audit/composer_events.jsonl`에 이벤트 한 건을 한 줄씩
추가한다. apply의 구성 파일 교체와 audit append는 같은 writer lock 아래서 수행하고,
append 후 flush한다. 다중 프로세스/다중 인스턴스 운영으로 확장할 때는 이 파일을
append-only DB 테이블로 옮기되 동일한 이벤트 계약을 유지한다.

최소 event shape은 다음과 같다.

```json
{"event": "composer.apply", "actor": "final_project_ui",
 "subject": "...", "timestamp": "2026-08-18T00:00:00Z",
 "previous_revision": "...", "revision": "...",
 "changed_fields": ["teams[0].implementation_ref", "ports.api.enabled"],
 "reason": "...", "correlation_id": "..."}
```

`actor`/`subject`는 JWT의 검증된 `sub` 및 필요 시 `jti`에서 얻고, timestamp는 서버
시간을 사용한다. `changed_fields`는 값·secret·전체 설정을 복사하지 않고 경로와
변경 종류(add/update/remove)만 요약한다. token, signing secret, 임의 파일 경로와
민감한 설정값은 event와 응답에 기록하지 않는다. `read`/`validate`도 필요하면
호출 감사 로그를 남길 수 있지만, 최소 영속 audit의 필수 대상은 mutation인 `apply`다.

## 경계 / 운영 제한

- **단일 프로세스 잠금**이다. 여러 워커·여러 인스턴스에 걸친 잠금은 없다. 이번
  프로젝트에서는 한 writer 인스턴스만 운영하고, 인스턴스가 늘어나면 파일 lock 또는
  DB 조건부 쓰기로 넓힌다.
- API는 VPN/SSH 터널과 Bearer JWT를 모두 요구한다. 브라우저 쿠키를 인증 수단으로
  쓰지 않으며, 브라우저에서 직접 호출하게 할 경우 CORS 허용 origin을 명시적으로
  제한한다.
- 토큰 검증은 signature, `exp`, `aud`, `sub`, scope를 모두 확인한다. 만료·위조·scope
  부족은 각각 적절한 401/403으로 거부한다.

## 테스트 계약

`tests/e2e/test_composer_write_channel.py`는 인증 필요, JWT 만료/위조, 세 scope 분리,
`composer_ui`가 꺼져 있어도 API가 살아 있음, validate가 파일을 안 건드림, registry
밖의 구현체 ID가 422로 거부됨, audit event의 actor/revision/changed_fields 기록,
동일 `base_revision`으로 보낸 동시 apply 2건 중 1건만 200이고 나머지는
409(`revision_conflict`)임을 검증한다.

## 개정 이력

### 2026-08-18 — 릴리스 후 개발 콘솔 보안 계약 확정

- 고정 공유 키를 폐기하고 VPN/SSH 터널 + 실행 시 발급하는 단명 JWT의 2계층 인증을
  추가했다. 학생 프로젝트 규모에는 HMAC JWT를 선택하고 mTLS는 후속 확장으로 남겼다.
- `composer:read`/`composer:validate`/`composer:write` scope를 확정했다.
- `.yaml.bak`을 audit으로 간주하지 않고 append-only JSONL audit event를 정의했다.
- 임의 `implementation_ref` import를 폐기하고 registry ID allowlist를 확정했다.
- final_project_ui는 인증된 Composer API만 호출하고 대상 파일/DB/Python을 직접
  만지지 않는 예외 경계를 문서화할 수 있도록 했다.

### 2026-08-19 — v3(토글 전용) 목표 계약 §0 추가, 옛 모듈 경로 정정

- `program/plan/A-COP_Composer_v3_설계_토글전용_UI이관.md`의 채택이 사용자
  채팅으로 확정돼, 그 문서 §2(계약 원문)를 이 문서 §0에 canonical 사본으로
  옮겼다. v3 §6의 1단계("대상 endpoint 계약 확정")를 이걸로 완료 처리한다.
  2~8단계(introspection 확장, cs 최소 endpoint, ui 화면, 정리)는 **아직
  착수 안 함** — 각각 별도 세션의 몫이다(cs·`final_project_ui`).
- 1번 줄의 `app.composer_staging.composer_service`가 실제로 존재하지 않는
  경로였음을 발견해 정정 — `acop_basement`/`acop_composer` 패키지 분리
  (v0.3.0, 같은 날) 이후 실제 경로는 `acop_composer.service`/`api`/`auth`다.
- v2와 v3의 실제 전환 방식(즉시 교체/병행/유지 — `program/plan/
  A-COP_Composer_v3_불일치_해소안.md`의 안 A/B/C)은 아직 결정 안 됨 —
  이 문서는 두 계약을 병기할 뿐 전환 시점을 정하지 않는다.
## 배포 경계와 운영상 제약

- `_WRITE_LOCK`은 **프로세스 로컬**이다. 배포는 writer 프로세스가 정확히
  하나여야 한다 — 워커나 인스턴스가 여러 개면 이 락을 공유하지 않는다.
  수평 확장을 하려면 먼저 분산 락 또는 DB 조건부 쓰기 경계로 바꿔야 한다.
- `/auth/token`은 공개 JWT 검증 API가 아니라 **운영자가 관리하는 JWT
  발급 endpoint**다. Composer 호출자는 단명 Bearer JWT만 받는다 — 발급
  자격증명과 서명 비밀키는 관리 경계 안에만 머문다.
- 실제 `apply()` 순서는 다음과 같다: `apply_candidate()`가 검증 후
  `_WRITE_LOCK` 아래서 `config/project.yaml`을 원자적으로 교체하고,
  **그 다음** API 핸들러가 `var/audit/composer_events.jsonl`에 audit
  이벤트를 append한다. **이 둘은 하나의 원자적 트랜잭션이 아니다** —
  audit append가 실패해도 config는 이미 적용된 상태이고, API는 오류를
  반환한다.
- `config/project.yaml`을 적용해도 **이미 떠 있는 프로세스가 그 상태를
  자동으로 재로드한다는 보장은 없다.** 재시작·reload endpoint·polling
  중 무엇을 쓸지는 운영 판단이며, 이 계약은 그것을 의도적으로 정하지
  않는다.
