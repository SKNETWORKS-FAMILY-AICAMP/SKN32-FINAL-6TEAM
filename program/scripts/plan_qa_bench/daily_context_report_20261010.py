"""일일 재검토 실험의 저장 답안을 재계수한다. 실패·누락은 분모에 남긴다."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def wilson(hit, total):
    if not total:
        return None
    z = 1.959963984540054
    p = hit/total
    center = (p+z*z/(2*total))/(1+z*z/total)
    half = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total)
    return [center-half, center+half]


def summarize(folder):
    source = json.loads((folder/'source_prompts.json').read_text(encoding='utf8'))
    files = list(folder.glob('*.jsonl'))
    assert len(files) == 1
    rows = [json.loads(line) for line in files[0].read_text(encoding='utf8').splitlines()]
    assert len({r['i'] for r in source}) == len(source)
    assert len({r['i'] for r in rows}) == len(rows)
    answers = {r['i']: r for r in rows}
    assert set(answers) <= {r['i'] for r in source}
    for x in source:
        if x['i'] in answers:
            assert x['gold'] == answers[x['i']]['gold']
    result = dict(saved=len(rows), expected=len(source), missing=len(source)-len(rows),
        errors=sum(bool(r.get('error')) for r in rows), unparsed=sum(not r.get('parsed') for r in rows),
        answers_sha256=hashlib.sha256(files[0].read_bytes()).hexdigest(),
        input_sha256=hashlib.sha256((folder/'source_prompts.json').read_bytes()).hexdigest())
    if source[0].get('gold_set') is not None:
        result['groups'] = {}
        for name, group in [('B_single_or_none',[x for x in source if len(x['gold_set'])!=2]),
                            ('C_two_items',[x for x in source if len(x['gold_set'])==2])]:
            correct=sum(bool(answers.get(x['i'],{}).get('parsed')) and
                        set(answers[x['i']]['pick'])==set(x['gold_set']) for x in group)
            result['groups'][name]=dict(correct=correct,total=len(group),rate=correct/len(group),wilson95=wilson(correct,len(group)))
        return result
    groups = {'all':source}
    if 'kind' in source[0]:
        groups.update({k:[x for x in source if x['kind']==k] for k in ['mixed','control']})
        groups.update({cat:[x for x in source if x['kind']=='mixed' and x['cat']==cat] for cat in sorted({x['cat'] for x in source})})
    result['groups'] = {}
    for name, group in groups.items():
        pos=[x for x in group if x['gold'] is not None];neg=[x for x in group if x['gold'] is None]
        def valid(x):return bool(answers.get(x['i'],{}).get('parsed'))
        hit=sum(valid(x) and answers[x['i']]['pick']==x['gold'] for x in pos)
        fp=sum(valid(x) and answers[x['i']]['pick'] is not None for x in neg)
        bad=sum(not valid(x) for x in neg)
        correct=sum(valid(x) and answers[x['i']]['pick']==x['gold'] for x in group)
        result['groups'][name]=dict(correct=correct,total=len(group),normal_correct=hit,normal_total=len(pos),
            false_picks=fp,no_request_total=len(neg),no_request_invalid_or_missing=bad,
            normal_wilson95=wilson(hit,len(pos)),false_pick_wilson95=wilson(fp,len(neg)),
            conservative_false_or_invalid=fp+bad)
    if 'mixed' in groups:
        m=result['groups']['mixed'];c=result['groups']['control']
        loss=100*(c['normal_correct']/c['normal_total']-m['normal_correct']/m['normal_total'])
        inc=100*(m['false_picks']/m['no_request_total']-c['false_picks']/c['no_request_total'])
        clean=result['missing']==result['errors']==result['unparsed']==0
        gates=[m['normal_correct']/m['normal_total']>=.95,m['false_picks']/m['no_request_total']<=.01,loss<=2,inc<=1]
        result.update(selection_loss_pp=loss,false_pick_increase_pp=inc,gates_passed=sum(gates),gates_total=4,
                      complete_without_errors=clean,gate_admissible=clean,
                      subtype_limits_passed=all(result['groups'][cat]['conservative_false_or_invalid']/result['groups'][cat]['no_request_total']<=.03 for cat in ['MX3','MX4','MX5a']))
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-root',required=True,type=Path);args=parser.parse_args()
    result={}
    for archive in ['A_archive','B_archive','A_context_archive','A_context_archive_v2']:
        root=args.evidence_root/archive
        if not root.exists():continue
        for folder in root.iterdir():
            if folder.is_dir() and (folder/'source_prompts.json').is_file():result[folder.name]=summarize(folder)
    output=args.evidence_root/'daily_recount_v2.json'
    with output.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    for job, s in result.items():
        if job.startswith('sac_') or job.endswith('_multi_items_bc_a1') or job in ['original_mx','cosine_s20261014_d3','finch_s20261014_d3']:
            print(job,json.dumps({k:v for k,v in s.items() if k not in ['answers_sha256','input_sha256']},ensure_ascii=False))


if __name__=='__main__':main()
