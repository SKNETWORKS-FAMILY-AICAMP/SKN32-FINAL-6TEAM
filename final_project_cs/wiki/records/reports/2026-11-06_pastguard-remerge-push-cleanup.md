---
type: report
title: 과거 날짜 가드레일 세션 마무리 — 원격 1cf4542a1 위 재병합 · 시험 · push · 정리
status: draft
domain: travel
---

# 2026-11-06 과거 날짜 가드레일 세션 마무리

사용자 승인(2026-10-26): 「문서화도 마무리하고, 이 세션 push 할 건 다 하고 삭제처리해」. 이 문서는 2026-10-26 세션 전체(통합 병합 → 날짜 가드 4요구 → LLM 날짜 읽기 → 지난 일정 삭제만 → a465c6022 재병합)를 한 곳에 묶고, 2026-11-06 의 마지막 재병합 · 시험 · push · 정리를 적는다. 앞 보고서는 고치지 않고 여기서 연결한다.

작업 위치: 격리 worktree `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106/wt`(`git -c core.autocrlf=false -c core.longpaths=true worktree add`), 브랜치 `integ/pastguard-on-mgr-1cf4542a1-20261106`. 원본 `C:/_proj/final_workspace` 는 조회 · fetch · worktree add 만 했다(pull · reset · checkout · stash · clean 0).

## 결론

- 두 원격 role-manager 는 같은 `1cf4542a1` 이었다(팀 SKN32-FINAL-6TEAM · 개인 roroblack/A-COP, 2026-11-06 09:3x KST fetch). 10-26 HEAD `60af7a7d2` 는 원격의 조상이 아니었다(원격이 `a465c6022` 뒤로 119커밋 전진).
- `1cf4542a1` 에서 새 브랜치를 따 `60af7a7d2` 를 병합했다(rebase 아님, `43a3ced29`). 충돌 9파일을 파일별로 풀었다. 원격의 날짜 변경 A13(`cb284d301`)이 우리 날짜 형식 판단과 의미상 겹쳐 함께 맞췄다(아래).
- DB 없는 격리 실행: unit/travel 8467/8467 = 100%(skip 128) · 웹 tsc 0 · eslint 0 · vitest 1235/1235 = 100%. gates 와 나머지 unit 의 실패는 원격 자체 실패 · runner 차단으로 분리했다(아래 「시험」).
- push 는 이 문서 커밋을 포함해 fast-forward 로만 한다. 실제 반영 SHA 는 push 뒤 `ls-remote` 로 확인해 인계 응답에 적는다(이 문서는 push 전에 커밋된다).

## 이 세션 전체(2026-10-26 ~ 11-06) — 연결

| 단계 | 내용 | 정본 기록 |
|---|---|---|
| 1. 통합 병합 | 원격 develop(`446bbb170`) + role-eval-ui(`0239cef98`)를 role-manager `08b995976` 위 `integ/manager-develop-ui-20261026-0045` 로 병합. develop 병합에서 충돌 9파일(아래 표). role-eval-ui 병합은 충돌 0 | 이 문서 「통합 병합 충돌 9개」 |
| 2. 날짜 가드 4요구 | ① 모델이 연도 없이 읽은 날은 다가오는 날 ② 채팅 수정이 지난 날짜 · 시각을 내면 「혹시 오타 아닌가요?」 + 가까운 앞 날짜 버튼(`choices`) ③ 일정 추가 · 수정은 지금 이후만(`plan_edit`, 마지막 남은 일정 빼기 금지 `no_upcoming_items`) ④ 지난 일정은 삭제만 | [과거 날짜 가드레일 확장](2026-10-26_past-date-guard-extension.md) · [지난 일정은 삭제만](2026-10-26_past-edit-delete-only.md) |
| 3. LLM 날짜 읽기 | 정규식 연도 판정을 빼고 모델이 `date_quote` → `year_quote` → `date_form` → `date` 를 낸다. 로컬 E4B 81문장 before/after: 개발 41 28/41 = 68.3% → 39/41 = 95.1%, 보류1 20 14/20 = 70.0% → 17/20 = 85.0%(독립 근거 아님), 깨끗한 보류2 20 12/20 = 60.0% → 15/20 = 75.0%. 「다가오는 날을 지난 날로」(전부 과거 거절 위험) 10건 → 1건 | [날짜 읽기 LLM 판단 전환](2026-10-26_llm-date-reading.md) · [증거](../evidence/2026-10-26_llm_date_read/) |
| 4. 1차 통합 시험 | HEAD `2cccbfaef` 전체 시험, 원격 전진(웹 5파일 충돌)으로 push 보류, v9 로컬 서빙 유지 | [통합 HEAD 전체 시험 · push/서빙 결정](2026-10-26_merged-head-fulltest-push-serving-decision.md) |
| 5. a465c6022 재병합 | 충돌 코드 0 · wiki 4, Codex 3회(달력에 없는 날 첫날 채움 지적 → `92541686d`) | [a465c6022 위 재병합](2026-10-26_rebase-merge-on-role-manager-a465c6022.md) |
| 6. 1cf4542a1 재병합 · push · 정리 | 이 문서 | — |

