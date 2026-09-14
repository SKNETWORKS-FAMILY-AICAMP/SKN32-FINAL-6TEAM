# 논의 요청 — 프롬프트 감사추적 배선 설계안 교차검증 (코드 작성 금지)

## 0. 배경

`wiki/records/reports/debugs/2026-08-17_2340_프롬프트_감사추적_미연결.md` 에서 발견한
결함: `prompts`/`llm_calls` 테이블(버전·감사추적용)이 실제 Team 실행 경로에
전혀 배선돼 있지 않다. `create_llm_call`/`record_llm_call`/
`register_prompt_files` 호출부가 저장소 전체에서 0건이고, 실제 LLM 호출
(`app/infrastructure/llm/openai.py::OpenAITeamLLM.complete()`)은 프롬프트를
그 자리에서 조립할 뿐 `prompts` 테이블을 참조하지 않는다.

사용자(제품 책임자)가 다음 방향을 정했다: **"A 안(진짜 템플릿 파일화)을
최대한 진행하고, 그 다음 C 안(하이브리드)으로 간다."** 아래는 그 지시를
구체적인 배선안으로 옮긴 초안이다. **이 문서는 논의용이다 — 코드를 쓰기
전에 Claude 가 놓친 것이 있는지, 더 나은 배선 지점이 있는지 검토해 달라.**

## 1. 실제 코드 사실관계 (직접 grep 으로 확인한 것만 적는다)

- 실제 사용 중인 prompt_key 는 정확히 4개뿐이다:
  `order_shipping.answer`, `order_shipping.answer.repair`,
  `return_exchange.answer`, `return_exchange.answer.repair`
  (`app/modules/customer_ops/order_shipping.py:47,51-52`,
  `app/modules/customer_ops/return_exchange.py:38,42-43`)
- `OpenAITeamLLM.complete(self, prompt_key, input_text, context)` 가 매번
  JSON 프롬프트를 그 자리에서 조립한다(`app/infrastructure/llm/openai.py:17-53`).
  instructions 블록(줄 29-36)은 완전히 고정 문자열이다 — team/시나리오별
  차이가 없다. `prompt_key` 는 지금 메타데이터 라벨로만 쓰인다.
- `prompts` DDL: `(prompt_id, prompt_key, version, template, sha256,
  model_family, active bool default false, UNIQUE(prompt_key,version),
  UNIQUE(prompt_key,sha256))`. ★`active=true` 인 행이 `prompt_key` 당
  **여러 개 동시에 있는 것을 막는 제약이 DB 에 없다** — 애플리케이션이
  알아서 관리해야 한다.
- `llm_calls` DDL: `prompt_id` 가 **NOT NULL** FK — 즉 호출마다 반드시
  유효한 `prompts.prompt_id` 하나를 확정해야 insert 가 가능하다.
- `OpenAITeamLLM` 은 `app/composition.py:173` 에서
  `OpenAITeamLLM()` 인자 없이 생성된다. **DB connection 을 갖고 있지 않다.**
  `Controller` 는 `connection_factory=get_connection` 을 갖고 있지만
  `OpenAITeamLLM` 생성 시 넘겨주지 않는다.
- `TeamTask.run_id` 는 `Controller._task()`(`app/application/controller.py:86`)
  가 `case_service.start_run()` 이 만든 `run_id` 를 실어 Team 에 넘긴다.
  Team 코드는 `self.llm.complete(...)` 를 부를 때 `task.run_id` 를 이미 갖고 있다.
- `Team` 계약(`wiki/records/handoff/04` §0): **"side effect 를 실행하지 않는다"** —
  이게 `llm_calls` 기록(텔레메트리)에도 적용되는 제약인지, 아니면 이
  제약은 `ActionProposal`(환불·반품 등 업무적 부작용)에만 해당하고 감사
  로그 기록은 별개인지 — **이 판단이 이번 논의의 핵심 쟁점 중 하나다.**

## 2. Claude 의 초안 (검토 대상 — 확정 아님)

### 2-1. 콘텐츠 (A안)

`prompts/order_shipping/answer.v1.md`, `prompts/order_shipping/answer.repair.v1.md`,
`prompts/return_exchange/answer.v1.md`, `prompts/return_exchange/answer.repair.v1.md`
4개 파일을 실제로 작성한다(옛 `prompts/billing/`·`prompts/technical/` 12개는
그대로 두거나 `legacy/` 로 옮긴다 — 이 논의에서 결정 X, 별도 트랙).
내용은 `OpenAITeamLLM.complete()` 의 지금 instructions 블록(줄 29-36)을
바탕으로, order/shipping 팀과 return/exchange 팀 각각의 실제 정책적
판단 기준(예: order 팀은 "받지 못한 상품 수량만큼만 환불" 같은
`verification_policy.py` 의 실제 규칙과 어긋나지 않게)을 반영해 쓴다.

### 2-2. 배선 (C안 — 정적/동적 분리)

