@echo off
chcp 65001 >nul
echo 正在同步任务到 Google Tasks...
cd /d "D:\my-ddl-calendar"
python sync_tasks.py
echo.
pause
