---
type: report
title: 구구루트 Telegram 총괄 세션 5fbd35ab 위키화 — 결정·결과·미완료·삭제 영향 (2026-11-03)
description: 10-27~11-02 Telegram 총괄 세션(2,056행, 압축 3회, 위임 하위 153개)을 state.db 읽기 전용으로 다시 읽어 사용자 지시·결정·작업 흐름별 결과를 기존 wiki 기록과 대조했다. wiki에 없던 인사동 대안 원인 분석과 일정 설명 원인 조사를 이 문서에 옮기고, scratch에만 있던 설명 작성기 후보를 backups에 보존했다. 세션은 지우지 않았다. 삭제 시 영향 범위와 남은 공백을 적는다
status: done
domain: ops
impl_scope: 기록만. 제품 코드·설정·서비스·원격·세션 DB 변경 0. 세션 삭제 0. 새 파일은 이 보고서·인계 1개와 Hermes profile backups 2곳. 기존 wiki는 목차·로그 줄 추가만
---

# 구구루트 Telegram 총괄 세션 `20261027_205452_5fbd35ab` 위키화 (2026-11-03)

- 수행: 후속 세션 `20261103_032201_d047d36a`의 하위 세션(이 세션을 지우기 전 위키화). 삭제는 사용자 결정이며 이 작업은 하지 않았다.
- 방법: guguroute `state.db`를 `mode=ro`로만 열었다. 비밀은 키 이름·길이·엔트로피만 출력했다. 시각은 DB `timestamp`(KST).
- 「오픈위키」: 이 저장소 wiki 표준의 기반인 LangChain OpenWiki를 가리킨다([작성 표준](../../governance/index.md) 「왜 이렇게 하는가」). 외부 위키가 아니라 이 `wiki/` 규칙(근거 등급, 보고서+결론 한 줄, 인계 목차)을 따랐다.
- 선행 감사: [10-28 Hi·현재 세션 종료 가능성 4차](2026-10-28_hi-and-current-session-close-readiness-audit.md)는 이 세션을 10-28 21:24까지만 봤다(사람 입력+마지막 보고 4건). 이 문서는 그 뒤를 포함해 전 기간을 다룬다.

## 1. 결론

- `[실측]` 세션 자체의 사용자 지시 134건과 답변 366건은 전문을 읽었다. 결정·결과는 대부분 이미 wiki 보고서·인계에 있다. 없던 것 3가지를 이번에 옮겼다: 인사동 대안 원인(§5-1), 일정 설명 원인 조사(§5-2), 설명 작성기 후보 보존(§5-3).
- `[실측]` 세션은 11-03 03:22 `session_reset`으로 이미 닫혔다. 실행 중인 admission 0(369건 모두 terminal), worker execution 0, 하위 153개 모두 `agent_close`.
- **삭제는 아직 권하지 않는다.** 이유: (1) 하위 13개 세션 출력에 비밀 후보 값이 있다(§7). 삭제는 값을 무효화하지 않는다. (2) 삭제하면 위임 하위 153개(19,633행)가 같이 지워지고, 지금 쓰고 있는 후속 세션은 부모를 잃는다(§8). (3) 미완료 작업 담당이 아직 정해지지 않은 것이 있다(§6). wiki 공백만 놓고 보면 이 문서로 닫혔다.
- `[실측, 2차 §11]` 설치 소스로 삭제 범위를 다시 계산했다(154개 세션·21,658행 + spillover 64개·request_dump 9개). 이 전부를 원문 그대로 비공개 보존본(guguroute `backups/session-5fbd35ab-export-20261103/`)으로 내보내 행 21,658/21,658·해시 220/220을 확인했다. **원문 보존 면에서는 삭제 준비가 됐다.** 비밀 교체와 삭제 실행은 여전히 사용자 결정이다.

## 2. 읽은 범위

| 대상 | 행/개수 | 읽은 방식 | 범위 |
|---|---|---|---|
| 사람 입력(OOB·답장 포함) | 134 고유 | 전문 | 134/134 = 100% |
| 압축 요약 | 3개(10-28 19:00 · 10-29 21:32 · 10-31 02:38) | 전문 | 3/3 = 100% |
| 답변 본문 | 366 고유 | 전문 | 366/366 = 100% |
| 도구 호출 | 600 고유(이름+인자) | 목록 생성, 대상 경로만 정독 | 전문 정독 아님 |
| 도구 출력 | 718행(약 2.2M자) | 비밀 검사로만 순회 | 정독 0 |
| 위임 완료·배경 알림 | 277행 | 답변이 요약한 내용과 대조 | 정독 아님 |
| 위임 하위 세션 | 153개, 19,633행, 약 32M자 | 마지막 보고의 wiki 경로 존재 대조 153/153 + 비밀 검사 + 마지막 보고 6개 정독 + scratch 보고서 3개를 도구 인자에서 복구 | 내용 정독은 일부 |

