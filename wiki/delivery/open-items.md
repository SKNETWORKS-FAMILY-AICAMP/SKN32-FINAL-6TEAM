---
type: plan
title: 열린 항목
description: 아직 안 끝난 일과 미확인 사항. 완료된 것은 여기 없다
status: draft
tags: [release]
owners: [human:미배정]
domain: travel
domain_note: 남은 일 목록이다. 커머스에서 넘어온 항목이 섞여 있다
---

# 열린 항목

`[실측]` `A-COP_남은작업_인수인계.md`(2026-08-24 작성)에서 **살아 있는 것만** 추출.

**완료된 것은 안 적는다.** 원본은 완료 항목까지 다 담아서 무엇이 남았는지 찾기 어려웠다.

## 이 문서로 % 를 낼 때의 규칙

`[2026-09-08 신설]` 루트 `CLAUDE.md` 「보고 형식」이 **분모를 밝히지 않으면 `%` 를
쓰지 말라**고 한다. 그런데 이 문서는 닫힘을 `~~취소선~~`·`닫힘`·`완료`·`확인됨`·
`확정 확인` 다섯 가지로 적고 있어서 **기계로 셀 수가 없었다.** 규칙을 정한다.

| | |
|---|---|
| **분모** | 아래 다섯 절의 표 행 — 「사람이 해야 하는 것」·「문서 쪽 열린 항목」·「측정 대기」·「아직 안 정한 것 셋」·「[2026-09-03] 인수인계에서 남은 것」 |
| **분모에서 빼는 것** | 「확인 완료로 닫은 것」(절 이름이 곧 판정) · 「v2 계약 네 항목 실측 대조」(세부 표) · 머리글 행 |
| **닫힘 판정** | **첫 칸이 `~~취소선~~`** 이거나 값에 `닫힘` 이 있다 |

★**닫을 때는 첫 칸에 취소선을 친다.** 값 칸에만 "확인됨"이라 적으면 사람은 알아보지만
집계에서 열린 것으로 세어진다 — 실제로 2026-09-08 에 그 이유로 셋을 잘못 셌다.

## 사람이 해야 하는 것

실행 순서와 명령은 [todo-user.md](todo-user.md)에 있다. 여기는 목록이다.

| 항목 | 왜 AI가 안 하나 |
|---|---|
| `git push -u origin workspace` | **AI 세션은 푸시를 실행하지 않는다** |
| ~~MVP 대상 도시~~ | **닫힘 (2026-09-10). 서울이다.** 기술 제약이 아니라 검증 주장의 분모를 만드는 일이다 → [D-016](../decisions/D-016-scope-narrowing-reasons.md). ★**도시를 기다리던 조사 넷이 이제 시작될 수 있다** |
| ~~지원 언어 범위~~ | **닫힘 (2026-09-10, v11 §0-4).** 우리는 **한국어 하나**만 내고 **고객 언어 번역은 고객 에이전트 몫**이다. ★**번역 품질을 보증하지 못하므로 「다국어 지원」이라고 말하지 않는다** |
| ~~**★ wiki 저장소 전환**~~ | **닫힘 — 이미 실행됐다.** `[실측 2026-09-07]` 사용자 호출로 같은 날 243개 이동(`d976932`). 이 줄은 실행 뒤에도 "부르면 실행"으로 남아 있었다 → [D-012](../decisions/D-012-cutover-timing.md) |

## 미확인

`[미확보]` 정직하게 적는다.

| 항목 | 상태 |
|---|---|
| (지금 미확인 항목 없음) | 아래 「확인 완료로 닫은 것」 참고 |

## 확인 완료로 닫은 것

| 항목 | 결과 |
|---|---|
| VOC 데이터 전처리 8종 | **2026-09-01 전부 완료** |
| `implementation_ref` allowlist 제한 | **확인됨.** `KNOWN_IMPLEMENTATION_REFS`로 코드에 있고 Composer HTTP 경로에만 적용 |
| Composer 범위 재검토 | → [D-CS-001](../../final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md) 외 Composer 계열 결정 |
| **v2 계약 문서 — 네 가지를 하나로 맞추기** | **2026-09-06 닫음.** 맞춘 게 아니라 **구현을 하나로 만들어** 맞출 것이 없게 했다 — Composer 구현이 패키지 `acop_composer` 하나뿐이고 cs·sample 이 각자 호스트 어댑터로 자기 것만 넘긴다(v9 §8-D). 실측 대조 ↓ |
| **UI가 import할 패키지 이름** | **2026-09-06 확정 확인: `acop_composer_ui`.** 콘솔 `console/composer.py:26` 이 실제로 이것을 import 하고 설치돼 있다(`final_project_sample/packages/acop_composer_ui/`). 대상 코드·스키마를 안 끌어오는 것은 게이트가 지킨다(`tests/architecture/test_composer_ui_package_boundary.py`) |

### v2 계약 네 항목 실측 대조 (2026-09-06)

| 맞춰야 했던 것 | cs | sample |
|---|---|---|
| endpoint 이름 | **같은 패키지가 정의한다** — `/apply` `/catalog` `/changes` `/current` `/restore` `/revisions` `/toggle` `/validate` | 동일(같은 코드) |
| `config_revision` | 계약 **1.1** · `config_revision`·`active_revision`·`desired_revision`·`reload_state`·`reload_error` | 동일 |
| 인증 scope | `composer:{read,validate,write,admin}` · `ops:{introspect,reload}` | 동일 |
| 감사 필드 | **같은 패키지가 쓴다** — `actor`·`changed_fields`·`correlation_id`·`event`·`operation`·`resource_type`·`instance_id`·`previous_revision`·`revision`·`reason`·`subject`·`timestamp`·`idempotency_key`·`implementation_id`·`result` | 동일(같은 코드) |

