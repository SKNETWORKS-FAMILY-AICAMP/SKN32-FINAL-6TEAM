---
type: plan
title: 열린 항목
description: 아직 안 끝난 일과 미확인 사항. 완료된 것은 여기 없다
status: draft
tags: [release]
owners: [human:미배정]
---

# 열린 항목

`[실측]` `A-COP_남은작업_인수인계.md`(2026-08-24 작성)에서 **살아 있는 것만** 추출.

**완료된 것은 안 적는다.** 원본은 완료 항목까지 다 담아서 무엇이 남았는지 찾기 어려웠다.

## 사람이 해야 하는 것

실행 순서와 명령은 [todo-user.md](todo-user.md)에 있다. 여기는 목록이다.

| 항목 | 왜 AI가 안 하나 |
|---|---|
| `git push -u origin workspace` | **AI 세션은 푸시를 실행하지 않는다** |
| ~~**★ wiki 저장소 전환**~~ | **닫힘 — 이미 실행됐다.** `[실측 2026-09-07]` 사용자 호출로 같은 날 243개 이동(`d976932`). 이 줄은 실행 뒤에도 "부르면 실행"으로 남아 있었다 → [D-012](../decisions/D-012-cutover-timing.md) |

## 미확인

`[미확보]` 정직하게 적는다.

| 항목 | 상태 |
|---|---|
| (지금 미확인 항목 없음) | 아래 「확인 완료로 닫은 것」 참고 |

## 확인 완료로 닫은 것

| 항목 | 결과 |
|---|---|
| VOC 데이터 전처리 8종 | **2026-09-01 전부 완료** |
| `implementation_ref` allowlist 제한 | **확인됨.** `KNOWN_IMPLEMENTATION_REFS`로 코드에 있고 Composer HTTP 경로에만 적용 |
| Composer 범위 재검토 | → [D-CS-001](../../final_project_cs/wiki/decisions/D-CS-001-composer-ui-removal.md) 외 Composer 계열 결정 |
| **v2 계약 문서 — 네 가지를 하나로 맞추기** | **2026-09-06 닫음.** 맞춘 게 아니라 **구현을 하나로 만들어** 맞출 것이 없게 했다 — Composer 구현이 패키지 `acop_composer` 하나뿐이고 cs·sample 이 각자 호스트 어댑터로 자기 것만 넘긴다(v9 §8-D). 실측 대조 ↓ |
| **UI가 import할 패키지 이름** | **2026-09-06 확정 확인: `acop_composer_ui`.** 콘솔 `console/composer.py:26` 이 실제로 이것을 import 하고 설치돼 있다(`final_project_sample/packages/acop_composer_ui/`). 대상 코드·스키마를 안 끌어오는 것은 게이트가 지킨다(`tests/architecture/test_composer_ui_package_boundary.py`) |

### v2 계약 네 항목 실측 대조 (2026-09-06)

| 맞춰야 했던 것 | cs | sample |
|---|---|---|
| endpoint 이름 | **같은 패키지가 정의한다** — `/apply` `/catalog` `/changes` `/current` `/restore` `/revisions` `/toggle` `/validate` | 동일(같은 코드) |
| `config_revision` | 계약 **1.1** · `config_revision`·`active_revision`·`desired_revision`·`reload_state`·`reload_error` | 동일 |
| 인증 scope | `composer:{read,validate,write,admin}` · `ops:{introspect,reload}` | 동일 |
| 감사 필드 | **같은 패키지가 쓴다** — `actor`·`changed_fields`·`correlation_id`·`event`·`operation`·`resource_type`·`instance_id`·`previous_revision`·`revision`·`reason`·`subject`·`timestamp`·`idempotency_key`·`implementation_id`·`result` | 동일(같은 코드) |

★`revision` **형식**만 일부러 다르다 — cs 는 sha256 64자, sample 은 12자. 맞추면
기존에 발급된 `base_revision` 이 전부 어긋나 저장이 409 로 튕긴다. revision 은 그
대상 안에서만 비교되므로 형식이 달라도 되고, "통일" 은 그 자체로 가치가 아니다.

★`cs 안에 자기 composer 라우터가 있나: False` — 사본이 없으므로 **갈라질 자리가
없다.** "두 사본을 계속 같게 유지한다" 는 지킬 수 없는 약속이었고, 실제로
2026-09-06 이전에 이미 갈라져 있었다(cs 4개 / sample 8개).

