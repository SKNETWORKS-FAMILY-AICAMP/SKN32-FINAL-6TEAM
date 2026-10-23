"""Fail-closed preparation gate. This script never launches or stops a GPU process."""
import argparse
import json
from pathlib import Path

REPO = 'ConwayResearch/Underdog-Saluki-27B-1.0'
REVISION = '1336c0b5d74dfe6ad7f793577092f5effd9f97c6'

def evaluate(candidate, stage='baseline'):
    if stage not in ('smoke', 'baseline', 'adoption'):
        raise ValueError('unknown stage')
    checks = {
        'same_saluki_identity': candidate.get('repo') == REPO and candidate.get('revision') == REVISION,
        'same_weight_lineage_verified': candidate.get('same_weight_lineage_verified') is True,
        'cuda_backward_verified': candidate.get('cuda_backward_verified') is True,
        'train_data_audited': candidate.get('train_data_audited') is True,
        'local_weights_verified': candidate.get('local_weights_verified') is True,
        'space_with_reserve': candidate.get('free_bytes', 0) >= candidate.get('required_bytes', 1) + 3 * 1024**3,
        'gpu_exclusive_lock_available': candidate.get('gpu_exclusive_lock_available') is True,
        'no_failed_attempt_retry': candidate.get('failed_attempt_requires_fix') is False,
    }
    if stage != 'smoke':
        checks['gpu_smoke_passed'] = candidate.get('gpu_smoke_passed') is True
    if stage == 'adoption':
        checks.update(independent_holdout_frozen=candidate.get('independent_holdout_frozen') is True,
                      independent_final_evaluation_passed=candidate.get('independent_final_evaluation_passed') is True,
                      normal_and_none_regression_passed=candidate.get('normal_and_none_regression_passed') is True)
    return {'repo': REPO, 'revision': REVISION, 'stage': stage, 'status': 'ready_for_reviewed_queue_registration' if all(checks.values()) else 'preparation_blocked',
            'checks': checks, 'passed': sum(checks.values()), 'total': len(checks),
            'blockers': [key for key, passed in checks.items() if not passed],
            'training_started': False, 'queue_worker_started': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('smoke', 'baseline', 'adoption'), default='baseline')
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding='utf-8-sig'))
    result = evaluate(data.get('gate_input', data), args.stage)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))
