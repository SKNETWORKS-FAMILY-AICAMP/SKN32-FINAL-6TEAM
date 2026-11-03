---
type: report
title: 날짜 위험 2차 보완 격리 검증
description: 최신 팀 develop 위 날짜 의미와 재사용·웹 표시 회귀, 실제 실행과 한계
status: draft
domain: travel
---

# 날짜 위험 2차 보완

## 범위와 경위

- 기준: `325ba25d88c91ce97da61f2bda635e5888fe3b40`. 격리 경로: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/date_risk_325ba25_02`.
- 원본은 읽기 전용 archive만 수행했습니다(`GIT_OPTIONAL_LOCKS=0 git -C C:/_proj/파이널스페이스 archive ...`). checkout/reset/stash/index 수정·서비스·DB·배포·push는 수행하지 않았습니다.
- 담당/검토: 날짜 위험 구현 에이전트가 접수·웹을 함께 검토했습니다. 독립 검토 완료가 아닙니다. 현재 계약을 먼저 수정하고 기존 재사용·risk_panel 스위치를 유지했습니다. 검색kind·채팅·공지 파일 이식은 없습니다.
- [실측] 원인: 현재경보를 as_of_now만으로 거르며 기간 근거를 보지 않았고, too_early를 소스 장애와 함께 미확인으로 셌습니다. 재사용은 판 전체 시간만 확인하여 24시간·종료 경계 및 연쇄 수명 연장을 놓쳤습니다.

## 구현과 TDD

- deferred 없는 응답, 겹치는 통제 삭제, 표식 없는 현재 경보, 재사용 24시간 경계·원래 확인시간 만료·방문 종료·기존 날짜 의미 정규화 각각을 assertion RED로 재현한 뒤 최소 수정했습니다.
- 웹 decoder → 패널 → riskChecks 순서로 assertion RED/GREEN을 확인했습니다. problem과 실제 unknown은 표시하고 순수 날짜 보류만 개수/행에서 분리했습니다.
- 원래 travel 날짜 시험의 too_early unknown 기대는 새 계약에 맞췄으며 기존 재사용 시험은 유지했습니다.
- [실측] 집중 backend 48/48 = 100%. 초기 웹 전체 1,152/1,152 = 100%. 타입 검사에서 새 시험 fixture의 필수 stage_label/fatal/trip_id 누락 TS2352 1건을 발견해 수정했습니다. 수정 후 재검증/기준본 검사는 아래 최종 결과에 기록합니다.

## 환경과 실패 보존

- 전체 TAR 첫 추출 `_01`은 Windows 긴 경로에서 중단했습니다. `_02` 확장경로 추출은 디렉터리 메타데이터 설정에서 오류가 났으나 일반 파일 18,985개는 모두 존재했습니다. 별도 baseline `_03`은 일반 파일을 정규화된 확장경로로 추출·해시 대조합니다. 실패 사본/자료는 삭제하지 않았습니다.
- Python 3.14 ARM64의 psycopg-binary wheel 부재로 첫 설치 실패. 프로젝트 CI의 3.12 계열로 격리 CPython 3.12.15 x64와 venv `date_risk_env_312`를 마련해 고정 requirements 전체를 설치했습니다.
- 최초 pytest는 설정 8개 누락으로 setup error 5건이며 RED 증거가 아닙니다. 별도 `date_risk_pytest_runner.py`는 CI와 같은 모의 설정, 없는 DB 주소, 소켓 접속 금지를 적용하며 서비스/실DB에 접근하지 않습니다. 그 후 assertion 실패를 따로 기록했습니다.
- npm ci 성공. 초기 웹 RED 3종은 Node 26에서 실제 assertion 실패로 확인했습니다(런타임 오류 아님). npm node@24 설치는 preinstall 차단으로 node.exe 없음: 성공으로 세지 않았습니다. 전역 보안정책 변경 없이 공식 Node v24.22.1 ARM64 ZIP을 SHA256 `a0c807319fede24c4a0d8f84564c82a619bd313b16b10c007c383c2609e99171`로 확인·격리 추출하고 직접 `node.exe --version` → v24.22.1을 확인했습니다. 최종 웹 검사는 이 실행 파일을 사용합니다.
- 수정 전 백업: scratch `date_risk_backups_01`. 기존 파일을 통째로 이식하지 않았습니다.

## 최종 실행 결과

[실측 2026-10-24 08:19 UTC] 아래 수치는 서로 겹치는 묶음이며 합산하지 않습니다.

| 검사 | 결과 | 한계 |
|---|---|---|
| 날짜 위험 집중(확장 묶음 안 2파일) | 49/49 = 100% | 날짜 29 + 기존 travel 20, DB/실제 제공처 미사용 |
| 위험/예보/패널 스위치/대안 인증/현행 장소검색 7파일 | 135/135 = 100%, skip 0 | Starlette/AnyIO deprecated alias 경고 1개 |
| `tests/unit/intake` 전체 | 59/59 = 100%, skip 0 | 위 날짜 시험과 중복 |
| architecture·contract·security | 604/636 수집 = 94.97%; 실행 607 중 604 통과/3 실패, DB/live 29 deselected, skip 0 | 기준본과 수정본 모두 동일 3건 WinError 5. 전체 통과 아님 |
| 웹 전체 Vitest | 1,152/1,152 = 100%, 131 파일 | Node v24.22.1 |
| 웹 타입/린트/빌드 | 통과 | 타입 오류 1건은 이번 새 시험 fixture에서 발생했으며 수정 후 통과. 원본 팀 기준본 tsc도 0건 |
| 실제 Edge 모형 부품 브라우저 | 4/4 = 100% | 375/1280px × 패널 on/off. 실제 RiskPanel SSR+부품 CSS, 외부 요청 차단·file URL. 실제 접수 앱/실서버 E2E가 아님 |
| 수정 Python ruff F/E9 | 통과 | 지정 3파일 |

### 실패·중단을 숨기지 않은 기록

- 최초 확장 명령은 잘못 쓴 `tests/unit/intake/test_explicit_place_search.py` 때문에 exit 4, 시험 실행 0건입니다. 실제 대응 경로 `tests/unit/travel/test_explicit_place_search.py`를 찾아 수정했으며 17건을 위 135건에 포함했습니다. 이 실패는 기능 RED가 아닙니다.
- 최초 소켓 차단 runner가 Windows asyncio 내부 socketpair까지 차단하여 확장 135건 중 HTTP 시험 3건이 실패했습니다. 동일 runner로 기준본의 위험 대안/앱분리 45건을 실행하여 22건에서 같은 오류를 재현했습니다. 제품 코드를 완화하거나 시험을 빼지 않고, runner에서 **그 스레드의 OS socketpair 생성 중 loopback 연결만** 허용했습니다. 그 후 기준본 45/45, 수정본 확장 135/135 통과입니다. 앱 외부 연결 금지는 유지했습니다.
- 초기 넓은 묶음은 8개 진행 표시 후 장시간 정체하여 중단했습니다. 이 부분 결과를 통과로 세지 않습니다. runner 보완 뒤 intake 59건 및 gates 607건을 별도로 끝까지 실행했습니다.
- `-x` 관문은 처음 126건에서 runner 오류, 다음 170건에서 Git subprocess 오류로 중단되어 각각 이후가 미검증이었습니다. 이후 **-x 없이** 기준본·수정본 같은 636건을 수집, 같은 조건으로 607건을 끝까지 실행했습니다.
- 남은 실패 3건(양쪽 동일):
  - `tests/contract/test_api_key_file.py::test_the_real_key_file_is_ignored_by_git`
  - `tests/contract/test_api_key_file.py::test_the_template_itself_is_not_ignored`
  - `tests/security/test_no_infra_in_tracked_files.py::test_no_tracked_text_file_leaks_infrastructure`
  - 원인: Python subprocess의 `git` 실행이 `PermissionError: [WinError 5]`로 거부됩니다. archive 사본에는 Git 메타데이터도 없으므로 정상 Git 실행 가능한 독립 checkout에서 이 세 시험을 다시 해야 합니다. 응답 모사·시험 제외·보안정책 완화는 하지 않았습니다.
- 전체 `tests/unit`·실DB 통합/E2E·실제 외부 제공처·운영 화면은 이번 완료 범위가 아닙니다. 배포·push·원본 역복사도 하지 않았습니다.

### 재현 명령과 산출물

scratch 기준 공통 실행 파일:

```text
PY=date_risk_env_312/Scripts/python.exe
RUN=date_risk_pytest_runner.py
NODE=date_risk_node24_official/node-v24.22.1-win-arm64/node.exe
```

`final_project_cs` 작업 디렉터리에서 실제 실행한 최종 backend 명령(위 두 실행 파일은 절대경로 사용):

```text
PY RUN tests/unit/intake/test_intake_risks_trip_date.py tests/unit/travel/test_intake_risks.py tests/unit/travel/test_risk_report.py tests/unit/travel/test_trip_risk_panel_switch.py tests/unit/travel/test_risk_alternative_request.py tests/unit/travel/test_early_risk_notice.py tests/unit/travel/test_explicit_place_search.py -q --junitxml=../date-risk-backend-expanded-final.xml
PY RUN tests/unit/intake -q --junitxml=../date-risk-intake-all.xml
PY RUN tests/architecture tests/contract tests/security -m "not live and not db" -q --junitxml=../date-risk-backend-gates-complete.xml
```

기준본은 같은 명령에 `DATE_RISK_ROOT=<scratch>/date_risk_baseline_03`을 설정했습니다. 웹 작업 디렉터리는 `final_project_cs/frontend/apps/web`이며 실제 명령은 `NODE node_modules/eslint/bin/eslint.js .`, `NODE node_modules/typescript/bin/tsc --noEmit`, `NODE node_modules/vitest/vitest.mjs run`, `NEXT_TELEMETRY_DISABLED=1 NODE node_modules/next/dist/bin/next build`입니다. npm check와 같은 네 관문을 지정 Node로 직접 실행했습니다. 브라우저는 `NODE <scratch>/date_risk_browser.cjs`입니다.

- 각 RED/GREEN/설치/최종 실행 로그·JUnit XML·PNG/HTML은 격리 루트의 `date-risk-*`, `risk-panel-*`에 남겼습니다. 기준본 로그/XML은 baseline 루트에 있습니다.
- 전달 묶음은 scratch `date_risk_delivery_01/`의 `changes.patch`, `manifest.json`, `files/`, `evidence/`입니다. manifest는 실제 파일·원본 archive·patch의 SHA256과 변경 경계를 기록합니다.
- 후속 담당: 이 patch만 검토하여 별도 정상 Git 환경에서 남은 3관문 및 운영 승인 전 통합/E2E를 실행하십시오. 과거 검색kind/채팅/공지 후보를 합치지 마십시오.

## 관계

- [계약](../../external/rest-endpoints/web-intakes.md)
- [인계](../../../../wiki/handoff/index.md)
