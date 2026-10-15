"""실제 문서 변경·백업·검사 결과로 v3 검토 화면을 만든다."""
from pathlib import Path
from datetime import datetime
import hashlib, html, json, os, shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
STAMP=datetime.now().strftime('%Y-%m-%d_%H%M%S_%f')+'_v3-render'

def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
def save(path,text):
    if path.exists():
        b=path.parent/'_backup'/STAMP/path.name;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,b)
    path.write_text(text.rstrip()+'\n',encoding='utf-8')
def href(path):return os.path.relpath(ROOT/path,HERE).replace('\\','/')
def link(path,label):return f'<a href="{html.escape(href(path),quote=True)}">{html.escape(label)}</a>'

events=[]
for name in ['applied-current-facts-v3.json','applied-governance-v3.json','applied-final-review-v3.json','applied-close-v3.json']:
    events.extend(read(name)['changes'])
events.extend(read('additional-backups-v3.json'))
events.extend([read('state-generator-backup-v3.json'),read('root-router-backup-v3.json')])
for s in ['program/scripts/build_wiki_catalogs.py','program/scripts/tests/test_wiki_governance.py','final_project_cs/wiki/data/migration-inventory.generated.md','final_project_cs/wiki/quality/invariant-summary.generated.md','final_project_cs/wiki/runtime/case-state-machine.generated.md']:
    events.append(dict(path=s,backup=None,before_sha256=None))
# The state diagram output was backed up by its generator.
state_backups=sorted((ROOT/'final_project_cs/wiki/runtime/_backup').glob('*_state-diagram/case-state-machine.generated.md'))
if state_backups:
    events[-1]['backup']=state_backups[-1].relative_to(ROOT).as_posix()
    events[-1]['before_sha256']=hashlib.sha256(state_backups[-1].read_bytes()).hexdigest()

by_path={};backup_checks={}
for c in events:
    p=ROOT/c['path'];assert p.exists(),c['path']
    b=c.get('backup')
    if b:
        assert (ROOT/b).exists(),b
        digest=hashlib.sha256((ROOT/b).read_bytes()).hexdigest()
        assert digest==c['before_sha256'],b
        backup_checks[b]=digest
    if c['path'] not in by_path:by_path[c['path']]=dict(path=c['path'],backups=[])
    if b and b not in by_path[c['path']]['backups']:by_path[c['path']]['backups'].append(b)
for c in by_path.values():c['sha256']=hashlib.sha256((ROOT/c['path']).read_bytes()).hexdigest()

audit=read('wiki-check-v3-verified.json')
assert audit['total_violations']==0
complete={'W01','W10','W14','W15','W16','W17','W19','W21','W22','W23','W25'}
partial={'W07','W08','W20'}
notes={
'W01':'루트·cs 작업 규칙과 문서 입구를 wiki 정본으로 통일했습니다. 옛 계획 기록은 보존했습니다.',
'W07':'3분 실행 주기와 300초 캐시를 구분했습니다. 원본 공표 지연·실제 최신성·호출 예산 측정은 남았습니다.',
'W08':'TeamRegistry·실행 계약·WatchBatch·watch_planners를 현재 이름과 책임으로 고쳤습니다. 전체 처리 시나리오의 인수 검증은 별도입니다.',
'W10':'평가 입구·골든·절차 안내를 여행 자료로 연결했습니다. 쇼핑몰 수치·표본 분석은 기록으로 보존했습니다.',
'W14':'여행 데이터 안내·스키마 안내·SQL 적용 안내를 다시 썼습니다. 실행 대상 89개·보류 1개를 자동 집계하며 DB 적용 수와 구분했습니다.',
'W15':'현재 학습 안내를 cs 모델 평가 정본으로 연결하고, 과거 Qwen 쇼핑몰 학습 실험을 records에 분리했습니다.',
'W16':'개발 담당과 에이전트 팀을 구분하고 instances 경로로 수정했습니다. 사람 배치는 README를 참조하며 새 담당자를 배정하지 않았습니다.',
'W17':'오늘 표시와 옛 쇼핑몰 작업표를 분리했습니다. 기존 최종 발표일과 문서 정비 순서만 남겼으며 새 마감일은 만들지 않았습니다.',
'W19':'datasets 전체 Git 제외와 README·REPORT 우선 규칙으로 수정했습니다.',
'W20':'문서 검토 상태·기존 결정 채택 표시·기존 구현 표시를 분리했습니다. 모든 기능의 실제 구현·배포 상태를 재검증한 것은 아닙니다.',
'W21':'확인된 깨진 경로 3곳을 고쳤습니다. 파일을 찾지 못한 옛 체크리스트는 미확보로 표시하고 현재 계약으로 연결했습니다.',
'W22':'현재·생성물·기록·백업·이관 폴더를 분리하고 실제 깨진 링크는 실패하게 했습니다. 전체 결과를 JSON으로 저장합니다.',
'W23':'기존 ARCH-007 시험을 카탈로그에 연결하고 등록 72개를 자동 집계했습니다. 등록 수를 시험 통과 수로 표시하지 않습니다.',
'W25':'감시 결정·모델 비교·에이전트 팀 안내 등의 현재 결론과 시점별 기록을 분리했습니다. 옛 본문과 링크를 보존했습니다.',
}
findings=read('findings-v2.json')['findings']
for f in findings:
    f['application_status']='complete' if f['id'] in complete else 'partial' if f['id'] in partial else 'pending'
    f['application_note']=notes.get(f['id'],'설계·제품 정책 또는 코드 정합성 확인이 필요한 항목입니다. 기존 검토안의 추천과 사용자 지시를 바탕으로 후속 검토합니다. 이번 사실·형식 정정만으로 해결 처리하지 않았습니다.')
    f['applied_files']=[c['path'] for c in by_path.values() if any(c['path']==e['path'] and f['id'] in e.get('findings',[]) for e in events)]