근거: `final_project_cs/docs/reports/2026-09-06_Composer를_패키지로_들어냈다.md`,
계약 `final_project_cs/docs/handoff/13`·`14`.
| **쿠팡 배송이력 5건 중 4건만 수집** | **★ [2026-09-04] 확인됨 — 정상 동작.** `preprocess_stats.json`을 열어 보니 8건 중 취소 3건(배송 자체 없음) 제외 5건 중 1건이 송장번호 미기재. 데이터 결손 아님 → [`../../datasets/wiki/scraper-notes.md`](../../datasets/wiki/scraper-notes.md) |

## 문서 쪽 열린 항목

| 항목 | 어디 |
|---|---|
| **Baseline B 가 Proposed 를 이긴다 — 방어 지표 비교가 없다** `[실측 2026-09-07]` 같은 실행에서 judge pass 가 B 46.8% · Proposed 11.6% 이고, B 는 2.5배 싸고 4.8배 빠르다. **"단순 RAG 보다 낫다"를 지금 산출물로는 말할 수 없다.** Proposed 의 값어치(승인 경계·기권·Action 제안)는 judge 총점이 아니라 방어 지표가 재는데, **세 군을 같은 실행에서 방어 지표로 비교한 산출물이 없다.** 그 측정이 먼저다 | [../evaluation/index.md](../evaluation/index.md) · [../evaluation/metrics.md](../evaluation/metrics.md) |
| **cs 소유 문서 둘이 outbox 옛 제약을 싣고 있다 — 코드 세션 몫** `[실측 2026-09-07]` 살아 있는 DB 는 `UNIQUE (tenant_id, topic, dedupe_key)` 인데(`outbox_tenant_topic_dedupe_key_key`), `docs/evidence/DoD-23_consumer_idempotency.md:33` 은 옛 제약을 **통과 근거로** 들고 있고 `docs/handoff/02_DB_스키마.md:119` 는 001 DDL 만 싣고 003 개정을 안 싣는다. `tenant_id` 누락은 테넌트끼리 dedupe 충돌을 내는 **보안급**이라 DoD-12 결함으로 기록돼 있다. wiki 쪽 세 곳(`idempotency.md`·`data/migrations.md`·`data/schema/index.md`)은 정정했다 | [../../final_project_cs/wiki/actions/outbox.md](../../final_project_cs/wiki/actions/outbox.md) |
| **wiki 스키마 스니펫이 실제 DB 와 어긋나도 아무도 안 잡는다** `[실측 2026-09-07]` outbox 제약이 문서 다섯 곳에 퍼져 있었고 003 마이그레이션 뒤에도 세 곳이 옛 값을 유지했다. **파일 이름만 새것으로 바꾸고 내용은 안 바꾼 자리도 있었다.** `check_wiki.py` 는 링크와 tag 를 보지 DDL 을 안 본다. `pg_constraint` 를 읽어 wiki 의 `UNIQUE(...)` 스니펫과 대조하는 검사가 필요하다 | [../../final_project_cs/wiki/quality/blind-spots.md](../../final_project_cs/wiki/quality/blind-spots.md) |
| ~~**이관 — 남은 것은 대조 38건**~~ **닫힘 (2026-09-07).** 39건을 절 단위로 훑어 격차 넷을 찾아 반영했다(→ [coverage-2026-09.md](../governance/migration-scope/coverage-2026-09.md) 19차). 경위: `[실측 2026-09-07]` 이 줄은 "사람 판정 79" 로 적혀 있었으나 **두 숫자를 섞은 것이었다.** 사람 판정은 2026-09-03 에 198/198 로 끝났다. 「판정필요 79」는 스크립트의 **초안** 판정이고 그마저 지금 다시 돌리면 68 이다(분모가 747→760 으로 늘었다). 실제로 남은 일은 **대조필요 38건** — "옮기기로 정했다"와 "옮겼다"는 다르고, 대조해 본 9번 중 9번에서 빠진 내용이 나왔다 | [../governance/migration-scope/status.md](../governance/migration-scope/status.md) · [../governance/migration-scope/index.md](../governance/migration-scope/index.md) |
| **골든셋 사람 라벨 24건 — 두 사람이 독립으로 채워야 한다** `[실측 2026-09-07]` 확인 결과 **2인은커녕 1인 라벨링도 안 됐다.** `holdout_human_labels_template.jsonl` 24행의 `labeler`가 전부 `None`, `human_label` 다섯 축이 전부 `null`. judge 프롬프트도 "2-person independent labeling was unavailable"라 적어 두었다. **이것 때문에 `eval/stats/agreement.py`가 재는 DoD-15/17 차단 항목(judge↔사람 일치율)을 평가할 수 없다** — 스크립트는 있는데 입력이 없다. 템플릿·집계 도구는 준비돼 있고 채우기만 하면 된다. 담당은 검증 & 프론트. `[실측 2026-09-07]` **사람이 볼 순서는 정해 뒀다** — 같은 24건을 모델로 두 번 더 독립 채점해 judge 와 어긋나는 6건을 골라냈다. 모델끼리의 일치라 이 항목을 닫지는 못한다 | [../evaluation/judge-second-opinion.md](../evaluation/judge-second-opinion.md) · [../evaluation/golden-set.md](../evaluation/golden-set.md) |
| ~~`final_project_sample/wiki/`가 git에 없다~~ **닫힘 — `.gitignore` 에 `!program/final_project_sample/` 부정 규칙이 들어갔다(2026-09-06). `[실측 2026-09-07]` 33개 전부 추적 중이고 미추적 0.** | 루트 `.gitignore:150~153` |
| ~~Team 경계 불변식 3개 자동화~~ **닫힘 — `INV-CS-ARCH-001·002·003` 셋 다 `automated` 이고 테스트가 실재한다.** `[실측 2026-09-07]` `tests/architecture/test_basement_is_domain_free.py` · `tests/contract/test_core_isolation.py` 65건 통과 | [`quality/invariants.md`](../../final_project_cs/wiki/quality/invariants.md) |
| ~~`final_project_cs/CLAUDE.md`가 v8을 가리킨다~~ **닫힘 — 담당 세션이 v9로 고침(`6bec5d9`).** `final_project_sample/CLAUDE.md`는 그 저장소 쪽 미커밋 수정 중이라 `[미확보]` — 2026-09-06 v9 판올림(루트 `CLAUDE.md`·`research/index.md`·드리프트 검사기는 갱신됨). 두 파일은 다른 세션이 수정 중이라 이 세션이 안 건드렸다. `v8` → `v9`, 경로 `plan/A-COP_구현계획서_v9.md` | [timeline.md](timeline.md) |
| ~~cs 안의 Composer 자체 복사본 셋~~ **닫힘 — 코드 세션이 들어냈고(`f2319aa`, 400줄 삭제, `app/composer_host.py`로 패키지에 주입, `composer:admin` 추가), wiki 갱신도 끝났다.** `[실측 2026-09-07]` 옛 파일 셋 전부 없음, `composer_host.py`·`entrypoint.py` 실재. `f2319aa`를 아는 페이지 6개 + `external/rest-api.md`에 "고객 릴리즈 앱엔 `/composer/*`가 아예 없다"를 추가했다 | [D-006](../decisions/D-006-composer-ownership.md) · [D-011](../decisions/D-011-composer-v3-gap.md) |
| ~~DoD evidence 9건이 낡았다~~ **닫힘 (2026-09-07).** 낡은 일곱(02·14·20·24·21·13·08)은 이름·수치·경로를 현행으로 고쳤고(`7373b67`), 다시 재야 했던 둘도 cs 에서 재측정했다 — **DoD-22**는 `tests/contract/test_team_tool_discipline.py` 10건을 새로 써서 사라진 근거를 복구했고, **DoD-06**은 cs 코퍼스로 다시 재 문서 25 / 청크 306 을 확인했다 | [`quality/dod-evidence-drift.md`](../../final_project_cs/wiki/quality/dod-evidence-drift.md) |
| ~~`program/research/index.md` 둘~~ **닫힘 (2026-09-07).** 표는 09-06 에 되살아났고 `migration-scope` 링크도 폴더형(`migration-scope/index.md`)으로 고쳐져 있었다. 남아 있던 진짜 문제는 **표 내용이 루트 `CLAUDE.md` 와 어긋난 것** — Composer 행 하나가 루트에만, DoD 행의 "evidence 9건 낡음" 이 research 에만 빠져 있었다. 맞추고 `check_drift.py` 검사 4 로 두 표를 행·값 대조하게 했다(`1a4fc82`) | [../governance/review-policy.md](../governance/review-policy.md) |
| ~~`cases.py`의 주석이 낡았다~~ **닫힘 (2026-09-07).** `[실측]` "sweeper 는 아직 없다" 문구가 소스에서 사라졌다. 코드 세션이 sweeper 쪽을 손보면서(`7192fee` — `errored` 를 세기만 하고 아무에게도 안 알리던 결함) 같이 정리한 것으로 보인다 | [`quality/guardrails.md`](../../final_project_cs/wiki/quality/guardrails.md) §2026-09-03 sweeper |

