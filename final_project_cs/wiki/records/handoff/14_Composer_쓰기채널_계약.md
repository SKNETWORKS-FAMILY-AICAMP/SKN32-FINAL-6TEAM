# 14 — Composer 쓰기 채널 계약 (2026-09-06)

> ★이 문서는 **이 저장소에 Composer 구현이 없다**는 사실부터 말한다.
> 구현은 별도 패키지 `acop_composer` 하나뿐이고, 이 저장소는 자기 것을
> 넘겨주기만 한다. 기준선: `../../../program/plan/A-COP_구현계획서_v9.md` §8-D.

`09_Composer_GUI_계약.md` 가 가리키던 `13_Composer_쓰기채널_계약.md` 는 이
저장소에 만들어진 적이 없다(13번은 introspection 계약이다). 그 자리를 이 문서가
채운다.

---

## 0. 왜 구현이 여기 없나

2026-09-06 이전에는 세 파일이 sample 것을 **손으로 베낀 사본**이었다.

| 파일 | 줄 수 |
|---|---|
| `app/presentation/api/composer.py` | 157 |
| `app/application/composer_service.py` | 167 |
| `app/presentation/composer_auth.py` | 76 |

사본이 실제로 만든 문제 둘.

1. **한쪽만 자랐다.** sample 이 `/catalog`·`/changes`·`/revisions`·`/restore`
   를 갖는 동안 cs 는 `/current`·`/validate`·`/apply`·`/toggle` 넷에 머물렀다.
   `final_project_ui` 콘솔은 `/composer/catalog` 와 `/composer/changes` 를
   부르므로, **cs 대상에서는 그 카드가 404 로 안 떴다.**
2. **쓰기 채널이 고객 릴리즈에 실려 있었다.** `create_app()` 이 composer
   라우터를 무조건 붙여서 방어가 scope 하나뿐이었다.

---

## 1. 두 가지 빌드

| 빌드 | 진입점 | `acop_composer` | `/composer/*` |
|---|---|---|---|
| **릴리즈** (고객) | `app.presentation.api.app:app` | 설치 안 함 | **없음** |
| **관리용** | `app.entrypoint:app` | 설치함 | 있음 |

★릴리즈 빌드에서 `/composer/current` 는 **404** 다 — 403 이 아니다.
"권한이 없다" 가 아니라 **"그런 표면이 없다"** 이며, 이쪽이 훨씬 강한 보장이다.

실측(2026-09-06, `sys.meta_path` 로 `acop_composer` import 를 막고 기동):

```
경로 18개로 기동 · Composer 표면 없음
/health 200 · /introspection 401(살아 있음) · /composer/current 404
```

★`/introspection` 은 **릴리즈 빌드에도 있다.** 조회는 운영에 필요하고 쓰기가
아니기 때문이다. 그래서 `config_revision()` 계산은 `app/core/project_config.py`
(코어)에 있다 — 예전에는 `composer_service` 에 있어서 **선택 기능에 필수 경로가
의존**하고 있었다.

★`POST /admin/reload` 도 **릴리즈 빌드에 있다**(scope `ops:reload`). Composer 가
없어도 선언 파일을 사람이 바꿔 놓고 반영시킬 수 있어야 하고, 반영은 쓰기 채널이
아니라 이 프로세스의 조립을 갈아 끼우는 일이다.

---

## 2. 이 저장소가 넘기는 것 — `app/composer_host.py`

패키지는 `ComposerHost` 가 준 것만 쓴다. 여기 없는 것을 패키지가 쓰면 그게 곧
결합이다.

| 필드 | 이 저장소가 넣는 것 |
|---|---|
| `codec` | `config_from_declaration` · `model_dump` · `config_revision` |
| `implementations` | 이 제품이 등록한 Team **6종** |
| `stores` | 파일 저장소 3종(`app/core/composer_stores.py`) |
| `auth` | `aud="final_project_cs"` · JWT 비밀 · 발급자 비밀 · scope 목록 · TTL |
| `default_config_path` | `config/project.yaml` |
| `audit_dir` | `var/audit/` |
| `default_deployment_id` | `"self"` (direct 방식) |

### 지켜야 하는 성질

