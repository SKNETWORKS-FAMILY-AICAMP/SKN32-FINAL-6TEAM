# S-RESPONSE-REVIEW-TEAM — Response Generation & Review Team 신설 (DoD-29)

## 배경

`../plan/A-COP_구현계획서_v8.md` §8-B(407~419행, v7.1 도입·v8 계승)와 §27
DoD-29 가 요구하는 새 Team Module 이다. **읽기 전용** — 그 문서는 고치지
않는다. 이 프롬프트가 그 요구를 이 저장소의 실제 계약·코드 형태로 옮긴 것이다.

이 저장소(`final_project_sample`)는 basement 지만, `app/modules/customer_ops/`
는 이미 도메인이 허용된 자리다(`billing.py`, `technical.py` 가 이미 거기
있다). 이 Team 도 같은 자리에 만든다 — **`app/core/**`, `app/domain/**` 는
건드리지 않는다**(basement 순수성, `tests/architecture/test_basement_is_domain_free.py`
가 검사한다).

## 계약 — 반드시 지킬 것

1. **계약을 바꾸지 않는다.** `TeamResult`(`app/core/contracts.py`)에 새
   필드를 추가하지 않는다 — `ConfigDict(extra='forbid')` 다. v8 §8-B 가
   지정한 매핑을 그대로 쓴다:
   - `final_response_text` → `answer`
   - `status` → `outcome`
   - `retry_count`, `review_history` → `decisions[]` (list of dict)
   - 반려 사유 → `warnings[]`
   - `escalation` → `outcome='escalated'` + `next_action=NextAction.ESCALATE`
2. **`TeamModule` Protocol** 을 그대로 구현한다(`wiki/records/handoff/04_Team_모듈_계약.md`
   §0 의 3가지 — manifest+execute, side effect 없음, 근거 없이 답 안 함).
3. **Registry 등록만으로 "구현 완료"라고 하지 않는다** — v8 §8-B 원문:
   "등록된 capability 가 있어도 실행 가능한 module·fixture·contract test 가
   없으면 구현 완료로 세지 않는다." 반드시 아래 "검증"의 테스트가 실제로
   통과해야 한다.

## 내부 흐름 (v8 §8-B 그대로)

톤 결정(규칙, 결정론) → GEN 초안(LLM) → REV 검증 → 완료. **최대 3회 재시도**.

REV 는 4항목을 검사하고, **결정론 검사를 LLM 검사보다 먼저** 실행한다
(자기채점 방지 논거는 LLM 판단에만 해당한다):

1. **과잉약속** — 금칙어 사전 대조(결정론). 사전은 도메인 선언
   (아래 "만들 것" 참조)이 갖는다 — basement 코드에 금칙어 문자열을
   하드코딩하지 않는다.
2. **근거 인용** — `refund_amount`·`policy_ref` 값이 실제 사실과 맞는지
   대조(결정론). ★이미 있는 `app/core/verification.py`(범용 대조 규칙
   엔진)와 `app/modules/customer_ops/verification_policy.py`(도메인 어휘
   선언) 패턴을 **재사용**한다 — 새 대조 엔진을 또 만들지 않는다.
3. **개인정보** — 정규식 검사(결정론). **발견 시 재시도 없이 즉시
   `escalated`** — 이건 다른 실패와 다르게 특별 취급한다.
4. **톤** — LLM 판정. 사람 라벨이 필요해 재시도 사유에서 **제외**하고
   경고(`warnings[]`)로만 남긴다(v8 §8-B 그대로 — 재시도를 유발하지 않는다).

지표(로그/decisions 에 남길 것): 1차 통과율, 에스컬레이션 비율(목표 5%
이하), 반려 사유 분포, 개인정보 노출율(목표 0%) — 이 프로젝트 규모에서는
`decisions[]` 에 남기는 구조화 필드로 충분하다. 별도 대시보드는 범위 밖.

## 만들 것

1. `app/modules/customer_ops/response_review_policy.py` — 도메인 선언:
   금칙어 사전(`frozenset[str]`), PII 정규식 목록, 톤 프로파일 설명.
   `verification_policy.py` 와 같은 스타일(basement 는 규칙만, 여기가 어휘).
