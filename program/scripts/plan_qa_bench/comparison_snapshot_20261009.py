"""Saved-answer A/B/C/D/E comparison. Never starts inference or overwrites evidence."""
import hashlib, json, sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from backlog_mx_report import summarize, paired, valid

HERE=Path(__file__).resolve().parent
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
ROOT=HERE.parents[2]
RES=HERE/'results'
sys.stdout.reconfigure(encoding='utf-8')
SOURCES={}
def read(p, lines=False):
    p=Path(p); raw=p.read_bytes(); SOURCES[p.relative_to(ROOT).as_posix()]=hashlib.sha256(raw).hexdigest()
    return [json.loads(l) for l in raw.decode('utf-8-sig').splitlines() if l.strip()] if lines else json.loads(raw.decode('utf-8-sig'))

FX={s:read(Path(fixture(f'{s}.json')))['sets'][s] for s in ['mix8','mix9','mix10','mix11','mix12']}
GS=read(Path(fixture('gold_sets.json')))
GOLDS={'d':read(ROOT/'datasets/core/pointing/testset/questions_plus_chitchat_v1/all_prompts.json'), 'd2':read(ROOT/'datasets/core/pointing/testset/chitchat_only_holdout_v1/all_prompts_d2.json'),
       'd3':read(ROOT/'datasets/core/pointing/testset/synthetic_chitchat_plus_questions_v1/all_prompts_d3.json'), 'h':read(ROOT/'datasets/core/pointing/testset/confusing_trap_sentences_v1/h_set_test_30_20261015_agree.json'),
       'mx':read(ROOT/'datasets/core/pointing/testset/requests_inside_chitchat_pairs_v1/mx_main_prompts.json')}
KEYS=[(s,i) for s in FX for i in range(len(FX[s]['qs']))]
MAPPING={}
for s,i in KEYS:
    q=FX[s]['qs'][i]
    hits=[x for x in GOLDS['d'] if x['set']==s.replace('mix','mixed') and x['gold']==q['gold'] and x['type']==q['type'] and '고객 질문: '+q['q']+'\n\n' in x['prompt']]
    assert len(hits)==1, (s,i,len(hits))
    assert all(h['text'] in hits[0]['prompt'] for h in q.get('history',[])), 'Lost history'
    MAPPING[(s,i)]=hits[0]['i']
assert len(KEYS)==len(MAPPING)==len(set(MAPPING.values()))==835

def abc(picks, validity):
    stats=defaultdict(lambda:dict(total=0,A=0,B=0,C=0,false_pick=0,failed=0))
    for k in KEYS:
        want=set(GS[k[0]][str(k[1])]); p=picks.get(k) or []; ok=validity.get(k,False)
        group='compound' if len(want)==2 else 'request' if want else 'no_request'
        a=bool(ok and ((p and p[0]==FX[k[0]]['qs'][k[1]]['gold']) if want else not p))
        b=bool(ok and (bool(set(p)&want) if want else not p)); c=bool(ok and set(p)==want)
        for name in ['all',group]:
            r=stats[name];r['total']+=1;r['A']+=a;r['B']+=b;r['C']+=c;r['false_pick']+=bool(ok and not want and p);r['failed']+=not ok
    return dict(stats)

