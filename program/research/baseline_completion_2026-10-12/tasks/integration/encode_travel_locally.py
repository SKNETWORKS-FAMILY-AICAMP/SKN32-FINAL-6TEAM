"""고정한 공개 원본 BGE-M3로 실제 여행 본문을 로컬 CPU에서 임베딩한다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast
import hashlib
import json
import os
import sys

os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
root = Path(__file__).resolve().parents[5]
cs = root/'final_project_cs'
sys.path.insert(0, str(cs))
from knowledge.ingest import load_corpus
base = root/'datasets/travel/baseline_completion_20261012'
manifest = base/'model/model-manifest.json'
identity = json.loads(manifest.read_text())
model_path = base/'model/bge-m3'
assert 'pytorch_model.bin' in identity['files']
def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024), b''):
            value.update(block)
    return value.hexdigest()
assert digest(model_path/'pytorch_model.bin') == identity['files']['pytorch_model.bin']
documents = load_corpus(cs/'knowledge/travel/manifest.json')
def corpus_hashes():
    return {str((cs/'knowledge/travel'/d.manifest['file']).relative_to(root)):digest(cs/'knowledge/travel'/d.manifest['file']) for d in documents}
before = corpus_hashes()
texts = [s.content for d in documents for s in d.sections]
# 실제 호출 문자열은 테스트 AST와 일정 생성기의 질의 조립 결과에서 수집한다.
test = cs/'tests/integration/rag/test_travel_corpus_retrieval.py'
for node in ast.walk(ast.parse(test.read_text(encoding='utf-8'))):
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and any('\uac00' <= c <= '\ud7a3' for c in node.value):
        texts.append(node.value)
from datetime import date
from app.domains.travel_ops.components.planning.planner import PlanRequest
import inspect
from app.domains.travel_ops.components.planning import planner
# ground_request를 실제 호출하되 검색 입구에서 구성된 질의를 수집한다. 벡터는 아래 원본 모델이 계산한다.
def collect(*args, **kwargs):
    texts.append(args[1] if len(args)>1 else kwargs['query'])
    return []
for preference in ['비가 오면 야외 활동은 어떻게 되나요','아이 동반이라 유모차로 다닐 수 있는 곳이 좋아요',
                   '지하철이 멈추면 다음 예약은 어떻게 되나요','노트북 보증 기간과 수리비가 궁금해요']:
    planner.ground_request(tenant_id='demo', search=collect, request=PlanRequest(city='서울',start_date=date(2026,10,5),days=2,party_size=2,preferences=preference))
texts = list(dict.fromkeys(texts))
prior = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')) if len(sys.argv)>1 else None
if prior:
    assert prior['model']==identity and prior['additional_training'] is False
vectors = dict(prior['vectors_by_text_sha256']) if prior else {}
reference_text = next((text for text in texts if hashlib.sha256(text.encode()).hexdigest() in vectors), None)
texts = [text for text in texts if hashlib.sha256(text.encode()).hexdigest() not in vectors]
if reference_text:
    texts.append(reference_text)
print('missing_actual_vectors',len(texts),'cached',len(vectors),flush=True)
import torch
from transformers import AutoTokenizer, AutoConfig, XLMRobertaModel
torch.set_num_threads(4)
tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
# 메모리 여유가 적을 때의 로더: 원본 FP32를 읽은 뒤 텐서마다 FP16 로 바꿔 끼우고,
# 모델 뼈대는 빈(meta) 텐서로 만들어 가중치 복사본을 따로 두지 않는다.
# 표준 로더(FP32 전체 + FP16 모델 동시 보유, 약 3.4GB 예상)보다 최대 사용량이 약 0.6GB 낮다(예상).
# 결과 동일성은 아래 reference_text 재계산(코사인 > 0.99999)으로 확인한다. mmap 읽기는 Windows 에서 죽어 쓰지 않는다.
config = AutoConfig.from_pretrained(model_path, local_files_only=True)
assert config.model_type == 'xlm-roberta', config.model_type
state = torch.load(model_path/'pytorch_model.bin', map_location='cpu', mmap=False, weights_only=True)
for key in list(state):
    tensor = state.pop(key)
    if key.startswith('pooler.'):
        continue  # CLS 벡터만 쓰므로 pooler 는 만들지 않는다.
    state[key] = tensor.half() if tensor.is_floating_point() else tensor
    del tensor
with torch.device('meta'):
    model = XLMRobertaModel(config, add_pooling_layer=False)
result = model.load_state_dict(state, strict=False, assign=True)
assert not result.missing_keys, result.missing_keys
assert set(result.unexpected_keys) <= {'embeddings.position_ids'}, result.unexpected_keys
del state
# 저장 대상이 아닌 위치 버퍼는 원래 정의대로 다시 만든다.
positions = torch.arange(config.max_position_embeddings).expand((1, -1))
model.embeddings.register_buffer('position_ids', positions.clone(), persistent=False)
if hasattr(model.embeddings, 'token_type_ids'):
    model.embeddings.register_buffer('token_type_ids', torch.zeros(positions.size(), dtype=torch.long), persistent=False)
assert not [n for n, t in list(model.named_parameters()) + list(model.named_buffers()) if t.is_meta]
print('loaded_original_weights_fp16_low_peak', flush=True)
model.eval()
with torch.inference_mode():
    for i, text in enumerate(texts):
        inputs = tokenizer(text,return_tensors='pt',truncation=False)
        assert inputs['input_ids'].shape[1] <= 8192
        output = model(**inputs).last_hidden_state[:,0]
        vector = torch.nn.functional.normalize(output.float(),p=2,dim=1)[0]
        assert len(vector)==1024 and torch.isfinite(vector).all()
        if text == reference_text:
            reference=torch.tensor(vectors[hashlib.sha256(text.encode()).hexdigest()])
            similarity=float(torch.nn.functional.cosine_similarity(vector,reference,dim=0))
            assert similarity>0.99999, ('loader_reference_mismatch',similarity)
            print('loader_reference_cosine',similarity,flush=True)
        vectors[hashlib.sha256(text.encode()).hexdigest()] = vector.tolist()
        if i%10==0: print('encoded',i+1,'/',len(texts),flush=True)
stamp=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')
out=base/('embeddings-'+stamp+'.json')
after = corpus_hashes()
assert before==after, '계산 중 원문 변경: 최신 문서로 다시 계산해야 함'
out.write_text(json.dumps({'model':identity,'additional_training':False,'provider':'local-transformers-CPU-fp16',
    'corpus':before, 'corpus_unchanged_during_encoding':True,
    'reused_artifact_sha256':digest(Path(sys.argv[1])) if prior else None,
    'vectors_by_text_sha256':vectors},ensure_ascii=False)+'\n',encoding='utf-8')
print('saved',out.relative_to(root),len(vectors),flush=True)
