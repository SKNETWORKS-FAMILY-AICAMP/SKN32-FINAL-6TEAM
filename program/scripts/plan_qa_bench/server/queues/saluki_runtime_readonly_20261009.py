"""Read installed GGUF loader capabilities without allocating model weights."""
import importlib.metadata as metadata
import json
from pathlib import Path
import transformers
import transformers.modeling_gguf_pytorch_utils as gguf_utils

versions = {}
for package in ('torch', 'transformers', 'peft', 'bitsandbytes', 'gguf', 'kernels'):
    try:
        versions[package] = metadata.version(package)
    except metadata.PackageNotFoundError:
        versions[package] = None
root = Path(transformers.__file__).parent
matches = []
paths = list((root / 'quantizers').glob('*gguf*')) + [Path(gguf_utils.__file__)]
for path in paths:
    source = path.read_text()
    matches.append({'file': str(path), 'qwen35_literal': 'qwen3_5' in source or 'qwen35' in source,
                    'trainable_lines': [line.strip() for line in source.splitlines()
                                        if 'is_trainable' in line or 'return False' in line or 'MPS' in line]})
print(json.dumps({'versions': versions, 'supported': getattr(gguf_utils, 'GGUF_SUPPORTED_ARCHITECTURES', None),
                  'loader_files': matches, 'model_allocation': False}))
