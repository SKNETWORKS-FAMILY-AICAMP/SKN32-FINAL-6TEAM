---
type: report
title: SKN develop 고정 기준 보존·분류·독립 candidate 실행절1
status: documented
domain: travel
---

# 결론

**팀 develop 고정 commit으로 이력이 보존된 독립 candidate를 실제 만들었습니다.** 원본 코드·정본·root current/handoff는 고치지 않았습니다. 순수 응대 adapter 4개·기존 감시 outbox caller의 깨끗한 3-way 1개·관련 시험 소스 7개만 candidate에 선별 반영했습니다. 전체 라이팅 통합·제품 수락 완료가 아닙니다.

## 고정 기준과 경로

- 원본: `C:/_proj/final_workspace`; HEAD `efeb873a8d065fbd28fe8e92dcc42e5cfb3de3e3`.
- 팀: `https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM.git`, `refs/remotes/team/develop = 325ba25d88c91ce97da61f2bda635e5888fe3b40`.
- 원본 HEAD...team develop = **0/899**. 커밋 도달성 차이이며 기능 수·완료율이 아닙니다.
- candidate: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/skn-develop-step1-20261025-014848/candidate`.
- 증거/백업 루트: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/skn-develop-step1-20261025-014848`.
- candidate의 `refs/pins/source-base`, `refs/pins/team-develop`를 고정했습니다. commit/push는 하지 않았고 candidate pushurl은 DISABLED입니다.

## 보존과 실제 해시 검증

- `clone --no-hardlinks --no-checkout` 뒤 candidate에만 `core.longpaths=true`, `core.autocrlf=false` 설정 후 고정 develop detached checkout.
- gitdir·전체 이력 연결성 `git fsck --connectivity-only --no-dangling` exit 0, alternates 없음, sparse 비활성·skip-worktree 없음.
- 변경 전 pinned 파일 **18,985/18,985 = 100%** Git blob 및 index tree 일치.
- 원본의 초기 tracked dirty 101개 중 일반 99개와 작업 관련 untracked 780개 = **879/879 = 100%** manifest hash/바이트 보존 검증. 여기에는 실행 중 다른 readonly child가 추가한 보고서/evidence 4개를 후속 snapshot으로 포함했습니다.
- 나머지 tracked dirty 2개는 legacy 삭제 경로라 원본 그대로 유지하고 예외 manifest에 base tree entry와 독립 이력 보존 위치를 기록했습니다. legacy 내용을 candidate에 되살리지 않았습니다.
- manifest 기준 원본 바이트 변경 0건, 보고서 4개 추가를 조정한 최종 status 동일. 이 고유 보고서 추가만 이후 허용한 원본 변경입니다.
- 선별 후 candidate **18,996/18,996 = 100%** SHA256 동결. 기존 upstream 18,984개는 원바이트 그대로, 1개는 깨끗한 3-way, 신규 11개입니다. index tree는 여전히 pinned upstream과 같습니다(선별 결과는 작업트리, 미커밋).
- `backup/manifest.json`, `backup/bytes/`, `HEAD-working.patch`, `index-working.patch`, `HEAD-index.patch`에 원본 증거를 보존했습니다.
- visible 예외 49,279개는 기존에 남기고 미복사했습니다. 비밀 env/개인키/credentials·브라우저 프로필·node_modules·모델·생성물·백업/legacy는 후보 이관 대상이 아닙니다. ignored 목록은 별도 `backup/ignored-preservation-exceptions.json`; collapsed directory 목록은 내부 파일 총수가 아닙니다.

## 현재 분류 분모: 879개

| 기계적 3-way 분류 | 파일 수 |
|---|---:|
| upstream과 동일(줄바꿈 동등 포함) | 67 |
| 독립 로컬 수정 | 6 |
| 양측 수정, 깨끗한 3-way 가능 | 33 |
| 양측 수정 충돌 | 50 |
| 양측 신규 add/add 충돌 | 17 |
| 독립 로컬 신규 | 706 |
| upstream-only / upstream 삭제-로컬 수정 | 0 / 0 |

**충돌 67파일(50개 수정 충돌 +17개 add/add), 수정 충돌 marker block 124개**입니다. 충돌 파일은 upstream 원본 그대로 두었으며 한쪽을 임의 선택하지 않았습니다. `conflicts.json`에 정확 경로·양측 변경 함수·업무 영역을 기록했습니다. 추가 파일은 신규 기능이라고 자동 인정하지 않습니다. 옛 모듈/커머스·이전 경로/기록은 보존-only 경계로 분리했습니다.

