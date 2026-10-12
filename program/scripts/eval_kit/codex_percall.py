# Codex CLI(gpt-6-luna · gpt-6-sol)를 **문제마다 한 번씩** 부르는 공용 도구 — 구독으로 쓰는 CLI 라 API 호출이 아니다(유료 Jev API 는 쓰지 않는다).
#  codex exec --output-schema 로 JSON 형식을 강제하고 -o 파일로 답을 받는다(읽기 전용 · 대화 저장 안 함). 시간을 재고 실패는 한 번 다시 부른다.
#  ★CLI 한 번 = 도구를 갖춘 에이전트 세션 하나라 API 직접 호출보다 느리다(시작·추론 오버헤드) — 지연은 「CLI 기준」으로만 읽는다.
#  ★OpenAI 구조화 출력 규칙: 모든 객체에 additionalProperties=false · 속성은 전부 required — `strictify` 가 맞춰 준다(maxItems 등 지원 안 될 수 있는 키워드는 뺀다).
import json
import os
import shutil
import subprocess
import tempfile
import time

CODEX = shutil.which('codex')
DROP = {'maxItems', 'minItems', 'minLength', 'maxLength', 'minimum', 'maximum', 'default'}


def strictify(schema):
    if isinstance(schema, dict):
        out = {k: strictify(v) for k, v in schema.items() if k not in DROP}
        if out.get('type') == 'object' and 'properties' in out:
            out['additionalProperties'] = False
            out['required'] = list(out['properties'])
        return out
    if isinstance(schema, list):
        return [strictify(x) for x in schema]
    return schema


def call(model, prompt, schema, work=None, timeout=600, retries=1):
    """(값 dict 또는 None, 걸린 초, 오류 문구). schema 는 strictify 를 거쳐 파일로 넘긴다."""
    work = work or tempfile.mkdtemp(prefix='codex_pc_')
    os.makedirs(work, exist_ok=True)
    uid = f'{os.getpid()}_{time.time_ns()}'
    sp, of, pf = (os.path.join(work, f'{uid}.{s}') for s in ('schema.json', 'out.json', 'prompt.md'))
    json.dump(strictify(schema), open(sp, 'w', encoding='utf-8'))
    open(pf, 'w', encoding='utf-8').write(prompt)
    err = None
    t0 = time.perf_counter()
    for attempt in range(retries + 1):
        try:
            with open(pf, 'rb') as fin:
                r = subprocess.run([CODEX, 'exec', '--skip-git-repo-check', '-s', 'read-only', '--ephemeral', '-C', work, '--output-schema', sp, '-o', of, '-m', model, '-'],
                                   stdin=fin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            if os.path.exists(of) and os.path.getsize(of) > 0:
                val = json.loads(open(of, encoding='utf-8').read())
                for f in (sp, of, pf):
                    try:
                        os.remove(f)
                    except OSError:
                        pass
                return val, time.perf_counter() - t0, None
            err = f'rc={r.returncode} {(r.stderr or b"")[-200:].decode("utf-8", "replace")}'
        except subprocess.TimeoutExpired:
            err = 'timeout'
        except Exception as e:  # noqa: BLE001
            err = f'{type(e).__name__}: {str(e)[:100]}'
    return None, time.perf_counter() - t0, err


class CodexChat:
    """decision_unit.decide 가 부르는 `chat.structured(system, user, schema, num_predict=…)` 모양을 흉내 낸다."""

    def __init__(self, model, work=None):
        self.model, self.work = model, work
        self.last_error = None

    def structured(self, system, user, schema, *, num_predict=160):
        val, sec, err = call(self.model, f'{system}\n\n---\n{user}\n\n위 지시대로 JSON 한 개로만 답하라. 파일을 만들거나 명령을 실행하지 마라.', schema, self.work)
        if val is None:
            from app.infrastructure.ollama_chat import OllamaError
            raise OllamaError(f'codex 호출 실패: {err}')
        return val