- 행 구성: 전체 2,056 = 활성 247 + 꼬리 원본 121 + 압축 1,688. 세 요약이 말한 압축 수(376+797+509=1,682)와 DB 압축 1,688의 차 6은 session_meta 1 + 머리 보호행으로 본다 `[추정]`.
- 하위 마지막 보고의 wiki 경로 대조: 경로 있음·전부 존재 83, 일부만 로컬 존재 9, 로컬 없음 1, 경로 언급 없음 60. 로컬에 없던 9개 이름은 `final_workspace/scratch/*/repo`·`.tmp/clones/hold3-*`(팀 role-manager 사본)에서 찾았다. 즉 원격 브랜치에 커밋된 문서다. `2026-10-29_라우팅전수검사_미결재집계_B10수정.md`·`2026-10-29_explain-writer-llm.md`(보고서)는 찾지 못했다 — 같은 내용의 인계 [B10](../../handoff/2026-10-29_routing-b10-independent-review.md)·[설명 작성기](../../handoff/2026-10-29_explain-writer-llm.md)는 있다.

## 3. 사용자 지시와 결정 (시간순, 요지)

| 시각 | 지시·결정 | 결과·기록 |
|---|---|---|
| 10-27 20:54 | 파이널스페이스가 왜 남았나, 무엇을 남기고 지웠나 | 이미 삭제됨. [이관·삭제 보고](2026-10-26_finalspace-migration-and-removal.md) |
| 10-27 21:14 | 백업 폴더를 분석해 쓸 것은 쓰고 푸시할 것은 푸시 | 262개 분류, 2건(`codex_percall` UUID, C1 알림 시험) 팀·개인 role-manager 푸시(`ffb5fb1b5`) |
| 10-27 21:39 | 프로젝트 용량이 크다, 불필요한 것 삭제 | 캐시 1.88GB·.tmp 1.60GB+0.99GB 삭제. [정리 보고](2026-10-27_workspace-cache-cleanup.md). 보존 지시가 있던 `manager-snapshot` 사본 1개를 확인 없이 지웠다(복원 기준은 남음) |
| 10-27 22:29 | 비민감 경량 작업은 OpenCode CLI 무료 모델, 그중 최고 성능 | `opencode/deepseek-v4.1-flash-free` 설정. [선정 기록](2026-10-28_opencode-free-model-selection.md). 「10월판」 여부 미확인 |
| 10-27 22:35 | ① 라우팅 전수검사·개발 계속 ② 계획 작성·서빙 속도 개선(EKS 구조 확인) ③ TeamFlow 버그 개선 | §4 |
| 10-27 22:37 | `C:\c` 삭제 또는 정리 | 고유 46개를 `.backup/2026-10-27_C-c-preserved`로(SHA 46/46) 옮긴 뒤 삭제. 원인: 네이티브 프로그램에 `/c/...` 경로 전달 |
| 10-28 00:04 | 속도 시험은 직접 사이트에 들어가서 | EKS 80.7초·x600 59.69초(각 1회, 서버가 달라 비교 불가). [x600 예시](2026-10-28_x600-browser-latency-example.md) |
| 10-28 00:12~13 | 첫 계획 대기 안내를 1분→2분으로 교체(서버 제한은 그대로) | x600 반영 확인. [인계](../../handoff/2026-10-28_plan-wait-estimate-two-minutes.md) |
| 10-28 00:16 | 서빙 속도는 Claude·Codex가 논의해 개선 | 빈칸만 계산(합성 9.55→4.42초)·SSE 생존 신호 role-manager 반영. 운영 개선 폭은 미입증 |
| 10-28 03:23 | final_workspace 구구루트 작업은 「라우팅 에이전트 구현」 세션(36cd5c)에 이관, 총괄은 하지 말 것 | [이관 인계](../../handoff/2026-10-28_routing-session-transfer.md). 당시 직접 전달 실패 → 10-31부터 gateway 경로로 전달·수락 |
| 10-28 13:35 | 실패가 남으면 해결이라 하지 말라, 다 해결 | EKS 후보 실패 3건 원인 수정(13,376 통과·0 실패) |
| 10-28 14:12 | C++ 상태 유지 서버로 바꿔야 하나 | 답: 근거 부족, 모델 서빙만 동일 조건 비교 후 결정(사용자 결정 아님) |
| 10-28 21:10 | EKS 문제 해결·푸시·실측, 라우팅 미결 마무리, TeamFlow 미완 0, Hi·이 세션 닫을 수 있게 wiki 보강, Claude/Codex/OpenCode 적절히 | §4. Hi는 [4차 감사](2026-10-28_hi-and-current-session-close-readiness-audit.md) |
| 10-28 22:18 | 문제의 폴더는 x600 **F:** 드라이브 | 11-02 처리 완료(qemu 1개 보존). [인계](../../handoff/2026-11-02_x600-f-root-guguroute-cleanup.md) |
| 10-29 11:52~15:39 | 일정·장소 설명과 추천 이유에 제대로 답해야 한다. 유료 모델 API 호출(정확한 결과만)과 사용자 대화 서빙(자연스러운 설명)을 구분, 답 못 하면 이유를 설명 | 설명 작성기 후보, 운영 미반영. §5-2·§5-3 |
| 10-29 13:29 | 앞으로 TeamFlow에 넣는 작업은 전부 매니저 브랜치 담당. 프로젝트는 종료 | 루트 AGENTS.md TeamFlow 절에 반영됨(`3rd_team_4_be`) |
| 10-29 15:02~15:14 | NPU 단독 속도 측정, NPU 클럭 표시 | 단독 경로 실측(§4). 연산 클럭은 `nvidia-smi` N/A, 9400MHz는 메모리 클럭 |
| 10-29 15:09 | 로컬 LLM에 비밀번호를 줘서 잠금 해제 | 거절(인증정보 전달·잠금 우회 안 함) |
| 10-29 16:00 | 용량이 애초에 안 커지게, C: 여유 400GB대 | [디스크 가드](2026-10-29_disk-growth-guard.md) + 정리 9회. 400GB 미달 |
| 10-29 17:55 | 이 세션은 오케스트레이션만, 작업은 각 세션에 배정 | 이후 위임·기존 세션 전달 위주 |
| 10-29 21:11 | Claude 사용량 제한은 배분 잘못 | 인정. 비민감 작업은 OpenCode, Claude는 복잡한 독립 검토로 |
| 10-30 00:11 | 세션 감시를 제대로, Antigravity Gemini 4도 활용 | 30분 감시 cron `a19614eada92` 등록(자동 재시작 아님). Gemini 4는 개인 한도 초과, 3.8 Flash는 응답 |
| 10-30 13:43~15:03 | Hermes 폴더를 150GB 안으로 — 적합한지 먼저, Claude와 논의 | 결론: 150GB는 잠정 목표·경고선, 강제 상한은 피크 측정 뒤. 미적용 |
| 10-30 15:31 | GHelper를 본인 GitHub 포크로 | `roroblack/g-helper` 포크, 브랜치 `h7407ba-arm64-v0.16` 푸시. 업로드 후 빌드·CI 0 |
| 10-30 19:41 | 인사동 대안·이유를 채팅에서 못 찾는다 | 원인 분석만, 수정 0, 담당 전달 안 됨. §5-1 |
| 10-30 20:44 | SGLang은 못 쓰나 | 답: GPU 서빙 대안 후보(WSL), NVIDIA NPU 해결책은 아님(문서의 NPU 지원은 Ascend) — 미시험 |
| 10-31 01:57~02:36 | 증류 영상 참고, 실제 질의로 현 모델 평가, 강화학습 없이 대형 교사 SFT, 최신 논문(Codex·Claude 각자 검색) | 계획·검사기 준비, 학습 0, 골든 0/47 미측정. [SFT 인계](../../handoff/2026-10-31_sft-distill-training-plan.md) · [골든](../../handoff/2026-10-31_guguroute-model-golden-eval.md) |
| 10-31 04:08 | 용량을 만드는 각 세션이 직접 정리하게 | 12개 중 11개 전달, 14.70GB. [인계](../../handoff/2026-10-31_session-cleanup-relay-supervision.md) |
| 10-31 19:49 | `C:\_proj` 루트의 38개 작업 폴더를 담당 세션이 마무리·삭제, 하나도 남기지 말 것 | 11-02 38/38 삭제. [13개 최종](2026-11-02_proj-root-13-final-retirement.md) · [삭제 후 인계](../../handoff/2026-11-02_proj-root38-post-deletion-handoff.md) |
| 11-02 18:58 | x600 F: 루트 구구루트 폴더 4개는 쓸 정보만 빼고 삭제 | 위 x600 인계 |
| 11-02 19:35 | 세션마다 컨텍스트 50%에서 자동 압축 | 세 프로필 `threshold 0.5` 확인. 512K 미만 로컬 Qwen은 코드상 75% 고정 — 우회(`threshold_tokens`)는 사용자 결정 |
| 11-02 22:22 | 새 세션을 열어 인수인계·문서화·삭제 | 13개 폴더 처리(`bbe8c7`), 이어 HOLD 3건 36cd5c 배정(`7a5e40`) |

