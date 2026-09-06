---
type: decision
title: Composer v3 설계와 구현 중 무엇을 맞출 것인가
description: 설계는 토글 전용인데 구현은 전체 교체다. 세 안을 비교했고 결정에 질문 6개가 남아 있다
status: draft
impl_scope: sample — Composer 는 sample 이 원본이고 cs 로 이식한다. D-006 참조
tags: [architecture, api, contract]
---

# D-011 Composer v3 설계와 구현 중 무엇을 맞출 것인가

`[실측]` **2026-09-06 결정됐다.** 아래 "결정" 절. 질문 여섯은 그 아래 기록으로 남긴다.

## 문제

**설계와 구현이 서로 다른 계약을 가리킨다.**

| | 계약 |
|---|---|
| **v3 설계** | `POST /composer/toggle` **하나로** — 등록 ID 확인 · flag 변경 · revision 충돌 · 감사 |
| **sample 구현** | `ProjectConfig` **전체**를 받아 검증·교체하는 v2 형 — `current` · `validate` · `apply` |

**항목 11개를 대조했더니 일치가 1건이었다.** → [sample/composer/design-gap.md](../../final_project_sample/wiki/composer/design-gap.md)

## 세 안

| | 무엇 |
|---|---|
| **안 A** | **구현을 설계에 맞춘다** — toggle 전용으로 좁힌다 |
| **안 B** | **설계를 구현에 맞춘다** — v2 형을 정본으로 |
| **안 C** | **병행한다** — 종료일을 정하고 |

### 기준별 비교

`[실측]` 설계 문서와 대조 보고서에서 확인된 기준.

| 기준 | A | B | C |
|---|---|---|---|
| UI 가 Core 모델을 import 안 함 | **가장 직접적으로 충족** | 직접 import 는 피하나 **schema 복제 위험** | 새 UI 만 충족 |
| Composer 를 고객 빌드에서 배제 | 구조상 가능 | 현재 구조로 가능 | 결합 검증 필요 |
| **좁은 v3 책임** | **충족** | **포기** | 새 경로만 |
| **v2 소비자 연속성** | **깨질 가능성 큼** | **가장 잘 보존** | 단기 보존 |
| 되돌리기 단순성 | 전환 중 큼 | 단순 | 장기에 복잡 |

**A 와 B 가 정확히 반대다.** 좁은 책임을 얻으면 연속성을 잃는다.

## ★ 답해야 결정할 수 있는 질문 여섯

`[미확보]` **하나도 안 정해졌다.**

1. **고객용 빌드에서 `acop_composer` 와 `/composer/*` 를 완전히 배제하는 것이 양보할 수 없는 목표인가?**
2. **기존 `/composer/validate`·`/composer/apply` 를 부르는 외부 소비자나 운영 절차가 실제로 있는가?**
3. 전체 `ProjectConfig` 교체가 필요한 운영 요구가 남아 있는가, 아니면 flag toggle 로 충분한가?
4. UI 의 비포크 원칙은 **직접 import 만** 금지하는가, **동등한 schema 복제도** 금지하는가?
5. 병행한다면 두 경로가 같은 `project.yaml` 을 공유해야 하는가?
6. deprecation 기간·종료일·제거 책임 주체를 정할 수 있는가?

### 1번과 2번이 갈림길이다

`[실측]` 원문의 권고가 이 둘로 갈린다.

```
1번이 필수 AND 2번이 없다   →  안 A
2번이 있거나 3번이 필수      →  안 B 또는 (종료일 있는) 안 C
```

**그러니 2번을 먼저 세면 된다.** 외부 소비자가 실제로 있는지는 셀 수 있는 사실이다.

`[실측 2026-09-06]` **세었다 — 외부 소비자가 없다.** `/composer/validate`·`/composer/apply`를 부르는 코드는 sample의 `acop_composer/api.py`·`service.py`(제공하는 쪽 자신)와 그 빌드 사본뿐이고, UI 패키지·cs·스크립트에는 호출이 없다. 문서(handoff 13, 프롬프트 4건)에만 이름이 남아 있다. 그러니 위 갈림길에서 2번은 "없다"이고, 1번(고객 빌드 배제가 필수인가)만 답하면 **안 A**로 기운다. 사용자 판단은 아직이다 — 팀 주제 재조사 중이라 미룬다.