def metrics(suite,path):
    rows=read(path,True); run={r['i']:r for r in rows};gold=GOLDS[suite];refs={r['i']:r for r in gold}
    assert len(run)==len(rows) and set(run)<=set(refs)
    assert all(r['gold']==refs[i]['gold'] and r['type']==refs[i]['type'] for i,r in run.items())
    single=[x for x in gold if x['type']!='compound_intent']
    r=dict(saved=len(rows),expected=len(gold),missing=len(gold)-len(rows),failed=sum(not valid(x) for x in rows),
           positive=summarize([x for x in single if x['gold'] is not None],run),negative=summarize([x for x in single if x['gold'] is None],run),
           subtypes={t:summarize([x for x in gold if x['type']==t],run) for t in sorted({x['type'] for x in gold})},
           source=path.relative_to(ROOT).as_posix(),answer_sha256=SOURCES[path.relative_to(ROOT).as_posix()])
    if suite=='d':
        picks={k:[] if run.get(i,{}).get('pick') is None else [run[i]['pick']] for k,i in MAPPING.items()}
        validity={k:valid(run.get(i)) for k,i in MAPPING.items()};r['ABC_single_contract']=abc(picks,validity)
    if suite=='mx':
        r['by_kind']={kind:{name:summarize([x for x in gold if x['kind']==kind and (x['gold'] is not None)==pos],run) for name,pos in [('request',True),('no_request',False)]} for kind in ['control','mixed']}
        r['natural']={name:summarize([x for x in gold if x['kind']=='mixed' and x['src']=='llm' and (x['gold'] is not None)==pos],run) for name,pos in [('request',True),('no_request',False)]}
        r['mixed_subtypes']={t:summarize([x for x in gold if x['kind']=='mixed' and x['cat']==t],run) for t in sorted({x['cat'] for x in gold})}
        r['paired']={name:paired([x for x in gold if (x['gold'] is not None)==pos],run) for name,pos in [('request',True),('no_request',False)]}
        p,n=r['by_kind']['mixed']['request'],r['by_kind']['mixed']['no_request']; cn=r['by_kind']['control']['no_request']
        r['fp_increase_pp']=100*(n['false_pick']/n['total']-cn['false_pick']/cn['total'])
        r['gates']={'request_accuracy':p['correct']/p['total']>=.95,'false_pick':n['false_pick']/n['total']<=.01,'request_loss':r['paired']['request']['loss_pp']<=2,'false_pick_increase':r['fp_increase_pp']<=1}
        r['subtype_gates']={t:r['mixed_subtypes'][t]['false_pick']/r['mixed_subtypes'][t]['total']<=.03 for t in ['MX3','MX4','MX5a']}
    latency=[x['ms']/1000 for x in rows if valid(x) and isinstance(x.get('ms'),(int,float))]
    if latency:
        import numpy as np
        r['observed_latency_s']={'samples':len(latency),'p50':float(np.quantile(latency,.5)),'p95':float(np.quantile(latency,.95)),'limits':'Whole-suite calls including loads/cache conditions; not controlled same-model engine comparison'}
    return r

specs=[('Saluki-27B IQ2-mix 原本','saluki_original',False),('FrogNano-4B Q8 原本','frog',False),('Gemma E4B Q4_K_M 原本','e4bbase',False),('Gemma E4B QAT Q4_0 原本','e4bqat_original',False),('Gemma 12B Q4_K_M 原本','g12bbase',False),('Winnow-E4B Q8 原本（Jev系）','winnow_original',False),('Winnow-E4B Q8 oos（Jev系）','winnow_oos',True)]
specs=[(a.replace('原本','원본').replace('（Jev系）','(Jev 계열)'),b,c) for a,b,c in specs]
for base,label in [('e4bbase','Q4_K_M'),('e4bqat','QAT Q4_0')]:
    for method in ['cosine','finch']:specs.append((f'Gemma E4B {label} {method} s20261012',f'{base}_{method}_s20261012',True))
for tag in ['oos1','oos2','oos3','oos2r']:specs.append((f'Gemma E4B QAT Q4_0 {tag}',f'e4bqat_{tag}',True))
records=[]
for label,prefix,trained in specs:
    rec=dict(model=label,our_training=trained,role='single choice',suites={})
    for suite in GOLDS:
        job=(f'{prefix}_{suite}_a1' if prefix=='saluki_original' else f'{prefix}_{suite}')
        folder=RES/'gpu_backlog_20261008'/job
        paths=list(folder.glob('d_test*.jsonl'))
        if prefix=='frog' and suite in ['d','d2','d3']:
            paths=[RES/'d_test'/({'d':'d_test_a_frognano.jsonl','d2':'d_test_d2_frog.jsonl','d3':'d_test_d3_frog.jsonl'}[suite])]
        if len(paths)==1 and paths[0].exists():
            rec['suites'][suite]=metrics(suite,paths[0])
            st=folder/'started.json'
            if st.exists():
                execution=read(st); rec['suites'][suite]['execution']=execution
                counts=list(folder.glob('*counts.json'))
                if counts:
                    stored=read(counts[0]);assert stored['answer_sha256']==rec['suites'][suite]['answer_sha256']
    records.append(rec)