## 측정 대기

`[미확보]` 반나절~하루면 되는데 결론을 크게 바꾸는 것들.

| 순위 | 무엇 | 무엇이 흔들리나 | 시간 |
|---|---|---|---|
| ~~1~~ | **3B 모델 VRAM 상한** — **해결** | 12GB 확정(세션 1 실측) → [../business/gpu-limits.md](../business/gpu-limits.md). **처리량(tok/s)은 아직** | 반나절 |
| **2** | **검토·승인 1건 소요시간** | **72% 절감이 여기 달려 있다.** 도구 설치 완료 → [../business/measure-review-time.md](../business/measure-review-time.md) | **30분** |
| ~~2~~ | **오류 1건당 손실** — **일부 측정** | 분쟁 8건 실측. 중앙값 5만 · 최대 152.6만 → [../business/error-cost.md](../business/error-cost.md) | 완료 |
| ~~3~~ | ~~Baseline A·B 재측정~~ **측정은 끝났다 (2026-09-06)** | `[실측 2026-09-07]` 2026-09-06 judge v3 재기준선이 A·B·Proposed 를 216건씩 같은 실행으로 돌려 놨다. 비용·지연·judge 점수 전부 있다 → [../evaluation/index.md](../evaluation/index.md). ★**그런데 결과가 기대와 반대다** — B 가 pass 46.8% 로 Proposed(11.6%)를 이긴다. 그래서 "단순 LLM보다 낫다"는 **여전히 못 말한다.** 막는 것이 측정 부재에서 **방어 지표 비교 부재**로 바뀌었다 | 완료 |
| 4 | **DoD-28 재측정** | **0% 가 모델 성능이 아니었다** → [../evaluation/dod28-rerun.md](../evaluation/dod28-rerun.md) | D-010 대기 |

