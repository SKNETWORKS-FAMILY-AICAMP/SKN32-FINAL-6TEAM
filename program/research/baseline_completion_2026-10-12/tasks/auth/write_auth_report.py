"""완료된 실행 증거에서 인증 인계 보고서를 만든다. 기존 보고서는 덮어쓰지 않는다."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

here = Path(__file__).resolve().parent
workspace = here.parents[4]
cs = workspace / 'final_project_cs'
latest = sorted(here.glob('isolated-*.xml'))[-1]
run_id = latest.stem.removeprefix('isolated-')
runtime = json.loads((here / f'runtime-{run_id}.json').read_text(encoding='utf-8'))
stop = json.loads((here / f'stop-{run_id}.json').read_text(encoding='utf-8'))
assert runtime['pytest_exit_code'] == 0 and runtime['test_database_dropped'] and stop['stopped']
cases = ET.parse(latest).findall('.//testcase')
assert not any(c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None for c in cases)
groups = {}
for case in cases:
    key = case.attrib['classname'].split('.')[1]
    groups[key] = groups.get(key, 0) + 1
oauth_count = sum(c.attrib['classname'].endswith('test_personal_ai_oauth') for c in cases)
db_count = sum(c.attrib['classname'].endswith('test_personal_ai_oauth_db') for c in cases)
manifest = json.loads((here / 'source-manifest.json').read_text(encoding='utf-8-sig'))
unchanged = all(hashlib.sha256((cs / item['path']).read_bytes()).hexdigest().upper() == item['sha256'] for item in manifest)
assert unchanged, '시험 시작 뒤 인증 담당 소스가 바뀌었습니다.'
now = datetime.now().astimezone().isoformat(timespec='seconds')
verification = {'run_id': run_id, 'verified_at': now, 'passed': len(cases), 'failed': 0, 'skipped': 0,
                'groups': groups, 'oauth_security': oauth_count, 'oauth_postgres_integration': db_count,
                'source_files_unchanged': len(manifest), 'database_dropped': True, 'postgres_stopped': True}
(here / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding='utf-8')
report = here / 'report.md'
record = cs / 'wiki/records/reports/2026-10-12_personal-ai-oauth.md'
assert not report.exists() and not record.exists(), '기존 보고서는 백업 후 별도 처리하세요.'
text = f'''# 개인 AI OAuth·여행 권한 구현 결과

개인 AI 로그인·동의·토큰 교환·폐기와 본인 여행 권한을 로컬 작업 트리에 구현했습니다. 실제 외부 개인 AI 연결과 x600 서버 배포는 하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 전체 보안·계약·관련 통합 시험 | 통과 | {len(cases)}/{len(cases)} = 100% |
| 신규 OAuth 보안 시험 | 통과 | {oauth_count}/{oauth_count} = 100% |
| 신규 PostgreSQL 통합 시험 | 통과 | {db_count}/{db_count} = 100% |
| 인증 화면 4종·2개 크기 | 확인 | 8/8 = 100% |
| 완료 기준 검사 | 통과 | 26/26 = 100% |

검증 기록 시각: {now}. 진행 분모는 이번 실행으로 수집한 시험·화면입니다. 제품 전체 인수나 배포 완료 비율이 아닙니다. 완료 기준 검사는 앞선 격리 실행의 결과이며 이후 인증 보강은 마지막 전체 보안·계약·관련 통합 실행으로 재검증했습니다.

## 바뀐 동작

- 사전 등록한 공개 클라이언트가 회원의 동의를 받아 본인 여행 작업을 위임받습니다. 발견 문서·인가 코드·S256 PKCE·대상 자원·명시적 권한·정확한 리디렉션을 검사합니다. 코드·토큰·동의 대기 값은 해시만 PostgreSQL에 저장합니다.
- 코드 교환은 한 번만 성공합니다. 갱신 때 access/refresh를 함께 교체하고 옛 refresh를 다시 쓰면 살아 있는 동의 전체를 폐기합니다. 옛 refresh 자체가 만료된 경우도 감지합니다. 마지막 소셜 계정 연결 해제·회원 탈퇴·연결 폐기 뒤 접근을 막습니다.
- MCP에서 본인 여행 소유 관계와 읽기·변경 권한을 검사합니다. 계정·연락처·키 생성 권한은 열지 않으며 공유 계획 링크는 OAuth 자격이 아닙니다. 쓰기 스위치는 기본 꺼짐입니다. OAuth 원문을 내부 웹 API로 넘기지 않고 검증된 사용자 문맥을 전달합니다. 기존 에이전트 키의 MCP 인증도 접합했습니다.
- 인증 전용 로그인 안내·동의·연결 목록·폐기 확인을 제공합니다. 고객 웹과 API의 주소가 달라도 설정된 API 출처에서 동의할 수 있고 다른 출처는 거절합니다. 고객 웹 공용 스타일·여행 API·공통 설정·배포·requirements 파일은 수정하지 않았습니다.

현재 계약은 [개인 AI OAuth](../../../../../final_project_cs/wiki/external/personal-ai-oauth.md), 정책은 [전용 설정](../../../../../final_project_cs/config/personal-ai-oauth.json), SQL은 [신규 인증 저장 구조](../../../../../final_project_cs/app/infrastructure/db/migrations/901_personal_ai_oauth.sql)에 있습니다. [통합 요청](integration-request.md)은 외부 클라이언트 등록과 운영 검토 조건입니다. SDK는 기존 `mcp[cli]==1.28.1`을 사용합니다.

## 실행 증거

독립 PostgreSQL 바이너리를 읽어 인증 담당 전용 클러스터를 만들고, 실행마다 빈 시험 DB를 생성했습니다. 기존 SQL 실행기와 현재 프롬프트 등록 도구를 그 시험 DB에서만 실행했습니다. 업무 DB·유료 API·고객 알림·외부 개인 AI는 사용하지 않았습니다.

```powershell
python program/research/baseline_completion_2026-10-12/tasks/auth/run_isolated_tests.py tests/security tests/contract tests/e2e/test_personal_ai_oauth_db.py tests/e2e/test_mcp_server.py tests/e2e/test_web_agent_keys.py
```

최종 결과는 보안 {groups['security']}개·계약 {groups['contract']}개·관련 E2E {groups['e2e']}개입니다. 실패 0·건너뜀 0입니다. [실행 로그](isolated-{run_id}.log) · [JUnit 원문](isolated-{run_id}.xml) · [SQL 실행 로그](migration-{run_id}.log) · [기본 문구 등록](seed-{run_id}.log) · [DB 정리 기록](runtime-{run_id}.json) · [PostgreSQL 종료 기록](stop-{run_id}.json) · [집계](verification.json).

완료 기준은 같은 실행기에 `--with-dod`를 넣어 `python -m scripts.verify_dod_v11`을 수행했습니다. [완료 기준 원문](dod-20261012_043233.log): 26/26, MVP 18/18, 미통과·미측정·시험 없음 각 0. 이 검사는 현재 여행 관문이며 과거 쇼핑몰 평가 도구를 실행하지 않았습니다.

신규 DB 통합 시험은 실제 회원 쿠키 → 동의 → SDK 코드 교환 → MCP initialize·여행 조회 → 폐기까지 확인합니다. 타 고객 여행은 404, 타 tenant 고객 외래 키는 거절, 동시 코드 교환은 한 번만 성공, 읽기 권한의 쓰기 호출은 거절합니다. [보안 시험](../../../../../final_project_cs/tests/security/test_personal_ai_oauth.py) · [DB 통합 시험](../../../../../final_project_cs/tests/e2e/test_personal_ai_oauth_db.py).

mock 서버 시험 8/8 (화면 반응): 실제 인증 라우터의 합성 세션·저장 대역 응답을 외부 요청 차단 Chromium에서 렌더링했습니다. 별도 HTTP mock 서버를 띄우지는 않았습니다. [화면 자료](screens-20261012_043819/) · [화면 측정](screens-20261012_043819/checks.json). 375px·1280px의 가로 넘침, 44px 이상 클릭 높이, 키보드 포커스를 검사하고 PNG 8장을 직접 확인했습니다.

실서버 확인 (서버 응답): 실제 외부 개인 AI·x600 서버의 cs 프로젝트 서버는 안 했음. 인증 담당 전용 PostgreSQL과 로컬 테스트 API·SDK MCP 응답은 확인했음. 소셜 업체의 실제 로그인 응답은 합성 교환 대역으로 대신했습니다.

[소스 해시](source-manifest.json)의 인증 담당 12개 파일은 최종 시험 시작 뒤 변경되지 않았습니다. PostgreSQL 시험 DB 삭제와 담당 인스턴스 종료를 확인했습니다. 공유 작업 트리에서 수행했으므로 저장소 전체가 고정돼 있었다는 뜻은 아닙니다.

## 실패 이력과 고친 점

1. 초기 Windows 제한 실행은 loopback/socketpair 생성에서 진행되지 않았습니다. 중단하고 격리 실행만 권한 확장으로 수행했습니다. 자동 승인 검토 거절은 받지 않았습니다.
2. 초기 보안 39개 중 3개와 통합 73개 중 4개가 실패했습니다. SDK의 frozen 오류 객체가 트랜잭션 문맥을 지나는 문제, 공개 클라이언트 revoke의 nullable 필드 차이, 시험의 잘못된 되돌림 인자를 고쳤습니다. 이후 보안 39/39·통합 73/73을 확인했습니다. 원 결과는 [초기 보안](security-v2.xml) · [초기 통합](isolated-20261012_041442.xml)에 보존했습니다.
3. 확장 시험 405개 중 2개는 빈 시험 DB의 활성 프롬프트 두 개가 등록되지 않아 실패했습니다. [실패 원문](isolated-20261012_042810.xml)을 보존하고 기존 등록 도구로 시험 전제를 채운 뒤 406/406을 확인했습니다. 이 실행의 출력 처리도 Windows 문자 인코딩 오류로 중단돼 실행기를 UTF-8로 고쳤습니다. 담당 PostgreSQL은 해당 예외 때도 종료했습니다.
4. 후속 검토에서 만료된 옛 refresh 재사용과 고객 웹·API 출처 분리, 기본 로그인 주소를 시험에 더했습니다. 최종 실행에 모두 포함했습니다. 기존 SDK 전송 API의 폐기 예정 경고와 다른 담당 코드의 escape 경고는 원 로그에 남겼습니다.

## 통합 조건과 한계

- 실제 외부 개인 AI의 client ID·정확한 callback을 아직 등록하지 않았고 종단 연결은 시험하지 않았습니다. 공개 HTTPS 주소·고객 웹 주소·쿠키 설정과 callback을 운영 환경에서 확인해야 합니다. 루프백 callback은 포트까지 정확히 일치해야 하며 임의 포트 CLI 호환은 미확인입니다.
- DCR·CIMD 자동 등록·confidential client는 구현 범위에 포함하지 않았습니다. 대기·만료·폐기 레코드의 정기 청소, 운영 부하 시험은 수행하지 않았습니다. tenant별 교환 잠금은 정확성 위주이며 처리량을 측정하지 않았습니다.
- 신규 SQL의 업무 DB 적용, x600 서버 배포, 독립 매니저·웹 검토는 남습니다. 검토자는 임의 배정하지 않았습니다. 구현·검증을 이번 인증 담당이 함께 했으며 독립 검토 완료로 표시하지 않습니다. 커밋·푸시하지 않았습니다.

## 백업

기존 파일을 바꾸기 전 [최초 통합 백업](../../../../../final_project_cs/_backup/2026-10-12_personal_ai_oauth_before_integration/)을 만들었습니다. 후속 산출물은 [화면 검토 전](../../../../../final_project_cs/_backup/2026-10-12_0428_personal_ai_final_review/) · [재사용 검토 전](../../../../../final_project_cs/_backup/2026-10-12_0437_refresh_replay_review/) · [출처 검사 전](../../../../../final_project_cs/_backup/2026-10-12_0441_native_auth_origin/) · [계약 갱신 전](../../../../../final_project_cs/_backup/2026-10-12_0444_auth_contract_status/) · [실행기·상태 보완 전](_backup/2026-10-12_0435_runner_fix/)에 보존했습니다. 실행 로그·화면은 회차별 새 이름으로 남겨 이전 결과를 덮어쓰지 않았습니다.
'''
report.write_text(text, encoding='utf-8')
record.write_text(f'''---
type: report
title: 개인 AI OAuth 로컬 구현·격리 검증
description: 회원 동의·PKCE·토큰 순환·MCP 소유권을 구현하고 실제 외부 연결·배포와 구분한다
status: draft
domain: travel
---

# 개인 AI OAuth 구현·검증 — 2026-10-12

개인 AI 인증·회원 동의·본인 여행 권한을 로컬 작업 트리에 구현했습니다. 검증 기록 시각은 {now}입니다. 외부 개인 AI 연결·업무 DB 반영·x600 서버 배포는 하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 보안·계약·관련 통합 | 통과 | {len(cases)}/{len(cases)} = 100% |
| 신규 OAuth 보안 | 통과 | {oauth_count}/{oauth_count} = 100% |
| 신규 PostgreSQL 통합 | 통과 | {db_count}/{db_count} = 100% |
| 인증 화면 4종·2크기 | 확인 | 8/8 = 100% |

인가 코드 + S256 PKCE·회원 동의·정확한 callback·대상 자원·권한을 검사하며 코드는 한 번만 교환됩니다. 토큰은 해시로 저장하고 갱신 순환·재사용 시 전체 폐기·회원 연결 해제를 검사합니다. MCP는 OAuth 원문 대신 검증한 사용자 문맥으로 기존 여행 소유권·읽기/변경 검사를 사용합니다. 쓰기 스위치는 기본 꺼짐입니다.

실행 명령: 인증 담당 실행기로 독립 PostgreSQL을 준비한 뒤 `pytest tests/security tests/contract tests/e2e/test_personal_ai_oauth_db.py tests/e2e/test_mcp_server.py tests/e2e/test_web_agent_keys.py -q`를 수행했습니다. 별도 앞선 실행에서는 `python -m scripts.verify_dod_v11` 26/26·MVP 18/18을 확인했습니다. 화면은 실제 라우터의 합성 응답을 Chromium 375px·1280px에서 그렸습니다.

문제·수정·최종 명령·실패 이력·원 로그·백업·남은 통합 조건은 [인증 담당 상세 보고](../../../../program/research/baseline_completion_2026-10-12/tasks/auth/report.md)에 있습니다. 현재 구현 계약은 [개인 AI OAuth](../../external/personal-ai-oauth.md)입니다. 사전 등록된 public client만 지원하며 외부 종단 연결·임의 루프백 포트·부하·만료 자료 청소는 확인하지 않았습니다. 독립 검토·커밋·푸시는 수행하지 않았습니다.
''', encoding='utf-8')
status = {'task': 'auth', 'phase': 'ready_for_integration', 'updated_at': now,
          'implementation': 'implemented', 'verification': verification,
          'deployment': 'not_deployed', 'business_database': 'not_modified',
          'external_personal_ai_connection': 'not_tested', 'independent_review': 'pending',
          'dependencies_remaining': ['trusted client preregistration and external end-to-end connection',
                                     'SQL owner deployment check for 901 migration', 'manager/web independent review'],
          'report': 'report.md', 'integration_request': 'integration-request.md'}
(here / 'status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(verification, ensure_ascii=False))