## 지금 상태

`[실측]` 2026-09-02 확인. **`/composer/toggle` 경로 자체는 존재한다.**

```
POST /composer/toggle   POST /composer/validate
POST /composer/apply    GET  /composer/current
```

**둘 다 있다.** 사실상 안 C(병행) 상태인데 **종료일이 없다.**

> **종료일 없는 병행은 안 C 가 아니라 그냥 미결이다.**

## ★ [2026-09-03] introspection 계약도 갈라져 있다

`[실측]` `A-COP_Composer_v3_설계_토글전용_UI이관.md` §2 를 오늘 구현과 대조했다.

| 어디 | 값 |
|---|---|
| **설계가 요구한 것** | `contract_version: "introspection.v3"` |
| **`final_project_sample`** | `CONTRACT_VERSION = "1.1"` |
| **`final_project_cs`** | `CONTRACT_VERSION = "1.0"` |

**이름 체계 자체가 다르다.** `introspection.vN` 이 아니라 `N.N` 이다.

### ★ 그리고 두 저장소가 갈려 있다

`[실측]` 2026-09-03 확인. **sample 이 `1.1`, cs 가 `1.0` 이다.**

**sample 이 앞서 있다** — [D-006](D-006-composer-ownership.md) 대로 Composer 는 sample 에서 먼저 만들고 cs 로 옮긴다. **아직 안 옮겨진 상태다.**

`[실측]` cs 쪽 계약 문서(`13_introspection_계약.md`)와 [cs wiki](../../final_project_cs/wiki/external/introspection.md) 는 **둘 다 `1.0` 으로 일치한다.** cs 안에서는 어긋난 데가 없다.

### 설계에만 있는 필드

`[실측]` 설계는 **`registered_ids`** 를 요구한다 — "제품이 등록해 둔 항목의 ID 목록".

```json
"registered_ids": {
  "modules": ["vector_rag", "graph_store", …],
  "teams": ["order_shipping", "return_exchange"],
  "ports": ["team_executor", "message_broker", "graph_store"]
}
```

**구현에 이 필드가 없다.** 대신 `modules`·`teams`·`ports` 를 직접 낸다.

### 구현에만 있는 필드

`[실측]` **구현이 설계보다 더 낸다.**

```python
"active_revision":  active_revision,      # 실행 중인 것
"desired_revision": desired_revision,     # 선언된 것
"reload_state":     reload_state,
"reload_error":     …,
"team_manifests":   manifests,
"port_implementations": …,
```

**주석이 이유를 적어 뒀다.**

> ★**선언과 조립을 함께 낸다.** 선언만 보면 **"켰다고 적혀 있는데 실제로는 안 올라간" 경우를 못 본다.**

> ★옛 소비자를 위해 `config_revision` 을 남긴다. 이제 **실행 중인** revision 을 가리킨다.

**구현이 설계보다 낫다.** 설계는 "무엇이 등록됐나"만 물었는데 구현은 **"등록된 것이 실제로 올라왔나"**까지 답한다.

### 그래서 D-011 의 질문이 하나 늘어난다

| 질문 | |
|---|---|
| **`registered_ids` 를 추가할 것인가** | 설계에만 있다. **UI 가 그걸 필요로 하는지 확인 안 됨** |
| **버전 이름을 맞출 것인가** | `1.1` vs `introspection.v3` |

`[미확보]` **UI 가 실제로 무엇을 읽는지 확인하지 않았다.** `packages/acop_composer_ui/` 를 봐야 안다.

## ★ 결정 (2026-09-06, 사용자)

**안 A를 기본으로 하되, 통째 교체는 없애지 않고 관리자 도구로 내린다. 그리고 이력과 복원을 같이 만든다.**

