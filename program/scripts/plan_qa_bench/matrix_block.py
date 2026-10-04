# 모델·구성 × 시험 세트 행렬 — eval_final_all.py 가 `--matrix <출력파일>` 일 때 같은 이름공간에서 실행한다(독립 실행 아님).
#  ① 직접 짚기(모델 하나가 규칙·앞단 없이 푼 것) ② 조합(규칙·앞단·게이트·여러 모델). 세트별 정답 수/문제 수 + 합 + 26B 대비·Jev 대비 짝지은 차이.
#  개발 5세트(heavy 판정·mix4~mix7)는 앞단 문턱·τ·게이트 문턱을 고른 세트라 조합 값이 낙관적이다 — 시험 세트(mix8·mix9)가 판정용이다.
import math

_DEV = LABELED
_ALL = _DEV + EV


def _pk_from_dec(tag, w):
    return _dec_pick(tag, w)


def _pk_jev(w):
    if w not in JEV:
        return None
    return [jev_choice(w, i)[0] for i in range(len(SETS[w]['qs']))]


def _pk_g(model):
    def f(w):
        return G[w].get(model) if model else None
    return f


def _pk_26(w):
    k = k26(w)
    return G[w][k] if k else None


def _pk_luna(proto):
    return lambda w: LUNA[w][proto]


# (이름, 크기·저장·활성 한 줄, 서버/방식, 질문당 시간, 사진: 고르는 함수)
_DIRECT = [
    ('Gemma 4 26B-A4B Q4_K_M (올라마)', '25B/17GB · 활성 3.8B', '쓰던 서버 올라마', '약 11초', _pk_26),
    ('Gemma 4 12B (올라마)', '12B 밀집/7.6GB · 활성 11.9B', '쓰던 서버 올라마', '약 3.6초', _pk_g(M12)),
    ('Gemma 4 E4B QAT (올라마)', '유효 4B/6.1GB', '쓰던 서버 올라마', '약 1.3초', _pk_g(M)),
    ('Codex luna 직접', '(외부 API)', 'Codex', '—', _pk_luna(False)),
    ('Codex luna + 정의 직접', '(외부 API)', 'Codex', '—', _pk_luna(True)),
    ('Jev 직접 (유료)', '(외부 API)', 'TypeSafe API', '0.23초', _pk_jev),
    ('OpenJev 26B Q4_K_M', '26B/19GB · CC BY-NC', 'GPU+램 분할', '14초', lambda w: _pk_from_dec('openjev26b', w)),
    ('decider-chat Gemma4-31B bf16', '31B/62GB · 오프로드', '램+디스크 오프로드', '4.7초', lambda w: _pk_from_dec('decider31bl', w)),
    ('pplx-decider 27B NF4', '27B/약 14GB(4비트)', 'bitsandbytes', '2.7초', lambda w: _pk_from_dec('pplx27b', w)),
    ('Decider-12B bf16', '12B/24GB · Apache', '램 오프로드', '1.6초', lambda w: _pk_from_dec('decider12bl', w)),
    ('Decider-12B 8비트', '12B/약 13GB · Apache', 'bitsandbytes 8bit', '1.3초', lambda w: _pk_from_dec('decider12bq8', w)),
    ('Decider-12B NF4 4비트', '12B/약 8GB · Apache', 'bitsandbytes 4bit', '1.2초', lambda w: _pk_from_dec('decider12bq4', w)),
    ('Winnow-12B Q8', '12B/12.7GB · Apache', '자체 llama.cpp 서버', '1.6초', lambda w: _pk_from_dec('winnow12b', w)),
    ('Cygnet(얼린 Gemma-4-12B-it 글자 읽기, 8비트)', '12B/약 13GB(8비트) · Apache+Gemma 정책', '레시피 읽기 + bitsandbytes 8bit', '2.0초', lambda w: _pk_from_dec('cygnet', w)),
    ('Cygnet bf16 오프로드(램+GPU, 8비트 아님)', '12B/24GB · Apache+Gemma 정책', '레시피 읽기 + accelerate 오프로드', '9.8초', lambda w: _pk_from_dec('cygnetbf16', w)),
    ('Hopper 12B(얼린 Gemma-4-12B-it + LoRA r32, 8비트 적재)', '12B/약 13GB · Apache', 'bitsandbytes 8bit + 어댑터', '2.8초', lambda w: _pk_from_dec('hopper12b', w)),
    ('Jev-Omni 묶음 읽기(20개 이하씩)', '12B/24GB(8비트로 적재) · Apache', 'bitsandbytes 8bit', '1.8초', lambda w: _pk_from_dec('jevomnig', w)),
    ('Jev-Omni(Gemma-4-12B 합병 + 결정 머리)', '12B/24GB(8비트로 적재) · Apache', 'bitsandbytes 8bit', '—', lambda w: _pk_from_dec('jevomni', w)),
    ('Winnow-E4B Q8', 'E4B 유효 4B/8GB · Apache', '자체 llama.cpp 서버', '—', lambda w: _pk_from_dec('winnowe4b', w)),
    ('JevK5 4B v0.3 Q8', '4B/4.5GB · Apache', 'llama.cpp + JevK5 런타임', '—', lambda w: _pk_from_dec('jevk54b', w)),
    ('JevK5-9B v0.3.3 Q8', '9B/9.5GB · Apache', 'llama.cpp + JevK5 런타임', '—', lambda w: _pk_from_dec('jevk59b', w)),
    ('Plumb-4B v5 Q8', '4B/4.5GB · Apache', 'llama.cpp + JevK5 런타임', '—', lambda w: _pk_from_dec('plumb4b', w)),
    ('decider-chat Qwen3.6-27B bf16', '27B/55GB · Apache', '램+디스크 오프로드', '4.9초', lambda w: _pk_from_dec('decider27ql', w)),
    ('Qwen3.8 27B (올라마)', '27B/17GB', '쓰던 서버 올라마', '약 45초', lambda w: G[w].get('qwen3.8:27b')),
    ('Decider-35B-A3B bf16', '35B/69GB · 활성 3B', '램+디스크 오프로드', '1.7초', lambda w: _pk_from_dec('decider35bl', w)),
    ('Nimble-9B-v3 Q8', '9B/9.5GB · CC BY-NC', 'llama.cpp', '1.4초', lambda w: _pk_from_dec('nimble9b', w)),
    ('Imajev-4B', '4B/약 8GB', '자체 서버(torch)', '0.8초', lambda w: _pk_from_dec('imajev4b', w)),
    ('Decider-4B (자체 라이브러리)', '4B/8GB · Apache', 'torch', '0.5초', lambda w: _pk_from_dec('decider4bl', w)),
    ('Decider-2B', '2B', 'torch', '0.2초', lambda w: _pk_from_dec('decider2bl', w)),
    ('Decider-0.8B', '0.8B', 'torch', '0.15초', lambda w: _pk_from_dec('decider08bl', w)),
    ('Kev-9B Q8', '9B/9.5GB', 'llama.cpp', '1.2초', lambda w: _pk_from_dec('kev9b', w)),
    ('Kev-4B Q8', '4B/4.5GB', 'llama.cpp', '0.9초', lambda w: _pk_from_dec('kev4b', w)),
    ('Malkuth-4B', '4B · CC BY-NC', 'Kev 엔진', '1.1초', lambda w: _pk_from_dec('malkuth4b', w)),
    ('Laya Q8', '0.5B/0.45GB', 'llama.cpp', '0.02초', lambda w: _pk_from_dec('laya', w)),
]


