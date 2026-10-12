# 「실전처럼 섞은 시험 세트」 만들기 — 사용자 지시(2026-10-06): 「관광지 질문 데이터를 우리 데이터셋에 있는 관광지·장소로 바꾼 합성 데이터셋을 만들어 다른 자료와 같이 섞어 시험 세트를 만들어라」.
#  재료(전부 git 밖 datasets/ 에 있다 — AI Hub 는 재배포 제한, 관광지 질문 모음은 라이선스 표기 없음 → 만든 결과도 datasets/travel/mixed_testset/ 에 두고 이 스크립트와 통계만 커밋한다):
#   ① 관광지 질문 모음(서울·경기 관광지 QA, 질문 2,543) — 질문 틀만 쓴다. 질문 속 장소 이름을 우리 DB 장소 목록(place_catalog 8,370곳) 이름과 글자가 가장 길게 겹치는 것으로 찾아 「{P}」 로 바꿔 틀을 만든다.
#   ② 우리 시험 세트 mix8~mix12 의 일정(항목 · 장소) — 일정 안 장소로 틀을 채우면 정답 항목이 정해진다(합성 · 정답 = 그 항목). 일정 밖 장소(place_catalog 에서 일정과 이름이 겹치지 않는 곳)로 채우면 정답은 「없음」.
#   ③ 일상 대화(AI Hub 주제별 일상 대화 · 카카오톡 구어체) · 신조어 구어체 대화(KoCulture) — 일정과 무관한 말(정답 = 없음, 규정 답으로 오인하면 오답).
#   ④ 우리 기존 시험 질문(Codex·Claude 가 쓴 합성 질문) mix8~12 835문제 그대로.
#  일정마다(mixed8~12) 위 질문들을 무작위로(seed 고정) 섞어 mixed<번호>.json 으로 저장한다 — 형식은 mix 세트와 같아 chain_e2e.py·평가 코드가 그대로 읽는다. 유형 이름: tourist_synth_in(일정 안 장소, 정답 항목) · tourist_synth_out(일정 밖 장소, 정답 없음) · chitchat(정답 없음) · 그 밖은 기존 유형.
# 사용: python build_mixed_testset.py   (final_project_cs 폴더의 로컬 DB 필요 — 읽기 전용)
import ast
import collections
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(ROOT, 'datasets', 'travel', 'mixed_testset')
TRAVEL = os.path.join(ROOT, 'datasets', 'travel')
SEED = 20261006
N_SYN = 60            # 일정마다: 일정 안 장소 N_SYN · 일정 밖 장소 N_SYN
N_CHAT = 200          # 일정마다: AI Hub 일상 대화
N_KOCUL = 60          # 일정마다: 신조어 구어체
sys.stdout.reconfigure(encoding='utf-8')
rnd = random.Random(SEED)
os.makedirs(OUT, exist_ok=True)


def titles_from_db():
    import psycopg
    env = open(os.path.join(ROOT, 'final_project_cs', '.env'), encoding='utf-8').read()
    url = re.search(r'^ACOP_DATABASE_URL=(.+)$', env, re.M).group(1).strip().replace('postgresql+psycopg://', 'postgresql://')
    with psycopg.connect(url, connect_timeout=5) as c:
        cur = c.cursor()
        cur.execute('select distinct title from place_catalog')
        return sorted({r[0].strip() for r in cur.fetchall() if r[0] and len(r[0].strip()) >= 3})


def has_batchim(ch):
    code = ord(ch) - 0xAC00
    return 0 <= code < 11172 and code % 28 != 0


def has_rieul(ch):
    code = ord(ch) - 0xAC00
    return 0 <= code < 11172 and code % 28 == 8


PART = [('은', '는'), ('이', '가'), ('을', '를'), ('과', '와')]


