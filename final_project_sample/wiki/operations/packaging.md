---
type: runbook
title: 배포본 만들기
description: basement를 다른 프로젝트가 쓸 수 있게 내보내는 경로. 내용 주소 매니페스트가 붙는다
status: draft
tags: [release, architecture]
domain: neutral
---

# 배포본 만들기

**sample 이 cs 없이 서는 것과 같은 이유로 이 경로가 있다.** basement 는 이 저장소 안에서만 쓰는 코드가 아니라 **다른 프로젝트가 가져다 쓰는 부품**이다.

## 무엇이 나오나

`[정정 2026-09-10]` `dist/` 바로 아래는 **`basement/` 하나**이고 그 안에 둘이 있다(「dist 안에 셋」으로 적혀 있었다).

```
dist/basement/files/          내보낸 소스
dist/basement/manifest.json   내용 주소 매니페스트
```

`scripts/export_basement.py` 가 만든다.

> Export the reusable basement sources and a **content-addressed manifest**.

**해시로 주소를 매긴다.** 같은 소스면 같은 매니페스트가 나오므로, 받은 쪽이 무엇을 받았는지 대조할 수 있다.

## 빠뜨리면 테스트가 잡는다

`[실측]` `tests/architecture/test_basement_manifest_covers_every_package.py`

**새 패키지를 만들고 매니페스트에 안 넣으면 실패한다.** 배포본에 빠진 채로 나가는 것을 막는다.

`scripts/basement_manifest.py` 의 `BASEMENT_COMPONENTS` 가 목록이다.

## 아직 확인 안 한 것

`[미확보]` 다음 셋을 실행해 보지 않았다.

| | 무엇 |
|---|---|
| `export_basement.py` 실행 | 지금 `dist/` 가 언제 만들어진 것인지 모른다 |
| 받은 쪽에서 import | 다른 프로젝트가 실제로 쓸 수 있는지 |
| `publish_public.py` | 무엇을 어디로 내보내는지 |

**확인 전에는 "된다"고 적지 않는다.**

## 관계

- [local-setup.md](local-setup.md) — 띄우기
- [../quality/architecture-tests.md](../quality/architecture-tests.md) — 매니페스트 검사
