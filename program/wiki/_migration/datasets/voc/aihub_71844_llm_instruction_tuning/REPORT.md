---
type: dataset
title: AI Hub 71844 — 민간 민원 상담 LLM 사전학습 및 Instruction Tuning 데이터
description: AI Hub 71844 — 민간 민원 상담 LLM 사전학습 및 Instruction Tuning 데이터
status: draft
tags: [data]
---

# AI Hub 71844 — 민간 민원 상담 LLM 사전학습 및 Instruction Tuning 데이터

## 출처

- AI Hub, 데이터셋 번호 23 / `dataSetSn=71844`
- `https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71844`
- 다운로드일: 2026-08-20
- 원천데이터 12,303건 + 라벨링데이터 132,401건(500자+/3턴+ 조건)
- 수집처: 하나카드 58.01% · LG유플러스 33.17% · 액티벤처 8.82%

## 받은 것

- 원천데이터 + 라벨링데이터 둘 다 받음 — 텍스트 상담 데이터라 콜센터(30716)처럼
  음성 용량 문제가 없다.
- `raw/3.개방데이터/1.데이터/Training/01.원천데이터/TS_액티벤처.zip`,
  `TS_엘지유플러스.zip`, `TS_하나카드.zip` (Validation도 동일 구조)
- 압축 해제 안 함
- 총 용량: 209MB

## 선택 이유

`datasets/voc/sources_catalog/PLAN.md` 참고. 요약: 71603·30716은 분류·QA용이고
이건 **instruction tuning 형식**이라 GEN(응답 생성)에 바로 쓸 수 있다는 게
다르다. 최소 3턴 이상·500자 이상 조건이 실제 Case의 왕복 상담 흐름과
맞는다. 수집처가 카드사·통신사라 쇼핑몰 도메인은 아니지만, GEN이 배워야
할 건 정책 지식(RAG 담당)이 아니라 **응대 형식**이라 도메인 불일치가
치명적이지 않다고 판단했다.
