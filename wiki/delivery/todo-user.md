---
type: guide
title: 사용자 실행 시트
description: AI가 준비를 끝내 둔 것. 사용자는 순서대로 실행하거나 고르기만 한다
status: draft
tags: [governance, documentation]
owners: [human:미배정]
domain: commerce
---

# 사용자 실행 시트

`[실측]` 2026-09-06. **AI가 할 수 있는 건 다 해 뒀다.** 명령은 **PowerShell 기준**이다(`&&`와 `*.patch` 확장이 안 되는 Windows PowerShell 5.1에서 그대로 붙여 넣어도 된다). Git Bash를 쓰면 아래 `bash` 블록을 쓴다. 아래는 사람이 실행하거나 결정해야만 넘어가는 것들이다. 위에서부터 순서대로 한다. 끝난 줄은 `[x]`로 바꾼다.

## 1. 푸시 — 로컬 커밋 146건

`role-core1` 브랜치가 `origin/role-core1`보다 **146 커밋** 앞서 있다(2026-09-06 03:40 기준). 다른 세션이 같은 브랜치에 커밋 중이라 늦을수록 충돌 위험이 커진다.

- [ ] 실행 전 확인 — 남의 미커밋 파일은 건드리지 않는다. `git status`에 보이는 `final_project_cs/CLAUDE.md`·`feedback.py`·`tests/unit/voc/*`·pptx는 다른 세션 작업이라 **스테이징하지 않는다**

```bash
git push origin role-core1
```

거부되면(non-fast-forward) 억지로 밀지 말고 이렇게 한다.

```powershell
git pull --rebase origin role-core1; if ($?) { python program/scripts/check_wiki.py }; if ($?) { git push origin role-core1 }
```

## 2. 원본 저장소 수정 — 패치 6장

원본 문서는 AI가 직접 안 고친다는 기준이라 **`program/patches/2026-09-06/`에 패치로 만들어 뒀다.** 여섯 장 전부 `git apply --check`를 통과했다. 저장소 루트에서 실행한다.

```powershell
Get-ChildItem program/patches/2026-09-06/*.patch | ForEach-Object { git apply $_.FullName }; git status --short
```

Git Bash라면 이렇게.

```bash
git apply program/patches/2026-09-06/*.patch && git status --short
```

| 패치 | 무엇을 고치나 | 근거 |
|---|---|---|
| `01_research_index` | 루트 `CLAUDE.md`가 정본이라 가리키는 "현재 기준 사실" 표를 `research/index.md`에 되살리고, 죽은 링크 `migration-scope.md` → `migration-scope/index.md` | [review-policy.md](../governance/review-policy.md) |
| `02_coupang_docs_readme` | "선택자는 전부 이 자료에서" 문구에 5.4.1 이후 목록은 DOM을 안 쓴다는 주의 | [coupang-extension.md](../../datasets/wiki/coupang-extension.md) |
| `03_nextdata_ref_readme` | 참고판 README 제목을 현행과 구분하고, 설치 경로가 자기 폴더를 가리키게 | 동 |
| `04_data_go_kr_report` | "`processed/`·`scripts/` 없음"이 낡았다 — 근거 사례 2종(53·89건)이 있고 스크립트가 `processed/` 안에 있다 | [catalog.md](../../datasets/wiki/catalog.md) |
| `05_dod_evidence_stale_notes` | DoD evidence 9건(02·14·20·24·06·21·13·08·22)의 판정 줄 아래에 "2026-09-06 낡음 확인" 한 단락씩. 본문은 안 건드린다 | [dod-evidence-drift.md](../../final_project_cs/wiki/quality/dod-evidence-drift.md) |
| `06_gitignore_sample_wiki` | `.gitignore`의 `final_project_sample/`이 `final_project_sample/wiki/`(33개 파일)까지 무시하던 것을 예외로. 적용 후 `git add final_project_sample/wiki`가 된다 | [open-items.md](open-items.md) |

- [ ] 적용했으면 검증하고 커밋한다

