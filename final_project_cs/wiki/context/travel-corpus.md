---
type: policy
title: 여행 정책 코퍼스 — 무엇을 담고 무엇을 안 담나
description: 12문서·130청크. 판단 기준만 담고 지금 값·법령 수치는 담지 않는다
status: draft
tags: [data, travel]
domain: travel
---

# 여행 정책 코퍼스

`knowledge/travel/` · scope 접두 `travel_` · 2026-09-22 신설

**쇼핑몰 코퍼스와 한 폴더에 섞지 않는다.** 둘은 같은 테넌트(`demo`)에 공존하고 **scope 이름으로만**
갈린다. 그래서 이름이 겹치면 안 되고, 겹침 0건을 `python -m scripts.check_corpus` 가 센다.

## 왜 만들었나

`[실측 2026-09-22]` 그 전까지 `knowledge_documents` 에는 쇼핑몰 25문서(306청크)뿐이고 여행 문서는
**0건**이었다. 결과가 셋이었다.

| 누가 | 무슨 일이 있었나 |
|---|---|
| Activity · Dining · Mobility | `required_context` 에서 `policy` 를 뺀 채로 돌았다(2026-09-17). 정책 0건이 Case 전체를 `degraded` 로 만들었기 때문이다 |
| Booking Handoff | `policy` 를 선언한 채 `booking`·`cancellation`·`penalty`·`supplier` 를 검색했는데 **넷 다 문서 0건**이라 **모든 Case 가 degraded → escalated** 였다 |
| Activity(잠재) | `knowledge_scope` 에 `refund` 가 있었다 — **쇼핑몰 코퍼스에 실재하는 scope** 다. 정책을 켜는 순간 활동 취소 판정이 쇼핑몰 환불 문서를 근거로 집어 온다(실측: 그 scope 를 되돌려 보니 top-8 중 **7건이 쇼핑몰 환불 문서**였다) |

## 담는 것 — 판단 기준

**RAG 에 넣는 것은 「판단 기준」이지 「지금 값」이 아니다**(`program/plan/A-COP_여행RAG_코퍼스_계획.md` §0).

| scope | 문서 | 무엇을 판정하나 |
|---|---:|---|
| `travel_activity` | 3 | 취소·변경 접수와 시점 구간 · 무료·무예약 판정 · 관람/자연 갈래의 운영 통제 |
| `travel_weather` | 2 | 기상 사유의 순연과 취소, 부담 주체 · 대기질·폭염·한파·지진 경보와 야외 일정 |
| `travel_dining` | 2 | 식사 예약의 시각·인원 조정과 늦은 통보 · 대체 식당을 고르는 기준 |
| `travel_mobility` | 3 | 운행 중단·지연의 대체 안내 · 연결 실패의 책임과 여유 설계 · 환불 안내 범위 |
| `travel_cancellation` | 1 | 취소·환급의 공통 절차와 업체 인계 (Team 넷이 공유한다) |
| `travel_access` | 1 | 동행 조건 — 이동 보조 · 유아 · 고령 · 식이·종교 |

## 담지 않는 것

★**여기가 이 문서의 요점이다.** 넣지 않기로 한 것과 그 이유.

| 안 담는 것 | 왜 | 어디가 대나 |
|---|---|---|
| **지금 값** — 영업시간 · 강수확률 · 잔여 좌석 · 이동 시간 | 오늘 바뀐다. 문서에 넣으면 낡은 값을 근거로 인용하게 된다 | 외부 API(`read.place`·`read.disruptions`·`read.route`) |
| **그 집이 할랄인가 같은 사실** | 업체가 인증을 잃어도 문서는 안 바뀐다 | `read.place` 의 `dietary`/`dietary_absent` |
| **법령·고시의 수치** (소비자분쟁해결기준의 업종별 위약금율 등) | **원문을 아직 조회하지 않았다.** 확인 안 한 규정을 요약해 넣으면 그 요약이 근거로 쓰인다 | 아직 없다 — 조회한 뒤 문서를 추가한다 |
| **계산에 쓰는 수치 자체** (취소 기한 시간 수 · 위약금율 표) | 검색해서 인용할 것이 아니라 계산에 넣을 값이다 | `config/guardrails.yaml` · 업체 약관. **코드는 산문에서 수치를 파싱하지 않는다**(아래) |
| **쇼핑 갈래**(백화점·시장) | 규정이 없다. 없는 규정을 문서로 만들면 근거 초과율이 오른다 | — |

## 수치의 출처 — 세 종류를 구분해 적었다

