# 프롬프트 감사추적 배선 설계안 교차검증

검토 대상: `A안(실제 템플릿 파일화) 후 C안(정적 템플릿 + 동적 입력/context)` 배선 초안

결론부터 말하면, 방향 자체는 타당하다. 다만 현재 초안 그대로 구현하면 프롬프트 등록 키가 런타임 키와 어긋나고, 등록만으로 활성 버전이 생기지 않으며, Controller가 열어 둔 업무 트랜잭션에 LLM 호출·감사 기록을 묶는 문제가 생긴다. 권장 배선은 다음과 같다.

- 템플릿 등록은 애플리케이션 기동이 아닌 명시적인 별도 등록 명령으로 둔다.
- 등록기는 파일의 부모 디렉터리까지 포함해 `order_shipping.answer` 같은 키를 만든다. 등록과 활성화는 하나의 트랜잭션에서 처리한다.
- LLM 어댑터는 활성 템플릿을 조회해 얻은 `prompt_id`를 같은 호출의 감사 기록에 사용한다. 다만 Controller의 장기 트랜잭션 connection을 LLM 어댑터에 공유하지 말고, `connection_factory`로 짧은 DB 트랜잭션을 별도로 연다.
- `run_id`는 `TeamTask`에 이미 있으므로 Team이 이를 LLM 포트 호출에 명시적으로 전달하는 것이 가장 단순하다. 이는 업무 상태를 변경하는 side effect가 아니라 호출의 소유 run을 전달하는 메타데이터다.
- active 단일성은 우선 애플리케이션 트랜잭션 + prompt_key별 advisory lock으로 보장할 수 있다. 다만 여러 등록 경로/운영자가 생길 가능성이 있으면 partial unique index를 별도 마이그레이션으로 추가하는 편이 최종적으로 안전하다.

## 1. 실제 코드와 초안의 불일치

### 1.1 등록기의 prompt_key 산출이 런타임 계약과 맞지 않는다

`app/tools/read_tools.py:118-136`의 현재 구현은 파일명에서 `stem`만 취한다. 따라서 다음 파일은:

`prompts/order_shipping/answer.v1.md` → `prompt_key="answer"`, `version="1"`

하지만 Team이 실제 전달하는 키는 `order_shipping.answer`다(`app/modules/customer_ops/order_shipping.py:47,51-54`, `app/modules/customer_ops/return_exchange.py:38,42-45`). 등록기는 상대 경로의 디렉터리와 파일 stem을 결합해야 한다. 그렇지 않으면 활성 조회가 성공해도 런타임 키로 찾을 수 없다.

또한 현재 `create_prompt(..., active=...)` 호출은 active 인자를 전달하지 않아 기본값 `false`를 사용한다(`app/infrastructure/db/repository.py:56-60`). 따라서 `register_prompt_files()`를 한 번 호출하는 것만으로는 활성 프롬프트가 생기지 않는다. 등록(immutable row 생성)과 활성화(어느 버전을 사용할지 결정)를 명시적으로 분리하거나, 등록 명령 안에서 정책적으로 함께 수행해야 한다.

기존 `billing`·`technical` 파일을 같은 등록기에 넣을 경우에도 부모 디렉터리를 포함해야 한다. 현재 파일명만 키로 만들면 서로 다른 디렉터리의 같은 stem이 충돌할 수 있고, 무엇보다 커머스 Team이 사용하지 않는 레거시 파일을 실수로 활성화할 수 있다. 이번 배선의 등록 대상은 우선 실제 네 개 키로 제한하는 것이 안전하다.

### 1.2 “현재 instructions 블록을 파일로 옮긴다”만으로는 repair 의미가 보존되지 않는다

`OpenAITeamLLM.complete()`의 instructions는 모든 키에 동일하다(`app/infrastructure/llm/openai.py:29-36`). 두 Team의 repair 호출은 `repair_instruction`을 `context`에 추가할 뿐이고, 현재 고정 instructions 자체는 repair 전용 규칙이 아니다(`order_shipping.py:51-54`, `return_exchange.py:42-45`).

