---
type: guide
title: 문서 변경 이력 (cs)
description: 이 저장소 wiki의 추가·수정 기록
status: draft
domain: neutral
domain_note: 작업 로그다. 무엇을 했는지의 기록이라 도메인이 섞인다
---

# 문서 변경 이력 (cs)

## 2026-09-22 — 여행 밀도 근거 조사 반영

학술·기관 자료 조사에 따라 직접 목표 입력, 시간 구성, 대기 중복 방지, 추정 정책 표시를 보강했다. [구현·검증 리포트](records/reports/2026-09-22_2240_여행밀도_근거반영_구현.md).

## 2026-09-22 — 여행 밀도 관측 경고

등록·조회 API가 명시된 시간·이동·완충시간으로 밀도를 측정하고 초과/미측정을 경고한다. [구현·검증 리포트](records/reports/2026-09-22_2200_여행밀도_관측경고.md).

최신이 위다. 기록 기준은 [중앙 허브 표준](../../wiki/governance/review-policy.md)을 따른다.

오탈자는 적지 않는다. **문서 추가·삭제, 결론·수치 변경, `status` 변경, 소유자 변경**만 적는다.

---

## 2026-09-23 — 이동 수단 `uses` 표기를 계약으로

일정 등록 몸통 `routes{<키>}.options[].uses` 의 표기를 정했다(`external/rest-endpoints.md`) — 지하철 `N호선:역명`(「역」·괄호 병기 뺌, 서울역 예외) · 버스 `버스:<노선번호>` · 도로 `도로:<UTIC 도로명 전체>` · 도보는 지나는 큰길을 `도로:` 로. 감시가 이 값을 문자열로 대조하므로 표기가 다르면 사건을 조용히 놓친다. 시나리오 JSON 의 어긋난 표기와 등록 시 형식 검사 부재는 `[미반영]` 으로 남겼다. [리포트](records/reports/2026-09-23_1817_경로_uses_표기_계약.md).

## 2026-09-22 (밤) — 위임을 주고 거두는 자리 · 상시 실행을 서버 쪽으로

위임 REST `/v1/delegations/*` 와 운영 화면 `/ui/delegations` 가 생겼다(`external/rest-endpoints.md`·`actions/approval.md`). ★화면에서 **위임을 바꾸는 것은 기본이 꺼짐**이다 — `/ui/*` 에는 로그인이 없고, 같은 이유로 2026-08-18 에 Composer 화면을 지웠다(D-CS-001). 다시 주기가 철회 기록을 덮던 결함을 고쳤다(`delegation_events`, 021).
상시 실행(DB·되잡기·안내·바깥함 일꾼·앱)을 서비스/서버로 옮기는 준비를 문서와 스크립트로 만들었다 — `operations/always-on.md`·`operations/move-to-server.md`·`scripts/ops/`. 시스템 설정은 바꾸지 않았다(등록 0건).

## 2026-09-22 (밤) — 알림은 운영 테넌트만 바깥으로 나간다

★사고: 점검을 한 회차 돌리는 사이에 **시연 테넌트의 통지 8건이 실제 채널로 나갔다**(고객 언어가 대만 중국어라 외국어로 도착). 일꾼이 모든 테넌트를 집고 있었다. 이제 기본은 운영 테넌트 하나뿐이고, 나머지는 `skipped` 로 사유와 함께 남는다 — `delivered` 로 찍지 않는다. 일부러 보내려면 `--send-tenant` 로 고른다(허브 `wiki/architecture/notifications.md` 「누구에게 보내나」).

## 2026-09-22 (밤) — 남은 DoD 여섯을 채웠다: 변경 링크 · 위임 범위 · 실행 장부 · 되돌림

업체 예약은 우리가 바꾸지 않고 **변경 링크**로 넘긴다(`external/rest-endpoints.md`, 차액은 모르면 「확인되지 않았습니다」). 승인 뒤 자동 실행에 **문이 둘**이다 — 공급자 등급과 **위임 범위**(금액·종류·횟수·무료취소 구간, `actions/approval.md`·`teams/booking-handoff.md`). 실행 장부에 무엇을·왜·얼마에·되돌림 기한을 남기고, 되돌림이 실패하면 사람에게 간다. 범위 밖 자동 실행 측정 = 13건 중 **0건**(`records/evidence/DoD-v11-18-21_위임범위와_되돌림.md`). ★v11 §12 **26/26 = 100%**(도구 실측), 전체 시험 1206건 실패 0.

