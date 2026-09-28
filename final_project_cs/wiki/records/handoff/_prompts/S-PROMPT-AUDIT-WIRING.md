# 구현 지시 — 프롬프트 감사추적 배선 (설계 확정, 구현 착수)

## 0. 배경과 확정된 설계

`wiki/records/reports/debugs/2026-08-17_2340_프롬프트_감사추적_미연결.md` 이 발견한
결함(`prompts`/`llm_calls` 감사추적이 실 런타임에 배선돼 있지 않음)의
구현 단계다. 설계는 `wiki/records/reports/2026-08-18_S-PROMPT-WIRING-DISCUSS_검토.md`
(Codex 교차검증 완료)의 §4 "권장 최종 배선"을 그대로 따른다 — **이 문서에서
설계를 다시 논의하지 않는다.** 아래는 그 설계를 정확한 파일·시그니처
단위로 못 박은 것이다.

프롬프트 콘텐츠(4개 파일)는 이미 Claude 가 직접 작성해 뒀다:
`prompts/order_shipping/answer.v1.md`, `prompts/order_shipping/answer.repair.v1.md`,
`prompts/return_exchange/answer.v1.md`, `prompts/return_exchange/answer.repair.v1.md`.
**이 4개 파일의 내용(정책 문구)은 건드리지 않는다.** 필요하면 읽기만 한다.

## 1. 소유 범위

```
쓰기 대상:
  app/tools/read_tools.py           (register_prompt_files 수정)
  app/infrastructure/llm/openai.py  (OpenAITeamLLM 배선)
  app/composition.py                (connection_factory 주입 지점만)
  app/modules/customer_ops/order_shipping.py   (LLM Protocol + 호출부 4곳 중 2곳)
  app/modules/customer_ops/return_exchange.py  (호출부 4곳 중 2곳)
  scripts/register_prompts.py       (신규)
  tests/unit/tools/test_prompt_registration.py       (신규)
  tests/integration/llm/test_llm_call_audit_wiring.py (신규, 디렉터리도 신규 생성)

★금지: 위 목록 밖의 모든 파일. 특히
  prompts/**  (콘텐츠 4개 파일 — 이미 작성됨, 건드리지 않는다)
  app/application/controller.py  (Controller 의 트랜잭션 경계는 바꾸지 않는다)
  app/core/**, app/domain/**     (Core 는 이 작업과 무관하다)
  app/infrastructure/db/migrations/**  (이번 범위는 마이그레이션 없이 간다 — §5 참고)
```

## 2. `app/tools/read_tools.py` — `register_prompt_files()` 재작성

### 2.1 지금 문제 (실측함, 다시 확인할 필요 없음)

```python
for path in sorted(root.glob("*/**/*.v*.md")):
    text = path.read_text(encoding="utf-8")
    stem, version = path.name.rsplit(".v", 1)
    version = version.removesuffix(".md")
    key = stem   # ★파일명만 — 부모 디렉터리가 빠진다
    ...
    ids.append(create_prompt(conn, prompt_key=key, version=version, template=text,
                              sha256=digest, model_family=model_family))
    # ★active 인자를 안 넘겨서 기본값 False 로 저장된다
```

`prompts/order_shipping/answer.v1.md` 를 읽으면 `key="answer"` 가 되는데
실제 Team 호출은 `"order_shipping.answer"` 를 쓴다 — 등록해도 못 찾는다.

### 2.2 새 동작

- 키 계산: 파일의 **부모 디렉터리 이름 + "." + stem** 으로 만든다.
  예: `prompts/order_shipping/answer.v1.md` → `prompt_key="order_shipping.answer"`.
  `prompts/order_shipping/answer.repair.v1.md` 처럼 stem 자체에 점이
  섞인 경우(`answer.repair`)도 `rsplit(".v", 1)` 로 얻은 stem 을 그대로
  쓰고 디렉터리만 접두어로 붙인다 → `"order_shipping.answer.repair"`.