- 미응답으로 끝난 질문: 10-27 20:56 「디스코드 셋팅은 왜 안 되냐」 — 총괄은 대상(고객 알림·TeamFlow 알림·Hermes 연결)을 되물었고 답이 없었다. **미해결.**

## 4. 작업 흐름별 마지막 확인 상태

| 흐름 | 마지막 확인 상태 | 기록 |
|---|---|---|
| EKS 배포·속도 | PR #109 main `57f3d2f`(CI 3/3·앱 4/4), 전후 3회 중앙값 57.25→60.68초로 개선 미입증. 10-28 13회 45.6→32.1초도 표본 부족. `checking→review` 56.85%. 운영 DB에 측정용 접수 26건(10-28)·6건(10-29)을 남겼다고 보고됐고, 그 뒤 처리 기록은 찾지 못했다 | [scalar](2026-10-29_eks-scalar-release-and-measurement.md) · [병목](2026-10-29_eks-serving-bottleneck-partition.md) |
| EKS HOLD 3건(11-02 배정) | ① 잔여18 판정 18/18(기대값 정정 14·제품 결함 4), PR110 draft 유지 ② reader fatal #6/#7 **BLOCKED**(허용 경로 0/3) ③ 513ab4cc 통합 적합, 1ab3f0d88 수정 필요 | [HOLD1](2026-11-02_hold3-eks-precision-remaining18.md) · [HOLD2](2026-11-02_hold3-reader-fatal-6-7-observation.md) · [HOLD3](2026-11-02_hold3-513ab4cc-1ab3f0d88-integration-fit.md) |
| 라우팅 전수검사 | 70건 중 미결 28(10-29). A11·B10 등 후보는 보안 관문 124/125 XML HOLD로 미통합 | [B10](../../handoff/2026-10-29_routing-b10-independent-review.md) · [A11](../../handoff/2026-10-29_routing-a11-reopen-kind-question-ready.md) |
| TeamFlow | 695건 중 미완료 109(10-30·11-02 cron). 10-28 증거 확인 12건 완료 처리(117→105), 10-29 ST4F-504·714 종결. 새 이슈 등록으로 다시 109 | [10-30 인계](../../handoff/2026-10-30_teamflow-guguroute-morning-recovery.md) |
| 인증·개인정보(ST4F-719 등) | 웹 1,463/1,463·PG/Edge 64/64, 필수 2/3 보안 HOLD | [인계](../../handoff/2026-10-29_st4f719-auth-generation-independent-review.md) |
| 일정 설명·유료 모델 서빙 | 후보 `4bc2d9080`+미커밋 r8, 운영 미반영, 유료 서빙 실검증 미완 | [인계](../../handoff/2026-10-29_explain-writer-serving-resume.md) · §5-3 |
| 인사동 대안 | 원인 7개(합성 재현), 수정 0, 담당 미전달 | §5-1 |
| SFT 증류 | 계획·검사기 v0.3, 학습 0, readiness NOT_READY | [인계](../../handoff/2026-10-31_sft-template-tokenizer-parity.md) |
| NPU(`C:/Users/kcxsz/frog-npu-dev`) | 단독 실행 FP32 기준 17/17 일치, 생성 약 0.06→0.15~0.28 tok/s(재적재 병목), GPU Q4 기준 정확도 실패. 11-02 기준 새 실측 0 | [10-30 인계](../../handoff/2026-10-30_npu-argen4-repro-async-unload.md) |
| C: 용량 | 지금 여유 243,312,676,864 B(11-03 05시 df), 400GB까지 약 156.7GB 부족 | [round9](2026-10-31_c-drive-400gb-cleanup-round9.md) |
| 서빙 빈 폴더 | 프로세스 3개가 빈 소스 폴더를 가리킴(8042는 LAN 노출), 36cd5c 수락 | [인계](../../handoff/2026-10-31_empty-serving-folders-routing-relay.md) |

