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

## `[2026-10-06 사용자]` 다섯을 압축 백업 후 삭제했다

사용자 지시: 「압축 백업 후 삭제해서 격리하고 전부 여행 관련으로 전환」. **이 지시가 위 본문의 「옮기고 이름표를 붙인다」보다 앞선다.**
(그동안 이 지시가 문서에 적히지 않아 10-03 판에는 「정하실 것」으로 남아 있었다.)
Codex 와 1회차에 같은 판단으로 합의했다 — 다섯 다 삭제 대상이고, **지우기 전에 그것을 부르는 연결을 먼저 끊는다.**

백업: `datasets/_archive/2026-10-06_commerce_removal/`(git 밖 · 압축 파일 1,049개를 풀어 해시 대조 통과)

| # | 무엇 | 한 일 |
|---|---|---|
| 1 | 쇼핑몰 지식 문서 25개 + DB 적재분(25문서 · 306청크) | 파일 삭제 · DB 행 삭제. **격리 시험을 먼저 다시 썼다** — 쇼핑몰 코퍼스를 「다른 영역」 음성 대조군으로 쓰던 6개를 「적재된 scope 는 여행뿐」·「문서 없는 scope 는 빈 결과」로 바꿨다. `scripts/check_corpus.py` 는 쇼핑몰 검사 대신 **되돌아왔는지**를 본다 |
| 2 | DB 쇼핑몰 표 5개(`orders` · `order_items` · `shipments` · `returns` · `products`) | pg_dump 백업(122KB) 뒤 `pending/015_drop_commerce_domain.sql` 적용 — **로컬 개발 DB(`acop_cs`)만.** x600 서버의 cs 프로젝트 서버 DB 는 건드리지 않았다. 통합 시험의 정리 SQL 두 줄도 걷어냈다 |
| 3 | `datasets/commerce/`(100MB — 쿠팡 · 네이버 주문 기록 · 택배 조회 · 팀 배포본) | 압축 백업(48MB) 뒤 삭제. 분할 점검 도구 둘(`program/scripts/check_split_staleness.py` · `migration_scope.py`)과 루트 `CLAUDE.md` 데이터 표에서 뺐다 |
| 4 | v8 29항목 DoD 검사 `scripts/verify_dod.py` | 삭제. 관문(`scripts/check_release_gate.py`) · 명령 시험 · `RULE.md` · `CLAUDE.md` · `wiki/operations/run.md` · 허브 `release-gate.md` 를 여행 기준 `scripts/verify_dod_v11.py` 로 바꿨다 |
| 5 | 쇼핑몰 팀 데모(`app/modules/customer_ops/team_modules/`) | **지울 코드가 없었다** — 폴더는 이미 없다(2026-10-06 빈 캐시 폴더까지 삭제). 문서 언급만 「삭제됨」으로 고쳤다 |

### 남긴 것 하나 — 옛 DoD 증거 문서

`wiki/records/evidence/DoD-15`~`29`(v8 쇼핑몰 기준 15건)는 **지우지 않았다.** Claude 와 Codex 가 같은 판단이다.
`RULE.md` §4.0 이 정한 **기록 폴더의 그때 실제 출력**이고, 이 결정 본문도 「남기는 것은 기록」이라고 적는다.
위험은 하나 — 지금 통과 증거로 오인될 수 있다. 그래서 관문·문서가 v11 을 가리키게 바꿨다.
**사용자가 이것까지 지우라고 하면 지운다**(백업 뒤).

### 되돌리는 법

```bash
# 파일
unzip datasets/_archive/2026-10-06_commerce_removal/datasets_commerce.zip -d .
unzip datasets/_archive/2026-10-06_commerce_removal/knowledge_commerce_corpus.zip -d .
# DB 표
psql -h 127.0.0.1 -p 5433 -U postgres -d acop_cs -f datasets/_archive/2026-10-06_commerce_removal/db_commerce_tables.sql
# DB 지식 행(문서 25 · 청크 306)
\copy knowledge_documents FROM 'datasets/_archive/2026-10-06_commerce_removal/db_commerce_knowledge_documents.csv' CSV HEADER
```

## 확인하는 법

```bash
python -m scripts.verify_travel_eval_datasets        # 여행 평가 자료가 서버 어휘 · 여행 문장인지
grep -rIl "주문번호\|택배\|반품" eval tests --include=*.py --include=*.jsonl --exclude-dir=__pycache__   # 쇼핑몰 낱말이 새로 섞였는지
```