def _cell(picks, w):
    if picks is None:
        return None
    idx = idx_of(w) if w in _DEV else list(range(len(gold[w]) if w in EV else len(SETS[w]['qs'])))
    n = len(idx)
    gw = [SETS[w]['qs'][i]['gold'] for i in range(len(SETS[w]['qs']))]
    try:
        ok = sum(picks[i] == gw[i] for i in idx)
        bad = sum(picks[i] is not None and picks[i] != gw[i] for i in idx)
    except Exception:  # noqa: BLE001
        return None
    return ok, n, bad


def _pair(vec_a, vec_b):
    a = sum(x == 1 and y == 0 for x, y in zip(vec_a, vec_b))
    b = sum(x == 0 and y == 1 for x, y in zip(vec_a, vec_b))
    d, lo_, hi_ = ci(a, b, len(vec_a))
    return d, lo_, hi_, a, b, pexact(a, b)


def _vec_from_picks(picks):
    return [int(picks[i] == gold[w][i]) for w in EV for i in range(len(gold[w]))]


_b26 = {w: _pk_26(w) for w in EV}
_v26 = None
if all(_b26[w] is not None for w in EV):
    _v26 = [int(_b26[w][i] == gold[w][i]) for w in EV for i in range(len(gold[w]))]
_jvp = {w: _pk_jev(w) for w in EV}
_vjev = [int(_jvp[w][i] == gold[w][i]) for w in EV for i in range(len(gold[w]))] if all(_jvp[w] is not None for w in EV) else None


