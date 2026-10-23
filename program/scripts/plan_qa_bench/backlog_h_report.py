"""보관된 원본 모델 H 답안을 전체 고정 분모로 집계한다."""
import json, sys, hashlib
from pathlib import Path
from backlog_mx_report import summarize, valid
HERE=Path(__file__).resolve().parent
job=sys.argv[1]
folder=HERE/'results/gpu_backlog_20261008'/job
execution=json.loads((folder/'started.json').read_text(encoding='utf-8'))
answer=folder/f"d_test_{execution['job']['tag']}.jsonl"
gold_path=HERE.parents[2]/'datasets/core/pointing/testset/confusing_trap_sentences_v1/h_set_test_30_20261015_agree.json'
gold=json.loads(gold_path.read_text(encoding='utf-8'))
rows=[json.loads(l) for l in answer.read_text(encoding='utf-8').splitlines()]
run={r['i']:r for r in rows}; ref={r['i']:r for r in gold}
assert len(rows)==len(run) and set(run)<=set(ref)
assert all(r['gold']==ref[i]['gold'] and r['type']==ref[i]['type'] for i,r in run.items())
positive=summarize([r for r in gold if r['gold'] is not None],run)
negative=summarize([r for r in gold if r['gold'] is None],run)
failed=[r for r in rows if not valid(r)]
label=execution['job']['label']
publisher=execution['job'].get('publisher_training') or ('Instruct release' if label.startswith('Gemma') else 'See publisher model card; exact training method not verified in this run')
display=('Jev 계열 모델 중 '+label) if label.startswith('Winnow') else label
result={'model':label,'our_training':execution['job']['our_training'],'publisher_training':publisher,
 'saved':len(rows),'expected':len(ref),'missing':len(set(ref)-set(run)),'failed_or_unparsed':len(failed),
 'positive':positive,'negative':negative,'subtypes':{t:summarize([r for r in gold if r['type']==t],run) for t in sorted({r['type'] for r in gold})},
 'failed_records':failed,'answer_sha256':hashlib.sha256(answer.read_bytes()).hexdigest(),
 'gold_sha256':hashlib.sha256(gold_path.read_bytes()).hexdigest(),'execution':execution,'repetitions':1,'final_ranking':False}
with (folder/'h_counts.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
report=f'''# {display} — 어려운 문장 평가

우리 자료 추가 학습 여부: {result['our_training']}. 개발사 학습 역할 기록: {publisher}. 공식 카드로 확인하지 않은 모델을 지시 학습 배포판이라고 단정하지 않습니다.

| 항목 | 상태 | 진행 |
|---|---|---|
| 답안 보관 | 완료 | {len(rows)}/{len(ref)} = {100*len(rows)/len(ref):.2f}% |
| 정상 요청 정답 | 실측 | {positive['correct']}/{positive['total']} = {100*positive['correct']/positive['total']:.2f}% |
| 요청 없음 오지목 | 실측 | {negative['false_pick']}/{negative['total']} = {100*negative['false_pick']/negative['total']:.2f}% |
| 실패·해석 불가 | 실측 | {len(failed)}/{len(ref)} = {100*len(failed)/len(ref):.2f}% |

분모는 정상 요청461개와 요청 없음855개입니다. 누락·실패를 분모에서 제외하지 않습니다. 실패한 null 출력은 요청 없음 정답으로 세지 않습니다. 실패는 오지목 계수와 별도로 표시하며 전체 정답률에서는 오답입니다.

[집계·실패 원문·실행 조건](h_counts.json)에 기록했습니다. 요구한 단일 번호 대신 배열을 낸 문항은 계약 위반으로 보존하며 번호 하나로 고쳐 정답 처리하지 않습니다. 해당 평가 전체를 다시 시작하지 않았습니다. 모델 실행1회·기존 개발/회귀 자료이며 같은 원본 비교군 전체 시험과 새 독립 보류 검증 전에 순위를 확정하지 않습니다.
'''
with (folder/'h_report.md').open('x',encoding='utf-8') as f:f.write(report)
print(json.dumps({k:result[k] for k in ['saved','expected','failed_or_unparsed','answer_sha256','positive','negative']},ensure_ascii=True))