- **등록표(`IMPLEMENTATIONS`)와 `KNOWN_IMPLEMENTATION_REFS` 는 같은 집합이다.**
  어긋나면 UI 에 뜨는데 저장이 422 로 거부되거나(카탈로그가 넓다), 저장은 되는데
  UI 에서 못 고른다(등록표가 넓다). 둘 다 운영자에게는 "되는데 안 된다" 로 보인다.
  게이트: `tests/architecture/test_composer_stays_out_of_this_repo.py`
- **비밀은 값이 아니라 함수로 넘긴다.** 프로세스가 뜬 뒤 설정이 바뀌어도 따라가고,
  이 객체를 로깅해도 비밀이 안 샌다.
- **`aud` 가 sample 과 달라야 한다.** 같으면 sample 발급자가 만든 토큰이 이쪽에서
  통한다 — 대상 격리는 서명만으로 되는 것이 아니다.
- **예외를 경계에서 옮긴다**(`_TranslatingStore`). 저장소가 자기 예외를 던지면
  패키지의 `except RevisionMismatch` 가 **조용히 빗나가** revision 충돌이 409 가
  아니라 500 으로 나간다. sample 에서 실제로 그 상태였다(2026-09-06 실측).
- **중앙 저장소 요청은 거부한다.** 이 제품은 direct(pip) 방식이라 파일뿐이다
  (D-007). 조용히 파일로 떨어뜨리면 설정 서비스로 띄웠을 때 **남의 대상을 자기
  파일에 쓴다.**

---

## 3. 표면

| 경로 | scope | 무엇 |
|---|---|---|
| `POST /auth/token` | 발급자 비밀 | 단명 HMAC JWT 발급 |
| `GET /composer/current` | `composer:read` | 지금 선언 + `revision` |
| `GET /composer/catalog` | `composer:read` | 고를 수 있는 구현 목록 |
| `GET /composer/revisions` | `composer:read` | 선언 이력(최신부터) |
| `POST /composer/validate` | `composer:validate` | 검증만. **선언을 안 바꾼다** |
| `POST /composer/toggle` | `composer:write` | 항목 하나의 활성 상태 |
| `POST /composer/changes` | `composer:write` | 항목 단위 CRUD |
| `POST /composer/apply` | **`composer:admin`** | 선언 **전체** 교체 |
| `POST /composer/restore` | **`composer:admin`** | 이력의 revision 으로 되돌리기 |

★**`/apply`·`/restore` 가 `composer:admin` 인 이유**(D-011). 운영자 화면은 항목
하나 단위만 쓴다. 전체를 갈아끼우는 경로는 **처음 설치·복원·이관** 용이라 관리자
에게만 연다 — 두 운영자가 전체본을 동시에 보내면 한쪽이 남의 변경을 덮거나 항상
409 로 튕긴다.

★**Python 경로(`implementation_ref`)를 UI 에 내보내지 않는다.** UI 는
`implementation_id` 만 주고받는다. UI 가 Python 경로를 알면 구현을 옮길 때마다
UI 를 고쳐야 한다. HTTP 로 들어온 `implementation_ref` 는 등록표 allowlist 대조로만
통과한다 — 임의 모듈을 import 시키는 경로가 아니다.

### 응답의 정직함

- 저장에 성공해도 `activation_state` 는 **`pending_restart`** 다. 조립은 프로세스
  기동 때 한 번 일어나므로, 저장됐다고 이미 떠 있는 런타임이 그 설정으로 도는 것이
  아니다. "적용 완료" 처럼 답하면 그게 조용한 성공 위장이다(`CLAUDE.md` §0.1).
- 낡은 `base_revision` 은 **409 `revision_conflict`** 다. 400 이 아니다 — 요청
  자체는 유효했고 그 사이 상태가 바뀐 것이다.
- 거부 코드를 뭉개지 않는다. "그런 대상이 없다"(`invalid_change`) 와 "토글할 수
  있는 종류가 아니다"(`validation_error`) 는 운영자가 할 일이 다르다.

---

## 4. 감사와 이력

| 것 | 어디 | 성질 |
|---|---|---|
| 감사 | `var/audit/composer_events.jsonl` | append-only. 누가·언제·무엇을·왜 |
| 이력 | `var/audit/composer_revisions.jsonl` | append-only. 선언 전문 + revision |

- 쓰기 경로가 `apply_candidate` 하나뿐이라 **`/toggle`·`/changes`·`/apply`·
  `/restore` 전부의 이력이 빠짐없이** 남는다.