## 2026-09-22 (저녁) — 정책 검색을 로컬 임베딩으로도 돌린다 · ODsay 를 쓰지 않는다

정책 검색(RAG)이 OpenAI 임베딩에만 매여 크레딧 소진 뒤 시험 3건이 계속 빨갰다. 임베딩 제공자를 설정으로 고르게 하고(`openai` 1536칸 · `ollama` bge-m3 1024칸, 두 벡터 **공존**), DB 에 있던 청크 306개를 로컬 모델로 다시 임베딩했다(실패 0). 고른 쪽 칸이 비면 예외 — 조용히 넘어가지 않는다. 결정 기록 `decisions/D-CS-005-odsay-not-used.md` — 약관이 결과 데이터 저장·가공을 사전 동의 없이 금지하고 무료 한도가 30회/일이라 쓰지 않는다.

## 2026-09-22 (오후) — 안내 문구 재사용률 실측 · 공급자 등급 게이트

안내 문구 캐시의 재사용률을 운영 경로로 쟀다(`scripts/measure_notice_phrases.py`, 리포트 `records/reports/2026-09-22_0836_…`): 7일·3언어에서 안내 126건 중 모델 호출 9회 = 92.9% 재사용, 값 어긋남 0/1,572. **모델 호출은 일수가 아니라 (문구틀 수 × 언어 수)로 정해진다.** 자동 실행은 시뮬레이션 공급자에만 열리게 게이트를 세웠다(`records/evidence/DoD-v11-14-15_공급자등급게이트.md`) — v11 DoD 14·15 통과, 전체 20/26.

## 2026-09-22 (오후) — 화면에서 찾은 결함 둘: Case 버전 통지에 링크 없음 · 다른 테넌트 링크가 404

시연 화면으로 하루를 돌려 통지를 열어 보고 찾았다. ①Case 버전의 변경 통지는 코어가 바깥함에 직접 써서 `plan_url` 이 빠져 있었다(허브 `wiki/architecture/notifications.md` 정정 — 09-20 에 「전부 붙는다」고 적은 것이 틀렸다). ②계획서 링크 화면이 설정된 테넌트 하나로만 토큰을 맞춰, 다른 테넌트(시나리오 전용)의 여행은 링크가 404 였다. 둘 다 고치고 통지 경로마다 링크를 보는 시험을 붙였다.

## 2026-09-22 (오전) — 안내 문구 언어별 캐시 · 로컬 DB 비정상 종료 조사

안내(②·③)는 **틀만** 언어마다 한 번 옮겨 담아 두고 값은 알림마다 원값으로 채운다 — 같은 언어의 다음 안내는 모델을 안 부른다(허브 `wiki/architecture/notifications.md` 「언어」, 리포트 `records/reports/2026-09-22_0759_…`). 완성 문장을 담으면 시각·장소가 섞이므로 구조로 막았다. 변경 통지(①)는 매번 새 문장이라 담지 않는다.
로컬 DB 가 종료 기록 없이 꺼지는 건을 조사해 운영 문서를 만들었다 — `records/manuals/운영_로컬DB_기동과_비정상종료.md`(되살리는 절차 · 낡은 postmaster.pid · 가설별 판정).

## 2026-09-22 — 여행 평가 데이터셋·러너로 DoD-22 를 재고, MVP 18항목이 전부 통과

`eval/datasets/travel_scenarios.jsonl`(시나리오 10건)과 `eval/runners/travel_scenarios.py` 를 만들었다. 확정 하루를 변형해 흘리고 **적용된 모든 일정 버전**을 등록 때와 같은 판정기로 다시 본다 — 실측 10/10 통과 · 필수 조건 위반 0건. 결제 필터를 일부러 꺼 보니 위반 3건을 잡았다. 허브 `wiki/delivery/dod.md` 갱신 — 전체 18/26, **MVP 18/18**(남은 미측정 8 은 전부 Booking Handoff 몫).

