---
type: report
title: 파이널스페이스 이관 백업(unmerged·conflicts) 파일별 재분류 — 팀 role-manager 93c7ba8e 대조
status: draft
domain: travel
---

# 파이널스페이스 이관 백업 파일별 재분류 (2026-10-27)

사용자 지시(2026-10-27): 이관 백업 `.backup/2026-10-26_finalspace_unmerged` 의 코드와 충돌 백업(`.backup/2026-10-26_finalspace_conflicts`)을 최신 팀 role-manager 와 실제 원본 작업트리에 대조해 파일별로 포함·대체·필요·미확인으로 나눈다. **읽기 전용 감사**다. 원본 코드·인덱스·브랜치는 수정하지 않았고 커밋·push 는 0건이다. 이 보고서 한 파일만 새로 썼다(wiki 목차는 고치지 않음).

## 결론

- 대상 262개 = unmerged 58 + conflicts 204. 분류 완료 262/262 = 100.0%(목록 기준이며 기능 동작 검증 비율이 아님).
- **필요 1개**: `program/scripts/eval_kit/codex_percall.py`(2026-10-16 동시 호출 파일명 겹침 수정, uuid). 팀 pin·원본 작업트리 모두 옛 `time_ns` 판이고, 원본 작업트리에는 이 수정을 요구하는 시험 `test_codex_percall.py`(미추적)만 있다. 제품(final_project_cs) 코드가 아니라 평가 도구다.
- **final_project_cs 제품 코드에서 백업에만 있고 아직 필요한 기능은 0개**로 판정했다. 백업 고유 코드(원격 채팅 REMOTE_CHAT, 종류 모름 B안 kind_known, 일일점검 until 없음, overflow 1차 시험, v5 시안)는 모두 팀 pin 의 후속 구현·결정이나 원본 작업트리의 새 판으로 대체됐다.
- 미확인 중 사람 결정이 필요한 코드·설정 3개: `.codex/hooks.json`(옛 PC 경로 가드 훅), `deploy/arm/setup_oracle_model_gpu.sh`(RunPod 설치 1회성 스크립트), rename 전 EKS 정적 manifest `deploy/eks/_backup/2026-10-18_012540_guguroute/namespace.yaml`. 나머지 미확인은 program 연구 스크립트·결과 JSON·발표 산출물·wiki 문서다(의미 검토 미완).
- 별도 주의: overflow(부하 동원) 기능은 **원본 작업트리에만**(미커밋 F3 판) 있고 팀 pin 에는 없다. 이 백업의 문제가 아니라 원본 작업트리 통합 몫이다.

## 기준

| 항목 | 값 |
|---|---|
| 팀 role-manager pin | `93c7ba8ecf053caedfe54ad7199dd0b9321e4f0b` (2026-10-27 18:54 +09:00, `git ls-remote` 와 격리 fetch exit 0 일치) |
| 원본 HEAD | `efeb873a8d065fbd28fe8e92dcc42e5cfb3de3e3` (role-manager, 2026-10-13) — pin 이 1,062 커밋 앞섬, 원본 고유 커밋 0 (`rev-list --left-right --count` 0/1062) |
| 원본 작업트리 | `git status --porcelain` 1,155줄(그중 final_project_cs 576) — 감사 전후 같음 |
| 참고 브랜치 | team develop `36ba4c2f`, main `e88e0192`, codex/aws-cicd `5be28a27` (EKS manifest 존재 확인용) · 옛 git bundle 11커밋(`.backup/2026-10-26_finalspace_git.bundle`) |
| 격리 환경 | `hermes/profiles/guguroute/cache/scratch/unmerged-audit-20261027/iso.git` (bare, 원본 objects 를 alternates 로 읽기만). 원본 `.git` 에는 fetch 하지 않음 |

## 방법

1. 백업 파일마다 원래 경로(정본 경로)를 정했다. unmerged 의 `<dir>/_backup/<날짜_이름>/<file>` 은 편집 직전 사본(pre-image)이므로 `<dir>/<file>` 로, conflicts 는 같은 상대 경로로 본다.
2. raw·CRLF→LF 정규화 blob 을 pin 끝, 원본 HEAD, 원본 작업트리 파일과 비교하고, pin·HEAD·bundle 이력 전체(`rev-list --objects`)에 같은 blob 이 있는지 찾았다.
3. 남은 파일은 비어 있지 않은 줄 단위로 pin·HEAD·작업트리 어디에도 없는 고유 줄을 세고, 고유 줄이 있는 코드는 기능·호출부·pin 의 후속 결정 문서까지 대조했다(비밀값은 출력하지 않고 키 이름만 확인).
4. 분류 정의 — **포함**: pin 끝과 같거나, 같은 bytes 가 pin 이력에 커밋됐거나, pin 판이 백업 줄을 모두 포함. **대체**: 이전/중간/기각/결함 판이며 같은 기능을 pin 의 후속 구현·결정 또는 원본 작업트리 새 판이 맡음(생성물·런타임 포함). **필요**: pin·원본 작업트리 어디에도 없는 아직 유효한 기능. **미확인**: 근거로 결정하지 못함.

## 집계

| 묶음 | 포함 | 대체 | 필요 | 미확인 | 분모 |
|---|---|---|---|---|---|
| unmerged 전체 | 31/58 = 53.4% | 24/58 = 41.4% | 0/58 = 0.0% | 3/58 = 5.2% | 58 |
| conflicts 전체 | 104/204 = 51.0% | 36/204 = 17.6% | 1/204 = 0.5% | 63/204 = 30.9% | 204 |
| conflicts · cs 코드 | 12/27 = 44.4% | 15/27 = 55.6% | 0/27 = 0.0% | 0/27 = 0.0% | 27 |
| conflicts · cs 문서·생성물·런타임 | 19/41 = 46.3% | 17/41 = 41.5% | 0/41 = 0.0% | 5/41 = 12.2% | 41 |
| conflicts · program·wiki·team_branch | 73/136 = 53.7% | 4/136 = 2.9% | 1/136 = 0.7% | 58/136 = 42.6% | 136 |
| 합계 | 135/262 = 51.5% | 60/262 = 22.9% | 1/262 = 0.4% | 66/262 = 25.2% | 262 |

`포함` 중 pin 끝과 정확히 같은 것: 95/262 = 36.3%. 나머지 포함은 pin 이력 커밋 또는 pin 판이 상위집합인 경우다.

## 주요 근거

| 주제 | 백업 파일 | 판정 근거 |
|---|---|---|
| 원격 채팅 REMOTE_CHAT (10-15) | unmerged deploy/arm 4 + 터널 사본 1, conflicts ollama_adapter·test_adapter·compose | pin·원본 작업트리 REMOTE_CHAT 0건. pin 은 앱 측 `ollama_fallback_base_urls` 와 `deploy/model-ssh-tunnel.service`(RunPod SSH 터널)로 같은 목적을 운영(pin 보고 2026-10-20_oracle-x600-fallback-and-failover-test) → 대체 |
| 종류 모름 B안 kind_known (10-14) | conflicts assemble·candidates, unmerged candidates 사본·test_intake_kind_unknown | pin 보고 2026-10-19_계획읽기_종류모름_처리확인: 새 구조(agent_read 종류 강제 · prefill place_not_found)로 「쓰지 않는다」. pin 앱 kind_known 0건 → 대체. 폐기 확정은 별도 확인으로 남아 있음 |
| 일일점검 until 없음 (10-14) | guardrails 사본 2, conflicts place_info·run_sweepers | pin 은 daily_check(03:00·03:30·08:00)·refresh_from 구현 보유 → 대체 |
| overflow 시험 (10-15) | conflicts test_llm_failover.py (고유 102줄) | 원본 작업트리 overflow 는 F3 판으로 바뀌어 inflight 키(url\|model)·counter 형식이 달라 그대로 맞지 않음. F3 시험이 대체. overflow 기능은 pin 미반영 |
| time_anchor v4/v5 | unmerged conversation 사본 | pin time_anchor.py = v4 사본과 동일 blob. v5 는 폴더명대로 기각 → 대체 |
| rename 결함 (10-18) | unmerged eks/namespace.yaml, conflicts deploy/README.md | pin 보고 2026-10-18_guguroute-rename-exceptions 가 EKS namespace·`__TRIPILOT_HOST__` 변경을 결함으로 판정 → 대체 |
| codex_percall uuid (10-16) | conflicts program/scripts/eval_kit/codex_percall.py | pin 32행 `uid = f'{os.getpid()}_{time.time_ns()}'` 그대로. 원본 작업트리에도 수정 없음 → **필요** |