★`revision` **형식**만 일부러 다르다 — cs 는 sha256 64자, sample 은 12자. 맞추면
기존에 발급된 `base_revision` 이 전부 어긋나 저장이 409 로 튕긴다. revision 은 그
대상 안에서만 비교되므로 형식이 달라도 되고, "통일" 은 그 자체로 가치가 아니다.

★`cs 안에 자기 composer 라우터가 있나: False` — 사본이 없으므로 **갈라질 자리가
없다.** "두 사본을 계속 같게 유지한다" 는 지킬 수 없는 약속이었고, 실제로
2026-09-06 이전에 이미 갈라져 있었다(cs 4개 / sample 8개).

근거: `final_project_cs/wiki/records/reports/2026-09-06_Composer를_패키지로_들어냈다.md`,
계약 `final_project_cs/wiki/records/handoff/13`·`14`.
| **쿠팡 배송이력 5건 중 4건만 수집** | **★ [2026-09-04] 확인됨 — 정상 동작.** `preprocess_stats.json`을 열어 보니 8건 중 취소 3건(배송 자체 없음) 제외 5건 중 1건이 송장번호 미기재. 데이터 결손 아님 → [`../../datasets/wiki/scraper-notes.md`](../../datasets/wiki/scraper-notes.md) |

## ★ [2026-09-08] 여행 전환이 이 목록의 절반을 흔든다

`[실측 2026-09-08]` 위 규칙으로 세면 **열린 항목 8/33 = 24%** 다. 그런데
**8건 중 셋이 쇼핑몰 골든셋에 묶여 있다.** 2026-09-08 도메인 전환(v10)으로
그 분모 자체가 바뀌는지 확인해야 한다 — 아니면 없어질 일을 붙들게 된다.

| 열린 항목 8건 | 여행 전환 뒤에도 유효한가 |
|---|---|
| `git push` | 유효 — 도메인 무관 |
| judge 루브릭이 "답이 없을 때"를 안 정한다 | **유효** — 평가 하네스는 도메인이 바뀌어도 그대로 쓴다 |
| `degraded` 가 세 가지를 뭉친다 | **유효** — 러너 결함이다 |
| `rescore.py` 가 `total` 을 검증 안 한다 | **유효** — 같다 |
| 검토·승인 1건 소요시간 (순위 2) | 유효 — 사람 검토 시간이라 도메인과 덜 묶인다 |
| **골든셋 사람 라벨 24건** | `[미확보]` **골든셋이 쇼핑몰 72건이다.** 여행 골든셋을 새로 만들면 이 24건은 대상이 아니다 |
| **골든셋 `persona` 필드 담당** | `[미확보]` 같은 이유 |
| **축 1 공개 통계 확보 여부** | `[미확보]` 쇼핑몰 시장 조사다. 여행은 `_CS_페인포인트_웹조사_2026-09-08.md` 가 새로 있다 |

★**셋을 지우지 않고 `[미확보]` 로 둔다.** 여행 골든셋을 새로 만들 것인지,
쇼핑몰 골든셋을 유지하며 도메인을 넓힐 것인지 아직 안 정해졌다
(`final_project_cs/wiki/records/evidence/` 의 `DoD-EVAL-DATASETS` 판정도
"golden/holdout 이 쇼핑몰 도메인" 이라고 적혀 있다). **그 결정 전에는 이 셋의
유효 여부를 말할 수 없다.**

## ★ [2026-09-09] 구현 카탈로그를 UI 에서 관리한다 — 안이 나왔고 결정이 남았다

`[실측]` 사용자 지시 2026-09-09. 상세와 갈래 넷은 [../decisions/D-015-implementation-catalog.md](../decisions/D-015-implementation-catalog.md).

**무엇이 문제인가.** 새 Team 을 붙일 때 코어에 손으로 유지하는 목록 **둘**을 고쳐야 한다 — `app/core/project_config.py` 의 `KNOWN_IMPLEMENTATION_REFS` 와 `app/composer_host.py` 의 `IMPLEMENTATIONS`. **안 고치면 조립은 뜨는데 Composer 로 저장이 안 된다**(422). 2026-09-09 에 실제로 그렇게 됐고 **e2e 하나에서만 터졌다.**

**권고안.** 목록을 UI 로 옮기는 게 아니라 **목록을 없앤다** — 배포된 `app/modules/` 를 스캔해 카탈로그를 계산한다. `TeamManifest.display_name` 이 이미 계약에 있다.

★**콘솔에서 ref 를 직접 등록하는 안은 기각했다.** [D-013](../decisions/D-013-declarative-team.md) 이 임의 import 를 원격 코드 실행으로 판정했고, 게다가 **모듈 파일이 서버에 없으면 어차피 import 가 안 되므로 배포 없이 Team 을 추가하게 해 주지도 않는다.**

| 누구 | 무엇 |
|---|---|
| **cs 코드 세션** | 스캔 방식 구현. 스캔 범위(`app/modules/`)를 **선언에 둬야** 나중에 코어를 안 고치고 넓힌다. `description` 을 manifest 에 넣을지 결정 |
| **UI 세션** | **① 드리프트 보기**(배포됐는데 선언에 없는 것 / 선언에 있는데 파일이 없는 것) — 이번 사고가 정확히 첫째였고 아무 화면에도 안 보였다 · ② 표시 문구 편집 · ③ 카탈로그 항목의 출처 표시 |
| **결정 필요** | 표시 문구를 manifest(코드)에 둘지 Composer 선언(데이터)에 둘지. 운영자가 고치려면 데이터여야 하는데 그러면 Team 이 자기 이름을 말하지 못한다 |

## 문서 쪽 열린 항목

