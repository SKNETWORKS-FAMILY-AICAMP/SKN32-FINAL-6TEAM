import json,sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,'.')
from curate_terms import curate
S=r"C:/Users/PLAYDA~1/AppData/Local/Temp/claude/C--Users-playdata2-Documents-final-workspace-final-project-ui/e4e0010d-d49f-4825-8df6-66d842b6eb6b/scratchpad/terms/"
key=sys.argv[1]; src={'arch':'arch.txt','req':'req.txt','w6':'w6_draft.md','multi':'multi.txt','vec':'vec.txt'}[key]
aud=json.load(open(S+f"audit_{'w6_draft' if key=='w6' else key}.json",encoding='utf-8'))
ov=json.load(open(S+f"override_{key}.json",encoding='utf-8')) if __import__('os').path.exists(S+f"override_{key}.json") else {}
override={int(k):v for k,v in ov.get('override',{}).items()}; drop=set(ov.get('drop',[]))
ok,rej,gl=curate(key, open(S+src,encoding='utf-8').read(), aud, override, drop)
print(key,'ok',len(ok),'rejected',len(rej),'glossary',len(gl))
for r in rej: print('  REJ',r)
