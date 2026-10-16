"""B/C 채점과 D 및 사용자 E(MX)의 보관 원본을 새 날짜 스냅샷으로 모은다."""
from pathlib import Path
from datetime import datetime
import json
import hashlib
import sys

HERE = Path(__file__).resolve().parent
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
ROOT = HERE.parents[2]
RES = HERE / 'results'
sys.stdout.reconfigure(encoding='utf-8')
stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
gs = json.loads((Path(fixture('gold_sets.json'))).read_text(encoding='utf-8'))
fixtures = {s: json.loads((Path(fixture(f'{s}.json'))).read_text(encoding='utf-8'))['sets'][s] for s in gs}
keys = [(s, i) for s in ['mix8', 'mix9', 'mix10', 'mix11', 'mix12'] for i in range(len(fixtures[s]['qs']))]
assert len(keys) == 835
comp = [k for k in keys if len(gs[k[0]][str(k[1])]) == 2]
assert len(comp) == 66
sources = {}


def read(p, lines=False):
    sources[p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()] if lines else json.loads(p.read_text(encoding='utf-8'))


def bc(picks, valid):
    b = c = cb = cc = non = 0
    for k in keys:
        if not valid.get(k, False):
            continue
        want = set(gs[k[0]][str(k[1])]); picked = set(picks[k] or [])
        hit_b = bool(picked & want) if want else not picked
        hit_c = picked == want
        b += hit_b; c += hit_c
        if k in comp:
            cb += hit_b; cc += hit_c
        else:
            non += hit_c
    return {'B': [b, 835], 'C': [c, 835], 'compound_B': [cb, 66], 'compound_C': [cc, 66],
            'single_correct': [non, 769], 'missing_or_invalid': 835-sum(valid.get(k, False) for k in keys)}


labels = [('기존 학습 시드1', 'r16e2'), ('기존 학습 시드2', 'e4bs2'), ('기존 학습 시드3', 'e4bs3'),
          ('잡담 보강 시드1', 'oos1'), ('잡담 보강 시드2', 'oos2'), ('잡담 보강 시드3', 'oos3'),
          ('어려운 문장 보강 oos2r', 'oos2r'), ('여러 항목 학습판', 'e4bm'),
          ('Jev 계열 Winnow-E4B 우리 학습 이전판', 'winnow_e4b'), ('spark-s1-4b-v6 우리 학습 이전판', 'spark_s1_4b'),
          ('Jev 계열 jevify-gemma4-e4b 우리 학습 이전판', 'jevify_e4b')]
labels = [('Gemma E4B '+label if tag in {'r16e2','e4bs2','e4bs3','oos1','oos2','oos3','oos2r','e4bm'} else label, tag) for label,tag in labels]
basics = []
for label, tag in labels:
    picks = {}; valid = {}; errors = 0
    for s in ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']:
        data = read(RES / f'_pull/distill_eval/eval_{tag}_{s}.json')[tag+'#lora']
        assert data['_errors'] == 0, 'Aggregate errors have no per-item location; cannot claim exact recount'
        assert len(data['picks']) == len(fixtures[s]['qs'])
        for i, p in enumerate(data['picks']):
            picks[(s, i)] = p if isinstance(p, list) else [] if p is None else [p]
            valid[(s, i)] = True
    basics.append({'model': label, 'our_training': True, 'tag': tag, 'execution': 'HF 4bit adapter basic evaluation', **bc(picks, valid)})
for name, pattern in [('Claude Opus 5.5', 'claude_claude_opus_5_5'), ('Claude Fable 5.1', 'claude_claude_fable_5_1'),
                      ('Codex gpt-6-luna', 'codexcli_gpt-6-luna'), ('Codex gpt-6-sol', 'codexcli_gpt-6-sol'),
                      ('Codex gpt-6-astra', 'codexcli_gpt-6-astra')]:
    picks = {}; valid = {}
    for s in ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']:
        rows = read(RES / f'{pattern}_{s}_multi.json')['rows']
        for i in range(len(fixtures[s]['qs'])):
            row = rows.get(str(i)); key = (s, i)
            valid[key] = row is not None and bool(row.get('parsed')) and not row.get('error')
            picks[key] = row.get('picks') if row else None
    basics.append({'model': name, 'our_training': False, 'execution': 'Cloud CLI, multi-item prompt; author-family bias', **bc(picks, valid)})

def summarize(items, answers):
    p = [x for x in items if x['gold'] is not None and x['type'] != 'compound_intent']
    n = [x for x in items if x['gold'] is None and x['type'] != 'compound_intent']
    valid = lambda r: r is not None and bool(r.get('parsed')) and not r.get('error')
    return {'positive_correct': [sum(valid(answers.get(x['i'])) and answers[x['i']]['pick'] == x['gold'] for x in p), len(p)],
            'false_pick': [sum(valid(answers.get(x['i'])) and answers[x['i']]['pick'] is not None for x in n), len(n)],
            'failed_or_missing': sum(not valid(answers.get(x['i'])) for x in items)}

