import { useEffect, useRef, useState } from 'preact/hooks';
import { api } from '../api.js';

export function WorkspacePicker({ value, defaultWorkspace, onChange }) {
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState(value || defaultWorkspace);
  const [listing, setListing] = useState(null);
  const [error, setError] = useState('');
  const dialog = useRef(null);
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) {
      if (element.showModal) element.showModal(); else element.setAttribute('open', '');
    } else if (!open && element.open) element.close?.();
  }, [open]);
  async function browse(next) {
    setError(''); setListing(null);
    try { const result = await api('/api/workspaces/browse', { method: 'POST', body: JSON.stringify({ path: next }) }); setPath(result.path); setListing(result); }
    catch (err) { setError(err.message); }
  }
  return <>
    <label>Thư mục làm việc<div class="workspace-picker-row"><input value={value} onInput={(e) => onChange(e.currentTarget.value)} spellcheck="false" aria-label="Đường dẫn workspace" /><button class="button" type="button" onClick={() => { setPath(value || defaultWorkspace); setOpen(true); browse(value || defaultWorkspace); }}>Chọn thư mục</button></div></label>
    {open && <dialog ref={dialog} onClose={() => setOpen(false)} class="directory-dialog" aria-labelledby="directoryTitle"><div class="directory-dialog-header"><div><div class="section-caption">CHỌN WORKSPACE</div><h2 id="directoryTitle">Chọn thư mục làm việc</h2></div><button class="icon-button" aria-label="Đóng" onClick={() => setOpen(false)}>×</button></div>
      <label class="directory-path-label">Đường dẫn đầy đủ<input value={path} onInput={(e) => setPath(e.currentTarget.value)} /></label><div class="workspace-picker-row"><button class="button" onClick={() => browse(path)}>Mở</button><button class="button" onClick={() => { onChange(listing?.path || path); setOpen(false); }}>Dùng thư mục này</button></div>
      {error && <p role="alert">{error}</p>}{listing && <><div class="directory-current">{listing.path}</div><div class="directory-list">{listing.parent && <button class="directory-entry" onClick={() => browse(listing.parent)}>↑ Thư mục cha</button>}{listing.directories.map((item) => <button class="directory-entry" key={item.path} onClick={() => browse(item.path)}>📁 {item.name}</button>)}</div></>}
    </dialog>}
  </>;
}
