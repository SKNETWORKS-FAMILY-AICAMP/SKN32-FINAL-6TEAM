# 경보 스냅샷 실행 증거 — 2026-10-09

mock 서버 시험 1/1 = 100% (화면 반응): 변경 전·대체안 미리 보기, `dry_run: true`, edits·confirm 요청 0건.
실서버 확인 (서버 응답): 했음 — x600 서버의 cs 프로젝트 서버 상태 API 200·시험 목록 API 404·경보 원본 5/6종. 실경보 대체안 화면 확인은 안 했음.

## 실행기 안전 시험

작업 폴더 `final_project_cs`, 새 임시 폴더를 지정해 실행:

```powershell
python -m pytest var/alert-snapshots/verify_runner.py -q --basetemp <작업폴더 안의 새 임시 경로> --tb=short
python -m py_compile scripts/capture_alert_scenarios.py
```

원문:

```text
......                                                                   [100%]
6 passed in 1.51s
```

pytest 종료 코드는 0이다. Python의 `pyreadline3` 종료 처리에서 Windows 핸들 경고가 추가로 나왔다. 시험 실패로 바꾸거나 그 경고를 숨기지 않는다. 첫 실행은 sandbox 임시 폴더 생성 권한 때문에 setup에서 5건 오류였고, 작업 폴더 안의 새 임시 경로를 지정해 다시 실행했다.

검사 항목: 덮기 전 원본 보존·동시 실행 차단·실패 후 잠금 해제·캐시의 첫 확인 시각 보존과 키 제외·API 404 시 브라우저 실행 금지와 반복 알림 억제·원본 수집 모드의 고객 API 및 브라우저 실행 금지. 네트워크를 사용하지 않는 실행기 시험이며 실제 경보 검증으로 세지 않는다.

## 브라우저 화면 시험

작업 폴더 `frontend/apps/web`, 회차 입력·출력 환경변수와 `LIVE_SKIP_BUILD=1`, `PLAYWRIGHT_CHANNEL=chrome`으로 실행:

```powershell
node node_modules/@playwright/test/cli.js test -c playwright.live.config.ts alert-snapshots.spec.ts
```

원문:

```text
ok 1 tests\live\alert-snapshots.spec.ts:21:1 › mock 서버 대체안 미리 보기의 전후 화면을 구분해 보관 (5.4s)
-  2 tests\live\alert-snapshots.spec.ts:39:1 › 실경보를 반영한 점검용 접수의 대체안과 전후 화면
1 skipped
1 passed (11.5s)
```

스킵한 1개는 실제 cs 프로젝트 서버 전용 시험이다. 통과 분모에 포함하지 않는다. 처음에는 백업의 `.spec.ts`가 시험으로 수집되는 문제가 있어 `.bak`로 바꿨다. 그다음 설치되지 않은 Playwright Chromium 경로로 실행이 실패해 설치된 Chrome을 지정했다. 이후 통과했다.

전후 화면을 직접 열어 확인했다: [변경 전](../../../../var/alert-snapshots/mock/initial-20261009/mock-before.png) · [대체안](../../../../var/alert-snapshots/mock/initial-20261009/mock-after.png). 원본 스냅샷은 git 밖에 둔다.

`node node_modules/typescript/bin/tsc --noEmit --pretty false`와 해당 시험의 ESLint는 종료 코드 0이다.

## 실제 경보 수집

최종 읽기 전용 실행:

```powershell
python -m scripts.capture_alert_scenarios --archive-only
```

원문:

```json
{"run_id": "2026-10-09_023735_6daf5437", "status": "archived_partial", "snapshots": 0, "should_notify": true}
```

최종 회차는 [개인 결과 폴더](../../../../var/alert-snapshots/real/2026-10-09_023735_6daf5437/)에 있다. 기상특보·재난문자·지진·UTIC·지하철 공지 5종을 읽었다. ITS는 `budget_exhausted`라 부르지 않았다. 캐시는 공급자 본문과 원래 확인 시각을 함께 보관하며 HTTP 새 응답과 구분했다. 당일 재난문자와 지진, 조회 시점의 서울 기상특보 목록은 비어 있었다. 교통 돌발은 따로 장소·적용 시간을 확인해야 한다. 지하철 공지 최신 페이지의 첫 공지는 9월 22일 운행 재개 안내였다. 이를 오늘 난 사건으로 쓰지 않았다.

한 회차는 시험 API 조회에서 실패했다: `2026-10-09_023438_59c708af`, 상세는 git 밖 `private-error.txt`에 있다. 수집 실패나 API 실패를 성공으로 바꾸지 않았다.

현재 배포 코드 확인은 `bd0239b09bb5891d39d3aaf78fdc3f6b189e79b1`, Ollama 목록 조회는 연결 끊김이었다. 런타임의 `llm_failover_enabled=true`, `llm_failover_model=gpt-6-luna`, cs 프로젝트 서버용 키 설정 여부 true를 읽었다. 이번 회차에서 모델 API를 새로 호출해 성공 여부를 잰 것은 아니다.

## 예약 등록

Codex 앱 도구 결과:

```text
Created automation in the app.
{"automationId":"tripilot","mode":"create","status":"ACTIVE"}
```

매일 오전 9시 이 채팅에서 `--archive-only`로 실행한다. 30분 감시·원격 시험 접수를 포함한 별도 등록은 자동 승인 검토에서 거절됐고, 사용자 승인 질문을 보냈다. 차단된 동작을 원본 수집 예약에 넣지 않았다.