payload=dict(updated_at=datetime.now().isoformat(),scope='문서 사실 정정·작성 지침 정리. 제품 구현 완료나 전체 사실 검증을 뜻하지 않음',complete=sorted(complete),partial=sorted(partial),findings=findings,files=list(by_path.values()),backups=backup_checks,audit=audit['scope'],warnings=audit.get('warnings',{}),checks={'wiki_violations':0,'governance_regressions':'3/3','state_diagram_tests':'2/2','catalog_generation':'일치','state_generation':'일치'})
save(HERE/'findings-v3.json',json.dumps(payload,ensure_ascii=False,indent=2))

labels={'complete':'문서 정정 완료','partial':'일부 정정·검증 남음','pending':'설계·정합성 검토 남음'}
cards=[]
for f in findings:
    files=f['applied_files']
    if f['id'] in {'W22','W23'}:files+=['program/scripts/check_wiki.py'] if f['id']=='W22' else ['final_project_cs/wiki/quality/invariant-summary.generated.md']
    links=' · '.join(link(s,Path(s).name) for s in dict.fromkeys(files))
    if not links:links=f'<a href="wiki-review-v2.html#{html.escape(f["id"])}">기존 검토안 보기</a>'
    cards.append(f'''<article data-state="{f['application_status']}" id="{f['id']}"><div class="meta"><b>{f['id']}</b><span class="badge {f['application_status']}">{labels[f['application_status']]}</span></div><h3>{html.escape(f['title'])}</h3><p>{html.escape(f['application_note'])}</p><div class="links">{links}</div></article>''')
file_rows=[]
for c in sorted(by_path.values(),key=lambda x:x['path']):
    backup_links=' · '.join(link(b,'원본 '+str(i+1)) for i,b in enumerate(c['backups'])) or '새 파일'
    file_rows.append(f'<tr><td>{link(c["path"],c["path"])}</td><td>{backup_links}</td></tr>')
