# -*- coding: utf-8 -*-
"""
生成标准 iCalendar (.ics) 日历订阅文件
兼容 Python 3.7+，无需安装第三方依赖
"""

import json
import uuid
from datetime import datetime, timedelta

def format_utc(dt):
    """转为 iCalendar 标准 UTC 时间格式: YYYYMMDDTHHMMSSZ"""
    return dt.strftime('%Y%m%dT%H%M%SZ')

def build_ics(tasks_path, output_path):
    with open(tasks_path, 'r', encoding='utf-8') as f:
        tasks = json.load(f)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Study DDL Calendar//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:学业与课程 DDL",
        "X-WR-TIMEZONE:Asia/Shanghai"
    ]

    now_utc = datetime.utcnow()

    for item in tasks:
        # 解析北京时间 (UTC+8)
        local_deadline = datetime.strptime(item["deadline"], "%Y-%m-%d %H:%M:%S")
        # 转换为 UTC 时间
        utc_deadline = local_deadline - timedelta(hours=8)
        # 事件时长默认设为 1 小时
        utc_start = utc_deadline - timedelta(hours=1)

        # 生成确定性 UID
        raw_id_str = item["title"] + item["deadline"]
        item_uid = str(uuid.uuid5(uuid.NAMESPACE_DNS, raw_id_str))

        summary = item.get("title", "未命名 DDL")
        description = item.get("description", "")
        if "course" in item:
            description = "课程: " + item["course"] + "\n" + description

        lines.extend([
            "BEGIN:VEVENT",
            "UID:" + item_uid,
            "DTSTAMP:" + format_utc(now_utc),
            "DTSTART:" + format_utc(utc_start),
            "DTEND:" + format_utc(utc_deadline),
            "SUMMARY:" + summary,
            "DESCRIPTION:" + description.replace("\n", "\\n"),
            "STATUS:CONFIRMED",
            # 提前 1 天提醒
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

    lines.append("END:VCALENDAR")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\r\n".join(lines) + "\r\n")

if __name__ == "__main__":
    build_ics("ddl_list.json", "ddl.ics")
    print("成功生成 ddl.ics")
