"""Audit existing travel SFT data against fixed development fixtures, without changing data."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / 'program/scripts/plan_qa_bench'

def normalize(text):
    return re.sub(r'\s+', '', text).casefold()

def question(row):
    if isinstance(row.get('q'), str):
        return row['q']
    found = re.search(r'고객 질문:\s*(.*?)\n\n', row.get('prompt', ''), re.S)
    return found.group(1).strip() if found else None

def rows(path):
    text = path.read_text(encoding='utf-8-sig')
    return [json.loads(line) for line in text.splitlines() if line.strip()] if path.suffix == '.jsonl' else json.loads(text)

def audit(train_path):
    train = rows(train_path)
    fixtures = [(name, BENCH / 'results/empty_probe' / filename) for name, filename in
                [('D', 'all_prompts.json'), ('D2', 'all_prompts_d2.json'), ('D3', 'all_prompts_d3.json')]]
    fixtures += [('H', BENCH / 'results/hard_set/h_set_test_30_20261015_agree.json'),
                 ('E_pair', ROOT / 'datasets/travel/mx_testset/mx_main_prompts.json')]
    errors = []
    for i, row in enumerate(train):
        try:
            answer = json.loads(row['completion'])
            if answer.get('item') != row['gold']:
                errors.append({'row': i, 'reason': 'gold_completion_mismatch'})
        except (KeyError, json.JSONDecodeError):
            errors.append({'row': i, 'reason': 'invalid_schema_or_completion'})
    qcounts = Counter(normalize(q) for row in train if (q := question(row)))
    pcounts = Counter(normalize(row['prompt']) for row in train)
    result = {'train_path': str(train_path.relative_to(ROOT)), 'train_rows': len(train),
              'sha256': hashlib.sha256(train_path.read_bytes()).hexdigest(),
              'type_counts': dict(Counter(row['type'] for row in train)),
              'none_rows': sum(row['gold'] is None for row in train),
              'gold_counts': dict(Counter(str(row['gold']) for row in train)),
              'completion_errors': errors, 'unparsed_question_rows': sum(question(row) is None for row in train),
              'duplicate_prompt_excess': sum(n - 1 for n in pcounts.values()),
              'duplicate_question_excess': sum(n - 1 for n in qcounts.values()), 'fixtures': []}
    for name, path in fixtures:
        fixture = rows(path)
        queries = [question(row) for row in fixture]
        result['fixtures'].append({'set': name, 'path': str(path.relative_to(ROOT)), 'rows': len(fixture),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'exact_prompt_overlap_rows': sum(normalize(row['prompt']) in pcounts for row in fixture),
            'exact_question_overlap_rows': sum(q is not None and normalize(q) in qcounts for q in queries),
            'unparsed_question_rows': sum(q is None for q in queries)})
    result['independent_holdout_verified'] = False
    result['limitations'] = ['Exact matching does not prove semantic independence.',
                            'Itinerary-family/source-document grouping and human label review still required.',
                            'These evaluated fixtures are development diagnostics, never final holdout.']
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--train', type=Path, default=ROOT / 'datasets/travel/train_oos/train_oos.jsonl')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = audit(args.train)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: output[k] for k in ('train_rows', 'completion_errors', 'none_rows', 'fixtures')}, ensure_ascii=False))
