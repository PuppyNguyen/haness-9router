export function ConnectionBanner({ state, error, onRetry }) {
  if (state === 'connected') return null;
  return <section class={`connection-banner ${state}`} role="status" aria-live="polite">
    <div><strong>{state === 'checking' ? 'Đang kiểm tra kết nối 9Router…' : 'Chưa kết nối được 9Router'}</strong>
      {state === 'disconnected' && <p>{error || 'Kiểm tra địa chỉ, API key và trạng thái 9Router.'}</p>}</div>
    {state === 'disconnected' && <button class="button" onClick={onRetry}>Thử kết nối lại</button>}
  </section>;
}
