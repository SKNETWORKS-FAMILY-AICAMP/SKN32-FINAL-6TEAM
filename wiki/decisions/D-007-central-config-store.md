---
type: decision
title: 중앙 설정 저장소
description: 고객 빌드에 쓰기 코드를 안 넣으면서 릴리즈 후 구성 관리를 하려면 로컬 파일로는 안 된다
status: draft
tags: [architecture, security, contract]
owners: [human:미배정]
domain: neutral
---

# D-007 중앙 설정 저장소

`[실측]` `A-COP_Composer_중앙설정저장소_결정.md`(2026-08-29)에서 이관.

## 맥락 — 두 요구가 충돌했다

| 요구 | 뜻 |
|---|---|
| **고객 빌드에 쓰기 코드를 넣지 않는다** | 배포본이 자기 설정을 못 고친다 |
| **릴리즈 후에도 구성을 관리한다** | 누군가는 고쳐야 한다 |

**로컬 YAML 파일 저장으로는 둘이 양립하지 않는다.** 고칠 수 있으면 쓰기 코드가 있는 것이고, 없으면 못 고친다.

## 결정

> **direct 와 central 두 모드를 모두 지원하고, UI 환경변수로 선택한다.**
>
> **수천 배포 규모에서는 central 을 쓴다.**

`[실측 2026-09-10]` **이 결정이 닿는 범위는 UI 프로젝트와 sample 이다.** cs 는 central 대상을 거부한다(`final_project_cs/app/composer_host.py` `_reject_central` — 「중앙 설정 저장소를 구현하지 않았다」). 아래 「구현 상태」 앞의 「두 배포 형태를 함께 두는 것 — 아직 결정 안 됐다」는 [D-004](D-004-self-hosting-rationale.md) 로 이어지는 **배포 형태** 이야기로 읽힌다. 설정 저장 모드(이 결정)와 축이 달라 「결정」과 「미결정」이 한 문서에 나란히 있다.

## 구조

```
중앙 설정 서비스 + DB
        ↓ 읽기 전용 부트스트랩
수천 개의 대상 배포본
```

**대상은 읽기만 한다.** 쓰기 코드가 배포본에 없다.

## 무엇이 바뀌나

| 무엇 | 전 | 후 |
|---|---|---|
| 저장 | YAML 파일 | **DB row + CAS** |
| 식별 | — | `deployment_id` |
| 감사 | 파일 | **append-only DB** |
| 읽기 | 로컬 | 중앙 |

## 바뀌지 않는 것

```
저장과 활성 상태 구분  (desired vs effective)
서버 판정            UI 가 아니라 대상이 검증한다
grant ceiling        권한 상한
```

**UI CRUD 계약(`/catalog`·`/changes`·`/toggle`)도 그대로다.** → [D-CS-003](../../final_project_cs/wiki/decisions/D-CS-003-composer-scope.md)

## ★ 반증 조건

`[실측]` **이 결정이 틀릴 수 있는 조건을 문서가 스스로 적었다.**

> **실제 대상이 수십 개 이하라면 중앙 운영 부담이 더 크다.**

**규모가 전제다.** 수천 대가 아니면 direct 가 낫다.

**반증 조건을 적은 게 이 문서의 좋은 점이다.** 결정을 언제 되돌릴지 미리 정해 뒀다.

## ★ [2026-09-02 추가] 자체호스팅 주장과 충돌한다

`[실측]` `_중앙설정저장소_검토_2026-08-29.md` 에서 이관. **이 절이 통째로 빠져 있었다.**

**이 결정 문서에 "자체 호스팅"이라는 말이 한 번도 안 나온다.** 그런데 제출표의 차별화 근거 두 개가 정확히 그것이다.

| 제출표 | 내용 |
|---|---|
| 배포 | 자체 호스팅을 목표로 설계했으며 **데이터 외부 반출 방지**를 별도 검증 항목으로 둔다 |
| 이유 4 | **Intercom Fin 은 자체 호스팅 불가** — [G2](../product/positioning.md) |
| 이유 5 | 자체 호스팅 수요는 규제가 만든다 — [F1](../product/positioning.md) |