따라서 네 파일을 만들 때 공통 schema 문구만 복사하면 `answer`와 `answer.repair`가 실질적으로 같은 템플릿이 된다. repair 템플릿에는 “기존 응답이 유효하지 않으므로 비어 있지 않은 answer를 반환” 같은 목적을 명시해야 한다. 반대로 order/return 정책 문구는 LLM의 안내용으로만 두고, 수량·환불 등 허용 여부의 권위는 계속 `verification_policy.py`와 Controller의 proposal 검증에 둬야 한다. 프롬프트가 업무 상태를 결정하거나 검증을 대체하면 안 된다.

### 1.3 `run_id` 전달은 필요하지만 현재 제안의 호출부 변경 범위가 누락돼 있다

`TeamTask.run_id`는 `Controller._task()`에서 이미 설정된다(`app/application/controller.py:86`). 반면 두 Team의 LLM Protocol/호출은 현재 `(prompt_key, input_text, context)` 세 인자만 사용한다(`order_shipping.py:16-17,47,51`, return Team의 호출부도 동일). 따라서 `complete(..., run_id=task.run_id)`를 채택하려면 다음 계약을 함께 바꿔야 한다.

- 두 Team의 LLM Protocol 또는 공통 포트
- 네 번의 실제 호출부
- 테스트용 fake/mock LLM과 live smoke 호출부
- `OpenAITeamLLM.complete()`의 시그니처

이 변경은 자연스럽다. Team은 이미 task의 run을 알고 있고 `TeamResult`에도 run_id를 되돌린다. run_id를 명시적으로 넘기는 것이 암묵적 전역 상태나 context에 숨기는 것보다 추적 가능성이 높다. 다만 LLM 포트가 모든 호출자에게 감사 저장소의 존재를 노출하지 않도록 이름과 문서에서는 “호출 소유 run 식별자”로 취급하는 것이 좋다.

### 1.4 infrastructure에 감사 기록을 두는 것은 Team purity 위반이 아니다. 단, 경계를 분명히 해야 한다

계약 문서 `wiki/records/handoff/04_Team_모듈_계약.md:0`의 side effect 금지는 Team이 환불·반품 실행이나 상태 전이를 하지 않고 `ActionProposal`만 반환한다는 의미로 읽는 것이 실제 코드와 일치한다. 실제 상태 변경은 Controller가 `transition_case()`와 action request 저장을 통해 수행한다(`app/application/controller.py:...`).

`OpenAITeamLLM`은 원래도 외부 OpenAI 호출을 담당하는 infrastructure adapter다. 여기에 호출 텔레메트리 저장을 붙이는 것은 Team이 DB를 직접 쓰는 것과 다르며, `OutboxBrokerAdapter`가 infrastructure에서 DB를 쓰는 선례와도 일관된다. 따라서 “LLM adapter 내부에 감사 기록”은 허용 가능한 선택이다.

단, 이것을 근거로 Team이 DB connection을 받아 직접 `record_llm_call()`을 부르게 해서는 안 된다. Team은 계속 LLM 포트만 호출해야 한다. 또 `llm_calls`는 업무 상태 변경과 달리 운영 관측 데이터이지만, 저장 실패를 LLM 결과 성공으로 숨길지 여부는 정책으로 정해야 한다. 감사추적이 필수라면 기록 실패를 호출 성공으로 간주하지 않고 명시적으로 실패시키는 fail-closed 정책이 필요하다.

### 1.5 Controller의 열린 트랜잭션에 LLM 외부 호출을 포함시키면 안 된다

`Controller.run_case()`는 `with self.connection_factory() as conn` 안에서 `with conn.transaction()`을 열고, 그 안에서 `await self.team_executor.execute(task)`를 수행한다(`app/application/controller.py:112` 이후). 즉 현재 경로는 외부 OpenAI 호출 동안 DB 트랜잭션이 열린 상태다.

초안처럼 `OpenAITeamLLM`에 Controller의 connection을 직접 넘기면 다음 문제가 생긴다.

