# Codex 가 Claude 가 쓴 분류 자료(CL)를 **정답 라벨을 보지 않고** 따로 라벨링한다 — 교차 확인(작성자 라벨과 어긋나는 칸은 학습·평가에서 뺀다).
#  입력: 메시지(id · message)와 라벨 정의만 준다. 작성자 라벨·note 는 주지 않는다.
# 사용: python codex_label_cls.py <labels_def.md> <입력 jsonl> <출력 jsonl> [--model gpt-6-sol] [--batch 100]
import json, os, re, subprocess, sys, tempfile, time

args = sys.argv[1:]
DEF, INP, OUT = args[0], args[1], args[2]
opt = lambda k, d: args[args.index(k) + 1] if k in args else d
MODEL, BATCH = opt('--model', 'gpt-6-sol'), int(opt('--batch', '100'))
ENUM = {'intent': ['itinerary_submit', 'incident_report', 'confirm_request', 'adjust_reject', 'other'], 'case_type': ['activity', 'dining', 'mobility', 'booking', 'lodging', 'flight', 'other'],
        'sentiment': ['positive', 'neutral', 'negative'], 'severity': ['low', 'medium', 'high', 'critical']}
SCHEMA = {'type': 'object', 'properties': {'labels': {'type': 'array', 'items': {'type': 'object', 'properties': {'id': {'type': 'string'}, **{k: {'type': 'string', 'enum': v} for k, v in ENUM.items()}},
          'required': ['id', *ENUM], 'additionalProperties': False}}}, 'required': ['labels'], 'additionalProperties': False}
WORK = os.path.join(tempfile.gettempdir(), 'codex_label_cls')
os.makedirs(WORK, exist_ok=True)
sp = os.path.join(WORK, 'schema.json')
json.dump(SCHEMA, open(sp, 'w'))
defs = open(DEF, encoding='utf-8').read()
rows = [json.loads(l) for l in open(INP, encoding='utf-8')]
done = {}
if os.path.exists(OUT):
    for l in open(OUT, encoding='utf-8'):
        r = json.loads(l)
        done[r['id']] = r
todo = [r for r in rows if r['id'] not in done]
for i in range(0, len(todo), BATCH):
    chunk = todo[i:i + BATCH]
    body = '\n'.join(json.dumps({'id': r['id'], 'message': r['message']}, ensure_ascii=False) for r in chunk)
    prompt = (defs + '\n\n---\n아래 여행 고객 메시지마다 라벨 넷(intent · case_type · sentiment · severity)을 정의대로 붙여라. 정답을 모르면 가장 알맞다고 보는 하나를 고른다(비워 두지 않는다). '
              '출력은 스키마에 맞는 JSON 객체 하나(labels 배열, 입력과 같은 id 순서)뿐이다. 파일·도구를 쓰지 말고 바로 답한다. 저장소·다른 자료는 읽지 마라.\n\n' + body + '\n')
    pf, rf = os.path.join(WORK, 'p.md'), os.path.join(WORK, 'o.json')
    open(pf, 'w', encoding='utf-8').write(prompt)
    if os.path.exists(rf):
        os.remove(rf)
    cmd = ['codex', 'exec', '--skip-git-repo-check', '-s', 'read-only', '--ephemeral', '-C', WORK, '-m', MODEL, '-c', 'model_reasoning_effort="low"', '--output-schema', sp, '-o', rf, '-']
    t0 = time.time()
    with open(pf, 'rb') as f:
        r = subprocess.run(cmd, stdin=f, capture_output=True, timeout=1500, shell=(os.name == 'nt'))
    log = (r.stdout + b'\n' + r.stderr).decode('utf-8', 'replace')
    if re.search(r'usage limit|hit your .*limit', log, re.I):
        sys.exit('쿼터 창이 막혔다: ' + (re.search(r'try again at[^.\n]*', log, re.I).group(0) if re.search(r'try again at', log, re.I) else '시각 모름'))
    if not (os.path.exists(rf) and os.path.getsize(rf)):
        print('실패', i, log[-300:])
        continue
    labs = json.load(open(rf, encoding='utf-8'))['labels']
    with open(OUT, 'a', encoding='utf-8') as f:
        for l in labs:
            f.write(json.dumps(l, ensure_ascii=False) + '\n')
    print(f'{i + len(chunk)}/{len(todo)} · {time.time() - t0:.0f}초', flush=True)
