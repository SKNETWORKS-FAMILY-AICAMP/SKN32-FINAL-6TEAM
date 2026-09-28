---
type: dataset
title: AI Hub 102 — 소상공인 고객 주문 질의-응답 텍스트
description: AI Hub 102 — 소상공인 고객 주문 질의-응답 텍스트
status: draft
tags: [data]
domain: commerce
domain_note: 이관 전 스테이징 사본이다. 원문을 형식만 바꿔 담아 둔 곳이라 고치지 않는다
---

# AI Hub 102 — 소상공인 고객 주문 질의-응답 텍스트

## 출처

- AI Hub, `dataSetSn=102`
- `https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=102`
- 다운로드일: 2026-08-20, 사용자가 직접 신청·다운로드
- 구축연도: 2020년 / 최신 업데이트: 2021-11-17(최종 데이터 보완)

## 받은 것

- **라벨링데이터만** — `raw/Training/라벨링데이터_train.zip`,
  `raw/Validation/라벨링데이터_validation.zip`
- 압축 해제 안 함(받은 그대로 zip 상태로 `raw/`에 보관)
- 총 용량: 189MB

## 원 데이터셋 규모(AI Hub 페이지 기준, 아직 이 폴더 안에서 직접 세어본 값 아님)

- 500만 문장/건(콜센터 질의응답 400만 건 + 녹취 기반 질의응답 100만 건)
- 백화점·홈쇼핑·e-commerce 등 유통 관련 콜센터 포함
- 고객 발화·상점 카테고리·Q/A·감성(중립/부정/긍정)·인텐트·개체명 라벨 동시 보유

## 선택 이유

`datasets/voc/sources_catalog/PLAN.md` §교차검증 리서치 참고. 2026-08-20
Claude·Codex(gpt-5.6-luna) 교차검증 리서치에서 Codex가 독립적으로 찾아낸
신규 발견 — 지금까지 확보한 것 중 **최대 규모 + 최다 라벨 종류**(감성+인텐트
+개체명 동시 보유)라 최우선 후보로 분류됐다.