- 네트워크 지연만큼 업무 트랜잭션이 열린다.
- `asyncio.to_thread()`에서 외부 호출을 수행한 뒤 같은 connection에 쓰는 것은 connection의 thread 사용 규칙과 경합 위험을 만든다.
- Team 결과가 timeout/예외가 되어 Controller 트랜잭션이 rollback되면, 같은 트랜잭션에 넣은 `llm_calls`도 함께 사라진다.
- 반대로 감사 기록을 별도 트랜잭션으로 쓰면 Controller의 업무 rollback과 독립적으로 남길 수 있다.

권장 방식은 `OpenAITeamLLM`에 `connection_factory`를 주입하는 것이다. 활성 prompt 조회를 호출 직전에 짧은 read transaction으로 수행하고, 외부 호출 후 `record_llm_call()`도 별도의 짧은 transaction으로 저장한다. 두 단계 사이에 prompt 행을 삭제하거나 비활성화해도 이미 확정한 `prompt_id`가 기록에 사용되므로 FK와 재현성이 유지된다. `prompts` 행은 덮어쓰지 않고 새 version을 추가해야 한다.

이 구조에서는 “호출 시도 자체”도 감사할 것인지 결정해야 한다. 현재 초안의 “호출 성공 후 기록”은 OpenAI 예외·timeout·JSON parse 실패를 누락시킨다. `llm_calls.response_json`은 nullable이므로 최소한 실패 시도 기록을 남길 여지는 있지만, 실패 코드/오류 메시지 전용 컬럼은 없다. 이번 범위에서 스키마를 넓히지 않는다면 성공 응답 기록부터 명확히 하고, 실패 감사는 별도 설계 항목으로 남기는 것이 정직하다. `input_tokens`, `output_tokens`, `latency_ms`도 현재 `complete()`가 response usage를 버리고 있어 실제 값을 기록하려면 response metadata를 어댑터 내부에서 수집해야 한다.

## 2. 등록 지점: (b) 별도 명령을 권장

추천 순서는 **(b) `scripts/register_prompts.py`를 별도 명령으로 만들고 배포/초기화 절차에서 명시적으로 실행**하는 것이다.

이 저장소에서 `scripts/seed.py`는 `demo` tenant와 고객·주문·배송·반품 fixture를 넣는 데 목적이 있고, 하나의 transaction에서 데모 데이터를 재현한다. 프롬프트 등록은 데모 데이터가 아니라 배포 artifact의 버전 등록이며, 운영 데이터와 lifecycle도 다르다. 따라서 (a)에 섞으면 seed 재실행이 템플릿 rollout을 암묵적으로 수행하는 문제가 생긴다.

`composition.py`는 concrete adapter와 Team을 조립하는 composition root다(`build_controller()`에서 `OpenAITeamLLM()`과 registry를 생성한다). DB에 파일을 쓰는 (c)는 조립 시점의 숨은 mutation이 된다. 매 프로세스 기동마다 파일을 읽는 방식은 여러 인스턴스의 동시 등록, DB 일시 불가로 인한 기동 실패, 현재 작업 디렉터리에 의존하는 prompt 경로, 예상하지 못한 활성화 변경을 초래할 수 있다. 멱등성만으로 이런 운영 의미가 해결되지는 않는다.

별도 명령은 다음 책임을 갖는 편이 좋다.

1. 허용된 네 개 키와 파일 경로를 검증한다.
2. UTF-8 내용의 sha256과 version을 계산한다.
3. `(prompt_key, version)`·`(prompt_key, sha256)` 충돌을 검증한다. 같은 version인데 내용이 다르면 실패시킨다.
4. 등록과 active 전환을 하나의 transaction에서 수행한다.
5. 모든 네 키에 정확히 하나의 active 행이 생겼는지 검증하고, 아니면 명령 전체를 실패시킨다.

배포 pipeline에서 이 명령을 앱 기동 전에 실행하고, 런타임은 “활성 프롬프트가 없거나 여러 개면 fail closed”하도록 하는 구성이 적합하다. 등록 명령을 seed와 별개로 두되, 개발 환경 bootstrap 문서에서 두 명령의 실행 순서를 함께 안내할 수는 있다.

## 3. active 버전 동시성

### 3.1 마이그레이션 없이 가능한 최소 안전책

단일 등록기와 통제된 운영 경로만 존재한다면 마이그레이션 없이도 애플리케이션에서 안전하게 처리할 수 있다.

