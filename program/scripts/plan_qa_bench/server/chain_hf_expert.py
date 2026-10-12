# 서버에서: 「가르친 Winnow-E4B(Jev 계열 모델 Winnow-E4B 에 우리 데이터로 QLoRA 학습)」를 한 줄 연결 시험(chain_e2e.py)에서 실제로 호출할 수 있게 작은 HTTP 서버로 띄운다.
#  서버 B 의 평가 하네스(qlora_eval2.py)와 똑같이 불러 쓴다 — HF 4비트(NF4, 이중 양자화, 계산 bf16) + LoRA 어댑터, 대화 틀 적용, 탐욕 생성 최대 12토큰, 확신도 = 답 토큰 확률의 곱.
#  (GGUF 로 합쳐 바꾸려면 합친 가중치 16GB 와 GGUF 8GB 를 둘 자리가 서버 C 에 없어서 하지 않았다 — 그래서 이 서버가 서버 B 하네스와 같은 가중치·같은 계산을 쓴다는 점이 장점이다.)
#  llama-server 의 /v1/chat/completions 와 같은 모양으로 답한다: {"choices":[{"message":{"content": 문자열}}], "x_conf": 확신도, "x_ms": 서버 안 계산 시간}.
# 사용: python chain_hf_expert.py <모델폴더> <어댑터폴더> <포트>
import json
import math
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODEL, ADAPTER, PORT = sys.argv[1], sys.argv[2], int(sys.argv[3])
tok = AutoTokenizer.from_pretrained(MODEL)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb, dtype=torch.bfloat16, device_map={'': 0})
model = PeftModel.from_pretrained(model, ADAPTER).eval()
LOCK = threading.Lock()
print('모델 준비 끝 · GPU 메모리', round(torch.cuda.memory_allocated() / 1e9, 2), 'GB', flush=True)


def solve(prompt):
    p = tok.apply_chat_template([{'role': 'user', 'content': prompt}], add_generation_prompt=True, tokenize=False)
    ids = tok(p, add_special_tokens=False, return_tensors='pt').to('cuda')
    t0 = time.perf_counter()
    with torch.inference_mode():
        g = model.generate(**ids, max_new_tokens=12, do_sample=False, output_scores=True, return_dict_in_generate=True)
    out = g.sequences
    s = tok.decode(out[0, ids['input_ids'].shape[1]:], skip_special_tokens=True)
    lp = 0.0
    for step, tid in enumerate(out[0, ids['input_ids'].shape[1]:]):
        if step >= len(g.scores):
            break
        lp += torch.log_softmax(g.scores[step][0].float(), -1)[tid].item()
        if tok.decode([tid.item()]).strip().endswith('}'):
            break
    return s, math.exp(lp), (time.perf_counter() - t0) * 1000


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n))
        prompt = body['messages'][-1]['content']
        with LOCK:
            s, conf, ms = solve(prompt)
        data = json.dumps({'choices': [{'message': {'content': s}}], 'x_conf': conf, 'x_ms': ms}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
