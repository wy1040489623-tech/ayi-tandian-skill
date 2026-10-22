@echo off
title 启动 Chrome 调试模式 (端口 9222)
echo ============================================================
echo   阿一小红书图片下载 Skill - 一键启动 Chrome 调试模式
echo ============================================================
echo.

:: 1. 自动探测 Chrome 安装路径
set "CHROME_PATH="
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_PATH=%LocalAppData%\Google\Chrome\Application\chrome.exe"
)

if "%CHROME_PATH%"=="" (
    echo [错误] 未在系统中找到 Google Chrome 浏览器！
    echo 请确认是否已安装 Chrome，或手动指定 chrome.exe 路径。
    echo.
    pause
    exit /b 1
)

:: 2. 设置独立调试数据目录（保证 9222 端口 100% 成功，且不影响日常正常使用的 Chrome 窗口）
if exist "E:\chrome_dev_profile" (
    set "USER_DATA_DIR=E:\chrome_dev_profile"
) else (
    set "USER_DATA_DIR=%LocalAppData%\Google\Chrome\ayi_debug_profile"
)
if not exist "%USER_DATA_DIR%" mkdir "%USER_DATA_DIR%" >nul 2>&1

:: 3. 检查 9222 端口是否已经在监听
netstat -ano | findstr ":9222" >nul
if %errorlevel% equ 0 (
    echo [提示] 9222 调试端口已在运行中！
    echo [唤起] 正在激活并将 Chrome 窗口前置，打开小红书页面...
    start "" "%CHROME_PATH%" --remote-debugging-port=9222 --user-data-dir="%USER_DATA_DIR%" https://www.xiaohongshu.com
    echo.
    echo [就绪] 浏览器已准备完毕，可直接执行图片下载任务！
    echo 3秒后窗口将自动关闭...
    ping -n 4 127.0.0.1 >nul
    exit /b 0
)

:: 4. 全新启动 Chrome 调试模式
echo [启动中] 正在拉起 Chrome 调试窗口 (端口: 9222)...
start "" "%CHROME_PATH%" --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="%USER_DATA_DIR%" https://www.xiaohongshu.com
echo.
echo [成功] Chrome 调试窗口已唤起并打开小红书！
echo 请在弹出的浏览器中确认登录小红书账号，即可开始自动化下载。
echo 3秒后窗口将自动关闭...
ping -n 4 127.0.0.1 >nul
exit /b 0
