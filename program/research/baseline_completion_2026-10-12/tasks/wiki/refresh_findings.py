"""사용자 선택을 보존하고 과거 검토와 현재 파일 확인을 구분한다."""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[5]
PATH = ROOT/'program/research/wiki_review_2026-10-11/findings-v2.json'
now = datetime.now(timezone(timedelta(hours=9)))
data = json.loads(PATH.read_text(encoding='utf-8-sig'))
before = copy.deepcopy(data)
stamp = now.strftime('%Y-%m-%d_%H%M%S_findings-current-evidence')
backup = PATH.parent/'_backup'/stamp/PATH.name
backup.parent.mkdir(parents=True)
shutil.copy2(PATH, backup)
data.setdefault('previous_review_updated_at', data['updated_at'])
data['updated_at'] = now.isoformat()
data['current_verification_scope'] = '현재 파일·기존 실행 기록 대조. 제품 전체 인수 시험·배포 확인 아님'
data['historical_review_metadata'] = {
    'updated_at': data['previous_review_updated_at'],
    'claude_verified': before.get('claude_verified'),
    'claude_rounds': before.get('claude_rounds'),
    'claude_model': before.get('claude_model'),
    'scope': '이전 검토판에서 수행한 검토. 이번 파일 정정·기능 구현의 신규 검증을 뜻하지 않음',
}
data['claude_verification_scope'] = 'historical_review_metadata 참조. 이번 갱신의 Claude 재검토 미실행'

sql = json.loads((ROOT/'program/research/sql_retirement_2026-10-12/summary.json').read_text(encoding='utf-8'))
for item in data['findings']:
    if 'historical_review' not in item:
        item['historical_review'] = {k: copy.deepcopy(item[k]) for k in
            ['status', 'completion_evidence', 'updated_evidence', 'document_updated', 'implementation_complete'] if k in item}
        item['historical_review']['source_review_updated_at'] = data['previous_review_updated_at']
        item['historical_review']['date_note'] = '원문 내 날짜가 있으면 그 날짜 우선. 모든 항목을 같은 날 실행했다는 뜻이 아님'
        if isinstance(item.get('completion_evidence'), str):
            item['completion_evidence'] = '[과거 검토 기록 — 현재 완료 근거 아님] '+item['completion_evidence']
    artifacts = []
    for name in item.get('targets', []):
        p = ROOT/name
        artifacts.append({'path': name, 'exists': p.exists(),
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None})
    verification = {
        'checked_at_kst': now.isoformat(),
        'scope': '작업 트리의 지정 파일 존재·해시 확인. 본문 의미 일치·기능 인수 시험 아님',
        'artifacts': artifacts,
        'implementation_status': 'unverified', 'validation_status': 'unverified',
        'deployment_status': 'unverified',
        'current_evidence': 'program/research/baseline_completion_2026-10-12/tasks/wiki/report.md',
        'follow_up': '공용 분담표의 해당 기능 담당 결과와 통합 검토 필요',
    }
    if item['id'] == 'W14':
        verification.update({
            'scope': 'SQL 정리 실행 기록의 현재 내용 대조. 이번 세션의 새 DB 조회·SQL 실행은 하지 않음',
            'current_evidence': 'program/research/sql_retirement_2026-10-12/summary.json',
            'environment_observations': {name: {
                'captured_at_utc': value['captured_at_utc'],
                'legacy_tables_after': value['legacy_tables_after'],
                'exact_retired_table_count': 5,
            } for name, value in sql['environments'].items()},
            'deployment_evidence': 'program/research/sql_retirement_2026-10-12/deployment-final.json',
            'follow_up': '기존 SQL 실행 원자성·향후 배포 안전 담당의 별도 결과 대기. 과거 실행 대상 89개 주장을 현재 집계로 사용하지 않음',
        })
        item['completion_evidence'] = '현재 SQL 정리 결과는 current_verification을 읽습니다. 이전 완료 문구·파일 수는 historical_review에 보존했습니다. SQL 안전 개선 전체 완료를 뜻하지 않습니다.'
    if item['id'] in {'W16', 'W20', 'W22', 'W23', 'W25'}:
        verification['follow_up'] = '이번 wiki 구현·검사 결과는 wiki 담당 report/status로 확인. 기능별 상태·운영 반영은 각 담당과 통합 검토 범위'
    item['current_verification'] = verification

for key in ('confirmed_choices', 'deferred', 'remaining_recommendations_approved'):
    assert data.get(key) == before.get(key), key
for old, new in zip(before['findings'], data['findings']):
    for key in ('id', 'selected', 'decision', 'options', 'execution_authorization'):
        assert old.get(key) == new.get(key), (old['id'], key)
PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
proof = {'checked_at_kst': now.isoformat(), 'findings': len(data['findings']),
         'selected_choices_unchanged': True, 'decisions_unchanged': True,
         'backup': backup.relative_to(ROOT).as_posix(),
         'before_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(),
         'after_sha256': hashlib.sha256(PATH.read_bytes()).hexdigest()}
(Path(__file__).parent/'findings-preservation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('선택·결정 보존 확인: '+str(proof['findings'])+'개')