### 중앙 저장소로 가면 이렇게 된다

**대상이 기동할 때마다 우리 서버로 나가야 한다.**

| 문제 | |
|---|---|
| **망분리 환경에서 아예 못 돈다** | **G2 로 Fin 을 비판한 논리가 그대로 돌아온다** |
| "설정이 어디 있냐"에 "우리 DB"라고 답해야 한다 | 규제 산업 고객 |
| 우리 중앙 서비스가 죽으면 고객사가 같이 죽는다 | **자체 호스팅의 장점이 사라진다** |

### 위치가 잘못돼 있었다

`[실측]` 결정 문서 §8 에 **"대상이 중앙에 못 붙을 때의 동작"**이 미정으로 적혀 있다.

> **이건 장애 대응 항목이 아니라 제품 포지셔닝 문제다.**

**그 자리에 있으면 안 된다.**

### 제안 — 뒤집자는 게 아니다

**두 배포 형태를 함께 두는 것**을 검토할 만하다. → [D-004](D-004-self-hosting-rationale.md)

`[미확보]` **아직 결정 안 됐다.**

## 구현 상태

`[실측]` 마이그레이션·store·config source·service app 커밋 완료. **438개 테스트 통과.**

`[실측 2026-09-06]` **그 코드는 전부 `final_project_sample`에 있다.** `acop_basement/core/config_store.py` · `application/config_source.py` · `migrations/006_project_configs.sql` · `acop_composer/api.py`·`service.py`, 테스트 5벌(store·central source·config service·composer service·UI 계약). **`final_project_cs`에는 `ConfigStore`·`project_configs`가 한 줄도 없다.** **★ 2026-09-06 결정 (사용자) — cs로 가져가지 않는다.** 중앙 설정 저장소는 **별도로 분리되어야 할 프로젝트**다. 굳이 어딘가에 붙인다면 그 자리는 **UI 프로젝트**(운영 콘솔 쪽)이지 cs가 아니다. cs는 대상(읽기 전용 부트스트랩)일 뿐이라 저장소를 품을 이유가 없고, D-006이 정한 "Composer는 cs 밖"과도 같은 방향이다. 따라서 cs 산출물 문서엔 "결정 있음 · 참고 구현은 sample · cs 범위 밖"으로 적고, 위 "이번 기간에 하나" 물음은 닫는다 — 이번 기간 cs 범위에는 없다.

## ★ [2026-09-03] 중앙에 못 붙으면 기동을 거부한다

`[실측]` 원본 §8 에서 이관. **wiki 전체에 `fail-fast`·`기동 거부` 가 0건이었다.**

> **기동 거부(fail-fast). 캐시는 두지 않았다** — 무엇이 켜져 있는지 모르는 채로 트래픽을 받는 것이 더 위험하다.

### ★ 대가는 가용성 결합이다

> **중앙이 죽으면 대상이 못 뜬다.**

**이게 위 "자체호스팅 충돌" 절의 세 번째 항목과 같은 말이다.** 그런데 그 절은 위험으로만 적었고 **이 결정이 실제로 그 대가를 택했다는 사실**이 빠져 있었다.

`[실측]` **캐시를 넣는다면 `degraded` 를 반드시 함께 신호해야 한다.** → [../../final_project_cs/wiki/context/context-broker.md](../../final_project_cs/wiki/context/context-broker.md)

### 두 모드가 있고 기본은 `direct` 다

```
CONSOLE_COMPOSER_MODE = direct | central
```

| 모드 | 언제 |
|---|---|
| **`direct`** (기본) | 대상이 적을 때. **지금까지의 동작** |
| `central` | 대상이 많을 때 |

`[실측 2026-09-06]` 사용자 방향 — **지금은 pip(direct) 방식으로 가고, 중앙은 UI 프로젝트의 옵션으로 열어 둔다.** 그 옵션은 이미 있다(`final_project_ui/console/profiles.py` `CONSOLE_COMPOSER_MODE`). 두 방식은 배타적이 아니라 같은 패키지의 두 모드다 → [D-011](D-011-composer-v3-gap.md) 2026-09-06 절.

