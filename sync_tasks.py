# -*- coding: utf-8 -*-
"""
通过 Google Apps Script Webhook 自动同步任务到 Google Tasks

注意：
- Google Tasks API 的 due 字段只支持日期级别，时间部分会被官方 API 截断丢弃。
- 因此 Google Tasks 定位为“每日待办清单”，具体精确截止时刻会同步写入任务备注首行。
- 精确到小时的弹窗提醒由 ICS 日历订阅（ddl.ics）提供。
"""

import json
import os
import socket
import sys
from datetime import datetime, timezone, timedelta

WEBHOOK_FILE = os.path.join(os.path.dirname(__file__), "webhook_url.txt")
TASKS_JSON_FILE = os.path.join(os.path.dirname(__file__), "ddl_list.json")

def detect_proxy():
    """自动获取代理配置：优先环境变量，其次探测本机代理端口（7892 / 7890 等）"""
    env_https = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    env_http = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    env_all = os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")

    active_proxy = env_https or env_http or env_all
    if active_proxy:
        return {"http": active_proxy, "https": active_proxy}

    # 常见本地客户端端口探测: 7892 (FlyingBird), 7890 (Clash), 10809 (v2ray)
    candidate_ports = [7892, 7890, 10809, 10808]
    for port in candidate_ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        if result == 0:
            p = f"http://127.0.0.1:{port}"
            return {"http": p, "https": p}

    return None

def parse_deadline(deadline_str: str) -> datetime:
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
    for fmt in formats:
        try:
            return datetime.strptime(deadline_str.strip(), fmt)
        except ValueError:
            pass
    raise ValueError(f"无法解析时间: {deadline_str}")

def sync_tasks(webhook_url=None) -> bool:
    if not webhook_url:
        if not os.path.exists(WEBHOOK_FILE):
            print("错误: 未找到 webhook_url.txt 文件。", file=sys.stderr)
            print("请把 Google Apps Script 部署后的 Webhook URL 复制保存到 webhook_url.txt 中。", file=sys.stderr)
            return False
        with open(WEBHOOK_FILE, "r", encoding="utf-8") as f:
            webhook_url = f.read().strip()

    if not webhook_url.startswith("https://script.google.com/"):
        print("错误: webhook_url.txt 中的链接格式不正确（必须以 https://script.google.com/ 开头）。", file=sys.stderr)
        return False

    if not os.path.exists(TASKS_JSON_FILE):
        print(f"错误: 找不到任务列表文件 {TASKS_JSON_FILE}", file=sys.stderr)
        return False

    with open(TASKS_JSON_FILE, "r", encoding="utf-8") as f:
        try:
            tasks = json.load(f)
        except Exception as e:
            print(f"错误: 解析 {TASKS_JSON_FILE} 失败: {e}", file=sys.stderr)
            return False

    payload_tasks = []
    for item in tasks:
        raw_dl = item.get("deadline", "")
        try:
            local_deadline = parse_deadline(raw_dl)
        except Exception as e:
            print(f"警告: 跳过条目 '{item.get('title')}': {e}", file=sys.stderr)
            continue

        utc_deadline = local_deadline - timedelta(hours=8)
        due_str = utc_deadline.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # 将具体时间作为显式显示字段传递，并在描述中前置
        due_display = local_deadline.strftime("%Y-%m-%d %H:%M")
        desc = item.get("description", "")
        # 在本地也确保 description 首行带上截止时间，保证即使旧版 GAS 也能看清时间
        full_desc = f"【截止时间: {due_display}】\n{desc}".strip()

        payload_tasks.append({
            "id": item.get("id", ""),
            "title": item.get("title"),
            "course": item.get("course", ""),
            "description": full_desc,
            "due": due_str,
            "due_display": due_display
        })

    if not payload_tasks:
        print("没有可同步的任务。")
        return True

    print(f"正在向 Google Tasks 推送 {len(payload_tasks)} 条任务...")
    proxies = detect_proxy()
    if proxies:
        print(f"已启用代理: {proxies.get('https')}")

    # 优先尝试 requests 模块
    try:
        import requests
        resp = requests.post(
            webhook_url,
            json={"tasks": payload_tasks},
            proxies=proxies,
            timeout=25,
            headers={"Content-Type": "application/json"},
            allow_redirects=True
        )
        if resp.status_code == 200:
            try:
                result = resp.json()
            except Exception:
                result = {"status": "ok", "raw": resp.text}

            if result.get("status") == "ok":
                print(f"同步成功！新增任务: {result.get('added', 0)} 条，跳过已存在: {result.get('skipped', 0)} 条。")
                print("提示: Google Tasks 作为清单展示，精确截止时间已记录在任务备注首行。")
                return True
            else:
                print(f"服务端返回错误: {result.get('message')}", file=sys.stderr)
                return False
        else:
            print(f"请求失败，状态码: {resp.status_code}, 内容: {resp.text}", file=sys.stderr)
            return False

    except ImportError:
        print("提示: 未检测到 requests 库，正在尝试使用标准库 urllib 同步（建议运行 pip install -r requirements.txt）...")
        import urllib.request
        import urllib.error

        req_data = json.dumps({"tasks": payload_tasks}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=req_data,
            headers={"Content-Type": "application/json"}
        )

        handlers = []
        if proxies and "https" in proxies:
            handlers.append(urllib.request.ProxyHandler({"https": proxies["https"], "http": proxies["http"]}))
        opener = urllib.request.build_opener(*handlers)

        try:
            with opener.open(req, timeout=25) as response:
                body = response.read().decode("utf-8")
                print(f"同步请求已发送，响应: {body[:200]}")
                return True
        except Exception as err:
            print(f"网络请求出错: {err}", file=sys.stderr)
            return False

    except Exception as e:
        print(f"网络请求出错: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    success = sync_tasks(url_arg)
    sys.exit(0 if success else 1)
