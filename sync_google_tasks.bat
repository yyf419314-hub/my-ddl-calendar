@echo off
chcp 65001 >nul

echo ===================================
echo   正在同步任务到 Google Tasks
echo ===================================
echo.

cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else if exist "D:\anaconda\python.exe" (
    set "PY_CMD=D:\anaconda\python.exe"
) else (
    echo [错误] 未检测到 Python，请检查环境变量。
    pause
    exit /b 1
)

"%PY_CMD%" sync_tasks.py
if %errorlevel% neq 0 (
    echo.
    echo [错误] 同步失败，请检查网络/代理或 Webhook 配置。
    pause
    exit /b 1
) else (
    echo.
    echo [成功] Google Tasks 任务清单已更新。
)

echo.
pause
