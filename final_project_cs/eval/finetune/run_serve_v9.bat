@echo off
set HF_HOME=E:\hf_cache
set TEMP=E:\tmp
set TMP=E:\tmp
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128,garbage_collection_threshold:0.8
set FT_ADAPTER_DIR=E:\dod28_ft\ckpt_stage3_v9
E:\dod28_ft\venv312\Scripts\python.exe -u E:\dod28_ft\serve.py --port 8100 > E:\dod28_ft\serve_v9.log 2>&1
