# -*- coding: utf-8 -*-
"""
Google Tasks 自动同步脚本
读取 ddl_list.json，自动同步未完成任务到 Google Tasks，并关联截止日期。
支持 Python 3.7+，使用标准库与 requests，支持本地代理。
"""

import json
import os
import sys
import webbrowser
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

CLIENT_SECRET_FILE = os.path.join(os.path.dirname(__file__), "client_secret.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "google_tasks_token.json")
TASKS_JSON_FILE = os.path.join(os.path.dirname(__file__), "ddl_list.json")
PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

def load_client_credentials():
    if not os.path.exists(CLIENT_SECRET_FILE):
        raise FileNotFoundError(f"未找到凭据配置文件: {CLIENT_SECRET_FILE}")
    with open(CLIENT_SECRET_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["client_id"], data["client_secret"]

CLIENT_ID, CLIENT_SECRET = load_client_credentials()

auth_code = None

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urlparse(self.path).query
        params = parse_qs(query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h1>授权成功！</h1><p>您可以关闭此窗口，回到命令行继续操作。</p>".encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write("授权失败，未收到授权码。".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # 静默请求日志

def get_auth_token():
    """获取或刷新 Google Tasks Access Token"""
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                token_data = json.load(f)
            # 尝试刷新 token
            refresh_token = token_data.get("refresh_token")
            if refresh_token:
                resp = requests.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                    proxies=PROXY,
                    timeout=10,
                )
                if resp.status_code == 200:
                    new_token = resp.json()
                    token_data["access_token"] = new_token["access_token"]
                    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                        json.dump(token_data, f, ensure_ascii=False, indent=2)
                    return token_data["access_token"]
        except Exception as e:
            print(f"本地 Token 刷新失败，将重新授权: {e}")

    # 首次授权：启动本地简易服务接收回调
    port = 8765
    redirect_uri = f"http://127.0.0.1:{port}"
    scope = "https://www.googleapis.com/auth/tasks"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope={scope}&"
        f"access_type=offline&"
        f"prompt=consent"
    )

    print("正在打开浏览器进行 Google 账号授权...")
    webbrowser.open(auth_url)

    server = HTTPServer(("127.0.0.1", port), OAuthHandler)
    while auth_code is None:
        server.handle_request()
    server.server_close()

    # 用授权码换取 token
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        proxies=PROXY,
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"换取 Token 失败: {resp.text}")

    token_data = resp.json()
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)
    print("授权信息已成功保存至本地。")
    return token_data["access_token"]

def get_or_create_tasklist(headers):
    """获取或创建名为 '学业与课程 DDL' 的任务清单"""
    list_url = "https://tasks.googleapis.com/tasks/v1/users/@me/lists"
    resp = requests.get(list_url, headers=headers, proxies=PROXY, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"获取任务列表失败: {resp.text}")

    lists = resp.json().get("items", [])
    target_name = "学业与课程 DDL"
    for item in lists:
        if item.get("title") == target_name:
            return item.get("id")

    # 创建新列表
    create_resp = requests.post(
        list_url,
        headers=headers,
        json={"title": target_name},
        proxies=PROXY,
        timeout=10,
    )
    return create_resp.json().get("id")

def sync_tasks():
    print("=== 开始同步 Google Tasks ===")
    token = get_auth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    tasklist_id = get_or_create_tasklist(headers)

    # 获取当前列表已有的任务（避免重复添加）
    tasks_url = f"https://tasks.googleapis.com/tasks/v1/lists/{tasklist_id}/tasks"
    existing_resp = requests.get(tasks_url, headers=headers, proxies=PROXY, timeout=10)
    existing_titles = set()
    if existing_resp.status_code == 200:
        for t in existing_resp.json().get("items", []):
            existing_titles.add(t.get("title"))

    # 读取本地 DDL 任务
    with open(TASKS_JSON_FILE, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    added_count = 0
    skipped_count = 0

    for item in tasks:
        title = item.get("title")
        if title in existing_titles:
            skipped_count += 1
            continue

        # 将本地北京时间转为 RFC 3339 格式的 UTC 时间
        local_deadline = datetime.strptime(item["deadline"], "%Y-%m-%d %H:%M:%S")
        utc_deadline = local_deadline - timedelta(hours=8)
        due_str = utc_deadline.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        notes = item.get("description", "")
        if "course" in item:
            notes = f"课程: {item['course']}\n{notes}"

        payload = {
            "title": title,
            "notes": notes,
            "due": due_str,
        }

        add_resp = requests.post(tasks_url, headers=headers, json=payload, proxies=PROXY, timeout=10)
        if add_resp.status_code in (200, 201):
            added_count += 1
            print(f"[已添加] {title}")
        else:
            print(f"[添加失败] {title}: {add_resp.text}")

    print(f"\n同步完成：成功新增 {added_count} 条任务，跳过已存在 {skipped_count} 条任务。")

if __name__ == "__main__":
    try:
        sync_tasks()
    except Exception as e:
        print(f"同步过程中发生错误: {e}")
