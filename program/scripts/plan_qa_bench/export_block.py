# 모델·구성 × 시험 세트 × 문제 결과를 CSV·JSON·엑셀로 남긴다 — matrix_block.py 끝에서 같은 이름공간으로 실행된다(`eval_final_all.py ... --matrix <md> --export <폴더>`).
#  만드는 것(폴더 안): per_question.csv(문제별 한 줄) · summary_model_set.csv(모델×세트 정답 수) · models.csv(모델 정보) · results_all.json · results_all.xlsx · README.md
#  ★「공정 비교 아님」 열: 세트 전체를 한 번에 푼 묶음 풀이(Claude · Codex 루나)는 fair_comparison=False 와 caveat 문장이 모든 파일에 붙는다.
import csv, datetime, json, os

import pandas as pd

EXP = argv0[argv0.index('--export') + 1]
os.makedirs(EXP, exist_ok=True)
AUTHOR = {'mix6': 'Codex(gpt-6-sol)', 'mix7': 'Codex(gpt-6-sol)', 'mix8': 'Codex(gpt-6-sol)', 'mix9': 'Codex(gpt-6-sol)', 'mix10': 'Codex(gpt-6-sol)',
          'mix11': 'Codex(gpt-6-sol)', 'mix12': 'Claude(Opus 하위 작업)'}
UNFAIR_CLAUDE = 'Claude 하위 작업이 세트 전체를 한 번에 푼 묶음 풀이이고 생각 설정을 통제하지 못했다(켜져 있었을 수 있다). 로컬(문제 하나씩·생각 끔·온도 0)과 공정한 비교가 아니다 — 천장 참고용(§62·§62-2)'
UNFAIR_LUNA = 'Codex 가 세트 전체를 한 번에 푼 묶음 풀이(생각 설정 모름). 로컬(문제 하나씩·생각 끔)과 공정한 비교가 아니다 — 천장 참고용(§14-8)'


def fair_info(label):
    if 'Claude' in label and '공정 비교 아님' in label:
        return False, UNFAIR_CLAUDE
    if 'Codex luna' in label and '공정 비교 아님' in label:
        return False, UNFAIR_LUNA
    return True, ''


def _idx(w):
    return idx_of(w) if w in _DEV else list(range(len(SETS[w]['qs'])))


rows = []          # per-question
models = []        # model meta
COLS = ['kind', 'model', 'set', 'set_author', 'q_index', 'q_type', 'gold', 'pick', 'correct', 'wrong_non_null', 'llm_calls', 'fair_comparison', 'caveat']


def add(kind, model, w, i, pick, calls, fair, cav):
    q = SETS[w]['qs'][i]
    g = q['gold']
    rows.append([kind, model, w, AUTHOR.get(w, '[미확인]'), i, q.get('type'), g, pick, int(pick == g), int(pick is not None and pick != g), calls, fair, cav])


for nm, sz, srv, tm, fn in _DIRECT:
    fair, cav = fair_info(nm)
    kind = 'direct' if fair else 'direct_reference_unfair'
    got = 0
    for w in _ALL:
        try:
            pk = fn(w)
        except Exception:  # noqa: BLE001
            pk = None
        if pk is None:
            continue
        idx = _idx(w)
        if len(pk) < max(idx) + 1:
            continue
        for i in idx:
            add(kind, nm, w, i, pk[i], 1, fair, cav)
        got += 1
    models.append({'kind': kind, 'model': nm, 'size_storage_active': sz, 'serving': srv, 'sec_per_q': tm, 'fair_comparison': fair, 'caveat': cav, 'sets_covered': got})

for n in names:
    got = 0
    for w in _DEV:
        try:
            for i in idx_of(w):
                p, c = P[n](w, i)
                add('combo', n, w, i, p, c, True, '')
            got += 1
        except Exception:  # noqa: BLE001
            continue
    for w in EV:
        for i in range(len(gold[w])):
            p, c = res[w][n][i]
            add('combo', n, w, i, p, c, True, '')
        got += 1
    models.append({'kind': 'combo', 'model': n, 'size_storage_active': '', 'serving': '규칙·앞단·게이트·모델 조합', 'sec_per_q': '', 'fair_comparison': True, 'caveat': '개발 세트(heavy·mix4~7) 값은 문턱·τ 를 고른 세트라 낙관적', 'sets_covered': got})

df = pd.DataFrame(rows, columns=COLS)
summ = (df.groupby(['kind', 'model', 'set', 'set_author', 'fair_comparison'], sort=False)
        .agg(n=('correct', 'size'), correct=('correct', 'sum'), wrong_non_null=('wrong_non_null', 'sum'), llm_calls=('llm_calls', 'sum')).reset_index())
