---
type: plan
title: 전체 일정
description: 선행 11일 + 공식 1W~9W. 중간발표 09-15, 최종발표 10-26
status: draft
tags: [release]
owners: [human:미배정]
---

# 전체 일정

## 구조

```text
선행    2026-08-17 ~ 08-27   11일   ✅ 완료
공식    1W ~ 9W
중간발표 2026-09-15
최종발표 2026-10-26
```

`[실측]` 오늘 2026-09-01 기준 중간발표 D-14, 최종발표 D-55.

## 지금 위치

선행 기간에 끝난 것.

| | 상태 |
|---|---|
| Core/Team 계약 고정 | 완료 |
| sample에서 Composer 쓰기채널 검증 | 완료 |
| 골든셋 72건 구성 | 완료 |
| 평가 하네스 (A/B/Proposed) | 완료 |
| 파인튜닝 파이프라인 | 완료 (결과는 부정적) |

## 중간발표까지 (D-14)

**목표는 "동작한다"이다.** "믿을 수 있다"는 최종발표 몫이다.

| 항목 | 소요 | 왜 지금 |
|---|---|---|
| 4070 SUPER 추론 실측 | 반나절 | 자체호스팅 논거 전체가 여기 달림 |
| 검토·승인 소요시간 실측 | 반나절 | 사업성 72% 절감이 여기 달림 |
| 오류 1건당 손실 집계 | 하루 | 가격 논거의 상한 |
| 환불 계산식 조치 판단 | 판단만 | 할인 붙으면 그날 터짐 |

**앞의 셋은 합쳐서 이틀이다.** 하고 나면 [../business/index.md](../business/index.md) 전체가 `[추정]`에서 벗어난다.

## 구현 6단계

`[실측]` v8 §14. **주차와 별개로 무엇을 먼저 만드는가의 순서다.**

| 단계 | 무엇 |
|---|---|
| 1 | 도메인·Case·ERD·상태·**Contract 확정** |
| 2 | Core Basement MVP · Registry · **세 Port** · Context Broker · Shared State |
| 3 | Team 구현 + RAG. **Return & Refund는 계약 + Mock** · Catalog는 A2A 기본 설계와 Agent Card |
| 4 | REST/MCP 외부 진입점 + **A2A 보안·실패·취소 처리** |
| 5 | UI와 trace/approval |
| 6 | 평가와 고도화 |

**1단계가 계약 확정인 게 중요하다.** 계약이 흔들리면 뒤의 모든 단계가 다시 간다. → 1W 금요일 Contract Freeze Day

`[실측]` **Registry 등록 수와 실제 구현 수는 별도로 검증한다.** 등록만 하고 구현이 없으면 목록은 늘어나 보인다.

## 주차별 계획

`[실측]` v8 §25에서 이관. 공식 부트캠프 일정 기준.

**Commerce Ops Pack(Procurement+Order·Fulfillment·Return·Catalog) 작업은 검증 쇼핑몰 프로젝트와 연계된 범위**이며, VOC·Response Generation & Review와 달리 그 프로젝트 진행에 따라 조정될 수 있다.

| 주차 | 기간 | 공식 산출물 |
|---|---|---|
| 선행 | 8/17~8/27 (11일) | 초안 준비 |
| 1W | 8/28~9/3 | WBS · 프로젝트 기획서 · 요구사항 정의서 |
| 2W | 9/4~9/10 | 수집 데이터 보고서 · DB/저장소 설계 문서 |
| **3W** | **9/11~9/17** | 데이터 전처리 결과서 · ML/DL 학습결과서 · 학습 모델 · **중간발표 PT (9/15)** |
| 4W | 9/18~9/28 (11일) | 신규 산출물 없음 |
| 5W | 9/29~10/6 | 벡터DB/GraphDB 결과서 · AI 시스템 아키텍처 · 멀티에이전트 테스트 보고서 · 요구사항 정의서(업데이트) · 화면설계서 |
| 6W | 10/7~10/14 | 신규 산출물 없음 |
| 7W | 10/15~10/21 | LLM 연동 웹 애플리케이션 · 시스템 구성도 · 서비스 테스트 보고서 |
| 8W | 10/21~10/24 (4일) | 최종발표 PT · 개발 소스코드 · 시연영상 |
| 9W | — | 8W 보완, **최종발표 10/26** |

### ★ 양식별 근거 문서 — 어디를 보고 채우나

`[실측]` `program/산출물양식/README.md`(2026-08-28 배포 양식)에서 옮기고 wiki 페이지로 바꿨다. **빈칸부터 채우지 말고 여기 적힌 문서를 먼저 읽는다.** 문서에 없는 것을 지어내지 않고, 미완성은 미완성이라고 적는다.

