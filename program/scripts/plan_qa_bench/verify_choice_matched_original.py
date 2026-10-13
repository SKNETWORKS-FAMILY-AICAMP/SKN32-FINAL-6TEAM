"""완료된 직접 선택 답안을 같은 기반 원본과 고정 문항별로 대조한다."""
from pathlib import Path
import hashlib
import json
import sys
from scipy.stats import binomtest

BASE = Path(__file__).resolve().parent/'results/gpu_backlog_20261008'
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
valid = lambda r: bool(r.get('parsed')) and not r.get('error')
correct = lambda r: valid(r) and r['pick'] == r['gold']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    job, original, observation = sys.argv[1:4]
    assert job != original
    trained, baseline = read(BASE/job/'choice_counts.json'), read(BASE/original/'choice_counts.json')
    assert trained['our_training'] and not baseline['our_training']
    assert trained['suite'] == baseline['suite']
    snap = read(BASE/f'A_snapshot_{observation}.json')
    assert snap['state']['jobs'][job]['status'].startswith('completed')
    registration = next(x for x in snap['manifest']['jobs'] if x['id']==job)
    assert trained['execution']['job']['lora_sha256'] == registration['lora_sha256']
    for key in ['prompt_sha256','script_sha256','engine_version']:
        assert trained['execution'][key] == baseline['execution'][key]
    assert trained['execution']['job']['model_sha256'] == baseline['execution']['job']['model_sha256']
    def load_answers(folder, r):
        path = folder/f"d_test_{r['execution']['job']['tag']}.jsonl"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == r['answer_sha256']
        rows = [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
        by_id = {x['i']:x for x in rows}
        assert len(rows) == len(by_id) == r['saved'] == r['expected'] and r['missing']==0
        assert sum(not valid(x) for x in rows) == r['failed_or_unparsed']
        return by_id
    ours, old = load_answers(BASE/job, trained), load_answers(BASE/original, baseline)
    assert set(ours) == set(old)
    assert all(ours[i]['gold']==old[i]['gold'] and ours[i]['type']==old[i]['type'] for i in ours)
    groups = {}
    for label, positive in [('positive',True),('negative',False)]:
        ids = [i for i,x in ours.items() if x['type']!='compound_intent' and (x['gold'] is not None)==positive]
        for data, counts in [(ours,trained[label]),(old,baseline[label])]:
            assert len(ids)==counts['total']
            assert sum(correct(data[i]) for i in ids)==counts['correct']
            assert sum(not valid(data[i]) for i in ids)==counts['failed_or_missing']
            assert sum(valid(data[i]) and data[i]['gold'] is None and data[i]['pick'] is not None for i in ids)==counts['false_pick']
        gain = sum(correct(ours[i]) and not correct(old[i]) for i in ids)
        loss = sum(correct(old[i]) and not correct(ours[i]) for i in ids)
        groups[label] = dict(total=len(ids), original=baseline[label], our_travel_adapter=trained[label],
            trained_only_correct=gain, original_only_correct=loss,
            exact_p=binomtest(gain,gain+loss).pvalue if gain+loss else 1)
    result = dict(original_job=original, trained_job=job, suite=trained['suite'],
        original_model=baseline['model'], our_adapter_model=trained['model'],
        original_answer_sha256=baseline['answer_sha256'], trained_answer_sha256=trained['answer_sha256'],
        full_ids_gold_type_match=True, frozen_input_script_engine_model_match=True,
        registered_adapter_hash_match=True, original_our_training=False, adapter_our_training=True,
        groups=groups, repetitions=1, final_ranking=False,
        limitations=['existing developer/regression suite','paired exact test does not replace independent holdout or seed repeats','no direct speed comparison'])
    with (BASE/job/'matched_original.json').open('x',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    main()