## 안전한 다음 통합 단위

1. **codex_percall 수정 1파일**: pin `93c7ba8e` 격리 사본에서 백업 판(sha256 `f701e6adf55f7243cc875cc59aa3e3450fcd28babfb721eca96d70387c950d60`)의 uuid 변경만 반영하고, 원본 작업트리의 미추적 `program/scripts/eval_kit/test_codex_percall.py` 를 함께 넣어 그 시험을 실행한다. 다른 파일과 겹치지 않는다. 이 감사에서는 구현·시험 실행을 하지 않았다.
2. 백업에서 final_project_cs 로 되살릴 코드는 없다. 옛 전체 파일을 pin 위에 되돌려 복사하지 않는다(REMOTE_CHAT·kind_known·until 없음은 후속 결정과 충돌).
3. 결정 대기(코드 아님): `.codex/hooks.json` 재연결 여부, `setup_oracle_model_gpu.sh` 운영 필요 여부, EKS 정적 manifest 저장소 보관 여부(EKS 담당).
4. 미확인 문서·연구 스크립트·발표 산출물은 기능 통합 대상이 아니라 기록 선별 대상이다. 필요하면 문서 담당이 같은 목록으로 따로 대조한다.
5. 별도 트랙: 원본 작업트리 미커밋 overflow(F3) 기능의 팀 반영은 이 백업과 무관한 원본 작업트리 통합 단위로 다룬다.

## 한계

- 정적 대조만 했다. 시험·서버 실행 없음. 줄 집합 비교는 줄 순서·삭제 의미를 보지 않으므로, 고유 줄 0 인 파일의 「대체」는 「백업에만 있는 줄이 없다」는 뜻이다.
- 미확인 문서류는 고유 줄 수만 셌고 내용 판단은 하지 않았다.
- 근거 JSON(파일별 blob·sha256·고유 줄 수): `hermes/profiles/guguroute/cache/scratch/unmerged-audit-20261027/rows.json` (scratch, 24시간 미사용 시 정리될 수 있음 — 아래 목록이 영구 기록).

## 전체 목록

열: 묶음 · 백업 상대 경로 · 정본 경로(다를 때만) · 종류 · 분류 · 백업 sha256 앞 12자 · 근거.