def _fmt_pair(vec):
    cells = []
    for base in (_v26, _vjev):
        if base is None:
            cells.append('—')
            continue
        d, lo_, hi_, a, b, p = _pair(vec, base)
        cells.append(f'{d:+.1f} [{lo_:+.1f}, {hi_:+.1f}] ({a}:{b}, p={p:.3f})')
    return cells


def _sum_cells(cs, ws):
    got = [cs[w] for w in ws if cs.get(w) is not None]
    if len(got) < len(ws):
        return None
    return sum(g[0] for g in got), sum(g[1] for g in got), sum(g[2] for g in got)


_hdr_sets = ' | '.join(['heavy(판정)', 'mix4', 'mix5', 'mix6', 'mix7'])
M_OUT = ['# 모델·구성 × 시험 세트 행렬', '',
         f'생성: eval_final_all.py --matrix (mix8+mix9={tot_n}문제). 칸 = 정답 수/문제 수, 「—」= 그 세트에서 안 잼. ',
         '**개발 5세트**(heavy 판정 88·mix4 88·mix5 88·mix6 130·mix7 173)는 앞단 문턱·τ·게이트 문턱을 고른 세트라 **조합의 개발 칸 값은 낙관적**이다(직접 짚기는 고른 것이 없어 낙관 없음). **판정은 시험 세트 mix8·mix9 의 336문제**.',
         '「26B 대비」·「Jev 대비」= 짝지은 차이 %p [95% 구간] (그 줄만 맞음 : 기준만 맞음, 정확검정 p). 기준: Gemma 4 26B 직접(311/336) · Jev 직접(319/336).', '']

# ---- 표 1: 직접 짚기
M_OUT += ['## 표 1. 직접 짚기 — 모델 하나가 규칙·앞단 없이 풀었을 때', '',
          '| 모델 | 크기·저장·활성 | 서버·방식 | 질문당 | ' + _hdr_sets + ' | 개발 합 | mix8 | mix9 | **시험 합 336** | 엉뚱한 답 | 26B 대비 | Jev 대비 |',
          '|---|---|---|---:|' + '---:|' * 5 + '---:|---:|---:|---:|---:|---|---|']
for nm, sz, srv, tm, fn in _DIRECT:
    cs = {w: _cell(fn(w), w) for w in _ALL}
    dv = _sum_cells(cs, _DEV)
    ts = _sum_cells(cs, EV)
    vec = None
    if ts is not None:
        vec = [int(fn(w)[i] == gold[w][i]) for w in EV for i in range(len(gold[w]))]
    cells = [(f'{cs[w][0]}/{cs[w][1]}' if cs.get(w) else '—') for w in _DEV]
    ev_cells = [(f'{cs[w][0]}/{cs[w][1]}' if cs.get(w) else '—') for w in EV]
    p26, pj = (_fmt_pair(vec) if vec is not None else ['—', '—'])
    M_OUT.append(f'| {nm} | {sz} | {srv} | {tm} | ' + ' | '.join(cells) + ' | ' + (f'{dv[0]}/{dv[1]}' if dv else '—') + ' | ' + ' | '.join(ev_cells) +
                 ' | ' + (f'**{ts[0]}** ({ts[0] / ts[1]:.1%})' if ts else '—') + ' | ' + (str(ts[2]) if ts else '—') + f' | {p26} | {pj} |')

# ---- 표 2: 조합
M_OUT += ['', '## 표 2. 조합 — 규칙(코드) · 학습 앞단 · 분류 게이트 · 여러 모델을 이은 구성', '',
          '| 구성 | LLM 호출(시험 336) | ' + _hdr_sets + ' | 개발 합 | mix8 | mix9 | **시험 합 336** | 엉뚱한 답 | 26B 대비 | Jev 대비 |',
          '|---|---:|' + '---:|' * 5 + '---:|---:|---:|---:|---:|---|---|']