### 통합 병합 충돌 9개(`446bbb170`, develop → integ) 해결 방식

`git show --remerge-diff 446bbb170` 로 다시 확인했다(증거 `remerge-446bbb170.diff`). 양쪽 모두 「전부 과거 날짜 거절」 hotfix(`d2ab93a65` develop 쪽 · `08b995976` role-manager 쪽 이식)를 가졌고, develop 쪽이 그 위에 요식 판정(`dining_review`) · 진행 알림(ST4F-732)을 더 가졌다.

| 파일 | 해결 |
|---|---|
| `intake/review.py` | develop 쪽(`_store_read` · `dining_review.refresh` · 저장 질문 답 병합 · `on_event` 전달)을 택했다 — role-manager 쪽 `store(...)` 줄의 상위집합. 두 쪽 모두 `guard_dates(payload)` 반환은 같다 |
| `tests/unit/travel/test_all_past_confirm_api.py` · `test_all_past_dates.py` | develop 쪽(`dining_review` import · monkeypatch 추가) — 시험 대상 코드가 develop 쪽 review 라서 |
| cs `wiki/index.md` · 루트 `wiki/index.md` | 두 쪽 줄을 모두 남김(role-manager 이식 21/21 줄 + develop 35개 회귀 줄) |
| `records/reports/2026-10-25_all-past-calendar-hotfix.md` · `..._allpast-normal-confirm-proof.md` · `wiki/handoff/` 같은 이름 2개 | add/add — role-manager 쪽 「role-manager 이식」 절을 위에, develop 쪽 원래 이력을 아래에 둠 |

## 2026-11-06 재병합 충돌 9개(`43a3ced29`)

| 파일 | 해결 |
|---|---|
| `intake/agent_read.py`(5곳) | 항목 스키마 하나에 셋을 함께 — 원격 I05 `_dated_items`(날짜를 내면 인용 필수 · 두 갈래 anyOf) + 우리 칸 순서 `date_quote → year_quote → date_form → date` + 원격 I06 `locked` · `locked_quote`. 프롬프트 예시는 원격의 「(예약 완료)」 항목(locked null)에 우리 날짜 칸을 더함. 프롬프트가 바뀌었으므로 판을 `intake.agent_read.v4-date-form` 으로 올리고 판을 고정한 I06 시험 2곳을 같이 올림. `ground` 는 우리 `_grounded_date`(인용 없음 · 형식 없음 · 달력 없음 처리 포함)와 원격 I06 고정 근거 확인을 함께 둠 |
| `conversation/chat_edit.py` | 원격 `split_range` · `shift_range`(범위 옮기기 한 곳 정책)와 우리 `past_item_refusal` · `frozen_refusal` · `past_time_refusal` 을 나란히 둠(서로 다른 함수) |
| `tests/e2e/test_intake_interpretations_api.py` · `test_intake_reading_prefs.py` | 원격의 실행 날 기준 상대 날짜(`reldate.day`)에 우리 `year_quote` · `date_form` 칸을 더함 |
| `wiki/external/trip-chat-context.md` · cs `wiki/index.md` · cs `wiki/log.md` · `wiki/handoff/index.md` · 루트 `wiki/index.md` | 두 쪽 모두 남김(원격 새 항목 위, 우리 10-26 항목 아래) |