## 5. wiki에 없던 내용 (이번에 옮김)

### 5-1. 인사동 대안 + 추천 이유 실패 원인 `[실측: 합성 재현, 실제 사례 아님]`

- 출처: 하위 `20261030_194120_878e52`·`20261030_195408_a81692`가 scratch에 쓴 `REPORT_KO.md`·`HANDOFF_TO_ROUTING_SESSION.md`. **scratch 파일은 이미 지워졌고** 원문은 이 세션 DB의 도구 인자에만 남아 있었다.
- 기준: 팀·개인 role-manager `fab3da50a`. 이 경로 파일은 EKS main `57f3d2f`와 같은 blob(코드 근거, 실서버 미확인). 실모델·유료·DB 호출 0.
- 합성 결과: 후보가 나온 3건 중 답에 이유 0/3, 일정에 인사동이 있는 5건 중 후보 도달 3/5, 일정에 없는 4건 중 자료 근거 후보 0/4, 후속 「왜 추천했어?」 0/2.
- 결함(확실도 순):
  1. 이유가 답에 안 나온다 — `conversation_work._propose_alternatives`·`trip_desk.propose_alternatives`가 이름만 낸다. 선택지에도 `reason` 칸이 없다.
  2. 이유 요청이 Team까지 안 간다 — propose와 함께 낸 reads는 `ignored_for_action`으로 버려지고, general_requests의 이유 문장은 업무 경로에서 기록 없이 사라진다.
  3. `itinerary_changes.plan_fresh_alternate`가 1위 후보 `pick_reason`을 저장하지 않는다.
  4. `guard_target`이 제목이 아니라 장소 이름(`_name_of`)만 봐서 「인사동 산책」처럼 맞는 대상도 되묻는다. 되묻기 후보가 날짜 순이라 실제 경합 항목이 빠진다.
  5. 일정 밖 지역(인사동) 질문을 처리할 길이 없다 — 위치 요청, 「어느 일정?」, 모델 기억 추천(「일반 안내」 표시만) 중 하나로 끝난다.
  6. 후속 「왜 추천했어?」가 직전 Case `options[].reason`을 읽을 계약이 없다.
  7. `same_site`(첫 낱말·1.5km) 제외·영업 모름·가격 모름이 고객 답에 설명되지 않는다.
- 설명 작성기 후보 `4bc2d9080`는 이 경로를 고치지 않는다. 오히려 `ask_policy`→schedule reroute가 이 질문을 인사동 배치 이유 설명으로 바꿀 위험이 있다 `[추정]`.
- 실제 원인 확정에 필요한 입력: 사용자의 정확한 문장·시각·화면(EKS/x600)·받은 답, trip 또는 Case id(승인된 읽기 전용), 실모델 재생 예산.
- 전달 상태: 36cd5c에 **전달되지 않았다**(10-30 데스크톱 전환 위험으로 차단, 11-02 `c283e5` 재확인).

### 5-2. 일정 「설명」 질문 응답이 제한적인 원인 (10-29, `fab3da50a` 읽기 전용)

- 출처: 하위 `20261029_115250_0de349`의 scratch `schedule-explain-audit-20261029/REPORT_KO.md`(지워짐).
- 원인: (1) `decision_unit` FACTS에 설명·이유 읽기 종류가 없다 (2) day·schedule 답은 템플릿 목록뿐 (3) 모델이 장소·이동 사실을 서술하지 못하게 막혀 있다(안전 장치로는 정당) (4) 「왜 이렇게 짰어」가 ask_policy로 가서 「찾지 못해 지어내 답하지 않았어요」로 끝나기 쉽다 `[추정: 비율 미측정]` (5) 일정 짜기가 저장한 `detail.planner`(끼니·이동 기준·고정 등)를 채팅이 안 읽는다 (6) `change_explanation` 분기는 FACTS에 없어 해석 실패로 끝난다 — 완성 후보는 원본 작업 폴더에 미커밋으로만 있었다.
- 이 조사를 바탕으로 만든 후보가 [설명 작성기](../../handoff/2026-10-29_explain-writer-llm.md)다.

