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

## 2026-10-28 원본 입력 대조 보충

원본 작업폴더의 `program/scripts/plan_qa_bench/results/codex_du/gpt-6-luna_rep2.json`(Git 비추적, sha256 `67986b87…8745`)은 **정정 전 자료**입니다. 정정 자료(`e476535a…96ba`, scratch `remaining_local_review/historical_roundtrip_exact_v2`에 보존)와 172행 중 1행(index 1, good false→true)만 다르며 good 집계는 164 대 165입니다. 원본 입력 복사본으로 원본 generator를 실행하면(rc0) 루나 161·164·166, pass^3 92.4%, McNemar 13:11/p0.84가 나오므로, 현재 원본 `codex_du_report.md`의 165·93.0%·13:10/p0.68은 **원본 저장 입력으로는 재생성되지 않습니다**(정정 자료 기준 값). generator가 가리키는 `results/_backup/2026-10-16_codex_du_before_rerun/`도 원본에 없습니다. 원본 자료 덮어쓰기 금지 규칙에 따라 자료 파일은 바꾸지 않았고, 정정 자료 반입 여부는 사용자 결정으로 남깁니다. 실모델·DB 호출 0. 증거: scratch `original_switch_20261028/{hist_regen_result.json,luna_rep2_compare.json}`.
