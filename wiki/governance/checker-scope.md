---
type: guide
title: 현재 wiki 검사기의 대상과 실행법
description: 기존 도구가 현재·생성물·기록·백업을 구분하는 방식
status: draft
domain: travel
---

# 현재 wiki 검사기의 대상과 실행법

검사기는 [check_wiki.py](../../program/scripts/check_wiki.py)라는 Python 프로그램입니다. wiki 글의 머리말·도메인 표시·문서 길이·본문 링크·인용한 코드 경로 등을 검사합니다. 제품 동작이나 글의 사실 여부를 자동 판정하는 프로그램은 아닙니다.

## A안의 실제 대상

기존 프로그램 하나에서 위치별로 검사 범위를 나눕니다. 기본은 현재 본문과 생성 문서입니다. `records/`는 현재 본문 검사에서 분리합니다. `_backup/`와 `_`·`.`로 시작하는 이관/숨김 폴더는 탐색에서 제외합니다. 생성 문서는 검사하되 내용은 생성기로 수정합니다.

워크스페이스 루트에서 실행합니다. 결과는 새 파일 이름으로 보관합니다.

```powershell
python program/scripts/check_wiki.py --json-output <새 결과 파일 경로>
python program/scripts/check_wiki.py --include-records --json-output <다른 새 결과 파일 경로>
```

`--include-records`는 과거 기록의 깨진 링크 통계를 별도로 냅니다. 과거를 현재 사양으로 다시 쓰는 옵션이 아닙니다. [이번 실제 실행 결과](../../program/research/sql_review_2026-10-11/wiki-check.json)를 확인합니다.

## B·C와의 차이

- B는 현재 문서 전용 프로그램을 새로 하나 더 만드는 안입니다. 기존 도구와 중복되므로 채택하지 않습니다.
- C는 검사할 파일을 고정 목록에 하나씩 적는 안입니다. 새 문서 누락 가능성이 있어 기본으로 쓰지 않습니다.

이미 기존 도구에 범위 구분이 반영되어 있어 선택을 다시 요구하지 않습니다. 옛 백업의 상대 링크를 현재 오류로 세지 않습니다. 현재 문서가 존재하지 않는 백업 파일로 링크하면 현재 링크 오류입니다.

## 관계

- [문서 작성 표준](document-standard.md) — 검사 기준
- [머리말 규격](front-matter.md) — 메타데이터 규칙