→ [../business/index.md](../business/index.md)

## ★ [2026-09-03] 미측정을 없애는 절차

`[실측]` `A-COP_페인포인트_페르소나_설계.md` §8 에서 이관. **이 절이 빠져 있었다.**

**`[추정]`·`[미확보]` 를 없애는 방법이 이미 정해져 있었다.** 지금 있는 데이터로 대부분 채울 수 있다.

### 1단계 — 있는 데이터로 채운다

| 채울 것 | 쓸 데이터 |
|---|---|
| ~~골든셋 페르소나 배분~~ **완료** | [personas.md](../product/personas.md) 재검증. 정미라 행 18→**28건(38.9%)** 정정 |
| ~~실제 문의 유형 분포~~ **확인 결과: 못 구한다** | [golden-set.md](../evaluation/golden-set.md). **자체 정정** — 처음엔 aihub_30716 이 order 40% 라고 적었는데 틀렸다. `sample_per_group` 층화표집이라 표본 자체가 균등하다 |
| ~~커머스 문의 유형~~ **동일 사유로 못 구한다** | `aihub_102_smb_order_qa` 도 `sample_per_group: 400` 층화표집 (stats.json 확인). 둘 다 자연 빈도가 아니다 |
| ~~오류 비용의 실제 사례~~ **완료** | [error-cost.md](../business/error-cost.md) |
| ~~감정 축 검증~~ **확인 결과: 못 한다** | [golden-set.md](../evaluation/golden-set.md). `aihub_71603` 은 제품 만족도(긍정/부정)를 재고 골든셋은 상담 중 감정·불확실성을 잰다 — **다른 축이라 대조 불가** |
| ~~`cost/case` 실측~~ **완료 (2026-09-07)** | 새로 돌리지 않았다 — 2026-09-06 judge v3 재기준선 산출물에 행마다 `cost_usd`·`latency_ms`·토큰이 이미 있었다. 세 군 같은 실행: A 0.33원 · B 1.20원 · Proposed 3.03원 (환율 1,400원 고정) → [../evaluation/index.md](../evaluation/index.md) |

**네 번째가 특히 중요하다.** **분쟁 조정까지 간 사례집**이므로 "오류 1건이 얼마나 커지는지"의 실제 근거가 된다.

> **지어낸 숫자를 안 써도 된다.**

`[실측]` 그 데이터는 이미 있다. → [../../datasets/wiki/source-selection.md](../../datasets/wiki/source-selection.md)

### 감정 축 검증이 뭘 가리나

**worried/confused 50% 가 골든셋 특성인지 일반 특성인지**를 판별한다.

**골든셋만의 성질이면 그 50% 로 제품을 설명하면 안 된다.**

## 아직 안 정한 것 셋

`[실측]` 같은 문서 §9.