- `register_prompt_files()` 를 부르는 지점을 새로 만든다 — 후보:
  (a) `scripts/seed.py` 에 한 단계로 추가, (b) 별도
  `scripts/register_prompts.py` 신설 후 배포 절차에 명시, (c) 애플리케이션
  기동 시(`app/composition.py`) 1회 자동 등록. ★**어느 게 맞는지 논의 필요**
  — (c)는 매 프로세스 기동마다 파일을 다시 읽어 sha256 이 같으면
  no-op(멱등)이어야 안전하다.
- `OpenAITeamLLM` 생성자에 `connection_factory`(또는 이미 로드된 프롬프트
  맵)를 주입하고, `complete()` 안에서 `prompt_key` 기준으로 **활성 버전의
  template** 을 읽어 instructions 블록 대신 쓴다. `input_text`/`context`
  는 지금처럼 그 자리에서 조립(동적 부분, C안 그대로).
- 호출 성공 후 `record_llm_call(run_id=?, prompt_id=<위에서 읽은 행의 ID>,
  provider="openai", model=settings.llm_model, response_json=..., ...)`
  를 부른다. ★**`run_id` 를 어떻게 `OpenAITeamLLM.complete()` 까지
  전달할지가 쟁점** — `complete()` 시그니처에 `run_id` 파라미터를 추가
  (Team 코드가 `task.run_id` 를 넘겨줌)하는 안이 제일 단순해 보이는데,
  이러면 Team 코드가 "이 LLM 호출이 어떤 run 에 속하는지"를 명시적으로
  알려주는 모양이 된다 — Team 은 `run_id` 를 몰라도 되는 게 맞는
  설계인지, 지금처럼 이미 `task.run_id` 로 알고 있으니 자연스러운
  연장인지 판단이 필요하다.
- `OpenAITeamLLM` 이 DB 에 쓰는 것 자체(`record_llm_call`)가
  `app/infrastructure/llm/**` 라는 **infrastructure 계층**에서 일어나는
  거라 Team purity 규칙(§0, "Team 은 side effect 를 실행하지 않는다")과
  충돌하지 않는다고 판단했는데 — **이 판단이 맞는지 반박해 달라.**
  `OutboxBrokerAdapter` 도 같은 infrastructure 계층에서 DB 를 쓰는
  선례가 있어 이걸 근거로 들었다(`app/infrastructure/messaging/outbox.py`).

### 2-3. 활성 버전 동시성

`active=true` 가 `prompt_key` 당 여럿일 수 있다는 DDL 제약 부재를 어떻게
다룰지 — 등록 시점에 "이 prompt_key 의 기존 active 를 전부 false 로
내리고 새 걸 true 로 올린다"를 애플리케이션 트랜잭션으로 강제할지,
아니면 부분 unique 인덱스(`CREATE UNIQUE INDEX ... WHERE active`)를
마이그레이션으로 추가할지 — **후자가 더 안전해 보이는데 마이그레이션을
새로 추가하는 게 이 범위에 맞는지 판단해 달라.**

## 3. 요청

1. 위 2번 초안에서 **기술적으로 안 맞는 부분**(시그니처 충돌, Team 계약
   위반, 트랜잭션 경계 문제 등)을 실제 코드를 근거로 지적해 달라.
2. §2-2 의 "등록 호출 지점" (a)/(b)/(c) 중 이 저장소의 기존 관례
   (`scripts/seed.py`, `composition.py` 의 역할 분리)에 제일 맞는 걸
   추천하고 이유를 대라.
3. §2-3 의 active 버전 동시성 처리를 마이그레이션 추가 없이 안전하게
   할 방법이 있는지, 아니면 마이그레이션이 꼭 필요한지 판단해 달라.
4. **코드를 쓰지 마라.** 이 논의의 결과물은
   `wiki/records/reports/2026-08-18_S-PROMPT-WIRING-DISCUSS_검토.md` 리포트
   파일 하나뿐이다. `app/**`·`prompts/**`·`scripts/**` 어떤 파일도
   수정하지 않는다.

## 4. ★환경 주의 (이전 시도가 여기서 죽었다)

이 저장소는 `C:/Users/playdata2/Documents/final_workspace` 를 루트로 하는
git 저장소의 하위 디렉터리다. 샌드박스 사용자 계정이 실제 소유자와 달라
평범한 `git status` 가 `fatal: detected dubious ownership` 로 죽는다.
**git 명령을 쓸 때마다** 아래처럼 `-c safe.directory=` 를 붙여라:

```powershell
git -c safe.directory='C:/Users/playdata2/Documents/final_workspace' status --short
```

★**리포트 파일을 먼저 저장하고, 그 다음에 git 확인을 시도해라.** 확인
명령이 실패해도 이미 저장된 리포트 파일은 남아 있어야 한다 — 검증 실패를
이유로 결과물 자체를 안 쓰고 끝내지 마라.
