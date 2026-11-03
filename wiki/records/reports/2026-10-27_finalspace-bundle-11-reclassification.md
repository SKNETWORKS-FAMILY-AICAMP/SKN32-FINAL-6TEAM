# 2026-10-27 옛 작업공간 bundle 고유 커밋 11개 — 현재 role-manager 대조 분류

사용자 지시(2026-10-27): 이관 Git bundle 의 고유 커밋 11개를 현재 팀·개인 role-manager 와 대조해 실제 미반영 기능 · 이력 전용 · 보류를 나누고, 안전한 통합 후보를 증거와 함께 보고. push · 원본 수정 금지. 실행 2026-10-27 21:00–21:50 (정적 대조. 시험 실행 없음).

## 결론

- **실제 미반영 기능: 0/11 = 0%.** 런타임 동작이 pin 에 없는 커밋은 없었다. 커밋이 따로 없다고 누락으로 보지 않았고, 커밋마다 추가된 줄·호출부·대체 시험·후속 보고서의 결정을 확인했다.
- 분류(커밋 11개): 이미 반영 3(대체 구현 포함) · 이력 전용 7 · 보류 1.
- 안전한 통합 후보: **C1 하나**(시험 1 + wiki 1쪽, 런타임 변경 0). C2 · C3 는 해도 되고 안 해도 되는 선택 항목이다.
- 분류 대상 파일 행 1,056/1,056 = 100% 를 기계로 셌다(병합 커밋은 자동 병합 결과와 달라진 파일만 셈). 이 비율은 목록을 얼마나 셌는지를 나타낼 뿐이며, 기능이 동작한다는 뜻은 아니다.

## 기준

| 항목 | 값 |
|---|---|
| bundle | `.backup/2026-10-26_finalspace_git.bundle` sha256 `85d0dfc0…a14bcd`, refs 11개 `refs/finalspace/*` |
| 팀 role-manager (SKN) | `93c7ba8ecf053caedfe54ad7199dd0b9321e4f0b` (2026-10-27 fetch exit 0) |
| 개인 role-manager (A-COP origin) | `93c7ba8ecf053caedfe54ad7199dd0b9321e4f0b` — 팀과 같다 |
| 원본 작업 폴더 | HEAD `efeb873a`(pin 기준 0 앞섬 / 1,062 뒤처짐), `git status` 1,155줄(커밋 안 된 변경) |
| 격리 | scratch 의 bare 저장소(원본 objects 를 alternates 로 읽기만)에 bundle 과 두 원격을 fetch. 원본 refs · index · 작업 폴더는 건드리지 않음. `GIT_OPTIONAL_LOCKS=0` |

11개 커밋의 모든 부모(10개 서로 다른 SHA)는 pin 의 조상이다. 따라서 이 커밋들만 가진 내용은 각 커밋 자체의 변경분과 병합 충돌 해소분뿐이다.

## 커밋별 분류

| 커밋 | 내용 | 분류 | 근거 |
|---|---|---|---|
| `520d1b56e` | 서수 어긋남 되묻기(ordinal_conflict) WIP | 이미 반영 | `decision_unit.py` 추가 43줄 · 시험 24줄이 pin 에 100% 있다. 보고서는 pin 과 같은 blob. eval 사례 JSON 4개는 pin 과 줄 기준 96.5~99.7% 일치(이후 다시 만든 것) |
| `988a7eda1` | 고객 외부 알림 운영 설정 + 232 SQL 재실행 | 이미 반영 + 시험·문서 보충 후보 | `customer_notice_delivery.py` · `232_intake_reopen.sql`(`llm_agent` 허용)이 pin 과 같은 blob. `web_guard` 스위치와 `run_outbox_worker` 의 테넌트별 판정도 pin 에서 같은 동작(import 별칭만 다름). 단위·재실행 시험 2개는 pin 의 `tests/integration/test_customer_notice_delivery_switch.py`(7개 시험) · `tests/integration/db/test_intake_migration_replay.py` 가 맡는다. pin 에 없는 것은 관리 콘솔 HTTP e2e(403 · 422 · 409 · 감사 이력)와 `wiki/external/customer-notice-controls.md` |
| `da8dcd533` | 약관 「마이페이지」 문구 · 판 2026-10-13.1(보관 브랜치) | 이미 반영(대체 구현) | 이 커밋은 「서비스 개선 동의와 함께 합친다」는 사용자 결정 때문에 보류돼 있었다. pin `63adc5621`(약관 판 2026-10-17.1)이 같은 문구 수정을 서비스 개선 동의와 함께 넣었고, 지금 판은 2026-10-19.1 이다. 추가 13줄 중 12줄이 pin 에 있고, 빠진 1줄은 옛 `TERMS_VERSION` 값이다 |
| `e147ab08f` | 위 약관 브랜치 병합(충돌 해소 2파일) | 이력 전용 | da8dcd533 을 pin 이 대체했다 |
| `a0cdb381b` | integ 병합 — role-activity-b 충돌을 매니저 판으로 해소 | 이력 전용 | 충돌 해소 때 activity-b 쪽 함수들을 뺐다. pin 은 그 함수들(`build_activity_judge_llm` · `alternative_order` 등)을 이미 갖고 있다. 이 해소를 되살리면 pin 의 기능이 지워진다 |
| `ab3ffba98` · `dcbbd5a91` · `e0110d026` | integ 자동 병합 3개(dining · develop · lodging) | 이력 전용 | `--remerge-diff` 결과 0파일. 부모가 모두 pin 의 조상이다 |
| `e2d29b8b5` | 계획 읽기 8줄 묶음 나누기 WIP | 이력 전용(설계가 대체·폐기됨) | pin 의 같은 보고서(`2026-10-16_계획읽기_묶음나누기.md`)에 「2회차 합의(사용자 승인)로 걷어 냈다」고 적혀 있다. pin `502da503c` 가 「한 번에 보내고 조금씩 받기 · 한 계획은 한 모델 · 끝내 못 읽으면 접수 실패」로 바꿨다(`intake_reader.chunk_chars`). `eval/intake_chunking` 9파일은 pin 과 같은 blob. 옛 설계 전용 시험 `test_intake_reading_chunks.py` 와 가드레일 `travel.intake_reading` 은 되살리지 않는다 |
| `382650d10` | 백업 가지 b(미커밋 변경 96파일) | 이력 전용 | 86파일이 pin 과 같은 blob. 나머지 9개는 추가된 줄이 pin 에 모두 있다. `wiki/handoff/index.md` 만 0.75 인데, 같은 6주차 항목이 다른 문구로 pin 에 있다. `.agents/skills/source-command-resume-model-queue/SKILL.md` 는 pin 에 없지만 원본 작업 폴더에 같은 blob 이 untracked 로 있다 |
| `29eecd500` | 백업 가지 a(911파일) | **보류** | b 가지와 내용이 같고, 여기에 삭제 815개(final_project_sample 718 · datasets 63 · cs/legacy 12 등)가 더 있다. 1분 뒤 b 가지를 삭제 없이 다시 만든 것으로 보아, 이 삭제는 당시 작업 사본에 파일이 없었던 탓으로 보인다(확정 아님). 삭제의 뜻이 정해지지 않았으므로 적용하지 않는다. sample 은 현재 규칙상 참고 구현으로 남겨 두는 대상이다 |

