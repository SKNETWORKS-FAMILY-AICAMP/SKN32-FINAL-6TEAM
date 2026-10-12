# Codex 모델(루나·솔)이 「질문이 가리키는 일정 항목」을 고르게 하고 Gemma 계열과 같은 90문항으로 비교한다.
#  - 세트마다 한 번 호출: 일정 목록 + 번호 붙인 질문 전부 → [{qi, item|null}] (정답은 넣지 않는다).
#    Gemma 는 질문 하나씩 풀었으므로 「한 번에 묶어 풀기」라는 조건 차이가 있다(유리한 쪽은 Codex).
#  - 시험 문제를 Codex(다른 세션)가 썼다는 점: 같은 계열 모델이 풀면 유리할 수 있다 `[주의]`.
# 사용: python codex_point.py <모델> <작업폴더> [job|heavy]   → <작업폴더>/codex_<모델>[_heavy].json , results/ 로 복사는 따로
#  heavy 는 문제마다 앞 대화(history)가 다르므로 문제 앞에 「[앞 대화 …]」를 붙여 한 번에 묶어 푼다.
import json, os, shutil, subprocess, sys, time
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
model, work = sys.argv[1], sys.argv[2]
jobname = sys.argv[3] if len(sys.argv) > 3 else 'job'
PROTO = os.environ.get('PROTO') == '1'
RULE = '한 문장에 항목이 여럿 나오면 가장 먼저 언급된 항목 하나만 고른다. 「그거·거기·방금 바꾼 것」 같은 말은 앞 대화에서 가리키는 항목으로 푼다. 앞 대화가 없어 대상을 알 수 없으면 null 이다.'
suf = ('' if jobname == 'job' else '_' + jobname) + ('_proto' if PROTO else '')
os.makedirs(work, exist_ok=True)
job = json.load(open(os.path.join(HERE, 'fixtures', jobname + '.json'), encoding='utf-8'))['sets']
W = '월화수목금토일'
schema = {'type': 'object', 'additionalProperties': False, 'required': ['answers'], 'properties': {'answers': {
    'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['qi', 'item'],
                               'properties': {'qi': {'type': 'integer'}, 'item': {'type': ['integer', 'null']}}}}}}
sp = os.path.join(work, 'schema.json')
json.dump(schema, open(sp, 'w'))
out = {}
for s, st in job.items():
    items = sorted(st['items'], key=lambda i: (i['date'], i['start']))
    lines = []
    for i in items:
        d = date.fromisoformat(i['date'])
        lines.append(f"- id {i['id']}: {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}")
    def fq(k, x):
        h = ''
        if x.get('history'):
            h = '[앞 대화: ' + ' / '.join(f"{'고객' if t['role'] == 'customer' else '서비스'}: {t['text']}" for t in x['history']) + '] '
        return f"{k}. {h}{x['q']}"

    qs = '\n'.join(fq(k, x) for k, x in enumerate(st['qs']))
    prompt = (f"여행 서비스 고객이 채팅으로 보낸 문장이 아래 일정의 어느 항목을 가리키는지 고른다. 오늘은 {st['today']} 이다.\n"
              f"각 문장마다 가리키는 항목의 id 하나를 고르고, 일정에 그런 항목이 없거나 판단할 수 없으면 null 로 답한다.\n"
              f"값(시각·장소)을 만들어 내지 말고 id 만 낸다. " + (RULE + ' ' if PROTO else '') + f"파일을 만들거나 고치지 말고 명령도 실행하지 마라.\n\n"
              f"일정:\n" + '\n'.join(lines) + f"\n\n문장(qi. 문장):\n{qs}\n\n"
              f"문장 {len(st['qs'])}개 모두에 대해 {{\"answers\":[{{\"qi\":0,\"item\":id 또는 null}}, ...]}} 형식으로만 답하라.")
    pf = os.path.join(work, f'{s}{suf}_prompt.md')
    open(pf, 'w', encoding='utf-8').write(prompt)
    of = os.path.join(work, f'{s}{suf}_{model}.json')
    t = time.time()
    with open(pf, 'rb') as fin, open(os.path.join(work, f'{s}{suf}_{model}.log'), 'wb') as log:
        rc = subprocess.run([shutil.which('codex'), 'exec', '--skip-git-repo-check', '-s', 'read-only', '--ephemeral',
                             '-C', work, '--output-schema', sp, '-o', of, '-m', model, '-'], stdin=fin, stdout=log, stderr=log).returncode
    ok = os.path.exists(of) and os.path.getsize(of) > 0
    print(s, model, 'rc', rc, 'ok' if ok else 'FAIL', f'{time.time() - t:.0f}s', flush=True)
    if ok:
        a = json.load(open(of, encoding='utf-8'))['answers']
        out[s] = {str(r['qi']): r['item'] for r in a}
    out['_sec_' + s] = time.time() - t
json.dump(out, open(os.path.join(work, f'codex_{model.replace("/", "-")}{suf}.json'), 'w', encoding='utf-8'))
print('done', model)
