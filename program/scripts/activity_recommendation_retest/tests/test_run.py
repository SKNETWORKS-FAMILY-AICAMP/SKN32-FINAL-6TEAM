import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run import DATA,CONFIG,rows,root_metrics
from fixtures import prepare_case
from metrics import evaluate,expected_ranking

CASES=rows(DATA/CONFIG['raw_subdirectory']/'dev.jsonl')+rows(DATA/CONFIG['raw_subdirectory']/'eval.jsonl')

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['case_id'])
def test_independent_scoring_matches_for_correct_and_reversed_outputs(case):
    prepared=prepare_case(case);state=prepared['status']
    if state!='ready':
        assert root_metrics(case,{'decision_status':state,'ranking':[]})['valid']==evaluate(case,{'status':state,'ranking':[]})['format_valid']
        return
    ranked=expected_ranking(case)
    for choice in (False,True):
        k=1 if choice else min(3,len(ranked))
        for selected in (ranked[:k],list(reversed(ranked))[:k]):
            actual=root_metrics(case,{'status':'ok','ranking':selected},choice)
            reference=evaluate(case,selected,expected_count=1 if choice else None)
            assert actual['top1']==reference['top1_correct']
            assert actual['ndcg']==pytest.approx(reference['ndcg1' if choice else 'ndcg3'])
            assert actual['recall']==pytest.approx(reference['recall1' if choice else 'recall3'])

def test_boundary_tie_does_not_replace_mandatory_higher_candidate():
    case=next(c for c in CASES if c['case_id']=='dev_a479dd320376d642cbffe82c')
    groups=prepare_case(case)['gold_score_groups']
    selected=groups[2]['candidate_ids'][:2]+groups[1]['candidate_ids'][:1]
    assert len(selected)==3
    assert root_metrics(case,{'status':'ok','ranking':selected})['recall']==pytest.approx(2/3)
