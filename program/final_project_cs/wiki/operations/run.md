---
type: guide
title: 실행
description: 테스트·평가·서버를 돌리는 명령
status: draft
tags: [testing, evaluation]
owners: [human:미배정]
---

# 실행

## 테스트

**계층 경계부터 본다.** 가장 빠르고 가장 근본적이다.

```bash
python -m pytest tests/architecture -q
```

```bash
python -m pytest tests/contract -q
```

```bash
python -m pytest tests/security -q
```

```bash
python -m pytest -q
```

`[실측]` 2026-08-30 기준 **406 passed** (`-m "not live"`) · skipped 0 · failed 0

live 마크는 별도로 돌린다.

```bash
python -m pytest -m live -q
```

## DoD 검증

```bash
python -m scripts.verify_dod
```

DoD 항목과 evidence 파일 존재를 검사한다.

## 코퍼스 게이트

```bash
python -m scripts.check_corpus
```

**건수만 세지 않는다.** 중복률·제목 점유율·조사 오류를 함께 본다. → [../context/rag-retrieval.md](../context/rag-retrieval.md)

## 평가

```bash
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7
```

```bash
python -m eval.stats.bootstrap --input eval/reports/raw.jsonl --n 10000
```

```bash
python -m eval.stats.mcnemar --input eval/reports/pairs.jsonl
```

**결과 파일의 도메인을 확인한다.** `case_id`가 `g-billing-*`이면 옛 도메인이라 무효다. → [../quality/eval-harness.md](../quality/eval-harness.md)

## 시연 데이터

```bash
python -m scripts.seed_demo_cases
```

`[실측]` 재실행이 안전하다. `case_id`가 `uuid5`로 고정돼 있고 `cases_in_tenant`가 불변이다.

시나리오 2종이 만들어진다.

| 시나리오 | 결과 |
|---|---|
| cust_01 / ORD-0101 배송완료 미수령 | `waiting_approval`에서 멈춤 |
| cust_02 / ORD-0201 교환 기한 문의 | `resolved` 종단 |

**하드코딩 UUID가 없다.** `scripts.seed`가 만든 실제 주문·배송 행을 조회해 근거로 쓴다.

## 개발 서버

`.claude/launch.json`의 `acop-ui` (포트 8041, `--reload`)

화면 4개.

```
/ui/cases  /ui/approvals  /ui/voc  /ui/trace
```

## ★ 백엔드 통과만으로 완료라고 하지 않는다

`[실측]` 이 프로젝트의 규칙이다.

> UI가 있으면 매 단계 **실제로 열어서** 확인한다.

**테스트만으로는 안 잡힌 결함이 실제로 두 건 있었다.**

| 결함 | 어떻게 찾았나 |
|---|---|
| 승인이 409로 막힘 | 브라우저에서 승인 버튼을 눌러 봄 |
| 감사 기록이 대기 큐에 유령으로 남음 | 동 |

## 관계

- [local-setup.md](local-setup.md) — 준비
- [troubleshooting.md](troubleshooting.md) — 막히면
- [../quality/eval-harness.md](../quality/eval-harness.md) — 평가 상세
- [../quality/test-map.md](../quality/test-map.md) — 테스트 위치
