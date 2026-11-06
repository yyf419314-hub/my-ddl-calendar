/**
 * Google Apps Script Webhook: 接收外部任务并同步至 Google Tasks
 * 
 * 部署步骤：
 * 1. 在浏览器打开 https://script.google.com/ ，新建一个项目。
 * 2. 将本文件代码完整粘贴替换 Code.gs。
 * 3. 在左侧菜单栏点击「服务 (Services) +」，找到「Tasks API」并添加启用。
 * 4. 点击右上角「部署 (Deploy)」->「新建部署 (New deployment)」。
 * 5. 种类选择「网页应用 (Web app)」：
 *    - 说明 (Description): DDL Webhook
 *    - 执行身份 (Execute as): 我 (Me)
 *    - 谁可以访问 (Who has access): 任何人 (Anyone)
 * 6. 点击「部署」，授权权限后复制「网页应用网址 (Web App URL)」。
 * 7. 将该网址粘贴到本地仓库的 webhook_url.txt 文件中。
 */

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse({ status: "error", message: "缺少请求体数据" });
    }

    var data = JSON.parse(e.postData.contents);
    var tasks = data.tasks;

    if (!Array.isArray(tasks) || tasks.length === 0) {
      return jsonResponse({ status: "ok", added: 0, skipped: 0, message: "无任务需要同步" });
    }

    // 获取默认任务列表 ID
    var taskListId = "@default";

    // 获取现有任务列表，用于去重比较
    var existingTasks = [];
    var pageToken = null;
    do {
      var res = Tasks.Tasks.list(taskListId, {
        maxResults: 100,
        pageToken: pageToken,
        showCompleted: false,
        showHidden: false
      });
      if (res.items && res.items.length > 0) {
        existingTasks = existingTasks.concat(res.items);
      }
      pageToken = res.nextPageToken;
    } while (pageToken);

    // 建立现有任务标题集合（大小写统一并去除首尾空格）
    var existingTitles = {};
    existingTasks.forEach(function(t) {
      if (t.title) {
        existingTitles[t.title.trim()] = true;
      }
    });

    var addedCount = 0;
    var skippedCount = 0;

    for (var i = 0; i < tasks.length; i++) {
      var item = tasks[i];
      var title = (item.title || "").trim();
      if (!title) continue;

      if (existingTitles[title]) {
        skippedCount++;
        continue;
      }

      // 准备任务备注内容
      // 注：Google Tasks API 的 due 字段只支持日期级别，时间部分会被 API 截断丢弃。
      // 为保证精确时间可见，在备注首行显式写入具体截止时间。
      var noteLines = [];
      if (item.due_display) {
        noteLines.push("⏰ 截止时间：" + item.due_display);
      }
      if (item.course) {
        noteLines.push("📚 课程：" + item.course);
      }
      if (item.description) {
        noteLines.push(item.description);
      }

      var taskResource = {
        title: title,
        notes: noteLines.join("\n")
      };

      if (item.due) {
        taskResource.due = item.due; // RFC 3339 格式
      }

      Tasks.Tasks.insert(taskResource, taskListId);
      existingTitles[title] = true; // 避免同批次内重复
      addedCount++;
    }

    return jsonResponse({
      status: "ok",
      added: addedCount,
      skipped: skippedCount,
      message: "同步成功"
    });

  } catch (err) {
    return jsonResponse({
      status: "error",
      message: err.toString()
    });
  }
}

function doGet(e) {
  return jsonResponse({
    status: "ok",
    message: "Google Tasks Webhook 服务运行正常。"
  });
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

