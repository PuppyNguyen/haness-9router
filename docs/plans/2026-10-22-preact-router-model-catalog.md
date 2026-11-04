# UI-07 Implementation Plan: Preact and 9Router Model Catalog

## Goal and constraints

Implement the approved design in `docs/specs/2026-10-22-web-ui-and-model-catalog-design.md`. Keep Haness as a modular monolith: Python stdlib HTTP server/runtime, SQLite state, and a Preact/Vite static frontend. Do not install, configure, or mutate 9Router. The live model catalog is read-only; profile CRUD is local Haness data. Keep the built assets in the repository so Node is needed only for frontend development/build. Preserve the existing CLI model setting and pin the chosen model onto each web-created task.

Execution checkout has no `.git` metadata, so no worktree, Git diff, or commit step is possible. Work directly in this checkout and report that limitation. Use existing project conventions and preserve unrelated user data. Every implementation step updates `docs/PROGRESS.md`, `docs/TESTING.md`, and `docs/PLAN.md`; update `docs/HANDOFF.md` at completion. No real model completion is required for catalog checks.

## Data and API contract to implement first

- `model_profiles(id TEXT PRIMARY KEY, display_name TEXT NOT NULL, model_id TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)`.
- `settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)`; use `web.selected_model_id` for the last choice for a new task.
- Keep `tasks.model` as the immutable model assigned to a task. Resume validates the stored model against the current live catalog and continues with that model.
- Provider `GET {base_url}/models`: authenticated, bounded response (1 MiB maximum), valid `data[].id` strings only, at most 1,000 distinct model IDs. Do not log key, response body, or authorization headers.
- Local profile bound: 200 records. Validate display name and model ID for non-empty bounded strings; model IDs are unique. A custom profile can be stored offline but cannot be selected until its model ID appears in the live catalog.
- `GET /api/models` returns connection state, bounded live IDs, local profiles, selected model ID, and a sanitized error. `POST /api/models/select` accepts only a live catalog ID and persists the setting. Profile create/update/delete APIs operate only on SQLite.
- New task request includes `model`; server re-fetches the catalog before enqueueing, rejects absent/unavailable selections, and calls Runtime with the selected model. Resume re-fetches and validates the task's stored model before starting the worker. These gates happen before task creation or worker start.
- No client-side API key exposure. Startup and retry use GET catalog; `/api/doctor` may retain its existing explicit completion check.

## Steps

### 1. Add a bounded provider model-list operation

**Files:** `agent_harness/provider.py`, `tests/test_core.py` or a focused `tests/test_provider.py`, `docs/PROGRESS.md`, `docs/TESTING.md`.

Add `NineRouterClient.list_models()` using the configured base URL and Bearer key. Read no more than 1 MiB plus one byte; validate JSON object shape and `data` entries; return stable unique IDs. Reuse timeout/retry policy only for transient provider/network failures, without retrying non-transient auth/not-found failures. Map all failures to sanitized `ProviderError` messages.

**Tests:** fake opener verifies URL, method, authorization presence without outputting it, valid parsing/deduplication, empty/malformed/oversized/too-many model lists, HTTP 401/404/5xx, and network timeout. Assert secrets and raw response bodies never appear in exception strings. Run focused provider tests.

### 2. Add SQLite profiles and remembered selection

**Files:** `agent_harness/store.py`, `tests/test_core.py`, docs progress/testing.

Add an idempotent schema migration for `model_profiles` and `settings`; add list/get/create/update/delete profile methods and selected-model get/set methods. Enforce the 200-profile limit and field bounds in the store boundary. Profile edits update timestamps; deleting a profile leaves tasks and provider untouched. Migration must retain existing tasks and task model values.

**Tests:** open a pre-change DB fixture and confirm migration preserves tasks; CRUD and timestamps; duplicate model ID and over-limit rejection; setting round-trip; deleting profile leaves existing task model unchanged.

### 3. Thread model choice through Runtime and secure web APIs

**Files:** `agent_harness/runtime.py`, `agent_harness/webserver.py`, `tests/test_web.py`, `tests/test_core.py`, docs progress/testing.

Extend `Runtime.new_task(..., model=None)` with backward-compatible default to configured CLI model. Add a webserver catalog helper that calls `list_models()` and returns only sanitized state. Add catalog and profile CRUD/select endpoints with existing loopback, token, body/response limits. For task creation, validate live catalog and requested ID before storing or starting the task, then persist it in `tasks.model`; store the remembered selection. For resume, validate existing task model against live catalog before worker creation; preserve paused state on failure. Ensure a failed revalidation leaves no new task and performs no model or tool action.