## 통합 후보

| ID | 내용 | 런타임 영향 | 상태 |
|---|---|---|---|
| **C1** | `988a7eda1` 의 `tests/e2e/test_customer_notice_admin_switch.py` + `wiki/external/customer-notice-controls.md` | 없음(시험·문서만) | pin 기준 `git diff --binary` 로 만들었고 `diff --check` 를 통과했다. 패치: [cand2_988a_tests_doc.patch](../evidence/2026-10-27_finalspace-bundle-reclassification/cand2_988a_tests_doc.patch)(sha256 `ac7962f3…dfe36e`, 2파일 +38). 시험이 쓰는 fixture(`test_trip_api.api` · `test_web_guard._client`), `/admin/limits` 경로, 저장소 기본값 `false` 가 pin 에 있는 것은 확인했다. **실행은 안 했다** — e2e 는 공유 Postgres 에 테넌트 행을 쓰기 때문이다. 넣기 전에 격리 DB 에서 실행하고, wiki 색인에 연결할지 정해야 한다 |
| C2 | `.agents/skills/source-command-resume-model-queue/SKILL.md` | 없음 | 원본 작업 폴더에 untracked 로 이미 있다. 커밋할지는 사용자가 정한다 |
| C3 | `eval/intake_chunking/results/2026-10-16/적용위치_선택.svg` | 없음 | 폐기된 설계의 측정 그림이다. 기록으로 남길지만 정하면 된다 |

## 증거

- [per_file.json](../evidence/2026-10-27_finalspace-bundle-reclassification/per_file.json) — 1,056행. 커밋 · 부모 · pin · 원본 작업 폴더 blob 과 상태(`==commit` · `==commit(eol)` · `==parent` · `diverged` · `absent`), 추가 줄의 pin · 작업 폴더 포함률. 소스 본문과 비밀값은 넣지 않았다(경로 검사 결과 비밀 파일은 `final_project_sample/.env.example` 1개뿐이며 내용은 출력하지 않았다).
- [classification.json](../evidence/2026-10-27_finalspace-bundle-reclassification/classification.json) — 커밋 11개의 분류 · 이유 · 후보.
- 줄 포함률은 4글자 이상 줄의 집합 포함 여부로 셌다. 값이 같지 않다는 것만으로는 기능이 빠졌다고 판정하지 않았고, `diverged` 행은 호출부와 후속 보고서로 다시 확인했다.

## 한계

- 시험·서비스·DB 실행: 0건. 정적 대조만 했다.
- 원본 작업 폴더의 커밋 안 된 변경 1,155줄은 이 커밋들과 겹치는 경로만 hash 로 대조했다. 그 밖의 의미는 이번 범위가 아니다.
- 커밋 · push · 원본 refs/index 변경: 0. 새로 만든 파일은 이 보고서와 evidence 폴더 하나뿐이다(색인 · 인계 목차 · CLAUDE/AGENTS 는 고치지 않았다).
