# Codex 가 여행 고객 채팅 분류 자료를 쓴다 — Claude 가 쓴 묶음(CL)과 출제자를 다르게 하려는 것(출제자 편향 분리, §84).
#  지침은 같은 spec.md(라벨 정의·말투 지침). 묶음마다 주제를 달리해 `codex exec` 를 한 번씩 부른다(읽기 전용 · 빈 임시 폴더 · 세션 저장 안 함).
#  결과: cls/cx_<번호>.jsonl (한 줄에 메시지 하나). 이 파일들은 평가(시험) 쪽 자료다 — 학습에는 쓰지 않는다.
# 사용: python codex_author_cls.py <spec.md 경로> <출력 폴더> [--model gpt-6-sol] [--per 80]
import json, os, re, subprocess, sys, tempfile, time

args = sys.argv[1:]
SPEC, OUT = args[0], args[1]
opt = lambda k, d: args[args.index(k) + 1] if k in args else d
MODEL, PER = opt('--model', 'gpt-6-sol'), int(opt('--per', '80'))
THEMES = [
    ('1', '식당·카페(dining)와 이동(mobility) 중심 — dining 35% · mobility 35% · 나머지 30%. 의도는 confirm_request 30 · incident_report 25 · adjust_reject 25 · itinerary_submit 8 · other 12 (%) 안팎.'),
    ('2', '활동(관광·체험·공연·쇼핑·날씨 영향) 중심 — activity 60% · 나머지 40%. 의도는 confirm_request 30 · incident_report 25 · adjust_reject 25 · itinerary_submit 8 · other 12 (%) 안팎.'),
    ('3', '예약·결제·숙소·항공 중심 — booking 35% · lodging 12% · flight 13% · 나머지 40%. 의도는 confirm_request 30 · incident_report 20 · adjust_reject 30 · itinerary_submit 8 · other 12 (%) 안팎. 예약 취소·변경·되돌리기·환불 말투를 다양하게.'),
    ('4', '일정 제출·전체 일정·잡담·감사·서비스 범위 밖 요청·외국어 — itinerary_submit 20 · other 30 · confirm_request 20 · adjust_reject 15 · incident_report 15 (%). 언어는 한국어 55% · 영어 20% · 일본어 15% · 중국어 번체 10% (locale ko/en/ja/zh-TW).'),
    ('5', '긴급·감정이 센 말 — 긴급도 high 35% · critical 10% · medium 30% · low 25%, 감정 negative 50% · positive 20% · neutral 30%. 감정과 긴급도가 어긋나는 사례를 30% 넣는다. 의도는 incident_report 35 · confirm_request 25 · adjust_reject 25 · other 10 · itinerary_submit 5 (%).'),
]
ENUM = {'intent': ['itinerary_submit', 'incident_report', 'confirm_request', 'adjust_reject', 'other'], 'case_type': ['activity', 'dining', 'mobility', 'booking', 'lodging', 'flight', 'other'],
        'sentiment': ['positive', 'neutral', 'negative'], 'severity': ['low', 'medium', 'high', 'critical'], 'locale': ['ko', 'en', 'ja', 'zh-TW']}
SCHEMA = {'type': 'object', 'properties': {'messages': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'id': {'type': 'string'}, 'message': {'type': 'string'}, **{k: {'type': 'string', 'enum': v} for k, v in ENUM.items()}, 'note': {'type': 'string'}},
    'required': ['id', 'message', 'locale', 'intent', 'case_type', 'sentiment', 'severity', 'note'], 'additionalProperties': False}}}, 'required': ['messages'], 'additionalProperties': False}
WORK = os.path.join(tempfile.gettempdir(), 'codex_author_cls')
os.makedirs(WORK, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
sp = os.path.join(WORK, 'schema.json')
json.dump(SCHEMA, open(sp, 'w'))
spec = open(SPEC, encoding='utf-8').read()
for num, theme in THEMES:
    of = os.path.join(OUT, f'cx_{num}.jsonl')
    if os.path.exists(of) and sum(1 for _ in open(of, encoding='utf-8')) >= PER * 0.9:
        print('이미 있음', of)
        continue
    prompt = (spec + f'\n\n---\n이번 묶음: 메시지 **{PER}개**. 주제: {theme}\nid 접두는 CX{num} (CX{num}-001 …). 출력은 스키마에 맞는 JSON 객체 하나(messages 배열)뿐이다. 파일·도구를 쓰지 말고 바로 답한다. '
              '저장소·다른 자료는 읽지 마라(평가 자료와 겹치면 안 된다).\n')
    pf, rf = os.path.join(WORK, f'cx{num}.prompt.md'), os.path.join(WORK, f'cx{num}.out.json')
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
        print('실패', num, log[-300:])
        continue
    msgs = json.load(open(rf, encoding='utf-8'))['messages']
    with open(of, 'w', encoding='utf-8') as f:
        for m in msgs:
            f.write(json.dumps(m, ensure_ascii=False) + '\n')
    print(f'cx_{num}: {len(msgs)}개 · {time.time() - t0:.0f}초', flush=True)