### 5-3. 설명 작성기 후보 보존 (이번에 실행)

- 상태: `feat/schedule-explain-writer-20261029`(`738aa9ad9`→`4bc2d9080`, 부모 `fab3da50a`)와 미커밋 수정 10개 파일·미추적 13개가 Hermes scratch `schedule-explain-impl-20261029/wt`에만 있었다. 원격·backups에 bundle이 없었다. scratch는 24시간 유휴 시 정리 대상이다.
- 보존: guguroute `backups/explain-writer-wt-20261103/` — thin bundle(`--not fab3da50a`, `bundle verify` 통과, head `4bc2d908005c`), `uncommitted-r8-tracked.patch`(10 files, +912/−106), 미추적 13개 원본 사본(`cmp` 13/13 동일), `SHA256SUMS` 16/16 OK. 원 작업트리는 건드리지 않았다(`GIT_OPTIONAL_LOCKS=0` 읽기만).
- 같은 폴더의 증거(`ev`·`llm`·`paid`·`review*`)는 옮기지 않았다. scratch 정리 때 사라질 수 있다.

## 6. 미완료·결정 대기

| # | 항목 | 다음 담당 |
|---|---|---|
| 1 | 비밀 후보 값(§7)과 이전 노출(Hi 하위 1행, `C:/_proj/k.txt` 평문 키, jira_for_me 저장소 평문 토큰 2곳, 로컬 모델 서버 키 로그 노출 보고) 교체 여부 | 사용자 |
| 2 | 인사동 대안 수정(§5-1) 담당 배정·전달 | 총괄 후속 세션 → 36cd5c |
| 3 | 설명 작성기 후보 통합 여부, 유료 서빙 실검증 | 사용자·라우팅 담당 |
| 4 | EKS: 제품 결함 4건 수정은 Mobility 담당 정책 승인 필요, 1ab3f0d88 수정, PR110 HOLD, reader fatal 로그는 사용자 제공 비식별 로그 필요, 측정용 운영 접수 32건 처리 | 36cd5c·사용자 |
| 5 | 보안 관문 124/125(보존 XML 탐지) — 여러 후보 통합을 막음. 탐지 약화·증거 삭제 없이 해결할 방법 결정 | 사용자 |
| 6 | TeamFlow 미완료 109건 | 매니저 브랜치 담당 |
| 7 | 골든 47문항 재실행(커밋 한도·GPU 경합), SFT 학습 시작 결정 4건 | 사용자 |
| 8 | NPU 실측 재개, NPU 세션에 용량 관리 지시 인수 확인 | NPU 세션 |
| 9 | C: 400GB(약 156.7GB 부족), Hermes 150GB 적용, scratch 승인 후보 15.95GB, 하드링크 분리 | 사용자 |
| 10 | x600 F: `qemu-cow-probe` 보존 결정 재검토, x600 유료 fallback 290회 원인·비용 | 사용자 |
| 11 | 디스코드 설정 질문 대상 확인 | 사용자 |
| 12 | 로컬 Qwen 세션 50% 압축(`threshold_tokens`) 여부, GHelper 빌드·CI, `Explain` 스킬 설치 여부 | 사용자 |
| 13 | 30분 감시 cron `a19614eada92`는 세션과 무관하게 계속 돈다(마지막 05:08). 유지 여부 | 사용자 |

- 기록 불일치: 루트 AGENTS.md 「Claude 실행 전 훅은 대표적인 위험 셸 명령을 차단한다」는 11-02 `c283e5` 조사에서 훅 미연결로 보고됐다. 이번에는 확인·수정하지 않았다(규칙 문서 변경은 범위 밖).
- [삭제 후 인계](../../handoff/2026-11-02_proj-root38-post-deletion-handoff.md)의 「HOLD 3건 실행 결과(36cd5c)」 절은 아직 비어 있다. 결과는 위 HOLD 보고서 3개에 있다.

## 7. 비밀 검사 (값 미출력)

- 부모 세션 2,056행: 고엔트로피 키=값·URL 자격·토큰 접두 0건 `[실측, 휴리스틱]`.
- 위임 하위 153개: 후보 19행·13개 세션. 이름·길이만 적는다.
  - `ACOP_SECRET_KEY`·`ACOP_COMPOSER_JWT_SECRET`·`ACOP_COMPOSER_ISSUER_SECRET` — 두 값 묶음(길이 37/34/37, 엔트로피 4.2~4.4와 34/38/41, 3.4~3.6), 하위 `7ba169`·`f6f619`·`33559d`·`eef96a`·`c47631`·`77b790`·`2a7efd`의 도구 출력. 실값인지 시험값인지 미확인.
  - `TEAMFLOW_API_TOKEN`(26자, `be5e8a`), `NEXT_PUBLIC_GOOGLE_MAP_API_KEY`(29자, `6b265c`) — 미확인.
  - `postgresql://…` 자격 8자(엔트로피 2.75) 5건 — 로컬 시험 DB 기본값으로 보인다 `[추정]`.
