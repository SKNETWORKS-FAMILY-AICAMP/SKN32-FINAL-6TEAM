# 구현 지시 — sample 프로젝트 대비 cs 의 격차 조사 (발견만, 수정 금지)

## 0. 배경과 절대 규칙

`final_project_cs`(이 저장소, 커머스 도메인)와 `final_project_sample`
(형제 저장소, 구독·청구 도메인, 경로 `../final_project_sample`)은 같은
기준선(`A-COP_구현계획서`)에서 각자 독립적으로 구현을 진행해 왔다.
사용자가 방금 지시했다: **sample 에서 버전이 올라간(새로 추가되거나
개선된) 부분을 찾아서 cs 로 가져올 계획을 세워라.**

★★★**절대 규칙 — 어길 경우 이 작업 전체가 무효다:**

1. **`../final_project_sample/` 의 어떤 파일도 절대 수정·삭제하지 않는다.**
   읽기만 한다. `git status`/`git diff` 도 그 저장소에는 실행하지 않는다
   (별도 git 저장소일 수 있고, 이 작업은 순수 파일 읽기 비교다).
2. **이 작업(`cs`)의 어떤 코드 파일도 수정하지 않는다.** 이번 지시는
   "무엇이 다른지 찾아서 보고"까지다. 실제로 코드를 가져오는 것은 다음
   단계(사람이 이 리포트를 검토한 뒤 별도 계약)에서 한다.
3. sample 은 **옛 구독·청구 도메인**(billing/subscription/payment 등)이고
   cs 는 **커머스 도메인**(order/shipping/return/exchange)이다. sample 의
   코드를 그대로 복사하면 안 된다 — **무엇이 도메인 무관 로직/설계이고
   무엇이 도메인 특화 콘텐츠인지 구분해서 보고한다.**

## 1. 소유 범위

```
읽기 대상:
  ../final_project_sample/**  (전체, 단 .git/ · __pycache__/ · node_modules/ 등 산출물 제외)
  app/**  (cs, 비교 기준선으로 읽기만)
  docs/**  (cs, 비교 기준선으로 읽기만)

쓰기 대상 (이것 하나만):
  wiki/records/reports/2026-08-18_S-SAMPLE-DIFF-DISCOVERY_리포트.md
```

## 2. 무엇을 조사하는가

### 2-1. `app/modules/customer_ops/` 격차 (최우선)

cs 는 Team 이 2개(`order_shipping.py`, `return_exchange.py`)뿐이고, 각
Team 의 `execute()` 를 보면 **딱 하나의 하드코딩된 시나리오**(배송완료
미수령 → 환불 제안 / 반품 신청 존재 → 반품 제안)만 분기 처리하고,
나머지 모든 문의는 LLM 자유 응답(`_llm_answer`)으로 떨어진다. 즉 `order`
intent 의 issue_code 중 `order_payment_failed`·`order_duplicate_charge`·
`order_change_or_cancel`·`order_other` 나 `shipping` 의
`shipping_delayed`·`shipping_other` 같은 것들은 Team 안에 **전용 판단
로직이 전혀 없다.**

sample 의 `app/modules/customer_ops/`(`feedback_team.py`,
`response_review.py`, `response_review_policy.py`, `team_modules/` 하위
전체)를 읽고:

- sample 의 Team 들은 issue_code/시나리오별로 몇 종류를 실제 분기
  처리하는가? cs 처럼 하나뿐인가, 더 많은가?
- `response_review.py`/`response_review_policy.py` 가 무엇을 하는
  모듈인가 — 이름으로 추측하지 말고 실제로 읽고 설명한다. 이게 cs 의
  두 Team 과 별개로 존재하는 **세 번째 종류의 Team/모듈**인가?
- `team_modules/` 디렉터리 구조가 cs 에는 없다 — 이게 실제 실행 경로에
  배선된 것인지(예: `composition.py` 나 `config/project.yaml` 에서
  참조되는지), 아니면 미완성/미사용 골격인지 sample 코드를 근거로 판단한다.

### 2-2. DoD-29 (Response Generation & Review) — cs 에는 없는 항목

cs 의 `CLAUDE.md` 는 "29번(Response Generation & Review 검증)은 v8 에서
신설된 항목으로 이 구현에서는 아직 평가되지 않았다"고 적어 뒀다. sample
쪽에 `wiki/records/evidence/DoD-29_ResponseGenerationReview.md` 가 있다(확인됨).
그 문서와 관련 코드(`response_review.py` 등)를 읽고:

- DoD-29 가 요구하는 것이 정확히 무엇인가 (v8 §27 원문 인용 가능하면 인용)
- sample 이 이걸 어떻게 구현했는가 (아키텍처 요약, 어떤 파일들이 관여하는가)
- 이 기능이 **도메인 무관**(어느 도메인에나 적용 가능한 일반 메커니즘)인지,
  아니면 sample 의 구독·청구 도메인에 특화된 내용이 섞여 있는지

### 2-3. 그 외 sample 에만 있고 cs 에는 없는 것들

`../final_project_sample` 최상위와 `app/`, `tests/`, `wiki/records/handoff/`,
`scripts/` 를 훑어 cs 에 대응 파일이 없는 것들을 찾는다. 특히:

- `app/presentation/composer_auth.py`, `app/infrastructure/db/migrations/004_agent_runs_active_uniqueness.sql`,
  `005_outbox_dedupe_key_tenant_scoped.sql` — 이름으로 보아 동시성/보안
  버그 수정으로 보인다. 실제로 무엇을 고치는지 읽고 요약한다. **cs 에도
  같은 결함이 있을 가능성**이 있으니, cs 의 대응 코드(`app/application/case_service.py`
  의 `start_run`, `app/infrastructure/messaging/outbox.py`)를 읽고 같은
  문제가 있는지도 판단한다.
- `wiki/records/handoff/_prompts/S-BUGHUNT-*` 계약들 — 최근에 무슨 결함을 잡았는지
  제목과 내용을 훑어 cs 에 해당하는 결함이 있는지도 함께 표시한다.

## 3. 리포트 형식

`wiki/records/reports/2026-08-18_S-SAMPLE-DIFF-DISCOVERY_리포트.md` 에:

1. **요약 표** — 발견 항목마다: sample 의 무엇 / cs 에 있는가 없는가 /
   도메인 무관인가 특화인가 / 포팅 우선순위(높음·중간·낮음) 추정과 근거
2. 각 항목 상세 — 파일 경로(양쪽 다), 무엇이 다른지 구체적으로,
   포팅한다면 무엇을 도메인 번역해야 하는지(예: `payment_id`→`order_id`
   같은 이번 세션에 이미 쓴 대응표를 참고해도 된다 —
   `app/modules/customer_ops/verification_policy.py` 상단 주석에 있다)
3. **포팅 계획 초안** — 우선순위 높은 항목부터, 어떤 순서로 어떤 계약을
   써서 진행하면 좋을지 제안(실행은 하지 않는다)

## 4. 완료 조건

- [ ] `../final_project_sample` 의 어떤 파일도 수정하지 않았다
- [ ] cs 의 리포트 파일 하나만 새로 생성했다
- [ ] 저장 후 `git -c safe.directory='C:/Users/playdata2/Documents/final_workspace' status --short`
      결과를 리포트 끝에 붙인다(실패해도 리포트는 남긴다)