- **등록 대상을 허용 목록으로 제한한다.** 이번 범위는 정확히 아래 4개
  키만 등록한다 — 다른 디렉터리(`prompts/billing/`, `prompts/technical/`
  등 옛 도메인 잔재)가 있어도 등록하지 않는다.
  ```python
  ALLOWED_PROMPT_KEYS = frozenset({
      "order_shipping.answer", "order_shipping.answer.repair",
      "return_exchange.answer", "return_exchange.answer.repair",
  })
  ```
  글롭으로 찾은 파일의 계산된 키가 이 집합 밖이면 **건너뛰고 경고를
  반환값에 남긴다**(조용히 버리지 않는다 — `CLAUDE.md` §3 "조용한 스킵을
  만들지 않는다"). 함수 반환 타입을 `list[UUID]` 에서
  `tuple[list[UUID], list[str]]`(등록된 id 목록, 건너뛴 경로 목록)로
  바꿔도 좋다 — 호출부(`register_prompts = register_prompt_files` 별칭
  포함)도 함께 맞춘다.
- **등록과 활성화를 하나의 트랜잭션에서, `prompt_key` 별 advisory lock
  아래 수행한다:**
  1. `SELECT pg_advisory_xact_lock(hashtext(%s))` 로 `prompt_key` 잠금
     (트랜잭션 스코프 lock — 커밋/롤백 시 자동 해제).
  2. 같은 `(prompt_key, sha256)` 행이 이미 있으면 재사용(새로 insert 안 함).
     같은 `(prompt_key, version)` 인데 `sha256` 이 다르면 **에러**(같은
     버전 번호로 다른 내용을 등록하려는 것 — `wiki/records/handoff/04` §3 이
     금지하는 상황).
  3. 그 `prompt_key` 의 기존 `active=true` 행을 전부 `false` 로 내린다.
  4. 방금 확정한 행을 `active=true` 로 올린다(신규 insert 시엔 그 행,
     재사용 시엔 그 행).
  5. 처리 끝나면 그 `prompt_key` 에 `active=true` 행이 **정확히 1개**인지
     `SELECT count(*)` 로 확인하고, 아니면 예외를 던져 트랜잭션을 롤백한다.
- 함수 시그니처는 `conn` 을 계속 받되, 내부에서 `with conn.transaction():`
  으로 위 절차를 감싼다(호출자가 이미 트랜잭션을 열고 있으면 중첩
  트랜잭션이 되므로, 이 함수를 부르는 쪽은 트랜잭션 밖에서 `conn` 만
  넘기는 것을 전제로 한다 — §4 의 `scripts/register_prompts.py` 가 그렇게 한다).

## 3. `app/infrastructure/llm/openai.py` — `OpenAITeamLLM` 배선

### 3.1 생성자

```python
def __init__(self, *, connection_factory=None, timeout: float = 60.0) -> None:
    self.connection_factory = connection_factory
    self.timeout = timeout
```

`connection_factory` 가 `None` 이면(테스트 등에서 감사 기록을 안 켜고
싶을 때) 활성 프롬프트 조회·`llm_calls` 기록을 **건너뛰고 지금처럼
인라인 instructions 로 동작**한다 — 이번 배선을 켜지 않은 기존 테스트가
깨지지 않게 하는 하위호환 경로다. 이 경로를 쓰면 `prompt_id` 가 없으므로
`record_llm_call` 도 당연히 안 부른다.

### 3.2 `complete()` 시그니처와 동작

```python
async def complete(self, prompt_key: str, input_text: str, context: dict[str, Any],
                    *, run_id: UUID | None = None) -> dict[str, Any]:
```

`connection_factory` 가 있으면:

1. **짧은 read 트랜잭션**을 열어 `SELECT prompt_id, template FROM prompts
   WHERE prompt_key=%s AND active=true` 를 조회한다.
   - 0행이면: 활성 프롬프트가 없다는 뜻이다. **외부 호출을 하지 않고
     예외를 던진다**(`RuntimeError` 계열 — "이건 fail-closed 다: 활성
     프롬프트 없이 고객에게 나갈 답을 만들지 않는다"). 지금 인라인
     instructions 로 조용히 넘어가지 않는다.
   - 2행 이상이면: 데이터 무결성 문제다. 마찬가지로 예외를 던진다
     (2번 §2.2 의 advisory lock 이 지켜졌다면 여기 도달하지 않아야
     정상이지만, 방어적으로 막는다).
   - 1행이면 그 `prompt_id`/`template` 을 확정하고 트랜잭션을 닫는다
     (읽기만 했으므로 커밋해도 되고 그냥 닫아도 된다).
2. 확정된 `template` 을 instructions 블록으로 써서 지금처럼 JSON 프롬프트를
   조립하고(`input_text`/`context` 는 지금처럼 매 호출 동적 삽입 — 파일
   내용이 바뀌는 게 아니라 instructions 자리에 파일 내용을 쓴다는 뜻이다),
   `asyncio.to_thread(call)` 로 OpenAI 를 부른다.
3. 응답을 성공적으로 받으면 **별도의 짧은 쓰기 트랜잭션**을 열어
   `record_llm_call(run_id=run_id, prompt_id=<1번에서 확정한 id>,
   provider="openai", model=settings.llm_model, response_json=<받은 응답>)`
   을 부른다. 이 트랜잭션은 1번의 조회 트랜잭션과도, 이 메서드를 호출한
   Controller 의 업무 트랜잭션과도 **완전히 분리**돼야 한다(같은 `conn`
   을 재사용하지 않는다 — `connection_factory()` 를 새로 불러 얻는다).
4. OpenAI 호출 자체가 예외를 던지면(timeout, API 오류 등) 지금처럼
   그 예외를 그대로 전파한다. **이번 범위에서는 실패 시도에 대한 감사
   기록은 만들지 않는다**(스키마에 실패 사유 컬럼이 없다 — 검토 리포트
   §1.5 가 이미 이렇게 판단했다. 이 판단을 뒤집지 않는다).
5. `record_llm_call` 자체가 실패하면(DB 에러 등) — **그 예외를 삼키지
   않는다.** LLM 응답은 이미 받았지만 감사 기록이 실패했다는 사실을
   호출자에게 알려야 한다(fail-closed). 다만 이미 받은 LLM 응답을
   버리지 말고, 감사 기록 실패를 별도 예외로 발생시켜 호출자가 무엇이
   문제였는지 구분할 수 있게 한다(예: `AuditWriteError` 를 새로 정의해
   `raise AuditWriteError(...) from db_exc`).

`input_tokens`/`output_tokens`/`latency_ms` 는 OpenAI 응답의 `usage` 필드
(`response.usage.prompt_tokens`/`completion_tokens`)와 `asyncio.to_thread`
호출 전후 `time.monotonic()` 차이로 채운다 — 지금 코드가 이 값을 버리고
있었다는 것도 검토 리포트가 지적한 부분이다.

## 4. `scripts/register_prompts.py` — 신규 배포 명령

```powershell
python -m scripts.register_prompts
```

`app/tools/read_tools.py::register_prompt_files(conn, prompt_root="prompts",
model_family=...)` 를 부르고, 반환된 (등록 id 목록, 건너뛴 파일 목록)을
사람이 읽을 수 있게 출력한다. 건너뛴 파일이 있으면 종료 코드를 0이 아닌
값으로 반환한다(허용 목록 밖 파일이 있다는 건 배포 구성이 예상과 다르다는
신호다 — 조용히 넘기지 않는다). 등록 후 4개 키 전부 `active=true` 행이
정확히 1개씩 있는지 다시 조회해 확인하고, 아니면 실패로 종료한다.

`scripts/seed.py`, `scripts/seed_demo_cases.py` 는 건드리지 않는다 —
프롬프트 등록은 데모 데이터 재현과 무관한 별도 배포 단계다.

## 5. Team 호출부 — `run_id` 전달

`app/modules/customer_ops/order_shipping.py:16-17` 의 `LLM(Protocol)`:

```python
class LLM(Protocol):
    async def complete(self, prompt_key: str, input_text: str, context: dict[str, Any],
                        *, run_id: UUID | None = None) -> dict[str, Any]: ...
```

`_llm_answer()` 안의 두 호출(`order_shipping.answer`,
`order_shipping.answer.repair`)에 `run_id=task.run_id` 를 추가한다.
`return_exchange.py` 도 (Protocol 선언은 없지만) 같은 방식으로 두 호출부에
`run_id=task.run_id` 를 추가한다. 이건 업무 상태를 바꾸는 side effect 가
아니라 "이 호출이 어느 run 소속인지" 알려주는 메타데이터 전달이다
(검토 리포트 §1.3 의 판단 — 뒤집지 않는다).

## 6. `app/composition.py` — 주입 지점

`build_controller()` 안의 `llm = llm if llm is not None else OpenAITeamLLM()`
를 `OpenAITeamLLM(connection_factory=get_connection)` 로 바꾼다. 이 한 줄
외에는 `composition.py` 를 건드리지 않는다.

## 7. 테스트

### 7.1 `tests/unit/tools/test_prompt_registration.py` (신규)

- 4개 실제 파일로 `register_prompt_files()` 를 부르면 정확히 4개 키가
  등록되고 각각 `active=true` 가 1개씩임을 DB 로 확인.
- 같은 함수를 두 번 연달아 불러도(멱등) 행 수가 늘지 않고 active 상태도
  그대로임을 확인.
- 허용 목록 밖의 파일이 섞여 있으면(테스트용 임시 디렉터리에 가짜 파일을
  만들어서) 등록되지 않고 "건너뜀" 목록에 잡히는지 확인.
- 같은 `(prompt_key, version)` 에 다른 내용을 등록하려 하면 에러가 나는지 확인.

### 7.2 `tests/integration/llm/test_llm_call_audit_wiring.py` (신규)

- 실 OpenAI 호출 없이(`monkeypatch` 로 `OpenAI` 클라이언트나
  `asyncio.to_thread` 대상 함수를 가짜로 교체) `OpenAITeamLLM.complete()`
  를 `connection_factory` 주입 상태로 호출하면 `llm_calls` 에
  `prompt_id`(등록된 행의 id)·`run_id` 가 채워진 행이 생기는지 확인
  (`tests/integration/api/test_recheck_before_execution.py` 의 DB 픽스처
  패턴을 참고해도 좋다 — 실제 세부 방식은 이 테스트가 정한다).
- 활성 프롬프트가 없는 `prompt_key` 로 부르면 외부 호출 없이 예외가
  나는지 확인(가짜 OpenAI 클라이언트가 호출 자체를 안 받았는지도 확인).
- `connection_factory=None` 이면 지금처럼 감사 기록 없이 동작하고
  깨지지 않는지 확인(하위호환 경로).

## 8. 검증

```powershell
python -m scripts.register_prompts
python -m pytest tests/unit/tools/test_prompt_registration.py -q
python -m pytest tests/integration/llm/test_llm_call_audit_wiring.py -q
python -m pytest -q
```

전체 테스트가 기존 298건에서 **추가만** 되고(실패 0), 회귀가 없어야 한다.
`-m live` 실 LLM 테스트(`tests/live/test_feedback_classifier_live_e2e.py`)는
이번 계약 범위 밖이라 이 작업으로 깨지면 안 된다 — 만약 이 테스트가 실
OpenAI 호출 경로에서 `OpenAITeamLLM` 을 쓴다면(실제로 쓴다 —
`composition.build_controller()` 경유), **활성 프롬프트가 등록돼 있지
않으면 이 테스트가 실패한다.** `python -m scripts.register_prompts` 를
먼저 실행해야 이 라이브 테스트가 통과한다는 뜻이다 — 리포트에 이 순서를
명시한다.

## 9. 완료 조건

- [ ] 4개 키 등록·활성화가 advisory lock + 단일 트랜잭션으로 동작
- [ ] `OpenAITeamLLM` 이 활성 프롬프트를 조회해 쓰고, 성공 호출마다
      `llm_calls` 에 `prompt_id`+`run_id` 가 채워진 행을 별도 트랜잭션으로 남김
- [ ] 활성 프롬프트 없으면 fail-closed(외부 호출 자체를 안 함)
- [ ] Controller 의 업무 트랜잭션과 감사 기록 트랜잭션이 분리됨(같은
      `conn` 을 공유하지 않음) — 코드로 확인 가능하게(다른 `connection_factory()`
      호출로 얻은 별개의 connection 객체를 씀)
- [ ] `prompts/**` 콘텐츠 파일은 건드리지 않음
- [ ] `python -m pytest -q` 전체 통과, 회귀 없음
- [ ] `wiki/records/reports/2026-08-18_S-PROMPT-AUDIT-WIRING_리포트.md` 제출
      (재현 명령 + 실제 출력 포함, 라이브 테스트 실행 순서 명시)
