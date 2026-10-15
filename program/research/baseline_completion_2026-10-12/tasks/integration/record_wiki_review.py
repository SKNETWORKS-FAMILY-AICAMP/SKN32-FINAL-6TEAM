"""독립 위키 검토를 기존 통합 판정에 추가하며 이전 산출물은 보존한다."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import shutil
import sys

BASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[5]
source = BASE / sys.argv[1]
data = json.loads(source.read_text(encoding='utf-8'))
now = datetime.now(timezone(timedelta(hours=9)))
stamp = now.strftime('%Y-%m-%d_%H%M%S_%f')
backup = BASE / '_backup' / (stamp + '_wiki_handoff_review')
backup.mkdir(parents=True)
for name in ('integration-table.json', 'integration-table.md', 'report.md', 'status.json'):
    shutil.copy2(BASE / name, backup / name)


def write_json(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


evidence = source.relative_to(ROOT).as_posix()
relative = source.relative_to(BASE).as_posix()
review_path = BASE / ('wiki-review-' + stamp + '.md')
review_text = f'''# 위키 인계 독립 검토 — {now.isoformat()}

위키 도구와 작성 규칙의 인계 근거를 확인했습니다. 전체 위키 검사는 위반 4건으로 실패하며, 최종 제품 완료를 뜻하지 않습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 인계 파일 해시 대조 | 일치 | {data['handoff_hashes']['matched']}/{data['handoff_hashes']['total']} = 100% |
| 위키 도구 회귀 재실행 | 통과 | 12/12 = 100% |
| 전체 위키 검사 | 위반 4건 | 306/306 = 100% 검사 실행 |
| 최종 문서 2종 | 결과 대기 | 0/2 = 0% |

## 실제 검토 범위

- 변경 도구 두 개와 시험 본문, 작성·머리말·근거·리뷰·상태 규격, 역할·코드 경로 안내, 감시 결정의 현재/과거 경계를 읽었습니다. 새 인명 배정·문서 stable 승격·제품 기능 인수는 하지 않았습니다.
- 담당 원본 JUnit은 위키 도구 12개·구조 12개가 각각 실패/오류/건너뜀 0개입니다. 이번에는 위키 도구 12개를 독립 재실행했습니다. 원본 24개와 이번 12개를 새 시험 36개로 합산하지 않습니다.
- 인계 해시 17개가 현재 파일과 일치하고, 검토 전후 이 17개는 바뀌지 않았습니다. 다른 활성 담당의 제품 코드·문서는 이 범위가 아닙니다. 원본 선택·결정 25개는 백업과 현재 값이 일치했습니다.
- 생성기 `--check`는 종료 0으로 출력 일치를 확인했습니다. 카탈로그 등록 수·파일 수를 기능 시험 통과 수로 표시하지 않습니다.

## 미해결과 판정

W16의 개발 책임·경로 문서와 W23 집계 도구는 검토 범위의 근거를 확인했습니다. W20은 검사 도구가 준비됐으나 적용 대상 93개 중 90개에 일부 상태 필드가 빠져 있습니다. W22의 범위 구분 회귀는 통과했고 전체 wiki 위반은 그대로 남겼습니다. W25의 현재 규칙·보존 기록 구분을 확인했으며 전체 기능 계약의 현재 코드 일치 판정은 아직 아닙니다.

전체 검사 위반 4건은 활성 작업 중인 무인 운영 문서의 상태 값 1건, 분류 실행 계획 문서의 상태 값과 아직 작성 중인 보고서 링크 2건, 이동 요금 웹 문서 머리말 1건입니다. 다른 담당 파일은 수정하지 않았습니다. 상태 필드 미적용 90개는 형식 위반 4건과 다른 분모입니다.

[독립 실행·원본 해시·전체 위반](./{relative})에 명령·KST 시각·종료 코드·원본 로그를 연결했습니다. 전체 제품 시험의 실패 19건은 검증 담당이 원인을 확인 중이며 이번 위키 도구 시험으로 닫지 않았습니다.

mock 서버 시험(화면 반응): 안 했음. 이번은 문서·도구 검사입니다.

실서버 확인(서버 응답): 안 했음. 업무 DB·원격 앱·유료 API를 호출하지 않았습니다.

[덮어쓰기 전 백업]({backup.relative_to(BASE).as_posix()}/)을 보존했고, 공유 구현·담당 상태·공용 coordination은 변경하지 않았습니다.
'''
review_path.write_text(review_text, encoding='utf-8')
table = json.loads((BASE / 'integration-table.json').read_text(encoding='utf-8'))
for row in table['rows']:
    if row['id'] not in data['acceptance']:
        continue
    row['owner_phases']['wiki'] = 'ready_for_integration'
    row['implementation_review'] = 'scoped_source_reviewed'
    row['validation_review'] = 'scoped_evidence_reviewed'
    row['acceptance'] = 'partial_pending_integration'
    row['integration_review'] = {'checked_at_kst': now.isoformat(), 'scope': data['acceptance'][row['id']],
                                  'evidence': evidence, 'final_product_acceptance': False}
    row['tests'] = [{'scope': '위키 도구 회귀; 기능 인수 아님', 'passed': 12, 'failed': 0,
                     'evidence': data['independent_governance_junit']['path']}]
table['last_review_at_kst'] = now.isoformat()
write_json('integration-table.json', table)
text = (BASE / 'integration-table.md').read_text(encoding='utf-8')
lines = []
for line in text.splitlines():
    if any(line.startswith('| ' + wid + ' |') for wid in data['acceptance']):
        columns = line.split('|')
        columns[4] = ' wiki: ready_for_integration '
        columns[5] = ' 담당 범위 검토·최종 인수 대기 '
        line = '|'.join(columns)
    lines.append(line)
text = '\n'.join(lines) + f'\n\n## 후속 위키 인계 검토\n\n[{now.isoformat()} 검토]({review_path.name}) — 변경 해시 17/17, 독립 도구 회귀 12/12, 생성물 일치. 전체 위키 위반 4건·상태 일부 미적용 90/93은 미해결이며 제품 완료로 승격하지 않습니다.\n'
(BASE / 'integration-table.md').write_text(text, encoding='utf-8')
report = (BASE / 'report.md').read_text(encoding='utf-8')
report += f'\n\n## 후속 확인 — {now.isoformat()}\n\n[위키 인계 독립 검토]({review_path.name}): 인계 해시 17/17 일치, 도구 회귀 12/12 통과, 생성물 일치. 전체 위키 검사 위반 4건·상태 필드 일부 미적용 90/93은 그대로 남겼습니다. 공통 시험 실패 19건은 검증 담당 진행 중입니다. 최종 v12·기준선은 0/2 = 0%이며 의존 결과 대기 상태를 유지합니다. [이번 변경 전 백업]({backup.relative_to(BASE).as_posix()}/).\n'
(BASE / 'report.md').write_text(report, encoding='utf-8')
status = json.loads((BASE / 'status.json').read_text(encoding='utf-8'))
status['phase'] = 'waiting_dependency'
status['updated_at_kst'] = now.isoformat()
status['checks'].append({'command': data['commands'][0]['command'], 'passed': 12, 'failed': 0, 'total': 12, 'evidence': evidence})
status['dependencies_remaining'] = []
for key in ('auth', 'orchestration', 'operations', 'wiki', 'verification'):
    path = BASE.parent / key / 'status.json'
    phase = json.loads(path.read_text(encoding='utf-8-sig'))['phase'] if path.exists() else 'status_not_written'
    status['dependencies_remaining'].append(key + ': ' + phase)
status['dependencies_remaining'].append('existing: 관련 결과의 변경 파일·원본 실행 로그 확인')
status['unresolved'] = list(dict.fromkeys(status['unresolved'] + ['전체 wiki 위반 4건·상태 필드 일부 미적용 90/93. 활성 담당 작업과 최종 통합에서 확인', '검증 담당 공통 시험 실패 19건. 원인 확인 중']))
status['wiki_review_evidence'] = evidence
status['latest_review_report'] = review_path.relative_to(ROOT).as_posix()
status['ready_reason'] = '위키 인계의 코드·규격·원본 JUnit·현재 해시와 독립 회귀를 검토했습니다. 필수 구현·전체 시험은 대기 중입니다.'
status['backup'] = backup.relative_to(ROOT).as_posix()
status['changed_files'] = sorted(set(status['changed_files'] + [p.relative_to(ROOT).as_posix() for p in (Path(__file__), BASE/'review_wiki_handoff.py', review_path, source)]))
write_json('status.json', status)
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps({'report': review_path.relative_to(ROOT).as_posix(), 'backup': status['backup'], 'phase': status['phase']}, ensure_ascii=False))
