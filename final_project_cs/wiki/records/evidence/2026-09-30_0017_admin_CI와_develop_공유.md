---
type: evidence
title: 운영 앱 GitHub CI 검증
description: admin과 develop PR CI의 실행 조건·원문 발췌·재현 명령
status: draft
domain: travel
---

# 운영 앱 GitHub CI 검증

2026-09-30 KST · Codex · PR #17 head `3aa0075e1f00ba436f2c680cdc57f3f12e126d0f` · base `38cd59d4d51113c1eee4626aeb63c2393269bc1a`.

## 실행 조건과 재현

GitHub Actions의 PR 병합 후보에서 실행했다. admin은 Ubuntu·Node 22·Chromium·`TZ=Asia/Seoul`·`NEXT_PUBLIC_ADMIN_DATA_MODE=demo`다. 미설정 시험은 모드를 빈 값으로 덮어쓰고 `.next-unconfigured`에 따로 빌드한다. 외부 API·실제 DB·비밀키는 사용하지 않는다.

admin 폴더에서 같은 순서를 실행한다. 로컬에서는 demo 환경변수를 먼저 설정한다.

```sh
npm ci
npm run check
npm run export:html
git diff --exit-code --stat -- mockups/admin-scenario.html
npx playwright install --with-deps chromium
npm run test:e2e
npm run test:unconfigured
```

develop CI는 Python 3.12·pgvector/pg16 서비스·테스트 전용 DB·mock LLM을 사용해 마이그레이션/프롬프트 등록 후 아래를 실행했다.

```sh
ruff check . --output-format=github
python -m pytest tests/architecture tests/contract tests/unit -q
```

## 실제 출력 발췌

전체 로그 중 결과 부분만 발췌했다. admin 로그의 ANSI 색상 코드는 제거했다.

[admin run 36588740572](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/36588740572):

```text
Test Files  1 passed (1)
     Tests  23 passed (23)
단일 HTML 생성: mockups/admin-scenario.html (761.5 KB) · 네트워크 불필요
Running 17 tests using 2 workers
  17 passed (20.4s)
  1 passed (3.0s)
{"conclusion":"success","status":"completed"}
```

HTML 차이 검사는 출력 없이 종료 코드 0이었다. admin 합계는 41/41(100%). workflow와 독립 검토에서 확인한 실행 순서가 실제 Ubuntu에서 성공했다.

[develop run 36588740375](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/36588740375):

```text
1712 passed, 67 skipped, 173 deselected, 1 warning in 11.47s
{"conclusion":"success","status":"completed"}
```

실행한 1,712개 중 1,712개(100%) 통과이며, 건너뜀/제외는 통과 수에 넣지 않는다. Ruff job도 success다. 전체 Python·security·제품 DoD 전체 통과를 주장하는 결과는 아니다.

## 로컬 정적 확인

```text
workflow YAML parsed; 9 steps
admin workflow links resolve
```

YAML을 Python으로 파싱하고 앱 문서의 workflow 링크 존재를 확인했다. 최초 샌드박스 실행은 Python 프로세스를 만들지 못했으며 실행 권한을 확보한 재시도에서 위 결과를 얻었다. `git diff --cached --check`는 통과했다. 동작 코드 변경 없이 CI와 실행 안내만 추가했으며, 최초 로컬 Chrome 검증과 별개로 이번에는 GitHub의 Chromium 결과를 확인했다.

## 구판 DoD 증거 전제조건

현재 `scripts.verify_dod`의 `ITEMS`와 `_evidence`를 읽어 `path`, `has_reproduction`, `has_actual_output`, `judgement == '통과'` 조건만 평가했다. 파일과 실제 판정은 변경하지 않았다. 전체 pytest를 호출하는 `main()`은 실행하지 않았다.

```text
DoD-15: 부분통과; reproduction=True; actual_output=False
DoD-17: 부분통과; reproduction=True; actual_output=True
DoD-28: 부분통과; reproduction=True; actual_output=True
legacy_evidence_pass=26/29
read-only evidence precondition check; full DoD script/test suite not executed
```

26/29(89.7%)는 구판 스크립트의 증거 전제조건 수치이며 현재 v11 제품 달성률이 아니다. 이 전제조건만으로도 구판 게이트의 전체 통과를 주장할 수 없다. [리포트의 병합 기준 미해결 사항](../reports/2026-09-30_0017_admin_CI와_develop_공유.md)을 함께 확인한다.

## 보안 검사 추가

로컬 개발 환경에서 mock LLM을 설정하고 `python -m pytest tests/security -q`를 실행했지만 120초 제한에서 중단되어 통과로 세지 않았다. DB 대상이 루프백임은 확인했으며 지연 원인은 이 작업에서 확정하지 않았다. 원문 요약은 `security_timeout_seconds=120`이다.

같은 검사를 기존 develop CI의 마이그레이션된 임시 PostgreSQL에서 실행하는 별도 단계로 추가했다. 로컬 DB 상태에 의존하지 않는 최종 결과는 PR #17의 최신 `CI (develop)`에서 확인한다. 두 workflow YAML 파싱과 새 report/evidence의 상대 링크 7/7(100%) 확인은 통과했다.