for label,tag in [('旧시드1','e4bt'),('旧시드2','e4bs2'),('旧시드3','e4bs3'),('oos1','oos1'),('oos2','oos2'),('oos3','oos3'),('oos2r','oos2r')]:
    rec=dict(model=f'Gemma E4B Q4_K_M {label.replace("旧","기존 ")}',our_training=True,role='single choice',suites={})
    patterns={'d':'d_test_lp_q4km_{}','d2':'d_test_lp_d2_q4km_{}','d3':'d_test_d3_q4km_{}','h':'d_test_lp_h_q4km_{}','mx':'d_test_lp_mx_q4km_{}'}
    for suite,pat in patterns.items():
        path=RES/'d_test'/(pat.format(tag)+'.jsonl')
        if path.exists():rec['suites'][suite]=metrics(suite,path)
    records.append(rec)

valen=dict(model='Valen-0.8B 원본 선택지 API',our_training=False,role='native choice head',suites={})
for suite in GOLDS:
    folder=RES/'gpu_backlog_20261008'/f'valen_08b_original_{suite}_a1'
    if (folder/'native_counts.json').exists():
        stored=read(folder/'native_counts.json');files=list(folder.glob('d_test*.jsonl'));assert len(files)==1
        valen['suites'][suite]=metrics(suite,files[0]);assert stored['answer_sha256']==valen['suites'][suite]['answer_sha256']
        valen['suites'][suite]['execution']=stored['execution']
if valen['suites']:records.append(valen)

multi=[]
for path in sorted((RES/'gpu_backlog_20261008').glob('*/multi_items_counts.json')):
    data=read(path);folder=path.parent;files=list(folder.glob('d_test*.jsonl'));assert len(files)==1
    rows=read(files[0],True);assert hashlib.sha256(files[0].read_bytes()).hexdigest()==data['answer_sha256']
    assert len(rows)==len({x['i'] for x in rows})==835
    prompts=read(ROOT/'datasets/travel/multi_items_eval_20261009/prompts.json'); byid={x['i']:x for x in prompts}
    from server.queues.multi_items_eval_20261009 import parse_items
    picks={};v={}
    for x in rows:
        ref=byid[x['i']];assert all(x[k]==ref[k] for k in ['set','qi','gold','gold_set','type'])
        parsed,p=parse_items(x.get('content'),set(ref['allowed_items']));good=parsed and valid(x)
        if good:assert p==x['pick']
        key=(ref['set'],ref['qi']);picks[key]=p;v[key]=good
    scores=abc(picks,v);assert scores['all']['C']==data['counts']['all']['C'] and scores['all']['B']==data['counts']['all']['B']
    multi.append(dict(model=data['model'],our_training=data['our_training'],scores=scores,source=path.relative_to(ROOT).as_posix(),execution=data['execution']))

basic=[]
for tag in ['r16e2','e4bs2','e4bs3','oos1','oos2','oos3','oos2r','e4bm','winnow_e4b','spark_s1_4b','jevify_e4b']:
    picks={};v={}
    for s in FX:
        data=read(RES/f'_pull/distill_eval/eval_{tag}_{s}.json')[tag+'#lora'];assert data['_errors']==0 and len(data['picks'])==len(FX[s]['qs'])
        for i,p in enumerate(data['picks']):picks[(s,i)]=p if isinstance(p,list) else [] if p is None else [p];v[(s,i)]=True
    basic.append(dict(model=tag,our_training=True,execution='HF 4bit adapter; historical basic evaluation',scores=abc(picks,v)))
