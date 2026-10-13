"""Strict paired quality comparison; latency describes one pass only."""
import argparse
import json
import statistics
from pathlib import Path


def load(path):
    rows = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        rows[row['i']] = row
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--strata', required=True)
    ap.add_argument('--baseline', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    items = json.loads(Path(args.input).read_text(encoding='utf-8'))
    candidate, baseline = load(args.strata), load(args.baseline)
    groups = {}
    for kind in ('mixed', 'control'):
        for label, selected in (
            ('item', [x for x in items if x['kind'] == kind and x['gold'] is not None]),
            ('none', [x for x in items if x['kind'] == kind and x['gold'] is None]),
        ):
            summary = {'n': len(selected)}
            paired = {'strata_only_correct': 0, 'baseline_only_correct': 0}
            for name, rows in (('strata', candidate), ('baseline', baseline)):
                recs = [rows.get(x['i'], {}) for x in selected]
                correct = sum(bool(r.get('parsed')) and r.get('pick') == x['gold']
                              for r, x in zip(recs, selected))
                latencies = [r['ms'] for r in recs if r.get('parsed') and 'ms' in r]
                summary[name] = {
                    'correct': correct, 'accuracy': correct / len(selected) if selected else None,
                    'missing_or_failed': sum(not r.get('parsed', False) for r in recs),
                    'wrong_item_selections': sum(bool(r.get('parsed')) and r.get('pick') is not None
                                                 and r.get('pick') != x['gold']
                                                 for r, x in zip(recs, selected)),
                    'latency_valid_n': len(latencies),
                    'latency_median_ms': statistics.median(latencies) if latencies else None,
                }
            for x in selected:
                a, b = candidate.get(x['i'], {}), baseline.get(x['i'], {})
                ca = bool(a.get('parsed')) and a.get('pick') == x['gold']
                cb = bool(b.get('parsed')) and b.get('pick') == x['gold']
                paired['strata_only_correct'] += ca and not cb
                paired['baseline_only_correct'] += cb and not ca
            summary['paired'] = paired
            groups[f'{kind}_{label}'] = summary
    report = {'groups': groups,
              'limitations': ['Synthetic input; one pass per model.',
                              'Different models and engines: no engine-only speedup claim.',
                              'Failures and missing answers remain in the full denominator.']}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
