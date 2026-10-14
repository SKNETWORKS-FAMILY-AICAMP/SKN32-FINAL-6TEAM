"""기존 경보 원본·모델 판본·환경 근거를 읽기만 하여 집계한다. 새 외부 요청 없음."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import collections
import hashlib
import json
import re
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT/'final_project_cs'
KST = ZoneInfo('Asia/Seoul')
stamp = datetime.now(KST).strftime('%Y-%m-%d_%H%M%S')
out = HERE/'runs'/('evidence_'+stamp)
out.mkdir(parents=True,exist_ok=False)
def load(path): return json.loads(path.read_text(encoding='utf-8'))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def dt(value):
    if not value: return None
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d.replace(tzinfo=KST) if d.tzinfo is None else d
    except ValueError: return None
def stats(values):
    return {'n':len(values),'min_seconds':min(values) if values else None,
            'median_seconds':statistics.median(values) if values else None,
            'max_seconds':max(values) if values else None}

sources=collections.defaultdict(lambda:{'status':collections.Counter(),'cache_age':[],'elapsed':[],'published_age':[],'cache_rows':0,'fresh_rows':0})
snapshots=[]
raw_files=[]
for path in sorted((CS/'var/alert-snapshots/real').glob('*/collection.json')):
    d=load(path); start=dt(d.get('at'))
    snap={'path':path.relative_to(ROOT).as_posix(),'sha256':digest(path),'at':d.get('at')}
    snapshots.append(snap)
    for name,source in d.get('sources',{}).items():
        s=sources[name];s['status'][source.get('status','unknown')]+=1
        raw=path.parent/source.get('raw_file',f'{name}-raw.json')
        if not raw.exists(): continue
        raw_files.append({'path':raw.relative_to(ROOT).as_posix(),'sha256':digest(raw)})
        rows=load(raw)
        if not isinstance(rows,list): continue
        received=[dt(r.get('received_at')) for r in rows if r.get('kind')=='http_body']
        received=[t for t in received if t]
        end=max(received) if received else start
        if start and end and received:s['elapsed'].append((end-start).total_seconds())
        for r in rows:
            if 'from_cache' not in r:continue
            cached=bool(r['from_cache']);s['cache_rows' if cached else 'fresh_rows']+=1
            confirmed=dt(r.get('confirmed_at'))
            # 캐시의 원 확인 시각을 회차 시작과 비교. 새 호출은 회차 시작 뒤이므로 제외한다.
            if cached and start and confirmed:s['cache_age'].append((start-confirmed).total_seconds())
        value=source.get('value')
        if name=='weather_warning' and isinstance(value,dict):
            published=dt(value.get('announced_at'))
            if end and published:s['published_age'].append((end-published).total_seconds())
gaps=[]
times=sorted(dt(x['at']) for x in snapshots if dt(x['at']))
for a,b in zip(times,times[1:]):gaps.append((b-a).total_seconds())
summary={name:{'status':dict(s['status']),'cache_rows':s['cache_rows'],'fresh_rows':s['fresh_rows'],
    'cache_age_at_round_start':stats(s['cache_age']),'round_start_to_http_receive':stats(s['elapsed']),
    'weather_announcement_to_http_receive':stats(s['published_age'])} for name,s in sources.items()}
save('monitoring.json',{'checked_at_kst':datetime.now(KST).isoformat(),'snapshots':snapshots,
    'raw_files':raw_files,'source_summary':summary,'observed_round_start_intervals':stats(gaps),
    'limits':['원본 8회차만 대상으로 한 관측 간격이며 상시 모니터링 실제 주기가 아니다.',
    '회차 시작→HTTP 수신은 앞 소스 처리·예산 대기·통신을 포함하며 단일 API 지연이 아니다.',
    '기상 announced_at만 공표 시각으로 계산. UTIC startDate/updateDate와 지하철 noftOcrnDt는 의미가 달라 공표 지연으로 계산하지 않는다.',
    '캐시 나이는 회차 시작 시점 기준. 원본 시각이 없는 사건은 추정하지 않는다.',
    '판정 완료·outbox 생성·배달 완료를 잇는 동일 사건 추적이 없어서 감지→판정→통지 지연은 미확보.',
    '스냅샷 사이 발생·해제된 사건, 페이지 범위 밖 사건, 과거 미제공 사건은 분모를 확보하지 못했다.']})

watch_path=ROOT/'program/research/daily_rag_slm/model_release_watchlist.json'
watch=load(watch_path)
versions=[{k:x.get(k) for k in ('repo_id','version','revision_sha','our_finetuning','publisher_training','status','checked_date','source_url')}
          for x in watch['candidates']]
report_path=CS/'wiki/quality/model-version-reports.md'
text=report_path.read_text(encoding='utf-8')
links=[]
for target in re.findall(r'\]\(([^)]+)\)',text):
    if target.startswith(('http:','https:','#')):continue
    p=(report_path.parent/target.split('#')[0]).resolve()
    links.append({'path':p.relative_to(ROOT).as_posix(),'exists':p.is_file(),'sha256':digest(p) if p.is_file() else None})
arm=ROOT/'program/scripts/plan_qa_bench/results/arm_stack_audit_20261012_005846/latest_soak_010914.json'
arm_data=load(arm)
runtime=[]
for short,h in arm_data['runtime_hashes'].items():
    p=CS/'app/domains/travel_ops/components'/short
    local=digest(p)
    runtime.append({'path':p.relative_to(ROOT).as_posix(),'observed_remote_sha256':h,'local_sha256':local,'matches':h==local})
save('models-environments.json', {'checked_at_kst':datetime.now(KST).isoformat(),
    'watchlist':{'path':watch_path.relative_to(ROOT).as_posix(),'sha256':digest(watch_path),'candidates':versions},
    'model_report_links':links,'arm_observation':{'path':arm.relative_to(ROOT).as_posix(),'sha256':digest(arm),
    'utc':arm_data.get('utc'),'runtime_hash_comparison':runtime},
    'scope':'기존 관측 재사용. 새 모델 학습·다운로드·추론·원격 가동 확인을 수행하지 않음.'})
print(out.relative_to(ROOT).as_posix())
print('snapshots',len(snapshots),'raw_files',len(raw_files),'sources',len(sources),'model_candidates',len(versions),'report_links',len(links),'broken',sum(not x['exists'] for x in links))
print(json.dumps(summary,ensure_ascii=False))