| 항목 | 판단 |
|---|---|
| ~~v8 병합 시점~~ | **폐기 (2026-09-06)** — 병합 대신 **v9로 판올림**해서 진행한다. 판올림 이후의 정본은 wiki다 |
| 골든셋 `persona` 필드 추가 담당 | **역할로 정함 (2026-09-06)** — [roles.md](roles.md)의 검증 & 프론트가 golden/holdout을 관리하므로 그 담당. 이름은 팀 재편 뒤에 |
| 축 1 공개 통계 확보 여부 | 확보 시도 / 미확보 유지 |
| ~~sLLM 파인튜닝이 6팀 필수인가~~ | **닫힘 (09-06, 사용자)** — 필수 여부와 무관하게 파인튜닝은 계속 시도하는 트랙 → [timeline.md](timeline.md) |
| ~~3W 산출물 "학습한 ML/DL 모델"에 무엇을 내나~~ | **닫힘 (09-06, 사용자)** — 지금까지의 학습 결과서·체크포인트(stage3 v9)를 있는 그대로 낸다. 임베딩·리랭커는 이후 후보 → [timeline.md](timeline.md) |

## [2026-09-03] 인수인계에서 남은 것

`[실측]` `A-COP_남은작업_인수인계.md` 에서 이관. **대부분 완료됐고 둘이 남았다.** (쿠팡 배송이력 항목은 2026-09-04 확인 완료로 닫혔다 — 위 표 참고)

| 항목 | 상태 |
|---|---|
| VOC 데이터 전처리 | **완료** (2026-09-01) |
| `implementation_ref` allowlist 제한 | **확인됨** — `KNOWN_IMPLEMENTATION_REFS`. Composer HTTP 경로에만 적용 |
| ~~네이버 주문 4건 누락~~ | **닫힘 (09-06, 사용자)** — 이미 수정했다고 정리. `naver_order_history/REPORT.md`의 68/72 문구만 낡았다 → [../../datasets/wiki/scraper-notes.md](../../datasets/wiki/scraper-notes.md) |
| **v2 계약 문서 정합** | `[미확보]` endpoint 이름·`config_revision`·인증 scope·감사 필드를 **하나로 맞춰야 한다** → [D-011](../decisions/D-011-composer-v3-gap.md) |
| **UI 가 import 할 패키지 이름** | `[미확보]` 아직 확정 안 됨 |

**세 번째가 D-011 과 같은 문제다.** 계약이 둘로 갈려 있어서 이름부터 안 맞는다.

## 원격 추적은 사람이 한다

`[실측]` 원본이 명시해 뒀다.

> **AI 세션은 푸시를 실행하지 않는다.** 사용자가 직접 실행한다.

**이 wiki 작업도 같다.** 커밋은 하되 푸시하지 않는다.

## ★ [2026-09-03] 정합성 점검이 남긴 미결 판단 둘

`[실측]` `program/research/_정합성_수정제안.md` 에서 이관. **A 묶음 6건은 적용됐고 B·C 가 미결로 남았다.**

### B-1. `research/index.md` 가 계획서·브리핑을 관리할 것인가

**충돌하는 두 원칙이 있다.**

| | |
|---|---|
| `index.md` 5행 | **"계획서·briefing·final_project 폴더는 이 정리의 대상이 아니다"** |
| 점검 권고 | **최신 문서군을 기준선에 기록하라** |
| 고르면 | 대가 |
|---|---|
| 포함 | **색인의 책임 범위가 넓어진다** |
| 제외 | **기준선 확인 정보가 `CLAUDE.md` 등 다른 문서에만 남는다** |

`[실측]` 2026-09-03 확인 — `index.md` 에 그 문구가 없다.

**★ 2026-09-06 결정 — 제외.** `research/index.md`는 지금처럼 research 폴더만 관리하고, 계획서·브리핑 기준선은 루트 `CLAUDE.md`(와 판올림 뒤엔 wiki)가 맡는다. `index.md` 5행 원칙 그대로다.

### C-1. `CLAUDE.md` 기준선에 Composer v3 문서군을 넣을 것인가

`[실측]` 2026-09-03 확인 — **두 `CLAUDE.md` 어디에도 `Composer_v3_설계_토글전용` 이 없다.** 미결이다.

~~**이건 [D-011](../decisions/D-011-composer-v3-gap.md) 이 정해져야 결정된다**~~ → **D-011이 2026-09-06에 정해졌다**(토글 방식 채택, 통째 교체는 관리자 도구). 그러니 v3 문서군은 기준선에 들어가는 게 맞고, v9 판올림 때 `CLAUDE.md` 표에 넣는다.

## 관계

- [timeline.md](timeline.md) — 일정
- [dod.md](dod.md) — 완료 기준
- [../governance/migration-scope/index.md](../governance/migration-scope/index.md) — 문서 이관
