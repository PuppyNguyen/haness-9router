(() => {
  "use strict";
  const token = document.querySelector('meta[name="haness-token"]').content;
  const $ = (id) => document.getElementById(id);
  let selectedTask = null;
  let refreshTimer = null;
  let toastTimer = null;
  let defaultWorkspace = "";
  let currentWorkspace = "";
  const labels = {
    user_request: "Yêu cầu đã nhận", workspace_identity: "Repository được ghi nhận",
    checkpoint: "Checkpoint đã lưu", model_request: "Đã gọi model", assistant_message: "Phản hồi từ agent",
    assistant_tool_call: "Agent gọi công cụ", tool_result: "Kết quả công cụ", runtime_error: "Tác vụ gặp lỗi",
    server_interruption: "Server đã khởi động lại", import_marker: "Tác vụ được nhập"
  };

  function showToast(message) {
    $("toast").textContent = message;
    $("toast").classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $("toast").classList.add("hidden"), 4000);
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (options.method && options.method !== "GET") {
      headers.set("Content-Type", "application/json");
      headers.set("X-Haness-Token", token);
    }
    const response = await fetch(path, {...options, headers, cache: "no-store"});
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.error || `Yêu cầu thất bại (${response.status})`);
    return result;
  }

  function statusClass(status) {
    return ["queued", "running", "paused", "completed", "failed"].includes(status) ? status : "";
  }

  function formatTime(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("vi-VN", {hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short"});
  }

  function renderTaskList(tasks) {
    const list = $("taskList");
    list.replaceChildren();
    $("taskCount").textContent = String(tasks.length);
    for (const task of tasks) {
      const button = document.createElement("button");
      button.className = `task-item${task.id === selectedTask ? " selected" : ""}`;
      button.type = "button";
      button.setAttribute("aria-label", `${task.status}: ${task.request}`);
      const dot = document.createElement("span");
      dot.className = `status-dot ${statusClass(task.status)}`;
      const text = document.createElement("span");
      text.className = "task-item-text";
      const title = document.createElement("span");
      title.className = "task-item-title";
      title.textContent = task.name || task.request;
      const meta = document.createElement("span");
      meta.className = "task-item-meta";
      const folder = (task.workspace || "").split(/[\\/]/).filter(Boolean).pop() || "workspace";
      meta.textContent = `${folder} · ${task.status} · ${formatTime(task.updated_at)}`;
      text.append(title, meta);
      button.append(dot, text);
      button.addEventListener("click", () => selectTask(task.id));
      list.append(button);
    }
  }

  function eventDescription(event) {
    const value = event.payload || {};
    if (event.kind === "user_request") return value.content || "";
    if (event.kind === "assistant_message") {
      const message = value.message || {};
      const toolCalls = message.tool_calls || [];
      return [message.content || "", ...toolCalls.map((call) => `Công cụ: ${call.function?.name || "không rõ"}`)].filter(Boolean).join("\n");
    }
    if (event.kind === "tool_result") return value.content || "";
    if (event.kind === "assistant_tool_call") return `${value.name || "tool"} · ${value.tool_call_id || ""}`;
    if (event.kind === "model_request") return `Model: ${value.model || "không rõ"} · lượt ${value.request_number ?? "?"}`;
    if (event.kind === "checkpoint") return `Giai đoạn: ${value.stage || "đang chạy"}`;
    return value.message || JSON.stringify(value);
  }

  function renderEvents(events) {
    const list = $("eventList");
    list.replaceChildren();
    $("eventCount").textContent = `${events.length} sự kiện`;
    for (const event of events) {
      const row = document.createElement("article");
      row.className = "event";
      const heading = document.createElement("div");
      const kind = document.createElement("span");
      kind.className = "event-kind";
      kind.textContent = labels[event.kind] || event.kind;
      const time = document.createElement("span");
      time.className = "event-time";
      time.textContent = formatTime(event.created_at);
      heading.append(kind, time);
      row.append(heading);
      const description = eventDescription(event);
      if (description) {
        const content = document.createElement("pre");
        content.className = "event-body";
        content.textContent = description;
        row.append(content);
      }
      list.append(row);
    }
  }

  function renderTask(data) {
    const task = data.task;
    $("welcomePanel").classList.add("hidden");
    $("taskPanel").classList.remove("hidden");
    $("taskTitle").textContent = task.name || (task.request.length > 80 ? `${task.request.slice(0, 80)}…` : task.request);
    $("taskMeta").textContent = `Task ${task.id} · Session ${task.session_id} · Model ${task.model || "chưa ghi nhận"} · ${task.workspace}`;
    setWorkspace(task.workspace);
    $("taskRequest").textContent = task.request;
    const status = task.status;
    $("taskStatusText").textContent = ({queued: "Đang chờ worker", running: "Agent đang làm việc", paused: "Đã tạm dừng", completed: "Đã hoàn tất", failed: "Thất bại"})[status] || status;
    const dot = $("taskStatusBanner").querySelector(".status-dot");
    dot.className = `status-dot ${statusClass(status)}`;
    $("stopTask").classList.toggle("hidden", !["queued", "running"].includes(status));
    $("resumeTask").classList.toggle("hidden", status !== "paused" || data.worker_active);
    const finalMessage = [...data.events].reverse().find((event) => event.kind === "assistant_message" && event.payload?.message?.content)?.payload?.message?.content;
    $("finalAnswerCard").classList.toggle("hidden", !finalMessage || status !== "completed");
    $("finalAnswer").textContent = finalMessage || "";
    renderEvents(data.events);
  }

  function setWorkspace(path) {
    if (!path) return;
    currentWorkspace = path;
    const name = path.split(/[\\/]/).filter(Boolean).pop() || path;
    $("workspaceName").textContent = name;
    $("workspacePathText").textContent = path;
    $("workspacePath").title = `Sao chép đường dẫn: ${path}`;
  }

  async function refresh() {
    try {
      const [status, taskResponse, workspace] = await Promise.all([
        api("/api/status"), api("/api/tasks"), api("/api/workspace/status")
      ]);
      defaultWorkspace = status.workspace;
      if (!currentWorkspace) setWorkspace(defaultWorkspace);
      if (!$("taskWorkspaceInput").value) $("taskWorkspaceInput").value = defaultWorkspace;
      $("serverState").textContent = status.busy ? "Đang xử lý task" : "Sẵn sàng";
      $("serverModel").textContent = `Model ${status.model}${status.command_execution.length ? " · command đã bật" : " · command tắt"}`;
      $("serverDot").className = `status-dot ${status.busy ? "running" : "completed"}`;
      $("workspaceButton").title = workspace.status;
      renderTaskList(taskResponse.tasks);
      if (selectedTask) {
        const result = await api(`/api/tasks/${encodeURIComponent(selectedTask)}`);
        renderTask(result);
      }
    } catch (error) {
      $("serverState").textContent = "Mất kết nối";
      $("serverDot").className = "status-dot failed";
      showToast(error.message);
    }
  }

  async function selectTask(taskId) {
    selectedTask = taskId;
    $("welcomePanel").classList.add("hidden");
    $("taskPanel").classList.remove("hidden");
    try {
      renderTask(await api(`/api/tasks/${encodeURIComponent(taskId)}`));
      $("taskWorkspaceInput").value = currentWorkspace;
    }
    catch (error) { showToast(error.message); }
    refresh();
  }

  async function submitTask() {
    const input = $("taskInput");
    const request = input.value.trim();
    if (!request) { input.focus(); return; }
    const button = $("submitTask");
    button.disabled = true;
    try {
      const name = $("taskNameInput").value.trim();
      const workspace = $("taskWorkspaceInput").value.trim() || defaultWorkspace;
      const result = await api("/api/tasks", {method: "POST", body: JSON.stringify({request, name: name || null, workspace})});
      input.value = "";
      $("taskNameInput").value = "";
      selectedTask = result.task_id;
      await refresh();
      showToast(`Đã tạo task ${result.task_id}`);
    } catch (error) { showToast(error.message); }
    finally { button.disabled = false; }
  }

  async function taskAction(action) {
    if (!selectedTask) return;
    const button = action === "stop" ? $("stopTask") : $("resumeTask");
    button.disabled = true;
    try {
      await api(`/api/tasks/${encodeURIComponent(selectedTask)}/${action}`, {method: "POST", body: "{}"});
      await refresh();
      showToast(action === "stop" ? "Đã gửi yêu cầu dừng." : "Đã xếp task để tiếp tục.");
    } catch (error) { showToast(error.message); }
    finally { button.disabled = false; }
  }

  async function showDiff() {
    $("diffPanel").classList.remove("hidden");
    $("gitStatus").textContent = "Đang tải…";
    $("gitDiff").textContent = "Đang tải…";
    try {
      const review = await api("/api/workspace/review", {method: "POST", body: JSON.stringify({workspace: currentWorkspace || defaultWorkspace})});
      $("gitStatus").textContent = review.status || "Không có thay đổi.";
      $("gitDiff").textContent = review.diff || "Không có diff.";
      if (review.truncated) $("gitDiff").textContent += "\n\n[Diff đã bị giới hạn kích thước hiển thị.]";
    } catch (error) { $("gitStatus").textContent = error.message; }
  }

  async function browseDirectory(path) {
    const list = $("directoryList");
    list.replaceChildren();
    list.textContent = "Đang đọc thư mục…";
    try {
      const result = await api("/api/workspaces/browse", {method: "POST", body: JSON.stringify({path})});
      $("directoryPath").value = result.path;
      $("directoryCurrent").textContent = result.path;
      list.replaceChildren();
      if (result.parent) {
        const parent = document.createElement("button");
        parent.className = "directory-entry directory-parent";
        parent.type = "button";
        parent.textContent = "↑ Thư mục cha";
        parent.addEventListener("click", () => browseDirectory(result.parent));
        list.append(parent);
      }
      for (const directory of result.directories) {
        const item = document.createElement("button");
        item.className = "directory-entry";
        item.type = "button";
        item.textContent = `📁 ${directory.name}`;
        item.title = directory.path;
        item.addEventListener("click", () => browseDirectory(directory.path));
        list.append(item);
      }
      if (!result.directories.length) list.textContent = "Không có thư mục con.";
      if (result.truncated) showToast("Đã giới hạn danh sách ở 200 thư mục.");
    } catch (error) {
      list.textContent = error.message;
      $("directoryCurrent").textContent = "";
    }
  }

  async function checkRouter() {
    const button = $("routerCheck");
    const state = $("routerState");
    button.disabled = true;
    state.textContent = "Đang kiểm tra…";
    try {
      const result = await api("/api/doctor", {method: "POST", body: "{}"});
      state.textContent = `9Router OK · ${result.model}`;
      showToast("Kết nối 9Router thành công.");
    } catch (error) {
      state.textContent = "9Router lỗi";
      showToast(error.message);
    } finally { button.disabled = false; }
  }

  $("submitTask").addEventListener("click", submitTask);
  $("taskInput").addEventListener("keydown", (event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") submitTask(); });
  $("focusComposer").addEventListener("click", () => { selectedTask = null; $("taskPanel").classList.add("hidden"); $("welcomePanel").classList.remove("hidden"); $("taskInput").focus(); });
  $("refreshButton").addEventListener("click", refresh);
  $("workspaceButton").addEventListener("click", showDiff);
  $("workspacePath").addEventListener("click", async () => {
    const path = $("workspacePathText").textContent.trim();
    try { await navigator.clipboard.writeText(path); showToast("Đã sao chép đường dẫn workspace."); }
    catch { showToast(path); }
  });
  $("browseWorkspace").addEventListener("click", () => {
    $("directoryDialog").showModal();
    browseDirectory($("taskWorkspaceInput").value.trim() || defaultWorkspace);
  });
  $("openDirectory").addEventListener("click", () => browseDirectory($("directoryPath").value.trim()));
  $("directoryPath").addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); browseDirectory($("directoryPath").value.trim()); } });
  $("useDirectory").addEventListener("click", () => {
    const path = $("directoryCurrent").textContent;
    if (!path) return;
    $("taskWorkspaceInput").value = path;
    setWorkspace(path);
    $("directoryDialog").close();
  });
  $("routerCheck").addEventListener("click", checkRouter);
  $("closeDiff").addEventListener("click", () => $("diffPanel").classList.add("hidden"));
  $("stopTask").addEventListener("click", () => taskAction("stop"));
  $("resumeTask").addEventListener("click", () => taskAction("resume"));
  document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => { $("taskInput").value = button.dataset.prompt; $("taskInput").focus(); }));
  window.addEventListener("keydown", (event) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); $("focusComposer").click(); } });
  refresh();
  refreshTimer = setInterval(refresh, 2500);
  window.addEventListener("beforeunload", () => clearInterval(refreshTimer));
})();
