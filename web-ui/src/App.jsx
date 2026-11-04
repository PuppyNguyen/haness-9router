import { useCallback, useEffect, useState } from 'preact/hooks';
import { api } from './api.js';
import { ConnectionBanner } from './components/ConnectionBanner.jsx';
import { TaskSidebar } from './components/TaskSidebar.jsx';
import { TaskComposer } from './components/TaskComposer.jsx';
import { TaskDetail } from './components/TaskDetail.jsx';
import { GitReview } from './components/GitReview.jsx';
import { RouterConnection } from './components/RouterConnection.jsx';

export function App() {
  const [connection, setConnection] = useState('checking');
  const [connectionError, setConnectionError] = useState('');
  const [models, setModels] = useState([]); const [baseUrl, setBaseUrl] = useState('');
  const [model, setModel] = useState(''); const [status, setStatus] = useState(null);
  const [tasks, setTasks] = useState([]); const [selectedId, setSelectedId] = useState(null); const [taskData, setTaskData] = useState(null);
  const [request, setRequest] = useState(''); const [name, setName] = useState(''); const [workspace, setWorkspace] = useState('');
  const [reviewOpen, setReviewOpen] = useState(false); const [gitStatus, setGitStatus] = useState(''); const [gitDiff, setGitDiff] = useState('');
  const [toast, setToast] = useState('');

  const loadModels = useCallback(async () => {
    setConnection('checking'); setConnectionError('');
    try {
      const result = await api('/api/models');
      setModels(result.models || []); setBaseUrl(result.base_url || '');
      if (!result.connected) { setConnection('disconnected'); setConnectionError(result.error || 'Kiểm tra địa chỉ, API key và trạng thái 9Router.'); return; }
      setConnection('connected');
      let configuredModel = '';
      try { configuredModel = (await api('/api/status')).model; } catch { configuredModel = status?.model || ''; }
      const initial = [result.selected_model_id, configuredModel, result.models[0]].find((item) => item && result.models.includes(item)) || '';
      setModel((current) => result.models.includes(current) ? current : initial);
    } catch (error) {
      setModels([]); setConnection('disconnected'); setConnectionError(error.message);
    }
  }, [status?.model]);

  const refresh = useCallback(async () => {
    try {
      const [nextStatus, taskResult] = await Promise.all([api('/api/status'), api('/api/tasks')]);
      setStatus(nextStatus); setTasks(taskResult.tasks || []);
      setWorkspace((current) => current || nextStatus.workspace);
      if (selectedId) setTaskData(await api(`/api/tasks/${encodeURIComponent(selectedId)}`));
    } catch (error) { setToast(error.message); }
  }, [selectedId]);

  useEffect(() => { loadModels(); refresh(); }, []);
  useEffect(() => { const timer = setInterval(refresh, 2500); return () => clearInterval(timer); }, [refresh]);
  useEffect(() => { if (!toast) return undefined; const timer = setTimeout(() => setToast(''), 4000); return () => clearTimeout(timer); }, [toast]);
  useEffect(() => {
    const onKey = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault(); setSelectedId(null); setTaskData(null); document.getElementById('taskInput')?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  async function chooseModel(id) {
    setModel(id);
    try { await api('/api/models/select', { method: 'POST', body: JSON.stringify({ model_id: id }) }); }
    catch (error) { setToast(error.message); await loadModels(); }
  }
  async function connectRouter() {
    setConnection('checking'); setConnectionError('');
    try {
      const result = await api('/api/connection/connect', { method: 'POST', body: JSON.stringify({ base_url: baseUrl }) });
      setBaseUrl(result.base_url); setModels(result.models || []); setConnection('connected');
      const next = result.models.includes(model) ? model : [result.selected_model_id, status?.model].find((item) => item && result.models.includes(item)) || '';
      setModel(next);
      if (next) await api('/api/models/select', { method: 'POST', body: JSON.stringify({ model_id: next }) });
      setToast('Đã kết nối 9Router và tải danh sách model.');
    } catch (error) { setConnection('disconnected'); setConnectionError(error.message); setModels([]); }
  }
  async function disconnectRouter() {
    try { await api('/api/connection/disconnect', { method: 'POST', body: '{}' }); setConnection('disconnected'); setModels([]); setToast('Đã ngắt kết nối 9Router.'); }
    catch (error) { setToast(error.message); }
  }
  async function submitTask(event) {
    event.preventDefault(); if (!request.trim() || !model || connection !== 'connected') return;
    try {
      const result = await api('/api/tasks', { method: 'POST', body: JSON.stringify({ request: request.trim(), name: name.trim() || null, workspace: workspace || status?.workspace, model }) });
      setRequest(''); setName(''); setSelectedId(result.task_id); setTaskData(null); setToast(`Đã tạo task ${result.task_id}`); await refresh();
    } catch (error) { setToast(error.message); if (error.message.includes('9Router')) await loadModels(); }
  }
  async function taskAction(action) {
    if (!selectedId) return;
    try { await api(`/api/tasks/${encodeURIComponent(selectedId)}/${action}`, { method: 'POST', body: '{}' }); await refresh(); setToast(action === 'stop' ? 'Đã gửi yêu cầu dừng.' : 'Đã xếp task để tiếp tục.'); }
    catch (error) { setToast(error.message); if (action === 'resume') await loadModels(); }
  }
  async function openTask(id) {
    setSelectedId(id); setTaskData(null);
    try { setTaskData(await api(`/api/tasks/${encodeURIComponent(id)}`)); }
    catch (error) { setToast(error.message); }
  }
  async function showReview() {
    setReviewOpen(true); setGitStatus('Đang tải…'); setGitDiff('Đang tải…');
    try { const result = await api('/api/workspace/review', { method: 'POST', body: JSON.stringify({ workspace: taskData?.task.workspace || workspace || status?.workspace }) }); setGitStatus(result.status || 'Không có thay đổi.'); setGitDiff(result.diff || 'Không có diff.'); }
    catch (error) { setGitStatus(error.message); setGitDiff(''); }
  }
  async function copyWorkspace() { try { await navigator.clipboard.writeText(taskData?.task.workspace || workspace || status?.workspace || ''); setToast('Đã sao chép đường dẫn workspace.'); } catch { setToast(workspace || 'Không thể sao chép đường dẫn'); } }
  const busy = !!status?.busy;
  const newTask = () => { setSelectedId(null); setTaskData(null); document.getElementById('taskInput')?.focus(); };

  return <div class="app-shell">
    <TaskSidebar tasks={tasks} selectedId={selectedId} onSelect={openTask} onNew={newTask} busy={busy} onRefresh={refresh} />
    <main class="main-area"><header class="topbar"><div class="breadcrumb" aria-label="Workspace hiện tại"><span class="workspace-label">Workspace hiện tại</span><strong>{(taskData?.task.workspace || workspace || status?.workspace || 'Đang tải…').split(/[\\/]/).filter(Boolean).pop()}</strong><button class="workspace-path" onClick={copyWorkspace} type="button"><span>{taskData?.task.workspace || workspace || status?.workspace || 'Đang tải đường dẫn…'}</span> ⧉</button></div><div class="topbar-meta"><span class="connection"><i />{connection === 'connected' ? `9Router · ${model || 'Chọn model'}` : connection === 'checking' ? 'Đang kiểm tra' : 'Ngoại tuyến'}</span><button class="text-button" onClick={showReview}>Git diff</button></div></header>
      <div class="content"><RouterConnection state={connection} baseUrl={baseUrl} setBaseUrl={setBaseUrl} onConnect={connectRouter} onDisconnect={disconnectRouter} error={connectionError} /><ConnectionBanner state={connection} error={connectionError} onRetry={connectRouter} />
        {!selectedId || !taskData ? <TaskComposer request={request} setRequest={setRequest} name={name} setName={setName} workspace={workspace} setWorkspace={setWorkspace} defaultWorkspace={status?.workspace || ''} models={models} model={model} connected={connection === 'connected'} busy={busy} onModelChange={chooseModel} onSubmit={submitTask} /> : <TaskDetail data={taskData} connected={connection === 'connected'} busy={busy} onResume={() => taskAction('resume')} onStop={() => taskAction('stop')} />}
      </div>
      <GitReview open={reviewOpen} status={gitStatus} diff={gitDiff} onClose={() => setReviewOpen(false)} />
      {toast && <div class="toast" role="status">{toast}</div>}
    </main>
  </div>;
}
