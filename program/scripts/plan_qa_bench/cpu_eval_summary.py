# 서버 B 에서 CPU 4코어로 푼 「가르친 E4B GGUF(Q8)」 결과(results/_pull/cpu/cpu_eval_e4bt_q8_<세트>.json)를 읽어
#  정확도(같은 769문제·요청 둘 포함 835 A 채점)와 질문당 시간(첫 질문 · 다음 질문의 평균/중앙값/95백분위)을 낸다. 새 호출 없음.
# 사용: python cpu_eval_summary.py [태그=e4bt_q8] > results/cpu_eval_summary.txt
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
TAG = sys.argv[1] if len(sys.argv) > 1 else 'e4bt_q8'
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
sys.stdout.reconfigure(encoding='utf-8')
FX = {s: json.load(open(fixture(f'{s}.json'), encoding='utf-8'))['sets'][s] for s in SETS}


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, math.ceil(p / 100 * len(v)) - 1)]


tot = ok_non = n_non = ok_all = n_all = errs = 0
warm_all, cold_all, new_tok, cache_tok, gen_ms = [], [], [], [], []
picks_all = {}
print(f'# CPU 4코어(GGUF Q8, 서버 B 의 AMD EPYC 7702 코어 4개, 다른 작업이 같은 기계에서 돌던 중) — 가르친 E4B 태그 {TAG}\n')
print(f'{"세트":<7}{"문제":>5}{"요청 둘 제외 맞음":>20}{"전체(A)":>11}{"읽기실패":>8}{"첫 질문(초)":>12}{"다음 질문 평균":>14}{"중앙값":>8}{"95%":>7}')
for s in SETS:
    f = os.path.join(HERE, f'results/_pull/cpu/cpu_eval_{TAG}_{s}.json')
    if not os.path.exists(f):
        print(f'{s}: 파일 없음')
        continue
    d = json.load(open(f, encoding='utf-8'))
    qs = FX[s]['qs']
    non = [i for i, q in enumerate(qs) if q['type'] != 'compound_intent']
    # 읽기 실패(빈 응답)는 null 로 기록돼 정답이 null 인 문제에서 우연히 맞게 세어진다 → 엄격히 틀린 것으로 센다
    good = lambda i: '"item"' in d['rows'][i]['raw'] and d['picks'][i] == qs[i]['gold']
    ok_n = sum(1 for i in non if good(i))
    ok_a = sum(1 for i in range(len(qs)) if good(i))
    warm = [r['wall_s'] for r in d['rows'][1:]]
    cold_all.append(d['rows'][0]['wall_s'])
    warm_all += warm
    new_tok += [r['prompt_n'] or 0 for r in d['rows'][1:]]
    cache_tok += [r['cache_n'] or 0 for r in d['rows'][1:]]
    gen_ms += [r['predicted_ms'] or 0 for r in d['rows'][1:]]
    tot += len(qs)
    n_non += len(non)
    ok_non += ok_n
    ok_all += ok_a
    n_all += len(qs)
    errs += d['_errors']
    for i in range(len(qs)):
        picks_all[(s, i)] = d['picks'][i]
    print(f'{s:<7}{len(qs):>5}{ok_n:>14}/{len(non):<5}{ok_a:>7}/{len(qs):<4}{d["_errors"]:>8}{d["rows"][0]["wall_s"]:>12.1f}{sum(warm) / len(warm):>14.2f}{sorted(warm)[len(warm) // 2]:>8.2f}{pct(warm, 95):>7.2f}')
if n_all:
    print(f'\n합계: 요청 둘 제외 {ok_non}/{n_non} = {100 * ok_non / n_non:.2f}% · 전체(A 채점) {ok_all}/{n_all} = {100 * ok_all / n_all:.2f}% · 읽기 실패 {errs}')
    print(f'첫 질문(일정 전체를 읽음) 평균 {sum(cold_all) / len(cold_all):.1f}초 ({", ".join(f"{c:.0f}" for c in cold_all)})')
    print(f'다음 질문(같은 일정, 캐시 맞음) 평균 {sum(warm_all) / len(warm_all):.2f}초 · 중앙값 {sorted(warm_all)[len(warm_all) // 2]:.2f} · 95백분위 {pct(warm_all, 95):.2f} · 최대 {max(warm_all):.1f} (n={len(warm_all)})')
    print(f'다음 질문 때 새로 읽은 토큰 평균 {sum(new_tok) / len(new_tok):.0f} · 캐시에서 쓴 토큰 평균 {sum(cache_tok) / len(cache_tok):.0f} · 생성에 쓴 시간 평균 {sum(gen_ms) / len(gen_ms) / 1000:.2f}초')
    # 하루 처리 가능 건수(한 대 24시간 100% 가동 가정): 다음 질문만 / 첫 질문 비율 f
    w = sum(warm_all) / len(warm_all)
    c = sum(cold_all) / len(cold_all)
    print('\n하루 처리 가능 건수 `[계산: 한 대 · 한 번에 한 질문 · 24시간 100% 가동 가정]`')
    for f_ in (0.0, 0.1, 0.2, 0.5, 1.0):
        avg = (1 - f_) * w + f_ * c
        print(f'  새 여행(첫 질문)이 {int(f_ * 100)}% 일 때 평균 {avg:.1f}초/건 → 하루 약 {86400 / avg:,.0f}건')
json.dump({f'{s}|{i}': v for (s, i), v in picks_all.items()}, open(os.path.join(HERE, f'results/cpu_eval_{TAG}_picks.json'), 'w'), ensure_ascii=False)
