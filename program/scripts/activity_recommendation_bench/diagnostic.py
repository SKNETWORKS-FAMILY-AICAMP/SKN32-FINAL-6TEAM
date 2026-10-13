"""Separate, budget-shared output-limit diagnostic; never mixes into main results."""
import argparse
import json
import random
import time
from datetime import datetime, timezone

import bench


def run(run_id):
    data_dir = bench.ROOT / bench.CONFIG['dataset_directory']
    source = data_dir / 'raw' / bench.CONFIG['evaluation_file']
    cases = sorted([json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()], key=lambda c: c['case_id'])[:5]
    directory = data_dir / 'runs' / run_id
    directory.mkdir(parents=True, exist_ok=False)
    config_original = dict(bench.CONFIG)
    bench.CONFIG['max_output_tokens'] = 4096
    metadata = {'diagnostic': True, 'selection': 'lexicographic first five case IDs, not selected by outcome',
                'config': bench.CONFIG, 'original_config': config_original, 'case_ids': [c['case_id'] for c in cases],
                'started_at': datetime.now(timezone.utc).isoformat(), 'dataset_hash': bench.digest(source.read_bytes()),
                'prompt_hash': bench.digest(bench.PROMPT.encode('utf-8')), 'repeats': 1, 'independent_cases': 5,
                'auto_retries': 0, 'tools': [], 'main_results_modified': False}
    (directory / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    budget = bench.Budget(data_dir)
    providers = bench.Providers(budget, directory)
    try:
        for i, case in enumerate(cases):
            pool = [c for c in case['candidates'] if bench.feasible(case, c)]
            random.Random(bench.CONFIG['seed'] + int(bench.digest(case['case_id'].encode())[:8], 16)).shuffle(pool)
            for lane in (['nano', 'luna'] if i % 2 == 0 else ['luna', 'nano']):
                result = providers.rank(lane, case, pool)
                bench.append(directory / 'results.jsonl', {'case_id': case['case_id'], 'group': case['group'],
                    'repeat': 0, 'condition': 'output_limit_4096_diagnostic', 'candidate_order': [c['id'] for c in pool],
                    'arm': lane + '_direct', **result, 'metrics': bench.evaluate(case, result.get('ranking', []))})
                time.sleep(bench.CONFIG['pause_seconds'])
            print(json.dumps({'diagnostic_completed_cases': i + 1, 'total_cases': 5, 'ledger_usd': budget.spent()}), flush=True)
    finally:
        print(json.dumps({'diagnostic_run': run_id, 'ledger_usd': budget.spent()}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    run(parser.parse_args().run_id)