_rows2 = []
for n in names:
    cs = {}
    for w in _DEV:
        try:
            ok = bad = 0
            for i in idx_of(w):
                p, _c = P[n](w, i)
                g = SETS[w]['qs'][i]['gold']
                ok += p == g
                bad += p is not None and p != g
            cs[w] = (ok, len(idx_of(w)), bad)
        except Exception:  # noqa: BLE001
            cs[w] = None
    for w in EV:
        ok = sum(res[w][n][i][0] == gold[w][i] for i in range(len(gold[w])))
        bad = sum(res[w][n][i][0] is not None and res[w][n][i][0] != gold[w][i] for i in range(len(gold[w])))
        cs[w] = (ok, len(gold[w]), bad)
    dv = _sum_cells(cs, _DEV)
    ts = _sum_cells(cs, EV)
    calls = sum(res[w][n][i][1] for w in EV for i in range(len(gold[w])))
    vec = [int(res[w][n][i][0] == gold[w][i]) for w in EV for i in range(len(gold[w]))]
    p26, pj = _fmt_pair(vec)
    cells = [(f'{cs[w][0]}/{cs[w][1]}' if cs.get(w) else '—') for w in _DEV]
    ev_cells = [f'{cs[w][0]}/{cs[w][1]}' for w in EV]
    _rows2.append((ts[0], f'| {n} | {calls} | ' + ' | '.join(cells) + ' | ' + (f'{dv[0]}/{dv[1]}' if dv else '—') + ' | ' + ' | '.join(ev_cells) +
                   f' | **{ts[0]}** ({ts[0] / ts[1]:.1%}) | {ts[2]} | {p26} | {pj} |'))
for _, line in sorted(_rows2, key=lambda x: -x[0]):
    M_OUT.append(line)

# ---- 26B(Gemma 4) 를 이긴 경우 — 기준 정답 수는 이번 합계에서 센다
_t26 = sum(_v26) if _v26 is not None else None
M_OUT += ['', f'## 표 3. 목표 점검 — Gemma 4 26B 직접({_t26}/{tot_n})을 점추정으로 넘은 구성과, 26B 와 통계로 구분된 구성', '',
          '「구분됨」 = 짝지은 차이의 95% 구간이 0 을 포함하지 않고 정확검정 p<0.05(비교가 많아 보정 기준은 p<0.001 안팎). 활성·저장은 표 1 의 부품 기준.', '',
          f'| 구성 | 합 {tot_n} | 26B 대비 %p [구간] (그 줄만 : 26B 만, p) | 판정 |', '|---|---:|---|---|']
_cand = []
for nm, _s, _v, _t, fn in _DIRECT:
    pk = [fn(w) for w in EV]
    if any(x is None for x in pk) or nm.startswith('Gemma 4 26B'):
        continue
    vec = [int(pk[k][i] == gold[w][i]) for k, w in enumerate(EV) for i in range(len(gold[w]))]
    _cand.append(('직접 · ' + nm, vec))
for n in names:
    vec = [int(res[w][n][i][0] == gold[w][i]) for w in EV for i in range(len(gold[w]))]
    _cand.append(('조합 · ' + n, vec))
_lower_sig = []
if _v26 is not None:
    for nm, vec in sorted(_cand, key=lambda x: -sum(x[1])):
        s_ = sum(vec)
        d, lo_, hi_, a, b, p = _pair(vec, _v26)
        if d < 0 and hi_ < 0 and p < 0.05:
            _lower_sig.append((nm, s_, d, lo_, hi_, a, b, p))
        if s_ <= _t26:
            continue
        verdict = ('구분됨(p<0.05, 보정 기준 0.001 은 ' + ('통과' if p < 0.001 else '미달') + ')') if (lo_ > 0 and p < 0.05) else '점추정만 높음 — 26B 와 구분되지 않음'
        M_OUT.append(f'| {nm} | {s_} | {d:+.1f} [{lo_:+.1f}, {hi_:+.1f}] ({a} : {b}, p={p:.3f}) | {verdict} |')
    _same = [(nm, sum(vec)) for nm, vec in _cand if sum(vec) <= _t26 and not any(nm == x[0] for x in _lower_sig)]
    M_OUT += ['', f'26B 와 같거나 낮지만 **구분되지는 않는** 구성 {len(_same)}개(예: ' + ', '.join(f'{n}({v})' for n, v in sorted(_same, key=lambda x: -x[1])[:6]) + ')는 표 1·2 에 있다.', '',
              f'**26B 보다 통계로 구분되게 낮은 구성**(p<0.05) {len(_lower_sig)}개:', '', '| 구성 | 합 | 26B 대비 %p [구간] (그 줄만 : 26B 만, p) |', '|---|---:|---|']
    for nm, s_, d, lo_, hi_, a, b, p in _lower_sig:
        M_OUT.append(f'| {nm} | {s_} | {d:+.1f} [{lo_:+.1f}, {hi_:+.1f}] ({a} : {b}, p={p:.3f}) |')
open(argv0[argv0.index('--matrix') + 1], 'w', encoding='utf-8').write('\n'.join(M_OUT) + '\n')
print('행렬 표 저장:', argv0[argv0.index('--matrix') + 1])
