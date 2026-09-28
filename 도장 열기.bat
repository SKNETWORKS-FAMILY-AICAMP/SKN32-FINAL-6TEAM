@echo off
REM A-COP 학습 도장 — 더블클릭하면 서버가 뜨고 브라우저가 열린다.
REM 창을 닫으면 서버도 닫힌다.
chcp 65001 > nul
cd /d "%~dp0"
echo 도장 서버를 띄웁니다. 이 창을 닫으면 서버도 닫힙니다.
python dojo.py serve --port 8765
pause