| 항목 | 어디 |
|---|---|
| **★여행 전환 설계 — 결정 7건이 사람 몫으로 남았다** `[2026-09-10]` 설계의 `[미확보]` 24건을 **실측 7건 · 결정 8건**으로 닫고, **혼자 정할 수 없는 7건**만 남겼다 — 슬러그를 v10 에 올릴지 · `business_subject` 사양(①한 Case 에 하나 / ②서버가 객체 id) · 알림 전달 계약(에이전트와 맞출 것) · Activity 쇼핑 제외 21종 · 무료 활동 판정 규칙 · 감시 소스 표본 · 강사가 말한 "에이전트". ★**앞 둘이 급하다** — 적용 순서 맨 앞이라 안 정하면 뒤가 막힌다 | [../../program/plan/A-COP_여행전환_아침보고_2026-09-10.md](../../program/plan/A-COP_여행전환_아침보고_2026-09-10.md) |
| **`select_capability` 훅이 옛 축에 묶여 있다 — 안 A 를 적용하면 조용히 멈춘다** `[실측 2026-09-09]` 여행 팀 여섯 중 **`mobility` 하나만** 이 훅을 구현했는데, 첫 줄이 `if intent != "mobility"` 라 **`intent` 를 객체 종류로 가정한다.** 안 A(요청 종류)를 넣으면 `None` 을 돌려주고 **예외 없이 기본 capability 로 떨어진다** — 지연·결항이 와도 `mobility.check_route` 가 불린다. 같은 문장으로 두 축을 넣어 확인했다(`mobility` → `mobility.exception`, `incident_report` → `None`). ★가드를 `intent` 요청 종류 기준으로 바꾸고, **`activity` 에도 넣어야 한다** — 시연이 `propose_change` 로 가야 하는데 기본은 `check_feasible` 이다 | [../../program/plan/A-COP_여행_분류어휘와_라우팅_명세.md](../../program/plan/A-COP_여행_분류어휘와_라우팅_명세.md) §6 |
| **★라우팅 축 — 값까지 정해 뒀다. 적용만 남았다 (코드 세션 몫)** `[실측 2026-09-09]` 안 A(두 축)를 **시뮬레이션으로 검증**했다 — `case_type`=객체 종류, `intent`=요청 종류로 넣으면 **6팀 전부 라우팅되고**, 요청 종류가 capability 네임스페이스와 안 맞아도 **안 좁힐 뿐 실패하지 않는다**. `case_type` 은 `issue_code` 접두에서 뽑으므로 **계약이 안 바뀐다**. 제안한 `ISSUE_CODES` 17개가 **17/17 라우팅 성공**. 고칠 자리는 셋 — 분류 어휘 2줄 · 컨트롤러 2줄 · 가드 테스트. ★가드 테스트는 **일부러 깨뜨려 빨간 것을 본 뒤** 고쳐야 한다(지금 것이 통과하면서 못 잡고 있었다) | [../../program/plan/A-COP_여행_분류어휘와_라우팅_명세.md](../../program/plan/A-COP_여행_분류어휘와_라우팅_명세.md) |
| ~~**★라우팅 축이 어긋나 있다 — 결정 필요**~~ **명세로 대체됨 (2026-09-09).** 원래 문구: `[실측 2026-09-09]` 레지스트리는 `resolve(case_type, intent)` 로 **두 축**을 받는데 `controller.py:71` 이 `case_type=intent` 로 **하나로 뭉개서** 넘긴다. 그래서 `intent` 가 곧 Team 선택 값이 되고, Team 은 **객체 종류**(`activity`·`booking`…)를 받으므로 **v11 §5-A 의 다섯 라벨(일정 제출/사건 신고/…)로는 라우팅이 안 된다** — 실행해 확인했다(객체 종류 3/3 성공, v10 라벨 3/3 실패). ★**설계는 이미 두 축이다. 컨트롤러가 그걸 안 쓰고 있을 뿐이다.** `issue_code` 가 이미 객체 접두를 달고 있어 (`order_payment_failed`) **계약을 안 바꾸고도 풀 수 있다.** 이게 정해져야 분류 어휘를 무엇으로 바꿀지 안다 | [../../program/plan/A-COP_지속관리루프와_알림_설계.md](../../program/plan/A-COP_지속관리루프와_알림_설계.md) |
| **★여행 Case 가 지금 라우팅되지 않는다 — 코드 세션 몫** `[실측 2026-09-09]` 여행 Team 6개가 등록·해석까지 다 됐는데(`config/project.yaml`, 6/6), **분류기 어휘가 아직 쇼핑몰**이다. `INTENTS` 5개·`ISSUE_CODES` 13개가 전부 커머스라 여행 `case_type` 6개(`activity`·`booking`·`mobility`·`dining`·`lodging`·`flight`)를 **하나도 만들어 내지 못한다** — 실행해 확인했다(`ClassificationFailed`). **2026-08-17 사고와 같은 모양**이고, 재발 방지로 만든 `test_feedback_intent_alignment.py` 가 **등록조차 안 된 팀 하나만 봐서 계속 통과한다** | [../../program/plan/A-COP_여행전환_현황_2026-09-09.md](../../program/plan/A-COP_여행전환_현황_2026-09-09.md) |
| **★한 Case 에 같은 종류 제안이 둘이면 두 번째가 조용히 사라진다 — 결정 필요** `[실측·검토 2026-09-10]` 서버가 Team 의 키를 버리고 **항상 `case_id`** 로 다시 만들고(`controller.py:363`), 충돌하면 `ON CONFLICT DO UPDATE ... RETURNING` 이 **기존 행의 id 를 돌려주며 두 번째 인자를 버린다**. 살아 있는 DB 에서 재현했다(롤백) — 예약 두 건이 한 행이 되고 `bk-002` 가 사라진다. ★**지금은 잠재 결함이다**(적대적 검토가 잡음) — 여행 Team 은 전부 제안 하나씩 돌려준다. 다만 `TeamResult` 는 여럿을 허용하고, **승인 화면·실행 직전 재검증이 저장된 행을 읽으므로 못 되살린다.** ★`case_id` 선택엔 근거가 있다(`2026-08-14_S-IDEMKEY_리포트`: 결제 식별자가 계약 필드로 없던 모델). **여행이 그 전제를 깬다.** 정할 것 — ①「한 Case 에 같은 종류 하나」를 사양으로 삼고 저장 전 거부 ② 서버가 대상 객체 id 를 키에 넣기 | [../../program/plan/A-COP_여행전환_현황_2026-09-09.md](../../program/plan/A-COP_여행전환_현황_2026-09-09.md) §4 |
| ~~**`business_subject` 3단 폴백이 여행 공용 기반으로 옮겨 왔다**~~ **닫힘 — 전제가 틀렸다 (2026-09-10).** Team 쪽 값은 저장되지 않는다. 원래 문구: `[실측 2026-09-09]` `travel_ops/_base.py:136` 이 `booking_id → trip_id → case_id` 폴백을 쓴다. 전에는 한 팀에만 있던 것이 **이제 공용 기반이라 여행 팀 전부가 물려받는다.** `booking_id` 가 `None` 이면 조용히 `case_id` 로 떨어지고 한 Case 안의 두 예약이 같은 idempotency 키를 갖는다. **Trip 하나에 예약이 여럿인 여행이 커머스보다 위험하다** | [../../program/plan/A-COP_여행전환_현황_2026-09-09.md](../../program/plan/A-COP_여행전환_현황_2026-09-09.md) |
| **여행 MVP 설계 결정 5건 — 초안 나왔고 결정이 남았다** `[2026-09-09]` 계획 생성·지속관리 루프·알림 경로·데이터 구분·화면을 코드 실측 위에 정리했다. **결정이 필요한 것 넷** — ① 정규화 다섯 칸에 `constraints`(동행 조건)를 넣을지 ② 감시 소스 설정을 Team manifest 에 둘지 `config/` 에 둘지 ③ 알림 수신 주체가 사람인지 고객 에이전트인지 ④ 기상 API 를 실제로 붙일지 Mock 으로 할지(시연 재현성). ★**`business_subject` 규칙과 정규화 다섯 칸이 먼저다** — 둘 다 계약이라 나중에 바꾸면 그 위가 전부 따라 바뀐다 | [../../program/plan/A-COP_여행MVP_설계질문_5건.md](../../program/plan/A-COP_여행MVP_설계질문_5건.md) |
| **[코드 담당 인계] 도메인 무관 가드가 여행 어휘를 모른다** `[실측 2026-09-09]` `final_project_cs/tests/architecture/test_basement_is_domain_free.py` 의 `DOMAIN_WORDS` 에 구독·결제·커머스 어휘만 있다. `trip`·`itinerary`·`booking`·`reservation`·`activity` 가 `app/core/` 에 들어가도 통과한다 — 여행 Team 구현 시작이 가장 새기 쉬운 시점이다. **옛 어휘는 지우지 않고 더한다**(되돌아갔을 때도 잡히게). sample 쪽 같은 파일도 같다 | [cs/wiki/domain-swap.md](../../final_project_cs/wiki/domain-swap.md) 2026-09-09 절 |
| **`business_subject` 에 무엇을 넣는지 규칙이 없다 — 계획서 담당 몫** `[실측 2026-09-09]` 코어는 이미 도메인 중립이다(`app/core`·`app/application` 에 `order_id`·`booking_id`·`shipment_id` **0회**). 도메인 객체는 `idempotency_key(...)` 의 `business_subject` 한 칸으로 들어가는데 **팀마다 다른 걸 넣는다** — `case_id` 3곳 · `shipment_id` 1곳 · `order_id→customer_id→case_id` 3단 폴백 1곳. ★키가 `f(tenant, request_id, action_type, subject)` 이고 `request_id` 는 Case 당 하나라, **`subject=case_id` 면 한 Case 안의 두 객체가 같은 키를 갖는다**(실측 확인). 쇼핑몰은 Case 하나=주문 하나라 안 드러났지만 **여행은 Trip 하나에 예약이 여럿**이고 사건 하나가 여러 예약을 바꾼다. 정할 것은 이름이 아니라 규칙이며, **v11 §6 이 키 산식을 안 적고 있다** | [../../program/plan/A-COP_여행Team모듈_구성안.md](../../program/plan/A-COP_여행Team모듈_구성안.md) |
| ~~**[담당 세션 인계] `program/research/index.md`의 옛 `docs/` 경로**~~ **닫힘 (2026-09-08).** 165행 하나였고 `wiki/records/handoff/08_모듈_컴포넌트_목록.md` 로 고쳤다(`be154be`). ★그 파일에 다른 세션의 미커밋 행 셋이 함께 있어 **HEAD 판에 내 한 줄만 얹어 커밋하고 작업본은 사본에서 되돌렸다** — 남의 작업물은 그 세션이 커밋한다. 원래 인계 문구: — 2026-09-08 docs 통합 때 그 파일을 다른 세션이 수정 중이라 건너뛰었다. `final_project_cs/docs/` → `final_project_cs/wiki/records/`, `final_project_sample/docs/` → `final_project_sample/wiki/records/` 치환 | [../governance/work-loop.md](../governance/work-loop.md) 2026-09-08 절 |
| **judge 루브릭이 "답이 없을 때"를 안 정한다** `[실측 2026-09-07]` `judge_v3.txt` 의 `correctness` 는 "답변 내용이 사실로 맞는가" 만 적고 **`answer` 가 `null` 일 때의 규칙이 없다.** 그 자리를 채점자가 메우고 있고, 실제로 **답이 없는 승인 대기 건에 `correctness` 4점을 준다.** 그 결과 **Proposed 통과 25건 중 23건(92%)이 답을 안 낸 건**이고, 실제로 답한 156행만 보면 Proposed 1.3% · B 46.8% 다. D-010 의 전제("본문이 없으니 낮게 준다")와 정반대이며, **D-010 을 정하기 전에 이 구멍을 먼저 막아야 한다** | [../evaluation/index.md](../evaluation/index.md) · [../decisions/D-010-deferral-scoring.md](../decisions/D-010-deferral-scoring.md) |
| **`degraded` 가 세 가지를 한 칸에 뭉친다 — 코드 세션 몫** `[실측 2026-09-07]` `context_degraded or failure_code or warnings` 로 계산해서, **Mock Team 의 정례 경고까지 degraded 로 찍힌다.** golden 216행 중 degraded 102행(47%)의 **58.8%(60행)가 Mock 경고만**이다. 기권 지표에서 과잉 기권으로 잡힌 12건이 전부 여기 걸려 있었다. 합쳐 놔서 되돌릴 수가 없다 — 세 칸으로 나눠 싣고 합치는 것은 읽는 쪽에서 한다 | [../../final_project_cs/wiki/quality/blind-spots.md](../../final_project_cs/wiki/quality/blind-spots.md) |
| **`rescore.py` 가 judge 의 `total` 을 검증 안 한다 — 코드 세션 몫** `[실측 2026-09-07]` 러너(`eval/runners/common.py:547`)는 다섯 축의 합과 `total` 이 다르면 `ValueError` 를 던지는데 `eval/rescore.py:100` 은 **키가 있는지만 본다.** 그래서 채점자의 산수 오류가 그대로 들어간다 — Proposed 11/216 · golden_proposed 6/72 · holdout 1/72 (A·B 는 0). ★오늘 결론은 안 바뀐다(평균 −0.09, pass 25 그대로). **다만 `score` 가 그 값에서 오므로 `score` 로 집계하는 모든 것이 노출돼 있다.** 같은 규칙이 두 자리에 갈라져 있는 게 원인이다 | [../../final_project_cs/wiki/quality/blind-spots.md](../../final_project_cs/wiki/quality/blind-spots.md) |
| ~~**Baseline B 가 Proposed 를 이긴다 — 방어 지표 비교가 없다**~~ **비교했다 (2026-09-07).** 골든셋 `expected_next_action` 이 이미 분모다. 적절한 기권율 A 46.7% · B 46.7% · **Proposed 60.0%**, 과잉 기권율 A 0% · B 0% · **Proposed 30.0%**. **Proposed 가 미뤄야 할 것을 더 잡되 과하게 미룬다.** 그리고 A 와 B 는 `next_action` 이 72/72 같다 — RAG 를 줘도 판단은 안 바뀌고 문장만 바뀐다. ★**여전히 열려 있는 것은 과잉 기권 30% 를 줄이는 일이다** — 그 전에는 "B 보다 낫다"가 안 선다. 경위: `[실측 2026-09-07]` 같은 실행에서 judge pass 가 B 46.8% · Proposed 11.6% 이고, B 는 2.5배 싸고 4.8배 빠르다. **"단순 RAG 보다 낫다"를 지금 산출물로는 말할 수 없다.** Proposed 의 값어치(승인 경계·기권·Action 제안)는 judge 총점이 아니라 방어 지표가 재는데, **세 군을 같은 실행에서 방어 지표로 비교한 산출물이 없다.** 그 측정이 먼저다 | [../evaluation/index.md](../evaluation/index.md) · [../evaluation/metrics.md](../evaluation/metrics.md) |
| ~~**cs 소유 문서 둘이 outbox 옛 제약을 싣고 있다**~~ **닫힘 (2026-09-08) — 고칠 대상이 아니었다.** 2026-09-08 `docs/` 통합으로 그 두 파일이 `wiki/records/` 로 들어갔고, **기록은 고치지 않는 것이 규칙**이다(루트 `CLAUDE.md`). 대신 **인용하는 살아 있는 쪽에 주석을 달았다** — [`actions/idempotency.md`](../../final_project_cs/wiki/actions/idempotency.md) 와 이 폴더의 [`dod.md`](dod.md) DoD-23 행. 원래 인계 문구: `[실측 2026-09-07]` 살아 있는 DB 는 `UNIQUE (tenant_id, topic, dedupe_key)` 인데(`outbox_tenant_topic_dedupe_key_key`), `docs/evidence/DoD-23_consumer_idempotency.md:33` 은 옛 제약을 **통과 근거로** 들고 있고 `docs/handoff/02_DB_스키마.md:119` 는 001 DDL 만 싣고 003 개정을 안 싣는다. `tenant_id` 누락은 테넌트끼리 dedupe 충돌을 내는 **보안급**이라 DoD-12 결함으로 기록돼 있다. wiki 쪽 세 곳(`idempotency.md`·`data/migrations.md`·`data/schema/index.md`)은 정정했다 | [../../final_project_cs/wiki/actions/outbox.md](../../final_project_cs/wiki/actions/outbox.md) |
| ~~**wiki 스키마 스니펫이 실제 DB 와 어긋나도 아무도 안 잡는다**~~ **닫힘 (2026-09-07)** — `check_drift.py` 검사 6 으로 붙였다. 살아 있는 DB 의 `pg_constraint`(유니크 57종)와 wiki 의 `UNIQUE(...)` 스니펫 27곳을 대조한다. 회귀를 심어 잡는 것을 확인했다. 경위: `[실측 2026-09-07]` outbox 제약이 문서 다섯 곳에 퍼져 있었고 003 마이그레이션 뒤에도 세 곳이 옛 값을 유지했다. **파일 이름만 새것으로 바꾸고 내용은 안 바꾼 자리도 있었다.** `check_wiki.py` 는 링크와 tag 를 보지 DDL 을 안 본다. `pg_constraint` 를 읽어 wiki 의 `UNIQUE(...)` 스니펫과 대조하는 검사가 필요하다 | [../../final_project_cs/wiki/quality/blind-spots.md](../../final_project_cs/wiki/quality/blind-spots.md) |
| ~~**이관 — 남은 것은 대조 38건**~~ **닫힘 (2026-09-07).** 39건을 절 단위로 훑어 격차 넷을 찾아 반영했다(→ [coverage-2026-09.md](../governance/migration-scope/coverage-2026-09.md) 19차). 경위: `[실측 2026-09-07]` 이 줄은 "사람 판정 79" 로 적혀 있었으나 **두 숫자를 섞은 것이었다.** 사람 판정은 2026-09-03 에 198/198 로 끝났다. 「판정필요 79」는 스크립트의 **초안** 판정이고 그마저 지금 다시 돌리면 68 이다(분모가 747→760 으로 늘었다). 실제로 남은 일은 **대조필요 38건** — "옮기기로 정했다"와 "옮겼다"는 다르고, 대조해 본 9번 중 9번에서 빠진 내용이 나왔다 | [../governance/migration-scope/status.md](../governance/migration-scope/status.md) · [../governance/migration-scope/index.md](../governance/migration-scope/index.md) |
| **골든셋 사람 라벨 24건 — 두 사람이 독립으로 채워야 한다** `[실측 2026-09-07]` 확인 결과 **2인은커녕 1인 라벨링도 안 됐다.** `holdout_human_labels_template.jsonl` 24행의 `labeler`가 전부 `None`, `human_label` 다섯 축이 전부 `null`. judge 프롬프트도 "2-person independent labeling was unavailable"라 적어 두었다. **이것 때문에 `eval/stats/agreement.py`가 재는 DoD-15/17 차단 항목(judge↔사람 일치율)을 평가할 수 없다** — 스크립트는 있는데 입력이 없다. 템플릿·집계 도구는 준비돼 있고 채우기만 하면 된다. 담당은 검증 & 프론트. `[실측 2026-09-07]` **사람이 볼 순서는 정해 뒀다** — 같은 24건을 모델로 두 번 더 독립 채점해 judge 와 어긋나는 6건을 골라냈다. 모델끼리의 일치라 이 항목을 닫지는 못한다 | [../evaluation/judge-second-opinion.md](../evaluation/judge-second-opinion.md) · [../evaluation/golden-set.md](../evaluation/golden-set.md) |
| ~~`final_project_sample/wiki/`가 git에 없다~~ **닫힘 — `.gitignore` 에 `!program/final_project_sample/` 부정 규칙이 들어갔다(2026-09-06). `[실측 2026-09-07]` 33개 전부 추적 중이고 미추적 0.** | 루트 `.gitignore:150~153` |
| ~~Team 경계 불변식 3개 자동화~~ **닫힘 — `INV-CS-ARCH-001·002·003` 셋 다 `automated` 이고 테스트가 실재한다.** `[실측 2026-09-07]` `tests/architecture/test_basement_is_domain_free.py` · `tests/contract/test_core_isolation.py` 65건 통과 | [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md) |
| ~~`final_project_cs/CLAUDE.md`가 v8을 가리킨다~~ **닫힘 — 담당 세션이 v9로 고침(`6bec5d9`).** `final_project_sample/CLAUDE.md`는 그 저장소 쪽 미커밋 수정 중이라 `[미확보]` — 2026-09-06 v9 판올림(루트 `CLAUDE.md`·`research/index.md`·드리프트 검사기는 갱신됨). 두 파일은 다른 세션이 수정 중이라 이 세션이 안 건드렸다. `v8` → `v9`, 경로 `plan/A-COP_구현계획서_v9.md` | [timeline.md](timeline.md) |
| ~~cs 안의 Composer 자체 복사본 셋~~ **닫힘 — 코드 세션이 들어냈고(`f2319aa`, 400줄 삭제, `app/composer_host.py`로 패키지에 주입, `composer:admin` 추가), wiki 갱신도 끝났다.** `[실측 2026-09-07]` 옛 파일 셋 전부 없음, `composer_host.py`·`entrypoint.py` 실재. `f2319aa`를 아는 페이지 6개 + `external/rest-api.md`에 "고객 릴리즈 앱엔 `/composer/*`가 아예 없다"를 추가했다 | [D-006](../decisions/D-006-composer-ownership.md) · [D-011](../decisions/D-011-composer-v3-gap.md) |
| ~~DoD evidence 9건이 낡았다~~ **닫힘 (2026-09-07).** 낡은 일곱(02·14·20·24·21·13·08)은 이름·수치·경로를 현행으로 고쳤고(`7373b67`), 다시 재야 했던 둘도 cs 에서 재측정했다 — **DoD-22**는 `tests/contract/test_team_tool_discipline.py` 10건을 새로 써서 사라진 근거를 복구했고, **DoD-06**은 cs 코퍼스로 다시 재 문서 25 / 청크 306 을 확인했다 | [`quality/dod-evidence-drift.md`](../../final_project_cs/wiki/quality/dod-evidence-drift.md) |
| ~~`program/research/index.md` 둘~~ **닫힘 (2026-09-07).** 표는 09-06 에 되살아났고 `migration-scope` 링크도 폴더형(`migration-scope/index.md`)으로 고쳐져 있었다. 남아 있던 진짜 문제는 **표 내용이 루트 `CLAUDE.md` 와 어긋난 것** — Composer 행 하나가 루트에만, DoD 행의 "evidence 9건 낡음" 이 research 에만 빠져 있었다. 맞추고 `check_drift.py` 검사 4 로 두 표를 행·값 대조하게 했다(`1a4fc82`) | [../governance/review-policy.md](../governance/review-policy.md) |
| ~~`cases.py`의 주석이 낡았다~~ **닫힘 (2026-09-07).** `[실측]` "sweeper 는 아직 없다" 문구가 소스에서 사라졌다. 코드 세션이 sweeper 쪽을 손보면서(`7192fee` — `errored` 를 세기만 하고 아무에게도 안 알리던 결함) 같이 정리한 것으로 보인다 | [`quality/guardrails.md`](../../final_project_cs/wiki/quality/guardrails.md) §2026-09-03 sweeper |