```powershell
python program/scripts/check_wiki.py
git add program/research/index.md datasets/commerce/coupang_order_history/docs/README.md datasets/commerce/coupang_order_history/scripts/extension_nextdata_ref/README.md datasets/voc/data_go_kr_consumer_complaints/REPORT.md final_project_cs/wiki/records/evidence .gitignore final_project_sample/wiki
git commit -m "docs: 2026-09-06 wiki 대조로 찾은 원본 낡음 6건 반영 + sample wiki 추적 시작"
```

`06`이 싫으면(sample wiki를 `final_project_sample` 저장소로 옮기는 쪽을 택하면) 그 패치만 빼고 적용하고, `git add`에서 `.gitignore`와 `final_project_sample/wiki`를 뺀다.

```powershell
Get-ChildItem program/patches/2026-09-06/*.patch | Where-Object { $_.Name -notlike "06_*" } | ForEach-Object { git apply $_.FullName }
```

## 3. 결정 — 고르기만 하면 AI가 문서에 반영한다

답을 이 파일에 적거나 채팅으로 말하면 된다. **"1번은 A"** 식이면 충분하다.

| # | 물음 | 선택지 | 정하면 바뀌는 곳 |
|---|---|---|---|
| 1 | ~~wiki를 어디에 놓나~~ | **A로 정함 (09-06)** | [D-012](../decisions/D-012-cutover-timing.md) |
| 2 | ~~Return & Refund~~ | **A Mock 유지 (09-06)** — 코드가 `Mock-only`라 cs에 만들어진 게 없었다 | [scope-verdicts.md](scope-verdicts.md) |
| 3 | ~~중앙 설정 저장소~~ | **정함 (09-06)** — cs로 안 가져간다. 별도 프로젝트로 분리, 붙인다면 UI 프로젝트 | [D-007](../decisions/D-007-central-config-store.md) |
| 4 | ~~Composer~~ | **정함 (09-06)** — 운영자 API는 스위치·생성·삭제만. 통째 교체는 관리자 scope로 내려 설치·복원용. **이력 표 + 이전 revision 복원을 같이 만든다.** → sample 구현(09-06) + **cs 복사본 제거·패키지 주입 완료(코드 세션 `f2319aa`)** | [D-011](../decisions/D-011-composer-v3-gap.md) |
| 5 | ~~v8 병합 시점~~ | **폐기 (09-06)** — **v9 판올림 완료** (`program/plan/A-COP_구현계획서_v9.md`, v8은 archive). cs `CLAUDE.md`는 담당 세션이 v9로 고침(`6bec5d9`) | [open-items.md](open-items.md) |
| 6 | ~~`research/index.md` 범위 (B-1)~~ | **B 제외로 정함 (09-06)** | 동 |
| 7 | ~~골든셋 `persona` 필드 담당~~ | **역할로 정함 (09-06)** — 검증 & 프론트 담당. 이름은 팀 재편 뒤 | [golden-set.md](../evaluation/golden-set.md) |

강사 확인 둘은 **사용자가 정리했다 (09-06).**

- [x] **sLLM 파인튜닝이 6팀 필수인가** — 필수 여부와 무관하게 **파인튜닝은 계속 시도하는 트랙**으로 간다. 진척이 있으면 적용하고, 결과가 나쁘면 나쁘다고 보고한다 → [timeline.md](timeline.md)
- [x] **3W 산출물 "학습한 ML/DL 모델"** — 지금까지의 학습 결과서와 체크포인트(stage3 v9)를 있는 그대로 낸다. 임베딩·리랭커 파인튜닝은 이후 후보

## 4. wiki 저장소 전환 — **완료 (2026-09-07)**

사용자 호출로 전환했다. 상세는 [D-012](../decisions/D-012-cutover-timing.md) "전환 완료" 절. 아래는 그 전 기록이다.

### (전환 전 기록)

