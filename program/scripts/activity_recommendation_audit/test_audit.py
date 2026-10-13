import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('activity_saved_audit', Path(__file__).with_name('audit.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_cache_rates_replace_input_not_add_to_it():
    usage = {'input_tokens':100,'input_tokens_details':{'cached_tokens':30,'cache_write_tokens':20},'output_tokens':10}
    rates = {'input':2,'cached_input':.2,'cache_write':2.5,'output':5}
    assert audit.estimate_cost(usage,rates,'observed_usage') == pytest.approx(.000206)
    assert audit.estimate_cost(usage,rates,'no_cache_same_tokens') == pytest.approx(.00025)
    assert audit.estimate_cost(usage,rates,'all_cache_read_same_tokens') == pytest.approx(.00007)


def test_recursive_oracle_removal():
    original = {'customer':[{'oracle_taste':1,'labels':{},'expected':'x','gold':['x'],'kept':'fact'}]}
    assert audit.public(original) == {'customer':[{'kept':'fact'}]}


def test_generated_pack_is_development_and_blinded():
    directory = audit.DATA / 'audit-20261010-v1'
    cases = json.loads((directory/'human-review-development/cases.json').read_text(encoding='utf-8'))
    labels = json.loads((directory/'human-review-development/labels.blank.json').read_text(encoding='utf-8'))
    saved = json.loads((directory/'audit.json').read_text(encoding='utf-8'))
    assert len(cases)==len(labels)==24
    for case in cases:
        assert audit.public(case)==case
        assert 'group' not in case
        assert len({c['id'] for c in case['candidates']})==14
        assert all(c['id'].startswith('place_') and '_c01' not in c['id'] for c in case['candidates'])
        assert all('01-01' not in c['name'] for c in case['candidates'])
    assert all(r['status']=='pending' and r['is_human'] is None and not r['preferred_top3'] for x in labels for r in x['reviewers'])
    assert saved['human_review']['holdout'] is False
    assert saved['human_review']['completed_human_reviews']==0
    assert saved['paid_api_calls']==0


def test_immutable_output_refuses_overwrite():
    with pytest.raises(FileExistsError):
        audit.run(audit.DATA/'audit-20261010-v1')
