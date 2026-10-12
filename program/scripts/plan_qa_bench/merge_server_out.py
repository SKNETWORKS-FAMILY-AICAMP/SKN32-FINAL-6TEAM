# 서버에서 받은 llm_<세트>_out.json 의 모델 키만 로컬 파일에 합친다(로컬에만 있는 키는 그대로 둔다).
# 사용: python merge_server_out.py <서버에서 받아 둔 폴더> 모델키...
import json, os, sys
src, keys = sys.argv[1], sys.argv[2:]
for j in ('heavy', 'mix4', 'mix5'):
    f = os.path.join('results', f'llm_{j}_out.json')
    loc = json.load(open(f, encoding='utf-8'))
    srv = json.load(open(os.path.join(src, f'llm_{j}_out.json'), encoding='utf-8'))
    for k in keys:
        if k in srv:
            loc[k] = srv[k]
            print(j, k, '합침')
        else:
            print(j, k, '서버 파일에 없음')
    json.dump(loc, open(f, 'w', encoding='utf-8'), ensure_ascii=False)
