# 「항목 짚기」 자체를 학습시킬 자료(SFT) 만들기 — 소형 언어 모델(Qwen3.5·Gemma 4 E2B 등)에 LoRA 로 학습.
#  장소·문장은 gen_train.py 와 같은 풀(Codex 작성, 시험 일정 장소 제외, 같은 검증 장소 분할)에서 뽑고, 일정·라벨은 코드가 만든다.
#  프롬프트는 서버 평가 질의문(llm_point_heavy.py)과 글자 그대로 같고, 답은 {"item": 번호} 또는 {"item": null}.
#  종류: 이름·별칭·오타·채팅체·설명·요청·정보(정답 있음 70%) · 일정에 없는 장소(정답 없음 20%) · 일정 무관 문장(정답 없음) · 앞 대화 지시어(일부)
# 사용: python gen_pointer_sft.py <places 폴더> → fixtures/pointer_sft.json {'train': [...], 'val': [...]}
import json, os, random, sys, glob, re

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen_train.py'), encoding='utf-8').read()
head = src[:src.index('def build(')]          # 풀·검증 분할·make_itinerary·doc 까지(같은 난수 순서로 실행되어 같은 분할이 나온다)
ns = {'__name__': 'gt', 'sys': sys, '__file__': os.path.abspath(__file__).replace('gen_pointer_sft.py', 'gen_train.py')}
exec(compile(head, 'gen_train_head', 'exec'), ns)
W = '월화수목금토일'
rnd = ns['rnd']
rnd.seed(777)                                   # 이후 표집은 새 난수
make_itinerary, tr_places, val_places, oos_tr, oos_val = ns['make_itinerary'], ns['tr_places'], ns['val_places'], ns['oos_tr'], ns['oos_val']
PRON = ['그거 취소해줘', '거기 예약돼 있어?', '그 시간 바꿔줘', '거기 몇 시였지?', '그건 빼줘', '그거 한 시간 미뤄줘', '거기 입장료 얼마야?']
TPL = ("오늘은 {today} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}고객 질문: {q}\n\n"
       "이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. 질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null.")


def sample_set(pool, oos_list, n_itin, per):
    out = []
    for _ in range(n_itin):
        items = make_itinerary(pool)
        for k, it in enumerate(items):
            it['id'] = k + 1
        days = sorted({i['date'] for i in items})
        plan = '\n'.join(f"{i['id']}. {days.index(i['date']) + 1}일차 {i['date'].month}/{i['date'].day}({W[i['date'].weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}" for i in items)
        today = (items[0]['date'].fromordinal(items[0]['date'].toordinal() - rnd.randint(1, 4))).isoformat()
        inset = {i['place'] for i in items}
        outside = [p for p in pool if p['name'] not in inset]
        for _ in range(per):
            r = rnd.random()
            hist = ''
            if r < 0.60:
                it = rnd.choice(items)
                q = rnd.choice(it['p']['questions'])['q']
                gold = it['id']
            elif r < 0.72:                       # 앞 대화 지시어
                it = rnd.choice(items)
                q = rnd.choice(PRON)
                d = days.index(it['date']) + 1
                hist = f"앞 대화:\n고객: {it['place']} 몇 시야?\n서비스: {d}일차 {it['start']} {it['title']}이에요\n\n"
                gold = it['id']
            elif r < 0.90 and outside:
                q = rnd.choice(rnd.choice(outside)['questions'])['q']
                gold = None
            else:
                q = rnd.choice(oos_list)
                gold = None
            prompt = TPL.replace('{today}', today).replace('{plan}', plan).replace('{hist}', hist).replace('{q}', q)
            out.append({'prompt': prompt, 'answer': json.dumps({'item': gold}, ensure_ascii=False), 'gold': gold})
    return out


N_ITIN = int(os.environ.get('N_ITIN', '60'))
train = sample_set(tr_places, oos_tr, N_ITIN, 40)
val = sample_set(val_places, oos_val, 12, 25)
json.dump({'train': train, 'val': val}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', os.environ.get('OUT', 'pointer_sft.json')), 'w', encoding='utf-8'), ensure_ascii=False)
print('학습', len(train), '· 검증', len(val), '· 정답 없음 비율', f"{sum(x['gold'] is None for x in train) / len(train):.0%}", '· 평균 프롬프트 글자', sum(len(x['prompt']) for x in train) // len(train))
