---
type: guide
title: 사용자 실행 시트
description: AI가 준비를 끝내 둔 것. 사용자는 순서대로 실행하거나 고르기만 한다
status: draft
tags: [governance, documentation]
owners: [human:미배정]
---

# 사용자 실행 시트

`[실측]` 2026-09-06. **AI가 할 수 있는 건 다 해 뒀다.** 아래는 사람이 실행하거나 결정해야만 넘어가는 것들이다. 위에서부터 순서대로 한다. 끝난 줄은 `[x]`로 바꾼다.

## 1. 푸시 — 로컬 커밋 146건

`role-core1` 브랜치가 `origin/role-core1`보다 **146 커밋** 앞서 있다(2026-09-06 03:40 기준). 다른 세션이 같은 브랜치에 커밋 중이라 늦을수록 충돌 위험이 커진다.

- [ ] 실행 전 확인 — 남의 미커밋 파일은 건드리지 않는다. `git status`에 보이는 `final_project_cs/CLAUDE.md`·`feedback.py`·`tests/unit/voc/*`·pptx는 다른 세션 작업이라 **스테이징하지 않는다**

```bash
git push origin role-core1
```

거부되면(non-fast-forward) 억지로 밀지 말고 이렇게 한다.

```bash
git pull --rebase origin role-core1 && python program/scripts/check_wiki.py && git push origin role-core1
```

## 2. 원본 저장소 수정 — 패치 6장

원본 문서는 AI가 직접 안 고친다는 기준이라 **`program/patches/2026-09-06/`에 패치로 만들어 뒀다.** 여섯 장 전부 `git apply --check`를 통과했다. 한 줄로 적용한다.

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
| `06_gitignore_sample_wiki` | `.gitignore`의 `final_project_sample/`이 `program/final_project_sample/wiki/`(33개 파일)까지 무시하던 것을 예외로. 적용 후 `git add program/final_project_sample/wiki`가 된다 | [open-items.md](open-items.md) |

- [ ] 적용했으면 검증하고 커밋한다

```bash
python program/scripts/check_wiki.py && git add program/research/index.md datasets/commerce/coupang_order_history/docs/README.md datasets/commerce/coupang_order_history/scripts/extension_nextdata_ref/README.md datasets/voc/data_go_kr_consumer_complaints/REPORT.md final_project_cs/docs/evidence/DoD-*.md .gitignore program/final_project_sample/wiki && git commit -m "docs: 2026-09-06 wiki 대조로 찾은 원본 낡음 6건 반영 + sample wiki 추적 시작"
```

`06`이 싫으면(sample wiki를 `final_project_sample` 저장소로 옮기는 쪽을 택하면) 그 패치만 빼고 `git apply` 한다. 그 경우 `program/final_project_sample/wiki/`를 그 저장소 안으로 옮기는 건 별도 작업이다.

## 3. 결정 — 고르기만 하면 AI가 문서에 반영한다

답을 이 파일에 적거나 채팅으로 말하면 된다. **"1번은 A"** 식이면 충분하다.

| # | 물음 | 선택지 | 정하면 바뀌는 곳 |
|---|---|---|---|
| 1 | **wiki를 어디에 놓나** | A `<저장소>/wiki/` (권고) · B `docs/wiki/` | [D-012](../decisions/D-012-cutover-timing.md) — 전환의 마지막 전제 |
| 2 | **Return & Refund** | A Mock 유지 · B LOCAL 승격(사유 코드·상태 전이 확인됐다는 뜻) | `CLAUDE.md` 표, golden 배분, [scope-verdicts.md](scope-verdicts.md) |
| 3 | **중앙 설정 저장소를 이번 기간에 하나** | A 안 한다 → 산출물에 "결정만, 착수 안 함" · B 한다 → 에픽 추가 | [D-007](../decisions/D-007-central-config-store.md), 스프린트 설계 |
| 4 | **Composer v3 채택** | A 구현을 v3에 맞춤 · B 설계를 현재 구현에 맞춤 · C 한시 병행 | [D-011](../decisions/D-011-composer-v3-gap.md) → 계약 문서 정합·패키지 이름·C-1 기준선이 줄줄이 풀린다 |
| 5 | **v8 병합 시점** | A 중간발표(09-15) 전 · B 후 | [open-items.md](open-items.md) |
| 6 | **`research/index.md`가 계획서·브리핑을 관리하나 (B-1)** | A 포함 · B 제외(지금처럼 `CLAUDE.md`에만) | 동 |
| 7 | **골든셋 `persona` 필드 담당** | 이름 하나 | [golden-set.md](../evaluation/golden-set.md) |

강사에게 물어야 하는 것 둘은 따로 있다.

- [ ] **sLLM 파인튜닝이 6팀 필수인가** — 시트 문구가 "3, 4번 팀"이라 불명 → [timeline.md](timeline.md)
- [ ] **3W 산출물 "학습한 ML/DL 모델"에 무엇을 내나** — 파인튜닝 미채택이면 LLM API만으론 안 채워진다

## 4. wiki 저장소 전환 — 3-1을 정한 뒤 부르면 한다

준비는 끝났다(문서 대조 22/22 · 검사 통과 · 미작성 링크 0). 스크립트는 지금 **dry-run만** 된다. 무엇이 바뀌는지 먼저 본다.

```bash
python program/scripts/cutover_rewrite.py --layout wiki
```

- [ ] 3-1을 정했다
- [ ] 위 dry-run 출력을 봤다
- [ ] 채팅에 **"전환해"** — 그러면 AI가 가드를 풀고 `--apply`, 경로 320곳 재작성, `CLAUDE.md` 진입점 한 줄, 검사 4(v8 ↔ wiki)까지 한 번에 한다. 그 전엔 절대 안 한다 → [cutover.md](../governance/cutover.md)

## 5. 네이버 주문 4건 누락 — 화면 하나만 떠 주면 된다

코드만으로는 못 고친다. **로그인 상태의 실제 DOM**이 필요하다.

- [ ] 네이버페이 주문 목록에서 **링크 없는 주문(취소·종료 등)이 보이는 페이지**를 연다
- [ ] 개발자 도구 → Elements → `<html>` 우클릭 → Copy → **Copy outerHTML**
- [ ] `datasets/commerce/naver_order_history/raw/_dom_2026-09-XX.html`로 저장한다 (`raw/`는 git 무시 대상이라 개인정보가 올라가지 않는다)
- [ ] 채팅에 파일 경로를 말한다 → AI가 식별 방법을 정하고 크롤러 수정안을 낸다 → [scraper-notes.md](../../datasets/wiki/scraper-notes.md)

## 6. 그 밖에 보고만 받으면 되는 것

| 항목 | 상태 |
|---|---|
| 유지 문서 대조 | **끝** — 18차까지, 잔여 0 → [coverage-2026-09.md](../governance/migration-scope/coverage-2026-09.md) |
| 검사기 | `check_wiki.py` 통과 · 242문서 |
| DoD-01 원본 v4 hash 판정 | `[미확보]` 기준 hash 확보 전엔 판정 불가 — 누가 갖고 있는지 모른다 |
| 추적 영상 mp4 넷 | `[미확보]` 리포트는 유튜브판 하나만 말한다. 나머지 셋을 지울지 말지 |

## 관계

- [open-items.md](open-items.md) — 전체 열린 항목
- [../decisions/D-012-cutover-timing.md](../decisions/D-012-cutover-timing.md) — 전환
- [../governance/cutover.md](../governance/cutover.md) — 전환 조건
