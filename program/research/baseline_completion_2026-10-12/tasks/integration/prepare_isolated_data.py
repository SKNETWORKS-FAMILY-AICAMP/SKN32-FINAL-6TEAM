"""이미 수집된 공개 원자료만 새 시험 클러스터에 적재한다. 업무 DB 연결은 호출자가 차단한다."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
_rag_context = None


def prepare(root, run, connect, dsn, save):
    source = root / 'datasets/dining/processed'
    build = run / 'dining-build'
    build.mkdir()
    scripts = root / 'final_project_cs/scripts/dining'
    sys.path.insert(0, str(scripts))
    inputs = [source/'tourapi_음식점_소개정보.json', source/'tourapi_서울_음식점_목록.json',
              *sorted((source/'vegan').glob('*.csv'))]
    before = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    old_argv = sys.argv
    try:
        sys.argv = ['isolated-dining-data']
        for name in ('parse_hours', 'make_load_sql', 'make_vegan_sql'):
            spec = importlib.util.spec_from_file_location(name, scripts/(name+'.py'))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.OUT = str(build)
            mod.DATA = str(source/'vegan' if name == 'make_vegan_sql' else source)
            mod.main()
    finally:
        sys.argv = old_argv
    with connect(dsn) as conn:
        for name in ('load_200.sql', 'vegan.sql'):
            conn.execute((build/name).read_text(encoding='utf-8'))
        counts = dict(conn.execute('SELECT \'places\', count(*) FROM dining.dn_place '
                                  'UNION ALL SELECT \'hours\', count(*) FROM dining.dn_hours_rule '
                                  'UNION ALL SELECT \'attributes\', count(*) FROM dining.dn_attribute').fetchall())
    after = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    assert before == after
    save('dining-data.json', dict(scope='TourAPI 목록·소개, 비건 근거; 전체 원장 재구축 아님',
         inputs=before, counts=counts, raw_unchanged=True,
         generated={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in build.iterdir() if p.is_file()}))
    from app.domains.travel_ops.instances.mobility.engine import paths
    paths.configure(root/'datasets/mobility/processed', source='isolated_actual_data')
    save('mobility-data.json', {'processed':str(paths.PROCESSED.relative_to(root)), 'source':paths.SOURCE})
    import os
    if os.environ.get('ACOP_INTEGRATION_EMBEDDINGS'):
        prepare_rag(root, run, save, Path(os.environ['ACOP_INTEGRATION_EMBEDDINGS']))


def prepare_rag(root, run, save, artifact):
    """실제 원본 BGE 계산 결과를 로컬 HTTP 호환 전송으로 적재·검색한다. Ollama 실행 검증은 아니다."""
    import os, threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from knowledge.ingest import load_corpus
    cs = root/'final_project_cs'
    prepared=json.loads(artifact.read_text(encoding='utf-8'))
    vectors=prepared['vectors_by_text_sha256']
    for doc in load_corpus(cs/'knowledge/travel/manifest.json'):
        for section in doc.sections:
            key=hashlib.sha256(section.content.encode()).hexdigest()
            assert key in vectors, (doc.frontmatter['document_id'],section.number,'실제 계산 벡터 누락')
    global _rag_context
    calls=[]
    failures=[]
    class Provider(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            try:
                assert self.path=='/api/embed'
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                assert body['model']=='bge-m3'
                texts=body['input'] if isinstance(body['input'],list) else [body['input']]
                keys=[hashlib.sha256(text.encode()).hexdigest() for text in texts]
                payload=json.dumps({'embeddings':[vectors[key] for key in keys]}).encode()
                calls.extend(keys)
                self.send_response(200)
            except Exception as error:
                failures.append(type(error).__name__)
                payload=json.dumps({'error':type(error).__name__}).encode(); self.send_response(422)
            self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload)
    http=ThreadingHTTPServer(('127.0.0.1',0),Provider)
    threading.Thread(target=http.serve_forever,daemon=True).start()
    _rag_context=(http,calls,failures)
    os.environ.update(ACOP_EMBEDDING_PROVIDER='ollama',ACOP_OLLAMA_EMBEDDING_MODEL='bge-m3',
                      ACOP_OLLAMA_BASE_URL=f'http://127.0.0.1:{http.server_port}')
    from app.core.settings import get_settings
    get_settings.cache_clear()
    from app.infrastructure.db.session import get_connection
    with get_connection() as conn:
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES('demo','Isolated travel corpus test tenant') ON CONFLICT DO NOTHING")
    import scripts.ingest_corpus_local as ingest
    old=sys.argv
    try:
        sys.argv=['isolated-local-ingest','--manifest','knowledge/travel/manifest.json']
        assert ingest.main()==0
    finally: sys.argv=old
    save('rag-data.json',{'embedding_artifact':str(artifact.relative_to(root)),
          'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'model':prepared['model'],
          'transport':'task-owned HTTP compatibility adapter; actual precomputed BGE-M3 vectors; not Ollama runtime',
          'calls_at_ingest':len(calls),'business_database':False})


def finish_rag(save):
    global _rag_context
    if _rag_context is not None:
        http,calls,failures=_rag_context
        http.shutdown()
        http.server_close()
        save('rag-transport-final.json', {'successful_text_requests':len(calls),
             'distinct_text_sha256':sorted(set(calls)), 'failed_requests':failures,
             'task_owned_adapter_stopped':True, 'ollama_runtime_verified':False})
        _rag_context=None
