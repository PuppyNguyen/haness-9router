export function TaskSidebar({ tasks, selectedId, onSelect, onNew, busy, onRefresh }) {
  const time = (value) => value ? new Date(value).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' }) : '';
  return <aside class="sidebar" aria-label="Thanh điều hướng">
    <div class="brand"><span class="brand-mark" aria-hidden="true">h</span><span>haness<span class="brand-muted">/agent</span></span></div>
    <button class="new-task-button" onClick={onNew}><span aria-hidden="true">＋</span> Tác vụ mới <kbd>⌘ K</kbd></button>
    <div class="sidebar-label"><span>TÁC VỤ</span><span>{tasks.length}</span></div>
    <nav class="task-list" aria-label="Danh sách tác vụ">{tasks.map((task) => <button key={task.id} class={`task-item${task.id === selectedId ? ' selected' : ''}`} onClick={() => onSelect(task.id)}>
      <span class={`status-dot ${task.status}`} /><span class="task-item-text"><span class="task-item-title">{task.name || task.request}</span><span class="task-item-meta">{(task.workspace || '').split(/[\\/]/).filter(Boolean).pop()} · {task.status} · {time(task.updated_at)}</span></span>
    </button>)}</nav>
    <div class="sidebar-footer"><span class={`status-dot ${busy ? 'running' : 'completed'}`} /><div><strong>{busy ? 'Đang xử lý task' : 'Sẵn sàng'}</strong><small>Haness local</small></div><button class="icon-button" onClick={onRefresh} aria-label="Làm mới">↻</button></div>
  </aside>;
}