for name,tag in [('Claude Opus 5.5','claude_claude_opus_5_5'),('Claude Fable 5.1','claude_claude_fable_5_1'),('gpt-6-luna','codexcli_gpt-6-luna'),('gpt-6-sol','codexcli_gpt-6-sol'),('gpt-6-astra','codexcli_gpt-6-astra')]:
    picks={};v={}
    for s in FX:
        data=read(RES/f'{tag}_{s}_multi.json')['rows']
        for i in range(len(FX[s]['qs'])):
            row=data.get(str(i));v[(s,i)]=row is not None and valid(row);picks[(s,i)]=row.get('picks') if row else []
    basic.append(dict(model=name,our_training=False,execution='Cloud CLI multi-item; author bias and wrapper differences',scores=abc(picks,v)))

stamp=datetime.now().strftime('%Y%m%d_%H%M%S');out=RES/f'comparison_abcde_{stamp}';out.mkdir(exist_ok=False)
def rat(n,d):return f'{n}/{d} = {100*n/d:.2f}%' if d else '—'
def metric(r,key):return rat(r[key],r['total'])
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'---|'*len(headers)]+['| '+' | '.join(map(str,row))+' |' for row in rows])
def source_link(r):return '['+r['model']+']('+str(ROOT/r['suites']['mx']['source']).replace('\\','/')+')'
md=['# Saluki와 전체 A·B·C·D·E 실측 비교',f'\n집계 시각: {datetime.now().astimezone().isoformat()}. 새 추론 호출 없이 보관 원본을 재계수했습니다.',
'\nSaluki는 E의 정상 요청에는 강하지만 요청 없는 입력의 오지목이 많아 채택 기준을 통과하지 못했습니다. 각 시험·출력 역할·양자화를 분리하며 종합 순위를 만들지 않습니다.',
'\n'+table(['할 일','상태','진행'],[['단일 선택 변형 재계수','완료',rat(len(records),len(records))],['복수 항목 역할 재계수','완료',rat(len(multi),len(multi))],['과거 HF·클라우드 역할','완료',rat(len(basic),len(basic))]]),
'\n## 채점과 분모',
'A·B·C는 별도 세트 세 개가 아니라 같은 835문항의 채점 세 가지입니다. A는 첫 번째 정답 항목과 출력 첫 항목, B는 정답 중 하나 이상, C는 전체 집합 일치를 봅니다. 정상 단일583·요청 없음186·복합66입니다. 아래 단일 선택 ABC는 D의 원래 기본835문항 부분을 질문·일정 묶음·정답·유형·앞 대화로 대조해 재계수했습니다. 복수 선택 역할은 별도 지시문으로 실행했으므로 섞지 않습니다.',
'D는 전체2735 중 복합66을 제외한 정상883·요청 없음1786입니다. D2는 요청 없음1000, D3는 정상120·요청 없음240, H는 정상461·함정855입니다. E는 MX: 혼합2007(정상1033·요청 없음974)+대조2007입니다. E 자연 평문 부분은 정상93·요청 없음146입니다.',
'\n## 단일 선택 역할 — A·B·C',
table(['모델·판','우리 추가 학습','A↑','B↑','C↑','복합 C↑','실패·미완료'],[[r['model'],'있음' if r['our_training'] else '없음',*[rat(r['suites']['d']['ABC_single_contract']['all'][k],835) for k in ['A','B','C']],rat(r['suites']['d']['ABC_single_contract']['compound']['C'],66),rat(r['suites']['d']['ABC_single_contract']['all']['failed'],835)] for r in records if 'd' in r['suites']]),
'단일 번호 출력은 복합 C가 구조상0/66입니다. 같은 기본 문항의 단일 선택 진단이며 복수 선택을 시켜 실패했다는 뜻은 아닙니다.',
'\n## 단일 선택 역할 — D와 E',
table(['모델·판','D 정상↑','D 오지목↓','E 정상↑','E 오지목↓','E 합산기준','D/E 실패·미완료'],[[r['model'],metric(r['suites']['d']['positive'],'correct'),metric(r['suites']['d']['negative'],'false_pick'),metric(r['suites']['mx']['by_kind']['mixed']['request'],'correct'),metric(r['suites']['mx']['by_kind']['mixed']['no_request'],'false_pick'),f"{sum(r['suites']['mx']['gates'].values())}/4",f"{r['suites']['d']['failed']+r['suites']['d']['missing']}/2735・{r['suites']['mx']['failed']+r['suites']['mx']['missing']}/4014"] for r in records if 'd' in r['suites'] and 'mx' in r['suites']]),
'合算基準'.replace('合算基準','합산 기준')+'은 정상≥95%, 오지목≤1%, 정상 대조 대비 손실≤2%p, 오지목 증가≤1%p입니다. 유형별 오지목≤3%도 별도 관문이라 합산4/4만으로 채택하지 않습니다.',
'\n## E — 대조 손실·자연 평문',
table(['모델·판','대조 정상↑','혼합 손실↓','오지목 증가↓','자연 정상↑','자연 오지목↓','지정 유형 기준'],[[r['model'],metric(r['suites']['mx']['by_kind']['control']['request'],'correct'),f"{r['suites']['mx']['paired']['request']['loss_pp']:+.2f}%p",f"{r['suites']['mx']['fp_increase_pp']:+.2f}%p",metric(r['suites']['mx']['natural']['request'],'correct'),metric(r['suites']['mx']['natural']['no_request'],'false_pick'),f"{sum(r['suites']['mx']['subtype_gates'].values())}/3"] for r in records if 'mx' in r['suites']]),
'혼합2007문항 중1768은 코드 연결,239는 모델이 자연 평문으로 작성했습니다. 사람 검수 및 새 독립 보류720문항 검증은 완료되지 않았습니다. 실제 고객 대화의 정확도·상용화 적합성을 증명한 결과가 아닙니다.',
'\n## D2·D3·H',
table(['모델·판','D2 오지목↓','D3 정상↑','D3 오지목↓','H 정상↑','H 함정 오지목↓','D2/D3/H 실패·미완료'],[[r['model'],metric(r['suites']['d2']['negative'],'false_pick') if 'd2'in r['suites'] else '미측정',metric(r['suites']['d3']['positive'],'correct') if 'd3'in r['suites'] else '미측정',metric(r['suites']['d3']['negative'],'false_pick') if 'd3'in r['suites'] else '미측정',metric(r['suites']['h']['positive'],'correct') if 'h'in r['suites'] else '미측정',metric(r['suites']['h']['negative'],'false_pick') if 'h'in r['suites'] else '미측정','・'.join(f"{r['suites'][s]['failed']+r['suites'][s]['missing']}/{r['suites'][s]['expected']}" if s in r['suites'] else '미측정' for s in ['d2','d3','h'])] for r in records]),
'\n## 복수 항목 JSON 역할 — 같은 실행 계약',
table(['모델·판','우리 추가 학습','A↑','B↑','C↑','복합 C↑','요청없음 오지목↓','실패·미완료'],[[r['model'],'있음' if r['our_training'] else '없음',*[rat(r['scores']['all'][k],835) for k in ['A','B','C']],rat(r['scores']['compound']['C'],66),rat(r['scores']['no_request']['false_pick'],186),rat(r['scores']['all']['failed'],835)] for r in multi]),
'Saluki와FrogNano의 이 복수 JSON 역할은 이번 표의 로컬 완료 결과에 포함되지 않았습니다. Gemma12B와Winnow 두 판은 누락 역할 보충 예약으로 처리 중이며 완료 값을 만들지 않습니다.',
'\n## 과거 HF 어댑터·클라우드 복수 출력 역할',
table(['모델·판','우리 추가 학습','A↑','B↑','C↑','복합 C↑','실패·미완료'],[[r['model'],'있음' if r['our_training'] else '없음',*[rat(r['scores']['all'][k],835) for k in ['A','B','C']],rat(r['scores']['compound']['C'],66),rat(r['scores']['all']['failed'],835)] for r in basic]),
'r16e2/e4bs2/e4bs3은 GemmaE4B 기존 학습 시드,oos는 잡담 보강,e4bm은 여러 항목 학습판입니다. Winnow/spark/jevify 태그는 이전 기본 학습판이며 현재 잡담 보강판으로 취급하지 않습니다. HF4비트+어댑터, GGUF, CLI 결과는 서로 실행 조건이 달라 직접 속도 순위를 정하지 않습니다. 클라우드 모델은 출제자 계열·정답키·에이전트 지시문 편향도 있습니다.',
'\n## E 유형별 전체 측정',
table(['모델·판','질문 MX1↑','변경 MX2↑','두언급 한요청 MX6a↑','일정밖 MX3 오지목↓','일정낱말잡담 MX4 오지목↓','전체변경 MX5a 오지목↓','전체감정 MX5b 오지목↓'],[[r['model'],*[metric(r['suites']['mx']['mixed_subtypes'][t],'correct' if t in ['MX1','MX2','MX6a'] else 'false_pick') for t in ['MX1','MX2','MX6a','MX3','MX4','MX5a','MX5b']]] for r in records if 'mx'in r['suites']])]

