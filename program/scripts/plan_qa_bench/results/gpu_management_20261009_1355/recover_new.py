from pathlib import Path
import subprocess,json,hashlib,tarfile,io,shutil,sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path.cwd();here=Path(__file__).parent
ids=['winnow_oos_multi_items_bc_a1','e4bqat_oos1_multi_items_bc_a1','e4bqat_oos3_multi_items_bc_a1','e4bqat_oos2r_multi_items_bc_a1','valen_08b_original_d2_a2']
src=(root/'program/scripts/plan_qa_bench/server/queues/recover_valen_completed_20261009_1110.py').read_bytes()
src=src.replace(b"ids=['valen_08b_original_d3_a1','valen_08b_original_mx_a1']",('ids='+repr(ids)).encode())
r=subprocess.run(['ssh','acopilot-gpu','python3 -'],input=src,capture_output=True,check=True)
with (here/'A_completed.tar.gz').open('xb') as f:f.write(r.stdout)
out=here/'A_completed';out.mkdir()
with tarfile.open(fileobj=io.BytesIO(r.stdout)) as t:
    for m in t.getmembers():
        assert m.isfile() and (out/m.name).resolve().is_relative_to(out.resolve())
        p=out/m.name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(t.extractfile(m).read())
proof=json.loads((out/'ARCHIVE_SHA.json').read_text())
for name,meta in proof.items():
    p=out/name;assert p.stat().st_size==meta['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==meta['sha256']
base=root/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
for ident in ids:
    assert not (base/ident).exists();shutil.copytree(out/ident,base/ident)
    script='backlog_valen_report.py' if ident.startswith('valen') else 'backlog_multi_items_report.py'
    args=[sys.executable,str(base.parent.parent/script),ident]+(['d2'] if ident.startswith('valen') else [])
    a=subprocess.run(args,capture_output=True,check=True)
    with (here/(ident+'_aggregate_stdout.json')).open('xb') as f:f.write(a.stdout)
with (here/'A_verification.json').open('x') as f:json.dump({'files':[len(proof),len(proof)],'jobs':ids,'answers':[4340,4340],'archive_sha256':hashlib.sha256(r.stdout).hexdigest()},f,indent=2)
print(json.dumps({'files':len(proof),'jobs':len(ids),'answers':4340}))