- 도구 출력은 모델 제공자에게 이미 전송됐다. 세션 삭제는 이 값들을 무효화하지 않는다. 0건은 안전 증명이 아니다.

## 8. 삭제 시 영향 (Hermes 2026.7082, v0.22.5)

> 2차 확인(§11)이 이 절의 행 수(19,633→19,602)와 「소스 재확인 안 함」을 대신한다. md 내보내기의 가림은 기본이 아니라 `--redact`를 줘야 켜진다.

- 설치된 `sessions delete`는 `model_config._delegate_from`이 있는 하위를 재귀로 지운다(skill `hermes-compacted-session-audit`의 검증 기록, 이번에 소스 재확인은 안 함).
  - 함께 지워짐: 위임 하위 153/154개, 메시지 19,633행. 이 하위들의 보고는 대부분 wiki에 있으나 전문 근거는 DB에만 있다.
  - 지워지지 않음: 후속 세션 `20261103_032201_d047d36a`(태그 없음, `_reset_from`, 열려 있음, 하위 2개) — 부모 참조를 잃는다. 삭제 전에 후속 세션이 부모 참조 없이 동작하는지 확인이 필요하다.
  - `state_meta` 지역 정책 lineage에 이 세션은 없다(0건). 대신 admission 결과 377건·mutation 5건이 이 세션 id를 담고 있다. 삭제가 이를 지우는지는 미확인이다.
- 삭제가 안 지우는 것: logs, scratch, browser 작업공간, wiki, backups, cron. FTS·빈 페이지는 `sessions optimize`가 필요하다.
- wiki 근거 손실: 이 세션 id를 인용하는 wiki 문서 13개(이 문서 제외, `grep 5fbd35ab`)는 삭제 뒤 원문 확인이 불가능해진다. 주요 문서는 §관계에 있다.
- 대안: `sessions export <dir> --format md --session-id 20261027_205452_5fbd35ab --delete-after-verified --yes`는 부모와 위임 하위를 가림 처리해 내보낸 뒤 지운다. 내보낸 파일에도 §7 후보가 남을 수 있으니 저장 위치를 정해야 한다.
- wiki 자체 내구성: 이 보고서와 11-02 보고서·인계 다수는 Git 미추적(`??`), 목차·로그는 미커밋(`M`)이다. 이 PC의 단일 사본이다.

## 9. 압축·절단과 복구 가능 범위

- 압축 3회. 압축 전 원본은 `compacted=1`로 DB에 그대로 있다. 요약 안의 `HERMES-CONTEXT-COMPRESSION … omitted` 구간(요약 1: 1,500자·3,386자, 요약 2: 1,262자)은 요약문만 잘렸고 원본 행은 남아 있다.
- 꼬리 원본 121행은 활성 사본과 따로 저장돼 있다(활성 쪽 도구 출력은 잘렸을 수 있음).
- **이미 잃은 것**: scratch 정리로 `schedule-explain-audit`, `insadong-alt-reason`, `insadong-chat-fullpath`의 실행 증거(`ev/*.xml`·`tree/` 합성 시험), `x600-croot-readonly`·`x600-froot-readonly` 조회 출력, `overnight-routing-supervisor.md`, `hi-audit-close` 스크립트. 보고서 본문은 도구 인자에서 복구했지만 실행 증거 파일은 복구할 수 없다.
- 10-31 라우팅 정리 때 `auth-diagnostic.log` 1개가 비밀 이름 규칙으로 보존되지 않았다(기존 기록, 변화 없음).

## 10. 이번 변경

- 새 문서: 이 보고서, [인계](../../handoff/2026-11-03_telegram-orchestrator-5fbd35ab-close-handoff.md).
- 수정: `wiki/handoff/index.md`(맨 위 1줄), `wiki/log.md`(끝에 1절), `wiki/index.md`(맨 위 1줄). 수정 전 사본: guguroute `backups/telegram-5fbd35ab-wiki-20261103/`(`SHA256SUMS.before`).
- 보존: guguroute `backups/explain-writer-wt-20261103/`(§5-3).
- 조회 스크립트: guguroute scratch `sess5fbd/`(state.db 읽기 전용). 내용 덤프 파일은 이 작업 끝에 지운다.
- `tools/safe_git.py`는 Python subprocess `WinError`로 실패해 `GIT_OPTIONAL_LOCKS=0 git status/log/bundle` 읽기로 대신했다.

## 11. 삭제 동작·원문 보존본 2차 검증 (설치 소스 기준, 11-03 05:40~06:10)

- 수행: 후속 세션 `d047d36a`의 하위 작업. 세션 삭제 0, 세션 DB 쓰기 0(`mode=ro`, Hermes `SessionDB(read_only=True)`), 비밀 값 출력 0, 외부 전송 0. 이 절이 §8의 「소스 재확인 안 함」·행 수를 대신한다.
- 읽은 소스(설치본 `NousResearchInc.HermesAgent_2026.7082.1520.0_arm64`, v0.22.5): `hermes_cli/sessions_cmd.py`(`_cmd_delete`·`_export_markdown_single`), `hermes_state_sessions.py`(`delete_session`·`get_session_delete_targets`·`_collect_delegate_child_ids`), `hermes_state_local.py`(`owned_lineage_ids`), `hermes_state_mutation_retirement.py`(`retire_sessions`), `hermes_state_media.py`, `hermes_state_portability.py`(`export_session`·`import_sessions`), `hermes_cli/session_export_md.py`.