| 무엇 | 어떻게 |
|---|---|
| 운영자 화면 API | **`/composer/toggle`·`/composer/changes`만.** 항목 하나 단위(켜기·끄기·생성·수정·삭제) |
| 통째 교체 `/composer/apply` | **관리자 전용 scope로 묶는다**(예: `ops:admin`, 기존 `composer:write`와 분리). 용도는 **처음 설치·복원·환경 간 이관**뿐. 운영 UI에는 버튼을 두지 않는다 |
| `/composer/validate` | 저장을 안 하니 그대로. 검사 도구로 쓴다 |
| **이력** | `project_configs`는 대상당 현재 행 하나뿐이라 되돌릴 수가 없다. **revision 이력 표를 추가한다** — 대상·revision·선언 전문·누가·언제·사유. 쓰기 경로가 하나(`apply_candidate()`)라 거기서 한 번만 적으면 된다 |
| **복원** | **"이전 revision으로 되돌리기"** — 이력에서 골라 새 revision으로 다시 적용한다(이력을 덮어쓰지 않고 앞으로 한 칸 더 간다). 이것도 관리자 scope |

**왜 이렇게.** 통째 교체가 정말 필요한 순간(설치·복원·이관·여러 항목 원자 변경)은 있지만 **운영자 손에 쥐어 주면 안 되는 도구**다. 스위치·삭제도 내부에선 전체본을 만들어 같은 저장 함수에 넘기므로 능력 자체는 남는다 — 없애는 건 "아무 설정이나 던져 넣는 공개 경로"이지 능력이 아니다. 되돌리기는 "예전 설정 던지기"가 아니라 이력에서 고르는 게 안전하다.

**배포 형태별로 봐도 같다.** `direct`(파일 하나)에선 통째 교체가 겨우 괜찮고, `central`(DB, 수천 대상)에선 두 운영자가 동시에 작업하면 항상 한쪽이 409로 튕기는 해로운 방식이다 → [D-007](D-007-central-config-store.md). 중앙 저장소는 별도 프로젝트로 가기로 했으니(D-007) 그쪽에 통째 교체 API가 딸려가지 않게 지금 정리하는 게 맞다.

`[실측]` **2026-09-06 sample에 구현했다.** ① `/apply` scope `composer:admin`(guardrails·scope 계약 테스트) ② `acop_basement/core/revision_store.py` + 마이그레이션 `009_project_config_revisions.sql`, `apply_candidate()`가 쓴 직후 같은 잠금 아래에서 기록(첫 기록은 `baseline` 먼저) ③ `GET /composer/revisions`(read) · `POST /composer/restore`(admin) ④ 404/409/422 와 중앙 모드 대상 격리 e2e. 관련 스위트 73개 통과. → [sample/composer/write-channel.md](../../final_project_sample/wiki/composer/write-channel.md) · [auth-scope.md](../../final_project_sample/wiki/composer/auth-scope.md)

`[실측]` **cs 에는 옛 v2 의 자체 복사본이 남아 있다** — `app/application/composer_service.py`·`api/composer.py`(`/apply`가 `composer:write`)·`composer_auth.py`, 그리고 `api/app.py` 가 무조건 include. 사용자가 정한 배포 형태 둘(중앙 → UI 프로젝트 / pip → cs 가 패키지를 설치·주입, 릴리즈 때 제거) 어느 쪽에서도 **cs 소스 안의 복사본은 자리가 없다** → [D-006](D-006-composer-ownership.md) 2026-09-06 절. 복사본을 지우고 `acop_composer` 패키지 주입으로 바꾸면 이 결정의 scope 분리·이력·복원이 패키지째 따라온다. cs 작업자 몫으로 open-items에.

위 질문 여섯 중 2번(외부 소비자)은 "없다"로 확인됐고, 1번(고객 빌드 배제)은 D-006·D-007 방향상 "예"로 본다. 3·4·5·6은 이 결정으로 답이 정해진다 — 전체 교체는 관리자 도구로, UI는 schema 복제 없이 항목 단위로, 병행은 없고, 제거 대신 격리.

## ★ [2026-09-06] cs 복사본을 지우고 패키지를 꽂으면 되나 — 지금은 안 된다, 셋 때문에