| 양식 | 근거 |
|---|---|
| 프로젝트 기획서 | `program/plan/A-COP_구현계획서_v9.md`(2026-09-06 판올림. v8은 `archive/`) · [../product/index.md](../product/index.md) |
| WBS | 이 문서 · `program/research/_WBS원본_2026-08-17.md` |
| 요구사항 정의서 (+ 5W 업데이트) | [dod.md](dod.md) — 29항목 |
| 수집 데이터 보고서 | [datasets/catalog.md](../../datasets/wiki/catalog.md) + 각 데이터셋 `REPORT.md`. 순서: 상용 주문(쿠팡·네이버) → 배송 조회 도구 → 공개 VOC → 번역 비교 |
| DB/저장소 설계 문서 | [cs data/schema](../../final_project_cs/wiki/data/schema/index.md) · [migrations](../../final_project_cs/wiki/data/migrations.md) |
| 데이터 전처리 결과서 | 각 데이터셋의 `scripts/normalize.py`·`processed/` — 현황은 [catalog.md](../../datasets/wiki/catalog.md) |
| **ML/DL 학습 결과서 · 학습한 모델** | [mt-benchmark](../research/mt-benchmark.md) · [dod28-rerun](../evaluation/dod28-rerun.md)(파인튜닝 — **채택 안 함**). **무엇을 "학습한 모델"로 낼지 미결** — 아래 |
| AI 시스템 아키텍처 | [architecture/index.md](../architecture/index.md) · [diagrams.md](../architecture/diagrams.md) |
| 멀티 에이전트 테스트 계획·결과 | [cs quality/evidence.md](../../final_project_cs/wiki/quality/evidence.md) · [evaluation/index.md](../evaluation/index.md) |
| 벡터DB/GraphDB 구축 결과서 | [rag-retrieval](../../final_project_cs/wiki/context/rag-retrieval.md) · [graph-retrieval](../../final_project_cs/wiki/context/graph-retrieval.md) |
| 자체 sLLM 인공지능 | **주제 3·4 팀만 해당.** 우리가 해당하는지 미결 — 아래 |
| 시스템 구성도 | [diagrams.md](../architecture/diagrams.md) 배포 다이어그램 |
| LLM 연동 웹 애플리케이션 | `final_project_ui/` · [cs operations/run.md](../../final_project_cs/wiki/operations/run.md) |
| 서비스 테스트 계획·결과 | [cs quality/evidence.md](../../final_project_cs/wiki/quality/evidence.md) |
| 중간·최종 발표 PT | [milestones/index.md](milestones/index.md) |

`[실측]` 원본 README의 두 주의는 지금 이렇게 읽는다 — **"VOC 5종은 전처리 전"은 낡았다**(2026-09-01 디스크 실측 기준 완료 8·미착수 1 — `kaggle_customer_support`뿐, [catalog.md](../../datasets/wiki/catalog.md)). **번역 성능 수치는 2026-08-24 GPU 서버 재검증 값이 정본이고 그 이전 GGUF 결과는 양자화 문제로 못 쓴다** → [mt-benchmark](../research/mt-benchmark.md).

### ★ 시트 원문이 말하는 것 — "10주"의 뜻과 미결 둘

`[실측]` `program/research/_WBS원본_2026-08-17.md`(부트캠프 구글 시트 `32기_대시보드`·`6팀` 원문 그대로). 루트 `CLAUDE.md`가 일정 정본으로 지정한 문서다.

**공식 기간은 8/28~10/26, 약 8.5주다.** 이 wiki 곳곳의 "10주"(scope·pack-model·positioning 등)는 **선행 11일(8/17~8/27)을 포함한 총 기간**이지 공식 기간이 아니다. 시트엔 "10주"가 없다 — 원문이 "기존 계획서의 10주는 시트와 맞지 않는다"고 적어 둔 이유다. 9W는 개발 주차가 아니라 "산출물 보완 및 잔여 리소스 정리"다.

| 시트에서 읽히는 것 | |
|---|---|
| 4W가 11일 | 추석 연휴 구간으로 보인다 |
| 8W가 4일 | 7W와 10/21 하루 겹친다 |
| `제출마감기한` 열 | **전 행이 비어 있다.** 마감은 주차 구간으로 읽는다 |

`[미확보]` **원문이 "판단이 필요하다"고 남긴 둘이 아직 wiki 어디에도 결정으로 없다.**

| 미결 | 왜 |
|---|---|
| **sLLM 파인튜닝이 6팀 필수인가** | 시트 문구는 "3, 4번 주제"·"3, 4번 팀"인데 6팀 시트에도 그 행이 그대로 있다. **강사 확인 전엔 필수로 단정하지 않는다** — DoD-28이 있으니 선택 항목으로는 살아 있다 |
| **3W 산출물 "데이터 전처리 결과서 · ML/DL 학습결과서 · 학습한 ML/DL 모델"을 무엇으로 채우나** | LLM API 호출만으로는 안 채워진다. 파인튜닝은 채택하지 않기로 했으니([../evaluation/dod28-rerun.md](../evaluation/dod28-rerun.md)) "학습한 모델"에 무엇을 낼지 정해야 한다 |

