"""Compare the same D3 item IDs, keeping failures in the denominator."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = HERE / 'results/d_test'


def load(path, field):
    if not path.exists():
        return {}
    return {r[field]: r for line in path.read_text(encoding='utf-8').splitlines()
            if (r := json.loads(line))}


def main():
    input_path = HERE.parents[2] / 'datasets/core/pointing/testset/synthetic_chitchat_plus_questions_v1/source/all_prompts_d3_mai_2026-10-08.json'
    direct_items = json.loads(input_path.read_text(encoding='utf-8'))
    verification_items = [x for x in json.loads((D / 'verify_inputs.json').read_text(encoding='utf-8')) if x['ds'] == 'D3']
    gold = {x['i']: x['gold'] for x in direct_items}
    results = {'direct': {}, 'verification': {}, 'limitations': [
        'MAI through Copilot CLI, FrogNano through local llama.cpp; latency paths differ.',
        'Neither model was trained with our data. FrogNano has publisher coding RL.',
        'Synthetic D3; one pass. MAI p_yes is declared confidence, not token probability.',
        'Incomplete, parsing and transport failures remain in denominators.']}
    for label, direct_name, verify_name in (
        ('MAI-Code-1.1-Flash', 'd_test_d3_mai_code_1_1_flash.jsonl', 'verify_mai_code_1_1_flash.jsonl'),
        ('FrogNano-4B-2609', 'd_test_d3_frog.jsonl', 'verify_frog.jsonl'),
    ):
        rows = load(D / direct_name, 'i')
        groups = {}
        for name, items in (('actual_request', [x for x in direct_items if x['gold'] is not None]),
                            ('chitchat', [x for x in direct_items if x['gold'] is None])):
            selected = [rows.get(x['i'], {}) for x in items]
            groups[name] = {'n': len(items),
                'completed': sum(bool(r) for r in selected),
                'correct': sum(bool(r.get('parsed')) and r.get('pick') == x['gold'] for r, x in zip(selected, items)),
                'wrong_item_selected': sum(bool(r.get('parsed')) and r.get('pick') is not None and r.get('pick') != x['gold'] for r, x in zip(selected, items)),
                'missing_or_failed': sum(not r.get('parsed', False) for r in selected)}
        results['direct'][label] = groups
        rows = load(D / verify_name, 'key')
        groups = {}
        for name, wanted in (('retain_correct', True), ('reject_wrong', False)):
            items = []
            for item in verification_items:
                _, item_id, pick = item['key'].split('|')
                assert int(item_id) in gold
                if (int(pick) == gold[int(item_id)]) == wanted:
                    items.append(item)
            selected = [rows.get(x['key'], {}) for x in items]
            groups[name] = {'n': len(items), 'completed': sum(bool(r) for r in selected),
                'correct': sum(r.get('content', '').strip() == ('YES' if wanted else 'NO') for r in selected),
                'missing_or_failed': sum('error' in r or r.get('content', '').strip() not in ('YES', 'NO') for r in selected)}
        results['verification'][label] = groups
    output = HERE / 'results/mai_frog_comparison_2026-10-08.json'
    if output.exists():
        backup = output.parent / '_backup/mai_frog_reports'
        backup.mkdir(parents=True, exist_ok=True)
        import time
        (backup / f'{time.time_ns()}.json').write_bytes(output.read_bytes())
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
