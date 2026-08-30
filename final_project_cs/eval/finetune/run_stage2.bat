@echo off
set HF_HOME=E:\hf_cache
set TEMP=E:\tmp
set TMP=E:\tmp
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128,garbage_collection_threshold:0.8
E:\dod28_ft\venv312\Scripts\python.exe -u E:\dod28_ft\train.py --stage 2 --data E:\dod28_ft\sft_stage2.jsonl --base E:\dod28_ft\ckpt_stage1 --out E:\dod28_ft\ckpt_stage2 > E:\dod28_ft\stage2.log 2>&1
echo DONE_EXIT_%ERRORLEVEL% >> E:\dod28_ft\stage2.log
