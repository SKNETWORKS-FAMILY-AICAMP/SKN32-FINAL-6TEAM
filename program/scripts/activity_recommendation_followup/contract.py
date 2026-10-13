"""Pure-Python development contract, not an LLM or serving implementation."""
from __future__ import annotations

from datetime import datetime
import math


FACT_TYPES={'open':bool,'unsafe':bool,'cost_krw':'number','travel_min':'number',
            'visit_min':'number','step_free':bool,'outdoor':bool}


class InvalidInput(ValueError):
    pass


def _keys(value,allowed,required,label):
    if not isinstance(value,dict):raise InvalidInput(label+': expected object')
    if set(value)-set(allowed):raise InvalidInput(label+': unknown field')
    if set(required)-set(value):raise InvalidInput(label+': missing structural field')


def _text(value,label):
    if not isinstance(value,str) or not value.strip() or value!=value.strip():
        raise InvalidInput(label+': expected nonempty trimmed string')
    return value


def _number(value,label,minimum=0,maximum=None):
    if type(value) not in (int,float):
        raise InvalidInput(label+': expected finite non-bool number')
    try:finite=math.isfinite(value)
    except OverflowError:finite=False
    if not finite:raise InvalidInput(label+': expected finite representable number')
    if value<minimum or (maximum is not None and value>maximum):
        raise InvalidInput(label+': number out of range')
    return float(value)


def _timestamp(value,label):
    if not isinstance(value,str):raise InvalidInput(label+': expected ISO timestamp')
    try:parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    except (ValueError,TypeError):raise InvalidInput(label+': invalid ISO timestamp') from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidInput(label+': timezone required')
    return parsed


def _boolean(value,label):
    if type(value) is not bool:raise InvalidInput(label+': expected bool')
    return value


def score_candidate(weights,values,taste,similarity):
    """Numeric fixture arithmetic only; no natural-language understanding."""
    return weights['taste']*taste+weights['travel']*max(0,1-values['travel_min']/60)+weights['similarity']*similarity


def _reasons(customer,values):
    reasons=[]
    if not values['open']:reasons.append('closed')
    if values['unsafe']:reasons.append('unsafe')
    if values['cost_krw']>customer['budget_krw']:reasons.append('budget')
    if values['travel_min']+values['visit_min']>customer['time_budget_min']:reasons.append('total_time')
    if customer['require_step_free'] and not values['step_free']:reasons.append('step_free')
    if values['outdoor'] and (customer['rain'] or not customer['allow_outdoor']):reasons.append('outdoor_restriction')
    return reasons