## 측정 대기

`[미확보]` 반나절~하루면 되는데 결론을 크게 바꾸는 것들.

| 순위 | 무엇 | 무엇이 흔들리나 | 시간 |
|---|---|---|---|
| ~~1~~ | **3B 모델 VRAM 상한** — **해결** | 12GB 확정(세션 1 실측) → [../business/gpu-limits.md](../business/gpu-limits.md). **처리량(tok/s)은 아직** | 반나절 |
| **2** | **검토·승인 1건 소요시간** | **72% 절감이 여기 달려 있다.** 도구 설치 완료 → [../business/measure-review-time.md](../business/measure-review-time.md) | **30분** |
| ~~2~~ | **오류 1건당 손실** — **일부 측정** | 분쟁 8건 실측. 중앙값 5만 · 최대 152.6만 → [../business/error-cost.md](../business/error-cost.md) | 완료 |
| ~~3~~ | ~~Baseline A·B 재측정~~ **측정은 끝났다 (2026-09-06)** | `[실측 2026-09-07]` 2026-09-06 judge v3 재기준선이 A·B·Proposed 를 216건씩 같은 실행으로 돌려 놨다. 비용·지연·judge 점수 전부 있다 → [../evaluation/index.md](../evaluation/index.md). ★**그런데 결과가 기대와 반대다** — B 가 pass 46.8% 로 Proposed(11.6%)를 이긴다. 그래서 "단순 LLM보다 낫다"는 **여전히 못 말한다.** 막는 것이 측정 부재에서 **방어 지표 비교 부재**로 바뀌었다 | 완료 |
| ~~4~~ | **DoD-28 재측정** — `[2026-09-07]` **차단 항목이 아니다** | "D-010 대기"는 틀렸다. 막던 것은 D-010 이 아니라 **결정이 이미 났다는 것**이다 — [D-CS-002](../../final_project_cs/wiki/decisions/D-CS-002-finetuned-model-not-adopted.md)가 파인튜닝 모델을 채택하지 않기로 정했다. 세 번째 arm(FT-RAG통합)은 **그 결정을 되돌리려는 사람이 근거로 쓸 때** 필요하다 → [../evaluation/dod28-rerun.md](../evaluation/dod28-rerun.md) | — |

