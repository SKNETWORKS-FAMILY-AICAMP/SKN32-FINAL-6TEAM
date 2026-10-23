"""해석 실패를 보존한 새 H 완료를 실행 기록과 wiki에 연결한다."""
from pathlib import Path
from datetime import datetime
import json, shutil
ROOT=Path(__file__).resolve().parents[3]
stamp=datetime.now().strftime('%Y-%m-%d_%H%M%S')+'_e4b_h_completion'
backups=[]
def save(rel,text):
    p=ROOT/rel
    if p.exists():
        b=p.parent/'_backup'/stamp/p.name;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
        backups.append(str(b.relative_to(ROOT)).replace('\\','/'))
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
results=ROOT/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
a=json.loads((results/'A_snapshot_1036.json').read_text(encoding='utf-8'))
r=json.loads((results/'e4bbase_h/h_counts.json').read_text(encoding='utf-8'))
assert r['answer_sha256']=='03690687044e0ceed2dac04b12da2d22fb7152d9d3055498570ab162db63a214'
assert r['positive']['correct']==433 and r['negative']['correct']==452 and r['negative']['false_pick']==402
assert r['negative']['correct']+r['negative']['false_pick']+r['negative']['failed_or_missing']==855
assert r['failed_or_unparsed']==1 and r['failed_records'][0]['content']=='{"item": [31]}'
daily='program/research/daily_rag_slm/'
state=json.loads((ROOT/daily/'gpu_backlog_2026-10-08.json').read_text(encoding='utf-8'))
state['gpu_A'].update({'snapshot':'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_snapshot_1036.json','observed_at_utc':a['observed_at_utc'],'state':a['state'],
 'answers_saved_at_snapshot':a['answers'],'jobs_completed':3,'jobs_completed_with_errors':1,'jobs_running':1,'jobs_ready_waiting':13,
 'instant_gpu_memory_and_utilization':a['gpu_snapshot'],'completed_e4bbase_h_archived':True})
