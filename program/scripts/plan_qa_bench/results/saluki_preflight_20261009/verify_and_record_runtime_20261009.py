"""이미 회수한 Saluki 실행 증거를 검증하고 새 기록으로 보존한다."""
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
workspace=Path(__file__).resolve().parents[5]
base=Path(__file__).parent
runtime=base/'runtime_20261009_0232'
now=datetime.now(timezone.utc)
stamp=now.astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d_%H%M%S')
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,data):
    with p.open('x',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
gold=read(base.parent/'empty_probe/all_prompts_d3.json')
reference={r['i']:r for r in gold}
assert len(reference)==len(gold)==360
smoke=read(base/'smoke_prompts_d3_12.json')
assert len(smoke)==len({r['i'] for r in smoke})==12
assert all(all(r[k]==reference[r['i']][k] for k in reference[r['i']]) for r in smoke)
proof={'captured_at_utc':read(runtime/'capture_manifest.json')['observed_at_utc'],'remote_local_sha_match':[14,14],'our_training':False,'repetitions':1,'final_ranking':False,'product_adoption':False}
for job,name,expected in [('saluki_original_smoke12_a1','saluki_smoke_a1',12),('saluki_original_d3_a1','saluki_original_d3_a1',360)]:
    folder=runtime/job
    rows=[json.loads(line) for line in (folder/f'd_test_{name}.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows)==len({r['i'] for r in rows})
    ref={r['i']:r for r in (smoke if expected==12 else gold)}
    assert set(r['i'] for r in rows)<=set(ref)
    assert all(all(r[k]==ref[r['i']][k] for k in ['gold','type','set','qi']) for r in rows)
    parsed=sum(bool(r.get('parsed')) for r in rows)
    errors=sum(bool(r.get('error')) for r in rows)
    correct=sum(bool(r.get('parsed')) and not r.get('error') and r['pick']==r['gold'] for r in rows)
    length=read(folder/'context_lengths.json')
    assert length['expected']==length['checked']==expected and length['oversize']==0
    assert len(length['rows'])==expected and all(r['fits'] for r in length['rows'])
    contract=read(folder/'saluki_contract.json')
    assert contract['our_training'] is False and contract['context']==4096 and contract['max_tokens']==16
    assert contract['enable_thinking'] is False and contract['temperature']==0
    assert contract['runner_sha256']==sha(workspace/'program/scripts/plan_qa_bench/server/queues/saluki_eval_20261009.py')
    expected_hash=sha(base/'smoke_prompts_d3_12.json') if expected==12 else sha(base.parent/'empty_probe/all_prompts_d3.json')
    assert contract['prompt_sha256']==expected_hash
    result=dict(saved=len(rows),expected=expected,parsed=parsed,errors=errors,unparsed=len(rows)-parsed,missing=expected-len(rows),metadata_matched=len(rows),answer_sha256=sha(folder/f'd_test_{name}.jsonl'),prompt_sha256=expected_hash,checked_prompt_lengths=length['checked'],max_prompt_tokens=length['max_tokens'],oversize=length['oversize'],partial_snapshot=expected!=12)
    if expected==12:
        result['correct']=correct
        result['positive_correct']=sum(bool(r.get('parsed')) and r['pick']==r['gold'] for r in rows if r['gold'] is not None)
        result['positive_expected']=sum(r['gold'] is not None for r in smoke)
        result['negative_false_pick']=sum(bool(r.get('parsed')) and r['pick'] is not None for r in rows if r['gold'] is None)
        result['negative_expected']=sum(r['gold'] is None for r in smoke)
        summary=read(folder/'saluki_summary.json')
        assert summary['correct']==correct and summary['parsed']==parsed and summary['errors']==errors
        assert read(runtime/'tripilot-saluki-20261009/SMOKE_PASS.json')==summary
    proof[job]=result
put(runtime/'runtime_verification.json',proof)

snapshot_dir=base.parent/'gpu_backlog_20261008'
a=read(snapshot_dir/'A_snapshot_saluki_registered_20261009.json')
ac=read(snapshot_dir/'A_conditions_saluki_registered_20261009.json')
b=read(snapshot_dir/'B_snapshot_saluki_registered_20261009.json')
bc=read(snapshot_dir/'B_conditions_saluki_registered_20261009.json')
states=a['state']['jobs']
finished=sum(s.get('status') in {'completed','completed_with_errors'} for s in states.values())
pending_cosine={job:{'saved':info['saved'],'expected':info['expected'],'status':'completed_remote_recovery_pending'} for job,info in states.items() if 'cosine_s20261012' in job and info.get('status')=='completed' and not job.endswith('_d3')}
assert len(pending_cosine)==7 and sum(v['saved'] for v in pending_cosine.values())==14116
statepath=workspace/'program/research/daily_rag_slm/gpu_backlog_2026-10-09.json'
state=read(statepath)
backup=statepath.parent/'_backup'/f'{stamp}_saluki_actual_running'/statepath.name
backup.parent.mkdir(parents=True,exist_ok=False)
shutil.copy2(statepath,backup)
state['before_saluki_actual_running_observation']={'A':state['A'],'B':state['B'],'conditional_work':state['conditional_work']}
state['recorded_at_utc']=now.isoformat()
state['A'].update(observed_at_utc=a['observed_at_utc'],snapshot=str((snapshot_dir/'A_snapshot_saluki_registered_20261009.json').relative_to(workspace)).replace('\\','/'),conditions=str((snapshot_dir/'A_conditions_saluki_registered_20261009.json').relative_to(workspace)).replace('\\','/'),gpu_snapshot=a['gpu_snapshot'],manifest_jobs=len(a['manifest']['jobs']),manifest_questions=sum(j['expected'] for j in a['manifest']['jobs']),completed_jobs=finished,running_jobs=[j for j,s in states.items() if s.get('status')=='running'],running_answers_saved=50,running_answers_expected=360,ready_jobs=len(ac['ready']),input_blocked_jobs=len(ac['blocked']),ready_ids=ac['ready'],new_jobs=6,new_questions=9437,worker_restarted=False,readiness_evidence='Smoke success marker and verified model symlink exist; existing worker started original D3',refill_audit='program/scripts/plan_qa_bench/results/saluki_preflight_20261009/queue_registered_A_20261009.json',remote_backup='/tmp/tripilot-a-backlog-20261008/_backup/2026-10-08_172443_saluki_registration/manifest.json')
state['B'].update(observed_at_utc=b['observed_at_utc'],snapshot=str((snapshot_dir/'B_snapshot_saluki_registered_20261009.json').relative_to(workspace)).replace('\\','/'),conditions=str((snapshot_dir/'B_conditions_saluki_registered_20261009.json').relative_to(workspace)).replace('\\','/'),gpu_snapshot=b['gpu_snapshot'],training_steps_saved=140,training_steps_expected=654,active_training_stage='optimizer update 140/654 in FINCH log',prepared_training_jobs=4)
state['conditional_work']=[item for item in state['conditional_work'] if 'Saluki' not in item.get('candidate','')]
report_path=workspace/f'final_project_cs/wiki/records/reports/{stamp}_saluki-install-smoke-and-evaluation.md'
state['saluki_actual_evaluation']={'report':str(report_path.relative_to(workspace)).replace('\\','/'),'model_revision':a['manifest']['jobs'][0]['model_revision'],'model_sha256':a['manifest']['jobs'][0]['model_sha256'],'model_bytes':7898369152,'our_training':False,'publisher_original':True,'A_model_storage':'Existing /dev/shm RAM; volatile','local_durable_model_archive':False,'local_space_available_bytes':4993708032,'B_disk_preservation_capture':str((runtime/'B_preservation_capture.json').relative_to(workspace)).replace('\\','/'),'B_disk_preservation_complete':False,'B_disk_preservation_saved_bytes':read(runtime/'B_preservation_capture.json')['state']['saved'],'registered_jobs':6,'smoke_saved':12,'smoke_expected':12,'smoke_parsed':12,'smoke_correct':9,'full_saved_partial_snapshot':proof['saluki_original_d3_a1']['saved'],'full_expected':9425,'full_completed_suites':0,'full_expected_suites':5,'snapshot_at_utc':proof['captured_at_utc'],'evidence':str((runtime/'runtime_verification.json').relative_to(workspace)).replace('\\','/'),'state_backup':str(backup.relative_to(workspace)).replace('\\','/'),'cosine_recovery_pending':pending_cosine,'full_sequence':['D3','E/MX','H','D','D2'],'speed_comparison':False,'final_ranking':False,'product_adoption':False}
state['scope']['new_model_download']=True
temporary=statepath.with_suffix('.saluki-update.tmp')
put(temporary,state)
temporary.replace(statepath)

prefix='../../../../'
def link(label,path): return f'[{label}]({prefix}{str(path.relative_to(workspace)).replace(chr(92),"/")})'
sm=proof['saluki_original_smoke12_a1']; d3=proof['saluki_original_d3_a1']
bp=read(runtime/'B_preservation_capture.json')['state']
text=f'''# Saluki 원본 설치·연결검사 및 실제 평가 시작

Saluki 원본을 받아 전체 파일 해시를 확인했고 기존 GPU 서버 A의 순차 실행기로 실제 질의 시험을 시작했습니다. 연결검사 성공과 정확도 점수를 구분합니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 고정 가중치 다운로드 | 해시 일치 | 7,898,369,152/7,898,369,152바이트 = 100% |
| 연결검사 호출·해석 | 완료 | 12/12 = 100% |
| 연결검사 정답 | 참고 실측 | 9/12 = 75.00% |
| 본 평가 답안 | 실행 중 | {d3['saved']}/9,425 = {100*d3['saved']/9425:.2f}% |
| GPU 서버 B 디스크 사본 | 전송 중 | {bp['saved']}/7,898,369,152바이트 = {100*bp['saved']/7898369152:.2f}% |

관측 기준은 2026-10-09 02:32:49 KST입니다. D3 부분 답안은 {d3['saved']}/360 = {100*d3['saved']/360:.2f}%이며 ID·정답·유형·세트·문항 번호가 고정 정답과 {d3['metadata_matched']}/{d3['saved']} 일치합니다. 저장된 부분의 호출 오류·해석실패는 0/{d3['saved']}이지만 나머지 {d3['missing']}개는 미완료이며 전체 360 및 전체 시험 9,425 분모에 남깁니다. 완료 본 세트는 0/5입니다. 연결검사 12개를 본 평가 독립 정확도 표본에 합치지 않습니다.

연결검사는 실제 모델 로드와 호출·해석 12/12, 오류 0/12로 끝났습니다. 정상 요청 정답 {sm['positive_correct']}/{sm['positive_expected']}, 요청 없음 오지목 {sm['negative_false_pick']}/{sm['negative_expected']}이며 전체 정답은 9/12입니다. 이 작은 연결검사로 정확도 개선·상위권·제품 채택을 판단하지 않습니다.

## 고정 모델·입력·실행 조건

모델은 개발사 학습이 있는 배포 원본 ConwayResearch/Underdog-Saluki-27B-1.0 IQ2-mix이며 우리 여행 자료로 추가 학습하지 않았습니다. 고정 revision은 1336c0b5d74dfe6ad7f793577092f5effd9f97c6, 전체 가중치 SHA256은 4a673518b11b1c4445f9b9a9d3c40356f5ba39f6a6260dcb25f3fbfd475d9efb입니다. 언어 27B로 자동 소형 모델 추가 학습 범위에 넣지 않습니다.

설치된 llama.cpp 4ebdf2c, build 0.5.0-dev의 qwen35 코드와 실제 로드를 확인했습니다. 기존 엔진은 덮지 않았습니다. 기존 비교와 같이 CPU 범위 0–5·추론 스레드 4·GPU 레이어 99·문맥 4096·동시 슬롯 1·jinja·enable_thinking=false·temperature=0·출력 최대16을 고정했습니다. 실제 질의 정보만 모델 입력에 보내며 정답은 호출 본문에 넣지 않습니다. 엔진 바이너리·실행 코드·입력 파일 SHA와 원문 응답을 보관했습니다.

문맥 길이는 연결검사 12/12·D3 360/360을 실제 설치 엔진의 같은 대화 템플릿과 토크나이저로 검사했습니다. 최대 입력은 각각 1,953·2,007토큰이며 입력+16출력 한도를 넘는 문항 0/12·0/360입니다. 임의 잘라내기나 출력 수정은 하지 않았습니다. D3·연결검사는 logprobs 비활성, 나머지 4세트는 기존 경로처럼 logprobs와 top20을 켭니다. 토큰 선택 확률과 말로 표현한 확신도는 구분하고 모델 변경 정확도를 같은 모델 엔진 속도 비교로 쓰지 않습니다.

## 순차 실행·자원·보관

기존 worker의 현재 작업이 끝난 후 연결검사→D3→E(MX)→H→D→D2 순서로 자동 이어지도록 6작업을 등록했습니다. 기존 학습·평가를 중단하거나 두 번째 GPU worker를 띄우지 않았습니다. 12개 호출·해석 성공 마커와 검증된 모델 연결 파일이 있어야 본 시험을 시작합니다. 매 작업 전에 가중치 크기·SHA·로드 전 메모리 여유를 검사합니다. 입력/가중치가 사라지면 조건 대기이며 실패 작업은 원인 수정 없이 자동 재시작하지 않습니다. 실제 D3 실행이 시작돼 설치 계획만으로 완료 표시한 상태가 아닙니다.

02:28:23 KST GPU 서버 A 관측: GPU 100%·8,142MiB, 전체 등록63개·118,442문항, 완료57개·실행1개·준비대기5개·조건대기0개입니다. GPU 서버 B는 GPU100%·12,899MiB, FINCH140/654회 갱신이며 뒤에 B57/B58 학습4개가 준비돼 있습니다. 순간 관측이며 하루 종일 사용률을 보장한 측정으로 해석하지 않습니다.

GPU 서버 A의 기존 /dev/shm RAM에 약7.9GB 파일을 보관했으므로 휘발성입니다. 실제 cgroup 메모리 한도는 약31GB이며 D3 로드 전 여유7,821,004,800바이트를 확인했습니다. 연결검사 후 로드 상태의 여유는3,819,016,192바이트였습니다. 다운로드는 GPU를 쓰지 않고 속도와 메모리 보호 조건을 두었습니다. 기존 저장공간을 확장하거나 모델을 삭제하지 않았습니다. 로컬 C의 여유4,993,708,032바이트는 파일 전체보다 작아 로컬 영구 가중치 사본은 아직 없습니다.

검증된 GPU 서버 A RAM 파일을 기존 GPU 서버 B 디스크로 GPU 연산 없이 옮기는 중입니다. 02:32:45 KST 수신 상태는 receiving, {bp['saved']}/7,898,369,152바이트이며 전체 SHA 검증·최종 이름 교체 전이므로 완료로 쓰지 않습니다. GPU 서버 B의 디스크 사본도 기계 삭제 후 유지되는 외부 영구 백업은 아닙니다. 로컬 제어 프로세스와 수신 상태를 확인해 살아 있으면 기존 전송을 기다립니다. 전송이 끊기면 .part와 GPU 서버 A 원본을 보존한 뒤 수신 바이트·기존 부분 해시를 확인하는 별도 재개 절차를 준비하며 지금 실행을 중복하지 않습니다.

cosine의 새 완료7개·14,116답안은 회수 대기입니다: Q4_K_M/QAT 각 D 2,735·D2 1,000·H 1,316, Q4_K_M E(MX) 4,014. 이전에 회수한 cosine D3 두 세트720개와 섞지 않았습니다. 다음 확인에서 완료 답안을 새 폴더에 회수하고 실패를 분모에 유지하는 기존 도구로 집계합니다. E는 backlog_mx_report.py를 사용합니다. 독립 보류 검증·반복·서비스 채택 및 상용화 판정은 아직 하지 않았습니다.

## 실행 증거·백업

- {link('전체 가중치 다운로드·SHA 검증',base/'download_verified_A_20261009.json')}
- {link('6작업 등록·기존 worker 및 원자 교체 백업',base/'queue_registered_A_20261009.json')}
- {link('회수 원문 및 부분 답안',runtime)}
- {link('원격·로컬 파일 SHA 14/14',runtime/'capture_manifest.json')}
- {link('고정 정답·유형·실행 조건 독립 검증',runtime/'runtime_verification.json')}
- {link('연결검사 원문 summary',runtime/'saluki_original_smoke12_a1/saluki_summary.json')}
- {link('D3 실행 조건',runtime/'saluki_original_d3_a1/saluki_contract.json')}
- {link('D3 360개 문맥 길이',runtime/'saluki_original_d3_a1/context_lengths.json')}
- {link('GPU 서버 B 수신 진행',runtime/'B_preservation_capture.json')}
- {link('최신 GPU 상태 JSON',statepath)}
- {link('상태 변경 직전 백업',backup)}
- {link('Saluki 실행 코드',workspace/'program/scripts/plan_qa_bench/server/queues/saluki_eval_20261009.py')}
- {link('실행 코드의 계측 보강 전 백업',workspace/'program/scripts/plan_qa_bench/server/queues/_backup/2026-10-09_0220_saluki_resource_samples/saluki_eval_20261009.py')}

공통 날짜 기록·색인·후보 목록·wiki 본문은 부모 에이전트가 소유하며 이 작업에서 수정하지 않았습니다. 기존 산출물을 수정한 GPU 상태 JSON과 실행 코드·원격 manifest는 수정 직전에 백업했고 신규 보고서·회수 파일은 새 이름으로 보관했습니다.
'''
with report_path.open('x',encoding='utf-8') as f:f.write(text)
links=re.findall(r'\]\(([^)]+)\)',text)
assert all((report_path.parent/p).resolve().exists() for p in links)
put(runtime/'report_link_verification.json',{'report':str(report_path.relative_to(workspace)).replace('\\','/'),'valid_links':len(links),'expected_links':len(links),'all_exist':True})
print(json.dumps(dict(report=str(report_path.relative_to(workspace)),state_backup=str(backup.relative_to(workspace)),verification=proof,links=len(links)),ensure_ascii=False,indent=2))
