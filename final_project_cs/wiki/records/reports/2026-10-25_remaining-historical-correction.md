---
type: report
title: 저장자료 기반 역사 정정 보충
status: verified
domain: travel
---

# 저장자료 기반 역사 정정 보충

원래 10-07 보고서와 조사표의 기존 본문·수치는 지우거나 재작성하지 않고 추가 주석으로 연결했습니다. historical_correction_v2.patch의 generator와 generated report 변경만 그대로 적용했습니다.

독립 검토의 고정 입력과 SHA256 manifest를 재사용합니다. 저장 1032행 중 동일 1031행, 차이 1행(gpt-6-luna_rep2.json, cases_real.jsonl index1), 저장 good 집계164→165입니다. 생성 보고의 루나 반복별161·165·166, pass^3 93.0%, McNemar13:10/p0.68은 저장값에 따른 재계산입니다. 원표의92.4%는 당시 값입니다.

과거10-16 당시 모델 재호출·정답성·타임라인은 이번에 재검증하지 않았습니다. generator에 포함된 옛 재호출 서술은 과거 자료의 주장으로 한정하며 이번 실행 사실로 읽지 않습니다. 실모델·외부API·DB 호출0. 입력26파일 해시 대조와 독립 generator의 실제 rc0/LF 동등성은 scratch evidence에 보존합니다.

최종 통합·실행 수치는 [비DB 통합 보고](2026-10-25_remaining-non-db-integration.md)를 따릅니다.
