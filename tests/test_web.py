import http.client
import contextlib
import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from agent_harness.runtime import Runtime
from agent_harness.provider import ProviderError
from agent_harness.store import Store
from agent_harness.webserver import LocalWebServer
from agent_harness.cli import main


class FakeConfig:
    def __init__(self, workspace):
        self.workspace = Path(workspace)
        self.model = "fake/model"
        self.fallback_model = None
        self.fallback_tool_calling = False
        self.max_requests = 4
        self.max_seconds = 10
        self.timeout = 0.1
        self.retries = 0
        self.allow_commands = ()
        self.api_key = "test-secret-value"
        self.base_url = "http://127.0.0.1:20128/v1"


class FakeClient:
    def __init__(self, block=False):
        self.calls = 0
        self.block = block
        self.started = threading.Event()
        self.release = threading.Event()
        self.models = ["fake/model", "fake/alternate"]
        self.catalog_error = None
        self.base_url = "http://127.0.0.1:20128/v1"

    def list_models(self):
        if self.catalog_error:
            raise self.catalog_error
        return list(self.models)

    def chat(self, model, messages, tools=None, *, max_tokens=4096):
        self.calls += 1
        if self.block:
            self.started.set()
            self.release.wait(2)
        if self.calls == 1:
            return {"model": "fake/model", "choices": [{"message": {
                "role": "assistant", "tool_calls": [{"id": "write-once", "type": "function",
                    "function": {"name": "write_file", "arguments": json.dumps({"path": "created.txt", "content": "hello"})}}]}}]}
        return {"model": "fake/model", "choices": [{"message": {"role": "assistant", "content": "Task finished."}}]}


class WebServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.store = Store(Path(self.temp.name) / "state.sqlite3")
        self.config = FakeConfig(self.root)
        self.client = FakeClient()
        self.runtime = Runtime(self.config, self.client, self.store)
        self.server = LocalWebServer(self.config, self.store, self.runtime, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.stop_worker()
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()
        self.store.close()
        self.temp.cleanup()

    def request(self, method, path, payload=None, token=None, origin=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["X-Haness-Token"] = token
        if origin:
            headers["Origin"] = origin
        body = json.dumps(payload) if payload is not None else None
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        result = response.read()
        status = response.status
        content_type = response.getheader("Content-Type")
        conn.close()
        return status, content_type, result

    def token(self):
        status, _, html = self.request("GET", "/")
        self.assertEqual(status, 200)
        marker = b'<meta name="haness-token" content="'
        start = html.index(marker) + len(marker)
        end = html.index(b'"', start)
        return html[start:end].decode()

    def test_status_does_not_expose_api_key_and_task_runs_in_background(self):
        status, _, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertNotIn(self.config.api_key.encode(), body)
        status_data = json.loads(body)
        self.assertEqual(status_data["workspace"], str(self.root))
        self.assertEqual(status_data["workspace_name"], "repo")
        token = self.token()
        status, _, body = self.request("POST", "/api/tasks", {"request": "Create a file"}, token)
        self.assertEqual(status, 202, body)
        result = json.loads(body)
        self.assertTrue(result["task_id"])
        self.assertTrue(result["session_id"])
        task_id = result["task_id"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status, _, body = self.request("GET", f"/api/tasks/{task_id}")
            task = json.loads(body)
            if task["task"]["status"] == "completed":
                break
            time.sleep(0.03)
        self.assertEqual(task["task"]["status"], "completed")
        self.assertEqual((self.root / "created.txt").read_text(), "hello")
        self.assertIn("Task finished.", json.dumps(task["events"]))
        self.assertNotIn(self.config.api_key, json.dumps(task))

    def test_model_catalog_is_read_only_and_selection_is_authenticated(self):
        status, _, body = self.request("GET", "/api/models")
        self.assertEqual(status, 200, body)
        data = json.loads(body)
        self.assertTrue(data["connected"])
        self.assertEqual(data["models"], ["fake/model", "fake/alternate"])
        token = self.token()
        status, _, body = self.request("POST", "/api/models/select", {"model_id": "fake/alternate"}, token)
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)["selected_model_id"], "fake/alternate")
        status, _, body = self.request("GET", "/api/model-profiles")
        self.assertEqual(status, 404)
        self.assertEqual(self.client.models, ["fake/model", "fake/alternate"])

    def test_disconnect_gates_tasks_and_reconnect_uses_selected_base_url(self):
        token = self.token()
        status, _, body = self.request("POST", "/api/connection/disconnect", {}, token)
        self.assertEqual(status, 200, body)
        self.assertFalse(json.loads(self.request("GET", "/api/models")[2])["connected"])
        before = len(self.store.all_tasks())
        status, _, _ = self.request("POST", "/api/tasks", {"request": "offline"}, token)
        self.assertEqual(status, 503)
        self.assertEqual(len(self.store.all_tasks()), before)
        status, _, body = self.request("POST", "/api/connection/connect", {"base_url": "https://router.example/v1"}, token)
        self.assertEqual(status, 200, body)
        self.assertEqual(self.client.base_url, "https://router.example/v1")
        self.assertEqual(self.store.setting("web.router_base_url"), "https://router.example/v1")
        self.assertTrue(json.loads(self.request("GET", "/api/models")[2])["connected"])

    def test_reconnect_rejects_invalid_url_without_changing_endpoint(self):
        token = self.token()
        original = self.client.base_url
        status, _, body = self.request("POST", "/api/connection/connect", {"base_url": "file:///etc/passwd"}, token)
        self.assertEqual(status, 400, body)
        self.assertEqual(self.client.base_url, original)

    def test_saved_router_url_and_disconnected_state_survive_server_restart(self):
        self.store.set_setting("web.router_base_url", "https://router.example/v1")
        self.store.set_setting("web.router_disconnected", "true")
        replacement = LocalWebServer(self.config, self.store, self.runtime, port=0)
        try:
            self.assertEqual(self.client.base_url, "https://router.example/v1")
            self.assertFalse(replacement.live_models()["connected"])
        finally:
            replacement.server_close()

    def test_create_and_resume_fail_closed_when_model_catalog_is_offline(self):
        token = self.token()
        self.client.catalog_error = ProviderError("9Router authentication failed; verify the configured API key", 401)
        before = len(self.store.all_tasks())
        status, _, body = self.request("POST", "/api/tasks", {"request": "must not start"}, token)
        self.assertEqual(status, 503, body)
        self.assertEqual(len(self.store.all_tasks()), before)
        task_id, _ = self.store.create_task(self.root, "paused", "fake/model")
        self.store.set_status(task_id, "paused")
        status, _, body = self.request("POST", f"/api/tasks/{task_id}/resume", {}, token)
        self.assertEqual(status, 503, body)
        self.assertEqual(self.store.task(task_id)["status"], "paused")
        self.assertFalse(self.server.worker_busy())
        self.assertNotIn(self.config.api_key, body.decode())

    def test_create_rejects_model_missing_from_live_catalog_before_persisting_task(self):
        token = self.token()
        before = len(self.store.all_tasks())
        status, _, body = self.request("POST", "/api/tasks", {
            "request": "must not start", "model": "not-in-catalog"
        }, token)
        self.assertEqual(status, 409, body)
        self.assertEqual(len(self.store.all_tasks()), before)

    def test_task_uses_selected_workspace_and_persists_custom_name(self):
        chosen = Path(self.temp.name) / "project with spaces" / "日本語"
        chosen.mkdir(parents=True)
        token = self.token()
        status, _, body = self.request("POST", "/api/tasks", {
            "request": "Create a file", "name": "Sửa phần đăng nhập", "workspace": str(chosen)
        }, token)
        self.assertEqual(status, 202, body)
        task_id = json.loads(body)["task_id"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            _, _, body = self.request("GET", f"/api/tasks/{task_id}")
            task = json.loads(body)
            if task["task"]["status"] == "completed":
                break
            time.sleep(0.03)
        self.assertEqual(task["task"]["status"], "completed")
        self.assertEqual(task["task"]["name"], "Sửa phần đăng nhập")
        self.assertEqual(task["task"]["workspace"], str(chosen.resolve()))
        self.assertEqual((chosen / "created.txt").read_text(), "hello")
        self.assertFalse((self.root / "created.txt").exists())

    def test_directory_browser_only_lists_directories_and_requires_token(self):
        (self.root / "child folder").mkdir()
        (self.root / "file.txt").write_text("not listed")
        status, _, _ = self.request("POST", "/api/workspaces/browse", {"path": str(self.root)})
        self.assertEqual(status, 403)
        status, _, body = self.request("POST", "/api/workspaces/browse", {"path": str(self.root)}, self.token())
        self.assertEqual(status, 200, body)
        result = json.loads(body)
        self.assertEqual([item["name"] for item in result["directories"]], ["child folder"])
        status, _, body = self.request("POST", "/api/workspaces/browse", {"path": str(self.root / "missing")}, self.token())
        self.assertEqual(status, 400)

    def test_mutations_require_token_and_same_origin(self):
        status, _, body = self.request("POST", "/api/tasks", {"request": "hello"})
        self.assertEqual(status, 403)

    def test_router_doctor_is_explicit_and_does_not_return_credentials(self):
        token = self.token()
        status, _, body = self.request("POST", "/api/doctor", {}, token)
        self.assertEqual(status, 200, body)
        result = json.loads(body)
        self.assertTrue(result["ok"])
        self.assertEqual(result["model"], "fake/model")
        self.assertNotIn(self.config.api_key.encode(), body)
        token = self.token()
        status, _, _ = self.request("POST", "/api/tasks", {"request": "hello"}, token,
                                    origin="http://evil.example")
        self.assertEqual(status, 403)

    def test_rejects_host_header_outside_loopback(self):
        status, _, _ = self.request("GET", "/api/status", host="attacker.example")
        self.assertEqual(status, 403)

    def test_server_recovers_stale_running_tasks_as_paused(self):
        task_id, _ = self.store.create_task(self.root, "interrupted", "fake/model")
        self.store.set_status(task_id, "running")
        recovered = LocalWebServer(self.config, self.store, self.runtime, port=0)
        try:
            self.assertEqual(self.store.task(task_id)["status"], "paused")
            kinds = [event["kind"] for event in self.store.events(task_id)]
            self.assertIn("server_interruption", kinds)
        finally:
            recovered.server_close()

    def test_cli_rejects_public_bind_addresses(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["web", "--host", "0.0.0.0"])
        self.assertEqual(caught.exception.code, 2)

    def test_malformed_and_oversized_bodies_and_unknown_resume_are_rejected(self):
        token = self.token()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("POST", "/api/tasks", b"{bad", {
            "Host": f"127.0.0.1:{self.port}", "Content-Type": "application/json",
            "X-Haness-Token": token
        })
        response = conn.getresponse()
        self.assertEqual(response.status, 400)
        response.read()
        conn.close()
        status, _, _ = self.request("POST", "/api/tasks", {"request": "x" * 70_000}, token)
        self.assertEqual(status, 413)
        status, _, _ = self.request("POST", "/api/tasks/missing/resume", {}, token)
        self.assertEqual(status, 404)

    def test_task_event_response_is_bounded(self):
        task_id, _ = self.store.create_task(self.root, "large event", "fake/model")
        self.store.event(task_id, "assistant_message", {"message": {"content": "x" * 2_000_000}})
        status, _, body = self.request("GET", f"/api/tasks/{task_id}")
        self.assertEqual(status, 200)
        self.assertLess(len(body), 512 * 1024)
        payload = json.loads(body)
        self.assertIn("[truncated]", payload["events"][0]["payload"]["message"]["content"])

    def test_single_active_worker_rejects_competing_task(self):
        self.client.block = True
        token = self.token()
        status, _, _ = self.request("POST", "/api/tasks", {"request": "first"}, token)
        self.assertEqual(status, 202)
        self.assertTrue(self.client.started.wait(1))
        status, _, body = self.request("POST", "/api/tasks", {"request": "second"}, token)
        self.assertEqual(status, 409)
        self.assertIn(b"busy", body)
        status, _, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200, body)
        self.assertTrue(json.loads(body)["busy"])
        self.client.release.set()

    def test_stop_then_resume_does_not_repeat_a_completed_tool_action(self):
        class Client:
            calls = 0
            def list_models(inner): return ["fake/model"]
            def chat(inner, model, messages, tools):
                inner.calls += 1
                if inner.calls == 1:
                    return {"model": "fake/model", "choices": [{"message": {
                        "role": "assistant", "tool_calls": [{"id": "write-once", "type": "function",
                            "function": {"name": "write_file", "arguments": json.dumps({"path": "once.txt", "content": "once"})}}]}}]}
                return {"model": "fake/model", "choices": [{"message": {"role": "assistant", "content": "done"}}]}
        client = Client()
        self.runtime.client = client
        tool_saved = threading.Event()
        release_tool = threading.Event()
        original_event = self.store.event
        def event_with_pause(task_id, kind, payload, event_id=None):
            result = original_event(task_id, kind, payload, event_id)
            if kind == "tool_result":
                tool_saved.set()
                release_tool.wait(2)
            return result
        self.store.event = event_with_pause
        token = self.token()
        status, _, body = self.request("POST", "/api/tasks", {"request": "write once"}, token)
        self.assertEqual(status, 202)
        task_id = json.loads(body)["task_id"]
        self.assertTrue(tool_saved.wait(2))
        self.assertEqual((self.root / "once.txt").read_text(), "once")
        status, _, _ = self.request("POST", f"/api/tasks/{task_id}/stop", {}, token)
        self.assertEqual(status, 200)
        release_tool.set()
        deadline = time.monotonic() + 2
        while self.server.worker_busy() and time.monotonic() < deadline:
            time.sleep(0.02)
        status, _, body = self.request("GET", f"/api/tasks/{task_id}")
        self.assertEqual(json.loads(body)["task"]["status"], "paused")
        status, _, _ = self.request("POST", f"/api/tasks/{task_id}/resume", {}, token)
        self.assertEqual(status, 202)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            _, _, body = self.request("GET", f"/api/tasks/{task_id}")
            if json.loads(body)["task"]["status"] == "completed":
                break
            time.sleep(0.03)
        task = json.loads(body)
        self.assertEqual(task["task"]["status"], "completed")
        actions = [event for event in task["events"] if event["kind"] == "assistant_tool_call"]
        self.assertEqual(len(actions), 1)
        self.assertEqual((self.root / "once.txt").read_text(), "once")

    def test_page_uses_built_assets_and_rejects_unknown_task(self):
        status, content_type, html = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertNotIn(b"test-secret-value", html)
        self.assertIn("Haness · Agent Workspace", html.decode("utf-8"))
        self.assertIn(b"/assets/index-", html)
        asset = html.split(b'src="/assets/', 1)[1].split(b'"', 1)[0]
        status, content_type, js = self.request("GET", f"/assets/{asset.decode()}")
        self.assertEqual(status, 200)
        self.assertIn("javascript", content_type)
        self.assertIn(b"9Router", js)
        status, _, _ = self.request("GET", "/assets/../../../../etc/passwd")
        self.assertEqual(status, 404)
        status, _, _ = self.request("GET", "/../README.md")
        self.assertNotEqual(status, 200)
        status, _, _ = self.request("GET", "/api/tasks/not-a-task")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
