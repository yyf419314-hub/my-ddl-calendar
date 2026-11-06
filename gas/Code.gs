/**
 * Google Apps Script Webhook: 接收外部任务并同步至 Google Tasks
 * 
 * 部署步骤：
 * 1. 在浏览器打开 https://script.google.com/ ，新建一个项目。
 * 2. 将本文件代码完整粘贴替换 Code.gs。
 * 3. （可选安全防护）在下方 AUTH_TOKEN 填入自定义密钥；并在本地仓库的 webhook_secret.txt 中填入相同密钥。
 * 4. 在左侧菜单栏点击「服务 (Services) +」，找到「Tasks API」并添加启用。
 * 5. 点击右上角「部署 (Deploy)」->「新建部署 (New deployment)」。
 * 6. 种类选择「网页应用 (Web app)」：
 *    - 说明 (Description): DDL Webhook
 *    - 执行身份 (Execute as): 我 (Me)
 *    - 谁可以访问 (Who has access): 任何人 (Anyone)
 * 7. 点击「部署」，授权权限后复制「网页应用网址 (Web App URL)」。
 * 8. 将该网址粘贴到本地仓库的 webhook_url.txt 文件中。
 */

// 可选：设置 Webhook 访问密钥。如果设置，客户端请求必须携带匹配的 token；留空则不开启密钥验证。
var AUTH_TOKEN = "";

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse({ status: "error", message: "缺少请求体数据" }, 400);
    }

    var data = JSON.parse(e.postData.contents);

    // 密钥校验
    if (AUTH_TOKEN && AUTH_TOKEN.trim() !== "") {
      if (!data.token || data.token !== AUTH_TOKEN) {
        return jsonResponse({ status: "error", message: "身份验证失败：密钥错误或缺失" }, 401);
      }
    }

    var tasks = data.tasks;
    if (!Array.isArray(tasks) || tasks.length === 0) {
      return jsonResponse({ status: "ok", added: 0, updated: 0, skipped: 0, message: "无任务需要同步" });
    }

    var taskListId = "@default";

    // 1. 获取所有现有任务（包含已完成和隐藏任务，用于真正幂等与防止死灰复燃）
    var existingTasks = [];
    var pageToken = null;
    do {
      var res = Tasks.Tasks.list(taskListId, {
        maxResults: 100,
        pageToken: pageToken,
        showCompleted: true,
        showHidden: true
      });
      if (res.items && res.items.length > 0) {
        existingTasks = existingTasks.concat(res.items);
      }
      pageToken = res.nextPageToken;
    } while (pageToken);

    // 2. 建立索引：优先按 [ddl-id:xxx] 索引，兼容旧版本按小写标题索引
    var tasksById = {};
    var tasksByTitle = {};

    existingTasks.forEach(function(t) {
      var notes = t.notes || "";
      var idMatch = notes.match(/\[ddl-id:([^\]\s]+)\]/);
      if (idMatch && idMatch[1]) {
        tasksById[idMatch[1]] = t;
      }
      if (t.title) {
        var normTitle = t.title.trim().toLowerCase();
        // 优先保留未完成任务或最新任务
        if (!tasksByTitle[normTitle] || tasksByTitle[normTitle].status === "completed") {
          tasksByTitle[normTitle] = t;
        }
      }
    });

    var addedCount = 0;
    var updatedCount = 0;
    var skippedCount = 0;

    for (var i = 0; i < tasks.length; i++) {
      var item = tasks[i];
      var title = (item.title || "").trim();
      if (!title) continue;

      var taskId = item.id ? String(item.id).trim() : "";
      var normTitle = title.toLowerCase();

      // 构建规范的 notes 内容，包含截止时间、课程、说明以及唯一的 ddl-id 标记
      var noteLines = [];
      if (item.due_display) {
        noteLines.push("⏰ 截止时间：" + item.due_display);
      }
      if (item.course) {
        noteLines.push("📚 课程：" + item.course);
      }
      if (item.description) {
        // 清理原有 description 中可能重复的截止时间前缀
        var cleanDesc = item.description.replace(/^【截止时间:[^】]+】\s*/, "");
        if (cleanDesc) {
          noteLines.push(cleanDesc);
        }
      }
      if (taskId) {
        noteLines.push("[ddl-id:" + taskId + "]");
      }

      var fullNotes = noteLines.join("\n");

      // 匹配现有任务：先查 id，没有 id 再查标题
      var matchedTask = null;
      if (taskId && tasksById[taskId]) {
        matchedTask = tasksById[taskId];
      } else if (tasksByTitle[normTitle]) {
        matchedTask = tasksByTitle[normTitle];
      }

      if (matchedTask) {
        // 若任务已被用户打勾完成，绝不重新插入，避免“死灰复燃”
        if (matchedTask.status === "completed") {
          skippedCount++;
          continue;
        }

        // 若任务未完成，使用 patch 更新标题、备注和日期
        var patchResource = {
          title: title,
          notes: fullNotes
        };
        if (item.due) {
          patchResource.due = item.due;
        }

        Tasks.Tasks.patch(patchResource, taskListId, matchedTask.id);
        updatedCount++;

        // 更新本地索引
        if (taskId) tasksById[taskId] = matchedTask;
        tasksByTitle[normTitle] = matchedTask;
      } else {
        // 任务不存在，创建新任务
        var newTaskResource = {
          title: title,
          notes: fullNotes
        };
        if (item.due) {
          newTaskResource.due = item.due;
        }

        var created = Tasks.Tasks.insert(newTaskResource, taskListId);
        addedCount++;

        // 记入索引避免同批次内重复
        if (taskId) tasksById[taskId] = created;
        tasksByTitle[normTitle] = created;
      }
    }

    return jsonResponse({
      status: "ok",
      added: addedCount,
      updated: updatedCount,
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
