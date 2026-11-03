---
type: report
title: 빈 폴더를 가리키는 serving 프로세스(8042·3100·61695·50487) — 원인·사용 여부·복원 경로
description: 10-27 19:45 텔레그램 세션의 scratch 정리(_cleanup3a/3b)가 실행 중 프로세스를 확인하지 않고 "git 없음" 폴더를 보관 없이 지워 로컬 live API·웹과 v5 비교 서버의 소스가 사라졌다. 바이트 단위 복원 경로는 없고, 기능상 가장 가까운 것은 role-manager efc6fca4 기반 새 서빙이다
status: done
domain: travel
impl_scope: 운영 기록 — 읽기 전용 조사. 서버 중지·재시작·포트·방화벽·기존 파일 변경 0. 각 API 포트에 GET /openapi.json 1회씩만 보냈다
---

# 빈 폴더를 가리키는 serving 프로세스 — 원인·사용 여부·복원 경로 (2026-10-31 06:15–06:40)

인계: [라우팅 세션 인계](../../handoff/2026-10-31_empty-serving-folders-routing-relay.md). 증거: [evidence.json](../evidence/2026-10-31_empty-serving-folders/evidence.json).

## 결론

- **원인은 확정됐다.** 10-27 텔레그램 세션 `20261026_055053_ce47d8ba`가 디스크를 비우려고 만든 `_cleanup3a.sh`(목록 작성)와 `_cleanup3b.py`(삭제)가 지웠다. 목록 규칙은 "3시간 넘게 안 바뀌었고, 최근 `_coord`에 이름이 없고, git 저장소가 없으면 그대로 삭제"였다. **실행 중인 프로세스의 명령줄이나 작업 폴더는 확인하지 않았다.** serving 폴더들은 git이 없어서 보관 없이 바로 지워졌다.
- **지금 쓰는 서버는 8042(API)와 3100(웹)뿐이다.** 61695·50487은 10-25 v5 비교 시험용으로, 아무것도 그 주소를 쓰지 않는다. 지금 이 네 포트에 맺힌 연결은 0개다.
- **똑같은 소스로 되살릴 길은 없다.** v10c는 git 밖에서 v8→v9→v10→v10c로 쌓은 로컬 판인데, 그 네 단계의 소스와 패치 파일이 모두 지워졌다. 롤백 대상(v9)도 비어 있다. 기능상 가장 가까운 것은 role-manager `efc6fca4`(또는 그 이후)다. 열린 API 경로 115개의 이름이 115/115 일치한다.
- **권장:** 8042+3100은 당장은 그대로 두고, `efc6fca4` 이후 커밋으로 새 폴더에 v11을 만들어 검증한 뒤 바꾼다. 61695·50487은 사용자가 승인하면 종료한다.

## 1. 원인 — 어느 세션이, 무엇으로, 언제

| 시각(10-27) | 일 | 근거 |
|---|---|---|
| 18:55 | `_cleanup1.py`: `node_modules`·`.next` 등 다시 만들 수 있는 폴더만 지움 | state.db 메시지 55542, 파일 시각 |
| 19:02 | `_cleanup2.py`: git 실행이 `WinError 5`로 막혀 보관 단계가 실패했고, 그래서 아무것도 지우지 않음 | 메시지 55572·55739 |
| 19:05–19:43 | `_cleanup3a.sh`: 보관과 목록 작성. `ok=230 keep=68` | 메시지 55736·55843, `_cleanup_ok.txt` 19:43:33 |
| 19:45:49 | `_cleanup3b.py`가 시작됨(PID 30116). 목록을 이름순으로 `rmtree` | 메시지 55858 |
| 19:52 / 19:56 / 20:04 / 20:18 | `cs-web-response-status`(42번째) / `integ-v10c-ctx`(79)·`integ-v9`(81) / `public-web-binding-v5`(136) / `web-v5-release`(211) 폴더 시각 | 20:03:42 확인 때 133번째 `port-l07-l02a`까지 진행 중이었다. 바로 다음 항목이 136번째다 |

- 지운 폴더 가운데 serving에 쓰던 7개는 모두 `_cleanup_ok.txt.nogit`에 「no git root (non-repo files only)」로 올라 있었다. 그래서 `_archive_20261027`에는 아무것도 남지 않았다. 해당 폴더: `integ-v10-20261026-042421`, `integ-v10c-ctx-…`, `integ-v9-…`, `integ-v9c-ctx-…`, `public-web-binding-v5-…`, `web-v5-release-…`, `cs-web-response-status`.
- 네 스크립트 어디에도 프로세스 확인(Win32_Process, netstat)이 없다. 같은 시간대 세션 기록에 Win32_Process가 2번 나오지만, 둘 다 20:06 이후 파이널스페이스 작업에서 쓴 것이다.
- 남은 파일은 실행 중이라 잠겨 있던 것뿐이다: `cs-web-response-status/node.exe`, 그리고 `web-v5-release` 안 `.next` 캐시 30개. 이 30개의 수정 시각은 10-25 17:16부터 10-26 03:14까지로, 삭제 전에 생긴 파일이다. "삭제 뒤에 새로 생긴 파일"이라던 앞선 추정은 틀렸다.
- 10-28 [scratch 정리 보고](2026-10-28_c-drive-free-space-units-and-scratch-cleanup.md)는 이 폴더들을 "실행 중이라 남김"으로 적었다. 실제로는 그때 이미 비어 있었다.