- 상세: `classification.json`, `classification-summary.json`, `conflicts.json`, `applied-manifest.json`.
- exact replay: `candidate-vs-pinned.patch`(tracked 수정) + `candidate-added-source.zip`(신규 소스) + SHA256 manifest. 일반 git diff는 untracked를 담지 않으므로 patch 하나로 전체라 주장하지 않습니다.

## 수용한 경계와 검증

- `components/response/{writing,plan,monitoring,public}.py` 4개: 기존 업무 결과를 작성·공개 enum allowlist로 투영하는 순수 adapter.
- `components/actions/itinerary_actions.py` 1개: 기존 성공/질문 outbox 한 건에 응대 메타데이터 부착. upstream 동작과 동시 변경을 보존한 자동 3-way 결과이며 별도 notice를 추가하지 않았습니다.
- 관련 로컬 시험 소스 7개는 바이트 보존하여 candidate에 추가했습니다. **이 7파일의 전체 pytest suite 통과를 주장하지 않습니다.** 아직 연결하지 않은 plan/inquiry/monitoring caller를 검증하는 시험도 포함됩니다.
- 선택 Python 소스 compile **12/12 = 100%**(import/pycache/service 없음).
- 실제 candidate 순수 adapter 대상 stdlib unittest **10/10 = 100%**: 질문 누락/미확인 근거 거절, deepcopy, 공개 allowlist, 미검증 등록 거절, draft와 등록 분리, 저장판 불일치 거절, 대기/일부 실패 상태. 네트워크·subprocess audit 차단 상태에서 수행했습니다.
- `evidence/compile.json`, `evidence/offline-unittest.{json,log}`, `evidence/pinned-worktree-audit.json`, `candidate-final-hashes.json`, `evidence/source-preservation-verification.json` 참조.
- 위 검증은 production caller 연결·저장/재조회·웹 소비·실 DB/모델 수락이 아닙니다. DB·모델·HTTP·서비스는 기동하지 않았습니다. API 전용 기존 runtime은 최신 requirements와 대조하지 않았으므로 최신 환경으로 채택하지 않았습니다.

## upstream 보존과 다음 소유 영역

upstream README는 이미 `구구루트 (GuguRoute)`이며 현재 규칙·최신 읽기/날씨·등록/reopen·고객 UI도 후속 구현입니다. 이름을 수동 재치환하지 않았습니다. [독립 정적 비교](2026-10-25_skn-pinned-writing-branding-independent.md)의 caller matrix를 함께 사용합니다.

1. **문의** `trip_messages/read_requests/decision_unit/case_dispatch`: 최신 time/weather/focus/pick/변경 계약을 보존하고 질문별 종결 및 Case/chat_reply/duplicate/web 공개 enum만 병합.
2. **계획** `pipeline/review/assemble/agent_read + trip_api`: registration/reopen lock·review_only·재검사·동일 trip 판 보존; commit 후 scoped 재조회한 실제 등록에만 registered 문구.
3. **감시** `pending/trip_watch_batch/trip_watch_cases`: 최신 성공/실패/배치 결과와 저장 증거에 응대 adapter 연결. resolved를 applied로 승격 금지.
4. **웹/세션** 최신 gateway 카드·notice changed·intake 계약을 보존하면서 status 소비와 dispatch generation fence 병합; API 반환 전/후 navigation 경계를 별도 검증.
5. **모델 공급자** llm_failover/ollama_chat/model_stream의 streaming·strict policy/budget 및 최신 requirements 대조. 기존 runtime 완료로 간주하지 않음.

## upstream 자체 추적 산출물 예외

최종 audit에서 **고정 upstream 자체에 이미 추적된 Chromium mockup profile 파일 127개**를 확인했습니다. 로컬 비추적 browserprofile을 가져온 것은 아니지만, 따라서 candidate를 「브라우저 프로필/생성물 전무한 정화 배포본」이라고 부를 수 없습니다. pinned 원본 보존 조건 때문에 임의 삭제하지 않았으며 `evidence/pinned-upstream-artifact-boundary.json`에 별도 기록했습니다. env 이름 추적 파일은 검사된 목록상 example 8개이며 실제 비밀 env를 로컬에서 복사하지 않았습니다. candidate 실행/배포 전 이 upstream 추적 산출물의 별도 제외·보존 결정을 해야 합니다.

## 도구 이슈

WindowsApps Git은 Python subprocess에서 WinError 5였습니다. 동일 bundled Git을 active profile scratch로 복사한 실행 파일은 version/실제 Git 작업 모두 성공했습니다. 첫 원본 status와 후속 status 차이는 다른 child 보고서 4개였으며, 이를 무시하지 않고 별도 snapshot·hash·분모 갱신 후 검증했습니다. 최초 snapshot의 status 원출력은 덮어쓰지 않았습니다. 원본 reset/stash/checkout/clean/pull·commit/push는 수행하지 않았습니다.
