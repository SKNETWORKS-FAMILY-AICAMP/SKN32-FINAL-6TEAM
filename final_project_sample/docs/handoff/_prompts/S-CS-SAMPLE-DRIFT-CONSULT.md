# S-CS-SAMPLE-DRIFT-CONSULT — cs가 sample보다 앞선 3개 기능을 어떻게 할 것인가 (의견만, 수정 금지)

## 이것도 설계 자문이다 — 어떤 파일도 고치지 마라, 새 파일을 만들지 마라

읽기 전용 샌드박스로 실행된다. 그래도 명시한다: `final_project_sample`도
`final_project_cs`도 **어떤 파일도 건드리지 마라.** 산문 의견만 낸다.

## 배경 — 정확히 확인한 사실 (Claude가 이번에 직접 대조한 것)

이 저장소(`final_project_sample`)는 basement(Core/Team 계약,
Composer 쓰기채널 인프라)를 **먼저 검증하는 참고 구현체**이고,
`final_project_cs`(형제 저장소, `../final_project_cs`)가 **실제 릴리스
대상**이다(`final_project_sample/CLAUDE.md` "릴리스 대상은
final_project_cs다... sample에서 먼저 만든 Composer 쓰기채널을 cs로
이식하는 관계"). 즉 정상적인 흐름은 **sample → cs**다.

그런데 사용자가 "cs가 앞선 것도 있다"고 지적했고, 대조해보니 사실이었다
— **역방향**으로 cs가 sample보다 먼저 만든 것 3가지:

### 1. 프롬프트 감사추적 배선 (cs만 있음)

- `final_project_cs/CLAUDE.md` (2026-08-18 상태표, "★프롬프트 감사추적
  배선" 행): `register_prompt_files()`가 실제로 `prompts`/`llm_calls`
  테이블에 배선됐다 — advisory lock 기반 active 유일성, `OpenAITeamLLM`이
  활성 프롬프트를 실제로 조회해서 쓰고, Controller 트랜잭션과 분리된
  트랜잭션으로 `llm_calls`(prompt_id·run_id·tokens·latency)를 기록하며,
  활성 프롬프트가 없으면 fail-closed 한다.
- `final_project_cs/scripts/register_prompts.py` — 이 스크립트 자체가
  sample엔 없다.
- 대조 결과: `final_project_sample/acop_basement/infrastructure/llm/openai.py`의
  `OpenAITeamLLM.complete()`는 `prompt_key`를 받기만 하고, `prompts`
  테이블에서 활성 버전을 조회하지도, `llm_calls`에 기록하지도 않는다.
  `scripts/register_prompts.py`도 sample엔 없다.
- `prompts (prompt_key, version) UNIQUE + sha256 immutable`이라는 계약
  자체는 **양쪽 다** 원래 v6 §22 기준선에 있었다(`create_prompt()` 함수는
  두 저장소가 바이트까지 동일하다) — **차이는 그 계약을 실제로 "쓰는"
  런타임 배선이 cs에만 있다는 것.**

### 2. DoD-29 Response Generation & Review — Controller 자동배선 (cs만 있음)

- 두 저장소 다 `app/modules/customer_ops/response_review.py`를 갖고
  있고, 둘 다 `TeamManifest`의 `accepted_case_types=[]`로 선언돼 있다
  (파일 자체는 거의 동일 — Team 단독 계약은 같다).
- 그런데 `final_project_cs/tests/integration/controller/
  test_response_review_wiring.py`를 열어보면, cs의
  `app/application/controller.py`가 `ResponseReviewConfig`라는
  설정 객체와 `Controller._maybe_review()`라는 메서드를 갖고 있다 —
  1차 Team 실행 결과를 review Team에 자동으로 두 번째 패스로 태우는
  실제 오케스트레이션 메커니즘이다(`enabled` 플래그로 켜고 끌 수 있다).
- `final_project_sample`엔 이 메서드도, 이 config 클래스도 없다 — sample의
  설계 기록(`docs/reports/2026-08-18_Composer_v2_ResponseReview_검수.md`
  류 문서)은 "Controller 자동배선은 `config/project.yaml` 미등록 — 사용자
  판단 몫"이라고 명시적으로 **보류**해뒀다.
- cs는 그 판단을 이미 내려서 구현했다.

### 3. prompt registration 고도화 (cs만 있음, 1과 겹치지만 별도 산출물)

- `register_prompt_files()`의 키 계산 로직(부모 디렉터리 포함)이
  버그였다가 고쳐진 이력이 cs의 `docs/history/2026-08-17_2350_
  handoff계약_동기화_및_프롬프트감사_발견.md`,
  `docs/reports/2026-08-18_S-PROMPT-AUDIT-WIRING_리포트.md`에 남아있다.
  이건 §1의 배선과 한 묶음으로 만들어진 산출물이지만, "프롬프트 파일을
  스캔해 DB에 등록하는 도구"라는 점에서 도메인과 무관한 **basement급
  유틸리티**로 보일 수 있다.

## 왜 이게 그냥 "두 프로젝트가 따로 발전했다"로 넘길 일이 아닐 수도 있는가

- sample은 오늘(2026-08-19) `acop_basement`/`acop_composer` 두 pip
  패키지로 쪼개졌다(`final_project_sample/docs/handoff/15_basement_버전_
  배포_계약.md`) — 목표는 "basement가 **범용·재사용 가능한 core**가
  되어, cs 같은 릴리스 대상이 그걸 그대로 pip install 해서 쓴다"는
  것이다(`final_project_sample/docs/handoff/10_도메인_교체_가이드.md`).
- 그런데 §1(프롬프트 감사추적 배선)과 §2(Controller 자동배선)는 **읽어보면
  도메인 특화 로직이 아니라 core/basement급 메커니즘처럼 보인다** —
  `OpenAITeamLLM`이 활성 프롬프트를 조회하는 것도, `Controller`가 2차
  review pass를 도는 것도 특정 쇼핑몰 도메인(order/shipping 등)과 무관한
  일반 메커니즘이다. 그렇다면 이게 **cs의 로컬 도메인 코드가 아니라
  basement(sample→cs 방향)로 흘러야 했던 것을, cs가 먼저 필요해서 자기
  로컬에 만들어버린 상황**일 수 있다.
- 만약 그렇다면: 앞으로 `acop_basement`를 pip install 하는 **제3의
  프로젝트**(VISION-10이 그리는 미래)는 이 두 메커니즘을 못 받는다 —
  cs 로컬에만 있으니까. sample의 "범용 basement" 주장과 실제로 안
  맞는 상태다.
- 반대로: 이게 사실은 **cs 특유의 운영 요구**(예: 실 LLM 비용 추적이
  cs 릴리스에선 당장 필요했지만 sample은 아직 mock 평가만 쓴다든가)일
  수도 있다 — 그렇다면 basement로 끌어올릴 필요 없이 지금처럼 cs
  로컬에 남는 게 맞다.

## 물어보는 것

1. **§1(프롬프트 감사추적 배선)과 §2(Controller 자동배선)는 성격상
   basement(core, 도메인 무관)에 속하는 것으로 보이는가, 아니면
   cs만의 운영 판단(도메인/제품 특화)으로 남아도 되는 것으로 보이는가?**
   실제 코드(두 파일 다 읽을 수 있다 — 경로는 위에 적었다)를 근거로
   판단해라. `basement`/`도메인` 경계 판단 기준은
   `final_project_sample/docs/handoff/10_도메인_교체_가이드.md` §0을
   참고해라(basement는 도메인 어휘를 몰라야 한다는 원칙).
2. **지금 아무것도 안 하면(사용자가 이번엔 "이건 안 건드림"이라고
   지시했다) 어떤 위험이 쌓이는가?** — sample과 cs가 서로 다른
   `Controller`/`OpenAITeamLLM` 구현을 영구히 갖게 되는 것의 실제
   비용(버그가 한쪽에서 고쳐지면 다른 쪽은 모른다, "sample이 참고
   구현체"라는 문서상 주장이 거짓이 된다 등)을 구체적으로 짚어라.
3. **선택지 비교** — 다음 중 무엇을 권고하는가, 또는 다른 안이 있는가.
   각 안의 실제 비용(누가, 무엇을, 어떤 순서로)과 리스크(cs는 이미 실
   테스트가 도는 릴리스 대상이라 잘못 건드리면 회귀 위험이 크다는 점을
   반영해라)를 같이 적어라.
   - (a) 지금은 그대로 둔다 — 문서(`docs/handoff/10` 또는 새 문서)에
     "이 두 가지는 cs가 sample보다 앞서 있고, 아직 basement로 역이식
     안 됐다"고 정직하게 기록만 해서 잊히지 않게 한다.
   - (b) sample의 `acop_basement`에 이 두 메커니즘을 **새로
     설계·구현**해 basement 버전을 올리고(minor, 기존 계약과 호환되는
     기능 추가 — `docs/handoff/15` SemVer 기준), 이후 cs가 원할 때
     `acop_basement`를 pip install 해서 자기 로컬 구현을 대체하도록
     경로를 열어둔다(cs 쪽 실제 교체는 별도 스트림, 지금은 하지 않는다).
   - (c) 반대로 cs의 구현을 **그대로 복사**해 sample의 basement에
     이식한다(코드 재작성 없이 포팅) — 리스크와 이 방식이 왜 위험할
     수 있는지(cs 코드가 아직 basement 순수성 검사를 거친 적이 없다,
     cs는 여전히 `app/` 단일 패키지 구조라 basement/도메인 경계가
     sample과 다를 수 있다)를 짚어라.
   - (d) 다른 안.
4. **지금 당장 뭘 해야 하나** — 사용자 지시는 "이건 안 건드림"이다.
   그 지시를 존중하면서도 "나중에 또 잊힌다"를 막으려면 최소한 뭘
   기록해둬야 하는지 구체적으로 제안해라(예: `docs/vision/`에 새 항목,
   `docs/handoff/10`에 한 절 추가 등 — 이 저장소가 실제로 쓰는 관행에
   맞춰서).

## 출력 형식

산문. 각 권고에 근거(`파일:줄번호`, 저장소 이름을 명시)와, 그 권고가
틀릴 수 있는 조건을 같이 적어라. "좋습니다"로 끝내지 마라 — 두 프로젝트를
지금처럼 갈라놓는 게 나은 이유가 있다면 그것도 정직하게 적어라.