state['latest_routine_observation'].update({'new_completed_jobs':2,'new_failed_or_unparsed_answers':1,'new_failed_jobs':0,'reason':'Frog MX and Gemma original H archived; format failure retained; A continues original Gemma MX with13 ready jobs; existing B training continues'})
save(daily+'gpu_backlog_2026-10-08.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
day=json.loads((ROOT/daily/'2026-10-08.json').read_text(encoding='utf-8'))
day['new_completed_evaluations'].append({'model':'Gemma-4-E4B-it Q4_K_M','our_training':False,'publisher_training':'Instruct release','suite':'H','saved':1316,'expected':1316,
 'unparsed':1,'missing':0,'positive_correct':433,'positive_total':461,'negative_false_pick':402,'negative_total':855,'negative_failed_or_unparsed':1,'repetitions':1,'full_ranking':False,
 'report':'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_h/h_report.md'})
save(daily+'2026-10-08.json',json.dumps(day,ensure_ascii=False,indent=2)+'\n')
save(daily+'2026-10-08.md',(ROOT/daily/'2026-10-08.md').read_text(encoding='utf-8')+'''
## 10시 36분 추가 확인 — Gemma E4B 원본 H 완료, 형식 실패 보존

우리 자료 학습 없는 Gemma-4-E4B-it Q4_K_M(개발사 지시 학습 배포판)의 어려운 문장 H답안1,316/1,316개를 보관했습니다. 정상 요청 정답433/461=93.93%, 요청 없는 함정·잡담 오지목402/855=47.02%이며 해석 실패1/1,316개입니다. 실패 문항951127은 단일 번호 대신 `{"item": [31]}` 배열을 출력했습니다. null 정답으로 바꾸거나 실패를 분모에서 빼지 않았으며 원문과 전체 오답을 보존했습니다.

GPU 서버 A의 원본과 로컬 SHA256이 일치합니다. 실패 문항을 포함해 새 H 집계의 정상/요청 없음 분모와 계수를 검증했습니다. 동일 모델 전체 시험을 반복하지 않았고 다음 혼합 요청 평가가 계속 실행 중입니다. 준비된 A 평가13개와 기존 B뒤 본 학습4개를 유지합니다. 다른 세트의 FrogNano 결과와 점수를 직접 순위 비교하지 않습니다.

[Gemma H 답안·집계](../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_h/h_report.md) · [완료·실패 근거 리포트](../../../final_project_cs/wiki/records/reports/2026-10-08_gemma-original-h-completion.md).
''')
rel='final_project_cs/wiki/quality/slm-model-evaluation.md'
save(rel,(ROOT/rel).read_text(encoding='utf-8')+'''
`[실측 2026-10-08]` 우리 자료 추가 학습 없는 Gemma E4B 원본 H도 회수했다. 단일 번호 대신 배열을 낸1개는 형식 실패·전체 오답으로 보존했고 분모를 줄이지 않았다. [원문·완료 근거](../records/reports/2026-10-08_gemma-original-h-completion.md).
''')
rel='final_project_cs/wiki/log.md';text=(ROOT/rel).read_text(encoding='utf-8')
save(rel,text.replace('# 문서 변경 이력 (cs)\n','# 문서 변경 이력 (cs)\n\n## 2026-10-08 — Gemma E4B 원본 H 완료·형식 실패 보존\n\n답안1,316개를 회수했고 배열 출력1개는 실패로 보존해 전체 분모로 집계했다. [완료·실패 근거](records/reports/2026-10-08_gemma-original-h-completion.md).\n',1))
save('final_project_cs/wiki/records/reports/2026-10-08_gemma-original-h-completion.md','''# Gemma E4B 원본 H 완료·형식 실패 보존 — 2026-10-08

우리 자료로 학습하지 않은 Gemma-4-E4B-it Q4_K_M의 H평가를 보관했다. 개발사 지시 학습은 있음으로 구분했다. 같은 원본 비교군의 전체 시험과 반복 검증 전에는 최종 순위를 확정하지 않는다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·정답 일치 | 완료 | 1,316/1,316 = 100% |
| 정상 요청 정답 | 실측 | 433/461 = 93.93% |
| 함정·잡담 오지목 | 실측 | 402/855 = 47.02% |
| 형식 실패 | 보존 | 1/1,316 = 0.08% |

요청 없음 분모855개는 정답452개·오지목402개·형식 실패1개로 이루어진다. 실패 문항951127은 `{"item": [31]}`을 출력했다. 계약은 단일 번호 또는 null이므로 배열을 유효한 번호나 null로 재해석하지 않았다. 실패·미완료는 전체 분모에서 빼지 않았다.

[원본 답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_h/d_test_h_backlog_e4bbase.jsonl) · [집계·실패 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_h/h_counts.json) · [집계 표](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_h/h_report.md) · [실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_h/started.json).

답안 SHA256은 GPU 서버 A 완료 원본과 동일한 `03690687044e0ceed2dac04b12da2d22fb7152d9d3055498570ab162db63a214`이다. llama.cpp commit4ebdf2c·기존 고정 세트·모델 실행1회이며 Wilson 구간은 문항별 구간이라 동일 일정의 상관을 반영하지 않는다. 새 독립 보류 자료와 반복 측정을 대신하지 않는다.

기존 지속 실행기는 다음 원본 Gemma 혼합 요청 평가를 실행한다. 새 실행기를 띄우거나 진행 중 GPU 서버 B 학습을 중단하지 않았다. 형식 실패1개 때문에 같은 H 전체를 반복하지 않았다. 실패 원문을 별도 회귀 진단으로 보존했으며 모델 정확도 개선이나 채택으로 표시하지 않았다.

이번 확인에서 새로 완료·회수한 것은 [FrogNano 원본 MX](2026-10-08_frog-original-mx-completion.md)와 이 Gemma H이다. 서로 다른 세트의 점수를 동일 조건의 모델 간 순위로 비교하지 않는다. 관련 정본과 cs wiki log·일일 기록을 연결했다.

수정 전 판의 백업:

'''+''.join('- ['+p+'](../../../../'+p+')\n' for p in backups))
print(json.dumps({'completed_archives':2,'completed_with_format_error':1,'ready_A':13,'wiki_report':'final_project_cs/wiki/records/reports/2026-10-08_gemma-original-h-completion.md'},ensure_ascii=True))
