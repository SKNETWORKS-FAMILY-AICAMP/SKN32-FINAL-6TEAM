---
type: report
title: 이 문서 표준이 무너지는 지점
description: 설계 당시 예측한 약점 9종과, 그중 실제로 일어난 것을 대조한다
status: draft
tags: [governance, documentation]
---

# 이 문서 표준이 무너지는 지점

`[실측]` 원본은 `program/plan/A-COP_문서표준_설계_codex초안.md` §10.

**설계 당시 약점을 미리 적어 뒀다.** 한 달 돌려 봤으니 **무엇이 실제로 일어났는지 대조한다.**

## 예측한 약점 9종과 실제

| 약점 | 예측한 실패 모습 | **실제로 일어났나** |
|---|---|---|
| **한 문서 한 개념** | 계획·결정·TODO 를 한 파일에 붙인다 | **★일어났다.** 분할 10건 · H1 3개짜리 2건 |
| **13개 type** | `report`/`evidence`, `guide`/`runbook` 혼동 | **★일어났다.** 검증 9회를 돌려야 했다 |
| 저장소 간 링크 | 깊이가 바뀌면 깨진다 | **★일어났다.** 305곳 재계산 필요 |
| **새 구조의 권위 착시** | **낡은 이관 문서가 stable 로 보인다** | **막았다** — 전부 `draft` 로 뒀다 |
| `index` 와 `log` 이중 관리 | PR 마다 누락 | 부분적. `index` 연결을 몇 번 놓쳤다 |
| 근거 등급 작성 부담 | 모든 문장에 붙이다 포기 | **안 일어났다.** 사실 주장에만 붙였다 |
| 혼합형의 인지 비용 | 중앙·로컬 위치를 매번 고민 | **일어났다** — `hub 가 한 구현만 가리킨다` 20건 |
| `stale` 알림 피로 | 문서가 한꺼번에 stale | **아직.** 알림을 안 켰다 |
| **`CLAUDE.md` 가 다시 지식 창고가 됨** | 라우터가 아니라 내용을 담는다 | **`[미확보]`** — 아직 wiki 를 안 가리킨다 |

**아홉 중 다섯이 실제로 일어났다.** 예측이 쓸모 있었다.

## ★ 가장 잘 맞은 예측 둘

### "한 문서 한 개념"이 제일 먼저 무너진다

> **줄 수보다 owner·type·변경 주기·승인 단위가 달라지는지를 리뷰한다.**

`[실측]` **줄 수로 잡은 게 맞았다.** 300줄 규칙에 걸린 파일이 실제로 두 가지를 하고 있었다 — `migration-scope`(321줄), `infrastructure-cost`(316줄).

**그런데 줄 수로 안 걸린 것도 있었다** — H1 이 3개인 파일 2건은 **140·210줄**이었다. → [type-verification/round-9.md](type-verification/round-9.md)

### type 혼동은 예측대로였다

> `report`/`evidence`, `guide`/`runbook` 혼동

`[실측]` **정확히 그 둘에서 갈렸다.** 검증 1차에서 `evidence` 를, 2차에서 `runbook` 을 추가했다. **둘 다 두 판정자가 같은 자리에서 막혀서 드러났다.**

## 규약이 무너지기 쉬운 지점 셋

`[실측]` 원본이 짚은 것.

| # | 어디 | 왜 |
|---|---|---|
| 1 | **front matter 선택 필드** | 일정이 급하면 본문만 쓰고 `owner`·`source`·`freshness` 를 뺀다 |
| 2 | **한 문서 한 개념** | 계획·회의·결정·TODO 를 한 파일에 계속 붙인다 |
| 3 | **자동 생성 문서의 수동 수정** | 문서 경고만으로 부족하다 |

**1번의 해법이 이거다.**

> **초안은 빨리 쓸 수 있게 하고, `stable` 전환 시 게시 프로필을 강제한다.**

`[실측]` **[check_wiki.py](review-policy.md) 가 그렇게 돼 있다** — `stable` 인데 필수 필드가 없으면 위반이다. `draft` 는 안 본다.

### 3번은 아직 안 막혀 있다

```yaml
automation:
  command: python dojo.py report
  owner: process:dojo-report
  manual_edit: false
```

`[미확보]` **이 필드가 없다.** 자동 생성 문서를 손으로 고쳐도 검사기가 모른다.

`[실측]` **해당하는 문서가 실제로 있다** — `program/research/테스트_사각지대_실측.md` 는 `python dojo.py report` 가 만든다. 루트 `CLAUDE.md` 가 **"손으로 고치지 않는다"**고 적어 뒀지만 **강제는 없다.**

## 아직 못 정한 것

`[미확보]` 원본 §10.4 가 남긴 것 중 **지금도 안 정해진 것.**

| 무엇 | 어디서 다루나 |
|---|---|
| **wiki 를 실제 저장소 어디에 둘지** | [cutover.md](cutover.md) |
| `stale` 임계값 | 미정 |
| 전역 catalog 를 만들지 | 미정 |

## 관계

- [document-standard.md](document-standard.md) — 문서 하나를 어떻게 쓰나
- [structure-guide.md](structure-guide.md) — 어떻게 배치하나
- [cutover.md](cutover.md) — 언제 실제로 쓰나
- [type-verification/index.md](type-verification/index.md) — type 혼동을 어떻게 줄였나
