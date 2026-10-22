@echo off
title Install Dependencies
color 0A

echo ========================================================
echo   Dianping Note Pipeline V4 - Environment Install
echo ========================================================
echo.

echo [1/2] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.9+ and check "Add to PATH".
    pause
    exit /b 1
)
python --version

echo.
echo [2/2] Installing packages (Pillow / requests / websocket / numpy / opencv)...
python -m pip install -r "%~dp0requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo [RETRY] Tsinghua mirror failed, switching to default index...
    python -m pip install -r "%~dp0requirements.txt"
)
if %errorlevel% neq 0 (
    echo [ERROR] Install failed. Check your network and run this file again.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   Done. Next: double-click the self-check file.
echo ========================================================
pause