def prepare(payload):
    """Return ready/no_feasible_candidates/facts_unresolved/invalid_input.

    A missing fact value, timestamp or evidence reference blocks the whole request.
    A malformed supplied value is invalid input, rather than an unresolved fact.
    """
    base={'requested_count':0,'eligible':[],'ranked_ids':[],'gold_score_groups':[],
          'unresolved_facts':[],'rejected':[],'human_review_count':0,
          'label_origin':'self-authored synthetic numerical fixture; not model performance'}
    try:
        _keys(payload,('customer','weights','candidates','as_of','max_age_seconds'),
              ('customer','weights','candidates','as_of','max_age_seconds'),'request')
        as_of=_timestamp(payload['as_of'],'as_of')
        max_age=_number(payload['max_age_seconds'],'max_age_seconds',minimum=.000001)
        customer=payload['customer']
        _keys(customer,('budget_krw','time_budget_min','require_step_free','rain','allow_outdoor'),
              ('budget_krw','time_budget_min','require_step_free','rain','allow_outdoor'),'customer')
        _number(customer['budget_krw'],'budget_krw');_number(customer['time_budget_min'],'time_budget_min')
        for key in ('require_step_free','rain','allow_outdoor'):_boolean(customer[key],key)
        weights=payload['weights']
        _keys(weights,('taste','travel','similarity'),('taste','travel','similarity'),'weights')
        for key in weights:_number(weights[key],'weight.'+key,maximum=1)
        if not math.isclose(sum(weights.values()),1,abs_tol=1e-9,rel_tol=0):
            raise InvalidInput('weights: sum must be 1')
        candidates=payload['candidates']
        if not isinstance(candidates,list):raise InvalidInput('candidates: expected array')
        seen=set();resolved=[];unresolved=[]
        for candidate in candidates:
            _keys(candidate,('id','description','category','taste','similarity','facts'),
                  ('id','description','category','taste','similarity'),'candidate')
            cid=_text(candidate['id'],'candidate.id')
            if cid in seen:raise InvalidInput('candidate.id: duplicate')
            seen.add(cid)
            _text(candidate['description'],'description');_text(candidate['category'],'category')
            taste=_number(candidate['taste'],'taste',maximum=1)
            similarity=_number(candidate['similarity'],'similarity',maximum=1)
            facts=candidate.get('facts',{})
            _keys(facts,FACT_TYPES,(),'facts')
            values={};evidence_ids={}
            for name,kind in FACT_TYPES.items():
                label=cid+'.'+name
                if name not in facts:
                    unresolved.append({'candidate_id':cid,'fact':name,'reason':'missing_fact'});continue
                fact=facts[name]
                _keys(fact,('value','observed_at','evidence_id'),(),label)
                if 'value' not in fact or fact['value'] is None:
                    unresolved.append({'candidate_id':cid,'fact':name,'reason':'missing_value'});continue
                if kind is bool:_boolean(fact['value'],label+'.value')
                else:_number(fact['value'],label+'.value')
                if not fact.get('observed_at'):
                    unresolved.append({'candidate_id':cid,'fact':name,'reason':'missing_timestamp'});continue
                observed=_timestamp(fact['observed_at'],label+'.observed_at')
                age=(as_of-observed).total_seconds()
                if age<0:
                    unresolved.append({'candidate_id':cid,'fact':name,'reason':'future_timestamp'});continue
                if age>max_age:
                    unresolved.append({'candidate_id':cid,'fact':name,'reason':'stale_fact'});continue
                if not fact.get('evidence_id'):
                    unresolved.append({'candidate_id':cid,'fact':name,'reason':'missing_evidence'});continue
                evidence_ids[name]=_text(fact['evidence_id'],label+'.evidence_id')
                values[name]=fact['value']
            if len(values)==len(FACT_TYPES):
                reasons=_reasons(customer,values)
                if reasons:base['rejected'].append({'candidate_id':cid,'reasons':reasons})
                else:resolved.append({'id':cid,'description':candidate['description'],'category':candidate['category'],
                      'values':values,'evidence_ids':evidence_ids,
                      'score':score_candidate(weights,values,taste,similarity)})
        if unresolved:return {**base,'status':'facts_unresolved','unresolved_facts':unresolved}
        if not resolved:return {**base,'status':'no_feasible_candidates'}
        ranked=sorted(resolved,key=lambda row:(-row['score'],row['id']))
        groups=[]
        for row in ranked:
            if not groups or not math.isclose(groups[-1]['score'],row['score'],abs_tol=1e-12,rel_tol=0):
                groups.append({'score':row['score'],'candidate_ids':[row['id']]})
            else:groups[-1]['candidate_ids'].append(row['id'])
        return {**base,'status':'ready','requested_count':min(3,len(ranked)),'eligible':ranked,
                'ranked_ids':[c['id'] for c in ranked],'gold_score_groups':groups}
    except InvalidInput as error:
        return {**base,'status':'invalid_input','error':str(error)}


def validate_output(prepared,response):
    """Validate IDs/count/references, not the semantic truth of reason text."""
    result={'valid':False,'evidence_references_exist':False,'semantic_factuality_verified':False,
            'human_review_count':0,'ranking_matches_gold':False}
    try:
        if prepared['status']!='ready':raise InvalidInput('request_not_ready')
        _keys(response,('ranking','reasons'),('ranking','reasons'),'response')
        ranking=response['ranking'];reasons=response['reasons']
        if not isinstance(ranking,list) or not isinstance(reasons,list):raise InvalidInput('response arrays required')
        count=prepared['requested_count']
        if len(ranking)!=count or len(reasons)!=count:raise InvalidInput('exact_count_required')
        for cid in ranking:_text(cid,'ranking.id')
        if len(set(ranking))!=count:raise InvalidInput('duplicate_ranked_id')
        candidates={c['id']:c for c in prepared['eligible']}
        if not set(ranking)<=set(candidates):raise InvalidInput('unknown_or_infeasible_id')
        reason_ids=[]
        for reason in reasons:
            _keys(reason,('candidate_id','evidence_ids','text'),('candidate_id','evidence_ids','text'),'reason')
            cid=_text(reason['candidate_id'],'reason.candidate_id');reason_ids.append(cid)
            _text(reason['text'],'reason.text')
            refs=reason['evidence_ids']
            if not isinstance(refs,list) or not refs:raise InvalidInput('nonempty_evidence_array_required')
            for ref in refs:_text(ref,'evidence_id')
            if len(set(refs))!=len(refs):raise InvalidInput('duplicate_evidence_reference')
            if cid not in candidates or not set(refs)<=set(candidates[cid]['evidence_ids'].values()):
                raise InvalidInput('unknown_or_other_candidate_evidence')
        if len(set(reason_ids))!=count or set(reason_ids)!=set(ranking):raise InvalidInput('reasons_must_match_ranked_ids')
        expected=[c['score'] for c in prepared['eligible'][:count]]
        selected=[candidates[cid]['score'] for cid in ranking]
        matches=all(math.isclose(a,b,abs_tol=1e-12,rel_tol=0) for a,b in zip(expected,selected))
        return {**result,'valid':True,'evidence_references_exist':True,'ranking_matches_gold':matches}
    except (InvalidInput,KeyError) as error:
        return {**result,'error':str(error)}
