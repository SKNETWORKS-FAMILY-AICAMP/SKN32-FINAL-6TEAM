"""최소 CLI 재생으로 줄인 자료 재생성 시 9호선 일반/급행이 보존되는지 확인한다."""
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from app.domains.travel_ops.instances.mobility.engine.congestion import Congestion

ROOT = Path(__file__).resolve().parents[5]
SCRIPT = ROOT/'datasets/mobility/scripts/reduce_75.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cli_world(tmp_path, flags=(), occupied=False):
    src, dst = tmp_path/'source', tmp_path/'destination'
    src.mkdir()
    dst.mkdir()
    rows = [dict(line='09호선', station_nm='여의도', dir='up', day_type='weekday',
                 slot='08:00', congestion=value, service=service, source_id='controlled-public-shape')
            for service, value in [('local', 20.0), ('express', 120.0)]]
    (src/'congestion_line9_v1.jsonl').write_text(
        ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf8')
    (src/'timetable_v1.jsonl').write_text(json.dumps(dict(line='09호선', station_nm='여의도',
        day_type='weekday', dep_time='080000', dir='up', dest_nm='개화', fetched_at='controlled'))+'\n',encoding='utf8')
    before = {p.name:sha(p) for p in src.iterdir()}
    if occupied:
        (dst/'preserve.txt').write_text('keep existing output',encoding='utf8')
    # -S: 표준 라이브러리만 사용하여 .env 읽기 선택 라이브러리를 불러오지 않는다.
    result = subprocess.run([sys.executable, '-S', str(SCRIPT), '--src', str(src), '--dst', str(dst),
                             *flags],capture_output=True,text=True,encoding='utf8',timeout=15)
    assert {p.name:sha(p) for p in src.iterdir()} == before
    return src,dst,result


@pytest.mark.parametrize('flags,rows,dropped', [((),2,False), (('--keep-express',),2,False),
                                               (('--drop-express',),1,True)])
def test_cli_default_and_compatibility_flags_match_manifest(tmp_path, flags, rows, dropped):
    src,dst,result = cli_world(tmp_path,flags)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((dst/'MANIFEST_git_v1.json').read_text(encoding='utf8'))
    entry = next(e for e in manifest['files'] if e['path']=='congestion_line9_v1.jsonl')
    assert manifest['rule']['row_deletion']['drop_express'] is dropped
    assert entry['rows'] == rows
    assert entry['reduce'] == dict(rows_in=2,rows_out=rows,rows_express=1,rows_dropped_express=int(dropped))
    assert entry['src_sha256'] == sha(src/'congestion_line9_v1.jsonl')
    assert entry['sha256'] == sha(dst/'congestion_line9_v1.jsonl')
    output = [json.loads(s) for s in (dst/'congestion_line9_v1.jsonl').read_text(encoding='utf8').splitlines()]
    assert {r['service'] for r in output} == ({'local'} if dropped else {'local','express'})


def test_default_cli_output_remains_distinct_in_the_product_congestion_loader(tmp_path):
    _src,dst,result = cli_world(tmp_path)
    assert result.returncode == 0
    cg = Congestion.load([dst/'congestion_line9_v1.jsonl'])
    assert cg is not None and cg.rows == 2
    levels = {'여유':{'lt':30},'매우혼잡':{'gte':100,'lt':130}}
    args = ('09호선','여의도','up','weekday',date(2026,10,12),480,levels)
    local,express = cg.lookup(*args,service='local'),cg.lookup(*args,service='express')
    assert local[:2] == (20.0,'여유') and local[2]['service']=='local'
    assert express[:2] == (120.0,'매우혼잡') and express[2]['service']=='express'
    assert cg.lookup(*args) is None, '운행 구분을 모르면 일반/급행 중 하나로 꾸미지 않는다'


def test_cli_refuses_an_occupied_destination_without_replacing_existing_output(tmp_path):
    _src,dst,result = cli_world(tmp_path,occupied=True)
    assert result.returncode == 2
    assert (dst/'preserve.txt').read_text(encoding='utf8') == 'keep existing output'
    assert list(p.name for p in dst.iterdir()) == ['preserve.txt']
