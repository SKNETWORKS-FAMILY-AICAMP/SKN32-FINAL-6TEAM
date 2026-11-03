---
type: report
title: 파이널스페이스 이관 백업 미확인 66개 — 의미별 재분류(보존·실사용·기록·미확인)
status: draft
domain: travel
---

# 이관 백업 미확인 66개 의미별 재분류 (2026-10-27)

사용자 지시(2026-10-27): [앞 감사](2026-10-27_finalspace-unmerged-conflicts-reclassification.md)에서 **미확인**으로 남긴 66개(unmerged 3 + conflicts 63)를 내용 의미로 다시 보고 보존·실사용·기록·미확인으로 나누고, 통합이 필요한 대상을 근거와 함께 적는다. **읽기 전용 감사**다. 원본 코드·인덱스·브랜치·백업은 고치지 않았다. 커밋·push 0건. 새로 만든 파일은 이 보고서, 근거 JSON 1개, 인계 1개다. 목차(`wiki/handoff/index.md`·`wiki/index.md`)는 고치지 않았다.

## 결론

- 분류 66/66 = 100%(목록 기준, 기능 동작 검증 비율 아님).
- **보존 44/66 = 66.7%** — 통합하지 않는다. 이름 표기(guguroute↔triPilot)만 다른 것 25개, 원본 작업트리 `_backup` 사전 사본과 같은 bytes인 이전 판 등 8개, 옛 작업공간에서 경로를 일괄로 바꾼 실행 기록 11개.
- **실사용 2/66 = 3.0%** — pin 코드에는 이미 있지만 계약 문서가 빠진 것: 관리자 사용자 목록 계약 색인(#60), UTIC 대기 20초 설정 설명(#62).
- **기록 17/66 = 25.8%** — 제품 동작과는 무관하다. 평가 결과 정정과 연구·현황 기록 보충이며, 4개 묶음으로 통합 후보를 정했다.
- **미확인 3/66 = 4.5%** — 사람 결정이 필요하다: `.codex/hooks.json`, `setup_oracle_model_gpu.sh`, rename 전 EKS manifest. 앞 감사와 같은 3개이며 근거만 보강했다.
- **final_project_cs 런타임 코드를 바꿔야 하는 것은 0개**다. 통합 대상은 모두 문서·평가 기록·평가 도구 결과다.

| 분류 | unmerged | conflicts | 합계 |
|---|---|---|---|
| 보존 | 0 | 44 | 44/66 = 66.7% |
| 실사용 | 0 | 2 | 2/66 = 3.0% |
| 기록 | 0 | 17 | 17/66 = 25.8% |
| 미확인 | 3 | 0 | 3/66 = 4.5% |
| 합계 | 3 | 63 | 66 |

## 분류 기준

- **보존**: 백업에 그대로 둔다. 고유 내용이 이름 표기, 이전·중간 판, 기록 경로 재작성뿐이다. 현재 판이나 사전 사본이 같은 내용을 갖고 있다.
- **실사용**: 현재 정본(pin 코드·설정과 wiki 계약)에 맞는 내용이 백업과 원본 작업트리 미추적 파일에만 있다. 반영하지 않으면 계약 문서가 빠지거나 실제 구현과 문서가 어긋난다.
- **기록**: 정정 주석, 측정값 보충, 결정 사유 같은 기록 가치가 있는 고유 내용이다. 제품 동작에는 영향이 없다. 기록 본문은 고치지 않고 날짜 붙은 정정 주석이나 기록 파일을 더하는 방식으로 다룬다.
- **미확인**: 근거만으로는 정할 수 없어 담당자 결정이 필요하다.

## 방법

1. 앞 감사의 근거(`cache/scratch/unmerged-audit-20261027/rows.json`·`blobs.batch`·격리 bare 저장소, pin `93c7ba8ecf053caedfe54ad7199dd0b9321e4f0b`)를 그대로 썼다. 원본 `.git` 에는 쓰지 않았다(`GIT_OPTIONAL_LOCKS=0`).
2. 행마다 pin·원본 HEAD·원본 작업트리에 없는 고유 줄을 뽑았다. 그 줄을 가장 가까운 현재 줄과 나란히 놓고 의미를 읽었다. 비밀값으로 보이는 패턴은 가렸고, 이 보고서에는 소스 본문을 싣지 않는다.
3. 제품 이름을 정규화(guguroute·TriPilot → triPilot)한 뒤 고유 줄을 다시 셌다.
4. 같은 폴더와 상위 2단계의 원본 작업트리 `_backup/**/같은 파일명`과 sha256·줄 포함을 대조했다(이전 판 판정).
5. 고유 줄이 가리키는 링크 대상이 pin과 원본 작업트리에 있는지, 추적 상태(`git status`/`check-ignore`)를 확인했다. pin 코드·설정 구현 여부는 `git grep` 으로 확인했다.
6. pptx는 zip 멤버와 슬라이드 글자(`a:t`)를 비교했다. JSON 결과는 행 단위로 비교했다.

## 통합 대상

| 묶음 | 대상(# = 앞 감사 번호) | 무엇을 | 근거 | 런타임 영향 |
|---|---|---|---|---|
| **I-1 codex_percall 정정 기록** | #64 · #77 · #85 · #86 · #87 · #88 | 동시 호출 파일명 겹침으로 섞인 루나 반복2 1건을 다시 부른 결과(good 164→165, pass^3 92.4→93.0%)와 생성기 문구, 2026-10-07 보고서·평가방법 조사의 날짜 붙은 정정 주석 | 원본 작업트리의 현재 결과 2파일(`codex_du_report.md`·`gpt-6-luna_rep2.json`) sha256 = `results/_backup/2026-10-16_codex_du_before_rerun/` 사본, 즉 정정 전이다. 백업은 정정 후다. 결과 JSON은 172행 중 1행만 다르다. 코드 수정은 [격리 반영 인계](../../handoff/2026-10-27_codex-percall-uuid-isolated-apply.md)가 별도로 끝냈다(push 대기) | 없음(평가 도구 결과) |
| **I-2 실사용 문서 연결** | #60 · #62 | ① `final_project_cs/wiki/external/index.md` 에 관리자 사용자 목록 계약 줄 + 원본 작업트리 미추적 `admin-users.md` ② `watch-monitoring.md` 에 `travel.utic_timeout_seconds`(20초) 설명 + 미추적 `wiki/records/reports/2026-10-18_oracle-rain-traffic-diagnosis.md` | pin 앱에 관리자 사용자 기능이 있다(`composition.py`·`ops_entrypoint.py`). pin 설정에도 `utic_timeout_seconds: 20` 이 있다(`guardrails.yaml`·`base.py`). 반면 pin wiki에는 두 설명이 모두 없다. 반영할 때 문서와 현재 코드를 대조하고, 「운영 검증 전」 같은 상태 문장은 다시 확인해야 한다 | 없음(문서) |
| **I-3 합성 자료 표현 정정** | #76 · #117 · #118 | 「시험 문장은 모두 합성, 사람 정답 0건」을 「테스트 서버에 팀이 직접 쌓은 채팅 질의가 있고 일부는 사용자가 검수」로 정정 | 같은 정정 표현이 원본 작업트리의 현행 w6 `build_sllm.py`·`build_model_package.py` 에 있다. 10-07 현황 문서와 w5 생성 코드는 정정 전이다. 원본 작업트리 `_backup/2026-10-18_012540_guguroute/` 사본에도 정정판이 있다 | 없음(문서·산출물 생성 코드) |
| **I-4 기록 보충** | #61 · #70 · #71 · #78 · #119 · #120 · #121 · #122 | 10-16 측정 2행, kf-deberta 미연결 사유·수치, 10-13 모니터링·코어 결과 단락, G 평가 준비 절, 미채택 아이디어 색인, 10-17 숙소 문단 링크(계약 문장은 pin이 대체), 팀 주제 메모 | 링크 대상 보고서가 모두 원본 작업트리 미추적으로만 있다. 그중 2개는 **pin 안에서 이미 끊긴 참조**다: pin `2026-10-22_파인튜닝_표준방법_조사와_계획서_초안.md` → `2026-10-16_일정짚기_학습모델_대_임베딩.md`, pin `2026-10-18_guguroute-rename-exceptions.md` → `wiki/research/agent-prompt-passing-idea.md`. `team_branch/` 는 `.gitignore` 대상이라 저장소 통합에서 제외한다 | 없음 |

결정 대기(미확인 3): `.codex/hooks.json` 재연결(사용자), `deploy/arm/setup_oracle_model_gpu.sh` 재사용 여부(운영 담당), EKS 정적 manifest 보관(EKS 담당).

통합 순서 제안: I-2(현재 계약 누락) → I-1(이미 격리 반영된 codex_percall 패치 뒤에 결과·주석) → I-3 → I-4. 모두 pin 격리 사본에서 문서·결과만 더한다. 옛 전체 파일을 pin 위에 덮어쓰지 않는다. 특히 #61 web-intakes.md 는 pin 판이 훨씬 새 판이므로 통째로 복사하지 않는다.

## 보존 판정 요약

| 유형 | 개수 | 근거 |
|---|---|---|
| 이름 표기만 다름 | 25 | 이름을 정규화하면 고유 줄이 0이다. 그중 #100~#116 의 17개는 09-14 중간발표 산출물(`program/산출물양식/w3/`, `.git/info/exclude` 대상)이고, pptx 는 슬라이드 19/19·zip 멤버 123/123 이 같다. 기록 원문은 이름을 바꾸지 않는다(pin `2026-10-18_guguroute-rename-exceptions.md`). 이름을 바꾸기 전 사본은 원본 작업트리 `_backup/2026-10-18_012540_guguroute/` 에 이미 있다 |
| 이전·중간 판 | 8 | #63(pin이 같은 문단을 더 길게 가짐), #73(10-10 계약 정정 전 문구), #79(분석 경로 v1 → pin v1-final), #80~#84(5개 모두 원본 작업트리 `_backup/2026-10-10_*` 사본과 같은 sha256) |
| 경로 재작성 실행 기록 | 11 | #89~#99. 10-16 옛 작업공간에서 `datasets/travel/…` 를 `datasets/core/pointing/…` 로 일괄로 바꿨다. 10-09~10-11 실행 기록은 원문 경로가 정본이다. 원문 경로는 디스크에 있고, 백업 경로 중 `legacy_runs/mx_testset` 은 지금 없다 |

## 한계

- 정적 대조만 했다. 시험·서버 실행은 없다. 줄 집합 비교는 줄 순서와 삭제 의미를 보지 않는다.
- 이전 판 판정에는 파일 mtime(옛 작업공간 일괄 작업 시각)도 참고했다. mtime만으로 판정한 행은 없고, 모두 내용이나 사전 사본 일치로 확인했다.
- 실사용 2건은 문서 누락까지만 확인했다. 문서 내용이 pin 코드 동작과 맞는지는 반영할 때 다시 대조해야 한다.
- 원본 작업트리 `git status` 는 감사 중 1,155 → 1,162줄로 늘었다(다른 세션 작업). 이 감사가 쓴 것은 아래 3파일뿐이다.
- 근거 JSON: [classification66.json](../evidence/2026-10-27_finalspace-unconfirmed66-semantic/classification66.json). 행마다 앞 감사 번호, sha256 앞 12자, 고유 줄 수, 이름 정규화 후 고유 줄 수, 사전 사본 일치, 분류, 묶음, 이유가 들어 있다. 소스 본문과 비밀값은 넣지 않았다. 작업 스크립트는 `cache/scratch/unmerged-semantic-20261027/` 에 있다(24시간 미사용 시 정리될 수 있음).

## 전체 목록

열: # · 앞 감사 # · 정본 경로 · 분류 · 묶음 · sha256 앞 12자 · 근거.
| # | 앞 # | 정본 경로 | 분류 | 묶음 | sha256 | 근거 |
|---|---|---|---|---|---|---|
| 1 | 1 | `.codex/hooks.json` | **미확인** | - | `de9b035d402f` | 옛 PC 경로의 Codex PreToolUse 훅. 원본 작업트리에 `.codex/` 없음, tools/local_data_guard.py 만 있음, AGENTS 규칙에 훅 연결 없음 — 재연결 여부는 사용자 결정 |
| 2 | 2 | `final_project_cs/deploy/arm/setup_oracle_model_gpu.sh` | **미확인** | - | `f184407be8b1` | 10-15 RunPod GPU 서버에 Ollama·학습 E4B 를 옮겨 설치하는 1회성 절차. 원본 작업트리 10-15 원격올라마 보고서만 언급하고 pin 은 model-ssh-tunnel.service 로 운영. 같은 서버를 다시 세울 때 쓰는지 운영 담당 확인 필요 |
| 3 | 3 | `final_project_cs/deploy/eks/namespace.yaml` | **미확인** | - | `72d59d68e6fe` | rename 전 EKS 정적 manifest(tripilot). pin·원본 작업트리에 deploy/eks 없음. 저장소 보관 여부는 EKS 담당 결정 |
| 4 | 60 | `final_project_cs/wiki/external/index.md` | **실사용** | I-2 실사용 문서 연결 | `4b620743586a` | 색인 1줄이 가리키는 admin-users.md 는 원본 작업트리에 미추적(??)으로만 있고 pin 에 없음. pin 앱(composition.py·ops_entrypoint.py)에는 관리자 사용자 목록 기능이 있어 계약 문서가 빠진 상태 |
| 5 | 61 | `final_project_cs/wiki/external/rest-endpoints/web-intakes.md` | **기록** | I-4 기록 보충 | `d449f76f7ff5` | kind_known 2줄은 폐기된 B안(보존 대상). 10-17 숙소 추천 문단 1줄은 pin web-intakes.md 의 후속 숙소 계약(숙소 팀·15km 반경 등)이 대체. 링크된 10-17 보고서는 원본 작업트리 미추적 기록 |
| 6 | 62 | `final_project_cs/wiki/external/watch-monitoring.md` | **실사용** | I-2 실사용 문서 연결 | `4cd58cf3a988` | pin 코드·설정에 travel.utic_timeout_seconds=20 이 구현돼 있으나 pin watch-monitoring.md 에 설명 없음. 근거 보고서 2026-10-18_oracle-rain-traffic-diagnosis.md 는 원본 작업트리 미추적. 문장의 「운영 검증 전」 상태는 반영 시 재확인 필요 |
| 7 | 63 | `final_project_cs/wiki/operations/gpu-work-queue.md` | **보존** | - | `46d2deb32d75` | 같은 10-16 문단의 앞 판. pin 이 같은 문단을 더 길게(커밋 차이·삭제 승인) 가짐 |
| 8 | 64 | `final_project_cs/wiki/records/reports/2026-10-07_오응답_실제경로와_Luna_Sol_비교_x600_반영.md` | **기록** | I-1 codex_percall 정정 묶음 | `2dd8524218f0` | 10-16 정정 주석 2줄(루나 92.4→93.0). 원본 작업트리·pin 은 정정 전. 기록 본문은 두고 날짜 붙은 정정 주석만 더하는 형태 |
| 9 | 65 | `program/baseline/build_baseline_html.py` | **보존** | - | `2b62c858f26e` | 제품 이름 표기(guguroute↔triPilot)만 다름 — 이름 정규화 후 고유 줄 0. 10-18 이름 바꾸기 전 사본이 원본 작업트리 `_backup/2026-10-18_012540_guguroute/` 에 이미 있음 |
| 10 | 66 | `program/baseline/triPilot-baseline-2026-10-12.html` | **보존** | - | `64de24c4ff66` | 제품 이름 표기(guguroute↔triPilot)만 다름 — 이름 정규화 후 고유 줄 0. 10-18 이름 바꾸기 전 사본이 원본 작업트리 `_backup/2026-10-18_012540_guguroute/` 에 이미 있음. (원본 작업트리는 「옮긴 안내」 짧은 판, pin 은 전체 판 — 백업과 무관한 작업트리 차이) |
| 11 | 67 | `program/baseline/triPilot-baseline-2026-10-12.md` | **보존** | - | `0ce84cf2c7f1` | 제품 이름 표기(guguroute↔triPilot)만 다름 — 이름 정규화 후 고유 줄 0. 10-18 이름 바꾸기 전 사본이 원본 작업트리 `_backup/2026-10-18_012540_guguroute/` 에 이미 있음 |
| 12 | 68 | `program/baseline/triPilot-baseline-2026-10-13.html` | **보존** | - | `dc7a0ee8a1ff` | 제품 이름 표기(guguroute↔triPilot)만 다름 — 이름 정규화 후 고유 줄 0. 10-18 이름 바꾸기 전 사본이 원본 작업트리 `_backup/2026-10-18_012540_guguroute/` 에 이미 있음 |
| 13 | 69 | `program/baseline/triPilot-baseline-2026-10-13.md` | **보존** | - | `2ad7fa893264` | 제품 이름 표기(guguroute↔triPilot)만 다름 — 이름 정규화 후 고유 줄 0. 10-18 이름 바꾸기 전 사본이 원본 작업트리 `_backup/2026-10-18_012540_guguroute/` 에 이미 있음 |
| 14 | 70 | `program/baseline/triPilot-verification-status-2026-10-12.html` | **기록** | I-4 기록 보충 | `75768df6e52e` | md 판(#15)에서 생성된 HTML. 고유 내용은 #15 와 같은 단락 + 원본 md SHA-256 표기 차이 |
| 15 | 71 | `program/baseline/triPilot-verification-status-2026-10-12.md` | **기록** | I-4 기록 보충 | `190cbe3d4ce1` | 「모니터링·코어 결과(10-13)」 단락 1개가 원본 작업트리에 없음. 근거 보고서 2026-10-13_감시회차_팀순서_도로사건방향.md 는 pin 에 있음. 나머지는 이름 표기 차이 |
| 16 | 72 | `program/plan/triPilot_구현계획서_v12.html` | **보존** | - | `bb9df1ba74f9` | 제품 이름 표기(guguroute↔triPilot)만 다름 — 이름 정규화 후 고유 줄 0. 10-18 이름 바꾸기 전 사본이 원본 작업트리 `_backup/2026-10-18_012540_guguroute/` 에 이미 있음 |
| 17 | 73 | `program/research/activity_recommendation_20261009/jev-only-flow-20261010.html` | **보존** | - | `6afd85922ebb` | 10-10 계약 정정(flow_actual_contract) 전 문구. 같은 줄이 원본 작업트리 `_backup/2026-10-10_flow_actual_contract/` 사본에 있고 현재판은 정정 후 |
| 18 | 74 | `program/research/baseline_2026-10-10/baseline-writing-guide-v2.html.txt` | **보존** | - | `3f587696a8e3` | 제품 이름 표기(guguroute↔triPilot)만 다름 — 이름 정규화 후 고유 줄 0. 10-18 이름 바꾸기 전 사본이 원본 작업트리 `_backup/2026-10-18_012540_guguroute/` 에 이미 있음 |
| 19 | 75 | `program/research/baseline_2026-10-10/triPilot-baseline-v2.html.txt` | **보존** | - | `21b1f915055b` | 제품 이름 표기(guguroute↔triPilot)만 다름 — 이름 정규화 후 고유 줄 0. 10-18 이름 바꾸기 전 사본이 원본 작업트리 `_backup/2026-10-18_012540_guguroute/` 에 이미 있음 |
| 20 | 76 | `program/research/발표_남은문제_현황점검_2026-10-07.md` | **기록** | I-3 합성 자료 표현 정정 | `2b2068a6be2d` | 「테스트 서버에 팀이 직접 쌓은 채팅 질의, 그 일부는 사용자가 직접 검수」 정정. 같은 표현이 원본 작업트리 현행 w6 build_sllm.py 에 있음 — 10-07 현황 문서는 정정 전 |
| 21 | 77 | `program/research/분류_라우팅_모델_평가방법_조사_2026-10-07.md` | **기록** | I-1 codex_percall 정정 묶음 | `c0e15799081e` | 10-16 정정 주석(루나 93.0) |
| 22 | 78 | `program/research/여행일정_질문인식_모델비교_2026-09-29.md` | **기록** | I-4 기록 보충 | `c442fe18eedd` | 10-16 학습 E4B·Winnow-E4B 측정 2행과 주석. 링크된 2026-10-16_일정짚기_학습모델_대_임베딩.md 는 원본 작업트리 미추적이며 pin 2026-10-22 보고서도 이 파일을 참조 |
| 23 | 79 | `program/scripts/activity_recommendation_bench/build_report.py` | **보존** | - | `d8d9d4d9da29` | 이전 판: 분석 경로 main-20261009-v1. pin 은 v1-final(디스크상 v1 17:45 → v1-final 17:47 생성) |
| 24 | 80 | `program/scripts/activity_recommendation_final_analysis_20261010.py` | **보존** | - | `d2766d135ddf` | 이전 판: 원본 작업트리 `program/scripts/_backup/2026-10-10_analysis_common_repeat/` 와 같은 bytes |
| 25 | 81 | `program/scripts/activity_recommendation_results_audit_20261010.py` | **보존** | - | `2c9c9df7fbc6` | 이전 판: 원본 작업트리 `program/scripts/_backup/2026-10-10_audit_choice_diag/` 와 같은 bytes |
| 26 | 82 | `program/scripts/activity_recommendation_retest/config.json` | **보존** | - | `38bcc65d60c6` | 이전 판: 원본 작업트리 `activity_recommendation_retest/_backup/2026-10-10_choice_rounding_context/` 와 같은 bytes |
| 27 | 83 | `program/scripts/activity_recommendation_retest/providers.py` | **보존** | - | `607a28990fa7` | 이전 판: 원본 작업트리 `activity_recommendation_retest/_backup/2026-10-10_choice_rounding_context/` 와 같은 bytes |
| 28 | 84 | `program/scripts/activity_recommendation_retest/run.py` | **보존** | - | `8e4574b98a77` | 이전 판: 원본 작업트리 `activity_recommendation_retest/_backup/2026-10-10_repeat_call_budget/` 와 같은 bytes |
| 29 | 85 | `program/scripts/plan_qa_bench/codex_du_report.py` | **기록** | I-1 codex_percall 정정 묶음 | `65e6e28613e2` | 보고서 생성기에 10-16 정정 문구 3줄 |
| 30 | 86 | `program/scripts/plan_qa_bench/results/codex_du/gpt-6-luna_rep2.json` | **기록** | I-1 codex_percall 정정 묶음 | `e476535a6778` | 재호출 정정 결과: 172행 중 1행(cases_real 1번)만 다르고 good 164→165. 원본 작업트리 현재 파일 = `results/_backup/2026-10-16_codex_du_before_rerun/` 사본(같은 sha256) = 정정 전 |
| 31 | 87 | `program/scripts/plan_qa_bench/results/codex_du/report.md` | **기록** | I-1 codex_percall 정정 묶음 | `ecefe026d666` | 정정된 보고서(루나 161·165·166, pass^3 93.0%) |
| 32 | 88 | `program/scripts/plan_qa_bench/results/codex_du_report.md` | **기록** | I-1 codex_percall 정정 묶음 | `ecefe026d666` | 정정된 보고서(#31 과 같은 bytes). 원본 작업트리 현재 파일 = before_rerun 사본과 같은 sha256 |
| 33 | 89 | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/adapter_transfer.json` | **보존** | - | `cfd219540503` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 34 | 90 | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/archive_B.py` | **보존** | - | `fb7fef75bc5a` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 35 | 91 | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/record_final.py` | **보존** | - | `3c4671f7878b` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 36 | 92 | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/source_identity.py` | **보존** | - | `e0af430de6e2` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 37 | 93 | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/source_identity_a2.py` | **보존** | - | `4033132620b6` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 38 | 94 | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/source_identity_verification.json` | **보존** | - | `2d3599c35bbf` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 39 | 95 | `program/scripts/plan_qa_bench/results/heartbeat_20261010_1400/E_maturity.json` | **보존** | - | `11fe53f59fe7` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 40 | 96 | `program/scripts/plan_qa_bench/results/heartbeat_20261010_2000/E_maturity.json` | **보존** | - | `843da71e4c6b` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 41 | 97 | `program/scripts/plan_qa_bench/results/heartbeat_20261011_0200/E_maturity.json` | **보존** | - | `26e74b7a0e45` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 42 | 98 | `program/scripts/plan_qa_bench/results/heartbeat_20261011_0800/E_file_recheck.json` | **보존** | - | `0b17e5042353` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 43 | 99 | `program/scripts/plan_qa_bench/results/heartbeat_20261011_0800/E_file_recheck_v2.json` | **보존** | - | `41d01888fee6` | 10-16 19:47 옛 작업공간 일괄 경로 재작성판(datasets/travel/… → datasets/core/pointing/…). 10-09~10-11 실행 기록이라 원문 경로가 정본이며 pin·원본 작업트리 경로(datasets/travel/…)가 디스크에 있음. 백업 경로 중 legacy_runs/mx_testset 은 현재 디스크에 없음 |
| 44 | 100 | `program/산출물양식/w3/[최종프로젝트]중간발표회발표_6팀.pptx` | **보존** | - | `113b93b42dbc` | 슬라이드 19/19·zip 멤버 123/123 동일. 슬라이드 글자 차이는 제품 이름과 공백 run 뿐. 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 45 | 101 | `program/산출물양식/w3/발표구성검토_인트로근거_2026-09-14.md` | **보존** | - | `c5e72236ea8d` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 46 | 102 | `program/산출물양식/w3/발표구성검토_코덱스원문_2026-09-14.md` | **보존** | - | `d5266a732b9d` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 47 | 103 | `program/산출물양식/w3/아키텍처/architecture-diagrams.html` | **보존** | - | `e3afd3cf3a4c` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 48 | 104 | `program/산출물양식/w3/아키텍처/build-v2.js` | **보존** | - | `dd56bdac33e0` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 49 | 105 | `program/산출물양식/w3/아키텍처/svg/08-agent-flow-dark.svg` | **보존** | - | `629932e4eae6` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 50 | 106 | `program/산출물양식/w3/아키텍처/svg/08-agent-flow-light.svg` | **보존** | - | `b91bd386804a` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 51 | 107 | `program/산출물양식/w3/아키텍처/svg/build_08.py` | **보존** | - | `61348e02edeb` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 52 | 108 | `program/산출물양식/w3/아키텍처/v2-01-system.svg` | **보존** | - | `fa5c1f7cb9a6` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 53 | 109 | `program/산출물양식/w3/아키텍처/v2-02-common.svg` | **보존** | - | `69f6bad19e65` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 54 | 110 | `program/산출물양식/w3/아키텍처/v2-03-activity.svg` | **보존** | - | `eefb825225d2` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 55 | 111 | `program/산출물양식/w3/아키텍처/v2-04-dining.svg` | **보존** | - | `f77735f3f5bb` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 56 | 112 | `program/산출물양식/w3/아키텍처/v2-05-mobility.svg` | **보존** | - | `720a73e71eef` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 57 | 113 | `program/산출물양식/w3/인트로/svg/build_intro.py` | **보존** | - | `d39b23fc0392` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 58 | 114 | `program/산출물양식/w3/인트로/svg/intro-1-what-dark.svg` | **보존** | - | `60065189ebfc` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 59 | 115 | `program/산출물양식/w3/인트로/svg/intro-1-what-light.svg` | **보존** | - | `6c1ef552e130` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 60 | 116 | `program/산출물양식/w3/인트로_장별내용_2026-09-14.md` | **보존** | - | `d279ea961cc1` | 제품 이름 표기만 다름(이름 정규화 후 고유 줄 0). 원본 작업트리에서 git 제외(.git/info/exclude `/program/산출물양식/w3/`)인 09-14 발표 산출물 — 기록 원문은 이름을 바꾸지 않는다(2026-10-18 rename-exceptions) |
| 61 | 117 | `program/산출물양식/w5/_공용/plain_terms.py` | **기록** | I-3 합성 자료 표현 정정 | `d947e535a16c` | #20 과 같은 정정(w5 산출물 생성 코드) |
| 62 | 118 | `program/산출물양식/w5/_공용/term_pass.py` | **기록** | I-3 합성 자료 표현 정정 | `26f768707f57` | #20 과 같은 정정(w5 용어 설명) |
| 63 | 119 | `program/산출물양식/w5/AI시스템아키텍처/src/doc_content.py` | **기록** | I-4 기록 보충 | `8c69d9cad27e` | kf-deberta 미연결 사유·비교 수치(72건 33% 대 64%, 24건 50% 대 54%). 근거 보고서 2026-10-14_학습분류모델_kf-deberta_미연결_사유와_성능.md 는 원본 작업트리 미추적 |
| 64 | 120 | `team_branch/나왔던 주제 목록.txt` | **기록** | I-4 기록 보충 | `c578ff82c26a` | 팀 주제·산출물 목록 메모. 백업이 원본 작업트리 판의 상위집합(+35줄, 원본 작업트리 고유 줄 0). team_branch/ 는 .gitignore 대상 — 저장소 통합 아님 |
| 65 | 121 | `wiki/evaluation/metrics.md` | **기록** | I-4 기록 보충 | `6d217aa69781` | 10-18 G 전체 평가 준비 절 + 링크. 링크 대상 보고서와 인계(2026-10-18_G_complete_evaluation_v2.md)는 원본 작업트리 미추적. 「학습 완료 뒤 측정」 상태는 반영 시 재확인 필요 |
| 66 | 122 | `wiki/research/index.md` | **기록** | I-4 기록 보충 | `26aafc03fbd7` | 미채택 아이디어 문서 색인 1줄. 대상 agent-prompt-passing-idea.md 는 원본 작업트리 미추적이며 pin 의 2026-10-18_guguroute-rename-exceptions.md 가 이 파일을 링크(pin 에서 끊긴 링크) |
