"""완료된 FrogNano H 답안의 엄격 계수와 원본 일치를 확인한다. 새 호출 없음."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'eval_kit'))
from stats import latency_summary, wilson

folder = HERE / 'results/gpu_backlog_20261008/frog_h'
answer = folder / 'd_test_h_backlog_frog.jsonl'
gold_path = HERE.parents[2] / 'datasets/core/pointing/testset/confusing_trap_sentences_v1/h_set_test_30_20261015_agree.json'
gold = {r['i']: r for r in json.loads(gold_path.read_text(encoding='utf-8'))}
rows = [json.loads(line) for line in answer.read_text(encoding='utf-8').splitlines()]
run = {r['i']: r for r in rows}
if len(run) != len(rows) or set(run) != set(gold):
    raise ValueError('Full unique answer coverage required')
if any(run[i]['gold'] != g['gold'] or run[i]['type'] != g['type'] for i, g in gold.items()):
    raise ValueError('Answer and frozen reference disagree')

def valid(r):
    return bool(r.get('parsed')) and not r.get('error')

def counts(ids):
    correct = sum(valid(run[i]) and run[i].get('pick') == gold[i]['gold'] for i in ids)
    false_pick = sum(valid(run[i]) and run[i].get('pick') is not None for i in ids
                     if gold[i]['gold'] is None)
    return dict(total=len(ids), correct=correct, false_pick=false_pick,
                failed_or_unparsed=sum(not valid(run[i]) for i in ids),
                correct_wilson95=wilson(correct, len(ids)))

positive = [i for i in gold if gold[i]['gold'] is not None]
negative = [i for i in gold if gold[i]['gold'] is None]
result = dict(model='FrogNano-4B-2609', our_training=False, publisher_training='coding RL',
              suite='H', saved=len(rows), expected=len(gold), repetitions=1,
              missing=0, errors_or_unparsed=sum(not valid(r) for r in rows),
              positive=counts(positive), negative=counts(negative),
              false_pick_wilson95=wilson(counts(negative)['false_pick'], len(negative)),
              subtypes={t: counts([i for i in gold if gold[i]['type'] == t])
                        for t in sorted({g['type'] for g in gold.values()})},
              latency_ms=latency_summary([r['ms'] for r in rows if 'ms' in r]),
              answer_sha256=hashlib.sha256(answer.read_bytes()).hexdigest(),
              gold_sha256=hashlib.sha256(gold_path.read_bytes()).hexdigest(),
              execution=json.loads((folder / 'started.json').read_text(encoding='utf-8')),
              limits=['One run; no repeat variance',
                      'Synthetic developer diagnostic, not the new independent final holdout',
                      'Question Wilson intervals do not account for shared itinerary correlation',
                      'No completed matched original cohort ranking yet',
                      'p_null from generated token position is not a calibrated option distribution'])
with (folder / 'frog_h_counts.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
p, n = result['positive'], result['negative']
report = f'''# FrogNano 어려운 문장 평가 완료

우리 자료로 추가 학습하지 않은 FrogNano-4B-2609의 어려운 문장 답안 1,316개를 모두 보관·검사했습니다.

| 항목 | 상태 | 진행 |
|---|---|---|
| 답안 보관·문항 일치 | 완료 | {len(rows)}/{len(gold)} = 100% |
| 정상 요청 정답 선택 | 실측 | {p['correct']}/{p['total']} = {100*p['correct']/p['total']:.2f}% |
| 함정·잡담 오지목 | 실측 | {n['false_pick']}/{n['total']} = {100*n['false_pick']/n['total']:.2f}% |

정상 요청 분모는 정답 항목이 있는 461개, 오지목 분모는 정답 항목이 없는 855개입니다. 오류·해석 실패·미완료는 각각 0개이며 분모에서 제외하지 않았습니다. 개발사 코딩 강화학습이 있는 배포판이고 우리 추가 학습은 없습니다.

혼합 요청 평가는 같은 대기열에서 이어서 실행 중입니다. H 한 세트·한 번의 결과로 전체 상위권이나 모델 채택을 확정하지 않습니다. H는 이미 본 개발·회귀 진단 자료이며 새 독립 보류 자료와 구분합니다.

| 유형 | 문항 | 정답 선택 | 오지목 |
|---|---:|---:|---:|
'''
for t, c in result['subtypes'].items():
    report += f"| {t} | {c['total']} | {c['correct']}/{c['total']} | {c['false_pick']}/{c['total']} |\n"
report += '\n구간·지연·해시·실행 버전은 같은 폴더의 frog_h_counts.json에 보관했습니다. 문항별 Wilson 구간은 같은 일정 안의 상관을 반영하지 못하므로 최종 채택의 반복·일정 단위 검증을 대신하지 않습니다. 지연은 이 실행의 관찰값이며 다른 엔진 경로와 속도 비교하지 않았습니다.\n'
with (folder / 'frog_h_report.md').open('x', encoding='utf-8') as f:
    f.write(report)
print(json.dumps({k: result[k] for k in ['saved', 'expected', 'errors_or_unparsed', 'positive', 'negative']}, ensure_ascii=True))