## 2. 사용 여부

| 서버 | 주소 | 정체 | 설정·프로세스가 참조하는가 | 현재 연결(netstat) |
|---|---|---|---|---|
| 8042 API (PID 23120) | 127.0.0.1, **192.168.0.15** | 로컬 live v10c | 3100 웹 빌드가 이 주소를 호출하도록 컴파일됐다(localhost 빌드는 `127.0.0.1:8042`, LAN 빌드는 `192.168.0.15:8042`, wiki `delivery/travel-response-current.md` 83행) | 0 |
| 3100 웹 (PID 26720·27028) | 127.0.0.1, **192.168.0.15** | 고객 웹 v5 빌드 | 사용자가 쓰는 로컬 화면 | 0 |
| 61695 (PID 23968) | 127.0.0.1 | v5 읽기 전용 shadow(10-25 비교) | 없음. 3300 admin(`.env.example`, `next.config.ts`)·8070·3100 모두 참조 0. 명령줄에 61695가 들어간 프로세스는 자신과 자신을 띄운 셸뿐이다 | 0 |
| 50487 (PID 2200) | 127.0.0.1 | v5 쓰기 가능 정상 비교(10-25, 복사 DB의 전용 tenant) | 없음(위와 같음) | 0 |

- 세 API의 `/openapi.json`(각 126,320 B)은 sha256 `765c3319…6c49`로 **3/3 같다.** 화면에서 부르는 API 목록은 v5와 v10c가 같다는 뜻이다.
- 이미 메모리에 올라간 코드만 응답한다. 아직 열린 적 없는 화면이나 모듈을 처음 불러야 하면 실패할 수 있다(웹은 `node_modules`·`.next`가 없음).

## 3. 복원 경로와 일치 증거

| 대상 | 기록된 구성 | 남아 있는 것 | 일치 확인 |
|---|---|---|---|
| 8042 v10c | v8(git 밖) → v9(+후보 6개, `deleg_7f3c4ea8`) → v10(+`da4ccd97` 실내·야외 되묻기 +T16, `deleg_60469741`) → v10c(+`ctx-overflow-v9.patch` sha256 `e40426437a42…75887435`, `launch-serving.py` `ACOP_OLLAMA_NUM_CTX` 12288, `policy.py` num_ctx 4곳 12288, `deleg_d97915d1`, [인계 08:45](../../handoff/2026-10-26_routing-agent-completion-overnight.md)) | **소스·패치·PARENT_SWAP 모두 없음.** 해시가 `e404…`인 파일은 프로필 전체에서 찾지 못했다. `_archive_20261027/ctx-overflow-*/*/dirty.patch` 3개(e6a0…, f24b…)는 role-manager 쪽 후보라서 해시가 다르다 | 바이트 단위 복원 0/1. 같은 기능이 role-manager에 들어가 있다: T16 `418cc190`, num_ctx `539cef63`, `8fae4901`, 그리고 셋 다 `efc6fca4`의 조상이다(3/3). `efc6fca4`의 `settings.py`는 `ollama_num_ctx=12288`이다 |
| 3100 웹 v5 | `public-web-binding-v5/source-v5` = 정본 `6c34589b` + 검증 delta 한 파일(접수 확인 사진 문구). BUILD_ID localhost `ZojSXmTH7hmXO9eyo677J`, LAN `oGN1-Tld3XUSF7MCHzon3`(`deleg_94d6616f`, [보고](2026-10-25_v5-frontend-parent-live.md)) | 커밋 `6c34589b`는 있다(`allpast-hotfix-20261025-2005/latest`). delta와 `PREPARED_FRONTEND_SWAP.json`은 없다 | 빌드 산출물 해시를 대조할 수 없다(원본 산출물 0). 커밋까지만 확인했다 |
| 61695·50487 v5 API | 같은 `source-v5`(`deleg_135ed6d6`: source closure 4,889/4,889) | 커밋 `6c34589b`만 있다 | 우선순위가 낮아 복원은 제안하지 않는다 |

**API 경로 이름 대조**(live openapi 115경로·125작업 대 git의 라우트 문자열. 스키마는 비교하지 못했다. 앱을 띄우려면 설정·DB 환경이 필요해서다):

