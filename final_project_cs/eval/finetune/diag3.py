import json
with open(r'E:\hf_cache\hub\models--Qwen--Qwen2.5-7B-Instruct\blobs\07bfe0640cb5a0037f9322287fbfc682806cf672', encoding='utf-8') as f:
    cfg = json.load(f)
print(list(cfg.keys()))
print('pad_token' in cfg, cfg.get('pad_token'))
print('eos_token' in cfg, cfg.get('eos_token'))
print('has chat_template', 'chat_template' in cfg)