→ [../business/index.md](../business/index.md)

## ★ [2026-09-03] 미측정을 없애는 절차

`[실측]` `A-COP_페인포인트_페르소나_설계.md` §8 에서 이관. **이 절이 빠져 있었다.**

**`[추정]`·`[미확보]` 를 없애는 방법이 이미 정해져 있었다.** 지금 있는 데이터로 대부분 채울 수 있다.

### 1단계 — 있는 데이터로 채운다

| 채울 것 | 쓸 데이터 |
|---|---|
| ~~골든셋 페르소나 배분~~ **완료** | [personas.md](../product/personas.md) 재검증. 정미라 행 18→**28건(38.9%)** 정정 |
| ~~실제 문의 유형 분포~~ **확인 결과: 못 구한다** | [golden-set.md](../evaluation/golden-set.md). **자체 정정** — 처음엔 aihub_30716 이 order 40% 라고 적었는데 틀렸다. `sample_per_group` 층화표집이라 표본 자체가 균등하다 |
| ~~커머스 문의 유형~~ **동일 사유로 못 구한다** | `aihub_102_smb_order_qa` 도 `sample_per_group: 400` 층화표집 (stats.json 확인). 둘 다 자연 빈도가 아니다 |
| ~~오류 비용의 실제 사례~~ **완료** | [error-cost.md](../business/error-cost.md) |
| ~~감정 축 검증~~ **확인 결과: 못 한다** | [golden-set.md](../evaluation/golden-set.md). `aihub_71603` 은 제품 만족도(긍정/부정)를 재고 골든셋은 상담 중 감정·불확실성을 잰다 — **다른 축이라 대조 불가** |
| ~~`cost/case` 실측~~ **완료 (2026-09-07)** | 새로 돌리지 않았다 — 2026-09-06 judge v3 재기준선 산출물에 행마다 `cost_usd`·`latency_ms`·토큰이 이미 있었다. 세 군 같은 실행: A 0.33원 · B 1.20원 · Proposed 3.03원 (환율 1,400원 고정) → [../evaluation/index.md](../evaluation/index.md) |