| 커밋 | 일치 |
|---|---|
| `6c34589b`(v5 기반) | 115/115 = 100% |
| `da4ccd97` · `8fae4901`(10-26 role-manager) | 114/115 = 99.1%(`dining-answers` 없음) |
| `bdb48ffc` · `efc6fca4` | 115/115 = 100% |

git: 로컬 저장소 `cache/scratch/allpast-hotfix-20261025-2005/latest`. `bdb48ffc..efc6fca4`는 1커밋이다. 원격은 지금 role-manager `fab3da50`, develop `3463b30c`다(ls-remote로 읽기만 했다).

## 4. 선택지

| 서버 | 선택지 | 결과(한 줄) | 위험 |
|---|---|---|---|
| 8042+3100 | 그대로 두기 | 지금 화면은 계속 된다 | 재부팅, 프로세스 종료, 처음 여는 화면에서 실패할 수 있고 되살릴 소스가 없다. 두 서버 모두 LAN(192.168.0.15)에도 열려 있다 |
| 8042+3100 | 같은 v10c로 복원 후 재기동 | **할 수 없다**(소스 0) | — |
| 8042+3100 | **efc6fca4 이후로 v11을 만들어 교체(권장)** | 소스가 git에 있는 판으로 바뀌고, 다시 띄울 수 있다 | 로컬 전용 v9 기능 일부가 role-manager에 없으면 동작이 달라질 수 있다(경로 이름은 115/115). DB 마이그레이션 차이를 확인해야 한다. 교체하는 동안 웹과 API가 1~3분 끊긴다 |
| 8042+3100 | 끄기 | 로컬 화면을 못 쓴다 | 사용자 확인이 필요하다 |
| 61695 | **끄기(권장)** | 아무 영향이 없다(참조 0, 연결 0) | 거의 없다. 10-25 비교 증거는 wiki 보고에 남아 있다 |
| 50487 | **끄기(권장)** | 아무 영향이 없다 | 거의 없다. 쓰기 가능한 API가 복사 DB에 붙어 있어서 켜 둘수록 손해다 |
| 61695·50487 | 그대로 두기 | 변화 없음 | 메모리와 DB 연결을 계속 쓴다. 다시 띄울 수 없다 |

**v11 절차(제안. 사용자가 승인한 뒤에만):**
1. 새 폴더 `cache/scratch/live-v11-<날짜>/`에 `git worktree add`(또는 `git archive`로 `final_project_cs`만)를 만든다. 원본 `C:/_proj/final_workspace`는 쓰지 않는다. 소스는 0.36GB(파일 10,782개)이고, 웹 `node_modules` 약 0.6GB와 빌드 2개 약 0.6GB를 더해 **약 2GB**가 든다(지금 C: 여유 219.75GB).
2. API는 기존 인터프리터 `date_risk_python_01`과 `ACOP_OLLAMA_NUM_CTX=12288`을 쓰는 새 포트(예: 8142)에서 shadow로 띄운다. `/health`와 `/openapi.json` 경로 115/115, 수용 49건과 16항목 해석 시험을 통과하는지 확인한다.
3. 웹은 localhost용과 LAN용을 따로 `next build`한다(각각 API 주소 컴파일). 새 포트에서 홈, `/start`, `/trips` 응답이 200인지 확인한다.
4. 사용자가 승인하면 8042·3100 리스너를 바꾸고, 바꾼 직후 같은 확인을 다시 한다. v10c로 돌아갈 롤백은 없으므로 실패하면 v11을 고쳐서 다시 올린다.

## 5. 재발 방지 제안

- 정리 스크립트는 지우기 직전에 `Win32_Process`의 모든 명령줄과 실행 파일 경로를 모으고, 대상 폴더 경로가 들어 있으면 지우지 않는다. listen 포트를 가진 PID도 같이 확인한다.
- serving 폴더에는 `SERVING_LOCK.json`(PID·포트·시작 시각)을 두고, 정리 스크립트는 그 PID가 살아 있으면 건너뛴다.
- "git 없음 = 지워도 됨" 규칙은 없앤다. git이 없는 폴더는 크기와 이름 목록을 보고하고, 사람이 승인한 것만 지운다.
- live로 교체할 때는 소스를 git 커밋으로 남긴다(로컬 브랜치 + bundle). 롤백 대상 폴더는 정리 대상에서 뺀다.

## 이번 조사에서 만든 것과 지운 것

- 만든 것: 이 보고서, `wiki/records/evidence/2026-10-31_empty-serving-folders/evidence.json`, 인계 문서에 덧붙인 결과 절.
- 임시 파일: `cache/scratch/empty-serving-audit-20261031/`(openapi 3개와 대조용 파일). 끝난 뒤 폴더째 지웠다.
