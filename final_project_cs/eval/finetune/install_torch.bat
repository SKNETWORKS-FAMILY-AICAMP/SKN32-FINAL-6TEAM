@echo off
mkdir E:\tmp 2>nul
set TEMP=E:\tmp
set TMP=E:\tmp
E:\dod28_ft\venv312\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128 --force-reinstall --no-deps
