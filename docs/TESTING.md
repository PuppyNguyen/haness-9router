# Kiểm thử và bằng chứng

## Trạng thái ban đầu (giai đoạn A, 2026-10-21)

- Máy thực thi: Linux x86_64 sandbox; Python 3.14.4; Docker CLI 29.7.2; không tìm thấy PowerShell.
- Git worktree chưa khởi tạo: `.git` rỗng, `git status` báo không phải repository.
- Sandbox lúc đó từ chối socket localhost; không thể xác minh 9Router đang chạy trong bước ban đầu.
- Chưa kiểm tra Windows. Không khẳng định máy đích đã được kiểm tra.

## Bằng chứng theo bước

Chi tiết ban đầu nằm trong `docs/PROGRESS.md`; kết quả 9Router thật sẽ ghi riêng khi mạng cho phép.

## Kết quả hiện tại

- `python3 -m unittest discover -s tests -v`: 40 tests pass, bao gồm model catalog giả, create/resume fail-closed, thư mục task có khoảng trắng/Unicode, token API, resume đúng workspace và migration SQLite.
- Coverage gồm provider giả/retry/error, path/symlink, file tools, command deny, checkpoint/resume/no replay, import/export, revision guard, fallback capability gate, Web API/worker/security, secret redaction và response bounds.
- `python3 -m compileall -q agent_harness tests`: pass.
- `bash -n scripts/bootstrap.sh run.sh`: pass.
- `cd web-ui && npm ci && npm test && npm run build`: pass with Node 24.18.0/npm 11.16.0; 4 component tests pass and Vite writes static assets into `agent_harness/web/dist`.
- Final frontend run after resume-gate coverage: 4/4 Vitest tests pass; production JS 31.75 kB, CSS 15.45 kB before gzip.
- Browser smoke check: local UI opened at `http://127.0.0.1:8765/`; page showed workspace `haness-9router`, configured model `cx/gpt-6-luna`, command execution disabled. Clicking Git diff showed a concise non-Git-repository status. The explicit UI doctor button succeeded against the configured local 9Router; response model was `gpt-6-luna` and no key was returned.
- Web API fake-provider tests verify task creation/completion and file write, responsive status during work, stop/resume without repeating an already completed tool, startup recovery, request/token/origin limits, no API key in status/task response, and explicit doctor endpoint without returning credentials.
- Web detail and list responses are bounded; test includes a 2 MB event payload and verifies truncation within the 512 KiB response cap.
- Workspace identity: `/api/status` trả đường dẫn chính xác và tên thư mục; HTML có vùng “Workspace hiện tại” cùng nút sao chép. Đã bổ sung assertions tương ứng; toàn bộ 29 tests pass.
- Server smoke UI-07: browser loopback hiển thị model catalog live; kiểm tra UI ban đầu ghi ở đây như lịch sử trước UI-08.
- Live tool-calling smoke check: ran the existing Runtime with the configured 9Router/model against an empty temporary workspace and temporary SQLite file. The model called `list_files` once, completed successfully as `gpt-6-luna`, and the temporary directory was cleaned up. The assigned repository and user task history were not touched by this smoke check.
- Local server was started by `./run.sh web --no-browser --port 8765` and remains running in the current session, bound to loopback. The Preact UI tab was left open for the user.
- Linux bootstrap tạo `.venv` bằng `--without-pip` (Python stdlib-only); sau đó `doctor` chạy được nhưng request tới `localhost:20128` thất bại do sandbox chặn network. Đây không phải xác minh router/model.
- `AGENT_HARNESS_HOME=/tmp/haness-bootstrap-check ./run.sh status`: exit 0; CLI launcher dùng dữ liệu tách biệt trong `/tmp`.
- Gọi launcher từ `/tmp`: exit 0; sandbox in cảnh báo stream fd nhưng CLI status vẫn hoàn tất.
- PowerShell/Windows: chưa kiểm tra; không có `pwsh`/Windows runtime trong môi trường.
- 9Router thật: Chat Completions and one `list_files` tool call succeeded with the configured model. Exact installed 9Router version, auth failure, model-not-found, timeout and outage cases were not tested against the live router; error paths use fake provider tests.
- Không chạy test/lint/build trên repository đích thực: workspace được giao ban đầu rỗng.
- Launcher dùng `PYTHONPATH` trỏ về package, giữ workspace mặc định theo current shell directory để thao tác repo đích.

Giới hạn kiểm chứng: ở giai đoạn A sandbox từ chối socket và home mặc định chỉ đọc. Trong lượt UI ngày 2026-10-22, local 9Router Chat Completions và một tool call đã được xác minh thật; chưa kiểm tra phiên bản router và các dạng provider error trực tiếp. Workspace hiện tại vẫn không có `.git`, nên Git diff của chính checkout không khả dụng.
# UI-07 implementation evidence

- `python3 -m unittest tests.test_core.ProviderTests -v` — PASS, 7 tests. Fake opener verified authenticated `GET /models`, bounded reads, catalog validation, deduplication, transient retries, and sanitized errors.
- `python3 -m unittest tests.test_core.StoreMigrationTests -v` — PASS, 2 tests. Existing DB migration, selected-model persistence, and task model retention verified.
- `python3 -m unittest discover -s tests -v` — PASS, 40 tests after web API integration. Covers catalog selection, offline/missing-model task rejection, resume remains paused, and legacy CLI/runtime behavior.
- Live 9Router catalog request was verified during design on this Linux execution host (HTTP 200, 24 IDs); this step used provider fakes and did not make a live request.

## UI-08: model catalog và vòng đời kết nối 9Router

- Frontend: `npm test` — Vitest 4/4 pass (gate, live model selection/task payload, connect/disconnect + Base URL, resume gate); `npm run build` — PASS.
- Backend: `./.venv/bin/python -m unittest discover -s tests -v` — PASS, 43/43 sau khi bỏ profile CRUD.
- Integration fake: catalog live read-only; disconnect chặn task mới, URL sai bị từ chối và endpoint trước đó không đổi; reconnect lưu Base URL sau khi catalog thành công. Tất cả qua API token.
- Live router/API smoke trên Linux: endpoint local hiện có trả 24 model; disconnect trả trạng thái ngoại tuyến; reconnect cùng URL khôi phục catalog 24 model. Không thử endpoint từ xa chưa được cung cấp. Server mới chạy tại `http://127.0.0.1:8765/`. Browser UI inspection bị chặn bởi browser URL policy trong phiên; xác minh hành vi qua API và frontend tests/build.