mai=read(RES/'mai_frog_final_stats_2026-10-08_040142.json')
md+=['\n## MAI指定比較'.replace('指定',' 지정 '),table(['모델(우리 학습 없음)','D3 정상↑','D3 잡담 오지목↓','맞은선택 유지↑','틀린선택 제거↑'],[[model,rat(mai['direct']['actual_request']['scores'][model]['correct'],120),rat(240-mai['direct']['chitchat']['scores'][model]['correct'],240),rat(mai['verification']['retain_correct']['scores'][model]['correct'],112),rat(mai['verification']['reject_wrong']['scores'][model]['correct'],92)] for model in ['MAI-Code-1.1-Flash','FrogNano-4B-2609']]),'검토204·직접360 완료. 같은 문항 직접요청p=.1892,잡담p=.3018,검토합계p=.0884이며 일반 우열로 확정하지 않습니다. MAI 말로 한p_yes와Frog 토큰 확률은 다른 신호입니다. MAI의 A/B/C/D전체/E는 미측정입니다.']

md+=['\n## 새 모델 완료분과 미완료 범위',table(['모델','A/B/C 단일 역할','D','D2','D3 정상↑ / 오지목↓','H 정상↑ / 오지목↓','E 정상↑ / 오지목↓'],[[r['model'],'완료' if 'd' in r['suites'] else '진행 중・집계 보류','완료' if 'd' in r['suites'] else '진행 중','완료' if 'd2' in r['suites'] else '대기',*[metric(r['suites'][s]['positive'],'correct')+' / '+metric(r['suites'][s]['negative'],'false_pick') if s in r['suites'] else '진행 중' for s in ['d3','h']],metric(r['suites']['mx']['by_kind']['mixed']['request'],'correct')+' / '+metric(r['suites']['mx']['by_kind']['mixed']['no_request'],'false_pick') if 'mx' in r['suites'] else '진행 중'] for r in records if r['role']=='native choice head']),
'Valen은 개발사가 결정 학습한 배포 원본입니다. 원본 선택지 head 확률로 한 항목/NONE을 선택하며 생성 JSON 경로와 다릅니다. 완료 세트만 보이고 미완료 전체 점수·순위는 보류합니다.',
'\n## 약속한 나머지 측정·검증의 상태',table(['측정','상태','근거·제약'],[
 ['시드 반복','기존3시드·보강3시드 완료; FINCH/cosine 두번째 시드 진행','동일 레시피 시드끼리 비교; QAT와일반은 별도'],
 ['양자화 비교','Q4_K_M/QAT Q4_0 개발시험 완료','양자화와기반모델 조건이 함께 달라 순수 양자화효과 아님; 과거Q8/Q4 같은모델 비교 별도'],
 ['확신도 보정','개발분류 ECE 등 과거 기록 있음; 현 E/Saluki 제품 경로 미검증','p_null 토큰확률·선택지head확률·말로한확신도 구분'],
 ['견고성','D/H/E 유형별 완료; 독립 말투·다국어 묶음 미완료','E 사람검수0/158; 최종 보류720 작성·검수 대기'],
 ['검토자 거부권','MAI/Frog D3 지정 완료','정상 보존·오답 제거와 직접 선택 분리'],
 ['엔진 속도·메모리','과거CPU/GPU·동시요청 및 ARM 실제시험 있음','모델 정확도 비교와 엔진 속도 비교 분리; 아래 원본 링크'],
 ['검색 회귀','10-09 고정 개발1700결정 완료; 개선 채택0','검색의 A/B는 여기 일정선택A/B와 다름'],
 ['누락 역할','Gemma12B·Winnow 원본/학습 복수JSON835씩 예약','완료 전 수치·순위 없음'],
 ['신모델','Valen0.8B 메인 진행; 기타 후보 준비','Saluki27B는 소형≤8B 조건 밖'],
 ['제품 채택·실서비스 배포','이번 결과로 승격 없음','독립 보류·회귀·지연·격리·자료/라이선스 별도 확인']]),
'\n모델 실행은 각 조건1회입니다. E의95%구간·대조짝 정확검정·일정군집2000회 부트스트랩은 JSON에 있습니다. 분모는 실패·미완료를 유지하며 실제 오지목과 형식 실패를 별도로 보입니다. 사용자가 지목한 각 시험별 비교표를 모두 모았으며 과거 모든 조합/규칙/문턱 실험은 아래 보존표를 연결합니다.',
'\n## 전체 원본·과거 표 링크',
'\n'.join('- ['+name+']('+str(ROOT/path).replace('\\','/')+')' for name,path in [('기존 모든 모델·규칙·조합 행렬','program/scripts/plan_qa_bench/results/matrix_all_mix8to12.md'),('과거 C·오프라인 문턱·조합','program/scripts/plan_qa_bench/results/c_scoring_all.txt'),('학습 시드 비교','program/scripts/plan_qa_bench/results/seed_scores.md'),('CPU4코어 원본','program/scripts/plan_qa_bench/results/cpu_eval_summary.txt'),('ARM 관측·성능 원본','program/research/daily_rag_slm/arm_serving_2026-10-09.json'),('최신 세기계 가동 관측','program/scripts/plan_qa_bench/results/utilization_check_20261009_1100/summary.json'),('E 평가셋 완성도 감사','final_project_cs/wiki/records/reports/2026-10-09_0214_e-testset-maturity-audit.md'),('검색 개발시험 원본','program/scripts/rag_gate/results/daily_20261009_selective_v1/summary.json')]),
'\n'+table(['모델·판','D','D2','D3','H','E'],[[r['model'],*[rat(r['suites'][s]['saved'],r['suites'][s]['expected']) if s in r['suites'] else '미측정' for s in GOLDS]] for r in records]),
'\n### 답안 원본', '\n'.join('- '+source_link(r) for r in records if 'mx'in r['suites']),
'\n[구조화된 전체 집계·해시·반복·실행 버전](snapshot.json)']
output=dict(observed_at=datetime.now().astimezone().isoformat(),definitions=dict(A='first item',B='any gold overlap',C='exact set',E='MX mixed free-text'),single_contract=records,multi_contract=multi,historical_basic=basic,MAI_comparison=mai,source_sha256=SOURCES,fixture_mapping_verified=835,independent_holdout_complete=False,final_ranking=False)
(out/'snapshot.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'comparison.md').write_text('\n\n'.join(md)+'\n',encoding='utf-8')
print(json.dumps(dict(output=str(out),single_models=len(records),multi_models=len(multi),historical_roles=len(basic),source_files=len(SOURCES),single_summary=[dict(model=r['model'],abc=r['suites'].get('d',{}).get('ABC_single_contract'),d=r['suites'].get('d',{}).get('positive'),e=r['suites'].get('mx',{}).get('by_kind'),gates=r['suites'].get('mx',{}).get('gates')) for r in records]),ensure_ascii=False))