`[실측]` 사용자 방향(지금은 pip 방식, 나중에 중앙은 UI 옵션으로)에 맞춰 "cs 의 자체 복사본을 지우고 `acop_composer` 를 설치해 라우터만 주입" 이 되는지 봤다. **그대로는 cs 설정을 전부 거부한다.**

| # | 막는 것 | 근거 |
|---|---|---|
| 1 | 패키지가 **sample 의 등록표**를 본다 — `acop_basement.core.project_config.KNOWN_IMPLEMENTATION_REFS` 는 `FeedbackAnalyticsTeam`·`PlaceholderTeam`·선언형 셋뿐. cs 의 여섯 Team(`app.modules.customer_ops…`)은 전부 "미등록" 으로 422 | `acop_composer/service.py::_validate_http_registry`, `catalog.py::IMPLEMENTATION_IDS` |
| 2 | 패키지가 **sample 의 스키마**로 검증한다 — `extra="forbid"` 인 `ProjectConfig` 에 `response_review` 키가 없어 cs 의 `project.yaml` 은 스키마부터 실패. `ports.graph_store` 의 `age`·`neo4j` 도 sample 엔 없다 | `acop_basement/core/project_config.py:53-147`, cs `config/project.yaml` |
| 3 | 패키지가 **`acop_basement` 통째**에 묶여 있다 — settings·DB 세션·config/audit/revision store·project_config 를 `acop_basement` 에서 import 한다(11곳). cs 에 설치하면 런타임 코어가 두 벌(`app.core` + `acop_basement.core`) 들어간다 | `acop_composer/*.py` import 목록 |

**고치는 방법 — 패키지를 호스트 주입형으로.** 라우터를 만들 때 호스트(cs)가 자기 `project_config`(스키마·등록표·기본 경로)와 저장소 팩토리(설정·감사·이력·DB 세션)를 넘긴다. `acop_composer` 안의 `acop_basement` import 를 그 주입 객체로 바꾸면 된다. 대상은 `api.py`·`service.py`·`catalog.py`·`auth.py` 와 테스트. 그 뒤 cs 는 복사본 셋(400줄)을 지우고 `create_app()` 에서 주입만 한다 — 그러면 D-011 의 `composer:admin`·이력·복원이 cs 에도 그대로 생긴다. cs 의 Composer 테스트(e2e 17건·scope 계약·openapi 표면)는 패키지 쪽으로 옮기거나 주입 기준으로 다시 쓴다.

`[실측]` **UI 쪽 옵션은 이미 있다.** `final_project_ui/console/profiles.py` 의 `CONSOLE_COMPOSER_MODE = direct | central`(기본 direct) 와 `CONSOLE_COMPOSER_DEPLOYMENT_ID`. 중앙으로 갈 때 UI 는 환경변수만 바꾼다. cs 가 중앙에서 읽는 쪽(`config_source: central`)은 sample 의 `acop_basement/application/config_source.py` 에만 있고 cs 엔 없다 — 그것도 위 주입의 일부로 같이 온다.

**★ 인계 (2026-09-06).** 패키지 주입형 전환 + cs 복사본 제거는 **코드 담당 세션 몫**으로 넘어갔다. 이 문서 세션은 코드를 더 건드리지 않는다. 담당 세션이 볼 것 — 위 표의 셋과 고치는 방법, 그리고 sample에 이미 들어간 구현(커밋 `d05aced`: `composer:admin`·`revision_store.py`·마이그레이션 009·`/revisions`·`/restore`, 전체 494 통과). 끝나면 이 절과 [open-items](../delivery/open-items.md)의 cs 복사본 행을 닫는다.

## 관계

- [D-006](D-006-composer-ownership.md) — Composer 소유는 sample
- [D-007](D-007-central-config-store.md) — 중앙 설정 저장소
- [sample/composer/design-gap.md](../../final_project_sample/wiki/composer/design-gap.md) — 항목 11개 대조
- 원본: `program/plan/A-COP_Composer_v3_불일치_해소안.md`
