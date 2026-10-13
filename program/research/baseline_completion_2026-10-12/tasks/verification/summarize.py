"""기존 실행 결과를 집계하고 담당 상태를 백업 후 갱신한다."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT/'final_project_cs'
RUN = HERE/'runs/2026-10-12_035832'
stamp = datetime.now(ZoneInfo('Asia/Seoul'))
snapshot = {'at_kst': stamp.isoformat(), 'runs': {}, 'source_changes': {}}
clean_run = HERE/'runs/2026-10-12_clean_travel'
labels = [(label,RUN) for label in ('common-v2','a2a-recheck','operations-added-v1','travel-v1')]
labels += [(p.name.removesuffix('-source-before.json'),clean_run) for p in sorted(clean_run.glob('*-source-before.json'))]
for current_run in sorted((HERE/'runs').iterdir()):
    if current_run.is_dir() and current_run not in (RUN,clean_run):
        labels += [(p.name.removesuffix('-source-before.json'),current_run) for p in sorted(current_run.glob('*-source-before.json'))]
for label,current_run in labels:
    path = current_run/(label+'-outcomes.json')
    if not path.exists():
        log = current_run/(label+'.log')
        visible = ''.join(match.group(1) for match in __import__('re').finditer(r'^([.FsExX]+)(?:\s|$)',log.read_text(encoding='utf-8',errors='replace') if log.exists() else '',__import__('re').MULTILINE))
        progress = current_run/(label+'-progress.jsonl')
        rows = [json.loads(line) for line in progress.read_text(encoding='utf-8').splitlines()] if progress.exists() else []
        counts = Counter(row['outcome'] for row in rows if row['when']=='call' or (row['when']=='setup' and row['outcome']=='skipped'))
        setup_errors = [row['nodeid'] for row in rows if row['when']!='call' and row['outcome']=='failed']
        completed_nodes = {row['nodeid'] for row in rows if row['when']=='call' or (row['when']=='setup' and row['outcome'] in ('skipped','failed'))}
        state = 'interrupted_not_final' if label=='travel-v1' else 'native_crash' if label=='travel-v2' else 'setup_failed' if label=='travel-v3' else 'running_or_not_finalized'
        if (current_run/(label+'-termination.json')).exists():
            state = json.loads((current_run/(label+'-termination.json')).read_text(encoding='utf-8')).get('state','native_crash')
        snapshot['runs'][label] = {'state':state,'visible_progress_markers':len(visible),'visible_counts':dict(Counter(visible)),'completed_reports_counts':dict(counts),'failed_nodeids':[row['nodeid'] for row in rows if row['outcome']=='failed'],'evidence':str(progress.relative_to(ROOT)) if progress.exists() else str(log.relative_to(ROOT)),'scope':'완료 단계별 판정과 종료 상태를 구분. 비정상 종료는 전체 통과가 아님'}
        snapshot['runs'][label].update(completed_nodeids_count=len(completed_nodes),setup_teardown_errors=setup_errors)
        continue
    data = json.loads(path.read_text(encoding='utf-8'))
    counts = Counter(row['outcome'] for row in data['reports'] if row['when']=='call' or (row['when']=='setup' and row['outcome']=='skipped'))
    setup_errors = [row['nodeid'] for row in data['reports'] if row['when']!='call' and row['outcome']=='failed']
    failures = [row['nodeid'] for row in data['reports'] if row['outcome']=='failed']
    snapshot['runs'][label] = {'state': 'finished', 'exit': data['exit'], 'counts':dict(counts), 'setup_teardown_errors':setup_errors, 'failed_nodeids':failures, 'network_blocks':len(data.get('network_blocks',[])), 'finished_at_kst':data['finished_at_kst']}
    before = json.loads((current_run/(label+'-source-before.json')).read_text(encoding='utf-8'))
    after = json.loads((current_run/(label+'-source-after.json')).read_text(encoding='utf-8'))
    snapshot['source_changes'][label] = [path for path in before if before[path]!=after.get(path)]
manifest = json.loads((CS/'tests/test-suites.json').read_text(encoding='utf-8'))
disk = {path.relative_to(CS).as_posix() for base in ('tests','eval/tests') for path in (CS/base).rglob('test_*.py') if not {'_backup','legacy','__pycache__'} & set(path.parts)}
registered = set(manifest['common']) | set(manifest['travel'])
snapshot['manifest'] = {'disk_files':len(disk), 'registered_files':len(registered), 'common_files':len(manifest['common']), 'travel_files':len(manifest['travel']), 'missing':sorted(disk-registered), 'stale':sorted(registered-disk), 'overlap':sorted(set(manifest['common'])&set(manifest['travel'])), 'sha256':hashlib.sha256((CS/'tests/test-suites.json').read_bytes()).hexdigest()}
out = RUN/('summary_'+stamp.strftime('%H%M%S')+'.json')
if out.exists():
    raise SystemExit('동일 이름의 집계가 있습니다.')
out.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
status_path = HERE/'status.json'
backup = HERE/'_backup'/stamp.strftime('%Y-%m-%d_%H%M%S_status')
backup.mkdir(parents=True)
shutil.copy2(status_path,backup/'status.json')
status = json.loads(status_path.read_text(encoding='utf-8'))
status['changed_files'] = ['final_project_cs/tests/test-suites.json','final_project_cs/wiki/records/reports/2026-10-12_0426_baseline-verification-progress.md'] + [p.relative_to(ROOT).as_posix() for p in sorted(HERE.iterdir()) if p.is_file()]
status.update(phase='waiting_dependency',updated_at_kst=stamp.isoformat(),tests=[{'label':label, **row, 'summary_evidence':(out.relative_to(ROOT).as_posix())} for label,row in snapshot['runs'].items()],unresolved=['공통 시험 실패 19건: 과거 상태 검사 18건, 30ms 취소 시험 1건. 재현·단계 측정 근거 보존.', '첫 여행 실행은 준비 누락·격리 설정 수정 중 SQL 재적용으로 중단했습니다. 최종 판정에서 제외하고 로그를 보존했습니다.', '새 DB travel-v2는 167통과 뒤 Windows access violation 0xC0000005로 종료. 마지막 시험 단독 재현은 1통과. 최신 재개 실행으로 나머지 검증 중.', '운영 추가 시험 26통과·PGlite 명시 경로 미설정 10건너뜀. 운영 담당 격리 DB 실행 결과와 대조 필요.'],dependencies_remaining=['최신 재개 실행: 남은 여행 검증 완료와 앞선 167건의 소스 해시 재대조', 'auth: 최종 변경 목록·OAuth 실행 증거', 'orchestration: 최종 변경 목록·실행 계획·감시 접합 증거', 'operations: 최종 SQL·권한·PGlite/격리 DB 실행 증거', 'integration: 공통 실패 19건 접합·최종 소스 해시 검토'],ready_reason='비정상 종료 증거를 보존하고 남은 여행 시험을 이어 실행 중입니다. 최종 구현·해시 대조 전 전체 통과를 선언하지 않습니다.')
latest_common_label=next((label for label in reversed(sorted(snapshot['runs'])) if label.startswith('common-final-') and snapshot['runs'][label].get('state')=='finished'),'common-final-v1')
latest_common=snapshot['runs'].get(latest_common_label,{})
if latest_common.get('exit')==0:
    status['initial_common_failures_latest_status']='초기 19실패는 최신 공통 871/871 실행에서 재현되지 않았습니다. 원본 이력 보존.'
    status['unresolved']=[
        '여행 삭제: 발견 당시 운영 조회 예산·조회 시각 1행씩 잔존을 재현했습니다. 이후 통합 담당의 삭제 코드·SQL 변경을 최신 격리 DB에서 재검증해야 합니다.',
        '여행 등록: 추가 이동 항목으로 고객 고정 사전 비교 실패 및 선택 장소 등록 422가 발생했습니다. 진행 JSONL·단독 재현 보존.',
        '여행 전체 실행은 Windows 비정상 종료 이력을 보존하고 최신 재개 실행으로 계속합니다. 앞선 167건은 별도 최신 코드 재검증 167통과를 확인했습니다.',
        '예약 정보 보호 기대 2건은 D-020 고객 고정 계약과 충돌합니다. 결과 표지 없는 감시 실패 통지 1건도 최신 코드 재현·계약 검토가 필요합니다.',
        '식당 자료가 비어 있어 여행 시험 5건 건너뜀. 실제 자료 전체 검증으로 합산하지 않습니다.',
        '운영 담당 기록은 실제 호출부 접합 대기입니다. 이후 통합 담당의 진단 재전송·worker 변경 증거를 대조해야 하며 설정 저장 통과를 기능 전체 완료로 쓰지 않습니다.'
    ]
    status['dependencies_remaining']=[
        '최신 재개 여행 실행 완료·실패·건너뜀 집계와 소스 변경 영향 재검증',
        '통합 담당: 여행 삭제 정리 누락 및 이동 삽입·등록 검사 접합',
        '운영·Dining·통합 담당: 실제 호출 정책·공통 진단·재전송 접합',
        '통합 담당: 담당별 계약·현재 소스·배포 상태 최종 검토'
    ]
    status['ready_reason']='공통 전체 완료 실행 871/871 통과를 보존합니다. 이후 재검증 835통과 뒤 Windows 비정상 종료·남은 56/56 통과는 분리 실행입니다. 여행 실패·자료 전제·운영 접합의 최신 검토 전 통합 준비 완료로 올리지 않습니다.'
    if latest_common_label=='common-final-v4':
        status['ready_reason']=f"최신 공통 전체 {latest_common.get('counts',{}).get('passed',0)}건 통과. 여행 전체의 최초 실패·자료 전제를 보존하며 최신 변경 재검증과 운영 접합의 최종 검토를 기다립니다."
    if snapshot['runs'].get('travel-v3c',{}).get('state')=='finished':
        status['travel_completed_summary']=snapshot['runs']['travel-v3c']
        status['unresolved'].append('여행 재개분 종료: 6662통과·49실패·20준비 오류·15건너뜀. 최신 수정 선택 재검증과 자료 적재 전제의 확인을 분리해 진행합니다.')
status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'summary':str(out),'runs':{key:{k:v for k,v in row.items() if k not in ('failed_nodeids','setup_teardown_errors')} for key,row in snapshot['runs'].items()},'manifest':snapshot['manifest'],'source_changes':snapshot['source_changes']},ensure_ascii=False,indent=2))
