"""초기 스냅샷을 보존하고 담당 상태·원본 증거·현재 해시를 다시 연결한다."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib, json, shutil, subprocess, sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8')
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
now=datetime.now(ZoneInfo('Asia/Seoul'))
stamp=now.strftime('%Y-%m-%d_%H%M%S')
backup=HERE/'_backup'/(stamp+'_current_reconciliation')
backup.mkdir(parents=True)
for name in ('integration-table.json','integration-table.md','status.json','report.md'):
    shutil.copy2(HERE/name,backup/name)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
states={p.parent.name:json.loads(p.read_text(encoding='utf-8')) for p in HERE.parent.glob('*/status.json')}
reports={p.parent.name:dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)
         for p in HERE.parent.glob('*/report.md')}
table=json.loads((HERE/'integration-table.json').read_text(encoding='utf-8'))
remaining={
'W02':'실제 개인 AI 종단 연결과 최신 화면/응답 조립 인수',
'W03':'실제 분류 모델·원격 실행 품질과 전체 여행 회귀',
'W04':'실제 클라이언트 사전 등록·정확한 callback·공개 HTTPS/쿠키·종단 연결',
'W05':'최신 여행 전체 회귀·실제 운영 볼륨/적용 인수',
'W06':'선택 장애 격리 검증 이후 최신 전체 회귀',
'W07':'원본 게시·캐시·감지 지연 실측과 실경보 방향 판정 실패 검토',
'W08':'한 여행 감시 묶음의 실제 모델 품질·원격 A2A; 일반 채팅 분해와 범위 구분',
'W09':'실제 무료 관측 대상 충족률·가격 조회 별도 결정 대조·환경 인수',
'W11':'최신 여행 전체·최종 관문·자료/외부 조건 판정 후 완료본 확정',
'W12':'권한·팀 도구·적용 경계의 최신 전체 회귀',
'W13':'최신 여행 전체 종료와 공통/여행 수집 목록의 정확한 대조',
'W14':'현재 SQL 최종 해시 대조; 업무 DB 적용은 미수행',
'W15':'실험 판본·학습 여부·독립 평가와 환경별 채택 증거 대조',
'W18':'환경별 코드·DB·모니터링·모델 시점 대조; 신규 기능 운영 적용 미확인',
'W19':'ignore 규칙 4/4 확인; 이미 추적 중인 57개는 인덱스 검토 별도',
'W24':'제품 미사용 유지; 별도 연구 대조의 조건·권한과 분리',
}
scoped={'W16','W20','W22','W23','W25'}
document={'W01','W10','W17','W21'}
for row in table['rows']:
    row['owner_phases']={owner:states[owner]['phase'] for owner in row['owners'] if owner in states}
    for ev in row['document_evidence']:
        p=ROOT/ev['path'];ev['previous_observed_sha256']=ev.get('sha256')
        ev['exists']=p.is_file();ev['sha256']=sha(p) if p.is_file() else None
        ev['changed_since_input']=ev['sha256']!=ev.get('input_sha256')
    row['current_owner_reports']=[reports[o] for o in row['owners'] if o in reports]
    row['implementation_review']='current_source_and_handoff_linked'
    row['validation_review']='latest_whole_travel_pending'
    row['acceptance']='document_scope_verified' if row['id'] in document else 'scoped_review_only' if row['id'] in scoped else 'partial_pending_final_acceptance'
    row['remaining_current']=remaining.get(row['id'],'담당 문서·검사 범위 확인; 제품 기능 인수와 구분')
    row['deployment']='not_deployed_by_this_task'
table.update(captured_at_kst=now.isoformat(),phase='implementation_integrated_final_validation_running',
             latest_dependency_phases={k:s['phase'] for k,s in states.items()},
             warning='담당 원보고서는 과거 관측으로 보존. 이 표의 후속 접합 판정과 구분하며 전체 완료를 뜻하지 않음.')
(HERE/'integration-table.json').write_text(json.dumps(table,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# 25개 항목 통합 검토표','',f'확인 시각: {now.isoformat()}. 현재 사양은 wiki이며 이 표는 제품 인수 완료표가 아닙니다.','',
'| 항목 | 요구 | 현재 검토 | 남은 조건 |','|---|---|---|---|']
labels={'document_scope_verified':'문서 범위 확인','scoped_review_only':'담당 범위 확인','partial_pending_final_acceptance':'최종 인수 대기'}
for r in table['rows']:
    lines.append(f"| {r['id']} | {r['subject']} | {labels[r['acceptance']]} | {r['remaining_current']} |")
lines+=['','## 원본 근거','']
for k,p in reports.items():lines.append(f"- [{k} 담당 보고서](../{k}/report.md): SHA-256 `{p['sha256']}`. 담당 범위와 관측 시각의 원본입니다.")
lines+=['','통합 후속 근거: [개인정보·218 회귀](../../../../../final_project_cs/wiki/records/reports/2026-10-12_0552_privacy-regression-integration.md), [최초 진단·268 회귀](../../../../../final_project_cs/wiki/records/reports/2026-10-12_0603_initial-diagnostics-integration.md), [현재 기계 판독 표](integration-table.json).','',
        f'[이전 표 백업]({backup.relative_to(HERE).as_posix()}/). 다른 담당 상태 파일과 coordination.json은 수정하지 않았습니다.']
(HERE/'integration-table.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
evidence=[]
for folder in ('2026-10-12_054657_390668_isolated_integration','2026-10-12_055733_173846_isolated_integration','2026-10-12_055926_851705_isolated_integration'):
    run=HERE/'checks'/folder
    cases=ET.parse(run/'junit.xml').getroot().findall('.//testcase')
    counts=dict(total=len(cases),failed=sum(c.find('failure') is not None for c in cases),errors=sum(c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
    counts['passed']=counts['total']-counts['failed']-counts['errors']-counts['skipped']
    result=json.loads((run/'result.json').read_text())
    clean=json.loads((run/'cleanup.json').read_text())
    assert result['source_changed']==[] and clean['own_cluster_stopped']
    evidence.append(dict(path=(run/'junit.xml').relative_to(ROOT).as_posix(),sha256=sha(run/'junit.xml'),**counts,
                         source_changed=result['source_changed'],external_attempts=len(result['network_blocks']),own_cluster_stopped=True))
manifest={}
excluded={'_backup','__pycache__','node_modules','.git','legacy','records'}
for base in ('wiki','final_project_cs/wiki','final_project_cs/app','final_project_cs/tests','final_project_cs/eval','final_project_cs/config','final_project_cs/deploy','final_project_cs/scripts','final_project_cs/knowledge','final_project_cs/frontend/apps/web/src'):
    for p in (ROOT/base).rglob('*'):
        if p.is_file() and not excluded.intersection(p.relative_to(ROOT).parts) and p.suffix in ('.md','.py','.sql','.json','.yaml','.yml','.sh','.ts','.tsx','.mjs'):
            manifest[p.relative_to(ROOT).as_posix()]=sha(p)
v11=ROOT/'program/plan/A-COP_구현계획서_v11.md'
assert sha(v11)=='f4ad43d9154d723d13c816d42a8bf54b78491d3f706d76a08dade79795e9dca9'
snapshot=HERE/('current-review-manifest-'+stamp+'.json')
snapshot.write_text(json.dumps(dict(at_kst=now.isoformat(),scope='순차 관측; 최종 동결·제품 인수 아님',files=manifest,v11_sha256=sha(v11),evidence=evidence),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state=states['integration']
state.update(updated_at_kst=now.isoformat(),phase='waiting_dependency',latest_review_manifest=snapshot.relative_to(ROOT).as_posix(),
dependencies_remaining=['최신 여행 전체 회귀 실행 중','실제 개인 AI 등록·종단 연결','여행 검색 자료 전제16개·요식/택시 자료·무료 관측 충족률 확인','최종 보안/계약/관문·문서/HTML·해시 검증'],
unresolved=['최종 v12·전체 기준선 인수 전 검토본','W19 ignore 예외 정리; 기존 추적57개 인덱스는 미변경','실경보 방향 판정 실패18건·실사용 택시 오차는 원본 검토 대상','초기 분류/라우팅 진단 포함268 통과; 최신 공통892통과12건너뜀; 여행 전체 진행 중'],backup=backup.relative_to(ROOT).as_posix())
state['tests']+=evidence[1:]
state['changed_files']=sorted(set(state['changed_files'])|{Path(__file__).relative_to(ROOT).as_posix(),snapshot.relative_to(ROOT).as_posix(),'.gitignore',
 'program/plan/triPilot_구현계획서_v12.md','final_project_cs/wiki/records/reports/2026-10-12_0603_initial-diagnostics-integration.md'})
(HERE/'status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (HERE/'report.md').open('a',encoding='utf-8') as f:
    f.write(f'\n## {now.isoformat()} 최신 공통·진단·자료 제외 정합화\n\n최초 진단268/268, 최신 공통892통과·12건너뜀(총904). 소스 불변·전용 DB 종료 확인. 여행 전체 실행 중. W19 ignore 예외 제거4/4, 기존 추적57개 미변경. v12 본문은 최종 인수 전 검토본으로 작성했습니다. [{snapshot.name}]({snapshot.name}), [이전 표 백업]({backup.relative_to(HERE).as_posix()}/).\n')
print(json.dumps(dict(rows=len(table['rows']),source_files=len(manifest),snapshot=snapshot.relative_to(ROOT).as_posix(),evidence=evidence),ensure_ascii=False))
