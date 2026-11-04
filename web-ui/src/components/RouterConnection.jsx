export function RouterConnection({ state, baseUrl, setBaseUrl, onConnect, onDisconnect, error }) {
  return <section class="router-connection" aria-label="Kết nối 9Router">
    <label for="routerUrl">9Router Base URL</label>
    <div class="router-connection-row"><input id="routerUrl" type="url" value={baseUrl} placeholder="http://localhost:20128/v1" onInput={(event) => setBaseUrl(event.currentTarget.value)} />
      {state === 'connected' && <button class="button button-quiet" type="button" onClick={onDisconnect}>Ngắt kết nối</button>}
      {state !== 'connected' && <button class="button" type="button" disabled={state === 'checking' || !baseUrl.trim()} onClick={onConnect}>{state === 'checking' ? 'Đang kiểm tra…' : 'Kết nối / kết nối lại'}</button>}
    </div>
    <small>API key lấy từ cấu hình Haness và chỉ được gửi đến địa chỉ này khi kết nối. Kiểm tra địa chỉ trước khi kết nối; dùng HTTPS cho router trên server.</small>
    {error && state === 'disconnected' && <p class="router-connection-error" role="status">{error}</p>}
  </section>;
}
