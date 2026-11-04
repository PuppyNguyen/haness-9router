const token = document.querySelector('meta[name="haness-token"]')?.content || '';

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.method && options.method !== 'GET') {
    headers.set('Content-Type', 'application/json');
    headers.set('X-Haness-Token', token);
  }
  const response = await fetch(path, { ...options, headers, cache: 'no-store' });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `Yêu cầu thất bại (${response.status})`);
  return result;
}