## 2026-09-21 (오후) — 일정을 받을 때 코드로 판정하고, 불가능하면 이유·완화 조건을 붙여 거절

`app/modules/travel_ops/itinerary_checks.py` 신설 — 겹침·이동 소요·영업시간·브레이크·결제·예산을 보낸 값으로 판정한다. 모르는 칸은 판정하지 않는다(결정 15). `POST /v1/trips` 가 `422 itinerary_infeasible` + `violations[]`(`reason`·`remedy`)로 거절한다(`external/rest-endpoints.md`). v11 DoD-2·3 이 미측정에서 통과로 — 전체 17/26, MVP 17/18.

## 2026-09-21 — v11 26항목을 실행으로 세는 DoD 검사기

`scripts/verify_dod_v11.py` 를 만들었다. 항목마다 그것을 보는 시험(node id)을 적어 두고 실제로 돌린다 — 재는 것이 없으면 「미측정」이고 통과로 세지 않는다. 첫 실측 통과 16/26 = 62%, MVP 18 기준 16/18 = 89%(허브 `wiki/delivery/dod.md`). 옛 `scripts/verify_dod.py` 는 v8 29항목 기록으로 남긴다.

## 2026-09-20 — 변경 통지에도 계획서 링크 · 끝난 Case 재실행 차단 · 멱등 키 충돌 표면화

변경 통지(①)에 `plan_url` 이 빠져 있던 것을 채웠다(`wiki/architecture/notifications.md` 허브 표 갱신). 끝났거나 기다리는 중인 Case 에는 Team 을 부르지 않는다(`actions/approval.md`). 적용기가 없어 키의 대상이 Case id 인 제안은 둘째가 합쳐져 사라지던 것을 `action_key_collision` 로 드러낸다(`actions/idempotency.md`).

## 2026-09-18 — 간헐 실패 원인(UUID 가림) · 일정 안내 · 승인 뒤 실행

「원인 모름 간헐 실패」는 코어 가림 규칙이 UUID 를 전화번호로 가리던 결함이었다(`records/reports/debugs/2026-09-18_1425_…`). 일정 안내(하루 시작·출발)를 운영 되잡기 작업으로 만들고, 기본 감시를 Case 버전으로 바꿨다(`operations/run.md`). 승인된 제안을 코어가 적용기로 실행하고, Booking Handoff 준비 capability 에 라우팅이 닿는다(`actions/approval.md` 「승인 뒤 실행」 · `actions/idempotency.md` · `teams/booking-handoff.md`). 리포트 `records/reports/2026-09-18_1500_…`.

## 2026-09-17 — Case 버전: 문장 해석이 분류보다 먼저, 실제 Gemma 로 확인

실제 gemma4:12b 로 재니 분류 접두가 늦음·품절·재요청 문장에서 빗나가 사람에게 넘어갔다. 대상이 정해진 고객 Case 는 분류 직전에 신고를 추출해 담당을 정하도록 바꿨다(`external/rest-endpoints.md` subject_ref 절, `teams/team-contract/index.md`). 여행 승인 제안이 근거 대조에서 막히던 결함도 고쳤다(`records/reports/debugs/2026-09-17_1450_…`).

## 2026-09-17 — Case 버전만으로 여행 일정 관리가 돈다

시나리오용 여행 버전에만 있던 일정 관리(감시 조정·고객 신고·다른 안·되돌리기·통지)를 Case → Controller → Team → 코어 적용 경로로 옮겼다. 같은 재생 하루에서 두 버전의 결과가 같다. 계약 페이지 넷(`external/rest-endpoints.md` subject_ref · `actions/approval.md` 승인 없이 적용 · `teams/team-contract/index.md` · `context/context-broker.md`)과 Team 페이지 셋을 고쳤다.
→ [records/reports/2026-09-17_0536_Case버전_여행일정관리_이식_리포트.md](records/reports/2026-09-17_0536_Case버전_여행일정관리_이식_리포트.md)

## 2026-09-01 (2) — 역방향 표식 완료. 양방향 잠김

cs 프로젝트가 테스트에 `# invariant:` 표식을 넣었다.

