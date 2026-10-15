"""현재 구성과 남은 인수 조건을 새 스냅샷으로 남깁니다. 완료로 승격하지 않습니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, json, re, shutil, os

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
now=datetime.now(ZoneInfo('Asia/Seoul'))
stamp=now.strftime('%Y-%m-%d_%H%M%S')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
backup=HERE/'_backup'/(stamp+'_final_review_snapshot')
def write(p,s):
    b=backup/p.relative_to(ROOT);b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
    p.write_text(s,encoding='utf-8')

summary_path=max((HERE/'checks').glob('suite-review-*.json'))
summary=read(summary_path)
assert summary['latest_per_test_counts']==dict(passed=7827,skipped=7,failed=2,error=14)
paths=('wiki','final_project_cs/wiki','final_project_cs/app','final_project_cs/tests','final_project_cs/eval',
       'final_project_cs/config','final_project_cs/deploy','final_project_cs/scripts','final_project_cs/knowledge',
       'final_project_cs/prompts','final_project_cs/frontend/apps/web/src','final_project_cs/frontend/apps/web/tests','program/scripts/tests')
excluded={'_backup','__pycache__','node_modules','.git','legacy','records','test-results','playwright-report','coverage'}
extensions={'.md','.py','.sql','.json','.yaml','.yml','.sh','.ts','.tsx','.mjs','.cjs','.toml'}
files={}
for base in paths:
    for directory,dirs,names in os.walk(ROOT/base):
        dirs[:]=[d for d in dirs if d not in excluded and not d.startswith('.next')]
        for name in names:
            p=Path(directory)/name
            if p.suffix in extensions:files[p.relative_to(ROOT).as_posix()]=sha(p)
for rel in ('.gitignore','AGENTS.md','README.md','final_project_cs/AGENTS.md','final_project_cs/RULE.md','final_project_cs/frontend/apps/web/package.json','final_project_cs/frontend/apps/web/package-lock.json','final_project_cs/frontend/apps/web/playwright.config.ts','program/scripts/check_wiki.py','program/scripts/build_wiki_catalogs.py','program/scripts/_domain_coupling.py','program/scripts/migration_scope.py'):
    p=ROOT/rel
    if p.is_file():files[rel]=sha(p)
v11=ROOT/'program/plan/A-COP_구현계획서_v11.md'
assert sha(v11)=='f4ad43d9154d723d13c816d42a8bf54b78491d3f706d76a08dade79795e9dca9'
delta=[]
for run in summary['runs'][:2]:
    old=read(ROOT/run['path']/'source-after.json')
    changed=[k for k,v in old.items() if sha(ROOT/'final_project_cs'/k)!=v]
    delta.append(dict(run=run['label'],changed_since_run=changed,limit='후속 단독4·DB/보안/계약404·이력14·OAuth8 재시험 원본에 연결'))
manifest=HERE/('current-review-manifest-'+stamp+'.json')
manifest.write_text(json.dumps(dict(at_kst=now.isoformat(),scope='현재 작업 트리 순차 관측. 최종 인수·동결·운영 배포 증거 아님',source_scope=paths,files=files,v11_sha256=sha(v11),suite_review=summary_path.relative_to(ROOT).as_posix(),suite_review_sha256=sha(summary_path),source_delta=delta,excluded='백업·기록·legacy·설치 패키지·실제 datasets·비밀 환경 파일·가중치·생성 빌드'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

reports={p.parent.name:dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in HERE.parent.glob('*/report.md')}
owner_states={p.parent.name:read(p)['phase'] for p in HERE.parent.glob('*/status.json')}
table=read(HERE/'integration-table.json')
remaining={
'W02':'실제 개인 AI 종단 연결·실자료 화면/응답 인수',
'W03':'실제 분류 모델·원격 실행 품질; 검색·실자료 전제',
'W04':'실제 클라이언트 사전 등록·정확한 callback·공개 HTTPS/쿠키·종단 연결',
'W05':'실제 운영 영속 볼륨·재시작 적용 인수',
'W06':'격리 전체·후속 장애 회귀 확인; 실제 환경 적용 별도',
'W07':'원본 게시·감지 지연 실측; 실경보 방향 실패18건의 고객 경로·공식 링크 대응',
'W08':'한 여행 감시 묶음의 실제 모델·원격 A2A; 일반 채팅 분해와 범위 구분',
'W09':'무료 관측 대상 충족률·가격 조회 별도 결정·환경 인수',
'W11':'필수 자료·실자료·외부 종단·환경 인수 미충족; 검토본 유지',
'W12':'보안92·계약283·후속404 확인; 실제 외부 종단은 별도',
'W13':'전체 고유7850 대조; 후속7827통과·검색 전제16·자료 건너뜀7 남음',
'W14':'현재 안전 SQL·DB 준비23 재시험 확인; 업무 DB 적용 미수행',
'W15':'학습 여부·자료/모델 판본 연결; 독립 제품 평가·채택 증거 별도',
'W18':'신규 기능의 환경별 SQL·정책·영속 볼륨 적용 인수 미확인',
'W19':'ignore 대표4/4; 기존 추적57개 인덱스 검토 별도',
'W24':'제품 미사용 유지; 별도 연구 조건·권한과 분리',
}
for row in table['rows']:
    row['owner_phases']={owner:owner_states[owner] for owner in row['owners'] if owner in owner_states}
    for ev in row['document_evidence']:
        p=ROOT/ev['path'];ev['previous_observed_sha256']=ev.get('sha256');ev['exists']=p.is_file();ev['sha256']=sha(p) if p.is_file() else None
        ev['changed_since_input']=ev['sha256']!=ev.get('input_sha256')
    row['current_owner_reports']=[reports[o] for o in row['owners'] if o in reports]
    row['validation_review']='whole_original_and_scoped_reruns_reviewed'
    row['remaining_current']=remaining.get(row['id'],row.get('remaining_current','담당 범위 확인'))
table.update(captured_at_kst=now.isoformat(),phase='local_integration_reviewed_external_data_acceptance_pending',latest_dependency_phases=owner_states,latest_manifest=manifest.relative_to(ROOT).as_posix(),latest_suite_review=summary_path.relative_to(ROOT).as_posix(),warning='문서·담당 범위 확인은 제품 인수 완료가 아님. 단일 전체 통과 실행으로 합산하지 않음.')
write(HERE/'integration-table.json',json.dumps(table,ensure_ascii=False,indent=2)+'\n')
labels={'document_scope_verified':'문서 범위 확인','scoped_review_only':'담당 범위 확인','partial_pending_final_acceptance':'최종 인수 대기'}
lines=['# 25개 항목 통합 검토표','',f'관측: {now.isoformat()}. wiki 정본을 따르며 필수 외부·자료 조건은 남습니다.','', '| 항목 | 요구 | 현재 검토 | 남은 조건 |','|---|---|---|---|']
for row in table['rows']:lines.append(f"| {row['id']} | {row['subject']} | {labels.get(row['acceptance'],row['acceptance'])} | {row['remaining_current']} |")
lines+=['','## 원본 근거','']+[f"- [{k} 담당 보고서](../{k}/report.md): SHA-256 `{v['sha256']}`." for k,v in reports.items()]
lines+=['',f'[전체·후속 원본 대조]({summary_path.relative_to(HERE).as_posix()}), [현재 구성]({manifest.name}), [상세 판정](integration-table.json), [이전 표 백업]({backup.relative_to(HERE).as_posix()}/).']
write(HERE/'integration-table.md','\n'.join(lines)+'\n')

baseline=ROOT/'program/baseline/triPilot-baseline-2026-10-12.md'
b=baseline.read_text(encoding='utf-8')
b=re.sub(r'구성 관측은 \*\*[^*]+\*\*','구성 관측은 **'+now.strftime('%Y-%m-%d %H:%M:%S KST')+'**',b)
b=re.sub(r'current-review-manifest-2026-10-12_\d{6}\.json',manifest.name,b)
b=re.sub(r'[\d,]+파일 SHA-256',f'{len(files):,}파일 SHA-256',b)
b=b.replace('현재 wiki·앱·시험·평가·설정·SQL·배포 정의·지식 문서·고객 웹 소스','현재 wiki·앱·시험·평가·설정·SQL·배포 정의·지식/문구틀·고객 웹 소스/시험·문서 검사 도구')
b=b.replace('records1338개','records1339개').replace('2026-10-12_0626_wiki.json','2026-10-12_0645_wiki.json')
anchor='선택 실행끼리 중복이 있으므로'
if '[고유 시험별 후속 대조]' not in b:
    b=b.replace(anchor,f"[고유 시험별 후속 대조](../research/baseline_completion_2026-10-12/tasks/integration/{summary_path.relative_to(HERE).as_posix()})는 **7,827/7,850 = 99.71% 통과**, 검색 자료 전제16개와 요식·이동 자료 건너뜀7개를 남깁니다. 수집 때 생성한 UUID를 쓰는 OAuth 고객 불일치 사례 하나만 사례 종류로 정규화했습니다. 단일 전체 실행의 통과 수가 아닙니다. 여행 전체의 DB 차단12회·외부 또는 기존 로컬 서비스 연결 차단4회도 원본으로 보존합니다.\n\n"+anchor)
write(baseline,b)
state=read(HERE/'status.json')
state.update(updated_at_kst=now.isoformat(),latest_review_manifest=manifest.relative_to(ROOT).as_posix(),source_manifest_sha256=sha(manifest),backup=backup.relative_to(ROOT).as_posix())
write(HERE/'status.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(manifest=manifest.relative_to(ROOT).as_posix(),files=len(files),source_delta=delta,backup=backup.relative_to(ROOT).as_posix()),ensure_ascii=True))