### 11-1. 실제 삭제 범위 `[실측: 설치 코드로 계산]`

| 항목 | 값 |
|---|---|
| `sessions delete 20261027_205452_5fbd35ab` 대상 | 154 = 부모 1 + 위임 하위 153(`_delegate_from` 재귀). 지역 reset lineage 없음(`owned_lineage_ids` = 부모만) |
| 지워지는 메시지 | 21,658행 = 부모 2,056 + 하위 19,602(§8의 19,633을 정정). 본문 35.45M자 + 도구 호출 12.68M자 |
| 지워지지 않는 것 | 후속 세션 `d047d36a`(열림, `_reset_from`) — `parent_session_id`만 NULL. 그 하위 4개(이 작업 포함)는 범위 밖 |
| 삭제 가드 | admission 369/369 terminal, worker 0, 활성 턴 lease·압축 잠금 0 → 지금 실행하면 막히지 않는다 |
| DB 밖에서 같이 지워지는 파일 | `cache/spillover/` 도구 출력 원본 64개(6,570,090 B, 다른 세션도 가리키는 3개는 남음) · `sessions/request_dump_<id>_*.json` 9개(API 요청 사본, 비밀 이름 포함). `sessions/<id>.json(l)`은 0개 |
| CASCADE | `session_model_usage` 158행 |
| 남는 DB 흔적 | `async_delegations` 37행(FK 없음, 결과 1.8M자, key=value 비밀 패턴 0) · `state_meta` admission 결과 378건은 전사 칸을 비운 영수증으로 축소 · mutation 5건은 내용 칸 NULL · 삭제 id 영구 fence 추가 |
| 빈 페이지 | state.db `secure_delete`=0. 지운 내용은 VACUUM 전까지 파일 빈 페이지·WAL에 남는다. `sessions optimize`는 다른 Hermes 프로세스(Desktop 등)가 state.db를 잡고 있으면 거부(`--force`는 실행 중 작성자 위험) |
| 삭제 hook | 프로필 `hooks/`·`plugins/`에 `on_session_delete` 0 |

### 11-2. 내보내기 방법 비교 `[소스 확인]`

| 방법 | 범위 | 원문 손실 | 비밀 | 복원 |
|---|---|---|---|---|
| `export <dir> --format md --session-id <id> --delete-after-verified --yes` | 154개를 내보내고 같은 트랜잭션에서 삭제 | 표시용 투영(`active=1 OR compacted=1`)이라 꼬리 원본 175행(부모 121·하위 54)이 빠진다. spillover 본문 없음 | **가림은 기본 꺼짐** — `--redact`를 줘야 가린다(가리면 원문 손실). 기본 위치 `<profile>/session-exports` | md는 Hermes로 되돌릴 수 없다(읽기용) |
| `export <file> --format jsonl --session-id <id>`(id마다) | 1세션씩 | 저장된 모든 행 + `active`/`compacted` | 가림 없음 | `import_sessions`로 **다른** 저장소에 복원. 세션당 5 MiB·1만 행 한도. 삭제한 같은 프로필에는 같은 id 가져오기를 영구 거부 |
| `hermes backup` | Hermes 홈 전체 zip(.env·auth 포함) | 없음 | 비밀 전체 동봉 | 범위가 너무 넓고 기본 `-k 3`이 이전 zip을 지운다 → 권하지 않음 |

### 11-3. 보존 실행 결과 `[실측]`

- 위치: guguroute `backups/session-5fbd35ab-export-20261103/`(약 112 MB). 저장소·wiki 밖이고 NTFS 권한은 state.db와 같다(SYSTEM·Administrators·사용자). **암호화·가림 안 됨 — 비밀 후보 값이 그대로 있다.** 같은 디스크의 단일 사본이다.
- 내용: `jsonl/` 154개(정상 CLI `sessions export --format jsonl`), `spillover/` 64개, `delete-targets-154.txt`, `MANIFEST.md`, `SHA256SUMS`(220/220 OK).
- 대조: DB 21,658행 = 내보낸 21,658행, 내용·도구 호출·표시·시각 일치 21,658/21,658 = 100%. 세션 칸 불일치 0. spillover `cmp` 64/64 = 100%.
- 복원 시험(scratch의 버리는 저장소, 시험 뒤 삭제): 하위 153/153 = 100% 가져오기 성공·내용 일치. 부모 0/1 — 8,571,235 B라 세션당 5 MiB 한도로 거부. 부모는 jsonl 원문으로 온전하지만 Hermes 가져오기로 되살리려면 한도 밖 처리가 필요하다.
- 넣지 않은 것: request_dump 9개(같은 내용의 요청 사본·비밀 이름 포함), `session_model_usage` 158행(세션 칸의 토큰·비용 합계는 jsonl에 있음).

### 11-4. 하위 153개 추가 조사 `[실측: DB 읽기 + 파일 존재]`

