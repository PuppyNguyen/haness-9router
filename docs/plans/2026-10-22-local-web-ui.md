# Local Web UI Implementation Plan

> **For agentic workers:** Execute inline task by task. Check off steps and update `docs/PROGRESS.md` after each task.

**Goal:** Add a loopback-only browser UI for all existing coding-agent task workflows while preserving CLI, 9Router config, existing permissions, and SQLite state.
**Architecture:** Python stdlib `ThreadingHTTPServer` serves static UI and same-origin JSON API. A single in-process worker invokes the existing synchronous Runtime; Store remains the durable source of task/event state. No new database schema or external dependency.
**Tech Stack:** Python 3.11+, `http.server`, `threading`, SQLite, HTML/CSS/vanilla JS, `unittest`.

## Global Constraints

- Bind only to `127.0.0.1` by default; never silently expose on a network interface.
- Reuse `Config`, `Store`, `Runtime`, `Tools` and current permission settings; do not expose the API key.
- Keep `AGENT_HARNESS_ALLOW_COMMANDS` disabled unless already explicitly configured.
- Do not add DB tables or third-party packages.
- The web UI covers existing coding-agent functions. Scheduler, document ingestion, multi-agent, long-term memory and deployment remain future extensions as specified in the original project plan.
- This checkout has no `.git` metadata; execute inline in the assigned checkout and report that isolation/commit verification is unavailable.

## File responsibilities

- `agent_harness/webserver.py`: worker lifecycle, HTTP server, local API and security checks.
- `agent_harness/web/index.html`, `app.css`, `app.js`: accessible task UI; all untrusted content rendered as text.
- `agent_harness/cli.py`: `web` subcommand and user-config loading integration.
- `tests/test_web.py`: loopback API, authorization, worker/task lifecycle and output safety tests with fake provider.
- `README.md`: run and security instructions.
- `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/TESTING.md`, `docs/HANDOFF.md`: project status and evidence.

---

### Task 1: Add a single-task worker and safe local HTTP API

**Files:** Create `agent_harness/webserver.py`; create `tests/test_web.py`.

**Interfaces:** `WebServer(config, store, runtime, host="127.0.0.1", port=8765)` with `serve_forever()`, `shutdown()`, and an ephemeral-port option for tests. HTTP endpoints: `GET /api/status`, `GET /api/tasks`, `GET /api/tasks/<id>`, `GET /api/workspace/status`, `GET /api/workspace/diff`, `POST /api/tasks`, `POST /api/tasks/<id>/stop`, `POST /api/tasks/<id>/resume`.

- [x] Test requests reject non-loopback Host/Origin, mutations without the per-process token, oversized JSON bodies, malformed JSON, and unknown task IDs.
- [x] Test a fake provider task runs on a background thread and status/detail requests remain available while it runs.
- [x] Implement one active worker at a time; reject competing create/resume with HTTP 409. Persist a new task before worker start. Stop remains cooperative. Do not resume until the prior worker exits.
- [x] Generate a random per-process token; embed only in the same-origin HTML response and require `X-Haness-Token` on every mutation. Check loopback peer address and Host/Origin; no CORS. Do not log request body, token, or query values.
- [x] On startup mark leftover `running` tasks paused and append an interruption event. Runtime resume validation remains authoritative.
- [x] Bound request body and diff/event response sizes; return generic JSON errors without tracebacks or provider secrets.
- [x] Run `python3 -m unittest tests.test_web -v`; all security and worker tests pass.

### Task 2: Build the browser UI for existing coding-agent workflows

**Files:** Create `agent_harness/web/index.html`, `agent_harness/web/app.css`, `agent_harness/web/app.js`; modify `agent_harness/webserver.py`; extend `tests/test_web.py`.

**Interfaces:** Serve `/` and static files from a fixed package directory. UI calls the API from Task 1 using same-origin fetch, polling task list/detail and workspace status/diff.

- [x] Test HTML embeds the current token without exposing credentials and static paths cannot escape the package directory.
- [x] Implement responsive layout with workspace/model summary, task composer, task list, status/ID/session, chronological event feed, final answer, Stop/Resume, Git status and expandable diff.
- [x] Render model/tool/task text using DOM `textContent`; never interpolate untrusted strings into HTML.
- [x] Disable submit/stop/resume controls while relevant requests are pending; show clear errors including busy/permission/resume conflicts.
- [x] Run `python3 -m unittest tests.test_web -v`; UI/API integration tests pass.

### Task 3: Integrate CLI and launcher operation

**Files:** Modify `agent_harness/cli.py`; modify `README.md`; extend `tests/test_web.py` or `tests/test_core.py`.

**Interfaces:** CLI command `./run.sh web [--host 127.0.0.1] [--port 8765] [--no-browser]`; only allow `127.0.0.1` or `localhost` host choices. Existing CLI commands and user config loader are unchanged.

- [x] Test parser accepts `web`, loopback host and port; rejects a non-loopback bind address.
- [x] Load the existing user config, construct the current Store/Runtime/9Router client, start server, print the local URL, and open the browser unless `--no-browser`.
- [x] Document launch, stop with Ctrl+C, task controls, existing command permission behavior, loopback/token protection, cooperative stop, interrupted task recovery and lack of OS sandboxing.
- [x] Run `python3 -m unittest discover -s tests -v`; all 29 existing and new tests pass.

### Task 4: Verify compatibility and update handoff evidence

**Files:** Modify `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/TESTING.md`, `docs/HANDOFF.md`.

- [x] Run `python3 -m unittest discover -s tests -v`.
- [x] Run `python3 -m compileall -q agent_harness tests` and `bash -n run.sh scripts/bootstrap.sh`.
- [x] Start the local server against an isolated temporary workspace and fake provider, verify page/API, create a task, observe completion, and stop the process; do not make a real 9Router request unless explicitly needed and available.
- [x] Record Linux results; leave Windows and real-router status as unverified unless evidence is available.
- [x] Check plan/spec coverage and report remaining gaps accurately.