2. `app/modules/customer_ops/response_review.py` — `ResponseGenerationReviewTeam`
   클래스. `TeamManifest`:
   ```python
   manifest = TeamManifest(
       team_id='response_generation_review', display_name='Response Generation & Review Team',
       contract_name='a_cop.team_task', supported_contract_versions=['1.0'],
       capabilities=['response.generate_review'],
       accepted_case_types=[],  # ★Controller 라우팅 대상 아님 - VOC/feedback_team 과 같은 이유
       required_context=['case_state', 'policy', 'db_facts', 'history'],
       allowed_tools=['read.policy'], knowledge_scope=['response_review'],
       max_steps=4, active=True, implementation_revision='...')
   ```
   ★`accepted_case_types=[]` 로 두는 이유 — 이 Team 은 v8 §8-B 가 말하는
   "모든 Case 의 최종 응답 문장을 검증"하는 **횡단 관심사**이지, billing/
   technical 처럼 Controller 가 `case_type` 으로 직접 라우팅하는 대상이
   아니다(`FeedbackAnalyticsTeam` 이 같은 이유로 `accepted_case_types=[]`
   를 쓴다 — `app/modules/customer_ops/feedback_team.py` 참고). 이번
   스코프는 **이 Team 단독의 GEN→REV 계약과 동작**을 증명하는 것까지다
   — Controller 를 고쳐 모든 Team 의 출력에 이걸 자동으로 물리는 배선은
   범위 밖(별도 결정 필요 — 리포트에 "이건 안 했다"고 명시할 것).
3. `LLM` Protocol 은 기존 Team 들(`billing.py`)과 같은 패턴으로 주입받는다
   (`llm: LLM | None = None`). LLM 미주입 시 결정론 검사만으로 동작하는
   경로도 있어야 한다(테스트가 실 LLM 없이 돌 수 있게).

## 하지 않을 것

- `app/core/contracts.py`, `app/domain/events.py` 변경 — 계약 불변
- Controller 를 고쳐 이 Team 을 자동으로 모든 Case 에 물리는 것 — 범위 밖
- `config/project.yaml` 의 `teams` 배열에 `active: true` 로 실제 등록하는
  것 — 이건 사용자가 나중에 판단할 몫이다. Registry 에 등록 가능한
  **코드**까지만 만들고, 선언 파일 자체는 건드리지 않는다(원한다면 예시로
  `active: false` 항목을 하나 추가하는 건 괜찮다 — 강제하지 않는다)
- 실제 LLM 호출 실행 — 이 환경의 Codex 샌드박스는 외부 네트워크가 막혀
  있다(`wiki/records/handoff/05_분업_규칙.md` §2-1). Fake/주입 LLM 으로 테스트를
  작성하고, "실 LLM 검증은 Claude 가 직접 돌려야 한다"고 리포트에 명시한다

## 검증

```powershell
python -m pytest tests/contract -q                    # Protocol + Core 격리 위반 없음
python -m pytest tests/unit/teams -q                   # 시나리오별 TeamResult 일관성
```

새로 만들 테스트(`tests/unit/teams/test_response_review_team.py` 가칭):
- GEN→REV 흐름이 실행되고 정상 응답이면 `completed`+`answer`+`evidence`
- 금칙어 위반 → 재시도(최대 3회) 후에도 실패하면 `escalated`, 그 전에
  통과하면 재시도 결과가 `decisions[]` 에 남는지
- `refund_amount`/`policy_ref` 불일치 → 위와 같은 재시도·최종 처리
- **개인정보 검출 → 재시도 없이 즉시 1회 만에 `escalated`** (다른 위반과
  다르게 재시도를 안 하는 게 핵심 — 반드시 assert 로 재시도 횟수가 0인지
  확인한다)
- 결정론 검사가 LLM 검사보다 먼저 실행되는지 — 예: 결정론 위반이 있는
  입력에서 LLM(가짜 LLM)의 호출 횟수가 0인지 확인
- 톤 문제만 있는 경우 재시도하지 않고 `warnings[]` 에만 남는지

## 만들 것 (문서)

- `wiki/records/evidence/DoD-29_ResponseGenerationReview.md` — 재현 명령 + 실제
  출력 원문 포함(`RULE.md` §4.0 형식)
- `wiki/records/handoff/04_Team_모듈_계약.md` 에 "3. Response Generation & Review
  Team" 절 추가(기존 1·2 항목과 같은 표 형식) — **계약을 코드보다 먼저
  고친다는 원칙(RULE.md §3.5)은 이미 어겼으니(이 프롬프트가 계약 역할을
  했다), 최소한 문서를 코드와 같은 커밋에서 동기화한다**

## 완료 기준
```powershell
python -m pytest -q   # 전체가 통과해야 한다 (2026-08-17 기준 355 passed 에서 시작)
```
`wiki/records/reports/` 에 리포트 제출. 만든 파일 목록, 재현 명령과 실제 출력,
"Controller 자동 배선은 범위 밖" 같이 의도적으로 안 한 것을 명시한다.