- 하위가 쓴 파일(write_file·patch) 중 지금 없는 것: 102개 세션의 516개(scratch 459, 11-02 지운 `C:/_proj/*1029` 작업 폴더 57). scratch는 132/153 = 86.3% 세션에서 일부 이상이 이미 사라졌다. 쓴 내용은 보존본 jsonl의 도구 인자에 남아 있다(실행 산출물·로그는 복구 불가).
- 사라진 .md/.txt 73개(49개 세션) 중 1,500자 넘고 wiki에 이름·문장이 없는 19개를 대조했다. 대부분 팀 원격 브랜치 문서(이름이 바뀐 `2026-10-28_먼저채우기_빈칸만_계산_서빙속도.md`·`2026-10-29_라우팅7건_TeamFlow_A13_role-manager_통합.md`·`2026-10-28_접수SSE_슬롯수명_후속.md` 등)나 기존 인계로 대체됐다. 남은 고유 요지:
  - `d430db` TeamFlow 미해결 14건 코드 대조(10-27): 코드상 해결 3(678·692·694)·미해결 6·서버 문제 4·실행 확인 필요 1(653), ST4F-631 로컬 재현. 이후 631·711 인계가 대체.
  - `0f2d95` SSE beat 후보 독립 검토: 조건부 적합. 끊김 뒤 슬롯은 반납되지만 스레드·DB 연결은 남는 수명 문제 → 후속 `접수SSE_슬롯수명_후속`이 다룸.
  - 나머지는 전달 메시지·프롬프트·스크립트 원문.
- 마지막 보고에 미완료 표현이 있는 하위 74/153 = 48.4%. 대부분 §4·§6과 기존 인계에 있다. 없던 것만 아래에 더한다.
- NPU 감사(`0e311b`)가 말한 「Claude 설계 원문은 DB 로그 #35159에만」은 이 범위가 아니다(다른 세션 행, 삭제 대상 아님).

### 11-5. §6에 더할 미완료·결정 대기

| # | 항목 | 근거 하위 | 다음 담당 |
|---|---|---|---|
| 14 | 원본 작업트리에만 미커밋으로 있는 「부하 동원」 기능 — 팀 최신에 없음, 별도 통합 과제 | `da8b6c` | 라우팅 담당·사용자 |
| 15 | 이관 미확인 3/66: `.codex/hooks.json`(사용자) · `setup_oracle_model_gpu.sh`(운영) · rename 전 EKS manifest(EKS) | `5ef9e1` | 각 담당 |
| 16 | 10-27 서빙 개선 순위 1(확인 화면 먼저)·2(출력 모양 재학습)·5(대안 펼칠 때 계산), x600 `OLLAMA_NUM_PARALLEL` | `67c1cc` | 사용자 결정 |
| 17 | jira_for_me MCP: 읽기 연동 확인, Hermes 등록 안 함, 그 서버 `.env` 토큰은 프로젝트 84 권한 없음 | `54eb96` | 사용자 |
| 18 | x600 compose/env·마이그레이션 상태 폴더에 DB 비밀번호·API 키 평문(값 미확인) — §6-1 비밀 목록에 추가 | `055ba1` | 사용자 |
| 19 | 실제 대화 골든셋 605 에피소드 원본 미발견, 어댑터 `f01456d8` 학습 파일 미확인 | `055ba1` | 모델 담당 |
| 20 | 시험용 Python 환경 `date_risk_env_312`(scratch)가 이미 사라짐 — SFT 검사 재실행 때 환경 재구성 필요 | `be7a0b` | SFT 담당 |

### 11-6. 삭제 준비 판단

- **원문 보존: 준비됨.** 삭제로 사라질 154개 세션의 전 행과 spillover 64개가 보존본에 있고 해시·행 대조를 통과했다. 부모 1개만 Hermes 가져오기 한도를 넘는다.
- **비밀: 해결 안 됨.** 보존본도 원문이라 비밀 후보가 그대로 있다. 삭제도 보존도 값 무효화가 아니다(§7). 교체 여부는 사용자 결정이다.
- 실행 방법(사용자 결정): 보존본이 있으므로 `hermes -p guguroute sessions delete 20261027_205452_5fbd35ab`(확인 프롬프트)로 충분하다. md 사본도 원하면 `sessions export <비공개 폴더> --format md --session-id 20261027_205452_5fbd35ab --redact --delete-after-verified --yes` — `--redact`를 빼면 가리지 않은 사본이 하나 더 생긴다. 빈 페이지 정리는 다른 Hermes 프로세스를 멈춘 뒤 `sessions optimize`.
- 남는 영향: 후속 `d047d36a`는 부모 참조가 NULL이 된다(열린 세션 동작 영향은 시험 안 함). wiki 13개 문서의 이 세션 id 인용은 보존본 jsonl로만 확인할 수 있다.
- 조회 스크립트: guguroute scratch `sess5fbd/v2/`(읽기 전용). 내용 덤프는 끝에 지웠다.

## 관계

- [Hi·현재 세션 4차 감사](2026-10-28_hi-and-current-session-close-readiness-audit.md) — 이 세션의 10-28 21:24까지 상태
- [38개 삭제 후 인계](../../handoff/2026-11-02_proj-root38-post-deletion-handoff.md) — 이 세션이 마지막에 맡긴 HOLD 3건
- [EKS 폴더 보존](2026-10-31_eks-folders-retire.md) · [라우팅 A11 폴더 보존](2026-10-31_routing-a11-folders-retire.md) · [루트 38개 담당 전달](2026-11-01_proj-root-38-owner-relay-and-blockers.md) · [clones 이전](2026-11-01_clones-root-move-and-enforcement.md) · [13개 최종](2026-11-02_proj-root-13-final-retirement.md) · [x600 F:](../../handoff/2026-11-02_x600-f-root-guguroute-cleanup.md) — 이 세션 id를 인용하는 기록