checked=sum(audit['scope'].get(k,0) for k in ['current_documents','generated_documents'])
warning='예약 인계 안내 303줄: 300~500줄은 기존 지침상 분할 검토 경고입니다. 단일 예약 인계 개념으로 검토했고 임의로 쪼개지 않았습니다.'
page='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>triPilot · wiki 수정 결과 · v3</title><style>
:root{font-family:"Malgun Gothic",Arial,sans-serif;color:#18302b;background:#f5f7f5;line-height:1.65;word-break:keep-all}*{box-sizing:border-box}body{margin:0}main{max-width:1100px;margin:auto;padding:40px 28px 80px}header{border-bottom:2px solid #18302b;padding-bottom:24px}h1{font-size:32px;letter-spacing:-1px;margin:6px 0 12px}h2{font-size:22px;margin-top:36px}h3{font-size:18px;line-height:1.5;margin:12px 0}p{margin:10px 0}.eyebrow{font-size:13px;letter-spacing:1px;color:#49695e}.lead{font-size:18px}.note{border-left:4px solid #b98732;background:#fff9ef;padding:12px 16px}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:24px 0}.stat{background:#fff;border:1px solid #d1dcd5;padding:18px}.stat strong{display:block;font-size:27px}.stat small{color:#4e665b}nav{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}button{font:inherit;font-size:14px;border:1px solid #869f91;background:#fff;color:#18302b;padding:8px 12px;cursor:pointer;border-radius:4px}button[aria-pressed="true"]{background:#183f32;color:white}button:focus-visible,a:focus-visible{outline:3px solid #ad7315;outline-offset:3px}a{color:#145d48;text-underline-offset:3px;overflow-wrap:anywhere}.cards{display:grid;grid-template-columns:1fr 1fr;gap:16px}article{background:#fff;border:1px solid #d1dcd5;padding:22px;min-width:0}article p{font-size:15px}.meta{display:flex;justify-content:space-between;gap:8px;align-items:center}.badge{font-size:12px;padding:3px 8px;background:#e9eeeb;border-radius:4px}.complete{background:#dceee3;color:#1b4d32}.partial{background:#fff0d6;color:#6c4810}.links{border-top:1px solid #e4eae5;padding-top:12px;font-size:13px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;background:white;font-size:14px;table-layout:fixed}th,td{padding:10px 12px;border:1px solid #d1dcd5;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#eaf0eb}th:first-child{width:72%}details{margin-top:22px}summary{cursor:pointer;font-weight:bold;padding:10px 0}[hidden]{display:none!important}footer{margin-top:32px;color:#526b5e;font-size:13px}@media(max-width:650px){main{padding:24px 16px 48px}.cards{grid-template-columns:1fr}.summary{grid-template-columns:1fr}.stat{padding:12px 16px}.stat strong{font-size:23px}h1{font-size:27px}.meta{align-items:flex-start}th:first-child{width:65%}th,td{padding:8px;font-size:12px}}@media print{nav{display:none}.cards{display:block}article{break-inside:avoid;margin-bottom:14px}details table{display:table}body{background:#fff}}
</style></head><body><main><header><div class="eyebrow">triPilot · 2026-10-11 · 실제 반영 결과 v3</div><h1>당연한 정정은 직접 반영했습니다.</h1><p class="lead">현재 안내는 정본으로 연결하고, 옛 실험·개발 기록은 별도로 보존했습니다.</p><p>이 문서는 수정 제안 목록이 아니라 실제 문서 변경 결과입니다. 제품 정책·구현·배포가 필요한 항목은 완료로 올리지 않았습니다.</p></header>'''
page+=f'''<section class="summary" aria-label="검토 결과"><div class="stat"><strong>{len(complete)}/25 = 44%</strong><small>기존 지적 중 문서 정정 완료 · 프로젝트 진행률 아님</small></div><div class="stat"><strong>{checked}/{checked} = 100%</strong><small>현재·생성 문서 형식 검사 · 위반 0</small></div><div class="stat"><strong>{len(backup_checks)}/{len(backup_checks)} = 100%</strong><small>이번 수정의 보존 사본 해시 확인</small></div></section><p class="note">검사 통과 범위는 문서 유형·상태·태그·경로·현재 문서의 Markdown 파일 링크·불변식 연결입니다. 전체 사실·외부 API·운영 DB·배포 상태의 검증 완료를 뜻하지 않습니다.</p><h2>무엇을 바꿨나</h2><ul><li><b>데이터 안내:</b> 여행 구조와 SQL 실행 방식을 갱신했습니다. 파일 수·DB 적용 여부를 구분하고 목록을 자동 생성합니다.</li><li><b>평가·학습 안내:</b> 현재 여행 평가 정본으로 연결했습니다. 과거 쇼핑몰 Qwen 실험·골든 분포·A/B 수치를 records로 분리했습니다.</li><li><b>기존 wiki 지침:</b> 정본·이력·문서 검토 상태를 분리하고, REST 계약을 호출 주체별로 나눴습니다. 생성물은 생성기에서 고칩니다.</li></ul><p>적용 기준: {link('wiki/governance/document-standard.md','문서 작성 표준')} · {link('wiki/governance/structure-guide.md','구조 지침')} · {link('wiki/governance/front-matter.md','메타데이터 규격')} · {link('wiki/governance/review-policy.md','리뷰 정책')}</p><h2>25개 지적의 현재 상태</h2><nav aria-label="항목 상태 필터"><button type="button" data-filter="all" aria-pressed="true">전체 25</button><button type="button" data-filter="complete" aria-pressed="false">문서 정정 완료 11</button><button type="button" data-filter="remaining" aria-pressed="false">검토·검증 남음 14</button></nav><p id="filter-count" role="status" aria-live="polite">25개 표시</p><section class="cards">'''+''.join(cards)+f'''</section><h2>검사 결과와 한계</h2><ul><li>현재 문서 {audit['scope']['current_documents']}개 + 생성물 {audit['scope']['generated_documents']}개: 위반 0. 기록 {audit['scope']['record_documents']}개는 현재 규칙에서 분리했으며 기록 링크 낡음 통계는 이번에 실행하지 않았습니다.</li><li>문서 검사기 회귀 시험 3/3, 상태 전이도 생성 시험 2/2 통과. 카탈로그·상태도 재생성 결과 일치.</li><li>{html.escape(warning)}</li><li>제품 코드·SQL·DB·배포 환경은 변경하지 않았습니다. 문서 검사기·생성기만 수정했습니다.</li></ul><p>{link('program/research/wiki_review_2026-10-11/wiki-check-v3-verified.json','전체 형식 검사 결과')} · <a href="findings-v3.json">적용 상태·최종 파일 해시</a> · {link('final_project_cs/wiki/records/reports/2026-10-11_wiki-current-and-governance-v3.md','작업 보고서')}</p><details><summary>수정·신규 파일 {len(by_path)}개와 백업 위치</summary><p>기존 파일은 수정 직전 사본을 남겼습니다. 원본 링크에서 당시 내용과 비교할 수 있습니다.</p><table><thead><tr><th>파일</th><th>보존 사본</th></tr></thead><tbody>'''+''.join(file_rows)+'''</tbody></table></details><footer>v1·v2는 이전 검토안으로 보존했습니다. 현재 반영 상태는 이 v3를 기준으로 읽습니다. v12 안내서와 최종 프로젝트 베이스라인은 후속 설계 정리가 끝난 뒤 작성합니다.</footer></main><script>
for(const button of document.querySelectorAll('[data-filter]'))button.addEventListener('click',()=>{const filter=button.dataset.filter;for(const b of document.querySelectorAll('[data-filter]'))b.setAttribute('aria-pressed',String(b===button));let count=0;for(const card of document.querySelectorAll('article[data-state]')){const show=filter==='all'||(filter==='remaining'?card.dataset.state!=='complete':card.dataset.state===filter);card.hidden=!show;if(show)count++;}document.getElementById('filter-count').textContent=count+'개 표시';});
</script></body></html>'''
save(HERE/'wiki-review-v3.html',page)
save(HERE/'wiki-review-v3.md',f'''# triPilot wiki 실제 반영 결과 v3

기존 지적 25개 중 문서 정정 완료 {len(complete)}개, 일부 정정·검증 남음 {len(partial)}개, 설계·정합성 검토 남음 {25-len(complete)-len(partial)}개입니다. 프로젝트 구현 진행률이 아닙니다.

현재·생성 문서 {checked}개 형식 검사 위반 0. 검사기 회귀 3/3·상태 전이도 시험 2/2, 생성물 일치. {warning}

실제 파일·백업·해시·항목별 상태는 [검토 HTML](wiki-review-v3.html)과 [적용 목록](findings-v3.json)을 확인합니다. 전체 사실·운영 DB·배포 검증 완료를 뜻하지 않습니다.
''')
print(json.dumps(dict(files=len(by_path),backups=len(backup_checks),closed=len(complete),partial=len(partial),checked=checked,html=str(HERE/'wiki-review-v3.html')),ensure_ascii=False))
