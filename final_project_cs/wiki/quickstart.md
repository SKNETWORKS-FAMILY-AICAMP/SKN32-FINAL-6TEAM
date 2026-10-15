---
type: guide
title: 여행 제품 코드 읽기
description: cs 구현 wiki 를 처음 읽는 순서 — 개발 역할과 코드·시험 안내부터
status: draft
domain: travel
---

# 여행 제품 코드 읽기

처음에는 [개발 역할](../../wiki/delivery/roles.md)과 [현재 코드·시험 안내](teams/code-layout.md)를 읽습니다. 옛 평면 폴더·고정 handoff 목록을 현재 구조로 옮겨 적지 않습니다.

## 작업 순서

1. [현재 wiki](index.md)에서 해당 기능의 계약을 찾습니다.
2. [TeamRegistry](teams/team-registry.md)와 [Controller](runtime/agentic-controller.md)의 실제 호출 경로를 확인합니다. 선언된 에이전트 팀 선택과 흐름 진행은 다른 책임입니다.
3. 변경된 계약의 성공·실패·권한·부수효과 경계를 시험하고 실행 기록을 남깁니다.

제품의 여행 기능은 `app/domains/travel_ops/`, 공통 실행 규칙은 `app/core/`·`app/application/`, 고객 웹은 `frontend/`에 있습니다. 정확한 파일 소유권은 코드·시험 안내가 소유합니다. 별도 개발 콘솔·sample의 완료 상태를 이 제품의 완료 상태로 사용하지 않습니다.

## 과거 기록

[수정 전 문서](records/commerce_2026-10-11/wiki--quickstart.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../wiki/index.md) — 현재 정본을 찾는 입구


## 이전 절 링크

<a id="final_project_cs-시작하기"></a>
<a id="한-장으로-보는-구조"></a>
<a id="코드와-문서의-대응"></a>
<a id="작업별-진입점"></a>
<a id="-고치기-전에-반드시-확인"></a>
<a id="자주-쓰는-명령"></a>
<a id="2026-09-10-evalrunpy-가-없다--이-명령은-돌지-않는다-러너는-evalrunnersbaseline_abaseline_bproposedpy-이고"></a>
<a id="정답이-모델-입력에-들어가는-문제로-여행-평가-전에-고쳐야-한다루트-wikievaluationprotocolmd"></a>
<a id="테스트-현황"></a>
<a id="다음"></a>