문서 쪽 준비는 끝났다(대조 완료 · 검사 통과 · 결정 완료). **도구 쪽은 아니다** — `[실측 2026-09-07]` `cutover_rewrite.py`는 계획만 내고 실제 이동·링크 재계산이 없다. `check_wiki.py`도 `program/` 경로 고정. 전환 전에 이 둘을 구현해야 한다(문서 세션 몫, 반나절). 무엇이 바뀌는지는 지금도 볼 수 있다.

```bash
python program/scripts/cutover_rewrite.py --layout wiki
```

- [x] 3-1을 정했다 — `<저장소>/wiki/`
- [x] 위 dry-run 출력을 봤다
- [x] 채팅에 **"전환해"** — 그러면 AI가 가드를 풀고 `--apply`, 경로 320곳 재작성, `CLAUDE.md` 진입점 한 줄, 검사 4(v8 ↔ wiki)까지 한 번에 한다. 그 전엔 절대 안 한다 → [cutover.md](../governance/cutover.md)

## 5. 네이버 주문 4건 누락 — 사용자 지시로 넘어간다 (2026-09-06)

사용자가 "저번에 수정한 걸로 기억한다"고 해서 이 항목은 닫는다. `[미확보]` 저장소의 `naver_order_history/REPORT.md` "알려진 문제"는 아직 68/72로 적혀 있어, 수정본이 다른 곳에 있거나 REPORT가 낡은 것이다 — 다음에 그 REPORT를 재생성할 때 같이 본다. 아래 절차는 다시 필요해질 때를 위해 남긴다.

- [ ] 네이버페이 주문 목록에서 **링크 없는 주문(취소·종료 등)이 보이는 페이지**를 연다
- [ ] 개발자 도구 → Elements → `<html>` 우클릭 → Copy → **Copy outerHTML**
- [ ] `datasets/commerce/naver_order_history/raw/_dom_2026-09-XX.html`로 저장한다 (`raw/`는 git 무시 대상이라 개인정보가 올라가지 않는다)
- [ ] 채팅에 파일 경로를 말한다 → AI가 식별 방법을 정하고 크롤러 수정안을 낸다 → [scraper-notes.md](../../datasets/wiki/scraper-notes.md)

## 6. 그 밖에 보고만 받으면 되는 것

| 항목 | 상태 |
|---|---|
| 유지 문서 대조 | **끝** — 18차까지, 잔여 0 → [coverage-2026-09.md](../governance/migration-scope/coverage-2026-09.md) |
| 검사기 | `check_wiki.py` 통과 · 242문서 |
| DoD-01 원본 v4 hash 판정 | **닫힘 (09-06 확인)** — evidence `DoD-01_v4원본_hash_불변.md`에 기준 hash(`b675556cf4d72e64…`, 21,790 bytes, 2026-08-12)가 있고 **지금 파일이 그 값과 일치한다**. `[재확인 2026-09-09]` 그 파일은 `program/plan/.archive/보존본_v5-v8_2026-09-09.zip` 안으로 들어갔지만 **풀지 않고도 대조된다** — `sha256 = b675556cf4d72e64…`, 21,790 bytes 그대로다. 확인: `python -c "import zipfile,hashlib;print(hashlib.sha256(zipfile.ZipFile('program/plan/.archive/보존본_v5-v8_2026-09-09.zip').read('A-COP_구현계획서(4).md')).hexdigest())"`. 08-20 "판정 불가"는 evidence를 안 본 것 |
| 추적 영상 mp4 넷 | **닫힘 (09-06 확인)** — 넷은 옛 판이 아니라 **용도가 다른 넷**이다: `추적`(그림 17장 crossfade), `추적_유튜브`(자막·챕터·썸네일판, 리포트 대상), `움직임`(케이스 하나가 프레임마다 움직이는 애니메이션), `낱장`(화면과 같은 배치의 애니메이션). 각각 만드는 스크립트가 따로 있고 `*.mp4`는 git 무시. 지울 것 없음 |

## 관계

- [open-items.md](open-items.md) — 전체 열린 항목
- [../decisions/D-012-cutover-timing.md](../decisions/D-012-cutover-timing.md) — 전환
- [../governance/cutover.md](../governance/cutover.md) — 전환 조건
