"""Publish a new local comparison viewer and immutable evidence report."""
import hashlib,json,re,html,sys
from pathlib import Path
from datetime import datetime
import markdown
from comparison_snapshot_20261009 import table,rat,ROOT,RES
# Import above performs only saved-answer recount and creates a fresh snapshot.
folders=sorted(RES.glob('comparison_abcde_*'));folder=folders[-1]
s=json.loads((folder/'snapshot.json').read_text(encoding='utf-8'));records=s['single_contract']
sys.path.insert(0,str(RES.parent.parent/'eval_kit'))
from stats import mcnemar_exact
gold=json.loads((ROOT/'datasets/core/pointing/testset/requests_inside_chitchat_pairs_v1/mx_main_prompts.json').read_text(encoding='utf-8'))
pos=[x for x in gold if x['kind']=='mixed' and x['gold'] is not None]
def correctness(r):
    rows={x['i']:x for x in [json.loads(l) for l in (ROOT/r['suites']['mx']['source']).read_text(encoding='utf-8').splitlines()]}
    return [bool(rows.get(x['i'],{}).get('parsed') and not rows[x['i']].get('error') and rows[x['i']]['pick']==x['gold']) for x in pos]
saluki=next(r for r in records if r['model'].startswith('Saluki'));g12=next(r for r in records if r['model'].startswith('Gemma 12B'))
pair=mcnemar_exact(correctness(saluki),correctness(g12))
arm_path=ROOT/'program/research/daily_rag_slm/arm_serving_2026-10-09.json';arm=json.loads(arm_path.read_text(encoding='utf-8'))
gpu_path=RES/'_pull/bench/conc_bench_A_gpu_taught.json';gpu=json.loads(gpu_path.read_text(encoding='utf-8'))
extra=['\n## Saluki 해석과 같은 문항 비교',
f"Saluki는 우리 자료 추가 학습 없이 E 정상997/1033으로 완주 원본6판(기반모델5종)의 관측 점수가 가장 높습니다. Gemma12B993/1033보다4개 많고 같은 문항 Saluki만/12B만 정답은{pair['a_only']}/{pair['b_only']}개, 정확검정p={pair['p']:.6f}입니다. 이는 양자화·모델크기 차이가 있는 개발시험1회이며 통계적 일반 우열을 뜻하지 않습니다. Saluki의95% Wilson 정상 구간은95.21~97.47%, E 오지목 구간은13.94~18.56%입니다. 더 작은Winnow-E4B 우리 학습판은 정상1000/1033·오지목20/974로 다른 균형을 보입니다.",
'Saluki는27B이므로 작업 기준 소형 약8B 이하에 속하지 않습니다. 우리 학습 없음은 사전학습만 한 Base라는 뜻이 아닙니다. 개발사 학습된 배포판의 특정 IQ2-mix 추론 결과입니다.',
'\n## 실행 중 기록된 지연 — E 유효 답안만',
table(['모델·판','지연 표본/전체','중앙값 p50(초)','느린쪽 p95(초)','오류·해석실패/전체'],[[r['model'],rat(r['suites']['mx']['observed_latency_s']['samples'],4014),f"{r['suites']['mx']['observed_latency_s']['p50']:.3f}",f"{r['suites']['mx']['observed_latency_s']['p95']:.3f}",rat(r['suites']['mx']['failed'],4014)] for r in records if r['suites'].get('mx',{}).get('observed_latency_s')]),
'각 판의 보관 답안ms에서 계산한 유효응답 지연입니다. 정확도 분모는 실패·미완료를 포함합니다. 지연 표본에서는 ms가 있는 유효답안만 표시하며 실패 응답 지연이 빠질 수 있습니다. 여행별 캐시·로드·기계경쟁·프롬프트·엔진이 통제된 A/B 속도 실험이 아니므로 빠른 엔진 순위나 시간당 상용 처리량으로 읽지 않습니다.',
'\n## 실제 CPU·GPU·동시 요청 측정',
table(['조건','정확도 또는 표본','중앙/평균 지연','p95 또는 실측 처리 간격','제약'],[
 ['Oracle ARM 2코어 Q4_K_M D3','정상107/120; 오지목29/240; 오류0/360',f"{arm['completed_Q4_D3']['latency_after_first_median_s']:.2f}초 (첫건 제외 중앙)",f"{arm['completed_Q4_D3']['latency_p95_upper_order_s']:.2f}초",'기존 합친 학습판・정확 레시피 미대조・직렬1회'],
 ['Oracle ARM 2코어 Q8 D3','정상106/120; 오지목31/240; 오류0/360',f"{arm['completed_Q8_D3']['latency_p50_s']:.2f}초 중앙",f"{arm['completed_Q8_D3']['latency_p95_s']:.2f}초",'Q4뒤Q8 순서・교대실험 아님・우열 확정 보류'],
 ['GPU 서버 A 학습E4B 같은일정 직렬','60/60 호출',f"{gpu['A_same_itinerary_sequential']['sec_per_q']:.3f}초/호출 전체경과 평균",'p95 미기록','과거 별도60문항・E와 다름'],
 ['GPU 서버 A 학습E4B 일정변경 직렬','60/60 호출',f"{gpu['B_changing_itinerary_sequential']['sec_per_q']:.3f}초/호출 전체경과 평균",'p95 미기록','과거 별도60문항・E와 다름'],
 ['GPU 서버 A 학습E4B 동시4','60/60 호출','개별요청지연 미기록',f"{gpu['C_concurrency']['4']['sec_per_q']:.3f}초/호출 전체경과 평균",'처리간격≠개별요청지연; 시간당수치는 외삽'],
 ['CPU4코어 Q8 학습E4B','정답748/769; 형식실패12/835','다음질문 중앙4.45초','다음질문p95 5.62초','과거835기본문항・ARM과 다른기계']]),
'메모리 관측은 모델별 최대값을 모두 측정한 비교표가 아닙니다. 11:01 관측에서 GPU 서버 A4972MiB・B12499MiB, Oracle ARM 작업9,364,701,184바이트(약8.72GiB)이며 당시 실행 모델·작업이 서로 달랐습니다. ARM 전체2코어 대비300.07초 평균CPU89.97%, 메모리상한10GiB입니다. 단기 관측을24시간 유지로 표현하지 않습니다. ARM 캐시ABBA60문항×4회는 반복 안정성·지연 대조이며240개 독립정확도 표본이 아닙니다.',
'\n## 반복·학습 변경 판정',
table(['비교','지금 있는 근거','판정'],[
 ['같은기존레시피3시드','HF기본750/769・760/769・748/769; 평균97.88%, 범위97.27~98.83%','시드차이 있음; 최고1판으로 확정 불가'],
 ['cosine/FINCH s20261012 Q4_K_M','E 정상947/1033 대932/1033; cosine만36・FINCH만21; p=.06274','한 시드・차이 확정 보류'],
 ['cosine/FINCH s20261012 QAT Q4_0','E 정상991/1033 대960/1033; cosine만42・FINCH만11; p=.00002248','이 조건의 차이 있음; 두번째시드 진행'],
 ['잡담보강 첫판/어려운문장 둘째판','oos2r는 오지목 개선·정상요청 회귀 함께 있음','다른후보 학습자료 일괄교체 안 함'],
 ['FINCH학습 상한','654/654 갱신; 상한적용639/654=97.71%;16~654연속','스모크통과·학습완료≠정확도개선']]),
'\n[비교 수치의 원본 JSON](snapshot.json)・[추가 통계와 운영 근거](supplement.json)']
text=(folder/'comparison.md').read_text(encoding='utf-8')+'\n\n'+'\n\n'.join(extra)
text=text.replace('模型','모델')
new=folder/'comparison-complete.md';new.write_text(text,encoding='utf-8')
supplement=dict(checked_at=datetime.now().astimezone().isoformat(),saluki_vs_gemma12b_E_request=pair,
              source_sha256={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in [arm_path,gpu_path]},
              repeats=1,independent_holdout_complete=False)