summ['accuracy'] = (summ['correct'] / summ['n']).round(4)
summ['caveat'] = summ['model'].map(lambda m: fair_info(m)[1])
mdf = pd.DataFrame(models)
wide = summ.assign(cell=lambda d: d['correct'].astype(str) + '/' + d['n'].astype(str)).pivot_table(index=['kind', 'model', 'fair_comparison'], columns='set', values='cell', aggfunc='first', sort=False).reset_index()
ordered = [c for c in ['heavy', 'mix4', 'mix5', 'mix6', 'mix7', 'mix8', 'mix9', 'mix10', 'mix11', 'mix12'] if c in wide.columns]
wide = wide[['kind', 'model', 'fair_comparison'] + ordered]

df.to_csv(os.path.join(EXP, 'per_question.csv'), index=False, encoding='utf-8-sig')
summ.to_csv(os.path.join(EXP, 'summary_model_set.csv'), index=False, encoding='utf-8-sig')
mdf.to_csv(os.path.join(EXP, 'models.csv'), index=False, encoding='utf-8-sig')
meta = {'generated': datetime.datetime.now().isoformat(timespec='seconds'), 'sets': _ALL, 'set_author': {w: AUTHOR.get(w, '[미확인]') for w in _ALL},
        'caveats': {'unfair_claude': UNFAIR_CLAUDE, 'unfair_codex_luna': UNFAIR_LUNA,
                    'fair_definition': '로컬 모델·조합은 문제 하나씩 · 생각 끔 · 온도 0 · 번호만 JSON. fair_comparison=False 는 이 조건과 달라 천장 참고용이다.',
                    'dev_sets': '개발 5세트(heavy·mix4~7)의 조합 값은 문턱·τ 를 고른 세트라 낙관적이다.'},
        'per_question_columns': COLS}
json.dump({**meta, 'models': models, 'summary': json.loads(summ.to_json(orient='records', force_ascii=False)),
           'per_question': json.loads(df.to_json(orient='values', force_ascii=False))},
          open(os.path.join(EXP, 'results_all.json'), 'w', encoding='utf-8'), ensure_ascii=False)
readme = pd.DataFrame({'읽는 법': [
    '이 파일은 eval_final_all.py --export 가 만든다(손으로 고치지 않는다).',
    f"생성 {meta['generated']} · 세트 {', '.join(_ALL)}",
    '※ fair_comparison=False 인 행(Claude Opus 5.5 · Fable 5.1 · Codex 루나)은 ' + '세트 묶음 풀이 + 생각 설정 통제 불가라 로컬과 공정한 비교가 아니다. 천장 참고용이다.',
    '로컬 모델·조합: 문제 하나씩 · 생각 끔 · 온도 0 · 번호만 JSON.',
    '개발 5세트(heavy·mix4~7)의 조합 값은 문턱·τ 를 고른 세트라 낙관적이다. 판정은 시험 세트(mix8 이후)로 한다.',
    'set_author: mix8~mix11 은 Codex(gpt-6-sol), mix12 는 Claude 가 썼다(§61). mix4·5·heavy 는 [미확인].',
    'per_question: pick 은 고른 일정 번호(없으면 빈 칸=null), gold 는 정답 번호(없으면 빈 칸=정답 없음), wrong_non_null=엉뚱한 번호를 댄 경우.']})
with pd.ExcelWriter(os.path.join(EXP, 'results_all.xlsx'), engine='openpyxl') as xw:
    readme.to_excel(xw, sheet_name='읽는 법', index=False)
    wide.to_excel(xw, sheet_name='요약(모델×세트)', index=False)
    summ.to_excel(xw, sheet_name='요약(긴 형식)', index=False)
    mdf.to_excel(xw, sheet_name='모델 정보', index=False)
    df.to_excel(xw, sheet_name='문제별 결과', index=False)
open(os.path.join(EXP, 'README.md'), 'w', encoding='utf-8').write(
    '# 모델 비교 결과 내보내기\n\n자동 생성 파일이다(`eval_final_all.py --sets ... --matrix <md> --export <폴더>`). 손으로 고치지 않는다.\n\n'
    + '\n'.join('- ' + t for t in readme['읽는 법']) + '\n\n'
    '| 파일 | 내용 |\n|---|---|\n| per_question.csv | 모델·구성 × 세트 × 문제 한 줄(정답·고른 번호·맞음 여부·공정 비교 여부) |\n'
    '| summary_model_set.csv | 모델 × 세트 정답 수·정확도 |\n| models.csv | 모델 정보(크기·서버·질문당 시간·공정 비교 여부·주의) |\n'
    '| results_all.json | 위 전부를 한 파일로 |\n| results_all.xlsx | 엑셀(요약·긴 형식·모델 정보·문제별 결과 시트) |\n')
print('내보내기:', EXP, '· 문제별', len(df), '줄 · 모델·구성', len(models), '개 · 공정 비교 아님', int((~mdf['fair_comparison']).sum()), '개')
