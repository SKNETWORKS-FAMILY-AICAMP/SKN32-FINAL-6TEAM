---
type: guide
title: REPORT 재생성
description: REPORT는 wiki로 옮기지 않는다. 생성 명령과 입력만 기록하고 다시 만든다
status: draft
tags: [data, documentation]
owners: [human:미배정]
---

# REPORT 재생성

## 왜 이관하지 않나

`[실측]` `datasets/` 에 md 문서가 44개 있다. **wiki로 옮기지 않는다.**

세 가지 이유다.

| 이유 | |
|---|---|
| **데이터와 함께 살아야 한다** | 데이터가 바뀌면 REPORT도 바뀐다. 떨어뜨리면 어긋난다 |
| **상당수가 스크립트로 재생성된다** | 손으로 옮기면 다음 생성 때 사라진다 |
| 폴더 규칙이 이미 있다 | `datasets/<도메인>/<이름>/REPORT.md` |

→ [../../wiki/governance/migration.md](../../wiki/governance/migration.md)

## 무엇을 기록하나

wiki에는 **생성 명령과 입력**만 둔다.

```yaml
automation:
  command: <생성 명령>
  owner: process:<프로세스 이름>
  manual_edit: false
```

**`manual_edit: false`면 손으로 고치지 않는다.** 고쳐야 하면 생성 스크립트를 고친다.

## 각 데이터셋의 스크립트

```text
datasets/<도메인>/<이름>/
├─ raw/         원시.   git 제외
├─ processed/   가공.   git 제외
├─ scripts/     ← 여기가 정본
└─ REPORT.md    ← scripts 가 만들거나 사람이 씀
```

**`scripts/`와 `REPORT.md`만 git에 올린다.**

## 숫자는 디스크를 센다

`[실측]` 이 프로젝트가 두 번 데인 것이다.

> **건수만 세는 검증은 이 프로젝트에서 두 번 실패했다.**

| 대상 | 세는 법 |
|---|---|
| 코퍼스 | `python -m scripts.check_corpus` |
| seed 데이터 | DB 직접 조회 |
| 데이터셋 크기 | **폴더를 센다** |

**문서에 적힌 수를 믿지 않는다.** [catalog.md](catalog.md)의 "VOC 5종 681MB" 사례가 그것이다 — 계획서에 오래 적혀 있었지만 근거가 없었고, 실제로는 4종 924MB였다.

## REPORT에 있어야 할 것

`[실측]` 기존 REPORT들이 공통으로 갖는 절.

```markdown
## 출처          어디서 받았나. URL
## 받은 것        실제 파일 목록
## 선택 이유      왜 이 데이터인가
## 아직 안 한 것   [미확보] 를 숨기지 않는다
## 전처리 결과    날짜와 함께
```

**"아직 안 한 것"이 있는 게 좋은 REPORT다.** 완료된 것만 적으면 무엇이 남았는지 모른다.

## 라이선스

`[실측]` `kaggle_customer_support`의 KR3처럼 **나중에 제약이 더 크다고 밝혀지는 경우**가 있다.

REPORT에 **확인 시점과 함께** 적는다. "확인 안 됨"도 상태다.

## 관계

- [index.md](index.md) — 폴더 규칙
- [catalog.md](catalog.md) — 데이터셋 목록
- [../../wiki/governance/document-standard.md](../../wiki/governance/document-standard.md) — 자동 생성 문서 규칙
- [../../wiki/governance/migration.md](../../wiki/governance/migration.md) — 이관 제외 근거
