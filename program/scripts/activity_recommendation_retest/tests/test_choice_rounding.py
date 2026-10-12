"""Actual API rounding boundary; active after the post-eval parser repair."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from providers import choice_answer

def test_reported_mass_point_99_has_a_valid_unrounded_distribution():
    probabilities={'a':.41,'b':.29,'c':.29}
    assert choice_answer({'choice':'a','probabilities':probabilities},set(probabilities))['ranking']==['a']

def test_bad_mass_cannot_be_explained_by_rounding():
    with pytest.raises(ValueError):choice_answer({'choice':'a','probabilities':{'a':.7,'b':.7}},{'a','b'})

def test_selected_id_must_have_maximum_probability_up_to_rounding():
    with pytest.raises(ValueError):choice_answer({'choice':'b','probabilities':{'a':.8,'b':.2}},{'a','b'})

def test_unknown_or_missing_id_is_rejected():
    with pytest.raises(ValueError):choice_answer({'choice':'outside','probabilities':{'a':.5,'b':.5}},{'a','b'})

def test_nonfinite_probability_is_rejected():
    with pytest.raises(ValueError):choice_answer({'choice':'a','probabilities':{'a':float('nan'),'b':.5}},{'a','b'})

def test_actual_saved_development_distribution_is_accepted():
    import json
    from providers import ROOT,CONFIG
    directory=ROOT/CONFIG['dataset_directory']/'runs/dev-v1'
    row=next(json.loads(s) for s in (directory/'results.jsonl').read_text(encoding='utf-8').splitlines()
       if json.loads(s)['arm']=='jev_choice' and json.loads(s)['status']=='failed')
    raw=json.loads((directory/'responses'/(row['call_ids'][0]+'.json')).read_text(encoding='utf-8'))
    answer=raw['answers']['best']
    assert choice_answer(answer,set(answer['probabilities']))['ranking']==[answer['choice']]

def test_choice_chunks_keep_candidate_facts_once_and_cover_all_candidates():
    from providers import Providers,CONFIG
    client=Providers.__new__(Providers);requests=[]
    def call(lane,request,parser):
        requests.append(request);criteria=request['questions']['best']['criteria']
        selected=next(iter(criteria));probabilities={cid:float(cid==selected) for cid in criteria}
        return {'status':'ok','cost_usd':0,'latency_ms':0,'call_ids':[],**parser({'answers':{'best':{'choice':selected,'probabilities':probabilities}}})}
    client.call=call
    candidates=[{'id':f'id_{i}','category':'문화','description':f'설명{i}','description_evidence_id':f'ev_{i}',
        'facts':{'travel_min':{'value':i}}} for i in range(70)]
    result=client.choice({'customer':{'likes':[]},'weights':{},'origin':{},'candidates':candidates})
    assert result['status']=='ok' and len(requests)==3
    assert all('candidates' not in r['state'] for r in requests)
    assert all(len(r['questions']['best']['criteria'])<=CONFIG['choice_chunk_size'] for r in requests)
    assert set().union(*(set(r['questions']['best']['criteria']) for r in requests[:2]))=={c['id'] for c in candidates}
    assert all('facts' in c for r in requests for c in r['questions']['best']['criteria'].values())
