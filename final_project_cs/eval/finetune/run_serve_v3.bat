@echo off
set HF_HOME=E:\hf_cache
set TEMP=E:\tmp
set TMP=E:\tmp
set FT_BASE_MODEL=Qwen/Qwen2.5-3B-Instruct
set FT_ADAPTER_DIR=E:\dod28_ft\ckpt_stage3_v3
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128,garbage_collection_threshold:0.8
cd /d E:\dod28_ft
E:\dod28_ft\venv312\Scripts\python.exe -u serve.py --host 127.0.0.1 --port 8100 > E:\dod28_ft\serve_v3.log 2>&1