d_gold = read(ROOT / 'datasets/core/pointing/testset/questions_plus_chitchat_v1/all_prompts.json')
e_gold = read(ROOT / 'datasets/core/pointing/testset/requests_inside_chitchat_pairs_v1/mx_main_prompts.json')
mixed = [x for x in e_gold if x['kind'] == 'mixed']
natural = [x for x in mixed if x['src'] == 'llm']
assert len(mixed) == 2007 and len(natural) == 239
de = []
for label, tag in labels[:7]:
    d = read(RES / f'd_test/d_test_lp_q4km_{"e4bt" if tag=="r16e2" else tag}.jsonl', True)
    e = read(RES / f'd_test/d_test_lp_mx_q4km_{"e4bt" if tag=="r16e2" else tag}.jsonl', True)
    de.append({'model': label, 'our_training': True, 'D': d, 'E': e})
de += [{'model': 'FrogNano-4B-2609 원본', 'our_training': False,
        'D': read(RES / 'd_test/d_test_a_frognano.jsonl', True),
        'E': read(RES / 'gpu_backlog_20261008/frog_mx/d_test_mx_backlog_frog.jsonl', True)},
       {'model': 'Gemma-4-E4B-it Q4_K_M 원본', 'our_training': False,
        'D': read(RES / 'gpu_backlog_20261008/e4bbase_d/d_test_d_backlog_e4bbase.jsonl', True),
        'E': read(RES / 'gpu_backlog_20261008/e4bbase_mx/d_test_mx_backlog_e4bbase.jsonl', True)}]
for r in de:
    for suite, gold in [('D', d_gold), ('E', e_gold)]:
        rows = r[suite]; answers = {x['i']: x for x in rows}; ref = {x['i']: x for x in gold}
        assert len(rows) == len(answers) and set(answers) == set(ref), 'Missing/duplicate IDs'
        assert all(x['gold'] == ref[i]['gold'] and x['type'] == ref[i]['type'] for i,x in answers.items())
        r[suite] = {'saved': len(rows), 'expected': len(gold), 'all_failures': sum(not x.get('parsed') or bool(x.get('error')) for x in rows),
                    **summarize(gold if suite=='D' else mixed, answers)}
        if suite == 'E':
            r['E_natural'] = summarize(natural, answers)
            control = summarize([x for x in e_gold if x['kind']=='control'], answers)
            r['E']['control'] = control
            p, n = r['E']['positive_correct'], r['E']['false_pick']
            pc, nc = control['positive_correct'], control['false_pick']
            r['E']['request_loss_pp'] = 100*(pc[0]/pc[1]-p[0]/p[1])
            r['E']['false_pick_increase_pp'] = 100*(n[0]/n[1]-nc[0]/nc[1])
            r['E']['gates_passed'] = sum([p[0]/p[1]>=.95, n[0]/n[1]<=.01, r['E']['request_loss_pp']<=2, r['E']['false_pick_increase_pp']<=1])

def ratio(pair):
    a,b = pair
    return f'{a}/{b} = {100*a/b:.2f}%'

snap = read(RES / 'gpu_backlog_20261008/A_snapshot_user_b_c_d_e.json')
out = {'observed_at': datetime.now().isoformat(), 'E_alias': 'User E = mixed/free-text request MX suite', 'BC': basics, 'DE': de,
       'E_natural_expected': len(natural), 'original_gemma12b_E_saved_at_observation': snap['answers'].get('g12bbase_mx/d_test_mx_backlog_g12bbase.jsonl'),
       'original_gemma12b_E_expected': 4014, 'sources_sha256': sources}
path = RES / f'bcde_results_{stamp}.json'
with path.open('x', encoding='utf-8') as f: json.dump(out, f, ensure_ascii=False, indent=2)
md = ['# B·C·D·E 최신 결과 스냅샷', '',
      '사용자가 말한 E는 저장된 MX(평문·잡담에 실제 일정 질문·변경 요청이 섞인 입력)다. B/C는 같은835문항의 서로 다른 채점이고 D/E는 별도 입력 세트다. 새 모델 호출 없이 보관 원본을 직접 계수했다.', '',
      '| 할 일 | 상태 | 진행 |', '|---|---|---|',
      f'| B/C 기본·집합 출력 재계수 | 완료 | {len(basics)}/{len(basics)} = 100% |',
      f'| D/E 전체 보관본 재계수 | 완료 | {len(de)}/{len(de)} = 100% |', '',
      '## D와 E 결과', '', '| 모델·판 | D 정상 요청↑ | D 요청 없음 오지목↓ | E 혼합 요청↑ | E 요청 없음 오지목↓ | E 기준 | D/E 형식 실패 |', '|---|---|---|---|---|---|---|']
