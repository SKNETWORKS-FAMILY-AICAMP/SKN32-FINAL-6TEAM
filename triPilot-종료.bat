@echo off
chcp 65001 >nul
call "%~dp0triPilot-실행.bat" stop
exit /b %ERRORLEVEL%