(folder/'supplement.json').write_text(json.dumps(supplement,ensure_ascii=False,indent=2),encoding='utf-8')
body=markdown.markdown(text,extensions=['tables','fenced_code']);body=re.sub(r'(<table>.*?</table>)',r'<div class="table-scroll">\1</div>',body,flags=re.S)
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>A~E 전체 실측 비교</title><style>body{font:15px/1.65 "Malgun Gothic",sans-serif;color:#202a32;background:#fafaf7;margin:24px auto;max-width:1500px;padding:0 20px}h1{font-size:27px}h2{font-size:21px;margin-top:44px}a{color:#185c91}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #d4d9db;padding:9px;text-align:left;white-space:nowrap}th{background:#e6edf0;position:sticky;top:0}tr:nth-child(even){background:#f0f3f3}.table-scroll{overflow:auto;margin:16px 0;border:1px solid #d4d9db}input{font:inherit;padding:10px;width:min(600px,90%);margin-bottom:14px}tr.hide{display:none}</style><h1>Saluki와 A~E 전체 비교</h1><p>모델 이름을 입력하면 각 비교표의 해당 행만 보입니다. 빈 칸은 전체 표시입니다.</p><input id="filter" placeholder="예: Saluki, oos3, finch, 원본" aria-label="모델 이름으로 표 필터">'''+body+'''<script>document.getElementById('filter').addEventListener('input',e=>{let q=e.target.value.toLowerCase().trim();document.querySelectorAll('table tbody tr').forEach(r=>r.classList.toggle('hide',q&&!r.innerText.toLowerCase().includes(q)))})</script></html>'''
(folder/'comparison.html').write_text(page,encoding='utf-8')
# Verify all snapshot sources independently; archived evidence must not change mid-report.
for relative,digest in s['source_sha256'].items():assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
verification=dict(source_hashes_verified=len(s['source_sha256']),expected=len(s['source_sha256']),
                  fixed_fixture_mapping=835,single_suite_count=sum(len(r['suites']) for r in records),
                  saved_single_answers=sum(z['saved'] for r in records for z in r['suites'].values()),
                  multi_answers=835*len(s['multi_contract']),historical_answers=835*len(s['historical_basic']))
(folder/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
stamp=datetime.now().strftime('%Y-%m-%d_%H%M');report=ROOT/f'final_project_cs/wiki/records/reports/{stamp}_saluki-all-abcde-comparison.md'
report.write_text('---\ntype: report\ntitle: Saluki를 포함한 모든 일정 선택 평가 역할 비교\ndescription: 보관 답안의 A·B·C·D·E와 추가 지표 재집계 및 누락 범위\nstatus: draft\ndomain: travel\n---\n\n# Saluki와 전체 측정 비교\n\nSaluki 배포 원본의 E 정상 요청 점수는 높지만 요청없음 오지목 기준을 실패했습니다. 단일 선택22판과 Valen 완료3세트, 복수JSON6판, 과거HF/CLI16역할을 분리해 원본으로 재계수했습니다.\n\n'+table(['할 일','상태','진행'],[['원본SHA 재검사','완료',rat(verification['source_hashes_verified'],verification['expected'])],['기본문항과D 대조','완료',rat(835,835)],['채택·독립검증','대기','0/1 = 0%']])+'\n\n[전체 비교표]('+new.as_posix()+')・[검색 가능한 표]('+str(folder/'comparison.html').replace('\\','/')+')・[검증]('+str(folder/'verification.json').replace('\\','/')+'). 각 표에 분자/분모·실패·반복·학습 여부·조건 차이를 기록했습니다. 과거 산출물을 덮어쓰지 않고 새 이름으로 보존했습니다.\n\nA·B·C는 같은835문항의 서로 다른채점, E는MX평문혼합입니다. 단일출력C0/66을 복수역할 실패로 읽지 않으며 새로운 복수역할누락은 기존GPU일꾼에 보충 중입니다. 양자화·모델변경 정확도와 엔진속도, 말로한확신도와 선택지/토큰확률을 구분했습니다. Saluki와Gemma12B E정상4문항차이를 일반우열로 확정하지 않습니다. 모델실행1회·개발세트이며 사람검수·독립보류·최종제품채택 미완료입니다.\n\n새 코드: [재계수 도구]('+str(RES.parent/'comparison_snapshot_20261009.py').replace('\\','/')+')・[표 생성/근거 검증]('+str(RES.parent/'finalize_comparison_20261009.py').replace('\\','/')+'). 기존집계도구 수정전 보관: [백업]('+str(RES.parent/'_backup/2026-10-09_1116_comparison_before_valen').replace('\\','/')+').\n',encoding='utf-8')
for target,line in [(ROOT/'program/research/daily_rag_slm/index.md',f'\n- [Saluki와 전체 A~E 실측 비교]({report.as_posix()}): 단일·복수 역할, E유형·손실·지연·검토자·반복과 누락범위를 한 표집에 연결했습니다.\n'),(ROOT/'final_project_cs/wiki/log.md',f'\n- 2026-10-09: Saluki 포함 A~E 보관 원본을 재계수하고 단일·복수 출력·개발시험·독립검증을 분리했다. [비교 근거]({report.as_posix()}).\n')]:
    backup=target.parent/'_backup'/f'{stamp}_comparison_link_before';backup.mkdir(parents=True,exist_ok=True)
    import shutil
    shutil.copy2(target,backup/target.name)
    with target.open('a',encoding='utf-8') as f:f.write(line)
print(json.dumps(dict(folder=str(folder),report=str(report),verification=verification,paired=pair),ensure_ascii=False))
