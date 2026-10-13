"""보존한 네이버 진단 8쌍을 로컬 계산기에 재생한다. 개발자 지도 API 호출 없음.

입력은 원문/조회 시각을 보존한 JSON이다. R01 원본 이름은 N007이지만
실제 신림역→안국역 관측이며 기존 N007과 독립 경로로 합산하지 않는다.
출력은 새 폴더에만 쓴다. 독립 검증이나 실제 탑승 정확도 평가가 아니다.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.domains.travel_ops.instances.mobility.engine.runtime import build_verifier
from app.domains.travel_ops.instances.mobility.engine import options as O
from scripts.mobility.compare_kakao_golden import _planner_leg
from scripts.mobility.summarise_fresh_web_experiment import paired


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input-dir',type=Path,required=True)
    parser.add_argument('--out-dir',type=Path,required=True)
    args=parser.parse_args()
    args.out_dir.mkdir(parents=True,exist_ok=True)
    output=args.out_dir/'ours.json'
    if output.exists() or (args.out_dir/'summary.json').exists():
        parser.error('기존 결과가 있다. 새 출력 폴더를 지정한다.')
    rt=build_verifier(quiet=True,local_router=True,gh_url='',seoul_key='')
    tz=timezone(timedelta(hours=9))
    def read(p):return json.loads(p.read_text(encoding='utf8'))
    one=read(args.input_dir/'naver-N007-1227.json')
    one.update(id='R01',a='신림역 2호선',b='안국역 3호선')
    items=[one]+[read(args.input_dir/f'naver-R{i:02d}.json') for i in range(2,9)]

    def station(name):
        nm,line=name.rsplit(' ',1)
        candidates=[r for r in rt._v.sc.by_key.values()
                    if O.station_name(r['station_nm'])==O.station_name(nm) and O.line_name(r['line'])==line]
        if not candidates:raise ValueError(name)
        r=candidates[0]
        return {'key':name,'name':nm,'lat':r['lat'],'lon':r['lng']}

    def run(r):
        text=r['text']
        if any(n.split(' ')[0] not in text for n in (r['a'],r['b'])):
            raise ValueError('원문 경로와 입력 이름이 다름')
        m=re.search(r'(?:(\d+)시간)?(\d+)분\n(오전|오후)\s*(\d+):(\d+) 도착\n([\d,]+)원',text)
        if not m:raise ValueError(r['id'])
        h=int(m[4])%12+(12 if m[3]=='오후' else 0)
        target=datetime(2026,10,8,h,int(m[5]),tzinfo=tz)
        obj,why=_planner_leg(rt,['subway','bus'])(station(r['a']),station(r['b']),target)
        row={'id':r['id'],'a':r['a'],'b':r['b'],'read_at':r['read_at'],
             'web_selected_departure':'2026-10-08T12:15:00+09:00',
             'web_min':int(m[1] or 0)*60+int(m[2]),'web_fare':int(m[6].replace(',','')),
             'our_arrival_target':target.isoformat(),'source_sha256':hashlib.sha256(text.encode()).hexdigest(),
             'ours':obj,'failure':why}
        if obj:
            o=next(o for o in obj['route']['options'] if o['id']==obj['route']['planned'])
            trace=next(t for t in obj['comparison']['options'] if t['id']==o['id'])
            row.update(our_min=o['eta_min'],our_wait=trace['wait_min'],our_fare=o.get('fare_krw'),our_label=o['label'])
        return row

    rows=[]
    with (args.out_dir/'ours.jsonl').open('x',encoding='utf8') as stream,ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed(pool.submit(run,r) for r in items):
            row=future.result();rows.append(row)
            stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
    with output.open('x',encoding='utf8') as stream:json.dump(rows,stream,ensure_ascii=False,indent=2)
    valid=[r for r in rows if r.get('our_min') is not None and r.get('our_wait') is not None]
    result={'n':len(rows),'comparable':len(valid),'purpose':'기존 진단8쌍 재생. 수정 후 독립 검증 아님',
            'time_with_wait':paired([r['our_min'] for r in valid],[r['web_min'] for r in valid]),
            'time_without_wait':paired([r['our_min']-r['our_wait'] for r in valid],[r['web_min'] for r in valid]),
            'fare_present':sum(r.get('our_fare') is not None for r in valid),
            'fare_equal':sum(r.get('our_fare')==r['web_fare'] for r in valid),
            'public_rows':[{k:r.get(k) for k in ('id','a','b','read_at','web_min','web_fare','our_min','our_wait','our_fare','our_label')} for r in rows]}
    with (args.out_dir/'summary.json').open('x',encoding='utf8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='public_rows'},ensure_ascii=False))


if __name__=='__main__':main()