**네 번째가 특히 중요하다.** **분쟁 조정까지 간 사례집**이므로 "오류 1건이 얼마나 커지는지"의 실제 근거가 된다.

> **지어낸 숫자를 안 써도 된다.**

`[실측]` 그 데이터는 이미 있다. → [../../datasets/wiki/source-selection.md](../../datasets/wiki/source-selection.md)

### 감정 축 검증이 뭘 가리나

**worried/confused 50% 가 골든셋 특성인지 일반 특성인지**를 판별한다.

**골든셋만의 성질이면 그 50% 로 제품을 설명하면 안 된다.**

## 아직 안 정한 것 셋

`[실측]` 같은 문서 §9.

| 항목 | 판단 |
|---|---|
| ~~v8 병합 시점~~ | **폐기 (2026-09-06)** — 병합 대신 **v9로 판올림**해서 진행한다. 판올림 이후의 정본은 wiki다 |
| 골든셋 `persona` 필드 추가 담당 | **역할로 정함 (2026-09-06)** — [roles.md](roles.md)의 검증 & 프론트가 golden/holdout을 관리하므로 그 담당. 이름은 팀 재편 뒤에 |
| 축 1 공개 통계 확보 여부 | 확보 시도 / 미확보 유지 |
| ~~sLLM 파인튜닝이 6팀 필수인가~~ | **닫힘 (09-06, 사용자)** — 필수 여부와 무관하게 파인튜닝은 계속 시도하는 트랙 → [timeline.md](timeline.md) |
| ~~3W 산출물 "학습한 ML/DL 모델"에 무엇을 내나~~ | **닫힘 (09-06, 사용자)** — 지금까지의 학습 결과서·체크포인트(stage3 v9)를 있는 그대로 낸다. 임베딩·리랭커는 이후 후보 → [timeline.md](timeline.md) |

