# sample 의 LLM 감사 추적이 끊겨 있다 (2026-09-06)

`CLAUDE.md` §1 이 요구하는 것:

> `llm_calls` prompt_id FK 로 어떤 프롬프트가 만든 답인지 추적

**이 저장소에서는 일어나지 않고 있다.** 실측:

| | sample | final_project_cs |
|---|---|---|
| `prompts` 행 | **0** | 7 |
| `llm_calls` 행 | **0** | **762** (전부 `response.generate`) |

## 무엇이 빠졌나 — 배선 하나

부품은 다 있다.

- `llm_calls` 테이블 — `001_schema.sql:21`
- `record_llm_call()` — `acop_basement/tools/read_tools.py:91`
- `register_prompt_files()` — 같은 파일 70행
- 프롬프트 파일 12개 — `prompts/{billing,technical,judge}/`

**아무도 `record_llm_call()` 을 부르지 않는다.** LLM 어댑터
(`acop_basement/infrastructure/llm/openai.py`)가 DB 를 아예 보지 않는다 —
`connection_factory` 를 받지도 않는다. 등록 실행기도 없다(cs 에는
`scripts/register_prompts.py` 가 있다).

## ★그런데 배선하면 깨진다 — 키가 안 맞는다

cs 방식으로 어댑터를 배선하면 "프롬프트를 DB 에서 찾아 쓰고, 없으면 fail-fast"
가 된다. 그런데 이 저장소는 **요청하는 키와 파일에서 나오는 키가 다르다.**

| 코드가 요청 | 파일에서 나오는 키 |
|---|---|
| `billing.answer` · `billing.answer.repair` | `classify_billing` · `explain_billing` · `propose_refund` |
| `technical.answer` · `technical.answer.repair` | `classify_entitlement` · `diagnose_entitlement` · `propose_support_action` |

키 규칙도 두 저장소가 다르다:

```python
key = stem                              # sample — 파일 이름만
key = f"{path.parent.name}.{stem}"      # cs   — 폴더까지 붙인다
```

cs 규칙을 써도 `billing.explain_billing` 이 되지 `billing.answer` 가 되지 않는다.
**어느 규칙으로도 안 맞는다.**

지금까지 안 드러난 이유는 단순하다 — 어댑터가 DB 를 안 뒤졌다.

## 왜 지금 고치지 않았나

요청하는 쪽이 `examples/customer_ops/{billing,technical}.py` 다. 이 둘은
**"Team 플러그인 구조가 실제로 동작했다" 는 예시로 보존**된 코드이고 10주 착수
목록에 없다(`CLAUDE.md` §5 「Agent Team — 예시 보존」). 굴러가는 기능이 아니다.

이름을 맞추는 일(파일을 코드에 맞추거나, 코드를 파일에 맞추거나)은 **제품
판단**이고, 보존용 예시를 위해 프롬프트 체계를 새로 세울 값어치가 크지 않다고
봤다. 릴리스 대상인 cs 에서는 이미 제대로 돌고 있다.

## 그래서 남는 사실

★**이 저장소의 `llm_calls` 는 비어 있고, 앞으로도 그럴 것이다.**
"감사 추적이 되고 있다" 고 읽으면 안 된다. 그 말을 여기 적어 두는 것이 이
리포트의 목적이다.

## 되살리려면 무엇이 필요한가

1. `examples/` 의 Team 이 요청하는 키와 `prompts/` 파일 이름을 **한쪽으로 맞춘다**
2. 키 규칙을 정한다(파일 이름만 / 폴더까지) — cs 와 맞출지도 함께
3. 배포 프롬프트 허용 목록을 정한다(cs 의 `ALLOWED_PROMPT_KEYS` 에 해당)
4. 어댑터에 `connection_factory` 를 넣어 조회·기록을 배선한다
5. `scripts/register_prompts.py` 를 만들어 등록·검증한다

★cs 에는 1~5 가 다 있다. 옮겨올 코드는 있고, **막고 있는 것은 1번뿐**이다.