- 첫 기록이면 직전 상태를 `baseline` 으로 먼저 남긴다 — 그래야 첫 변경 직후에도
  되돌리기가 성립한다.
- 감사·이력 기록에 실패하면 **500 으로 올린다.** 삼키지 않는다. 못 남겼는데
  성공으로 답하면 감사로서 값이 없다.
- 깨진 JSONL 줄은 **건너뛰지 않고 `StoreError`** 다. 조용히 넘기면 "이력에 없다"
  와 "이력을 못 읽는다" 가 같은 모습이 되고, 되돌리기가 이유를 모른 채 실패한다.

★**감사 이벤트 모양이 2026-09-06 에 바뀌었다.** 옛 cs 구현은
`target_type`/`target_id`/`previous_active`/`active` 를 적었고, 패키지는
`resource_type`/`instance_id`/`operation` 과 **`changed_fields`**(무엇이 바뀌었는지를
값이 아니라 **경로**로) 를 적는다. 옛 기록은 옛 모양 그대로 남는다 — 덮어쓰지
않고 공존시킨다(`CLAUDE.md` §1).

---

## 5. revision

내용에서 나온다. 파일 mtime 도 커밋도 아니다.

★**sample 은 12자, 이쪽은 sha256 64자다.** 형식을 맞추면 기존에 발급된
`base_revision` 이 전부 어긋나 저장이 409 로 튕긴다. revision 은 그 대상 안에서만
비교되므로 형식이 달라도 되고, 굳이 맞출 이유가 없다.

★`/introspection` 이 말하는 `config_revision` 과 Composer 가 말하는 `revision` 은
**같은 함수**(`app.core.project_config.config_revision`)에서 나온다. 두 벌 만들면
둘이 갈리는 날이 온다.

---

## 6. 게이트

`tests/architecture/test_composer_stays_out_of_this_repo.py` 가 막는 것:

1. 지운 사본 3종이 **다시 생기는 것**
2. 조립부(`app/composer_host.py`·`app/entrypoint.py`) **밖에서** 패키지를 부르는 것
3. 릴리즈 진입점(`app/presentation/api/app.py`)이 패키지를 끌어오는 것
4. 카탈로그와 등록표가 어긋나는 것

★사람 눈으로는 못 막는다. 파일 하나 더 만드는 것이 문법적으로 아무 때나
가능하기 때문이다.

---

## 7. 왕복 실측 (2026-09-06, 관리용 빌드 · 임시 선언 파일)

```
[1] 현재      6cca23ee13b8
[2] 카탈로그  구현 12종 · python 경로 노출 False
[3] 토글      200 · pending_restart
[4] 낡은 base 409 revision_conflict
[5] 이력      [(9a0497d7, toggle), (6cca23ee, baseline)]
[6] write 로 복원 403          ← 복원은 admin 이다
[7] 복원      200 · restored_from 6cca23ee13b8
[8] 파일이 원래대로 True · 감사 2줄
```

전체 테스트 **681 passed · 4 deselected**.

---

## 8. 하지 않은 것

- **중앙 설정 저장소** — 이 제품은 direct(pip)다(D-007). 중앙은 별도 프로젝트로
  분리됐고 cs 범위 밖이다. 요청이 오면 거부한다(§2).
- ~~**`POST /admin/reload`**~~ — **2026-09-06 같은 날 이식했다.** 이 문단을 쓸
  때는 없었다. 지금은 계약 **1.1** 이고 `ops:reload` scope 로 열려 있다
  ([`13_introspection_계약.md`](13_introspection_계약.md)).

  ★그래도 `/toggle`·`/changes` 응답의 `activation_state` 는 여전히
  `pending_restart` 다. **저장과 반영은 여전히 다른 행위**이기 때문이다 —
  이 API 는 저장까지만 하고, 반영은 `ops:reload` 를 가진 사람이 따로 부른다.
  콘솔은 어긋났을 때만 [반영] 버튼을 낸다.
- **여러 인스턴스에 걸친 잠금** — 파일 모드는 단일 writer 전제다. 여러 프로세스가
  같은 선언 파일을 쓰는 형태가 되면 파일 락이나 중앙 저장소의 조건부 쓰기가
  필요하다.
