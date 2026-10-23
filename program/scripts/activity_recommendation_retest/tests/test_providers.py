import copy
import importlib.util
from pathlib import Path
import sys
import pytest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from providers import price_usage,validation,compact,Providers,score_value

def test_independent_api_rounding_is_accepted_without_replacing_score():
    assert score_value({'score':2.26,'probabilities':{'0':.11,'1':.23,'2':.21,'3':.18,'4':.27}})==.565

def test_material_score_distribution_mismatch_is_rejected():
    with pytest.raises(ValueError,match='score_distribution_mismatch'):
        score_value({'score':3,'probabilities':{'0':.11,'1':.23,'2':.21,'3':.18,'4':.27}})

def test_material_distribution_mass_error_is_rejected():
    with pytest.raises(ValueError,match='invalid_distribution'):
        score_value({'score':2,'probabilities':{'0':.1,'1':.1,'2':.1,'3':.1,'4':.1}})

def fixture():
    return {'customer':{'text':'조용함 선호'},'candidates':[{'id':'opaque-a','category':'문화','description':'차분하게 앉아 감상합니다.',
       'description_evidence_id':'desc_a','facts':{'travel_min':{'value':5,'observed_at':'2026-10-10T00:00:00+09:00','evidence_id':'ev'}}}]}

def answer():
    return {'ranking':['opaque-a'],'reasons':[{'candidate_id':'opaque-a','evidence_id':'desc_a','quote':'차분하게 앉아 감상합니다.'}]}

def test_valid_exact_quote_and_candidate_reference():
    assert validation(answer(),fixture(),1)==['opaque-a']

@pytest.mark.parametrize('change',[
    lambda a:a['reasons'][0].update(quote='무료로 우주에 갑니다.'),
    lambda a:a['reasons'][0].update(evidence_id='other'),
    lambda a:a['reasons'][0].update(candidate_id='other'),
    lambda a:a['ranking'].append('opaque-a'),
    lambda a:a.update(extra='ignored')])
def test_bad_output_rejected(change):
    a=answer();change(a)
    with pytest.raises(ValueError):validation(a,fixture(),1)

def test_compaction_preserves_values_and_drops_source_timestamps():
    original=fixture();saved=copy.deepcopy(original);p=compact(original)
    assert original==saved
    assert p['candidates'][0]['facts']['travel_min']==5
    assert 'observed_at' not in str(p)

def test_cache_write_replaces_input_price():
    usage={'input_tokens':1000,'output_tokens':100,'input_tokens_details':{'cached_tokens':300,'cache_write_tokens':200}}
    assert price_usage('luna',usage)==pytest.approx((500*.1+300*.01+200*.125+100*.5)/1e6)

def test_invalid_cache_total_rejected():
    with pytest.raises(ValueError):price_usage('nano',{'input_tokens':1,'output_tokens':0,'input_tokens_details':{'cached_tokens':2}})

@pytest.mark.parametrize('method',('choice','score','rank','pick'))
def test_single_candidate_never_needs_provider_or_credentials(method):
    provider=object.__new__(Providers)
    result=getattr(provider,method)(*({'choice':(fixture(),),'score':(fixture(),),'rank':('nano',fixture(),'low'),'pick':('nano',fixture())}[method]))
    assert result['ranking']==['opaque-a'] and result['cost_usd']==0 and result['call_ids']==[]
    assert result['bypassed_single_candidate']
