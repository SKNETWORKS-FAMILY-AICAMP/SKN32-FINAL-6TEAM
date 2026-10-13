"""Read public official release metadata only. No credentials or private project data sent."""
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import urllib.request

OUT = Path('program/scripts/plan_qa_bench/results/release_watch_20261009_v1')
REPOS = ['Valen-Team/Valen-0.8B','Valen-Team/Valen-2B','Valen-Team/Valen-4B','CohereLabs/North-Micro-Vision-Instruct','Aleph-Alpha/Kolibri-1']


def read(url):
    req = urllib.request.Request(url,headers={'User-Agent':'triPilot-public-release-review'})
    return urllib.request.urlopen(req,timeout=40).read()


def collect(repo):
    target = OUT/repo.replace('/','__'); target.mkdir(parents=True)
    meta = json.loads(read('https://huggingface.co/api/models/'+repo+'?blobs=true'))
    (target/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    revision = meta['sha']; files = [r['rfilename'] for r in meta['siblings']]
    selected = [f for f in files if f in ('README.md','config.json','LICENSE','LICENSE.txt','LICENSE.md','NOTICE','NOTICE.md','pyproject.toml') or f.endswith('.py')]
    downloaded = []
    for filename in selected:
        body = read('https://huggingface.co/'+repo+'/resolve/'+revision+'/'+filename)
        file = target/filename; file.parent.mkdir(parents=True,exist_ok=True); file.write_bytes(body)
        downloaded.append({'name':filename,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
    weights = [{'name':f['rfilename'],'bytes':f.get('size'),'lfs':f.get('lfs')} for f in meta['siblings'] if f['rfilename'].endswith(('.safetensors','.bin','.gguf'))]
    return {'repo_id':repo,'revision':revision,'last_modified_utc':meta['lastModified'],'created_at_utc':meta.get('createdAt'),'parameters':meta.get('safetensors'),'card_data':meta.get('cardData'),'weights':weights,'weight_bytes':sum(f['bytes'] or 0 for f in weights),'metadata_files':downloaded,'weights_downloaded':False,'path':target.as_posix()}


if __name__=='__main__':
    if OUT.exists():
        raise FileExistsError(OUT)
    OUT.mkdir(parents=True)
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(collect,repo):repo for repo in REPOS}
        for future in concurrent.futures.as_completed(futures):
            try:
                row = future.result()
            except Exception as error:
                row = {'repo_id':futures[future],'failed':True,'error':str(error)}
            rows.append(row)
    result = {'observed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Public official metadata/config/license/code; no weights or authentication','repositories':rows}
    (OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:r.get(k) for k in ('repo_id','revision','last_modified_utc','parameters','weight_bytes','failed','error')} for r in rows],ensure_ascii=False,indent=2))