1. **우리가 고른 운영 기준** — 「우리 기준」이라고 문서 안에 적었다. 무료 취소 구간 72시간,
   되돌림 24시간, 같은 예약 자동 실행 2회, 건당 50,000원·누적 150,000원, 항목 사이 여유 15분 등.
   이 값들은 `config/guardrails.yaml` 의 `travel.delegation`·`travel.reminders` 와 **같은 값**이고,
   문서는 「왜 그 값인가」를 적고 계산은 설정을 읽는다.
2. **바깥에서 온 사실** — 기상 특보 종류, 대기질 등급, 지진 규모·진앙. 발표 기관의 값을 그대로
   옮기고 우리가 다시 계산하지 않는다.
3. **아직 없는 것** — 법령·고시 수치. **비워 뒀고 비웠다고 적었다.**

## ★ 코드는 이 산문에서 수치를 꺼내지 못한다

`[실측 2026-09-22]` `ActivityTeam._policy_hours` · `_penalty_rate` 는 `isinstance(chunk, dict)` 로
거르는데 RAG 가 주는 것은 `PolicyChunk` **dataclass** 라 **어떤 코퍼스를 넣어도 `None`** 이다.
실행으로 확인했다 → [../records/reports/debugs/2026-09-22_정책청크에서_수치를_못_꺼낸다.md](../records/reports/debugs/2026-09-22_정책청크에서_수치를_못_꺼낸다.md)

그래서 이 코퍼스가 지금 바꾸는 것은 **근거 문장**이지 취소 기한·위약금율 **수치**가 아니다.
수치를 어디서 읽을지는 `program/plan/A-COP_여행RAG_필요대상_재점검_2026-09-10.md` §3 이
①구조화 정책 ②front matter 수치 ③LLM 추출 셋으로 정리해 뒀고 **아직 안 정해졌다.**

## 청크 경계 규칙

`## ` 로 시작하는 줄 하나가 청크 하나이고 경계는 다음 `## ` 직전까지다. 첫 `## ` 앞의 머리말은
청크가 아니다. 제목은 본문에서 빼고 `metadata_json.section_title` 로 싣는다. 쪼개는 코드는
`knowledge/ingest.py` 의 `load_corpus()` **하나뿐**이고 적재 스크립트가 그것을 부른다 —
전문은 [`scripts/ingest_corpus_local.py`](../../scripts/ingest_corpus_local.py) 머리말.

## 적재

```powershell
python -m scripts.check_corpus                                              # 먼저 통과해야 한다
python -m scripts.ingest_corpus_local --manifest knowledge/travel/manifest.json --dry-run
python -m scripts.ingest_corpus_local --manifest knowledge/travel/manifest.json
```

`[실측 2026-09-22]` 문서 **12** · 청크 **130** · 차원 **1024**(`bge-m3`, `embedding_1024` 칸) ·
실패 0. 수치는 [../records/evidence/DoD-06T_여행_정책코퍼스_적재.md](../records/evidence/DoD-06T_여행_정책코퍼스_적재.md).

★**1536 칸(OpenAI)은 비어 있다** — 크레딧이 없어 로컬 임베딩으로만 넣었다. 그래서
`ACOP_EMBEDDING_PROVIDER=openai` 로 되돌리면 여행 scope 검색이 **예외로 죽는다.**
조용히 0건이 되지 않게 `search_policy` 가 그 상태를 직접 검사한다.

## 게이트

`python -m scripts.check_corpus` 가 **컬렉션마다 따로** 돈다 — 쇼핑몰 25문서의 판정이 여행
문서가 늘어도 그대로여야 하기 때문이다. 여행 쪽 인수 기준은 `config/guardrails.yaml` 의
`rag.travel.*`(문서 12 · 청크 110~170 · 문서당 9~15)이고 내용 기준(길이·중복·조사·수치)은
쇼핑몰과 **같은 상수**를 쓴다.

`[실측 2026-09-22]` 여행 — 청크 길이 평균 258자(최소 200·최대 342) · 전체 청크쌍 유사도 중앙 0.000 ·
조사 오류 0 · 30% 초과 공통 8-gram 0종 · 구체 수치 포함 문서 100% / 섹션 45%.

## 관계

- [rag-retrieval.md](rag-retrieval.md) — 검색이 어떻게 도나
- [corpus-authoring.md](corpus-authoring.md) — 게이트 우회 4수법은 이미 거부됐다
- [../teams/activity.md](../teams/activity.md) · [../teams/dining.md](../teams/dining.md) · [../teams/mobility.md](../teams/mobility.md) · [../teams/booking-handoff.md](../teams/booking-handoff.md) — 이 코퍼스를 쓰는 쪽
- [../teams/team-contract/fields.md](../teams/team-contract/fields.md) — `policy_optional_capabilities`