`[실측]` **전환에 코드 변경이 없다.** 그리고 **Composer 는 1곳에만 설치한다** — 수천 개 cs 에 설치하지 않는다. `[2026-09-10]` 둘 다 **UI 프로젝트·sample 에 한정**한다 — cs 는 central 을 거부하므로 cs 쪽 전환에는 중앙 저장소 구현이라는 코드 변경이 든다. 「1곳 설치」도 central 모드 이야기다.

**그래서 마이그레이션 경로가 필요 없다.** 파일 모드가 기본으로 남아 있고 중앙은 **설정으로 켜는 옵션**이다.

### 재기동 없이 갈아 끼운다

`[실측]` 2026-08-31 확정. `POST /admin/reload` (scope `ops:reload`)

**설계검토는 원래 "재기동"을 골랐는데** 재검토 트리거로 **"대상과 Composer 가 같은 durable config store 를 쓰기로 정해진 때"**를 남겼고, **이 결정이 그 조건을 충족시켰다.**

함께 `/introspection` 이 셋을 구분해 낸다.

```
active_revision    실행 중
desired_revision   저장됨
reload_state
```

`[실측]` **그 전에는 저장 직후 반영도 안 됐는데 새 revision 을 보고했다.** → [D-011](D-011-composer-v3-gap.md)

## 아직 안 정한 것

`[미확보]`

```
HA · 백업 · 인증 · 방화벽 승인
```

**운영에 필요한 것들이 남았다.** 구현은 됐지만 운영 준비는 아니다.

`[실측]` `_중앙설정저장소_검토_2026-08-29.md` §6이 위 넷 밖에 **더 물어야 할 것 넷**을 적었다. 이 페이지에 없던 것들이다.

| 물음 | 왜 정해야 하나 |
|---|---|
| **감사 로그가 중앙에 있나 대상에 있나** | append-only 테이블로 옮긴다고만 적혔다. 승인 기록은 업무 데이터라 대상에, 설정 변경 기록은 중앙이 맞아 보인다 — 나눌지 합칠지 |
| **`deployment_id`는 누가 발급하나** | 대상이 자기를 증명하는 방법(위 "인증")과 함께 정해야 한다 |
| **설정 유출** | 중앙 한 곳이 뚫리면 **고객사 3,000곳의 구성이 한 번에** 드러난다. 파일 기반엔 없던 위험인데 결정 문서에 항목이 없다 |
| ~~**이번 기간에 하나**~~ | **닫힘 (09-06)** — cs 범위 밖. 별도 프로젝트로 분리하며, 붙인다면 UI 프로젝트. 에픽 없는 게 맞다 |

같은 검토 §1 — 이 결정은 산출물 세 문서(DB·Vector DB 설계서 `project_configs`, 시스템 구성도 2.1, 화면설계서 SCR-03)에 반영됐고 **셋 다 "아직 연결되지 않았다"고 적었다.** 저장 계층은 있지만 부르는 곳이 없어서다 — 위 "구현 상태"의 438 테스트 통과가 "연결됐다"는 뜻은 아니다.

## 다른 결정과의 관계

| | |
|---|---|
| 인스턴스 CRUD 금지 | **철회됨** |
| 임의 Python 경로 등록 금지 | **유지** |
| 3패키지 소유권 | **유지** → [D-006](D-006-composer-ownership.md) |

## 관계

- [D-006](D-006-composer-ownership.md) — Composer 소유권
- [`sample/wiki/composer/`](../../final_project_sample/wiki/composer/index.md) — `core/config_store.py` 가 여기 있다
- [`D-CS-003`](../../final_project_cs/wiki/decisions/D-CS-003-composer-scope.md) — 세 층 구분
- [`D-CS-001`](../../final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md) — `/ui/composer` 폐기
- [../architecture/repository-map.md](../architecture/repository-map.md) — 저장소 관계