**Tests:** authenticated API CRUD and validation, unauthorized mutation, live model selection, task model pinning, configured-model backward compatibility, provider unavailable/missing model create failure without task row, and resume failure without worker start or status change. Run full Python suite.

### 4. Establish the Preact/Vite component frontend

**Files:** new `web-ui/package.json`, `package-lock.json`, `vite.config.js`, `index.html`, `src/main.jsx`, `src/api.js`, `src/App.jsx`, `src/styles.css`, focused `src/components/*`; generated `agent_harness/web/dist/*`.

Add exact pinned frontend dependencies and lockfile. Use Preact 10.29.8, Vite 8.3.5, `@preact/preset-vite` 2.10.6, Vitest 5.0.5, `@testing-library/preact` 3.2.6, and jsdom 30.1.3, subject to `npm ci` engine/peer validation. Build static hashed assets into the Python package web directory. Split existing UI responsibilities into `App`, `ConnectionBanner`, `TaskSidebar`, `TaskComposer`, `WorkspacePicker`, `ModelPicker`, `ModelProfileManager`, `TaskDetail`, `GitReview`, and `Toast`; retain current workflows and Vietnamese labels.

**Checks:** `npm ci`, `npm run build`; verify output is static, same-origin, and has no external CDN/runtime server dependency. Inspect output paths before wiring Python serving.

### 5. Implement startup gate, model picker, and local profile manager

**Files:** `web-ui/src/App.jsx`, `src/api.js`, component modules/styles, `web-ui/src/**/*.test.*`.

Start UI in `checking`; fetch `/api/models` without enabling model actions. While checking/disconnected, disable model selection, task submit, and resume controls and show status plus retry. Keep local navigation, stop, Git review, and local profile CRUD usable. When connected, allow choosing a live ID; persist choice using select API and include it in new task submission. Show profile list separately with add/edit/delete forms; profile model ID can be chosen from live IDs or entered manually. Use accessible labels, buttons, dialog semantics, keyboard operation, and text rendering for all user/provider strings.

**Tests:** Vitest/jsdom component tests for initial checking gate, disconnected state, retry recovery, selection persistence, create-task model payload, profile CRUD, and resume disabled/enabled based on connection. Run tests and build.

### 6. Serve production assets and preserve local server protections

**Files:** `agent_harness/webserver.py`, `agent_harness/web/` generated output, `tests/test_web.py`.

Serve Vite index and manifest-listed static assets from a fixed resolved dist root; reject traversal and unknown paths; do not reintroduce token replacement into JavaScript assets. Keep loopback Host/Origin validation, session token on mutations, CSP, no-store, and output limits. Add a clear 500 response if built assets are absent with a build command hint. Remove or retire stale vanilla assets only after regression tests target the production bundle.

**Tests/checks:** HTTP tests for index, hashed JS/CSS content types, missing assets, traversal rejection, headers, local auth, and current coding-agent UI APIs. Run `python3 -m unittest discover -s tests -v`, `python3 -m compileall -q agent_harness tests`, `npm ci`, `npm test`, and `npm run build`.

### 7. Browser smoke, docs, and handoff

**Files:** `README.md`, `docs/TESTING.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/HANDOFF.md`, optionally `docs/DECISIONS.md`.

Update setup and operations docs: model catalog is read-only, profile CRUD is local, startup disconnected state, retry, model selection, task pinning/resume behavior, and Node only required for rebuilding UI. Record actual Linux browser smoke for connected catalog and simulated disconnected/error state; do not claim Windows verified. Record every command and observed result, then refresh the handoff and feature maturity table.

**Acceptance:** existing coding-agent flows remain usable; no task submit/resume occurs while offline or with a missing model; profile changes survive server restart; resume uses stored model; secrets stay out of response/logs; locked build and component tests pass. Live 9Router catalog request was verified during design on this execution host, but record any post-change live probe separately from fake-provider test evidence.

## Final self-review

Before completion, compare each approved-spec acceptance item against implementation and evidence; inspect new endpoints and built assets for secret leakage, unsafe HTML insertion, path traversal and accidental 9Router mutation. Run the frontend/backend regression commands above. Report unresolved Windows/manual-environment checks honestly. No commit is planned because this checkout has no Git metadata.
