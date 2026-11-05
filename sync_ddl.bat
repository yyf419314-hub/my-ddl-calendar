@echo off
chcp 65001 >nul
echo 正在检查并更新 DDL 日历...
cd /d "D:\my-ddl-calendar"
"D:\Git\cmd\git.exe" add ddl_list.json
"D:\Git\cmd\git.exe" commit -m "update: update ddl_list.json"
"D:\Git\cmd\git.exe" push origin main
echo.
echo ===================================
echo 更新已成功推送到 GitHub！
echo 云端 Actions 将在 30 秒内完成日历刷新。
echo ===================================
pause
