---
type: decision
title: 쇼핑몰(커머스) 시절의 자료·코드·데이터는 지금 프로젝트에서 쓰지 않는다
status: accepted
domain: travel
---

# D-023 쇼핑몰 시절의 자료·코드·데이터는 지금 프로젝트에서 쓰지 않는다

## 결정 `[2026-10-03 사용자]`

**쇼핑몰(커머스) 시절에 만든 자료 · 코드 · 데이터는 지금 프로젝트의 판단 · 시험 · 평가 · 시연 · 화면 · 관문(게이트)에 쓰지 않는다.** 남기는 것은 **기록**(`wiki/records/` · 옛 판 문서 · `legacy/`)뿐이다. 새 시험 · 평가 자료 · 예시 · 시연은 **여행 도메인으로 만든다.**

- 위에 적힌 「쓰지 않는다」는 **재료로 가져다 쓰지 않는다**는 뜻이다. 기록을 지우라는 뜻이 아니다 — 옮기고 이름표를 붙인다(되살릴 수 있게 `git mv`).
- 이 결정 전에는 문서에 이 규칙이 **없었다.** 오히려 반대로 적혀 있었다 — 「`app/modules/customer_ops/` 는 지우지 않았다 — 쇼핑몰 시절 기록이자 비교 대상」(`final_project_cs/CLAUDE.md`). **기록으로 남긴다는 부분은 그대로이고, 판단 · 평가 · 관문의 재료로 쓰는 것은 이 결정이 막는다.**

## 왜

도메인을 여행으로 바꾼 뒤(2026-09-08)에도 평가 자료(golden 72 · holdout 24)가 주문 · 배송 · 반품 · 교환 문장 그대로여서 **여행 분류 정확도를 재지 못하고 있었다**(2026-10-03 확인 — 여행 · 일정 · 호텔 · 관광 낱말이 든 줄 0건). 옛 도메인을 재료로 쓰는 한 「통과」가 새 도메인에 대해 아무것도 말해 주지 않는다.

## 이번에 한 것 (2026-10-03)

| 무엇 | 어디로 | 이유 |
|---|---|---|
| 쇼핑몰 평가 자료 `golden.jsonl` · `holdout.jsonl` | `legacy/commerce_eval/eval/datasets/` | 주문 · 배송 · 반품 · 교환 문장 |
| 그 자료를 읽는 평가 도구(러너 셋 · 채점 · 심판 · 라벨링 · 시간 측정 · 시험 3) 와 검사 스크립트 넷 | `legacy/commerce_eval/` (경로 그대로) | 자료가 없으면 못 돈다 · 쇼핑몰 어휘를 허용 목록으로 갖고 있다 |
| **여행 분류 평가 자료** `travel_golden.jsonl`(72) · `travel_holdout.jsonl`(24) | `eval/datasets/` | 서버가 쓰는 어휘(`feedback.INTENTS` · `ISSUE_CODES`)로 만든 여행 문장. 라벨은 **사람 검수 전 초안**(`label_by`) |
| 여행 자료 검사기 | `scripts/verify_travel_eval_datasets.py` | 서버 어휘를 그대로 불러 대조 · 쇼핑몰 낱말이 섞이면 실패 |
| 여행 분류 재생 시험 | `eval/travel_classification/replay.py` | 실제 모델로 정확도 · 엉뚱한 팀 · 지연을 잰다 |

## 아직 남은 것 — 정하실 것

옮기면 시험이 깨지거나 DB · 조립에 걸려 있어 **이번에 건드리지 않았다.**

1. **쇼핑몰 지식 문서 25개**(`knowledge/documents/`) + DB 적재분 + 그것을 쓰는 RAG 시험(쇼핑몰 질의 시험 · 영역 격리 시험).
2. **쇼핑몰 시절 팀 데모**(`app/modules/customer_ops/team_modules/` — `local_team_a` · `local_team_b` · `remote_team_demo`) — `app/composition.py` · `app/core/project_config.py` · 모듈 토글 시험이 부른다. Composer 카탈로그에도 남아 있다.
3. **DB의 쇼핑몰 표**(주문 · 배송 · 결제 …). 제거 마이그레이션이 **이미 준비돼 있다** — `app/infrastructure/db/migrations/pending/015_drop_commerce_domain.sql`. 적용하지 않은 이유가 「평가 하네스가 `orders` · `shipments` 에 쓰고 읽는다」였는데, **그 하네스를 이번에 `legacy/` 로 옮겨 전제가 풀렸다.** 적용 전에 다른 사용처가 없는지 한 번 더 확인해야 한다(DROP 은 되돌릴 수 없다).
4. **루트 `datasets/commerce/`**(쿠팡 · 네이버 주문 기록 · 택배 조회) — 루트 `CLAUDE.md` 데이터 표.
5. **v8 29항목 DoD 관문**(`scripts/verify_dod.py` · 증거 `DoD-15`~`29`)은 쇼핑몰 기준이다. 여행 기준은 v11 §12 26항목(`scripts/verify_dod_v11.py`).

## 확인하는 법

```bash
python -m scripts.verify_travel_eval_datasets        # 여행 평가 자료가 서버 어휘 · 여행 문장인지
grep -rIl "주문번호\|택배\|반품" eval tests --include=*.py --include=*.jsonl --exclude-dir=__pycache__   # 쇼핑몰 낱말이 새로 섞였는지
```
