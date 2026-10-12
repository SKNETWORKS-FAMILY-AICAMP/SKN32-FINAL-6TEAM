"""Run disjoint common/travel suites without moving shared fixtures.

Manifest paths are explicit. Unassigned collected tests are errors, not silently skipped.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class SuiteSelector:
    def __init__(self, suite, manifest, output):
        self.suite, self.manifest, self.output = suite, manifest, output

    def pytest_ignore_collect(self, collection_path, config):
        if self.suite=='all' or collection_path.suffix!='.py':
            return None
        path=collection_path.resolve().relative_to(ROOT).as_posix()
        other='travel' if self.suite=='common' else 'common'
        return True if path in self.manifest[other] else None

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session, config, items):
        import pytest
        common=set(self.manifest['common'])
        travel=set(self.manifest['travel'])
        if common & travel:
            raise pytest.UsageError('Suite manifest has overlapping file paths')
        all_ids={'common':[], 'travel':[]}
        selected, deselected=[],[]
        missing=[]
        for item in items:
            path=Path(str(item.path)).resolve().relative_to(ROOT).as_posix()
            group='common' if path in common else 'travel' if path in travel else None
            if group is None:
                missing.append(path);continue
            all_ids[group].append(item.nodeid)
            (selected if self.suite in ('all',group) else deselected).append(item)
        if missing:
            raise pytest.UsageError('Classify new test files first: '+', '.join(sorted(set(missing))))
        result={'suite':self.suite,'common_nodeids':all_ids['common'],'travel_nodeids':all_ids['travel'],
                'collected_total':len(items),'selected':len(selected),'deselected':len(deselected),
                'overlap':len(set(all_ids['common']) & set(all_ids['travel'])), 'unassigned':len(missing)}
        if self.output:
            target=Path(self.output)
            if target.exists():
                raise pytest.UsageError('Use a new output name; do not overwrite previous evidence')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        config.hook.pytest_deselected(items=deselected)
        items[:]=selected


def main():
    import pytest
    parser=argparse.ArgumentParser()
    parser.add_argument('--suite',choices=['common','travel','all'],required=True)
    parser.add_argument('--json-output')
    args,rest=parser.parse_known_args()
    manifest=json.loads((ROOT/'tests/test-suites.json').read_text(encoding='utf-8'))
    return pytest.main(rest, plugins=[SuiteSelector(args.suite,manifest,args.json_output)])


if __name__=='__main__':
    raise SystemExit(main())
