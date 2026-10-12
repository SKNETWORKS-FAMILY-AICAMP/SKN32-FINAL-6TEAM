"""Gold-plan injection into the real read component, with explicit partial coverage.

No LLM, DB mutation, API, or invented place fact is used. Unsupported actions and
facts remain in the 467-row ledger and are NOT counted as passed logic tests.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
from uuid import uuid5, NAMESPACE_URL
import collections
import hashlib
import json
import os
import sys


def probe(row, gold):
    requests = gold['requests']
    result = {'case_id': row['case_id'], 'logic_tested': False,
              'full_app_executor_tested': False, 'factual_answer_tested': False}
    if not requests or any(r['action'] != 'read' or r['mode'] != 'answer' for r in requests):
        return dict(result, status='outside_read_component_scope')
    supported = {'start': 'time', 'duration': 'duration'}
    if any(r.get('guard') or r.get('depends_on') or set(r['values']) != {'fact'}
           or r['values']['fact'] not in supported or len(r['target_ids']) != 1 for r in requests):
        return dict(result, status='unmapped_contract_or_fact')
    from app.domains.travel_ops.components.conversation import read_requests, trip_facts
    from app.domains.travel_ops.components.conversation.decision_unit import Decision
    source = row['input']; items = []; aliases = {}; expected = []
    for seq, (ident, item) in enumerate(source['items'].items(), 1):
        stop = SimpleNamespace(item_id=uuid5(NAMESPACE_URL, 'e2-test-only/' + ident), seq=seq,
            title=item['title'], kind=item['kind'], detail={},
            place={'name': item['place']} if item.get('place') else None,
            starts_at=datetime.fromisoformat(item['date']+'T'+item['start']+':00+09:00'),
            ends_at=datetime.fromisoformat(item['date']+'T'+item['end']+':00+09:00') if item.get('end') else None)
        items.append(stop); aliases[ident] = stop
    alias_by_uuid = {str(item.item_id): f"i{n}" for n,item in enumerate(trip_facts._stops(items),1)}
    reads = []; expected_targets = []
    for request in requests:
        ident=request['target_ids'][0]; item=aliases.get(ident)
        if item is None:
            return dict(result, status='fixture_target_missing')
        fact = request['values']['fact']
        reads.append(dict(fact=supported[fact], target_item=alias_by_uuid[str(item.item_id)], reference='explicit',
                          origin_item='none', query=None, text='', advice=''))
        expected_targets.append(str(item.item_id))
        if fact == 'start':
            expected.append(source['items'][ident]['start'])
        elif item.ends_at is not None:
            expected.append(str(int((item.ends_at-item.starts_at).total_seconds()/60))+'분')
        else:
            return dict(result, status='fixture_end_missing')
    decision = Decision(action='answer_fact', item=aliases[requests[0]['target_ids'][0]],
                        change=None, fact=reads[0]['fact'], minutes=None, question='', reads=reads)
    now=datetime.fromisoformat(source['received_at'])
    try:
        outcome, basis, focus = read_requests.reply(decision, items=items, message=source['message'],
            selected=None, turns=[], version=source['itinerary_version'], now=now,
            context_now=now, ttl_seconds=1800, place_source=None)
        unresolved = [x.get('unresolved') for x in basis['questions'] if x.get('unresolved')]
        correct = [x.get('item_id') for x in basis['questions']] == expected_targets and len(basis['questions']) == len(requests) and not unresolved and all(x in outcome['text'] for x in expected)
        return dict(result, logic_tested=True, status='component_checks_passed' if correct else 'component_check_failed',
                    component_correct=correct, outcome=outcome, basis=basis, expected_fragments=expected,
                    intervention='reviewed correct read targets injected; selection/history resolution and writes not tested')
    except Exception as exc:
        return dict(result, logic_tested=True, status='component_exception', error=type(exc).__name__, detail=str(exc)[:300])


def main():
    root=Path(__file__).parent
    config=json.loads((root/'config.json').read_text())
    sys.path[:0]=[config['source'], config['dependencies']]
    for relative, expected in config['source_hashes'].items():
        assert hashlib.sha256((Path(config['source'])/relative).read_bytes()).hexdigest()==expected
    rows=list(map(json.loads,(root/'inputs.jsonl').read_text().splitlines()))
    gold={r['case_id']:r['gold'] for r in map(json.loads,(root/'gold.jsonl').read_text().splitlines())}
    if '--preflight-only' in sys.argv:
        candidates=[r for r in rows if all(x['action']=='read' and x['values']=={'fact':'start'} for x in gold[r['case_id']]['requests']) and gold[r['case_id']]['requests']]
        assert candidates
        result=probe(candidates[0],gold[candidates[0]['case_id']]);assert result.get('component_correct'),result
        print(json.dumps({'preflight':result['status'],'GPU_started':False}));return
    counts=collections.Counter()
    with Path('d_test_'+os.environ['TAG']+'.jsonl').open('x',encoding='utf8') as output:
        for i,row in enumerate(rows):
            result=probe(row,gold[row['case_id']]);counts[result['status']]+=1
            output.write(json.dumps({'i':i,'parsed':result},ensure_ascii=False)+'\n')
    Path('component_summary.json').write_text(json.dumps(dict(planned=len(rows),status_counts=counts,
        full_app_executor_tested=False,model_tested=False,causal_attribution='pending raw outputs and equivalent-representation review; partial real read-component intervention only'),indent=2))


if __name__=='__main__':main()
