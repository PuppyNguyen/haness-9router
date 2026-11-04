import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/preact';
import { App } from './App.jsx';
import { TaskDetail } from './components/TaskDetail.jsx';

const status = { workspace: '/tmp/project', model: 'model-a', busy: false };
const tasks = { tasks: [] };
const connectedModels = { connected: true, models: ['model-a', 'model-b'], selected_model_id: null, base_url: 'http://localhost:20128/v1' };
function response(body, ok = true, statusCode = 200) { return { ok, status: statusCode, json: async () => body }; }

describe('router connection and model catalog', () => {
  beforeEach(() => { vi.stubGlobal('fetch', vi.fn(async (url) => url === '/api/models' ? response(connectedModels) : url === '/api/status' ? response(status) : url === '/api/tasks' ? response(tasks) : response({}))); });
  afterEach(() => vi.unstubAllGlobals());

  it('gates task controls until the router connects', async () => {
    fetch.mockImplementation(async (url) => url === '/api/models' ? response({ connected: false, models: [], base_url: 'http://localhost:20128/v1', error: 'Router offline' }) : url === '/api/status' ? response(status) : url === '/api/tasks' ? response(tasks) : response({}));
    render(<App />);
    expect(screen.getByRole('button', { name: /Gửi yêu cầu/ }).disabled).toBe(true);
    expect((await screen.findByLabelText('Yêu cầu coding agent')).disabled).toBe(true);
    expect(screen.getByLabelText('Model cho tác vụ').disabled).toBe(true);
  });

  it('loads every live model and sends selected model in task request', async () => {
    let submitted;
    fetch.mockImplementation(async (url, options = {}) => {
      if (url === '/api/models') return response(connectedModels);
      if (url === '/api/status') return response(status);
      if (url === '/api/tasks' && options.method === 'POST') { submitted = JSON.parse(options.body); return response({ task_id: 'task-1' }); }
      if (url === '/api/tasks') return response(tasks);
      return response({});
    });
    render(<App />);
    const input = await screen.findByLabelText('Yêu cầu coding agent');
    await screen.findByRole('option', { name: 'model-b' });
    expect(screen.queryByRole('button', { name: 'Quản lý model' })).toBeNull();
    fireEvent.change(screen.getByLabelText('Model cho tác vụ'), { target: { value: 'model-b' } });
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/models/select', expect.objectContaining({ method: 'POST' })));
    fireEvent.input(input, { target: { value: 'Sửa lỗi' } });
    fireEvent.click(screen.getByRole('button', { name: /Gửi yêu cầu/ }));
    await waitFor(() => expect(submitted?.model).toBe('model-b'));
  });

  it('disconnects and reconnects using an editable Base URL', async () => {
    fetch.mockImplementation(async (url, options = {}) => {
      if (url === '/api/models') return response(connectedModels);
      if (url === '/api/status') return response(status);
      if (url === '/api/tasks') return response(tasks);
      if (url === '/api/connection/disconnect') return response({ connected: false });
      if (url === '/api/connection/connect') return response({ ...connectedModels, base_url: JSON.parse(options.body).base_url });
      return response({});
    });
    render(<App />);
    await screen.findByRole('button', { name: 'Ngắt kết nối' });
    fireEvent.click(screen.getByRole('button', { name: 'Ngắt kết nối' }));
    await screen.findByRole('button', { name: 'Kết nối / kết nối lại' });
    fireEvent.input(screen.getByLabelText('9Router Base URL'), { target: { value: 'https://router.example/v1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Kết nối / kết nối lại' }));
    await waitFor(() => expect(fetch.mock.calls.some(([url, options]) => url === '/api/connection/connect' && JSON.parse(options.body).base_url === 'https://router.example/v1')).toBe(true));
    await screen.findByRole('button', { name: 'Ngắt kết nối' });
    expect(screen.getByRole('button', { name: /Gửi yêu cầu/ }).disabled).toBe(false);
  });

  it('disables resume when router is disconnected', () => {
    render(<TaskDetail data={{ task: { id: 't', session_id: 's', status: 'paused', model: 'model-a', workspace: '/tmp', request: 'task' }, events: [], worker_active: false }} connected={false} busy={false} onResume={() => {}} onStop={() => {}} />);
    expect(screen.getByRole('button', { name: 'Tiếp tục' }).disabled).toBe(true);
  });
});