## [2026-09-03] 인수인계에서 남은 것

`[실측]` `A-COP_남은작업_인수인계.md` 에서 이관.

★`[2026-09-08 정정]` **"둘이 남았다"는 낡았다. 남은 것은 0 이다.**
아래 두 줄(`v2 계약 문서 정합` · `UI 가 import 할 패키지 이름`)이 `[미확보]` 로
남아 있었는데, **같은 문서의 「확인 완료로 닫은 것」 표가 둘 다 2026-09-06 에
닫아 뒀다.** 한 파일 안에서 같은 항목을 두 절이 다르게 말하고 있었다.

| 항목 | 상태 |
|---|---|
| ~~VOC 데이터 전처리~~ | **닫힘 — 완료** (2026-09-01) |
| ~~`implementation_ref` allowlist 제한~~ | **닫힘** — **확인됨.** `KNOWN_IMPLEMENTATION_REFS`. Composer HTTP 경로에만 적용 |
| ~~네이버 주문 4건 누락~~ | **닫힘 (09-06, 사용자)** — 이미 수정했다고 정리. `naver_order_history/REPORT.md`의 68/72 문구만 낡았다 → [../../datasets/wiki/scraper-notes.md](../../datasets/wiki/scraper-notes.md) |
| ~~**v2 계약 문서 정합**~~ | **닫힘 (2026-09-06)** — 맞춘 게 아니라 **구현을 하나로 만들어** 맞출 것이 없게 했다(Composer 가 패키지 `acop_composer` 하나뿐). 실측 대조표는 위 「v2 계약 네 항목」 표 |
| ~~**UI 가 import 할 패키지 이름**~~ | **닫힘 (2026-09-06)** — `acop_composer_ui`. 콘솔 `console/composer.py:26` 이 실제로 import 하고 설치돼 있다 |

