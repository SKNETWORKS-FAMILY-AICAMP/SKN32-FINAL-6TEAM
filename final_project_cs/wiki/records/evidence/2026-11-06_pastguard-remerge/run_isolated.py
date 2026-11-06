"""DB-free isolated pytest runner for the pastguard-final-20261106 worktree.

Blocks socket connect/connect_ex/bind/listen (except the exact stdlib Windows socketpair self-pipe),
socket.create_connection and psycopg.connect / psycopg.Connection.connect. Synthetic unit settings only.
"""
import inspect
import os
import socket
import sys
from pathlib import Path

W = Path(r'C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106')
for key in [k for k in os.environ if k.startswith('ACOP_')] + ['TEST_DATABASE_URL']:
    os.environ.pop(key, None)
os.environ.update(
    ACOP_DATABASE_URL='postgresql://unit:unit@127.0.0.1:1/unit', ACOP_OPENAI_API_KEY='unit-placeholder-key',
    ACOP_LLM_MODEL='unit-placeholder-model', ACOP_EMBEDDING_MODEL='unit-placeholder-embed', ACOP_TENANT_ID='demo',
    ACOP_SECRET_KEY='unit-placeholder-secret-0123456789abcdef', ACOP_COMPOSER_JWT_SECRET='unit-placeholder-composer-0123456789abcdef',
    ACOP_COMPOSER_ISSUER_SECRET='unit-placeholder-issuer-0123456789abcdef', ACOP_LLM_PROVIDER='mock',
    PYTHONDONTWRITEBYTECODE='1', TIKTOKEN_CACHE_DIR=r'C:/Users/kcxsz/AppData/Local/Temp/data-gym-cache',
    TMP=str(W / 'tmp'), TEMP=str(W / 'tmp'))
(W / 'tmp').mkdir(exist_ok=True)
root = W / 'wt' / 'final_project_cs'
print('pastguard-final runner root:', root, flush=True)
os.chdir(root)
sys.path.insert(0, str(root))
sys.path.append(str(root.parent / 'final_project_sample'))
os.environ['PATH'] = str(W / 'mingit' / 'cmd') + os.pathsep + os.environ['PATH']


def denied(*a, **kw):
    raise RuntimeError('pastguard-final isolated runner: network/database denied')


for method in ('connect', 'connect_ex', 'bind', 'listen'):
    original = getattr(socket.socket, method)

    def guarded(self, *args, _original=original, **kwargs):
        if inspect.currentframe().f_back.f_code is socket._fallback_socketpair.__code__:
            return _original(self, *args, **kwargs)
        return denied()

    setattr(socket.socket, method, guarded)
socket.create_connection = denied
import psycopg  # noqa: E402

psycopg.connect = denied
psycopg.Connection.connect = classmethod(lambda cls, *a, **k: denied())
import pytest  # noqa: E402

raise SystemExit(pytest.main(sys.argv[1:]))