`[미확보]` 시트의 팀명·깃허브·협업툴·멘토 칸이 2026-08-17엔 전부 비어 있었다. 지금 채워졌는지 확인하지 않았다.

### 역할별 배분

| 주차 | 코어 1 | 코어 2 | 모델 3명 | 검증·프론트 |
|---|---|---|---|---|
| 1W | 선행 초안 동결, CAS·transition 경계 정리 | **Contract Freeze**, REST/MCP·scope skeleton | 검증 쇼핑몰 5개 Team 계약 정리 | harness skeleton·UI fixture |
| 2W | Case·Action 상태와 Registry를 seed에 맞춤 | REST/MCP skeleton·저장소 경계 문서화 | demo seed·knowledge documents·RAG 적재 범위 | 평가 harness 입력·데이터 fixture 고정 |
| 3W | Controller·MessageBus를 중간발표 경로에 연결 | Action/approval 경계 연결 | PII masking·Case fixture·RAG corpus 정리, Team 단독 테스트 | Case UI·중간발표 demo |
| 4W | Context Broker·projection 안정화 | Tool adapter·audit 보완 | RAG 25/300~400과 Team 통합 보완 | trace 화면·발표 피드백 반영 |
| 5W | Outbox·retry·WAIT/RESUME, GraphStorePort·SQL adapter | idempotency·unknown, MCP/A2A 보안 경계 | 검증 쇼핑몰 Team 통합, Catalog A2A 경계 테스트 | API/UI contract, Graph gate 측정 |
| 6W | Shared State merge·재처리 경로 보완 | A2A 실패·타임아웃·취소·인증, 승인·감사 회귀 | VOC 위임 제안·Response GEN/REV·ActionProposal 흐름 | end-to-end demo 회귀 점검 |
| 7W | GraphStorePort·SQL adapter·시스템 구성도 고정 | MCP/A2A 보안·서비스 경계 점검 | 관계 질의 fixture·Team 성능 점검 | 운영 UI·LLM 연동, 서비스 테스트 결과 |
| 8W | 재처리·경합 테스트, DoD 근거 최종 확인 | input-required·callback·cancel, 승인·감사 흐름 확인 | LOCAL Team과 Catalog A2A 동일 결과 경로 동결 | 모듈별 golden/holdout 실행, 발표·시연영상 동결 |
| 9W | 버그 수정, DoD·Alembic gate 확인 | 승인·보안 회귀, 배포·감사 점검 | Team 성능 수정, 시나리오 잔여 결함 표시 | bootstrap/McNemar, 최종 리포트·실행 절차 점검 |

### 두 가지 고정점

**1W 금요일은 Contract Freeze Day다.** 계약을 여기서 얼린다.

**Core 1과 Core 2의 Alembic revision은 단일 브랜치로 유지한다.** 마이그레이션이 갈리면 병합이 지옥이 된다.

## 최종발표까지

**목표는 "믿을 수 있다"이다.**

| 단계 | 내용 |
|---|---|
| Team 착수 완료 | LOCAL 4개 + Remote A2A PoC 1개 |
| 평가 전체 실행 | 60 + 20, 3회 반복, 통계 처리 |
| 근거 지표 확정 | 정합률·초과율·기권율 |
| DoD 29항목 | [dod.md](dod.md) |

## 1번 리스크 — 범위 과대

기준선으로 통제한다.

```
도메인 1개 · 착수 LOCAL Team 4개 · Remote A2A PoC 1개
```

**Team 수는 아키텍처 상한이 아니다.** Registry 등록으로 확장되는 값이고, 확장 여부는 **일정과 평가 여력**으로 판단한다. Team이 늘면 골든셋과 라우팅 평가 축도 같이 늘어난다.

## 일정에 걸린 외부 의존

| 의존 | 무엇이 막히나 |
|---|---|
| 검증 쇼핑몰 진행 범위 | Commerce Ops Pack 4개 Team |
| 검증 쇼핑몰 계약 협의 | 환불 계산식 전환 ([D-001](../decisions/D-001-payment-ownership.md)) |

**Commerce Ops Pack은 일정에 따라 조정된다.** CS Pack 2종만 확정이다.

## 관계

- [milestones/index.md](milestones/index.md) — 두 발표
- [dod.md](dod.md) — 완료 기준
- [roles.md](roles.md) — 누가 무엇을
- [../product/scope.md](../product/scope.md) — 범위 통제
