@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   一键同步：GitHub 日历 + Google Tasks
echo ========================================
echo.

cd /d "D:\my-ddl-calendar"

:: 检测 Python 路径
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

:: 检测 Git 路径
where git >nul 2>nul
if %errorlevel% equ 0 (
    set "GIT_CMD=git"
) else if exist "D:\Git\cmd\git.exe" (
    set "GIT_CMD=D:\Git\cmd\git.exe"
) else if exist "C:\Program Files\Git\cmd\git.exe" (
    set "GIT_CMD=C:\Program Files\Git\cmd\git.exe"
) else (
    echo [错误] 未检测到 Git，请检查 Git 安装路径。
    pause
    exit /b 1
)

echo [1/3] 正在同步到 Google Tasks...
"%PY_CMD%" sync_tasks.py
if %errorlevel% neq 0 (
    echo [警告] Google Tasks 同步未成功（可能是网络、代理或 Webhook 配置原因）。
    echo.
) else (
    echo [成功] Google Tasks 已同步完成。
    echo.
)

echo [2/3] 正在本地验证并生成 ICS 日历...
"%PY_CMD%" generate_ics.py
if %errorlevel% neq 0 (
    echo [错误] ICS 日历生成失败，请检查 ddl_list.json 格式。
    pause
    exit /b 1
)
echo.

echo [3/3] 正在检查并推送到 GitHub...
"%GIT_CMD%" add ddl_list.json
"%GIT_CMD%" diff --cached --quiet
if %errorlevel% equ 0 (
    echo [提示] ddl_list.json 无变动，无需提交到 GitHub。
) else (
    "%GIT_CMD%" commit -m "update: update ddl_list.json"
    if !errorlevel! neq 0 (
        echo [错误] Git 提交失败。
        pause
        exit /b 1
    )
    "%GIT_CMD%" push origin main
    if !errorlevel! neq 0 (
        echo [错误] Git 推送失败，请检查网络或 GitHub 认证。
        pause
        exit /b 1
    )
    echo [成功] 已成功推送到 GitHub，Actions 将自动发布最新日历。
)

echo.
echo ========================================
echo   同步流程执行完毕！
echo ========================================
pause