for r in de:
    md.append(f"| {r['model']} | {ratio(r['D']['positive_correct'])} | {ratio(r['D']['false_pick'])} | {ratio(r['E']['positive_correct'])} | {ratio(r['E']['false_pick'])} | {r['E']['gates_passed']}/4 | {r['D']['all_failures']}/{r['E']['all_failures']} |")
md += ['', 'D 전체2735문항, 복합66개를 제외한 단일 선택2669개: 정상883·요청 없음1786이다.',
       'E 전체4014개는 혼합2007·대조2007이며 혼합 중 정상 요청1033·요청 없음974다. 실제 오지목과 형식 실패를 별도로 센다. 실패·미완료는 해당 전체 분모에 남기고 정답으로 세지 않는다.', '',
       '## E의 자연스럽게 쓴 혼합 문장만', '', '| 모델·판 | 자연 혼합 요청↑ | 자연 혼합 요청 없음 오지목↓ |', '|---|---|---|']
for r in de:
    md.append(f"| {r['model']} | {ratio(r['E_natural']['positive_correct'])} | {ratio(r['E_natural']['false_pick'])} |")
md += ['', '혼합2007개 중1768개는 코드로 잡담을 이어 붙였고239개는 모델이 자연스러운 평문으로 작성했다. 자연 혼합239개는 정상93·요청 없음146이다. 실제 사용자 자유 대화나 DB 답변 정확도를 검증한 것은 아니다. 사람 정답 검수0건·합의분 선별로 어려운 사례가 제외된 한계가 있다.', '',
       '## B와 C', '', '| 모델·판 | B 하나라도 맞힘(835) | C 전부 정확(835) | 두 요청 B(66) | 두 요청 C(66) | 실패·누락 |', '|---|---|---|---|---|---|']
for r in basics:
    md.append(f"| {r['model']} | {ratio(r['B'])} | {ratio(r['C'])} | {ratio(r['compound_B'])} | {ratio(r['compound_C'])} | {r['missing_or_invalid']} |")
md += ['', 'B는 정답 목록 중 하나라도 고르면 성공, C는 선택한 전체 목록이 정답 목록과 정확히 같아야 성공이다. 요청 없으면 둘 다 빈 목록이 정답이다. 한 번호만 내는 모델의 두 요청 C는0/66이며 단일 선택 결과만으로 다중 요청을 지원한다고 하지 않는다.',
       'B/C 우리 학습판은HF4비트+어댑터 기본 평가, D/E는 서비스 기반Q4_K_M llama.cpp 평가다. 서로 다른 경로의 지연을 비교하지 않으며 시드·학습 자료·출력 계약 차이를 구분한다. 이전 Winnow/spark/jevify 어댑터의 기본 평가를 현재 실행 중인 잡담 보강 새 어댑터의 결과로 취급하지 않는다.',
       'Claude·Codex 집합 출력은 모델·문항 작성자 계열에 따른 편향이 있어 공정한 일반 순위로 해석하지 않는다. 그외 과거 원본·조합 C 기록은 [기존 전체 C표](c_scoring_all.txt), 독립 개발/시험 문턱 분리는 [오프라인 C표](c_offline_mix8to12.md)에서 확인한다.',
       f"Gemma12B 원본 E는 관측 당시 {out['original_gemma12b_E_saved_at_observation']}/4014개 저장·실행 중이므로 최종 점수를 내지 않았다. Winnow-E4B 원본 E도 대기 중이다. MAI는D3만 지정 완료했으며 B/C/D전체/E 점수를 이 표에 대입하지 않았다.",
       '기존 개발/회귀 세트・모델 실행1회이며 시드3개의 범위와1개 모델의 반복 검증은 다르다. 새 독립 보류 자료와 전체 원본 비교군 완료 전 서비스 채택·일반 우열을 확정하지 않는다.', '',
       f'[구조화된 원본 경로·해시·계수]({path.name}). 새 이름의 스냅샷으로 저장해 기존 결과를 덮지 않았다.']
md_path = path.with_suffix('.md')
with md_path.open('x', encoding='utf-8') as f: f.write('\n'.join(md)+'\n')
print(json.dumps({'report': md_path.relative_to(ROOT).as_posix(), 'BC_models':len(basics), 'DE_models':len(de),
                  'BC':basics, 'DE': [{k:v for k,v in r.items() if k!='our_training'} for r in de]}, ensure_ascii=False))
