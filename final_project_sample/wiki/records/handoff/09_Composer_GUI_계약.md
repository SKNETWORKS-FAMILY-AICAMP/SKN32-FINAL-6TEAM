# 09 — Composer GUI 계약 (제작 단계 구성기)

> ★**폐기됨 (2026-08-18).** `/ui/composer`는 인증이 전혀 없는 채로 이 앱(고객
> 접근 가능 포트)에 물려 있었다 — 실측으로 확인. `app/presentation/ui/composer.py`
> 삭제, `mount_ui()`에서 라우터 제거, `config/project.yaml`의 `composer_ui` 모듈
> 제거 완료. 같은 기능(모듈·Team·Port 편집)은 이제 별도 프로그램
> `final_project_ui`가 대상의 **인증된** `/composer/current`·`/validate`·`/apply`
> API(scope 필요, 계약: `13_Composer_쓰기채널_계약.md`)로만 제공한다. 이 문서의
> 나머지는 옛 설계 기록으로 남긴다 — 되살리지 않는다.

---


> 운영 화면(`/ui/{cases,approvals,voc,admin}`)과 **목적이 다르다.**
> 운영 화면은 *돌아가는 시스템을 본다.* Composer 는 *무엇을 조립할지 정한다.*

- 경로: `/ui/composer`
- 모듈 키: `composer_ui` — **기본 `true`** (제작 중인 저장소이므로)
- 구현: `app/presentation/ui/composer.py`
- 단일 입력: `config/project.yaml`

---

## 1. 켜고 끄기

지금은 **켜져 있다.** 이 저장소는 제작 중이고, 구성기는 제작 단계의 도구다.
배포 산출물을 만들 때 끄면 된다:

```yaml
composer_ui:
  enabled: false      # 배포용
```

★**재기동해야 반영된다.** 선언은 기동 시 `app/composition.py` 가 읽는다.

### ★기본값을 테스트에 묶지 마라

전에 `test_composer_is_404_when_disabled` 가 `config/project.yaml` 을 **그대로 읽어**
404 를 단언했다. 그래서 **테스트를 통과시키려면 저장소 기본값이 꺼짐이어야 했고,
정작 쓰려는 구성기가 계속 404 였다.** 기본값을 켜려는 시도가 테스트 실패로 되돌려졌다.

검사하려던 성질은 **"선언이 false 면 라우트가 없다"** 이지
**"저장소 기본값이 false 다"** 가 아니다. 지금은 임시 선언으로 그 성질만 검사한다.

> 테스트가 검사하는 것이 의도한 성질인지 확인하라.
> 아니면 테스트가 제품을 잘못된 방향으로 끌고 간다.

---

## 2. 무엇을 바꿀 수 있고 무엇을 못 바꾸나

### 2-1. 모듈 — 켜고 끈다 (7종)

| 모듈 | 끄면 |
|---|---|
| `vector_rag` | 정책 검색이 없다. ★평가에서 grounding 3.98 → 0.00 |
| `graph_store` | 관계 조회 없음 |
| `a2a_executor` | Team 을 원격으로 실행하지 못한다 |
| `mcp` | 개인 AI 접속 경로 없음 |
| `voc` | 일일 배치·급증 탐지 없음 |
| `ops_ui` | 운영 화면 4종이 404 |
| `composer_ui` | ★**이 화면 자신이 404** |

★`composer_ui` 는 **자기 자신을 끌 수 있다.** 의도한 설계다
(GUI 도 필요 없으면 빠질 수 있어야 한다). 다만 **끄면 GUI 로는 되돌릴 수 없고**
`config/project.yaml` 을 손으로 고쳐야 한다 → 체크박스 옆에 경고를 띄운다.

### 2-2. Port — 구현을 갈아 끼운다 (3종)

| Port | 선택지 | 상태 |
|---|---|---|
| `team_executor` | `local` · `a2a` | 둘 다 구현됨 |
| `message_broker` | `outbox` · ~~`redis_streams`~~ | outbox 만 구현 |
| `graph_store` | `sql` · ~~`age`~~ · ~~`neo4j`~~ | sql 만 구현 |

★**어댑터가 없는 선택지는 화면에 내지 않는다.** 고를 수 없는 것을 보여 주면
"고를 수 있는데 왜 안 되지" 가 된다.

★**`a2a` 에는 순서가 있다** — `a2a_executor` 모듈을 먼저 켜고 저장해야
`team_executor` 선택지에 나타난다. 모듈이 꺼진 채 port 만 `a2a` 면 조립이 깨진다.
화면이 그 이유를 적는다.

> ★한때 `a2a` 를 `(미구현)` 으로 표기했다. **거짓이었다** —
> `A2ATeamExecutor` 는 구현돼 있고 테스트를 통과한다.
> 라벨이 사실과 다르면 쓸 수 있는 것을 못 쓴다(설계 원칙 §3).

### 2-3. Team — 추가·제거한다 (개수 가변)

이것이 이 화면의 존재 이유다. **Team 이 3개였다가 2개가 되거나 4개가 될 수 있다.**

- `Team 추가` → `active: false` 인 자리를 만든다.
  **세부 구현은 그 팀이 나중에 채운다.** 등록만 되고 라우팅되지 않는다
- `제거` → 행을 뺀다
- `active` 체크 → 라우팅 대상에 넣는다

★**`active: true` 인데 `implementation_ref` 를 import 할 수 없으면 저장을 거부한다.**

