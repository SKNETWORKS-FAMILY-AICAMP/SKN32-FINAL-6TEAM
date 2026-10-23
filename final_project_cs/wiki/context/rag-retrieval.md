---
type: guide
title: RAG 검색 경계
description: 여행 정책 검색의 책임·격리·실패 경계와 시점별 실험 기록
status: draft
domain: travel
---

# RAG 검색 경계

## 책임

허용된 여행 정책 근거를 검색해 ContextPack에 전달합니다. 검색 범위는 에이전트 팀 manifest의 `knowledge_scope`, 도구 호출 권한은 `allowed_tools`로 구분합니다.

## 경계

검색은 고객·tenant·허용 scope 범위를 지킵니다. 근거 검색을 실패한 뒤 일반 지식으로 확답하지 않습니다. 여행 코퍼스의 내용·제약은 [여행 코퍼스 정책](travel-corpus.md), 수치형 취소 조건은 [구조화 조건 결정](../decisions/D-CS-006-cancellation-terms-are-structured.md)을 따릅니다.

쇼핑몰 25문서·306청크와 여행 코퍼스가 함께 운영된다는 9월 설명은 현재 안내에서 제외합니다. [D-023](../../../wiki/decisions/D-023-no-commerce-assets-in-use.md)의 로컬 개발 DB 정리 기록을 확인하되, 다른 환경의 현재 건수로 확대하지 않습니다. **[미확보] 오늘 환경별 코퍼스 건수는 이번 문서 수정에서 조회하지 않았으며 해당 DB 조회가 필요합니다.**

## 구현

- [정책 검색기](../../app/infrastructure/rag/retriever.py) — 검색 구현의 정본
- [Context 예산](context-budget.md) — 검색 결과를 담는 예산과 누락 기록

## 불변식·실패

테넌트 격리와 Context 예산 항목은 [불변식 카탈로그](../quality/invariants.md)를 확인합니다. 검색·임베딩 오류와 정상 빈 결과를 구분하고, 누락을 표시합니다. 과거 쇼핑몰 질의의 검색 성공을 여행 검색 통과로 보고하지 않습니다.

## 시점별 기록

[정정 전 전체 본문](../records/reports/2026-10-11_rag-retrieval.md) — 날짜별 계약·검증·초안을 보존했습니다. 날짜가 붙은 결과를 오늘의 전체 통과나 운영 반영으로 읽지 않습니다. 후속 결정이 없는 계약 조항은 원문의 적용 범위를 확인합니다.

### 기존 링크 연결

<a id="인터페이스"></a> [기존 절: 인터페이스](../records/reports/2026-10-11_rag-retrieval.md#인터페이스)
<a id="scope로-좁힌다"></a> [기존 절: scope로 좁힌다](../records/reports/2026-10-11_rag-retrieval.md#scope로-좁힌다)
<a id="코퍼스"></a> [기존 절: 코퍼스](../records/reports/2026-10-11_rag-retrieval.md#코퍼스)
<a id="-코퍼스-게이트"></a> [기존 절: ★ 코퍼스 게이트](../records/reports/2026-10-11_rag-retrieval.md#-코퍼스-게이트)
<a id="-코퍼스에-법령이-들어간다--지어내면-틀린-답을-가르친다"></a> [기존 절: ★ 코퍼스에 법령이 들어간다 — 지어내면 틀린 답을 가르친다](../records/reports/2026-10-11_rag-retrieval.md#-코퍼스에-법령이-들어간다--지어내면-틀린-답을-가르친다)
<a id="25문서-배분"></a> [기존 절: 25문서 배분](../records/reports/2026-10-11_rag-retrieval.md#25문서-배분)
<a id="범위-밖"></a> [기존 절: 범위 밖](../records/reports/2026-10-11_rag-retrieval.md#범위-밖)
<a id="격리"></a> [기존 절: 격리](../records/reports/2026-10-11_rag-retrieval.md#격리)
<a id="예산-안에서-잘린다"></a> [기존 절: 예산 안에서 잘린다](../records/reports/2026-10-11_rag-retrieval.md#예산-안에서-잘린다)
<a id="실패하면-조용히-메우지-않는다"></a> [기존 절: 실패하면 조용히 메우지 않는다](../records/reports/2026-10-11_rag-retrieval.md#실패하면-조용히-메우지-않는다)
<a id="실패-사례"></a> [기존 절: 실패 사례](../records/reports/2026-10-11_rag-retrieval.md#실패-사례)
<a id="관계"></a> [기존 절: 관계](../records/reports/2026-10-11_rag-retrieval.md#관계)

## 관계

- [영역 안내](index.md) — 인접 문서와 읽기 순서