```python
# invariant: INV-CS-ARCH-001
def test_basement_layers_do_not_know_the_business_domain(): ...
```

`[실측]` 검사기 대조 결과.

| | 값 |
|---|---|
| 코드 표식 | **48개** |
| 문서 불변식 | 51개 |
| 코드에만 있는 ID | **0개** |
| 문서에만 있는 ID | 3개 |

**문서에만 있는 3개는 정상이다.** `INV-CS-TEAM-003·004·005`는 판정이 `review`라 대응 테스트가 없다.

### 이제 무엇이 잠겼나

```
문서 → 테스트   경로와 함수 실재를 검사기가 확인   117개
테스트 → 문서   표식 ID 가 카탈로그에 있는지 확인   48개
```

**한쪽만 고치면 CI가 잡는다.** 테스트를 지우면 문서가 가리키는 곳이 사라지고, 표식만 남기면 카탈로그에 없는 ID가 된다.

### 남은 것

`[미확보]` **Team 경계 3개의 자동화.** import 검사로 가능해 보인다.

```
INV-CS-TEAM-003  side effect 를 실행하지 않는다
INV-CS-TEAM-004  read 도구를 직접 호출하지 않는다
INV-CS-TEAM-005  다른 Team 을 직접 호출하지 않는다
```

`tests/architecture/test_basement_is_domain_free.py`가 이미 import 검사를 하므로 같은 방식을 쓸 수 있다.

**자동화되면 사람 판정이 3개 → 0개가 된다.**

---

## 2026-09-01 — wiki 신설

### 추가

`final_project_cs/wiki/` 를 만들었다. 기존 `docs/` 는 그대로 두고 이관하지 않았다.

| 영역 | 상태 |
|---|---|
| `runtime/` | index만 |
| `teams/` | index만 |
| `context/` | index만 |
| `actions/` | index만 |
| `external/` | index만 |
| `data/` | index만 |
| `quality/` | index + **invariants.md** |
| `operations/` | index만 |
| `decisions/` | index만 |

전부 `status: draft`다.

### 불변식 카탈로그 작성

[quality/invariants.md](quality/invariants.md) 에 **33개**를 정리했다. 실제 테스트 함수와 대조했다.

| 영역 | 총 | automated | 사람 판정 |
|---|---|---|---|
| 아키텍처 | 6 | 6 | 0 |
| Team 계약 | 5 | 2 | 3 |
| Action | 3 | 3 | 0 |
| 보안 | 8 | 8 | 0 |
| 도메인 검증 | 7 | 7 | 0 |
| Runtime | 4 | 0 | **4** |

### 작성하면서 드러난 것

**하나 — Runtime 불변식 4개가 자동 판정이 아니다.** Case 상태가 제품의 중심인데 테스트로 강제되지 않는다. 카탈로그의 가장 큰 구멍이다.

**둘 — Team 경계 3개도 자동 판정이 아니다.** side effect 금지, read 도구 직접 호출 금지, Team 간 직접 호출 금지. 설계의 핵심인데 사람 리뷰에 의존한다.

**셋 — `INV-CS-VER-002`가 환불 계산 결함을 못 잡는다.** "환불 ≤ 주문 총액"만 보는데 총액 자체가 잘못된 기준이면 통과한다. 쿠폰 5,000원 사례에서 15,000 ≤ 30,000이라 통과하지만 실제 환불은 12,500원이다.

**넷 — 코드에 `# invariant:` 역방향 표식이 아직 없다.** 넣어야 CI가 양방향 검사를 할 수 있다.

---

## 이관 예정

`docs/` 하위 문서 중 이관 대상 선별이 필요하다. 범위 산정은 [중앙 허브](../../wiki/governance/migration.md).

| 원본 | 판정 |
|---|---|
| `wiki/records/reports/` 151개 | 시점 기록. **제외** |
| `wiki/records/handoff/` 128개 | 완료분 제외, 진행 중만 |
| `wiki/records/history/` 43개 | git으로 복원 가능. 결정만 추출 |
| `wiki/records/plans/` | 선별 이관 |
| `wiki/records/evidence/` | 선별 이관 |
