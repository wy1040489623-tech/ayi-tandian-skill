@echo off
chcp 65001 >nul
title 阿一商铺笔记封面生成器 V4 - 一键生成工具

echo ========================================================
echo    🎨 阿一商铺笔记封面生成器 V4 (年轻白领松弛网感版)
echo    ⚡ 免配置 · 自包含 · 自动环境自愈
echo ========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python 环境！
    echo 请先安装 Python (https://www.python.org/downloads/)，安装时请勾选 "Add to PATH"。
    echo.
    pause
    exit /b
)

set "SCRIPT_DIR=%~dp0"
set "PY_SCRIPT=%SCRIPT_DIR%store_note_cover_generator_v4.py"

if not "%~1"=="" (
    echo [处理中] 正在为拖入的目录生成封面: "%~1"
    python "%PY_SCRIPT%" --folder "%~1"
    echo.
    echo [完成] 封面已生成完毕！
    pause
    exit /b
)

echo 【使用说明】
echo 1. 你可以直接把【商铺文件夹】拖拽到本 bat 文件图标上，即可自动秒生成封面！
echo 2. 或者在下方直接粘贴商铺文件夹路径（或父目录路径）：
echo.
set /p TARGET_PATH="请输入商铺文件夹或批量父目录路径: "

if "%TARGET_PATH%"=="" (
    echo 输入为空，已退出。
    pause
    exit /b
)

:: 去除两端可能包含的双引号
set TARGET_PATH=%TARGET_PATH:"=%

echo.
echo [1] 为这单个商铺生成封面
echo [2] 批量为该父目录下的所有商铺生成封面
set /p MODE="请选择模式 (默认回车为 1): "

if "%MODE%"=="2" (
    echo [处理中] 正在批量生成封面...
    python "%PY_SCRIPT%" --batch_dir "%TARGET_PATH%"
) else (
    echo [处理中] 正在为单个商铺生成封面...
    python "%PY_SCRIPT%" --folder "%TARGET_PATH%"
)

echo.
echo ========================================================
echo [完成] 处理结束！
echo ========================================================
pause
