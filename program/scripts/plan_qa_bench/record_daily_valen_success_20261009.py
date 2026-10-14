"""별도 수정 시도의 실제 연결 성공을 재계수하고 일일 기록에 연결한다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil
from backlog_valen_report import check_native

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
FOLDER=BASE/'valen_08b_original_smoke12_a2'
OUT=ROOT/'program/scripts/rag_gate/results/daily_20261009_selective_v1/valen_success_parent_verification.json'
assert not OUT.exists()
prompts=ROOT/'datasets/travel/valen_native_eval_20261009/smoke12.json'
ref={r['i']:r for r in json.loads(prompts.read_text(encoding='utf-8'))}
answers=FOLDER/'d_test_valen_08b_original_smoke12_a2.jsonl'
rows=[json.loads(l) for l in answers.read_text(encoding='utf-8').splitlines()]
assert len(rows)==len(ref)==len({r['i'] for r in rows})==12
assert {r['i'] for r in rows}==set(ref)
for r in rows:
    q=ref[r['i']]
    assert all(r[k]==q[k] for k in ['set','qi','gold','type'])
    assert check_native(r,q['request']['questions']['selection']['criteria'])
correct=sum(r['pick']==r['gold'] for r in rows)
assert correct==4
summary=json.loads((FOLDER/'valen_summary.json').read_text())
assert summary['parsed']==summary['saved']==summary['expected']==12
assert summary['errors']==summary['missing']==0
context_path=BASE/'Valen_preflight_runtime_20261009_1028/all_input_context_preflight.json'
ctx=json.loads(context_path.read_text())
lengths=[r for s in ctx['suites'].values() for r in s['lengths']]
assert len(lengths)==ctx['checked']==ctx['expected']==9425
assert all(not s['failed'] for s in ctx['suites'].values())
assert max(r['tokens'] for r in lengths)==3934 and max(r['choices'] for r in lengths)==47
now=datetime.now(ZoneInfo('Asia/Seoul'))
stamp=now.strftime('%Y-%m-%d_%H%M%S_valen_actual_success')
backups=[]
def save(p,text):
    dest=p.parent/'_backup'/stamp/p.name
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    backups.append(str(dest.relative_to(ROOT)).replace('\\','/'))
    p.write_text(text,encoding='utf-8')
watch_path=ROOT/'program/research/daily_rag_slm/model_release_watchlist.json'
watch=json.loads(watch_path.read_text(encoding='utf-8'))
c=next(c for c in watch['candidates'] if c['repo_id']=='Valen-Team/Valen-0.8B')
c.update(status='Repaired a2 GPU load/API parsed12/12, errors0, diagnostic correct4/12; full five suites unblocked and running, no ranking',
    GPU_smoke_completed=True, GPU_smoke_expected=12, GPU_smoke_saved=12, GPU_smoke_correct=4,
    GPU_smoke_errors=0, max_GPU_allocated_bytes=summary['max_gpu_allocated'],
    full_input_token_checked=9425, full_input_token_expected=9425, max_input_tokens=3934,
    GPU_smoke_evidence='program/scripts/plan_qa_bench/results/gpu_backlog_20261008/valen_08b_original_smoke12_a2/native_counts.json',
    original_benchmark_state='Smoke1 attempt failed before load and preserved; repaired attempt complete12/12; full5 suites executing, not completed',
    korean_travel_measured=True, original_benchmark_completed=False, upper_tier=None,
    product_adoption=False)
watch['updated_at_kst']=now.isoformat();save(watch_path,json.dumps(watch,ensure_ascii=False,indent=2)+'\n')
day_path=ROOT/'program/research/daily_rag_slm/2026-10-09.json'
day=json.loads(day_path.read_text(encoding='utf-8'))
day['measurement'].update(Valen_GPU_smoke_completed=True,Valen_GPU_smoke_saved=12,
    Valen_GPU_smoke_correct=4,Valen_GPU_smoke_expected=12,Valen_GPU_smoke_errors=0,
    Valen_observation_scope='Repaired GPU smoke completed; five main suites unblocked, main saved progress tracked in GPU canonical state',
    multi_item_role_collected_rows=5010,multi_item_role_collected_jobs=6)
day['Valen_queue'].update(GPU_load_passed=True,all_input_token_compile='complete9425/9425,failed0,max3934tokens/47choices',
    successful_smoke_evidence=c['GPU_smoke_evidence'], main_state='Unblocked; D3 running at2026-10-09T01:29:27Z snapshot, not all9425 complete')
day['updated_at_kst']=now.isoformat();save(day_path,json.dumps(day,ensure_ascii=False,indent=2)+'\n')
report=ROOT/'final_project_cs/wiki/records/reports/2026-10-09_1015_daily-research-and-serving.md'
addition='''\n## 修正 연결 성공과 전체 시험 시작 — 10:29 KST 이후 회수\n\n별도a2 시도는 원본 FP32 가중치 GPU 로드와 API·확률 해석12/12를 완료했다. 오류·미완료0, 진단 정답4/12(정상4/4, 요청없음·함정 오지목8/8)이다. 이 연결 표본으로 원본 순위를 정하지 않는다. 최대 GPU allocation4,726,889,984바이트를 관측했고 최적 causal_conv1d 커널이 없는 기존 환경의 PyTorch 경로를 썼다. 설치 없이 성공했다. 첫a1 환경 실패는 그대로 보존했다.\n\n전체 본 입력의 CPU token 검사도9,425/9,425·실패0, 최대3,934토큰·47선택지로 확인했다. 연결 성공 표시가 생겨 본5평가가 자동으로 열렸다. 10:29:27 KST 관측에서 D3는 실행 중이고 본 전체가 완료된 상태는 아니다.\n\n복수 항목 역할6설정5,010/5,010 답안을 모두 회수했다. 앞4설정20파일과 뒤2설정10파일, 총SHA30/30을 확인했고 해석 실패11개를 고정 분모에 포함해 집계했다. 개발·회귀용835문항을6설정으로 호출한 것이며5,010개 독립 표본이 아니다.\n\n[실제 연결 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/valen_08b_original_smoke12_a2/native_counts.json) · [성공·첫 실패·부분 본평가 회수 SHA](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_actual_smoke_runtime_20261009_1031/verification.json) · [전체 입력 길이 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_preflight_runtime_20261009_1028/all_input_context_preflight.json) · [뒤2설정 회수 SHA](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_multi_items_finch_completed_20261009_1029/verification.json) · [부모 재계수·백업 목록](../../../../program/scripts/rag_gate/results/daily_20261009_selective_v1/valen_success_parent_verification.json).\n'''.replace('修正','수정')
save(report,report.read_text(encoding='utf-8')+addition)
md=ROOT/'program/research/daily_rag_slm/2026-10-09.md'
save(md,md.read_text(encoding='utf-8')+'\n수정a2 실제GPU 연결12/12·해석오류0·진단정답4/12를 회수했습니다. 전체 입력 길이9,425/9,425를 통과해 기존worker 본5평가가 시작됐습니다. 복수항목 역할6설정5,010/5,010도 전부 보관했으며 기존 개발문항의 반복 설정 비교입니다. [실제 연결 집계](../../scripts/plan_qa_bench/results/gpu_backlog_20261008/valen_08b_original_smoke12_a2/native_counts.json).\n')
proof=dict(verified_at_kst=now.isoformat(),parsed=12,expected=12,correct=correct,errors=0,
    full_input_checked=len(lengths),full_input_expected=9425,max_tokens=3934,max_choices=47,
    answer_SHA256=hashlib.sha256(answers.read_bytes()).hexdigest(),
    context_SHA256=hashlib.sha256(context_path.read_bytes()).hexdigest(),
    full_model_benchmark_completed=False, first_failure_preserved=True, backups=backups)
OUT.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False))