def fit_particle(place, post):
    """장소 이름 끝 글자에 맞게 바로 뒤 조사를 고친다(은/는 · 이/가 · 을/를 · 과/와 · 으로/로)."""
    last = place[-1]
    b = has_batchim(last)
    for with_b, no_b in PART:
        if post.startswith(with_b) or post.startswith(no_b):
            if post[:1] in (with_b, no_b) and (len(post) == 1 or not ('가' <= post[1] <= '힣') or post[1] in '의에서도만'):
                return (with_b if b else no_b) + post[1:]
    if post.startswith('으로') or (post.startswith('로') and not post.startswith('로서')):
        rest = post[2:] if post.startswith('으로') else post[1:]
        return ('으로' if (b and not has_rieul(last)) else '로') + rest
    return post


def build_templates(titles):
    qs = [json.loads(l) for l in open(os.path.join(TRAVEL, 'tourist_attractions_qa_seoul_gyeonggi', 'processed', 'questions.jsonl'), encoding='utf-8')]
    by_len = sorted(titles, key=len, reverse=True)
    tmpl, miss = [], 0
    for r in qs:
        q = r['input']
        hit = next((t for t in by_len if t in q), None)
        if hit is None:
            miss += 1
            continue
        i = q.index(hit)
        tmpl.append({'instruction': r['instruction'], 'pre': q[:i], 'post': q[i + len(hit):], 'orig_place': hit, 'orig': q})
    return qs, tmpl, miss


def fill(t, place):
    return t['pre'] + place + fit_particle(place, t['post'])


def load_chat():
    chat = []
    with open(os.path.join(TRAVEL, '020.주제별 텍스트 일상 대화 데이터', 'processed', 'chat_utterances.jsonl'), encoding='utf-8') as f:
        for k, line in enumerate(f):
            if k >= 200000:               # 앞 20만 줄에서만(한 파일이 155만 줄)
                break
            x = json.loads(line)
            t = x['t'].strip()
            if 6 <= len(t) <= 80 and '여행' not in (x.get('subject') or '') and not re.fullmatch(r'[ㅋㅎㅠㅜ\s.?!~]+', t):
                chat.append(t)
    kocul = []
    for line in open(os.path.join(TRAVEL, 'koculture_dialogues', 'processed', 'utterances.jsonl'), encoding='utf-8'):
        t = json.loads(line)['question'].strip()
        if 6 <= len(t) <= 80:
            kocul.append(t)
    return chat, kocul


