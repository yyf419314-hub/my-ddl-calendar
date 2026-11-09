# -*- coding: utf-8 -*-
"""
通过 Google Apps Script Webhook 自动同步任务到 Google Tasks

注意：
- Google Tasks API 的 due 字段只支持日期级别，时间部分会被官方 API 截断丢弃。
- 因此 due 直接使用北京时间当天日期（YYYY-MM-DDT00:00:00.000Z），避免早上 8 点前的任务因减 8 小时跨日到前一天。
- Google Tasks 定位为“每日待办清单”，具体精确截止时刻会同步写入任务备注首行。
- 精确到小时的弹窗提醒由 ICS 日历订阅（ddl.ics）提供。
"""

import json
import os
import socket
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBHOOK_FILE = os.path.join(BASE_DIR, "webhook_url.txt")
SECRET_FILE = os.path.join(BASE_DIR, "webhook_secret.txt")
TASKS_JSON_FILE = os.path.join(BASE_DIR, "ddl_list.json")

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
    if not isinstance(deadline_str, str) or not deadline_str.strip():
        raise ValueError("缺少 deadline 字段或为空")
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
    for fmt in formats:
        try:
            return datetime.strptime(deadline_str.strip(), fmt)
        except ValueError:
            pass
    raise ValueError(f"无法解析时间: '{deadline_str}'")

def handle_response_text(body_text: str) -> bool:
    """统一解析 Google Apps Script 返回的 JSON 结果"""
    try:
        result = json.loads(body_text)
    except Exception:
        print(f"错误: 服务端返回了非 JSON 响应（请检查 Webhook 部署权限是否为“任何人”）:\n{body_text[:300]}", file=sys.stderr)
        return False

    if result.get("status") == "ok":
        added = result.get("added", 0)
        updated = result.get("updated", 0)
        skipped = result.get("skipped", 0)
        deleted = result.get("deleted", 0)
        summary = f"同步成功！新增: {added} 条，更新: {updated} 条，跳过（无变更或已完成）: {skipped} 条"
        if deleted:
            summary += f"，清理已移除任务: {deleted} 条"
        print(summary + "。")
        print("提示: Google Tasks 作为清单展示，精确截止时间已记录在任务备注首行。")
        return True
    else:
        print(f"服务端返回错误: {result.get('message', body_text)}", file=sys.stderr)
        return False

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

    # 读取可选密钥
    token = ""
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "r", encoding="utf-8") as f:
            token = f.read().strip()

    if not os.path.exists(TASKS_JSON_FILE):
        print(f"错误: 找不到任务列表文件 {TASKS_JSON_FILE}", file=sys.stderr)
        return False

    with open(TASKS_JSON_FILE, "r", encoding="utf-8") as f:
        try:
            tasks = json.load(f)
        except Exception as e:
            print(f"错误: 解析 {TASKS_JSON_FILE} 失败: {e}", file=sys.stderr)
            return False

    if not isinstance(tasks, list):
        print(f"错误: {TASKS_JSON_FILE} 顶层必须是数组", file=sys.stderr)
        return False

    payload_tasks = []
    seen_ids = set()
    has_error = False

    for idx, item in enumerate(tasks, start=1):
        if not isinstance(item, dict):
            print(f"错误: 第 {idx} 项不是有效的 JSON 对象", file=sys.stderr)
            has_error = True
            continue

        title = str(item.get("title", "")).strip()
        if not title:
            print(f"错误: 第 {idx} 项缺少 title 字段", file=sys.stderr)
            has_error = True
            continue

        raw_dl = item.get("deadline", "")
        try:
            local_deadline = parse_deadline(raw_dl)
        except Exception as e:
            print(f"错误: 第 {idx} 项 ('{title}') 时间格式非法: {e}", file=sys.stderr)
            has_error = True
            continue

        item_id = str(item.get("id", "")).strip()
        if item_id:
            if item_id in seen_ids:
                print(f"错误: 第 {idx} 项 ('{title}') 的 id '{item_id}' 重复", file=sys.stderr)
                has_error = True
                continue
            seen_ids.add(item_id)

        # Google Tasks API 的 due 仅保留 UTC 日期部分（YYYY-MM-DD），丢弃时分秒
        # 直接使用北京时间的日期生成 YYYY-MM-DDT00:00:00.000Z，防止 00:00~07:59 的任务被减到前一天
        due_str = local_deadline.strftime("%Y-%m-%dT00:00:00.000Z")
        due_display = local_deadline.strftime("%Y-%m-%d %H:%M")

        payload_tasks.append({
            "id": item_id,
            "title": title,
            "course": str(item.get("course", "")).strip(),
            "description": str(item.get("description", "")).strip(),
            "due": due_str,
            "due_display": due_display,
            "completed": bool(item.get("completed", False))
        })

    if has_error:
        print("错误: 数据校验未通过，已中止向 Google Tasks 同步。", file=sys.stderr)
        return False

    if not payload_tasks:
        print("没有可同步的任务。")
        return True

    payload = {
        "tasks": payload_tasks,
        "prune_deleted": True
    }
    if token:
        payload["token"] = token

    print(f"正在向 Google Tasks 推送 {len(payload_tasks)} 条任务...")
    proxies = detect_proxy()
    if proxies:
        print(f"已启用代理: {proxies.get('https')}")

    # 优先使用 requests
    try:
        import requests
        resp = requests.post(
            webhook_url,
            json=payload,
            proxies=proxies,
            timeout=25,
            headers={"Content-Type": "application/json"},
            allow_redirects=True
        )
        if resp.status_code == 200:
            return handle_response_text(resp.text)
        else:
            print(f"请求失败，状态码: {resp.status_code}, 内容: {resp.text[:300]}", file=sys.stderr)
            return False

    except ImportError:
        print("提示: 未检测到 requests 库，正在使用标准库 urllib 同步...")
        import urllib.request
        import urllib.error

        req_data = json.dumps(payload).encode("utf-8")
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
                return handle_response_text(body)
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
