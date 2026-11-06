# 学业与课程 DDL 订阅日历

基于 GitHub Actions 自动化维护的标准日历订阅源（iCalendar / .ics），可以直接在 iPhone、iPad、Android 手机及电脑系统日历中订阅。

## 手机日历订阅地址

- **订阅链接**：`https://yyf419314-hub.github.io/my-ddl-calendar/ddl.ics`

---

## 快速订阅方法

### 1. 苹果设备（iPhone / iPad / Mac）
1. 打开系统自带 **日历** App。
2. 依次点击：底部 **日历** -> **添加日历** -> **添加订阅日历**。
3. 粘贴上述订阅地址，点击 **订阅**。
4. **刷新频率** 建议设为 **每小时**，并开启 **提醒** 开关。
5. 可在主屏幕或锁屏添加系统日历小组件，查看临近 DDL。

### 2. 安卓设备
- **Google 日历**：
  在电脑端打开 [Google 日历网页版](https://calendar.google.com/)，在左侧「其他日历」点击 `+` -> **通过网址添加**，输入上述链接。手机端 Google 日历 App 会自动拉取同步。
- **国产安卓系统（小米 / 华为 / OPPO / vivo 等）**：
  打开系统自带「日历」-> 设置 -> 「日程导入」或「添加网络/URL订阅日历」，粘贴链接即可。

---

## 功能说明与架构分工

本项目支持 **ICS 日历订阅** 与 **Google Tasks 待办同步** 两条链路，分工如下：

1. **ICS 系统日历（核心）**：
   - 负责精确到分钟的日程展示与到期提醒。
   - 包含两个默认提醒节点：**截止前 24 小时**（提前 1 天）与 **截止前 2 小时**。
   - 遵循 RFC 5545 规范（支持 75 字节 UTF-8 安全折行与字符转义）。
2. **Google Tasks（辅助清单）**：
   - 作为手机桌面小组件与每日待办清单。
   - **机制说明**：受 Google Tasks 官方 API 特性限制，API 的 `due` 字段仅记录日期，不保存具体小时分钟。为弥补该限制，同步脚本已将精确截止时刻（如 `截止时间: 23:59`）自动写在任务备注的第一行。

---

## 如何添加或修改 DDL

直接修改仓库根目录的 `ddl_list.json` 文件：

```json
[
  {
    "id": "micro-econ-20261112",
    "title": "【微观经济学】作业与复习",
    "deadline": "2026-11-12 23:59:00",
    "description": "模块5-8讲义及课后练习整理",
    "course": "微观经济学"
  }
]
```

### 字段说明
- `id`：任务唯一标识（英文字符/拼音/数字），修改标题或时间时保持 `id` 不变，日历客户端会自动更新已有日程，不会生成重复事件。
- `title`：任务标题。
- `deadline`：截止时间（格式为 `YYYY-MM-DD HH:MM:SS` 或 `YYYY-MM-DD HH:MM`）。
- `course`：课程名称（可选）。
- `description`：补充说明（可选）。

修改保存后：
- 双击运行本地的 `sync_all.bat`（一键同步到 Google Tasks 并提交推送到 GitHub）；
- 或仅推送日历时运行 `sync_ddl.bat`；
- 推送后，GitHub Actions 会在约 30 秒内完成编译与发布。手机端将在设定的刷新周期（如每小时）或手动下拉日历时同步最新日程。

---

## 本地环境与 Google Tasks 配置

如果只需要使用系统日历订阅，不需要配置任何本地 Python 依赖，直接修改 `ddl_list.json` 推送到 GitHub 即可。

如果需要使用 Google Tasks 同步：
1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
   *(脚本内部已集成网络库降级处理，未安装 requests 时会自动尝试标准库)*
2. 部署 Apps Script Webhook：
   - 参考 `gas/Code.gs` 文件头部的说明，在 Google Apps Script 中部署 Web 应用并获取 URL。
   - 将 URL 写入本地的 `webhook_url.txt`。
3. 代理支持：
   - 脚本会自动检测系统环境变量代理，并在未配置时自动尝试检测本地端口（如 `7892`、`7890`）。