보존 검산(프로그램, `preserve-43a3ced29.json`): 우리 diff(`a465c6022..60af7a7d2`) 추가 줄 3,519 중 병합 트리에 그대로 없는 줄 15, 원격 diff(`a465c6022..1cf4542a1`) 48,636 중 35 — 전부 위 표에서 두 쪽을 한 줄로 합친 곳(스키마 required · 예시 JSON · dropped 칸 · 시험 자료 · A13 판정 줄)이다. 그 밖의 빠진 줄 0. 충돌 표시 0(`git grep -E '^(<<<<<<<|>>>>>>>)( |$)'`).

### 의미상 겹침 — 원격 A13(`cb284d301`)과 우리 날짜 형식 판단

- 원격 A13(10-28 전수검사, Codex 검토): 모델이 고른 해가 날짜 인용(`date_quote`)에 적혀 있지 않으면 값은 두고 확인 표시(`how: agent_year`). 정규식 `_year_written`.
- 우리(10-26 사용자 지시 · 확정 정책): 날짜 형식은 모델 판단, 연도를 적은 과거만 과거, 연도 인용이 원문에 없으면 연도 없는 날(오늘 이후 처음 오는 그 날 · 확인 필요).
- 그냥 합치면: ①머리줄 해(「2027년 겨울 여행 / 1월 3일」)를 A13 이 「해 없음」으로 표시, ②「'26.3.5」(연도 인용 `'26`)도 표시, ③원격 시험 3파일 · 우리 시험 1개가 상대 계약 때문에 실패(병합 직후 unit/travel 12 실패, 증거 `merge1-unit-travel-failures.txt`).
- 맞춘 방법: A13 판정은 남기되 근거를 **모델이 원문에서 인용한 연도 조각**(`AgentItem.year_quote`, 없으면 `date_quote`)으로 바꿨고 줄인 해의 따옴표(「'26」)를 적힌 해로 본다. 연도 없는 날(`--MM-DD`)은 날짜 해석이 이미 `year_filled`(확인 필요)로 두므로 A13 이 다시 보지 않는다. 따라서 A13 이 실제로 더하는 경우는 「연도 인용은 원문에 있으나 모델 해와 다르다」(「1027년」 인데 2027)뿐이다.
- 원격 A13 시험의 「값은 그대로」 단언 중 연도 근거가 원문에 없는 3경우는 정책(다가오는 날)이 앞서 값이 2026-10-30 으로 바뀐다 — 확인 표시 · 「연도」 안내 단언은 남겼다. 이 판단은 2026-10-26 사용자 확정 정책을 따른 것이며 A13 쪽 의도와 다르면 사용자 결정이 필요하다.
- 머리줄 해 시험을 새로 넣고, 판정 근거를 옛 `date_quote` 로 되돌리는 변이에서 실패하는 것을 확인했다(`a13-mutation-red.log`, 1 failed).
- 원격의 범위 옮기기(`shift_range`)는 지난 시각이 되면 기존 `time_in_past` 거절을 낸다(버튼 없음) — 한 일정이 아니라 여러 일정이라 「가까운 날짜」 버튼을 붙이지 않았다. 지금 이후만 규칙은 서버 `plan_edit` 가 같이 지킨다.

## 시험 (DB 없음 · 실DB/네트워크 차단)

실행기: 새 Python 3.12.10 venv(NuGet `python/3.12.10`, `requirements.txt`) + `run_isolated.py`(socket connect/bind/listen · `create_connection` · `psycopg.connect` 차단, stdlib socketpair 만 예외, 합성 unit 설정). 10-26 의 `fullrun-20261026` · `date_risk_env_312` 는 scratch 정리로 이미 없어 새로 만들었다. 선택 `-m "not live and not db"`. 웹은 worktree 안에 `npm ci --ignore-scripts`(원본 node_modules 는 next 16.3.5 로 lock 과 달라 재사용하지 않음), node v26.7.0.

| 묶음 | 병합 직후 | 최종 `43a3ced29` |
|---|---|---|
| tests/unit/travel | 8455/8467, 12 실패(위 겹침) | **8467/8467 = 100%**(skip 128 — git 밖 자료 없음, 통과로 세지 않음) |
| architecture + contract + security | 632/633, 1 실패 | 문서 커밋 뒤 다시 돌림 — 인계 응답 참고 |
| tests/unit 나머지 | — | 1827/1831 = 99.8%, 4 실패 = `test_llm_failover::test_http_*` — runner 가 loopback HTTPServer bind 를 막음(10-26 과 같음, 제품 실패 아님) |
| 웹 tsc · eslint · vitest | 0 · 0 · 1235/1235 = 100%(138 파일) | 웹 파일은 병합 뒤 바뀌지 않음 |

- gates 1 실패 `tests/security/test_no_infra_in_tracked_files.py` 는 **원격 자체 실패**다: 걸린 두 파일(`wiki/records/evidence/2026-10-29_st4f728-guest-logout/security-ready.xml` — 시험값 공인 IP · 웹훅 모양, `wiki/records/reports/2026-10-26_activity-public-web-text-evidence.md` — 공인 IP 모양 숫자열)은 `1cf4542a1` 과 바이트가 같고 우리 diff 밖이다. 원격 기준 트리로 따로 돌리지는 않았다(파일 동일로 판정). 이 세션은 고치지 않았다.
- DB 표시 시험(unit/travel 506건 등)과 실모델(E4B) 재측정은 하지 않았다.

## 알려진 한계 · 남은 모델 실패 유형

- 웹 · 채팅에서 **이미 지난(고정된) 일정을 삭제하는 경로가 없다** — 수정 접수가 지난 일정을 싣지 않는다. 사용자 결정으로 보류(지난 일정은 「삭제만」 정책이지만 실제 삭제 버튼 · 채팅 빼기는 아직 「지난 일정 빼기는 아직 채팅으로 하지 못해」 안내).
- E4B 남은 날짜 실패(10-26 after C): 「'26.3.5」 연도 인용 비움 · 「11월 둘째 토요일」 날짜 비움 · 「이번 주 일요일」 하루 앞 · 「어린이날」 relative 로 보고 비움 · 「작년 6월 10일」 원문에 없는 2025 · 머리줄 연도 합성 인용, 보류1 「작년 이맘때」. 표본 81문장(합성)이라 서비스 전체로 일반화하지 않는다.
- 이번 병합 프롬프트(`v4-date-form` = 날짜 칸 + I06 locked + I05 두 갈래)는 **E4B 로 측정하지 않았다**. 로컬 서빙 v10 교체도 하지 않았다.
- 원격 범위 옮기기의 지난 시각 거절은 버튼 없는 기존 문장이다.

## 로컬 서빙(v9) · 롤백 정보 — 2026-11-06 실측

- 10-26 기록의 v9 백업 `cache/scratch/fullrun-20261026/serving/v9-identity/` 와 실행 원천 `integ-v9-20261026-025943/runtime-v9-serving/` 은 **이미 없다**. 누가 언제 지웠는지는 `backups/` · 원본 `wiki/records/reports/` 검색에서 기록 0건이라 모른다(Hermes scratch 는 24시간 유휴 항목을 자동 정리한다). 2026-11-06 확인 때 8042 · 3100 · 11434 에 LISTEN 없음(netstat). 따라서 10-26 기록의 롤백 명령은 그대로 쓸 수 없다.
- 이 세션은 서빙을 바꾸지 않았다. v10(= v9 + 이번 제품 패치 + `travel.chat_edit.past_date_choices`) 구성과 E4B 재측정은 남은 일이다.

## 삭제 대상 목록(삭제 전 기록)

사용자 승인 범위: 이 세션이 만든 것만. 실행 중 서빙 · 다른 세션 폴더 · 원본 · 로컬 브랜치는 대상이 아니다.

| 경로 | 상태 · 처리 |
|---|---|
| `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106/` | 이번에 만든 폴더(worktree `wt` · venv · py312 · mingit 복사 · npm 캐시 · 증거). push 양쪽 성공 확인 뒤에만 `git worktree remove` → 이 worktree 만 prune → 폴더 삭제. 크기: 문서 작성 때 3,337,414,935 B · 79,093 파일(`delete-manifest-pre.json`), 삭제 직전 다시 재서 인계 응답에 적는다. 증거 요약은 [`evidence/2026-11-06_pastguard-remerge/`](../evidence/2026-11-06_pastguard-remerge/) 에 먼저 보존 |
| `scratch/mgr-merge-20261026-0045` · `past-edit-delete-only-20261026` · `integ-mgr-a465c6022-20261026` | 이미 없음 — 10-29 다른 세션 정리에서 bundle · patch 보존 후 삭제(`backups/scratch-worktree-archive-20261029/<이름>/SUMMARY.txt`, `wiki/records/reports/2026-10-29_guguroute-scratch-copy-cleanup.md`). `scratch/_archive_20261027/` 아래 같은 이름의 빈 폴더(파일 0)는 다른 세션 보관 폴더라 지우지 않는다 |
| `scratch/past-guard-ext-20261026` · `past-edit-delete-only-20261026-evidence` · `llm-date-read-20261026` · `fullrun-20261026` · `integ-mgr-a465c6022-20261026-tools` · `date_risk_env_312` | 이미 없음(2026-11-06 확인, 삭제 기록은 찾지 못함). git 밖 유일 자료 중 날짜 측정 · Codex 기록 · 시험 요약은 10-26 에 `evidence/2026-10-26_llm_date_read/` · `evidence/2026-10-26_rebase-merge-a465c6022/` 로 저장소에 보존됐다. v9 서빙 식별 백업은 보존되지 못했다(위 절) |

남기는 로컬 브랜치(지우지 않음): `feat/past-date-guard-ext-20261026` `07dcebe35` · `feat/past-edit-delete-only-20261026` `4e61b6b52` · `integ/manager-develop-ui-20261026-0045` `0239cef98` · `integ/rebase-on-manager-a465c6022-20261026` `60af7a7d2` · `integ/pastguard-on-mgr-1cf4542a1-20261106`.

## 인증 메모

전역 git 자격 도우미가 옛 Hermes 앱 경로의 `gh.exe` 를 가리켜 개인 원격 fetch 가 실패했다. 전역 설정은 바꾸지 않고 명령마다 `GIT_CONFIG_COUNT` 환경변수로 현재 앱 경로의 `gh auth git-credential`(기존 roroblack 로그인)을 썼다. 토큰 출력 · 새 로그인 0. `tools/safe_git.py fetch` 는 WindowsApps git 이 Python 에서 WinError 5 라 scratch MinGit 복사본으로 팀 원격만 됐고, 개인 원격 fetch 는 같은 이유로 셸 git(`GIT_OPTIONAL_LOCKS=0`)로 했다.

증거(저장소 안): [`evidence/2026-11-06_pastguard-remerge/`](../evidence/2026-11-06_pastguard-remerge/) — remerge diff 2개 · 보존 검산 · 시험 요약 · A13 원래/변이 로그 · runner · 충돌 해결 스크립트.
