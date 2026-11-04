"""Loopback-only browser interface for the existing coding-agent runtime."""

import ipaddress
import json
import mimetypes
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .provider import ProviderError
from .tools import Tools


MAX_BODY_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 512 * 1024
MAX_DIFF_CHARS = 50_000
MAX_EVENTS = 50
MAX_EVENT_TEXT = 1_600
MAX_TASKS = 100
MAX_DIRECTORIES = 200
WEB_ROOT = Path(__file__).with_name("web")
WEB_DIST = WEB_ROOT / "dist"


def _workspace_path(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("Choose an existing folder using its full path")
    try:
        path = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("Folder does not exist or cannot be accessed") from exc
    if not path.is_dir():
        raise ValueError("Selected workspace must be a folder")
    return path


class LocalWebServer(ThreadingHTTPServer):
    """HTTP server restricted to loopback clients and one active task worker."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, config, store, runtime, host="127.0.0.1", port=8765):
        if host not in {"127.0.0.1", "localhost"}:
            raise ValueError("Web UI may only bind to 127.0.0.1 or localhost")
        self.config = config
        self.store = store
        self.runtime = runtime
        saved_url = self.store.setting("web.router_base_url")
        if saved_url:
            self.runtime.client.base_url = saved_url.rstrip("/")
        self.token = secrets.token_urlsafe(32)
        self._worker_lock = threading.RLock()
        self._active_task = None
        self._worker = None
        self._recover_interrupted_tasks()
        super().__init__((host, port), _make_handler(self))

    def _recover_interrupted_tasks(self):
        for task in self.store.all_tasks():
            if task["status"] == "running":
                self.store.set_status(task["id"], "paused")
                self.store.event(task["id"], "server_interruption", {
                    "message": "Server restarted while this task was running; inspect before resuming."
                })

    def worker_busy(self):
        with self._worker_lock:
            return self._worker is not None and self._worker.is_alive()

    def start_task(self, task_id, resume=False):
        with self._worker_lock:
            self._start_locked(task_id, resume)

    def live_models(self):
        base_url = self.runtime.client.base_url
        if self.store.setting("web.router_disconnected") == "true":
            return {"connected": False, "models": [], "selected_model_id": self.store.selected_model_id(),
                    "base_url": base_url, "error": "Đã ngắt kết nối 9Router."}
        try:
            models = self.runtime.client.list_models()
            return {"connected": True, "models": models,
                    "selected_model_id": self.store.selected_model_id(), "base_url": base_url, "error": None}
        except ProviderError as exc:
            return {"connected": False, "models": [], "selected_model_id": self.store.selected_model_id(),
                    "base_url": base_url, "error": str(exc)}
        except Exception as exc:
            return {"connected": False, "models": [], "selected_model_id": self.store.selected_model_id(),
                    "base_url": base_url,
                    "error": f"9Router connection check failed ({type(exc).__name__})"}

    def require_live_model(self, model_id):
        if self.store.setting("web.router_disconnected") == "true":
            raise ConnectionError("9Router is disconnected")
        try:
            models = self.runtime.client.list_models()
        except ProviderError as exc:
            raise ConnectionError(str(exc)) from None
        except Exception as exc:
            raise ConnectionError(f"9Router connection check failed ({type(exc).__name__})") from None
        if model_id not in models:
            raise LookupError("Selected model is not available in the connected 9Router catalog")

    def create_task(self, request, name=None, workspace=None, model=None):
        with self._worker_lock:
            if self._worker is not None and self._worker.is_alive():
                raise RuntimeError("Haness is busy with another task")
            task_id, session_id = self.runtime.new_task(request, workspace=workspace, name=name, model=model)
            self._start_locked(task_id, False)
            return task_id, session_id

    def _start_locked(self, task_id, resume):
        if self._worker is not None and self._worker.is_alive():
            raise RuntimeError("Haness is busy with another task")
        self._active_task = task_id
        worker = threading.Thread(target=self._run_task, args=(task_id, resume),
                                  name=f"haness-task-{task_id[:8]}", daemon=True)
        self._worker = worker
        worker.start()

    def stop_worker(self):
        """Ask an active task to stop at a step boundary and wait before DB close."""
        with self._worker_lock:
            worker, task_id = self._worker, self._active_task
        if worker is None or not worker.is_alive():
            return
        if task_id:
            try:
                self.runtime.stop(task_id)
            except ValueError:
                pass
        timeout = max(1, float(self.config.timeout) * (int(self.config.retries) + 1) + 2)
        worker.join(timeout=timeout)

    def _run_task(self, task_id, resume):
        try:
            self.runtime.run(task_id, resume=resume)
        except Exception as exc:
            self.store.event(task_id, "runtime_error", {
                "message": self.store._redact(f"{type(exc).__name__}: {str(exc)[:500]}")
            })
        finally:
            with self._worker_lock:
                if self._active_task == task_id:
                    self._active_task = None
                    self._worker = None


def _make_handler(app):
    def clip_event_value(value):
        if isinstance(value, str) and len(value) > MAX_EVENT_TEXT:
            return value[:MAX_EVENT_TEXT] + " … [truncated]"
        if isinstance(value, list):
            return [clip_event_value(item) for item in value]
        if isinstance(value, dict):
            return {key: clip_event_value(item) for key, item in value.items()}
        return value

    class Handler(BaseHTTPRequestHandler):
        server_version = "HanessLocal/1"
        sys_version = ""

        def log_message(self, fmt, *args):
            # Default access logs include request targets. Keep task text and tokens out of logs.
            return

        def _send(self, status, body, content_type="application/json; charset=utf-8"):
            if isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            if len(body) > MAX_RESPONSE_BYTES:
                status = 413
                body = json.dumps({"error": "Response exceeds the 512 KiB limit"}).encode("utf-8")
            self._send(status, body)

        def _error(self, status, message):
            self._json(status, {"error": message})

        def _request_is_local(self):
            try:
                if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                    return False
                host = urlsplit("//" + self.headers.get("Host", "")).hostname
                port = urlsplit("//" + self.headers.get("Host", "")).port
                if host not in {"127.0.0.1", "localhost"} or port != app.server_port:
                    return False
                origin = self.headers.get("Origin")
                if origin:
                    parsed = urlsplit(origin)
                    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
                        return False
                    if parsed.port != app.server_port or parsed.path not in {"", "/"}:
                        return False
                return True
            except (ValueError, TypeError):
                return False

        def _authorized_mutation(self):
            if not self._request_is_local():
                self._error(403, "Request origin is not allowed")
                return False
            if not secrets.compare_digest(self.headers.get("X-Haness-Token", ""), app.token):
                self._error(403, "Missing or invalid local session token")
                return False
            return True

        def _read_json(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise ValueError("Invalid Content-Length")
            if size < 0 or size > MAX_BODY_BYTES:
                raise OverflowError("Request body exceeds the 64 KiB limit")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Content-Type must be application/json")
            try:
                value = json.loads(self.rfile.read(size).decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("Invalid JSON request body") from exc
            if not isinstance(value, dict):
                raise ValueError("JSON request body must be an object")
            return value

        def do_GET(self):
            if not self._request_is_local():
                self._error(403, "Request origin is not allowed")
                return
            path = urlsplit(self.path).path
            if path == "/":
                try:
                    page = (WEB_DIST / "index.html").read_text(encoding="utf-8")
                except OSError:
                    self._error(500, "Built web interface is unavailable. Run `npm ci && npm run build` in web-ui.")
                    return
                self._send(200, page.replace("__HANESS_SESSION_TOKEN__", app.token), "text/html; charset=utf-8")
                return
            if path.startswith("/assets/"):
                try:
                    root = WEB_DIST.resolve(strict=True)
                    asset = (WEB_DIST / "assets" / path.removeprefix("/assets/")).resolve(strict=True)
                    if not asset.is_relative_to(root) or not asset.is_file():
                        raise OSError("Invalid static asset path")
                    body = asset.read_bytes()
                except (OSError, RuntimeError):
                    self._error(404, "Web asset not found")
                    return
                if len(body) > MAX_RESPONSE_BYTES:
                    self._error(413, "Web asset exceeds the response size limit")
                    return
                media_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                if media_type in {"text/javascript", "text/css"}:
                    media_type += "; charset=utf-8"
                self._send(200, body, media_type)
                return
            if path == "/api/status":
                workspace = str(app.config.workspace)
                self._json(200, {"workspace": workspace, "workspace_name": app.config.workspace.name or workspace,
                                 "model": app.config.model,
                                 "busy": app.worker_busy(),
                                 "command_execution": list(app.config.allow_commands)})
                return
            if path == "/api/models":
                result = app.live_models()
                self._json(200, result)
                return
            if path == "/api/tasks":
                tasks = app.store.all_tasks()[-MAX_TASKS:]
                for task in tasks:
                    task["request"] = app.store._redact(task["request"])
                    if len(task["request"]) > 500:
                        task["request"] = task["request"][:500] + " … [truncated]"
                tasks.reverse()
                self._json(200, {"tasks": tasks})
                return
            if path.startswith("/api/tasks/"):
                task_id = path[len("/api/tasks/"):]
                if not task_id or "/" in task_id:
                    self._error(404, "Task not found")
                    return
                task = app.store.task(task_id)
                if not task:
                    self._error(404, "Task not found")
                    return
                task["request"] = app.store._redact(task["request"])
                all_events = app.store.events(task_id)
                events = [{**event, "payload": clip_event_value(event["payload"])}
                          for event in all_events[-MAX_EVENTS:]]
                self._json(200, {"task": task, "events": events,
                                 "events_truncated": len(all_events) > MAX_EVENTS,
                                 "worker_active": app._active_task == task_id and app.worker_busy()})
                return
            if path == "/api/workspace/status":
                self._json(200, {"status": Tools(app.config.workspace).git_status()[:MAX_DIFF_CHARS]})
                return
            if path == "/api/workspace/diff":
                diff = Tools(app.config.workspace).git_diff()[:MAX_DIFF_CHARS]
                self._json(200, {"diff": app.store._redact(diff), "truncated": len(diff) >= MAX_DIFF_CHARS})
                return
            self._error(404, "Not found")

        def do_POST(self):
            if not self._authorized_mutation():
                return
            path = urlsplit(self.path).path
            if path not in {"/api/tasks", "/api/doctor", "/api/workspaces/browse", "/api/workspace/review", "/api/models/select", "/api/connection/connect", "/api/connection/disconnect"} and not path.startswith("/api/tasks/"):
                self._error(404, "Not found")
                return
            try:
                body = self._read_json()
            except OverflowError:
                self._error(413, "Request body exceeds the 64 KiB limit")
                return
            except ValueError as exc:
                self._error(400, str(exc))
                return
            if path == "/api/connection/disconnect":
                app.store.set_setting("web.router_disconnected", "true")
                self._json(200, {"connected": False})
                return
            if path == "/api/connection/connect":
                candidate = body.get("base_url")
                if not isinstance(candidate, str) or len(candidate.strip()) > 2048:
                    self._error(400, "Enter a valid 9Router Base URL")
                    return
                candidate = candidate.strip().rstrip("/")
                try:
                    parsed = urlsplit(candidate)
                    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/v1"}:
                        raise ValueError
                except ValueError:
                    self._error(400, "Base URL must be http(s)://host with an optional /v1 path")
                    return
                client = app.runtime.client
                previous = client.base_url
                client.base_url = candidate
                try:
                    models = client.list_models()
                except Exception as exc:
                    client.base_url = previous
                    message = str(exc) if isinstance(exc, ProviderError) else f"9Router connection check failed ({type(exc).__name__})"
                    self._json(502, {"error": message})
                    return
                app.store.set_setting("web.router_base_url", candidate)
                app.store.set_setting("web.router_disconnected", "false")
                self._json(200, {"connected": True, "models": models, "base_url": candidate,
                                 "selected_model_id": app.store.selected_model_id()})
                return
            if path == "/api/doctor":
                if app.worker_busy():
                    self._error(409, "Haness is busy with another task")
                    return
                try:
                    response = app.runtime.client.chat(app.config.model,
                        [{"role": "user", "content": "Reply with OK."}], max_tokens=8)
                    model = response.get("model", app.config.model)
                    self._json(200, {"ok": True, "model": model})
                except Exception as exc:
                    self._json(502, {"ok": False, "error": f"9Router check failed ({type(exc).__name__}). Check the router URL, dashboard API key, configured model, and that 9Router is running."})
                return
            if path == "/api/models/select":
                model_id = body.get("model_id")
                try:
                    app.require_live_model(model_id)
                    selected = app.store.set_selected_model_id(model_id)
                except ConnectionError as exc:
                    self._error(503, str(exc))
                    return
                except LookupError as exc:
                    self._error(409, str(exc))
                    return
                except ValueError as exc:
                    self._error(400, str(exc))
                    return
                self._json(200, {"selected_model_id": selected})
                return
            if path == "/api/workspaces/browse":
                try:
                    workspace = _workspace_path(body.get("path"))
                    children = []
                    for entry in sorted(workspace.iterdir(), key=lambda item: item.name.casefold()):
                        try:
                            if entry.is_dir():
                                child = entry.resolve(strict=True)
                                children.append({"name": entry.name, "path": str(child)})
                                if len(children) >= MAX_DIRECTORIES:
                                    break
                        except (OSError, RuntimeError):
                            continue
                    self._json(200, {"path": str(workspace), "parent": str(workspace.parent) if workspace.parent != workspace else None,
                                     "directories": children, "truncated": len(children) == MAX_DIRECTORIES})
                except (ValueError, OSError) as exc:
                    self._error(400, str(exc)[:300])
                return
            if path == "/api/workspace/review":
                try:
                    workspace = _workspace_path(body.get("workspace"))
                    tools = Tools(workspace, app.config.allow_commands)
                    git_status = tools.git_status()[:MAX_DIFF_CHARS]
                    diff = tools.git_diff()[:MAX_DIFF_CHARS]
                    self._json(200, {"workspace": str(workspace), "status": git_status,
                                     "diff": app.store._redact(diff), "truncated": len(diff) >= MAX_DIFF_CHARS})
                except (ValueError, OSError) as exc:
                    self._error(400, str(exc)[:300])
                return
            if path == "/api/tasks":
                request = body.get("request")
                name = body.get("name")
                workspace_value = body.get("workspace", str(app.config.workspace))
                model = body.get("model") or app.store.selected_model_id() or app.config.model
                if not isinstance(request, str) or not request.strip():
                    self._error(400, "A non-empty string request is required")
                    return
                if len(request) > 20_000:
                    self._error(413, "Task request exceeds the 20,000 character limit")
                    return
                if name is not None and (not isinstance(name, str) or not name.strip() or len(name.strip()) > 120):
                    self._error(400, "Task name must contain 1 to 120 characters")
                    return
                try:
                    workspace = _workspace_path(workspace_value)
                except ValueError as exc:
                    self._error(400, str(exc))
                    return
                try:
                    app.require_live_model(model)
                    app.store.set_selected_model_id(model)
                    task_id, session_id = app.create_task(request.strip(), name.strip() if name else None, str(workspace), model)
                except ConnectionError as exc:
                    self._error(503, str(exc))
                    return
                except LookupError as exc:
                    self._error(409, str(exc))
                    return
                except ValueError as exc:
                    self._error(400, str(exc))
                    return
                except RuntimeError:
                    self._error(409, "Haness is busy with another task")
                    return
                self._json(202, {"task_id": task_id, "session_id": session_id, "status": "queued"})
                return
            pieces = path.split("/")
            if len(pieces) != 5 or pieces[1:3] != ["api", "tasks"] or pieces[4] not in {"stop", "resume"}:
                self._error(404, "Not found")
                return
            task_id, action = pieces[3], pieces[4]
            task = app.store.task(task_id)
            if not task:
                self._error(404, "Task not found")
                return
            if action == "stop":
                app.runtime.stop(task_id)
                self._json(200, {"task_id": task_id, "status": app.store.task(task_id)["status"]})
                return
            if app.worker_busy():
                self._error(409, "Haness is busy with another task")
                return
            if task["status"] != "paused":
                self._error(409, "Only a paused task can be resumed")
                return
            try:
                app.require_live_model(task["model"])
                app.start_task(task_id, resume=True)
            except ConnectionError as exc:
                self._error(503, str(exc))
                return
            except LookupError as exc:
                self._error(409, str(exc))
                return
            except RuntimeError:
                self._error(409, "Haness is busy with another task")
                return
            self._json(202, {"task_id": task_id, "status": "queued"})

    return Handler

