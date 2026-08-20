# 검사 지시 — 이 저장소가 "무엇이든 올릴 수 있는 Basement" 인가

## 0. 목적

이 프로젝트의 주장은 **"모듈형 Basement"** 다. 즉 Agent Team 을 갈아 끼우고
도메인을 바꿔도 Core 가 버텨야 한다. **그 주장이 코드로 성립하는지 검사하라.**

★**코드를 고치지 마라. 이건 검사 작업이다.**
결함을 발견하면 고치지 말고 **리포트에 적어라.** 그게 산출물이다.

기준: `../A-COP_브리핑_A2A_Graph반영_최종.html` **§6 모듈형 Basement 4축**
- **Core Runtime** — Local/A2A Team 을 동일 Case lifecycle 안에서 조정
- **Agent Interoperability** — Personal AI 의 Tool 접근과 독립 Agent 의 Task 협업을 분리
- **Context & Knowledge** — Vector 는 유사성, Graph 는 연결 관계
- **Agent Team Modules** — 동일 Team Contract 아래 내부 구성·배포는 독립

## 1. 소유 범위

```
docs/reports/  (리포트만)
docs/history/
```
★**그 밖 전부 읽기 전용.** `app/**`, `tests/**`, `eval/**` 를 **수정하지 마라.**

## 2. 검사 항목 — 각각 **근거(파일:줄번호)** 를 대라

### 2-1. Team 을 갈아 끼울 수 있는가 (핵심)

1. 새 Agent Team 을 추가하려면 **몇 개 파일을 건드려야 하나?**
   실제로 세어라 — Registry 등록, manifest, tool allowlist, prompt, DI 배선…
2. Core(`app/core/**`)가 특정 Team 을 **이름으로 알고 있는가?**
   `git grep -n "Billing\|Technical" app/core/` 로 확인하라. 나오면 결합이다
3. `TeamModule` Protocol 만 만족하면 등록되는가, 아니면 다른 곳도 고쳐야 하는가
4. ★**Team 을 제거하면 Core 가 깨지는가?**

### 2-2. 도메인을 바꿀 수 있는가

1. `customer_ops` 를 다른 도메인(예: HR, 물류)으로 바꾸려면 Core 에서 무엇을 고쳐야 하나
2. Case 상태 12종(`app/domain/events.py`)이 **고객운영 전용 어휘**인가,
   일반 업무 Case 에도 쓸 수 있는 어휘인가
3. `guardrails.yaml` 의 수치가 도메인 종속인가

### 2-3. 저장소·LLM·전송을 갈아 끼울 수 있는가

Port/Adapter 분리가 실제로 되어 있는지 **import 방향**으로 확인하라:
1. Core 가 `psycopg`·`openai` 같은 **구체 라이브러리를 직접 import** 하는 곳이 있나
2. `MessageBrokerPort` / `TeamExecutorPort` / `GraphStorePort` 의 구현체를
   **Core 가 직접 import** 하는가, 주입받는가
3. LLM Provider 를 바꾸려면 몇 곳을 고치나

### 2-4. 경계가 실제로 지켜지는가

1. `app/core/**` → `app/modules/**` import: **0건이어야 한다** (검사 후 실측 보고)
2. `app/core/**` → `app/presentation/**` import
3. `app/core/**` → `app/infrastructure/**` import
4. Team 이 `transition_case()` 를 직접 부르는 곳이 있나 (있으면 위반)
5. `customer_cases` 를 `transition_case()` 밖에서 UPDATE 하는 곳

### 2-5. A2A 로 Team 을 원격 분리할 수 있는가

1. Controller 가 `TeamExecutorPort` 로만 Team 을 부르는가 (`app/application/controller.py`)
2. `LocalTeamExecutor` → `A2ATeamExecutor` 교체 시 **다른 곳을 고쳐야 하나**
3. `TeamResult` 계약이 Local/Remote 양쪽에서 동일한가

### 2-6. 확장 시 걸림돌 (솔직하게)

- 지금 구조에서 **가장 먼저 부러질 곳**은 어디인가
- Team 이 5개, 10개로 늘면 무엇이 문제가 되나
- 아직 Port 가 없어서 하드코딩된 지점은 어디인가

## 3. 산출물

`docs/reports/2026-08-13_Basement_구조검사_v2.md`

형식:
```markdown
# Basement 구조 검사

## 판정 요약
| 축 | 판정 | 근거 |
|---|---|---|
| Core Runtime | 성립/부분/미성립 | 파일:줄 |
...

## 2-1. Team 교체 가능성
- 관측: <파일:줄번호와 실제 코드>
- 판정: <몇 개 파일을 고쳐야 하는지 숫자로>
- 걸림돌: <있으면>
...

## ★가장 먼저 부러질 곳
...

## 확인하지 못한 것
...
```

★**규칙**
- 모든 주장에 **`파일:줄번호`** 를 붙여라. 근거 없는 평가를 쓰지 마라
- ★**"잘 되어 있다" 로 끝내지 마라.** 이 검사의 가치는 **약한 곳을 찾는 것**이다
- 좋게 보이려고 결함을 빼지 마라. 검수 담당이 같은 검사를 다시 돌린다
- 숫자로 답할 수 있는 것은 숫자로 (예: "새 Team 추가 시 고칠 파일 4개")

## 4. 하지 말 것
- ❌ 코드 수정
- ❌ 근거 없는 평가
- ❌ 결함 은폐 / "문제 없음" 으로 마무리
- ❌ `docs/reports/` 밖 파일 생성

## ★재검사 (2026-08-13 2차)

1차 검사 이후 두 가지가 고쳐졌다. **그 효과를 확인하는 것이 이번 검사의 핵심이다.**

| 고친 것 | 무엇이 달라졌나 |
|---|---|
| Controller._capability() | 하드코딩 → **Registry 조회**. 1차에서 "가장 먼저 부러질 곳" 으로 지목한 지점 |
| Core 격리 | pp/core/transition.py → pp.presentation import 제거. 계약 테스트 범위를 presentation·infrastructure·pplication 까지 확대 |

★**1차 판정(4축 전부 "부분")이 이제 어떻게 바뀌는지 다시 판정하라.**
바뀌지 않았다면 **왜 여전히 부분인지** 근거를 대라. 좋게 바꾸지 마라.

★1차에서 "새 Team 추가 시 최소 2개 파일" 이라고 셌다. **지금 다시 세어라.**