| # | 묶음 | 백업 경로 | 정본 경로 | 종류 | 분류 | sha256 | 근거 |
|---|---|---|---|---|---|---|---|
| 1 | unmerged | `.codex/hooks.json` | = | code | **미확인** | `de9b035d402f` | 옛 PC 경로(C:/Users/playdata2/...)의 Codex PreToolUse 훅. 팀 저장소 대상 아님. tools/local_data_guard.py 는 이관됐지만 현재 AGENTS 규칙·훅 연결 없음 — 재연결 여부는 사용자 결정 |
| 2 | unmerged | `final_project_cs/deploy/arm/setup_oracle_model_gpu.sh` | = | code | **미확인** | `f184407be8b1` | RunPod GPU 서버에 Ollama·학습 E4B 를 옮겨 설치하는 1회성 운영 스크립트. pin 에 같은 설치 절차 파일 없음(터널·경로 설정만 있음). 지금 운영에 필요한지는 운영 담당 확인 필요 |
| 3 | unmerged | `final_project_cs/deploy/eks/_backup/2026-10-18_012540_guguroute/namespace.yaml` | `final_project_cs/deploy/eks/namespace.yaml` | code | **미확인** | `72d59d68e6fe` | rename 전 원래 EKS 정적 manifest(tripilot). 팀 role-manager·develop·main·aws-cd 브랜치 어디에도 정적 manifest 없음 — main 의 aws_cd.py 는 기존 Deployment 를 kubectl 로 갱신. 저장소 보관 여부는 EKS 담당(I PR) 결정 |
| 4 | unmerged | `final_project_cs/app/core/_backup/2026-10-15_0102_overflow_hedge/settings.py` | `final_project_cs/app/core/settings.py` | code | **대체** | `727c4a988586` | overflow 추가 전 pre-image. 고유 1줄(ollama_num_ctx 8192)은 pin 12288 로 갱신 |
| 5 | unmerged | `final_project_cs/app/core/_backup/2026-10-18_012540_guguroute/settings.py` | `final_project_cs/app/core/settings.py` | code | **대체** | `2fe9a9c5bda4` | rename 전 pre-image. overflow 설정 2개는 원본 작업트리(미커밋)에 그대로 있음 — 팀 pin 미반영은 원본 작업트리 통합 몫 |
| 6 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-13_2345_resume_new_request/trip_facts.py` | `final_project_cs/app/domains/travel_ops/components/conversation/trip_facts.py` | code | **대체** | `9bb4b50d03fc` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 7 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_1145_service_help_score/trip_messages.py` | `final_project_cs/app/domains/travel_ops/components/conversation/trip_messages.py` | code | **대체** | `a92fbce3e487` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 8 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_2100_anchor_v4/decision_unit.py` | `final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py` | code | **대체** | `fe9b5c70d57a` | at_time 스키마(v3) pre-image. pin은 anchor_kind/anchor_item/anchor_time(v4) 구조, time_anchor.py 는 v4 판과 pin 동일 |
| 9 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_2310_anchor_v4_before_v5/decision_unit.py` | `final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py` | code | **대체** | `713dfb27d4a8` | v5 시도 전 pre-image. 고유 3줄은 fact 튜플 표기 차이, pin decision_unit 은 이후 구조로 변경 |
| 10 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-15_0000_v5_rejected/decision_unit.py` | `final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py` | code | **대체** | `ef7add6f493d` | 폴더명대로 기각된 v5(맨 위 칸 한 번) 시안. pin 은 v4 time_anchor 유지 |
| 11 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-15_0000_v5_rejected/test_time_anchor.py` | `final_project_cs/app/domains/travel_ops/components/conversation/test_time_anchor.py` | code | **대체** | `035b51ce9847` | 기각된 v5 시험. pin tests/unit/travel/test_time_anchor.py 가 v4 계약 시험 |
| 12 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-18_012540_guguroute/decision_unit.py` | `final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py` | code | **대체** | `713dfb27d4a8` | rename 전 pre-image(2310 판과 같은 고유 3줄). pin 은 이후 구조 |
| 13 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-18_012540_guguroute/trip_messages.py` | `final_project_cs/app/domains/travel_ops/components/conversation/trip_messages.py` | code | **대체** | `2a709dbbcb40` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 14 | unmerged | `final_project_cs/app/domains/travel_ops/components/intake/_backup/2026-10-14_1432_kind_unknown/assemble.py` | `final_project_cs/app/domains/travel_ops/components/intake/assemble.py` | code | **대체** | `a4e78ce26289` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 15 | unmerged | `final_project_cs/app/domains/travel_ops/components/intake/_backup/2026-10-14_1432_kind_unknown/review.py` | `final_project_cs/app/domains/travel_ops/components/intake/review.py` | code | **대체** | `f48accb2f22d` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 16 | unmerged | `final_project_cs/app/domains/travel_ops/components/intake/_backup/2026-10-17_012632_lodging_recommendation/candidates.py` | `final_project_cs/app/domains/travel_ops/components/intake/candidates.py` | code | **대체** | `a1f87e2c7f26` | 2026-10-14 B안(kind_known/kind_unknown)은 pin 보고서 2026-10-19_계획읽기_종류모름_처리확인에서 「새 구조(agent_read 종류 강제·prefill place_not_found)로 쓰지 않는다」로 결정. pin 앱 코드 kind_known 0건 |
| 17 | unmerged | `final_project_cs/app/domains/travel_ops/entry/_backup/2026-10-18_012540_guguroute/trip_api.py` | `final_project_cs/app/domains/travel_ops/entry/trip_api.py` | code | **대체** | `400672c859f3` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 18 | unmerged | `final_project_cs/app/infrastructure/_backup/2026-10-14_0100_num_ctx/llm_failover.py` | `final_project_cs/app/infrastructure/llm_failover.py` | code | **대체** | `cad7eac341a2` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 19 | unmerged | `final_project_cs/config/_backup/2026-10-14_1145_service_help_score/guardrails.yaml` | `final_project_cs/config/guardrails.yaml` | code | **대체** | `910bc54fc869` | 2026-10-14 일일점검 「until 없음」은 pin의 후속 결정(daily_check 03:00 시작·03:30 마감·08:00 정지, watch/daily_check.py·refresh_from)으로 대체 |
| 20 | unmerged | `final_project_cs/config/_backup/2026-10-18_012540_guguroute/guardrails.yaml` | `final_project_cs/config/guardrails.yaml` | code | **대체** | `f58cf1918c82` | 2026-10-14 일일점검 「until 없음」은 pin의 후속 결정(daily_check 03:00 시작·03:30 마감·08:00 정지, watch/daily_check.py·refresh_from)으로 대체 |
| 21 | unmerged | `final_project_cs/deploy/arm/_backup/2026-10-18_012540_guguroute/connect_gpu_ollama_tunnel.sh` | `final_project_cs/deploy/arm/connect_gpu_ollama_tunnel.sh` | code | **대체** | `8fa6eb7c8742` | 위 터널 스크립트의 rename 전 판. 2026-10-15 원격 채팅(REMOTE_CHAT) 경로는 팀 pin의 앱 측 다중 Ollama(`ollama_fallback_base_urls`)·`deploy/model-ssh-tunnel.service`(RunPod SSH 터널, 관리 콘솔 SSH 경로)로 대체. pin·원본 작업트리 모두 REMOTE_CHAT 0건 |
| 22 | unmerged | `final_project_cs/deploy/arm/apply_oracle_remote_chat.py` | = | code | **대체** | `552059ad31dd` | 2026-10-15 원격 채팅(REMOTE_CHAT) 경로는 팀 pin의 앱 측 다중 Ollama(`ollama_fallback_base_urls`)·`deploy/model-ssh-tunnel.service`(RunPod SSH 터널, 관리 콘솔 SSH 경로)로 대체. pin·원본 작업트리 모두 REMOTE_CHAT 0건 |
| 23 | unmerged | `final_project_cs/deploy/arm/apply_oracle_remote_chat.sh` | = | code | **대체** | `c37513e1d1ed` | 2026-10-15 원격 채팅(REMOTE_CHAT) 경로는 팀 pin의 앱 측 다중 Ollama(`ollama_fallback_base_urls`)·`deploy/model-ssh-tunnel.service`(RunPod SSH 터널, 관리 콘솔 SSH 경로)로 대체. pin·원본 작업트리 모두 REMOTE_CHAT 0건 |
| 24 | unmerged | `final_project_cs/deploy/arm/connect_gpu_ollama_tunnel.sh` | = | code | **대체** | `e1311053edcf` | 2026-10-15 원격 채팅(REMOTE_CHAT) 경로는 팀 pin의 앱 측 다중 Ollama(`ollama_fallback_base_urls`)·`deploy/model-ssh-tunnel.service`(RunPod SSH 터널, 관리 콘솔 SSH 경로)로 대체. pin·원본 작업트리 모두 REMOTE_CHAT 0건. 같은 목적(오라클→GPU Ollama 터널)을 pin 은 systemd 서비스 템플릿으로 보유 |
| 25 | unmerged | `final_project_cs/deploy/eks/namespace.yaml` | = | code | **대체** | `65c85dcd9d8d` | 10-18 rename 으로 EKS namespace·part-of 라벨을 guguroute 로 바꾼 판. pin 보고서 2026-10-18_guguroute-rename-exceptions 가 운영 식별자 변경을 결함으로 판정 |
| 26 | unmerged | `final_project_cs/frontend/apps/web/tests/live/_backup/2026-10-18_012540_guguroute/stub-server.mjs` | `final_project_cs/frontend/apps/web/tests/live/stub-server.mjs` | code | **대체** | `2aa32fd2c210` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 27 | unmerged | `final_project_cs/tests/unit/travel/test_intake_kind_unknown.py` | = | code | **대체** | `90af5aeafc88` | 2026-10-14 B안(kind_known/kind_unknown)은 pin 보고서 2026-10-19_계획읽기_종류모름_처리확인에서 「새 구조(agent_read 종류 강제·prefill place_not_found)로 쓰지 않는다」로 결정. pin 앱 코드 kind_known 0건 |
| 28 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-13_2345_resume_new_request/case_dispatch.py` | `final_project_cs/app/domains/travel_ops/components/conversation/case_dispatch.py` | code | **포함** | `5abf4208626f` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/case_dispatch.py); pin 끝은 이후 판 |
| 29 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-13_2345_resume_new_request/decision_unit.py` | `final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py` | code | **포함** | `ca314aa19335` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py); pin 끝은 이후 판 |
| 30 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-13_2345_resume_new_request/read_requests.py` | `final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py` | code | **포함** | `5be843ea1a72` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py); pin 끝은 이후 판 |
| 31 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_0200_pointer_num_ctx/item_pointer.py` | `final_project_cs/app/domains/travel_ops/components/conversation/item_pointer.py` | code | **포함** | `77681136ddda` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/item_pointer.py); pin 끝은 이후 판 |
| 32 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_1015_condition_guard/decision_unit.py` | `final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py` | code | **포함** | `de66774dd6d7` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py); pin 끝은 이후 판 |
| 33 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_1030_place_identity/read_requests.py` | `final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py` | code | **포함** | `7b54fb5a2897` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py); pin 끝은 이후 판 |
| 34 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_1800_time_anchor/decision_unit.py` | `final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py` | code | **포함** | `931b2b3945c9` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/decision_unit.py); pin 끝은 이후 판 |
| 35 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_1800_time_anchor/read_requests.py` | `final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py` | code | **포함** | `a5ab42ea4c09` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py); pin 끝은 이후 판 |
| 36 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_2100_anchor_v4/read_requests.py` | `final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py` | code | **포함** | `6d414c186557` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py); pin 끝은 이후 판 |
| 37 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_2100_anchor_v4/test_time_anchor.py` | `final_project_cs/app/domains/travel_ops/components/conversation/test_time_anchor.py` | code | **포함** | `d5334ac8b8a9` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/tests/unit/travel/test_time_anchor.py); pin 끝은 이후 판 |
| 38 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_2100_anchor_v4/time_anchor.py` | `final_project_cs/app/domains/travel_ops/components/conversation/time_anchor.py` | code | **포함** | `2162337d6e89` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/time_anchor.py); pin 끝은 이후 판 |
| 39 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_2310_anchor_v4_before_v5/read_requests.py` | `final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py` | code | **포함** | `6e501186f840` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py); pin 끝은 이후 판 |
| 40 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_2310_anchor_v4_before_v5/test_time_anchor.py` | `final_project_cs/app/domains/travel_ops/components/conversation/test_time_anchor.py` | code | **포함** | `5083747a6768` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/tests/unit/travel/test_time_anchor.py); pin 끝은 이후 판 |
| 41 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-14_2310_anchor_v4_before_v5/time_anchor.py` | `final_project_cs/app/domains/travel_ops/components/conversation/time_anchor.py` | code | **포함** | `5270460ee300` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 42 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-15_0000_v5_rejected/read_requests.py` | `final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py` | code | **포함** | `6e501186f840` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/read_requests.py); pin 끝은 이후 판 |
| 43 | unmerged | `final_project_cs/app/domains/travel_ops/components/conversation/_backup/2026-10-15_0000_v5_rejected/time_anchor.py` | `final_project_cs/app/domains/travel_ops/components/conversation/time_anchor.py` | code | **포함** | `5270460ee300` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 44 | unmerged | `final_project_cs/app/domains/travel_ops/components/intake/_backup/2026-10-14_1432_kind_unknown/candidates.py` | `final_project_cs/app/domains/travel_ops/components/intake/candidates.py` | code | **포함** | `ee9ffd08e4e8` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/intake/candidates.py); pin 끝은 이후 판 |
| 45 | unmerged | `final_project_cs/app/domains/travel_ops/components/intake/_backup/2026-10-17_012632_lodging_recommendation/autofix.py` | `final_project_cs/app/domains/travel_ops/components/intake/autofix.py` | code | **포함** | `a4376d7038cd` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/intake/autofix.py); pin 끝은 이후 판 |
| 46 | unmerged | `final_project_cs/app/infrastructure/_backup/2026-10-13_2330_warm_timeout/llm_failover.py` | `final_project_cs/app/infrastructure/llm_failover.py` | code | **포함** | `37cf8ad33342` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/infrastructure/llm_failover.py); pin 끝은 이후 판 |
| 47 | unmerged | `final_project_cs/app/infrastructure/_backup/2026-10-15_0102_overflow_hedge/llm_failover.py` | `final_project_cs/app/infrastructure/llm_failover.py` | code | **포함** | `4b5db0982708` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/infrastructure/llm_failover.py); pin 끝은 이후 판 |
| 48 | unmerged | `final_project_cs/app/infrastructure/_backup/2026-10-18_012540_guguroute/ollama_chat.py` | `final_project_cs/app/infrastructure/ollama_chat.py` | code | **포함** | `fe2078364d85` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/infrastructure/ollama_chat.py); pin 끝은 이후 판 |
| 49 | unmerged | `final_project_cs/deploy/arm/_backup/2026-10-15_0110_remote_chat/ollama_adapter.py` | `final_project_cs/deploy/arm/ollama_adapter.py` | code | **포함** | `894226b5d01a` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 50 | unmerged | `final_project_cs/frontend/apps/web/src/lib/live/_backup/2026-10-14_1045_gateway_502/stream.test.ts` | `final_project_cs/frontend/apps/web/src/lib/live/stream.test.ts` | code | **포함** | `134f34d1efc6` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/frontend/apps/web/src/lib/live/stream.test.ts); pin 끝은 이후 판 |
| 51 | unmerged | `final_project_cs/tests/_backup/2026-10-17_014043_lodging_suite/test-suites.json` | `final_project_cs/tests/test-suites.json` | code | **포함** | `0d245d28f8ed` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/tests/test-suites.json); pin 끝은 이후 판 |
| 52 | unmerged | `final_project_cs/tests/architecture/_backup/2026-10-14_cells_skip_backup/test_travel_ops_cells.py` | `final_project_cs/tests/architecture/test_travel_ops_cells.py` | code | **포함** | `28c8c493cde1` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/tests/architecture/test_travel_ops_cells.py); pin 끝은 이후 판 |
| 53 | unmerged | `final_project_cs/tests/e2e/test_intake_lodging_recommendation.py` | = | code | **포함** | `5c92e3a7a6d9` | 백업 모든 줄이 pin 판에 있음(pin 이 95줄 더 큼) |
| 54 | unmerged | `final_project_cs/tests/unit/infrastructure/_backup/2026-10-15_0102_overflow_hedge/test_llm_failover.py` | `final_project_cs/tests/unit/infrastructure/test_llm_failover.py` | code | **포함** | `a3d0c9d5d540` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/tests/unit/infrastructure/test_llm_failover.py); pin 끝은 이후 판 |
| 55 | unmerged | `final_project_cs/tests/unit/travel/_backup/2026-10-14_0140_ignore_fields/test_schedule_query.py` | `final_project_cs/tests/unit/travel/test_schedule_query.py` | code | **포함** | `52bb89f0d825` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/tests/unit/travel/test_schedule_query.py); pin 끝은 이후 판 |
| 56 | unmerged | `final_project_cs/tests/unit/travel/_backup/2026-10-14_1030_place_identity/test_read_requests.py` | `final_project_cs/tests/unit/travel/test_read_requests.py` | code | **포함** | `b1fadf5266ae` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/tests/unit/travel/test_read_requests.py); pin 끝은 이후 판 |
| 57 | unmerged | `final_project_cs/tests/unit/travel/test_intake_lodging_candidates.py` | = | code | **포함** | `0dde4b350b42` | 백업 모든 줄이 pin 판에 있음(pin 이 1줄 더 많음) |
| 58 | unmerged | `final_project_cs/tests/unit/travel/test_tour_daily_check.py` | = | code | **포함** | `8da58080149b` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/tests/unit/travel/test_tour_daily_check.py); pin 끝은 이후 판 |
| 59 | conflicts | `program/scripts/eval_kit/codex_percall.py` | = | code | **필요** | `f701e6adf55f` | 2026-10-16 동시 호출 파일명 겹침 결함 수정(uuid). pin·원본 작업트리 codex_percall.py 는 옛 time_ns 판인데 원본 작업트리에 이 수정의 시험 test_codex_percall.py(미추적)만 있음. 제품 코드 아님(program 평가 도구) |
| 60 | conflicts | `final_project_cs/wiki/external/index.md` | = | doc | **미확인** | `4b620743586a` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 61 | conflicts | `final_project_cs/wiki/external/rest-endpoints/web-intakes.md` | = | doc | **미확인** | `d449f76f7ff5` | kind_known 계약 2줄은 B안(미사용 결정)이나 10-17 숙소 추천 계약 문단 1줄은 pin 문서에 없음 — 문서 대조 필요 |
| 62 | conflicts | `final_project_cs/wiki/external/watch-monitoring.md` | = | doc | **미확인** | `4cd58cf3a988` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 63 | conflicts | `final_project_cs/wiki/operations/gpu-work-queue.md` | = | doc | **미확인** | `46d2deb32d75` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 64 | conflicts | `final_project_cs/wiki/records/reports/2026-10-07_오응답_실제경로와_Luna_Sol_비교_x600_반영.md` | = | doc | **미확인** | `2dd8524218f0` | pin·HEAD·원본 작업트리에 없는 줄 2개 — 문서·산출물 의미 검토 미완 |
| 65 | conflicts | `program/baseline/build_baseline_html.py` | = | doc | **미확인** | `2b62c858f26e` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 66 | conflicts | `program/baseline/triPilot-baseline-2026-10-12.html` | = | doc | **미확인** | `64de24c4ff66` | pin·HEAD·원본 작업트리에 없는 줄 2개 — 문서·산출물 의미 검토 미완 |
| 67 | conflicts | `program/baseline/triPilot-baseline-2026-10-12.md` | = | doc | **미확인** | `0ce84cf2c7f1` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 문서·산출물 의미 검토 미완 |
| 68 | conflicts | `program/baseline/triPilot-baseline-2026-10-13.html` | = | doc | **미확인** | `dc7a0ee8a1ff` | pin·HEAD·원본 작업트리에 없는 줄 2개 — 문서·산출물 의미 검토 미완 |
| 69 | conflicts | `program/baseline/triPilot-baseline-2026-10-13.md` | = | doc | **미확인** | `2ad7fa893264` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 문서·산출물 의미 검토 미완 |
| 70 | conflicts | `program/baseline/triPilot-verification-status-2026-10-12.html` | = | doc | **미확인** | `75768df6e52e` | pin·HEAD·원본 작업트리에 없는 줄 4개 — 문서·산출물 의미 검토 미완 |
| 71 | conflicts | `program/baseline/triPilot-verification-status-2026-10-12.md` | = | doc | **미확인** | `190cbe3d4ce1` | pin·HEAD·원본 작업트리에 없는 줄 4개 — 문서·산출물 의미 검토 미완 |
| 72 | conflicts | `program/plan/triPilot_구현계획서_v12.html` | = | doc | **미확인** | `bb9df1ba74f9` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 73 | conflicts | `program/research/activity_recommendation_20261009/jev-only-flow-20261010.html` | = | doc | **미확인** | `6afd85922ebb` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 74 | conflicts | `program/research/baseline_2026-10-10/baseline-writing-guide-v2.html.txt` | = | doc | **미확인** | `3f587696a8e3` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 75 | conflicts | `program/research/baseline_2026-10-10/triPilot-baseline-v2.html.txt` | = | doc | **미확인** | `21b1f915055b` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 문서·산출물 의미 검토 미완 |
| 76 | conflicts | `program/research/발표_남은문제_현황점검_2026-10-07.md` | = | doc | **미확인** | `2b2068a6be2d` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 77 | conflicts | `program/research/분류_라우팅_모델_평가방법_조사_2026-10-07.md` | = | doc | **미확인** | `c0e15799081e` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 78 | conflicts | `program/research/여행일정_질문인식_모델비교_2026-09-29.md` | = | doc | **미확인** | `c442fe18eedd` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 문서·산출물 의미 검토 미완 |
| 79 | conflicts | `program/scripts/activity_recommendation_bench/build_report.py` | = | code | **미확인** | `d8d9d4d9da29` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 코드 의미 검토 미완 |
| 80 | conflicts | `program/scripts/activity_recommendation_final_analysis_20261010.py` | = | code | **미확인** | `d2766d135ddf` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 코드 의미 검토 미완 |
| 81 | conflicts | `program/scripts/activity_recommendation_results_audit_20261010.py` | = | code | **미확인** | `2c9c9df7fbc6` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 코드 의미 검토 미완 |
| 82 | conflicts | `program/scripts/activity_recommendation_retest/config.json` | = | code | **미확인** | `38bcc65d60c6` | pin·HEAD·원본 작업트리에 없는 줄 7개 — 코드 의미 검토 미완 |
| 83 | conflicts | `program/scripts/activity_recommendation_retest/providers.py` | = | code | **미확인** | `607a28990fa7` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 코드 의미 검토 미완 |
| 84 | conflicts | `program/scripts/activity_recommendation_retest/run.py` | = | code | **미확인** | `8e4574b98a77` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 코드 의미 검토 미완 |
| 85 | conflicts | `program/scripts/plan_qa_bench/codex_du_report.py` | = | code | **미확인** | `65e6e28613e2` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 코드 의미 검토 미완 |
| 86 | conflicts | `program/scripts/plan_qa_bench/results/codex_du/gpt-6-luna_rep2.json` | = | code | **미확인** | `e476535a6778` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 코드 의미 검토 미완 |
| 87 | conflicts | `program/scripts/plan_qa_bench/results/codex_du/report.md` | = | doc | **미확인** | `ecefe026d666` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 문서·산출물 의미 검토 미완 |
| 88 | conflicts | `program/scripts/plan_qa_bench/results/codex_du_report.md` | = | doc | **미확인** | `ecefe026d666` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 문서·산출물 의미 검토 미완 |
| 89 | conflicts | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/adapter_transfer.json` | = | code | **미확인** | `cfd219540503` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 코드 의미 검토 미완 |
| 90 | conflicts | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/archive_B.py` | = | code | **미확인** | `fb7fef75bc5a` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 코드 의미 검토 미완 |
| 91 | conflicts | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/record_final.py` | = | code | **미확인** | `3c4671f7878b` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 코드 의미 검토 미완 |
| 92 | conflicts | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/source_identity.py` | = | code | **미확인** | `e0af430de6e2` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 코드 의미 검토 미완 |
| 93 | conflicts | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/source_identity_a2.py` | = | code | **미확인** | `4033132620b6` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 코드 의미 검토 미완 |
| 94 | conflicts | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/source_identity_verification.json` | = | code | **미확인** | `2d3599c35bbf` | pin·HEAD·원본 작업트리에 없는 줄 2개 — 코드 의미 검토 미완 |
| 95 | conflicts | `program/scripts/plan_qa_bench/results/heartbeat_20261010_1400/E_maturity.json` | = | code | **미확인** | `11fe53f59fe7` | pin·HEAD·원본 작업트리에 없는 줄 4개 — 코드 의미 검토 미완 |
| 96 | conflicts | `program/scripts/plan_qa_bench/results/heartbeat_20261010_2000/E_maturity.json` | = | code | **미확인** | `843da71e4c6b` | pin·HEAD·원본 작업트리에 없는 줄 4개 — 코드 의미 검토 미완 |
| 97 | conflicts | `program/scripts/plan_qa_bench/results/heartbeat_20261011_0200/E_maturity.json` | = | code | **미확인** | `26e74b7a0e45` | pin·HEAD·원본 작업트리에 없는 줄 4개 — 코드 의미 검토 미완 |
| 98 | conflicts | `program/scripts/plan_qa_bench/results/heartbeat_20261011_0800/E_file_recheck.json` | = | code | **미확인** | `0b17e5042353` | pin·HEAD·원본 작업트리에 없는 줄 4개 — 코드 의미 검토 미완 |
| 99 | conflicts | `program/scripts/plan_qa_bench/results/heartbeat_20261011_0800/E_file_recheck_v2.json` | = | code | **미확인** | `41d01888fee6` | pin·HEAD·원본 작업트리에 없는 줄 4개 — 코드 의미 검토 미완 |
| 100 | conflicts | `program/산출물양식/w3/[최종프로젝트]중간발표회발표_6팀.pptx` | = | doc | **미확인** | `113b93b42dbc` | pin·HEAD·원본 작업트리에 없는 줄 290개 — 문서·산출물 의미 검토 미완 |
| 101 | conflicts | `program/산출물양식/w3/발표구성검토_인트로근거_2026-09-14.md` | = | doc | **미확인** | `c5e72236ea8d` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 문서·산출물 의미 검토 미완 |
| 102 | conflicts | `program/산출물양식/w3/발표구성검토_코덱스원문_2026-09-14.md` | = | doc | **미확인** | `d5266a732b9d` | pin·HEAD·원본 작업트리에 없는 줄 5개 — 문서·산출물 의미 검토 미완 |
| 103 | conflicts | `program/산출물양식/w3/아키텍처/architecture-diagrams.html` | = | doc | **미확인** | `e3afd3cf3a4c` | pin·HEAD·원본 작업트리에 없는 줄 5개 — 문서·산출물 의미 검토 미완 |
| 104 | conflicts | `program/산출물양식/w3/아키텍처/build-v2.js` | = | doc | **미확인** | `dd56bdac33e0` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 105 | conflicts | `program/산출물양식/w3/아키텍처/svg/08-agent-flow-dark.svg` | = | doc | **미확인** | `629932e4eae6` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 106 | conflicts | `program/산출물양식/w3/아키텍처/svg/08-agent-flow-light.svg` | = | doc | **미확인** | `b91bd386804a` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 107 | conflicts | `program/산출물양식/w3/아키텍처/svg/build_08.py` | = | doc | **미확인** | `61348e02edeb` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 108 | conflicts | `program/산출물양식/w3/아키텍처/v2-01-system.svg` | = | doc | **미확인** | `fa5c1f7cb9a6` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 109 | conflicts | `program/산출물양식/w3/아키텍처/v2-02-common.svg` | = | doc | **미확인** | `69f6bad19e65` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 110 | conflicts | `program/산출물양식/w3/아키텍처/v2-03-activity.svg` | = | doc | **미확인** | `eefb825225d2` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 111 | conflicts | `program/산출물양식/w3/아키텍처/v2-04-dining.svg` | = | doc | **미확인** | `f77735f3f5bb` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 112 | conflicts | `program/산출물양식/w3/아키텍처/v2-05-mobility.svg` | = | doc | **미확인** | `720a73e71eef` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 113 | conflicts | `program/산출물양식/w3/인트로/svg/build_intro.py` | = | doc | **미확인** | `d39b23fc0392` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 문서·산출물 의미 검토 미완 |
| 114 | conflicts | `program/산출물양식/w3/인트로/svg/intro-1-what-dark.svg` | = | doc | **미확인** | `60065189ebfc` | pin·HEAD·원본 작업트리에 없는 줄 2개 — 문서·산출물 의미 검토 미완 |
| 115 | conflicts | `program/산출물양식/w3/인트로/svg/intro-1-what-light.svg` | = | doc | **미확인** | `6c1ef552e130` | pin·HEAD·원본 작업트리에 없는 줄 2개 — 문서·산출물 의미 검토 미완 |
| 116 | conflicts | `program/산출물양식/w3/인트로_장별내용_2026-09-14.md` | = | doc | **미확인** | `d279ea961cc1` | pin·HEAD·원본 작업트리에 없는 줄 6개 — 문서·산출물 의미 검토 미완 |
| 117 | conflicts | `program/산출물양식/w5/AI시스템아키텍처/src/doc_content.py` | = | code | **미확인** | `8c69d9cad27e` | pin·HEAD·원본 작업트리에 없는 줄 3개 — 코드 의미 검토 미완 |
| 118 | conflicts | `program/산출물양식/w5/_공용/plain_terms.py` | = | code | **미확인** | `d947e535a16c` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 코드 의미 검토 미완 |
| 119 | conflicts | `program/산출물양식/w5/_공용/term_pass.py` | = | code | **미확인** | `26f768707f57` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 코드 의미 검토 미완 |
| 120 | conflicts | `team_branch/나왔던 주제 목록.txt` | = | doc | **미확인** | `c578ff82c26a` | pin·HEAD·원본 작업트리에 없는 줄 35개 — 문서·산출물 의미 검토 미완 |
| 121 | conflicts | `wiki/evaluation/metrics.md` | = | doc | **미확인** | `6d217aa69781` | pin·HEAD·원본 작업트리에 없는 줄 2개 — 문서·산출물 의미 검토 미완 |
| 122 | conflicts | `wiki/research/index.md` | = | doc | **미확인** | `26aafc03fbd7` | pin·HEAD·원본 작업트리에 없는 줄 1개 — 문서·산출물 의미 검토 미완 |
| 123 | conflicts | `final_project_cs/app/domains/travel_ops/components/intake/assemble.py` | = | code | **대체** | `cf1c1bd1010b` | 2026-10-14 B안(kind_known/kind_unknown)은 pin 보고서 2026-10-19_계획읽기_종류모름_처리확인에서 「새 구조(agent_read 종류 강제·prefill place_not_found)로 쓰지 않는다」로 결정. pin 앱 코드 kind_known 0건 |
| 124 | conflicts | `final_project_cs/app/domains/travel_ops/components/intake/autofix.py` | = | code | **대체** | `e9bd236a4277` | 고유 1줄은 주석. 나머지는 HEAD 판, pin 이 이후 판 |
| 125 | conflicts | `final_project_cs/app/domains/travel_ops/components/intake/candidates.py` | = | code | **대체** | `dda8ad948ee6` | 2026-10-14 B안(kind_known/kind_unknown)은 pin 보고서 2026-10-19_계획읽기_종류모름_처리확인에서 「새 구조(agent_read 종류 강제·prefill place_not_found)로 쓰지 않는다」로 결정. pin 앱 코드 kind_known 0건. 나머지 숙소 줄은 pin 숙소 추천 구현(lodging_context 등)으로 대체 |
| 126 | conflicts | `final_project_cs/app/domains/travel_ops/components/itinerary/itinerary.py` | = | code | **대체** | `d98357fe8576` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 127 | conflicts | `final_project_cs/app/domains/travel_ops/components/places/place_info.py` | = | code | **대체** | `c9a6813eaa2a` | 2026-10-14 일일점검 「until 없음」은 pin의 후속 결정(daily_check 03:00 시작·03:30 마감·08:00 정지, watch/daily_check.py·refresh_from)으로 대체 (pin place_info 에 refresh_from 있음) |
| 128 | conflicts | `final_project_cs/app/domains/travel_ops/components/watch/simulation.py` | = | code | **대체** | `e7ea923854ed` | 재난 정지 여행 409 검사 — pin simulation.py 에 같은 검사(문구 개선)가 있음 |
| 129 | conflicts | `final_project_cs/deploy/README.md` | = | doc | **대체** | `0ec5475fa0ac` | `__guguroute_HOST__` 는 rename 결함(자리표시 변경). pin 은 Caddyfile.tripilot 의 `__TRIPILOT_HOST__` 유지 |
| 130 | conflicts | `final_project_cs/deploy/arm/compose.yml` | = | code | **대체** | `75e29536f874` | 2026-10-15 원격 채팅(REMOTE_CHAT) 경로는 팀 pin의 앱 측 다중 Ollama(`ollama_fallback_base_urls`)·`deploy/model-ssh-tunnel.service`(RunPod SSH 터널, 관리 콘솔 SSH 경로)로 대체. pin·원본 작업트리 모두 REMOTE_CHAT 0건 |
| 131 | conflicts | `final_project_cs/deploy/arm/ollama_adapter.py` | = | code | **대체** | `bc50f8481d43` | 2026-10-15 원격 채팅(REMOTE_CHAT) 경로는 팀 pin의 앱 측 다중 Ollama(`ollama_fallback_base_urls`)·`deploy/model-ssh-tunnel.service`(RunPod SSH 터널, 관리 콘솔 SSH 경로)로 대체. pin·원본 작업트리 모두 REMOTE_CHAT 0건 |
| 132 | conflicts | `final_project_cs/deploy/arm/test_adapter.py` | = | code | **대체** | `6bc2da6cfb81` | 2026-10-15 원격 채팅(REMOTE_CHAT) 경로는 팀 pin의 앱 측 다중 Ollama(`ollama_fallback_base_urls`)·`deploy/model-ssh-tunnel.service`(RunPod SSH 터널, 관리 콘솔 SSH 경로)로 대체. pin·원본 작업트리 모두 REMOTE_CHAT 0건 (원격 경로 시험) |
| 133 | conflicts | `final_project_cs/deploy/make_server_env.py` | = | code | **대체** | `bd5878829b74` | ACOP_OLLAMA_NUM_CTX=8192·9초 주석 — pin 은 num_ctx 12288·primary_timeout 9.0 으로 갱신 |
| 134 | conflicts | `final_project_cs/frontend/apps/admin/next-env.d.ts` | = | generated | **대체** | `098aa2acbeda` | Next 생성물(추적 안 함). 원본 작업트리에 재생성본 있음 |
| 135 | conflicts | `final_project_cs/frontend/apps/admin/src/lib/gateway.ts` | = | code | **대체** | `31afcce375cd` | operationSimulations(tripId, query) — pin 에 같은 시그니처 구현 있음 |
| 136 | conflicts | `final_project_cs/frontend/apps/admin/tsconfig.json` | = | code | **대체** | `6a8f4c704b76` | 로컬 .next-* 빌드 폴더 include 5줄뿐. 원본 작업트리=pin |
| 137 | conflicts | `final_project_cs/frontend/apps/admin/tsconfig.tsbuildinfo` | = | generated | **대체** | `ba2182d72b6a` | 빌드 생성물 |
| 138 | conflicts | `final_project_cs/frontend/apps/web/tests/live/stub-server.mjs` | = | code | **대체** | `c7d440c4136a` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 139 | conflicts | `final_project_cs/frontend/apps/web/tsconfig.tsbuildinfo` | = | generated | **대체** | `4d630c024671` | 빌드 생성물 |
| 140 | conflicts | `final_project_cs/scripts/run_sweepers.py` | = | code | **대체** | `4664f34c7f5a` | 2026-10-14 일일점검 「until 없음」은 pin의 후속 결정(daily_check 03:00 시작·03:30 마감·08:00 정지, watch/daily_check.py·refresh_from)으로 대체 (pin run_sweepers 에 refresh_from 있음) |
| 141 | conflicts | `final_project_cs/tests/unit/infrastructure/test_llm_failover.py` | = | code | **대체** | `1722e01948ea` | 10-15 overflow(부하 동원) 시험 10개. 원본 작업트리의 overflow 구현은 F3 판으로 바뀌어 inflight 키 형식(url\|model)·counter 가 달라 이 시험은 그대로 맞지 않음. F3 시험(test_llm_overflow_f3·f3_acceptance)이 대체. 단 overflow 기능 자체는 팀 pin 미반영(원본 작업트리 미커밋) — 그 통합 때 행동 범위 대조 권장 |
| 142 | conflicts | `final_project_cs/var/ops/heartbeat/daily_feedback.alert.json` | = | runtime | **대체** | `770ff1543638` | 런타임 heartbeat/log. 원본 작업트리에 현재 파일 있음. 코드 통합 대상 아님 |
| 143 | conflicts | `final_project_cs/var/ops/heartbeat/daily_feedback.json` | = | runtime | **대체** | `ea6ef6a2dc8d` | 런타임 heartbeat/log. 원본 작업트리에 현재 파일 있음. 코드 통합 대상 아님 |
| 144 | conflicts | `final_project_cs/var/ops/heartbeat/outbox.alert.json` | = | runtime | **대체** | `ccc2a93ce22d` | 런타임 heartbeat/log. 원본 작업트리에 현재 파일 있음. 코드 통합 대상 아님 |
| 145 | conflicts | `final_project_cs/var/ops/heartbeat/outbox.json` | = | runtime | **대체** | `52e461a377d7` | 런타임 heartbeat/log. 원본 작업트리에 현재 파일 있음. 코드 통합 대상 아님 |
| 146 | conflicts | `final_project_cs/var/ops/heartbeat/sweepers.alert.json` | = | runtime | **대체** | `6aa0b12ec505` | 런타임 heartbeat/log. 원본 작업트리에 현재 파일 있음. 코드 통합 대상 아님 |
| 147 | conflicts | `final_project_cs/var/ops/heartbeat/sweepers.json` | = | runtime | **대체** | `ca4a4e721004` | 런타임 heartbeat/log. 원본 작업트리에 현재 파일 있음. 코드 통합 대상 아님 |
| 148 | conflicts | `final_project_cs/var/ops/logs/outbox-20261013.log` | = | runtime | **대체** | `c5a6d847d817` | 런타임 heartbeat/log. 원본 작업트리에 현재 파일 있음. 코드 통합 대상 아님 |
| 149 | conflicts | `final_project_cs/var/ops/logs/sweepers-20261013.log` | = | runtime | **대체** | `9696973aab0c` | 런타임 heartbeat/log. 원본 작업트리에 현재 파일 있음. 코드 통합 대상 아님 |
| 150 | conflicts | `final_project_cs/wiki/decisions/index.md` | = | doc | **대체** | `046190af0cd4` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 151 | conflicts | `final_project_cs/wiki/external/watch-simulation.md` | = | doc | **대체** | `7946c8bb9025` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 152 | conflicts | `final_project_cs/wiki/teams/dining.md` | = | doc | **대체** | `7b687f74d718` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 153 | conflicts | `final_project_cs/wiki/teams/index.md` | = | doc | **대체** | `37b83894f754` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 154 | conflicts | `final_project_cs/wiki/teams/액티비티 LLM 연동 계획서.md` | = | doc | **대체** | `6c5dbba802be` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 155 | conflicts | `program/plan/triPilot_구현계획서_v12.md` | = | doc | **대체** | `e0f1804ef13f` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 156 | conflicts | `program/research/activity_recommendation_20261009/research.md` | = | doc | **대체** | `398212d6a04e` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 157 | conflicts | `program/scripts/activity_recommendation_bench/README.md` | = | doc | **대체** | `fb89e8be9d71` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 158 | conflicts | `program/scripts/plan_qa_bench/results/mx_report.md` | = | doc | **대체** | `5ec996f580a9` | 비어 있지 않은 모든 줄이 pin·HEAD·원본 작업트리 중 하나에 있음(중간/이전 판) |
| 159 | conflicts | `final_project_cs/app/domains/travel_ops/components/conversation/item_pointer.py` | = | code | **포함** | `2638e2e0e7af` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/item_pointer.py); pin 끝은 이후 판 |
| 160 | conflicts | `final_project_cs/app/domains/travel_ops/components/conversation/trip_replies.py` | = | code | **포함** | `e1f4f342f338` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/conversation/trip_replies.py); pin 끝은 이후 판 |
| 161 | conflicts | `final_project_cs/app/domains/travel_ops/components/places/catalog_hours.py` | = | code | **포함** | `ec93da1ff25a` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/components/places/catalog_hours.py); pin 끝은 이후 판 |
| 162 | conflicts | `final_project_cs/app/domains/travel_ops/instances/mobility/team.py` | = | code | **포함** | `342c059a3253` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/app/domains/travel_ops/instances/mobility/team.py); pin 끝은 이후 판 |
| 163 | conflicts | `final_project_cs/app/infrastructure/rag/retriever.py` | = | code | **포함** | `98eac78705ac` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 164 | conflicts | `final_project_cs/frontend/apps/web/src/lib/live/stream.test.ts` | = | code | **포함** | `3284f0d692c8` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/frontend/apps/web/src/lib/live/stream.test.ts); pin 끝은 이후 판 |
| 165 | conflicts | `final_project_cs/tests/architecture/test_travel_ops_cells.py` | = | code | **포함** | `1b0ba16e10db` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 166 | conflicts | `final_project_cs/tests/e2e/test_web_conversation_resume.py` | = | code | **포함** | `9aad344b4b7e` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 167 | conflicts | `final_project_cs/tests/integration/rag/test_rag_integration.py` | = | code | **포함** | `5912bebb4d50` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 168 | conflicts | `final_project_cs/tests/test-suites.json` | = | code | **포함** | `8afabddbf532` | 백업 모든 줄이 pin 판에 있음 |
| 169 | conflicts | `final_project_cs/tests/unit/travel/test_read_requests.py` | = | code | **포함** | `e8f4a0ca0f10` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/tests/unit/travel/test_read_requests.py); pin 끝은 이후 판 |
| 170 | conflicts | `final_project_cs/tests/unit/travel/test_schedule_query.py` | = | code | **포함** | `649db002f248` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/tests/unit/travel/test_schedule_query.py); pin 끝은 이후 판 |
| 171 | conflicts | `final_project_cs/wiki/data/migrations.md` | = | doc | **포함** | `52457075b7d1` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 172 | conflicts | `final_project_cs/wiki/operations/arm-develop-cd.md` | = | doc | **포함** | `76a474f35225` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/wiki/operations/arm-develop-cd.md); pin 끝은 이후 판 |
| 173 | conflicts | `final_project_cs/wiki/operations/call-budget.md` | = | doc | **포함** | `12b16dcd198f` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/wiki/operations/call-budget.md); pin 끝은 이후 판 |
| 174 | conflicts | `final_project_cs/wiki/quality/itinerary-crud-e2-evaluation.md` | = | doc | **포함** | `84b9072af65c` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 175 | conflicts | `final_project_cs/wiki/quality/model-version-reports.md` | = | doc | **포함** | `e883806dee9d` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 176 | conflicts | `final_project_cs/wiki/quality/selection-grounded-answer-evaluation.md` | = | doc | **포함** | `105afeb7f24c` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 177 | conflicts | `final_project_cs/wiki/quality/slm-model-evaluation.md` | = | doc | **포함** | `dd22b620b71f` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 178 | conflicts | `final_project_cs/wiki/quality/test-map.md` | = | doc | **포함** | `dad9785ac5a3` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/wiki/quality/test-map.md); pin 끝은 이후 판 |
| 179 | conflicts | `final_project_cs/wiki/records/reports/2026-10-06_서비스_평가_베이스라인과_개선_전후.md` | = | doc | **포함** | `a11628c97fd7` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 180 | conflicts | `final_project_cs/wiki/records/reports/2026-10-08_131541_winnow_training_completion.md` | = | doc | **포함** | `568129790440` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 181 | conflicts | `final_project_cs/wiki/records/reports/2026-10-09_0810_gpu-saluki-cosine-completion-finch-refill.md` | = | doc | **포함** | `e18f318c4b90` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 182 | conflicts | `final_project_cs/wiki/records/reports/2026-10-09_1208_saluki-reviewed-set-baseline.md` | = | doc | **포함** | `5daabfe68f98` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 183 | conflicts | `final_project_cs/wiki/records/reports/2026-10-09_1400_six-hour-gpu-arm-report.md` | = | doc | **포함** | `fb94d7512e0c` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 184 | conflicts | `final_project_cs/wiki/records/reports/2026-10-09_140358_gpu-finch-seed2-completion-valen-final-refill.md` | = | doc | **포함** | `abe9d05b3c08` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 185 | conflicts | `final_project_cs/wiki/records/reports/2026-10-09_200918_gpu-seed2-results-cosine-refill-local-feeder.md` | = | doc | **포함** | `11e13187c0ce` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 186 | conflicts | `final_project_cs/wiki/records/reports/2026-10-12_e2-crud-pilot-and-real-dialogue.md` | = | doc | **포함** | `25aabb247d02` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 187 | conflicts | `final_project_cs/wiki/records/reports/2026-10-12_e2-gold-review-and-a4000-registration.md` | = | doc | **포함** | `3569f331cf1d` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 188 | conflicts | `final_project_cs/wiki/teams/db_column.md` | = | doc | **포함** | `01b26ad4a4dc` | 같은 bytes 가 pin 이력에 커밋됨(final_project_cs/wiki/teams/db_column.md); pin 끝은 이후 판 |
| 189 | conflicts | `final_project_cs/wiki/teams/team-boundary.md` | = | doc | **포함** | `bfd7e36f67c2` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 190 | conflicts | `program/research/baseline_2026-10-10/checks/project-checks-v2.json` | = | doc | **포함** | `c7863924b1ec` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 191 | conflicts | `program/research/baseline_2026-10-10/checks/project-checks.json` | = | doc | **포함** | `cae920b09e63` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 192 | conflicts | `program/research/daily_rag_slm/2026-10-08.json` | = | doc | **포함** | `7ff4357f1129` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 193 | conflicts | `program/research/daily_rag_slm/2026-10-08.md` | = | doc | **포함** | `de17d18d29c3` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 194 | conflicts | `program/research/daily_rag_slm/2026-10-09.json` | = | doc | **포함** | `655a2b944711` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 195 | conflicts | `program/research/daily_rag_slm/gpu_backlog_2026-10-08.json` | = | doc | **포함** | `bba0a36addb1` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 196 | conflicts | `program/research/daily_rag_slm/gpu_backlog_2026-10-09.json` | = | doc | **포함** | `327fdc7ca15b` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 197 | conflicts | `program/research/daily_rag_slm/saluki_finetune_2026-10-09.json` | = | doc | **포함** | `bfa8362bcecd` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 198 | conflicts | `program/research/daily_rag_slm/saluki_finetune_plan_2026-10-09.md` | = | doc | **포함** | `2ba24613d207` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 199 | conflicts | `program/research/daily_rag_slm/selection_answer_plan_2026-10-09_v2.md` | = | doc | **포함** | `da9cb8f87b9b` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 200 | conflicts | `program/research/daily_rag_slm/selection_answer_review_2026-10-09_v2.json` | = | doc | **포함** | `2828c2774c42` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 201 | conflicts | `program/scripts/plan_qa_bench/build_e_mixed_view.py` | = | code | **포함** | `7a279052763a` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 202 | conflicts | `program/scripts/plan_qa_bench/build_hard_set.py` | = | code | **포함** | `f31e05b2ae4c` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 203 | conflicts | `program/scripts/plan_qa_bench/build_mix10.py` | = | code | **포함** | `870c73772cda` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 204 | conflicts | `program/scripts/plan_qa_bench/build_mix10_inputs.py` | = | code | **포함** | `c91ac386c82a` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 205 | conflicts | `program/scripts/plan_qa_bench/build_mix11.py` | = | code | **포함** | `c1e26e425f95` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 206 | conflicts | `program/scripts/plan_qa_bench/build_mix11_inputs.py` | = | code | **포함** | `2e8fb761ee33` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 207 | conflicts | `program/scripts/plan_qa_bench/build_mix12.py` | = | code | **포함** | `1eaa65d089da` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 208 | conflicts | `program/scripts/plan_qa_bench/build_mix6.py` | = | code | **포함** | `0d02be46a8a1` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 209 | conflicts | `program/scripts/plan_qa_bench/build_mix7.py` | = | code | **포함** | `ffe603c41d42` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 210 | conflicts | `program/scripts/plan_qa_bench/build_mix8.py` | = | code | **포함** | `605df3ac6d52` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 211 | conflicts | `program/scripts/plan_qa_bench/build_mix8_inputs.py` | = | code | **포함** | `e187afca9bcd` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 212 | conflicts | `program/scripts/plan_qa_bench/build_mix9.py` | = | code | **포함** | `01f45b9cb8c9` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 213 | conflicts | `program/scripts/plan_qa_bench/build_mix9_inputs.py` | = | code | **포함** | `8be23e0a0ba9` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 214 | conflicts | `program/scripts/plan_qa_bench/build_mixed_testset.py` | = | code | **포함** | `18f7f110e941` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 215 | conflicts | `program/scripts/plan_qa_bench/build_verify_inputs.py` | = | code | **포함** | `0c30807492d2` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 216 | conflicts | `program/scripts/plan_qa_bench/chain_report.py` | = | code | **포함** | `6a9da2d5daa1` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 217 | conflicts | `program/scripts/plan_qa_bench/claude_batch_collect.py` | = | code | **포함** | `6daa4bd3239c` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 218 | conflicts | `program/scripts/plan_qa_bench/claude_batch_tasks.py` | = | code | **포함** | `7f7f9084fdeb` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 219 | conflicts | `program/scripts/plan_qa_bench/claude_solve.py` | = | code | **포함** | `0cedc6c44054` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 220 | conflicts | `program/scripts/plan_qa_bench/codex_solve.py` | = | code | **포함** | `8479d929f420` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 221 | conflicts | `program/scripts/plan_qa_bench/cpu_eval_summary.py` | = | code | **포함** | `35ba21105176` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 222 | conflicts | `program/scripts/plan_qa_bench/cpu_q4_vs_q8.py` | = | code | **포함** | `d72a84465d4c` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 223 | conflicts | `program/scripts/plan_qa_bench/d_test_ollama.py` | = | code | **포함** | `71b9d6e86a4d` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 224 | conflicts | `program/scripts/plan_qa_bench/empty_probe_build.py` | = | code | **포함** | `dc6061ab055d` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 225 | conflicts | `program/scripts/plan_qa_bench/eval_e1_d1.py` | = | code | **포함** | `b40b3767d530` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 226 | conflicts | `program/scripts/plan_qa_bench/eval_final.py` | = | code | **포함** | `2e91a7b1917d` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 227 | conflicts | `program/scripts/plan_qa_bench/eval_ft_pipeline.py` | = | code | **포함** | `5e5dbe39927b` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 228 | conflicts | `program/scripts/plan_qa_bench/eval_night.py` | = | code | **포함** | `a029d2cd5aa5` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 229 | conflicts | `program/scripts/plan_qa_bench/eval_pipeline.py` | = | code | **포함** | `c3da9a119617` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 230 | conflicts | `program/scripts/plan_qa_bench/eval_retrieval.py` | = | code | **포함** | `734babd1e148` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 231 | conflicts | `program/scripts/plan_qa_bench/eval_router.py` | = | code | **포함** | `23602a8f1fc3` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 232 | conflicts | `program/scripts/plan_qa_bench/eval_trio_types.py` | = | code | **포함** | `6e2c8bc4f060` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 233 | conflicts | `program/scripts/plan_qa_bench/hard_report.py` | = | code | **포함** | `6914387dfed7` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 234 | conflicts | `program/scripts/plan_qa_bench/mixed_report.py` | = | code | **포함** | `507ea29a34f4` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 235 | conflicts | `program/scripts/plan_qa_bench/opencode_solve.py` | = | code | **포함** | `34feb56d3ca4` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 236 | conflicts | `program/scripts/plan_qa_bench/record_backlog_mx_completion.py` | = | code | **포함** | `1b26039a55f6` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 237 | conflicts | `program/scripts/plan_qa_bench/results/bcde_results_2026-10-08_115224.json` | = | code | **포함** | `dca0e0c02c22` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 238 | conflicts | `program/scripts/plan_qa_bench/results/bcde_results_2026-10-08_115323.json` | = | code | **포함** | `cd44b409d02c` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 239 | conflicts | `program/scripts/plan_qa_bench/results/comparison_abcde_20261009_111158/snapshot.json` | = | code | **포함** | `975c8685ab21` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 240 | conflicts | `program/scripts/plan_qa_bench/results/comparison_abcde_20261009_111341/snapshot.json` | = | code | **포함** | `6297afc15caa` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 241 | conflicts | `program/scripts/plan_qa_bench/results/comparison_abcde_20261009_111621/snapshot.json` | = | code | **포함** | `9461bc00c2ea` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 242 | conflicts | `program/scripts/plan_qa_bench/results/e_maturity_audit_20261009.json` | = | code | **포함** | `1c44257e5f26` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 243 | conflicts | `program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_finch_completed_hb0754_20261009/archive_verification.json` | = | code | **포함** | `75158ee87d00` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 244 | conflicts | `program/scripts/plan_qa_bench/results/gpu_backlog_20261008/report_verification_hb0810_20261009.json` | = | code | **포함** | `450a6d7ef8cb` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 245 | conflicts | `program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/basic_completion_verified_1328.json` | = | code | **포함** | `78b5e4024355` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 246 | conflicts | `program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/training_archive.json` | = | code | **포함** | `e85a60b8eea4` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 247 | conflicts | `program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/training_archive_verified.json` | = | code | **포함** | `2f9ea7f74bfc` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 248 | conflicts | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1355/adapter_transfer.json` | = | code | **포함** | `5a17f20fdd2b` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 249 | conflicts | `program/scripts/plan_qa_bench/results/gpu_management_20261009_1355/record_results.py` | = | code | **포함** | `759655492326` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 250 | conflicts | `program/scripts/plan_qa_bench/results/heartbeat_20261009_0754/e_maturity_audit.json` | = | code | **포함** | `cde6027f3f1f` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 251 | conflicts | `program/scripts/plan_qa_bench/results/heartbeat_20261010_0200/human_review_check.json` | = | code | **포함** | `6687571a4d9f` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 252 | conflicts | `program/scripts/plan_qa_bench/results/selection_answer_work_verification_20261009_v1.json` | = | code | **포함** | `bb31986062b7` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 253 | conflicts | `program/scripts/plan_qa_bench/results/selection_answer_work_verification_20261009_v2.json` | = | code | **포함** | `f42d38862c8a` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 254 | conflicts | `program/scripts/plan_qa_bench/seed_scores.py` | = | code | **포함** | `0427df7a2f00` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 255 | conflicts | `program/scripts/plan_qa_bench/server/queues/completed_adapter_feeder.py` | = | code | **포함** | `3e3d770cc0a1` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 256 | conflicts | `program/scripts/plan_qa_bench/small_ensemble_769.py` | = | code | **포함** | `27f85b65e10f` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 257 | conflicts | `program/scripts/plan_qa_bench/verify_veto_report.py` | = | code | **포함** | `56cccdb54e53` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 258 | conflicts | `program/scripts/rag_gate/rag_metrics_live.py` | = | code | **포함** | `0ab3457873b0` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 259 | conflicts | `program/산출물양식/w5/멀티에이전트_테스트보고서/_재료/코덱스_의논.log` | = | doc | **포함** | `1b4c0d8dd6bb` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 260 | conflicts | `wiki/delivery/release-gate.md` | = | doc | **포함** | `d12c8d7cb27f` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 261 | conflicts | `wiki/product/positioning.md` | = | doc | **포함** | `aedf2af46c9f` | pin 끝 blob 과 동일(LF 정규화 포함) |
| 262 | conflicts | `wiki/product/scope.md` | = | doc | **포함** | `efc730e30dfa` | pin 끝 blob 과 동일(LF 정규화 포함) |