★**"세 번째가 D-011 과 같은 문제다"도 같이 낡았다.** 계약이 둘로 갈려 있다는 전제가
구현 통합으로 없어졌다. D-011 자체는 여전히 미결이지만 **이 줄이 가리키던 문제는 아니다.**

## 원격 추적은 사람이 한다

`[실측]` 원본이 명시해 뒀다.

> **AI 세션은 푸시를 실행하지 않는다.** 사용자가 직접 실행한다.

**이 wiki 작업도 같다.** 커밋은 하되 푸시하지 않는다.

## ★ [2026-09-03] 정합성 점검이 남긴 미결 판단 둘

`[실측]` `program/research/_정합성_수정제안.md` 에서 이관. **A 묶음 6건은 적용됐고 B·C 가 미결로 남았다.**

### B-1. `research/index.md` 가 계획서·브리핑을 관리할 것인가

**충돌하는 두 원칙이 있다.**

| | |
|---|---|
| `index.md` 5행 | **"계획서·briefing·final_project 폴더는 이 정리의 대상이 아니다"** |
| 점검 권고 | **최신 문서군을 기준선에 기록하라** |
| 고르면 | 대가 |
|---|---|
| 포함 | **색인의 책임 범위가 넓어진다** |
| 제외 | **기준선 확인 정보가 `CLAUDE.md` 등 다른 문서에만 남는다** |

`[실측]` 2026-09-03 확인 — `index.md` 에 그 문구가 없다.

**★ 2026-09-06 결정 — 제외.** `research/index.md`는 지금처럼 research 폴더만 관리하고, 계획서·브리핑 기준선은 루트 `CLAUDE.md`(와 판올림 뒤엔 wiki)가 맡는다. `index.md` 5행 원칙 그대로다.

### C-1. `CLAUDE.md` 기준선에 Composer v3 문서군을 넣을 것인가

`[실측]` 2026-09-03 확인 — **두 `CLAUDE.md` 어디에도 `Composer_v3_설계_토글전용` 이 없다.** 미결이다.

~~**이건 [D-011](../decisions/D-011-composer-v3-gap.md) 이 정해져야 결정된다**~~ → **D-011이 2026-09-06에 정해졌다**(토글 방식 채택, 통째 교체는 관리자 도구). 그러니 v3 문서군은 기준선에 들어가는 게 맞고, v9 판올림 때 `CLAUDE.md` 표에 넣는다.

## 관계

- [timeline.md](timeline.md) — 일정
- [dod.md](dod.md) — 완료 기준
- [../governance/migration-scope/index.md](../governance/migration-scope/index.md) — 문서 이관
