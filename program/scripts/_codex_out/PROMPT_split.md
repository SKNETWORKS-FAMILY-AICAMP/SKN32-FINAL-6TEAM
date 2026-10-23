# 작업 — datasets 의 REPORT 10건을 둘로 나눈다

## 규칙 (판정 기준은 한 줄이다)

> **날짜를 적어야 말이 되면 `report` 다.**

"2026-09-01 전처리 완료"는 날짜가 필요하다. "출처는 AI Hub"는 필요 없다.

```
<이름>/REPORT.md      데이터가 무엇인가   type: dataset   안 변한다
<이름>/STATUS.md      지금 어디까지 됐나  type: report    계속 변한다
```

| REPORT.md 로 | STATUS.md 로 |
|---|---|
| 출처·URL·라이선스 | 전처리 진행 상황 |
| 받은 파일 목록·크기 | 실행 결과·건수 |
| 스키마·필드 의미 | 발견한 문제 |
| **선택 이유** | **아직 안 한 것** |
| 이용 제약·PII 금지 | **날짜가 붙은 모든 절** |

## ★ 절대 하지 말 것

1. **원본 파일을 고치거나 지우지 마라.** 읽기만 한다. 결과는 응답으로만 낸다.
2. **문장을 새로 쓰지 마라.** 원문 문장을 그대로 옮긴다. 다듬지도 마라.
   이건 창작이 아니라 분류다. 원문에 없는 사실을 넣으면 안 된다.
3. **버리지 마라.** 원본의 모든 절이 둘 중 하나에는 들어가야 한다.
   어느 쪽인지 모르겠으면 `REPORT.md` 에 두고 그 절 옆에 `<!-- 판정보류 -->` 를 단다.
4. **`build/`·`dist/`·`__pycache__` 는 읽지 마라.**

## 대상 10건

```
datasets/voc/sources_catalog/PLAN.md
datasets/mt/olist_reviews_mt_bench/REPORT.md
datasets/commerce/coupang_order_history/docs/실제HTML_페이지네이션.md
datasets/commerce/naver_order_history/REPORT.md
datasets/commerce/courier_tracking/REPORT.md
datasets/commerce/coupang_order_history/docs/실제HTML_주문상세_배송조회.md
datasets/voc/aihub_102_smb_order_qa/REPORT.md
datasets/voc/aihub_30716_callcenter_qa/REPORT.md
datasets/voc/aihub_71603_aspect_sentiment/REPORT.md
datasets/voc/aihub_71844_llm_instruction_tuning/REPORT.md
```

## ★ 두 건은 성격이 다르다

`실제HTML_페이지네이션.md` 와 `실제HTML_주문상세_배송조회.md` 는
**H1(`# `)이 3개다.** 한 파일에 문서 두세 개가 들어 있다.
이 둘은 REPORT/STATUS 가 아니라 **H1 단위로 나눈다.**
각 H1 의 제목에서 파일명을 만들어라 (예: `주문상세_구조.md`, `배송조회_구조.md`).

## front matter

각 산출물 맨 앞에 넣는다. 원본에 front matter 가 없으면 새로 만든다.

```yaml
---
type: dataset          # STATUS.md 는 report, HTML 구조 문서는 reference
title: <원본 H1 그대로>
description: <한 문장>
status: draft
tags: [data]
---
```

`tags` 는 `data`, `testing`, `architecture` 중에서만 고른다.

## 출력 형식

```
===== FILE: <원본폴더>/REPORT.md =====
<내용>

===== FILE: <원본폴더>/STATUS.md =====
<내용>
```

`<원본폴더>` 는 `datasets/` 를 뗀 경로다. 예: `voc/aihub_71603_aspect_sentiment`

다른 설명이나 요약은 붙이지 마라. 파일 내용만 낸다.
