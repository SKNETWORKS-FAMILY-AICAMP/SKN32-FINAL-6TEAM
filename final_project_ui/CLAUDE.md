# final_project_ui — 작업 규칙

CS 제작 플랫폼의 **개발 콘솔**을 제품에서 떼어낸 별도 프로그램이다.
프로젝트 경로만 주면(또는 같은 루트의 형제 프로젝트를 스스로 찾아) 그 프로젝트에 붙는다.

---

## 0. 가장 중요한 규칙

### 0.1 ★다른 폴더를 마음대로 참조하지 않는다

이 저장소의 작업 범위는 **이 폴더 안**이다.
`final_project_sample`·`final_project_cs` 등 **다른 폴더를 읽어야 하면 먼저 허가를 받는다.**

대상 프로젝트를 읽는 것은 **런타임 기능**이고, 그건 사용자가 경로를 줄 때 일어난다.
개발 중에 참고하려고 남의 폴더를 여는 것과는 다르다.

### 0.2 ★전체를 포크하지 않는다 — UI 만이다

이 저장소에 들어오는 것은 **화면과 읽기 어댑터**뿐이다.

| 여기 있어도 되는 것 | ★여기 있으면 안 되는 것 |
|---|---|
| 프로젝트 탐지 | Core 계약 모델 (`ProjectConfig`·`TeamManifest`·`ContextPack` …) |
| 파일·DB **읽기** 어댑터 | 상태기계·`transition_case()`·리듀서 |
| 화면·표현 | Agent Team·Registry·Controller |
| 대상 프로필 | 마이그레이션·DDL·seed |
|  | 평가 러너·프롬프트·코퍼스 |

★**대상의 파일은 "데이터" 로 읽는다.** 대상의 검증 모델을 가져오지 않는다 —
`project.yaml` 을 읽으려고 `ProjectConfig` 를 복사해 오면 그 순간 포크가 시작되고,
대상이 스키마를 바꿀 때마다 여기도 따라 고쳐야 한다.

대시보드는 **선언이 유효한지 판정하지 않는다.** 그건 대상의 일이다.
여기서는 *무엇이 적혀 있는가* 를 보여주고, 못 읽으면 **못 읽었다고 적는다.**

★표현도 마찬가지다. 대상의 `theme.py` 를 복사하지 않는다. 이 프로그램의 화면은
이 프로그램이 만든다 — 대상이 없어도 떠야 하기 때문이다.

### 0.3 대상 프로젝트의 파이썬을 import 하지 않는다

★**여기서 "대상"은 `final_project_cs`다.** 릴리스 대상 제품을 말한다.
`final_project_sample`은 대상이 아니다. Core 계약과 인프라를 먼저 검증하는 공용
구현체이고, 거기서 만든 것을 패키지로 배포한다. **sample이 만든 패키지를
pip install해서 쓰는 것은 이 원칙이 금지하는 대상이 아니다.**

Composer 판단·요청 로직은 sample에서 만들고 이 프로그램이 가져다 쓴다. 같은 코드를
두 번 만들지 않기 위해서다. 근거는 `program/plan/A-COP_Composer_소유권_정정.md`다.

★이 프로그램은 **남의 프로세스 안에서 코드를 실행할 수 없다.**
대상의 `composition.build_registry()` 같은 것을 부르려 들면 그 순간 분리가 무너진다.

읽는 것은 **데이터**뿐이다:

| 출처 | 무엇 |
|---|---|
| `config/project.yaml` | 모듈·Port·Team 선언 |
| `docs/evidence/DoD-*.md` | 판정·근거 |
| `eval/reports/*.jsonl` | 평가 run |
| DB (접속 정보를 줄 때) | 실행 이력 |
| introspection 응답 (대상이 떠 있을 때) | 조립 실측 |

★**예외 — 대상이 내놓는 인증된 Composer 쓰기 API는 호출할 수 있다.**
`/composer/current`·`/composer/validate`·`/composer/apply`(계약: 대상 저장소
`docs/handoff/13_Composer_쓰기채널_계약.md` v2)는 모듈·Team·Port 구성을 바꾸는
유일한 경로이고, 릴리스 후에도 항상 살아있다. 이 예외는 "대상 파일을 직접 쓰지
않는다"는 원칙을 깨지 않는다 — 쓰기 자체는 대상 프로세스 안에서, 대상의 Core
계약으로 검증한 뒤 실행되고, 여기서는 그 API를 호출할 뿐이다. 이 예외로도 대상
파일·DB·Python 모듈을 직접 읽거나 수정하거나 import하지 않는다.
구현: [`console/composer.py`](console/composer.py) — raw dict만 주고받는다
(`ProjectConfig` import 없음, 아키텍처 테스트로 강제).

인증은 계약 v2 — VPN/SSH 터널 + 실행 시 발급하는 단명 JWT, `composer:read`/
`composer:validate`/`composer:write` scope 분리, 대상의
`var/audit/composer_events.jsonl` append-only audit.
★**실측(2026-08-18): `final_project_sample`은 이제 v2다** — 다른 세션이 그 사이
`app/presentation/composer_auth.py`(`POST /auth/token`, HMAC JWT, TTL 15~60분)를
구현했다(`docs/reports/2026-08-18_P11_Composer_쓰기채널.md` 후반부 실측 기록).
`CONSOLE_COMPOSER_ISSUER_SECRET`에는 `/auth/token` 발급자 전용 비밀키를 넣는다.
`console/composer.py`가 동작별 최소 scope로 매번 단명 JWT를 발급받아 실제 요청에 사용한다.
대상이 아직 v1(고정 토큰)뿐인 다른 프로젝트는 이 v2 어댑터의 지원 범위가 아니다.

### 0.4 없는 것을 지어내지 않는다

못 읽었으면 **`missing`·`모름`** 이라고 적는다. `0` 으로 채우지 않는다 —
화면의 `0` 은 "정상" 으로 읽힌다.

★**조용히 자르지 않는다.** N개만 보여주면 "전체 M개 중 M−N개는 화면에 없다" 를 적는다.

---

## 1. 계약 원칙

- 대상이 내는 introspection 에는 `contract_version` 이 있다.
  **모르는 버전이면 모른다고 말한다** — 추측해서 그리지 않는다
- 대상의 파일 형식이 바뀌면 **여기서 먼저 깨져야 한다.** 조용히 빈 화면이 되면 안 된다
- 대상을 **직접** 쓰지 않는다. 이 프로그램은 read-only 다 — 단, §0.3의 인증된 Composer API 호출은 예외다

## 2. 코드 원칙

- 오진 위에 수정을 쌓지 않는다. 하나 고치면 그것만 검증하고 다음으로 간다
- 조용한 스킵을 만들지 않는다. `except: continue` 는 실패를 세어 보고한다
- 오진했던 내용을 주석에 남긴다
- **검사하는 척하는 검사를 만들지 않는다** — 항상 참인 단언, 형태만 갖춘 fixture

## 3. 검증 원칙

- 화면이 있으면 **실제로 열어서** 확인한다. HTTP 200 만으로 "된다" 하지 않는다
- 대상 프로젝트로 검증할 때는 **허가를 받고** 어떤 폴더를 읽었는지 리포트에 적는다

---

## 4. 문서

- 계획: `docs/plans/`
- 계약: `docs/handoff/`
- 리포트: `docs/reports/` · 결함: `docs/reports/debugs/`