def main():
    titles = titles_from_db()
    qs_all, tmpl, miss = build_templates(titles)
    # 틀 거르기: 질문이 너무 길거나(한 문장 120자 초과) 장소 뒤에 「주변·인근」 이 붙은 추천형은 장소 이름만 바꿔도 의미가 어긋나지 않아 그대로 둔다
    # 틀 거르기: ① 한 문장 100자 미만 ② 장소 이름 바로 앞이 단어 중간이면(예: 원문 장소의 앞 일부만 찾은 경우) 버린다 — 앞부분이 비었거나 공백으로 끝나고 6자 이하(지역 접두어 「연천 」 정도)여야 한다
    #  ③ 장소 바로 뒤는 조사·공백·문장부호로 시작해야 한다(뒤가 한글 내용어면 장소 이름의 뒷부분을 놓친 것)
    ok_post = re.compile(r'^(?:$|[\s,.?!)]|은|는|이|가|을|를|의|에|도|만|과|와|으로|로|에서|부터|까지|하고)')
    tmpl = [t for t in tmpl if len(t['pre'] + t['post']) < 100 and (t['pre'] == '' or (t['pre'].endswith(' ') and len(t['pre']) <= 6)) and ok_post.match(t['post'])]
    by_ins = collections.Counter(t['instruction'] for t in tmpl)
    chat, kocul = load_chat()
    rnd.shuffle(chat)
    rnd.shuffle(kocul)
    sets = {}
    stats = {'원본 관광지 질문': len(qs_all), '장소 이름을 찾은 틀': len(tmpl), '장소를 못 찾음(지역·일반 질문 등)': miss, '틀 유형 분포': dict(by_ins.most_common()), '일상 대화 후보': len(chat), '구어체 후보': len(kocul), 'seed': SEED, 'per_set': {}}
    ci = ki = 0
    catalog_pool = list(titles)
    syn_rows = []
    for w in ('mix8', 'mix9', 'mix10', 'mix11', 'mix12'):
        job = json.load(open(os.path.join(HERE, 'fixtures', f'{w}.json'), encoding='utf-8'))['sets'][w]
        items = [i for i in job['items'] if i['kind'] != 'mobility' and len(i['place']) >= 2]
        item_names = ' '.join(f"{i['title']} {i['place']}" for i in job['items'])
        qs = [dict(q, src='합성(Codex·Claude)') for q in job['qs']]
        # 일정 안 장소로 채운 질문 — 정답 = 그 항목
        inn = []
        for _ in range(N_SYN):
            it = rnd.choice(items)
            t = rnd.choice(tmpl)
            inn.append({'q': fill(t, it['place']), 'gold': it['id'], 'type': 'tourist_synth_in', 'split': 'test', 'history': [], 'src': '관광지 질문 틀 × 일정 안 장소', 'tmpl_ins': t['instruction']})
        # 일정 밖 장소로 채운 질문 — 정답 없음(이름이 일정 어느 항목과도 겹치지 않는 장소만)
        out = []
        while len(out) < N_SYN:
            place = rnd.choice(catalog_pool)
            if any(w_ in item_names for w_ in re.split(r'\s+', place) if len(w_) >= 2) or place in item_names or len(place) > 18:
                continue
            t = rnd.choice(tmpl)
            out.append({'q': fill(t, place), 'gold': None, 'type': 'tourist_synth_out', 'split': 'test', 'history': [], 'src': '관광지 질문 틀 × 일정 밖 장소(우리 장소 목록)', 'tmpl_ins': t['instruction']})
        chats = [{'q': t, 'gold': None, 'type': 'chitchat', 'split': 'test', 'history': [], 'src': '일상 대화(AI Hub)'} for t in chat[ci:ci + N_CHAT]]
        ci += N_CHAT
        kos = [{'q': t, 'gold': None, 'type': 'chitchat', 'split': 'test', 'history': [], 'src': '구어체 대화(KoCulture)'} for t in kocul[ki:ki + N_KOCUL]]
        ki += N_KOCUL
        allq = qs + inn + out + chats + kos
        rnd.shuffle(allq)
        name = w.replace('mix', 'mixed')
        sets[name] = {'today': job['today'], 'items': job['items'], 'qs': allq}
        syn_rows += inn + out
        stats['per_set'][name] = dict(collections.Counter(q['type'] if q['type'] in ('tourist_synth_in', 'tourist_synth_out', 'chitchat') else '기존 합성 질문' for q in allq), 합계=len(allq))
        json.dump({'sets': {name: sets[name]}}, open(os.path.join(OUT, f'{name}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        # 임베딩 점수 계산용 쌍 자료(질문 × 항목 설명)는 같은 일정의 기존 파일에서 항목 설명만 가져다 쓴다 — chain_emb.py 가 item → 설명 대응만 읽는다
        pairs = json.load(open(os.path.join(HERE, 'fixtures', f'pairs_{w}.json'), encoding='utf-8'))
        json.dump(pairs, open(os.path.join(OUT, f'pairs_{name}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump(syn_rows, open(os.path.join(OUT, 'synth_tour_questions.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    json.dump(stats, open(os.path.join(HERE, 'results', 'mixed_testset_stats.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in stats.items() if k != '틀 유형 분포'}, ensure_ascii=False, indent=1))
    for r in rnd.sample(syn_rows, 10):
        print(r['type'], '|', r['gold'], '|', r['q'])


if __name__ == '__main__':
    main()
