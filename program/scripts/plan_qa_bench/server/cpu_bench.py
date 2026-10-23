# 서버에서: GPU 없는 배포 가능성 1차 측정 — llama-server 를 CPU 4코어(taskset)·GPU 끔으로 띄우고, 실제 일정 질문 프롬프트(일정 전체 + 고객 질문)로 시간을 잰다.
#  재는 것: ① 처음 질문(일정 전체를 읽는 프롬프트 처리) 시간 ② 같은 일정에서 다음 질문(일정 앞부분이 캐시에 있을 때) 시간 ③ 생성 속도.
#  llama-server 응답의 timings(prompt_n · cache_n · prompt_ms · predicted_per_second)를 그대로 읽는다. 이 서버 CPU 는 x86 이라 ARM 4코어(Neoverse N1 급)보다 빠르다 → 결과는 「상한」이다.
# 사용: python cpu_bench.py <GGUF 경로> [코어 범위=60-63] [스레드=4]   → cpu_bench_<모델>.json
import json, os, subprocess, sys, time, urllib.request
from datetime import date

GGUF = sys.argv[1]
CORES = sys.argv[2] if len(sys.argv) > 2 else '60-63'
THREADS = sys.argv[3] if len(sys.argv) > 3 else '4'
PORT = 8160
W = '월화수목금토일'
job = json.load(open('mix11.json', encoding='utf-8'))['sets']['mix11']
items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
days = sorted({i['date'] for i in items})


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


head = f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n" + '\n'.join(lab(i) for i in items) + '\n\n'
env = dict(os.environ, CUDA_VISIBLE_DEVICES='')
srv = subprocess.Popen(['taskset', '-c', CORES, '/root/llama.cpp/build/bin/llama-server', '-m', GGUF, '-t', THREADS, '-ngl', '0', '-c', '4096', '-np', '1', '--port', str(PORT), '--host', '127.0.0.1'],
                       env=env, stdout=open('/root/cpu_server.log', 'w'), stderr=subprocess.STDOUT)


def post(body):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/completion', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=1800))


t0 = time.time()
for _ in range(300):
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=3)
        break
    except Exception:  # noqa: BLE001
        time.sleep(3)
load_s = time.time() - t0
rows = []
qs = [x for x in job['qs'][:8]]
for k, x in enumerate(qs):
    text = head + f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. 없으면 null. 출력 형식: " + '{"item": 번호 또는 null}'
    t1 = time.time()
    r = post({'prompt': text, 'n_predict': 12, 'temperature': 0, 'cache_prompt': True})
    wall = time.time() - t1
    tm = r.get('timings', {})
    rows.append({'q': k, 'wall_s': round(wall, 2), 'prompt_n': tm.get('prompt_n'), 'cache_n': tm.get('cache_n'), 'prompt_ms': tm.get('prompt_ms'), 'pp_tok_s': tm.get('prompt_per_second'),
                 'predicted_n': tm.get('predicted_n'), 'tg_tok_s': tm.get('predicted_per_second')})
srv.terminate()
rss = None
cold, warm = rows[0], rows[1:]
summ = {'model': os.path.basename(GGUF), 'size_gb': round(os.path.getsize(GGUF) / 1e9, 1), 'cores': CORES, 'threads': THREADS, 'load_s': round(load_s, 1),
        'cold_wall_s': cold['wall_s'], 'cold_prompt_tokens': cold['prompt_n'], 'pp_tok_s': round(cold['pp_tok_s'] or 0, 1),
        'warm_wall_s_mean': round(sum(r['wall_s'] for r in warm) / len(warm), 2), 'warm_new_tokens_mean': round(sum((r['prompt_n'] or 0) for r in warm) / len(warm)),
        'warm_cached_tokens_mean': round(sum((r['cache_n'] or 0) for r in warm) / len(warm)), 'tg_tok_s': round(sum((r['tg_tok_s'] or 0) for r in warm) / len(warm), 1)}
json.dump({'summary': summ, 'rows': rows}, open(f"cpu_bench_{os.path.basename(GGUF)}.json", 'w', encoding='utf-8'), ensure_ascii=False)
print(json.dumps(summ, ensure_ascii=False))