```
검증 실패
team 'new_team' implementation_ref 'app.modules.placeholder:PlaceholderTeam'
cannot be imported: No module named 'app.modules.placeholder'
→ 검증에 실패한 선언은 저장하지 않았습니다.
```

이래야 "GUI 에서는 켰는데 기동하면 죽는" 상태가 안 생긴다.

### 2-4. 컴포넌트 — ★끌 수 없다 (9종)

| 컴포넌트 | 왜 선택지가 아닌가 |
|---|---|
| Case lifecycle · `transition_case()` | 상태 변경의 단일 진입점 |
| Contract models | Team 계약 그 자체 |
| Team Registry | capability 해석과 라우팅 |
| Context Broker | 예산과 `degraded` 신호 |
| DB repository / session | Source of Truth |
| Outbox publisher | 트랜잭션과 이벤트 발행의 원자성 |
| Case service | run/resume 중복 실행 방지 |
| Controller | 실행 루프 |
| Settings / guardrails | 설정의 단일 출처 |

이것들을 끄면 **A-COP 이 아니게 된다.** 화면에 읽기 전용으로 띄우되
"구성기에서 제거할 수 없습니다" 를 함께 적어 **토글로 오해하지 않게** 한다.

---

## 2-5. 구조도 — 실행 순서대로

화면 아래에 **Case 가 실제로 지나가는 순서**로 컴포넌트·모듈을 그린다.

```
1  입력             REST /v1 (고정)          · mcp (모듈)
2  Case 생성·전이    transition_case() · case_events · Contract models   (전부 고정)
3  분류             인라인 분류 (고정)        · voc (모듈)
4  컨텍스트 조립      Context Broker (고정)    · vector_rag · graph_store (모듈)
5  라우팅            Team Registry (고정)
6  실행             TeamExecutorPort (고정)  · LocalTeamExecutor · a2a_executor (모듈)
7  Agent Team       ★개수가 바뀌는 유일한 자리 (인스턴스)
8  제안·승인          Controller · Case service · Human Approval   (전부 고정)
9  발행             Outbox · Settings/guardrails                 (전부 고정)
10 관측             ops_ui · composer_ui (모듈)
```

표기:

| 테두리 | 뜻 |
|---|---|
| 실선 + 파란 좌변 | **고정** — 컴포넌트. 끌 수 없다 |
| 점선 + 초록 좌변 | **모듈** — 위 체크박스로 켜고 끈다 |
| 점선 + 노란 좌변 | **인스턴스** — 개수가 바뀐다 (Agent Team) |
| 흐림 + 취소선 | 지금 **꺼져 있다** |

★**정적인 그림이 아니라 현재 선언의 투영이다.**
`vector_rag` 를 끄고 저장하면 그 자리가 즉시 취소선으로 바뀐다.
그림과 실제 조립이 어긋나면 그림이 거짓말을 하기 때문에, 선언에서 직접 그린다.

★7번이 이 화면의 존재 이유다. 나머지 자리는 **있거나 없거나** 지만
Agent Team 만 **몇 개인지**가 바뀐다.

---

## 3. 저장 절차 — 검증이 먼저다

```
폼 입력
  → 임시 파일(.composer.validation.yaml) 로 쓴다
  → ★정식 로더 load_project_config() 로 읽는다   ← 검증은 여기서 일어난다
      · 스키마
      · team_id 중복
      · port 값 유효성
      · active Team 의 implementation_ref import
  → 통과하면 원본을 .bak 로 백업하고 덮어쓴다
  → 실패하면 임시 파일을 지우고 원본은 그대로 둔다
```

★**검증기를 따로 만들지 않았다.** 기동 때 쓰는 로더를 그대로 쓴다.
검증기와 실제 로더가 다르면 "GUI 는 통과했는데 기동은 실패" 가 생긴다.

---

## 4. 실측 (브라우저 왕복)

| 조작 | 결과 |
|---|---|
| `a2a_executor` 켜고 저장 | YAML 에 `enabled: true` 기록. `team_executor` 선택지에 `a2a` 등장 |
| `team_executor: local → a2a` | YAML 에 `a2a` 기록 |
| `Team 추가` → `shipping_support` 저장 | YAML 에 `active: false` 로 기록됨 |
| 그 Team 을 `active: true` + 없는 ref 로 저장 | ★**거부** — `No module named 'app.modules.nonexistent'`, 저장 안 함 |
| `제거` 후 저장 | YAML 에서 사라짐 |

★거부 시 **원본 파일은 건드리지 않는다.** 임시 파일에 써서 검증하고, 통과했을 때만 덮어쓴다.

---

## 5. 한계 — 아직 못 하는 것

- ★**재기동이 필요하다.** 저장은 선언만 바꾼다. 무중단 재조립은 없다
- ★**Team 의 내용을 만들지 않는다.** 자리(`team_id`·`implementation_ref`)만 만들고
  구현 파일은 사람이 쓴다. 스캐폴딩 생성 기능은 없다
- **되돌리기가 `.bak` 한 단계뿐이다.** 버전 이력이 없다
- **`composer_ui` 를 끄면 GUI 로 못 돌아온다** (경고만 띄운다)
- `knowledge_scope`·`allowed_tools`·`max_steps` 같은 **manifest 내부는 못 고친다** —
  그건 Team 구현이 선언하고 Registry 가 계약으로 검사한다
