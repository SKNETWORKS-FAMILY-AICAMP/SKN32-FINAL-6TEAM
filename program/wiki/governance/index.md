---
type: guide
title: Governance
description: 문서를 어떻게 쓰고 어떻게 유지하는가. 6명이 같은 규칙으로 쓰게 만드는 영역
status: draft
---

# Governance

문서 자체에 대한 규칙. **새 문서를 쓰기 전에 여기를 읽는다.**

## 읽기 순서

1. [structure-guide.md](structure-guide.md) — 폴더와 파일을 어떻게 배치하는가
2. [document-standard.md](document-standard.md) — 문서 하나를 어떻게 쓰는가
3. [front-matter.md](front-matter.md) — 문서 머리에 붙이는 메타데이터 규격
4. [evidence-grades.md](evidence-grades.md) — 주장에 근거 등급 붙이는 법
5. [review-policy.md](review-policy.md) — 누가 무엇을 검토하는가
6. [migration.md](migration.md) — 기존 문서를 언제 어떻게 옮기는가

**1번과 2번이 짝이다.** structure-guide는 문서들을 어떻게 **배치**하는가, document-standard는 문서 하나를 어떻게 **쓰는가**를 다룬다.

## 각 문서

| 문서 | 답하는 질문 |
|---|---|
| [structure-guide.md](structure-guide.md) | 새 문서를 어디에 두고, 커지면 어떻게 쪼개는가 |
| [document-standard.md](document-standard.md) | 문서를 어떻게 쓰는가 |
| [front-matter.md](front-matter.md) | `type`은 무엇을 쓰고 언제 무엇이 필수인가 |
| [evidence-grades.md](evidence-grades.md) | 이 숫자가 실측인가 추정인가를 어떻게 표시하는가 |
| [review-policy.md](review-policy.md) | draft를 stable로 올리려면 무엇이 필요한가 |
| [migration.md](migration.md) | 기존 1,285개 문서를 어떻게 처리하는가 |

## 이 표준의 세 원칙

**하나 — 한 문서에 한 개념.** 파일 단위가 아니라 개념 단위로 자른다. 소유자·변경주기·승인단위가 달라지면 다른 문서다.

**둘 — 코드를 다시 적지 않는다.** 코드를 읽으면 아는 것은 문서에 없어도 된다. 문서가 담을 것은 **책임·경계·불변식·관계·결정 이유·구현 위치** 여섯이다.

**셋 — 모르는 것은 모른다고 적는다.** 빈칸으로 두면 나중에 아무도 그게 빈칸이었는지 모른다. `[미확보]`로 적고 무엇이 있어야 채워지는지 쓴다.

## 왜 이렇게 하는가

문서를 사람만 읽는 게 아니다. Claude Code·Codex 같은 코딩 에이전트가 작업 전에 읽는다. 그때 필요한 건 전체를 통독하는 게 아니라 **지금 필요한 두세 개를 싸게 찾아내는 것**이다.

그래서 `index.md`가 단순 목차가 아니라 판단 재료를 준다. 그래서 `description`이 제목보다 중요하다. 그래서 링크를 많이 건다.

기반은 Google OKF(Open Knowledge Format)와 LangChain OpenWiki다. 다만 그대로 쓰지 않고 이 프로젝트에 맞게 줄였다. 무엇을 뺐는지는 [document-standard.md](document-standard.md) 마지막 절에 있다.

## 인접 영역

- [../index.md](../index.md) — 허브 전체 지도
- [../decisions/index.md](../decisions/index.md) — 결정 문서는 별도 골격을 쓴다
