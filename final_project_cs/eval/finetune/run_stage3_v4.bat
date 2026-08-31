@echo off
set HF_HOME=E:\hf_cache
set TEMP=E:\tmp
set TMP=E:\tmp
set PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128,garbage_collection_threshold:0.8
E:\dod28_ft\venv312\Scripts\python.exe -u E:\dod28_ft\train.py --stage 3 --data E:\dod28_ft\sft_stage3_train_v3.jsonl --base E:\dod28_ft\ckpt_stage2 --out E:\dod28_ft\ckpt_stage3_v4 --epochs 4 --max_length 11264 > E:\dod28_ft\stage3_v4.log 2>&1
echo DONE_EXIT_%ERRORLEVEL% >> E:\dod28_ft\stage3_v4.log
