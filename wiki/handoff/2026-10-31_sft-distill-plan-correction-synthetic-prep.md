---
type: handoff
title: SFT 증류 계획 정정·합성 검사 준비물 인계 — 배포 JSON 전체 목표·부정시험 35/35 (2026-10-31)
description: 검토 지적 코드 대조 완료, 배포 decide() 무모델 재현 검사기·부정시험 실제 실행(양성 7/7·부정 35/35·단위 15/15), 관문별 exact 문항 수, 승인 경계 분리 기록. 학습·추론·teacher 라벨·유료·x600 0
status: draft
domain: travel
---

# SFT 증류 계획 정정·합성 검사 준비물 — 인계

보고: [정정·준비물 보고](../../final_project_cs/wiki/records/reports/2026-10-31_sft-distill-plan-correction-synthetic-prep.md) · 준비물: [`program/research/sft_distill_synth_prep_2026-10-31/`](../../program/research/sft_distill_synth_prep_2026-10-31/README.md) · 이전: [독립 검토 인계](2026-10-31_sft-distill-plan-independent-review.md) · [원 계획 인계](2026-10-31_sft-distill-training-plan.md)

## 한 일
- 검토 지적을 대조했습니다. 배포 사본 `decision_unit.py`에서 한 번의 호출 JSON에 `social`·`general_requests`가 필수 칸으로 들어 있었고, 빈 일반 답은 오류 없이 버려졌습니다. G train 18,927행 중 채팅 형식은 0행입니다. 배포 기본 num_ctx는 12288입니다. 상시 학습 승인 기록도 확인했습니다.
- 계획을 정정했습니다. 학습 목표는 배포 JSON 전체입니다. 무학습 대조군 A1(프롬프트)·A2(검색·서버)·A′를 넣고, 관문별로 exact 문항 수를 계산했으며, 승인 경계를 분리했습니다.
- 준비물을 만들었습니다. 배포 `decide()`를 모델 없이 재현하는 어댑터, 손작성 합성 픽스처 7건(가상 장소), 행 검사기, manifest 계약 검사기, 부정 사례 35건, 문항 수 계산기를 만들었습니다.
- 실제로 실행했습니다. 양성 7/7, 부정 35/35, 단위 15/15 = 100%입니다. 배포 서버는 부정 28/35 = 80%를 받아들였으므로, 서버 검증만으로는 라벨 필터가 되지 않습니다. 절제 시험으로 각 검사가 실제로 작동한다는 것도 확인했습니다.

## 하지 않은 것
학습, 모델 적재·추론, teacher 라벨 생성, 유료 호출, x600 접속, 실제·고객 자료 사용, 운영 변경은 모두 0입니다. 원 계획·검토 준비물과 기존 시험 파일은 수정하지 않았고, 원 계획 맨 위에 정정 안내 한 줄만 붙였습니다. 다른 세션의 메모리 진단 중이라 GPU·모델은 건드리지 않았습니다. 커밋·푸시도 0입니다.

## 다음 담당에게
1. 사용자: 상시 학습 승인(`slm-model-evaluation.md`)이 이 트랙에 적용되는지 한 줄 확인이 필요합니다. 새 승인 요청은 아닙니다.
2. 평가자: 메모리 진단이 끝난 뒤 기준선을 num_ctx 12288로 잽니다(G1). B0 vs A′ 파일럿에서 불일치율을 재서 `tools/sample_size_exact.py`를 다시 돌립니다.
3. 라우팅·채팅 구현: A1/A2 무학습 개선판을 만듭니다(G2). 독립 검토 인계의 문안을 사용하십시오.
4. teacher 라벨 허용 지시가 나오면 `tools/target_check.py` 전 부류 통과를 필수 필터로 씁니다. 유료·plain 스키마 출력은 생성 스키마로 다시 검사합니다.
5. 도구 문제: `tools/safe_git.py`가 Python에서 WindowsApps git을 실행하지 못합니다(WinError 5). 실행에 쓰는 venv `date_risk_env_312`는 Hermes scratch(24시간 유휴 정리) 안에 있습니다.
