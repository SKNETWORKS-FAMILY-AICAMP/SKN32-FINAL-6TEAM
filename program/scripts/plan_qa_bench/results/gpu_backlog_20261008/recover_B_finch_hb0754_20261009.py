from pathlib import Path
import subprocess,json,hashlib,sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[5]
base=Path(__file__).parent
detail=json.loads((base/'B_completion_detail_hb0754_20261009.json').read_text(encoding='utf-8'))
out=base/'B_finch_completed_hb0754_20261009';out.mkdir(exist_ok=False)
weights=root/'datasets/travel/train_oos/oos2r_finch_5e5_seed20261012_20261009';weights.mkdir(exist_ok=False)
rows=[]
for file in detail['finch_files']:
    if '/root/adapters/' in file['path'] or file['path'].endswith('.gguf'):
        dest=weights/Path(file['path']).name
    else:dest=out/Path(file['path']).name
    assert not dest.exists()
    subprocess.run(['scp','-q','acopilot-gpu-b:'+file['path'],str(dest)],check=True)
    assert dest.stat().st_size==file['size'] and hashlib.file_digest(dest.open('rb'),'sha256').hexdigest()==file['sha256']
    rows.append(dict(source=file['path'],local=str(dest.relative_to(root)).replace('\\','/'),bytes=file['size'],sha256=file['sha256']))
recipe=json.loads((weights/'recipe_complete.json').read_text(encoding='utf-8'))
assert recipe['status']=='completed' and recipe['optimizer_steps']==654
with (out/'archive_verification.json').open('x',encoding='utf-8') as f:json.dump(dict(files=rows,remote_local_sha_match=[len(rows),len(rows)],recipe=recipe,GGUF_sha256='d96f5ce87bf3df7a0a7f7701389743642d47f02c79f5d7e389a6ae0e8fb062cd'),f,ensure_ascii=False,indent=2)
subprocess.run(['scp','-q',str(weights/'oos2r_finch_5e5_20261008_lora_f16.gguf'),'acopilot-gpu:/tmp/tripilot-trained-adapters-20261008/finch_s20261012_lora_f16.gguf'],check=True)
print(json.dumps(dict(files=len(rows),adapter=str(weights),archive=str(out))))
