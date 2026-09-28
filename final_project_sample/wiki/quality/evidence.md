---
type: evidence
title: DoD 증거 색인
description: 30건이 어디서 무엇을 증명하나. cs 와 판정이 갈리는 항목이 있다
status: draft
tags: [testing, evaluation]
domain: neutral
---

# DoD 증거 색인

`[실측]` 2026-09-03. 원본 30건은 `final_project_sample/wiki/records/evidence/` 에 있다.

## 원본이 정본이다

**이 문서는 증거를 복사하지 않는다.** 재현 명령과 출력은 원본에 있고, 여기는 **무엇이 어디서 무엇을 증명하는지**만 적는다.

복사하면 정본이 둘이 된다. → [../../../final_project_cs/wiki/quality/evidence.md](../../../final_project_cs/wiki/quality/evidence.md) 도 같은 방식이다.

## 판정 분포

| 판정 | 건수 |
|---|---|
| 통과 | **25** |
| **부분 통과** | **4** |
| 판정란 없음 | 1 |

### ★ cs 와 갈리는 항목이 있다

`[실측]` 같은 DoD 번호인데 판정이 다르다.

| DoD | sample | cs |
|---|---|---|
| **23** consumer 멱등성 | **부분 통과** — 발행측은 증명, **consumer 측은 대상이 하나뿐** | 통과 (2026-08-20 갱신) |
| **28** 파인튜닝 방어지표 | **부분 통과** — 방어 지표 5종은 만들고 **파인튜닝은 미착수** | 부분 통과 — 파인튜닝 **실행했고 채택 불가** |
| 15 A/B | 부분 통과 | 부분 통과 |
| 17 마일스톤 게이트 | 부분 통과 | 부분 통과 |

**23·28 이 두 저장소의 성격 차이를 그대로 보여준다.**

`[2026-09-10]` 이 표의 23·28 은 **v8 쇼핑몰 판 번호**다(23 consumer 멱등성 · 28 파인튜닝). v11 의 23 은 라우팅 도달성이고 28 은 없다(26항목).

| | |
|---|---|
| **sample** | **계약이 성립하는지**를 본다. consumer 가 하나여도 계약은 증명된다 |
| **cs** | **도메인이 도는지**를 본다. consumer 를 늘려야 통과다 |

`[실측]` **28 은 방향이 반대다.** sample 은 지표만 만들고 안 돌렸고, cs 는 돌렸다.

**다만 cs 의 "못 쓴다"는 결론도 성립하지 않는다** — 파이프라인 밖에서 호출해 근거를 못 받은 상태로 근거 점수를 쟀다. → [../../../wiki/evaluation/dod28-rerun.md](../../../wiki/evaluation/dod28-rerun.md)

**sample 이 안 돌린 게 결과적으로 손해가 아니었다.**

## 실측 원문 `_raw/`

`[실측]` 24건 중 **11건이 인용된다. cs 와 목록이 완전히 같다.**

```
DoD-04_v3 · 05_v4 · 07_v2 · 08 · 09_v2 · 10_v4
11_v3 · 13 · 14 · 17 · 18
```

**같은 것이 우연이 아니다.** 두 저장소가 같은 계약을 같은 방식으로 검증했다는 뜻이다.

**인용된 11건을 끊으면 근거 사슬이 끊긴다.** 나머지 13건은 중간판이다.

`[실측]` 이 분리는 스크립트가 한다 — `program/scripts/migration_scope.py` 의 인용 검사.

## 무엇을 보려고 여기 오나

| 알고 싶은 것 | 어디 |
|---|---|
| **엔진이 다른 도메인에서 도나** | [another-domain.md](another-domain.md) — 10 passed |
| 무엇이 강제되나 | [invariants.md](invariants.md) — 12개 |
| 도메인을 어떻게 바꾸나 | [domain-swap.md](domain-swap.md) |
| **어느 DoD 가 무엇으로 증명됐나** | 이 문서 |

## 낡음

`[미확보]` **각 항목을 다시 돌려보지 않았다.** 재현 명령은 원본에 있으므로 돌릴 수는 있다.

`[실측]` 다만 하나는 확인했다 — `test_engine_serves_another_domain.py` 는 **2026-09-02 에 10 passed** 였다.

## 관계

- [index.md](index.md) — 품질 영역
- [invariants.md](invariants.md) — 불변식 12개
- [../../../final_project_cs/wiki/quality/evidence.md](../../../final_project_cs/wiki/quality/evidence.md) — cs 쪽 같은 색인
