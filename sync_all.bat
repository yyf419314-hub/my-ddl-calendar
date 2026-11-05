@echo off
chcp 65001 >nul
echo ========================================
echo   一键同步：GitHub 日历 + Google Tasks
echo ========================================
echo.

cd /d "D:\my-ddl-calendar"

echo [1/2] 正在同步到 Google Tasks...
python sync_tasks.py
echo.

echo [2/2] 正在推送到 GitHub 日历...
"D:\Git\cmd\git.exe" add ddl_list.json
"D:\Git\cmd\git.exe" commit -m "update: update ddl_list.json"
"D:\Git\cmd\git.exe" push origin main
echo.

echo ========================================
echo   全部同步完成！
echo   手机 Google Tasks 和日历小组件已就绪。
echo ========================================
pause
