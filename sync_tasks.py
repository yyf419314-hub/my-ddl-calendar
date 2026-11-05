# -*- coding: utf-8 -*-
"""
通过 Google Apps Script Webhook 自动同步任务到 Google Tasks
"""

import json
import os
import sys
from datetime import datetime, timedelta
import requests

WEBHOOK_FILE = os.path.join(os.path.dirname(__file__), "webhook_url.txt")
TASKS_JSON_FILE = os.path.join(os.path.dirname(__file__), "ddl_list.json")
PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

def sync_tasks(webhook_url=None):
    if not webhook_url:
        if not os.path.exists(WEBHOOK_FILE):
            print("错误: 未找到 webhook_url.txt 文件。")
            print("请把 Google Apps Script 部署后的 Webhook URL 复制保存到 webhook_url.txt 中。")
            return
        with open(WEBHOOK_FILE, "r", encoding="utf-8") as f:
            webhook_url = f.read().strip()

    if not webhook_url.startswith("https://script.google.com/"):
        print("错误: webhook_url.txt 中的链接格式不正确。")
        return

    with open(TASKS_JSON_FILE, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    payload_tasks = []
    for item in tasks:
        local_deadline = datetime.strptime(item["deadline"], "%Y-%m-%d %H:%M:%S")
        utc_deadline = local_deadline - timedelta(hours=8)
        due_str = utc_deadline.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        payload_tasks.append({
            "title": item.get("title"),
            "course": item.get("course", ""),
            "description": item.get("description", ""),
            "due": due_str
        })

    print(f"正在向 Google Tasks 推送 {len(payload_tasks)} 条任务...")

    try:
        resp = requests.post(
            webhook_url,
            json={"tasks": payload_tasks},
            proxies=PROXY,
            timeout=20,
            headers={"Content-Type": "application/json"}
        )
        if resp.status_code == 200:
            result = resp.json()
            if result.get("status") == "ok":
                print(f"同步成功！新增任务: {result.get('added', 0)} 条，跳过已存在: {result.get('skipped', 0)} 条。")
                print("现在打开手机 Google Tasks App 即可看到最新任务！")
            else:
                print(f"服务端返回错误: {result.get('message')}")
        else:
            print(f"请求失败，状态码: {resp.status_code}, 内容: {resp.text}")
    except Exception as e:
        print(f"网络请求出错: {e}")

if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    sync_tasks(url_arg)