- 등록/활성화 전체를 하나의 DB transaction으로 묶는다.
- `prompt_key`마다 PostgreSQL transaction-level advisory lock을 획득한다. lock key는 prompt_key의 안정적인 해시로 만든다.
- 해당 키의 기존 active를 모두 false로 만든 뒤 새 version을 insert하고 true로 만든다.
- 이미 같은 version·같은 hash가 있으면 그 행을 재사용하되 active 전환을 수행한다.
- 런타임 조회는 `WHERE prompt_key = ? AND active = true`로 하고, 0개 또는 2개 이상이면 임의로 고르지 말고 오류로 중단한다.

이 방법은 모든 writer가 같은 lock 규칙을 지킨다는 전제에서만 안전하다. 기존 active를 내리고 새 행을 올리는 두 SQL을 transaction 밖에서 나누면 안 된다. 또한 lock을 모르는 수동 SQL, 다른 배포 도구, 별도 관리자 화면이 있으면 애플리케이션 보장은 깨진다.

### 3.2 partial unique index의 판단

마이그레이션은 이번 배선의 선행 조건으로 반드시 필요한 것은 아니다. 위의 단일 writer + advisory lock을 먼저 적용하면 현재 스키마에서도 운영을 시작할 수 있다. 그러나 DB가 불변식의 최종 방어선이 되려면 다음 형태의 별도 마이그레이션을 추가하는 것이 바람직하다.

`UNIQUE(prompt_key) WHERE active`인 partial unique index

추가 전에는 기존 중복 active를 먼저 탐지하고 하나를 선택해 정리해야 한다. 인덱스가 있으면 두 인스턴스가 동시에 서로 다른 version을 active로 만들려는 경우 적어도 commit 시점에 한쪽이 실패하므로, 애플리케이션 transaction/lock과 함께 쓰는 것이 좋다. 인덱스만으로 “기존 active를 내리고 새 active를 올리는 rollout 전체”의 의미가 자동으로 보장되는 것은 아니므로 등록 transaction은 여전히 필요하다.

따라서 판단은 **지금 당장 배선을 막는 필수 마이그레이션은 아니지만, 다중 인스턴스·수동 운영까지 고려한 완료 조건으로는 partial unique index를 권장**이다. 스키마 변경을 이번 작업 범위에 넣지 않기로 하면 advisory lock과 fail-closed 조회를 명시적 불변식으로 남겨야 한다.

## 4. 권장 최종 배선

1. 네 실제 prompt_key에 대응하는 네 파일을 만들고, repair 파일에는 repair 목적을 실제로 포함한다. 정책 문구는 참고 지침이며 Controller 검증을 대체하지 않는다.
2. 별도 등록 명령에서 부모 디렉터리 + 파일 stem으로 키를 계산한다. 예: `order_shipping/answer.v1.md` → `order_shipping.answer`.
3. 등록 명령이 각 파일의 hash/version 충돌을 검사하고, prompt_key별 lock 아래에서 등록·active 전환을 transaction으로 수행한다.
4. `OpenAITeamLLM`은 `connection_factory`를 받아 활성 행을 조회하고, 그 행의 `prompt_id`와 template을 고정한다. 활성 행이 없거나 복수면 외부 호출을 하지 않는다.
5. Team의 LLM 포트 계약에 `run_id`를 명시적으로 전달한다. Team은 DB를 직접 만지지 않고, LLM adapter가 호출·감사 저장을 담당한다.
6. 호출 기록은 Controller의 장기 transaction과 분리된 짧은 transaction에서 저장한다. 성공/실패 시도 기록의 범위와 감사 저장 실패 정책은 구현 전에 확정한다.
7. 이후 테스트에서 네 키의 active 단일성, prompt_id FK, `run_id` 연결, 일반 호출 + repair 호출의 두 기록, 등록 재실행 멱등성을 검증한다.

이 배선이면 Team의 업무 side effect 금지와 감사 추적을 분리하면서도, 실제 LLM 호출마다 사용한 immutable prompt version을 `llm_calls.prompt_id`로 복원할 수 있다.
