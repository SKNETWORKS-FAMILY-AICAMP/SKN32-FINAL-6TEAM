"""Tie-aware synthetic ranking metrics, separate from status-response validation."""
from __future__ import annotations

import math

try:
    from .fixtures import prepare_case
except ImportError:
    from fixtures import prepare_case


def gold_groups(case):
    prepared=prepare_case(case)
    if prepared['status']!='ready':return []
    return [{'score':group['score'],'ids':list(group['candidate_ids'])} for group in prepared['gold_score_groups']]


def expected_ranking(case):
    return [cid for group in gold_groups(case) for cid in sorted(group['ids'])]


def evaluate(case,ranking,expected_count=None):
    prepared=prepare_case(case);status=prepared['status']
    supplied_status=ranking.get('status') if isinstance(ranking,dict) else None
    selected=ranking.get('ranking') if isinstance(ranking,dict) else ranking
    is_array=isinstance(selected,list)
    selected=selected if is_array else []
    choice=expected_count==1
    metric_k=1 if choice else 3
    key_ndcg=f'ndcg{metric_k}';key_recall=f'recall{metric_k}'
    result={'expected_status':status,'status_correct':supplied_status==status,
            'ranking_applicable':status=='ready','metric_k':metric_k,
            'metric_scope':'Choice top-1 only' if choice else 'ranked top-3 with sparse candidate count',
            'selected':selected,'hard_violations':0,'duplicate_count':0,
            'output_count_valid':False,'format_valid':False,'top1_correct':None,
            key_ndcg:None,key_recall:None,'regret_top1':None,
            'human_review_count':0,'semantic_factuality_verified':False}
    if status!='ready':
        result.update(output_count_valid=is_array and not selected,
                      format_valid=is_array and not selected and supplied_status==status)
        return result
    # A list represents a ranking response for a ready request; state cases require
    # an explicit status object so the scorer never invents an unresolved response.
    if not isinstance(ranking,dict):result['status_correct']=True
    requested=prepared['requested_count'] if expected_count is None else expected_count
    if type(requested) is not int or requested<1 or requested>prepared['requested_count']:
        raise ValueError('invalid_expected_count')
    result['requested_count']=requested
    possible=set(prepared['feasible_ids'])
    well_typed=all(isinstance(cid,str) for cid in selected)
    result['hard_violations']=sum(not isinstance(cid,str) or cid not in possible for cid in selected)
    result['duplicate_count']=len(selected)-len(set(selected)) if well_typed else len(selected)
    result['output_count_valid']=is_array and len(selected)==requested
    valid=result['status_correct'] and result['output_count_valid'] and not result['duplicate_count'] and not result['hard_violations']
    result['format_valid']=valid
    groups=gold_groups(case)
    scores={cid:group['score'] for group in groups for cid in group['ids']}
    ideal=[group['score'] for group in groups for _ in group['ids']][:requested]
    result['gold_groups']=groups
    result['gold_top_ids']=expected_ranking(case)[:requested]
    best=ideal[0]
    result['regret_top1']=max(0,best-scores.get(selected[0],0)) if selected and well_typed else best
    if not valid:
        result.update(top1_correct=False,**{key_ndcg:0.0,key_recall:0.0})
        return result
    result['top1_correct']=math.isclose(scores[selected[0]],best,abs_tol=1e-12,rel_tol=0)
    dcg=sum(scores[cid]/math.log2(i+2) for i,cid in enumerate(selected))
    idcg=sum(score/math.log2(i+2) for i,score in enumerate(ideal))
    result[key_ndcg]=dcg/idcg if idcg else 1.0
    remaining=requested;hits=0
    for group in groups:
        quota=min(remaining,len(group['ids']))
        hits+=min(quota,len(set(selected)&set(group['ids'])))
        remaining-=quota
        if not remaining:break
    result[key_recall]=hits/requested
    return result


def validate_citations(case,response):
    """Mechanical quote/source linking; never claims semantic or human review."""
    result={'valid':False,'human_review_count':0,'semantic_factuality_verified':False,
            'quote_mechanical_match':False}
    try:
        if not isinstance(response,dict) or set(response)!= {'ranking','reasons'}:raise ValueError('invalid_response_fields')
        ranking=response['ranking'];reasons=response['reasons']
        if not isinstance(ranking,list) or not isinstance(reasons,list) or len(reasons)!=len(ranking):raise ValueError('invalid_reason_count')
        if not all(isinstance(cid,str) for cid in ranking) or len(set(ranking))!=len(ranking):raise ValueError('invalid_ranking_ids')
        by_id={c['id']:c for c in case['candidates']};reason_ids=[]
        for reason in reasons:
            if not isinstance(reason,dict) or set(reason)!= {'candidate_id','evidence_id','quote'}:raise ValueError('invalid_reason_fields')
            cid=reason['candidate_id'];reason_ids.append(cid)
            if cid not in by_id or reason['evidence_id']!=by_id[cid]['description_evidence_id']:raise ValueError('source_candidate_mismatch')
            quote=reason['quote']
            if not isinstance(quote,str) or not quote.strip() or quote not in by_id[cid]['description']:raise ValueError('quote_not_in_description')
        if len(set(reason_ids))!=len(reason_ids) or set(reason_ids)!=set(ranking):raise ValueError('reason_candidate_mismatch')
        return {**result,'valid':True,'quote_mechanical_match':True}
    except (ValueError,KeyError,TypeError) as error:return {**result,'error':str(error)}
