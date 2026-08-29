@echo off
set HF_HOME=E:\hf_cache
"C:\Users\Yeon\AppData\Local\Programs\Python\Python314\python.exe" E:\dod28_ft\train.py --stage 1 --data E:\dod28_ft\sft_stage1.jsonl --base Qwen/Qwen2.5-7B-Instruct --out E:\dod28_ft\ckpt_stage1 > E:\dod28_ft\stage1.log 2>&1
echo DONE_EXIT_%ERRORLEVEL% >> E:\dod28_ft\stage1.log
