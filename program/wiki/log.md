---
type: guide
title: 문서 변경 이력
description: 중앙 허브 wiki의 추가·수정 기록. 최근 무엇이 바뀌었는지 여기서 확인한다
status: draft
---

# 문서 변경 이력

최신이 위다. "최근 뭐 바뀌었어"에 답하려고 전체 wiki를 뒤지지 않게 하는 파일이다.

기록 단위는 **개념 문서**다. 오탈자 수정은 적지 않는다. 다음 중 하나면 적는다.

- 문서 추가·삭제
- 결론이나 수치가 바뀜
- `status`가 바뀜
- 소유자가 바뀜

---

## 2026-09-01 (2) — ★ 검증에서 낡은 수치 발견·정정

`program/scripts/check_wiki.py` 를 만들어 표준을 실제로 검사했다. 그 과정에서 **인용한 평가 수치가 무효 데이터였음**을 발견했다.

### 무엇이 틀렸나

초판이 인용한 `eval/reports/raw_proposed.jsonl`·`raw_baseline_a.jsonl`·`raw_baseline_b.jsonl`은 **2026-08-13 측정이고 `case_id`가 `g-billing-*`인 옛 구독 도메인** 데이터다.

`final_project_cs/CLAUDE.md`가 2026-08-17에 이 측정을 무효로 선언했다. 코퍼스와 golden/holdout이 쇼핑몰 도메인으로 교체됐기 때문이다.

| 항목 | 초판 (무효) | 정정 |
|---|---|---|
| 건당 LLM 비용 | 4.06원 | **3.03원** |
| p50 지연 | 33.9초 | **20.0초** |
| p95 지연 | 50.6초 | **32.2초** |
| Baseline A / B | 0.35 / 0.92원 | **새 도메인 재측정본 없음** |
| 온프레미스 손익분기 | 28,100건 (32명) | **37,600건 (43명)** |
| 자체호스팅 배수 | 2.7~10.5배 | **3.6~14배** |
| 건당 총계 (A-COP 병행) | 1,133원 | **1,132원** |
| LLM 비중 | 0.36% | **0.27%** |

### 결론은 바뀌었나

**방향은 안 바뀌었다.** LLM 비용은 여전히 사람 대비 무시할 수준이고, 지연은 여전히 실시간 채팅에 부적합하다.

**두 가지가 바뀌었다.**

1. **손익분기가 올라갔다.** API가 싸질수록 자체호스팅이 불리해진다. 32명 → 43명
2. **Baseline 비교를 못 한다.** "단순 LLM보다 몇 배 비싸다"를 지금은 말할 수 없다. 중간발표 전 재측정 필요

### 고친 문서

`business/` 4건, `product/` 2건, `evaluation/` 3건, `delivery/` 2건, `decisions/` 1건, `governance/` 2건, `final_project_cs/wiki/context/` 1건.

### 배운 것

**`[실측]` 표기만으로는 부족하다.** 그 측정이 **아직 유효한지**를 함께 봐야 한다. 데이터 파일이 존재한다고 그 숫자가 현재를 대표하지 않는다.

`sources` 필드에 측정 시점과 도메인을 적는 것을 [governance/evidence-grades.md](governance/evidence-grades.md)에 반영해야 한다. `[미확보]`

---

## 2026-09-01 — wiki 신설

### 추가

`program/wiki/` 중앙 허브를 만들었다. 기존 `program/plan/`·`program/research/`의 문서는 아직 이관하지 않았다.

| 영역 | 상태 |
|---|---|
| `product/` | 초안 작성 |
| `business/` | 초안 작성 |
| `architecture/` | 초안 작성 |
| `delivery/` | 초안 작성 |
| `evaluation/` | 초안 작성 |
| `research/` | index만 |
| `decisions/` | D-001 작성, 나머지 index만 |
| `governance/` | 초안 작성 |

전부 `status: draft`다. 이관 문서는 기본 draft로 두고, 사람이 확인한 뒤에만 `stable`로 올린다.

### 결정 기록

- [D-001 결제 소유 경계](decisions/D-001-payment-ownership.md) — 결제 실행은 검증 쇼핑몰이 소유한다

### 미결정으로 올린 것

- 가격 정책, 자체호스팅 채택, 검토·승인 소요시간, 음성 채널 원가

---

## 이관 예정

아래는 아직 `program/plan/`에 있고 이 wiki로 옮겨야 한다.

| 원본 | 목표 | 판정 |
|---|---|---|
| `A-COP_구현계획서_v8.md` (1,466줄) | 여러 영역으로 분할 | 분할 |
| `A-COP_사업성_단위경제.md` | `business/` 4개 문서 | 분할 |
| `A-COP_페인포인트_페르소나_설계.md` | `product/` 2~3개 문서 | 분할 |
| `A-COP_결제소유_경계.md` | `decisions/D-001` | 이관 완료 |
| `A-COP_문서구조_v1.md` | `governance/document-standard.md` | 분할 |
| `A-COP_문서표준_설계_codex초안.md` | 참고자료. 이관 안 함 | 제외 |

전체 범위 산정은 [governance/migration.md](governance/migration.md).
