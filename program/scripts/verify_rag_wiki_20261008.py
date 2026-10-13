"""문서 보완 범위 검사와 기존 wiki 검사기의 수정 전후 비교. 파일 삭제 없음."""
from pathlib import Path
import json, re, importlib.util, contextlib, io, sys, builtins, shutil
from datetime import datetime
ROOT = Path(__file__).resolve().parents[2]
changes = json.loads((ROOT/'program/scripts/rag_wiki_changes_20261008.json').read_text(encoding='utf-8'))
out = ROOT/'program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008'
out.mkdir(parents=True, exist_ok=True)
spec=importlib.util.spec_from_file_location('wiki_check',ROOT/'program/scripts/check_wiki.py')
checker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
oldmap={}
for b in changes['backups']:
    parts=Path(b).parts
    idx=parts.index('_backup')
    oldmap[str((ROOT/Path(*parts[:idx])/parts[-1]).resolve())]=ROOT/b
new={str((ROOT/r).resolve()) for r in changes['changed']} - set(oldmap)
origglob=checker.glob.glob
origopen=builtins.open

def measure(before):
    captured={}
    def glob(pattern,*a,**kw):
        vals=origglob(pattern,*a,**kw)
        if pattern.endswith('*.md'):
            vals=[v for v in vals if not ('/_backup/' in v.replace('\\','/') and 'rag_wiki' in v)]
            if before:
                vals=[v for v in vals if str(Path(v).resolve()) not in new]
        return vals
    def opened(file,*a,**kw):
        try: k=str(Path(file).resolve())
        except TypeError: k=''
        if before and k in oldmap:
            file=oldmap[k]
        return origopen(file,*a,**kw)
    def trace(frame,event,arg):
        if frame.f_code is checker.main.__code__ and event=='return':
            captured.update({k:list(v) for k,v in frame.f_locals['problems'].items()})
        return trace
    stream=io.StringIO()
    checker.glob.glob=glob
    builtins.open=opened
    sys.settrace(trace)
    try:
        with contextlib.redirect_stdout(stream): code=checker.main()
    finally:
        sys.settrace(None)
        checker.glob.glob=origglob
        builtins.open=origopen
    (out/('before.txt' if before else 'after.txt')).write_text(stream.getvalue(),encoding='utf-8')
    return {'exit_code':code,'violations':sum(map(len,captured.values())),'problems':captured}

before=measure(True)
after=measure(False)
def identity(message):
    # 같은 장문 지적은 줄 수가 달라져도 새 위반으로 세지 않는다.
    return re.sub(r'  \(\d+줄\)$','',message)
added={k:sorted(vv for vv in v if identity(vv) not in {identity(x) for x in before['problems'].get(k,[])}) for k,v in after['problems'].items()}
added={k:v for k,v in added.items() if v}
files=changes['changed']
links=[]
broken=[]
for rel in files:
    text=(ROOT/rel).read_text(encoding='utf-8')
    text=re.sub(r'```.*?```','',text,flags=re.S)
    for dest in re.findall(r'(?<!!)\[[^\]]*\]\(([^\n)]+)\)',text):
        dest=dest.strip('<>').split('#')[0]
        if not dest or re.match(r'[a-z]+://',dest): continue
        # 최근 문서의 로컬 파일 연결만 검사한다.
        target=Path(dest[1:]) if dest.startswith('/C:') else ROOT/Path(rel).parent/dest
        links.append({'source':rel,'target':dest,'exists':target.exists()})
        if not target.exists(): broken.append(links[-1])
pages=['wiki/research/rag-slm-improvements.md','final_project_cs/wiki/quality/slm-model-evaluation.md','final_project_cs/wiki/operations/gpu-work-queue.md']
registered=sum(Path(p).name in (ROOT/Path(p).parent/'index.md').read_text(encoding='utf-8') for p in pages)
result={'scope':'13 changed documents; full checker compares virtual prior contents and excludes only this audit backup copies',
        'changed_documents':len(files),'local_links_checked':len(links),'broken_links':broken,
        'registered_pages':registered,'registration_total':len(pages),
        'preserved_backups':sum((ROOT/b).exists() for b in changes['backups']),'backup_total':len(changes['backups']),
        'global_before':before['violations'],'global_after':after['violations'],'new_checker_problems':added}
(out/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
