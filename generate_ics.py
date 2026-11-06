# -*- coding: utf-8 -*-
"""
生成符合 RFC 5545 标准的 iCalendar (.ics) 日历订阅文件
兼容 Python 3.7+，无需安装第三方依赖
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

def escape_text(text: str) -> str:
    """
    RFC 5545 3.3.11 TEXT 属性转义:
    '\\' -> '\\\\'
    ';'  -> '\\;'
    ','  -> '\\,'
    '\\n' -> '\\n' (换行符转换为文本 '\\n')
    """
    if not text:
        return ""
    # 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 先转义反斜杠，再转义分号、逗号
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    # 最后将换行符替换为字面量 \n
    text = text.replace("\n", "\\n")
    return text

def fold_line(line: str, max_octets: int = 75) -> str:
    """
    RFC 5545 3.1 行折行规则:
    行长度不得超过 75 字节（octets）。
    长行在字符边界处截断，续行以单个空格（\\r\\n ）开头。
    续行的开头空格本身占 1 字节，续行内容长度需 <= 74 字节。
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= max_octets:
        return line

    chunks = []
    current_chunk = []
    current_len = 0
    limit = max_octets

    for char in line:
        char_len = len(char.encode("utf-8"))
        if current_len + char_len > limit:
            chunks.append("".join(current_chunk))
            current_chunk = [char]
            current_len = 1 + char_len  # 续行前导空格占 1 字节
            limit = max_octets
        else:
            current_chunk.append(char)
            current_len += char_len

    if current_chunk:
        chunks.append("".join(current_chunk))

    if not chunks:
        return ""

    result = [chunks[0]] + [" " + c for c in chunks[1:]]
    return "\r\n".join(result)

def format_utc(dt: datetime) -> str:
    """转为 iCalendar 标准 UTC 时间格式: YYYYMMDDTHHMMSSZ"""
    return dt.strftime('%Y%m%dT%H%M%SZ')

def parse_deadline(deadline_str: str) -> datetime:
    """解析截止时间，支持多种常用格式"""
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
    for fmt in formats:
        try:
            return datetime.strptime(deadline_str.strip(), fmt)
        except ValueError:
            pass
    raise ValueError(f"无法解析时间格式: '{deadline_str}'，请使用 'YYYY-MM-DD HH:MM:SS' 或 'YYYY-MM-DD HH:MM'")

def build_ics(tasks_path: str, output_path: str) -> bool:
    if not os.path.exists(tasks_path):
        print(f"错误: 找不到任务数据文件 {tasks_path}", file=sys.stderr)
        return False

    with open(tasks_path, "r", encoding="utf-8") as f:
        try:
            tasks = json.load(f)
        except Exception as e:
            print(f"错误: 解析 {tasks_path} 失败: {e}", file=sys.stderr)
            return False

    now_utc = datetime.now(timezone.utc)

    raw_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Study DDL Calendar//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:学业与课程 DDL",
        "X-WR-TIMEZONE:Asia/Shanghai"
    ]

    valid_count = 0
    for idx, item in enumerate(tasks, start=1):
        raw_deadline = item.get("deadline", "")
        try:
            local_deadline = parse_deadline(raw_deadline)
        except Exception as e:
            print(f"警告: 跳过第 {idx} 项 ('{item.get('title', '未知')}'): {e}", file=sys.stderr)
            continue

        # 北京时间 (UTC+8) 转 UTC 时间
        utc_deadline = local_deadline - timedelta(hours=8)
        # 事件起止时间：以截止时间为起点，默认持续 15 分钟作为明确截止标识
        # 从而使相对于 DTSTART 的 VALARM 准确在截止时刻前 24 小时和 2 小时触发
        utc_start = utc_deadline
        utc_end = utc_deadline + timedelta(minutes=15)

        # 稳定唯一 UID：优先使用数据源显式 id，缺省时降级为 UUID5 哈希
        item_id = item.get("id")
        if item_id:
            item_uid = f"{item_id}@ddl-calendar"
        else:
            raw_id_str = f"{item.get('title', '')}_{raw_deadline}"
            item_uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_id_str))

        raw_summary = item.get("title", "未命名 DDL")
        raw_desc_parts = []
        if "course" in item and item["course"]:
            raw_desc_parts.append(f"课程: {item['course']}")
        if "description" in item and item["description"]:
            raw_desc_parts.append(item["description"])
        raw_description = "\n".join(raw_desc_parts)

        # RFC 5545 转义
        summary_escaped = escape_text(raw_summary)
        description_escaped = escape_text(raw_description)

        raw_lines.extend([
            "BEGIN:VEVENT",
            f"UID:{item_uid}",
            f"DTSTAMP:{format_utc(now_utc)}",
            f"DTSTART:{format_utc(utc_start)}",
            f"DTEND:{format_utc(utc_end)}",
            f"SUMMARY:{summary_escaped}",
            f"DESCRIPTION:{description_escaped}",
            "STATUS:CONFIRMED",
            # 提前 1 天（24小时）提醒
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:距离 DDL 还有 1 天",
            "TRIGGER:-P1D",
            "END:VALARM",
            # 提前 2 小时提醒
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:距离 DDL 仅剩 2 小时",
            "TRIGGER:-PT2H",
            "END:VALARM",
            "END:VEVENT"
        ])
        valid_count += 1

    raw_lines.append("END:VCALENDAR")

    # 对每一行执行 RFC 5545 75 字节折行
    folded_lines = [fold_line(line) for line in raw_lines]
    content = "\r\n".join(folded_lines) + "\r\n"

    # 确保目标文件夹存在
    target_dir = os.path.dirname(output_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

    print(f"成功生成 {output_path}，包含 {valid_count} 个有效事件。")
    return True

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_file = os.path.join(base_dir, "ddl_list.json")

    # 同时更新根目录（供本地直接查看）与 public 目录（供 Actions 发布）
    root_output = os.path.join(base_dir, "ddl.ics")
    public_output = os.path.join(base_dir, "public", "ddl.ics")

    success_root = build_ics(tasks_file, root_output)
    success_pub = build_ics(tasks_file, public_output)

    if not (success_root and success_pub):
        sys.exit(1)
