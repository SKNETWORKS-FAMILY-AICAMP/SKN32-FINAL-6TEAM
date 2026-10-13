"""일정 후보의 표시 순서만 바꾼다. 항목 ID·질문·정답·사실은 보존한다."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def transform(row):
    original = row['prompt']
    marker = '\n\n고객 질문:'
    assert original.count(marker) == 1, '질문 경계를 검증하지 못했습니다'
    schedule, question = original.split(marker)
    lines = schedule.splitlines(keepends=True)
    candidates = [i for i, text in enumerate(lines) if re.match(r'^\d+\. ', text)]
    assert len(candidates) >= 2 and candidates == list(range(candidates[0], candidates[-1]+1))
    entries = [lines[i] for i in candidates]
    # 마지막 행 개행 차이로 내용/연결이 달라지는 것을 막는다.
    bodies = [x.rstrip('\r\n') for x in entries]
    ids = [int(x.split('.', 1)[0]) for x in bodies]
    assert sorted(ids) == list(range(1, len(ids)+1)) and len(set(ids)) == len(ids)
    # 앞 대화는 후보가 아니므로 후보 블록 뒤 문자열도 원문 그대로 보존한다.
    trailing = '\n' if entries[-1].endswith('\n') else ''
    revised = ''.join(lines[:candidates[0]]) + '\n'.join(reversed(bodies)) + trailing + ''.join(lines[candidates[-1]+1:]) + marker + question
    assert revised != original
    result = dict(row, prompt=revised)
    assert {k:v for k,v in result.items() if k!='prompt'} == {k:v for k,v in row.items() if k!='prompt'}
    # 같은 질의 안의 '3번' 같은 참조도 ID를 바꾸지 않아 그대로 유효하다.
    assert revised.split(marker)[1] == question
    assert sorted(re.findall(r'^\d+\. .*$', revised.split(marker)[0], re.M)) == sorted(bodies)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('source', type=Path);p.add_argument('output', type=Path);a=p.parse_args()
    rows=json.loads(a.source.read_text(encoding='utf8'));out=[transform(r) for r in rows]
    assert len({r['i'] for r in rows}) == len(rows)
    with a.output.open('x',encoding='utf8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
    audit=dict(rows=len(rows),source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),output_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),transformation='reverse display order, unchanged IDs and question and metadata',independent_holdout=False)
    with a.output.with_suffix('.audit.json').open('x',encoding='utf8') as f:json.dump(audit,f,indent=2)
    print(json.dumps(audit))


if __name__=='__main__':main()
