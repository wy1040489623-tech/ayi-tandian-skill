@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title 环境自检
python "%~dp0check_env.py"
echo.
pause
