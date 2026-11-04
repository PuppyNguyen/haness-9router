# Handoff

Ngày 2026-10-21 UTC. Repo giao ban đầu trống và chưa phải Git repository. Đã hoàn tất A-01; xem `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`, `docs/TESTING.md`.

Triển khai theo stdlib Python/SQLite, OpenAI-compatible adapter, CLI và root-scoped file tools. Tài liệu công khai 9Router cho endpoint local `http://localhost:20128/v1`, API key từ dashboard; model ID phải do người dùng cấu hình. Không biết phiên bản, model và trạng thái dịch vụ thực tế do sandbox không cho socket.

Coding agent bản đầu đã được triển khai. Chạy `python3 -m unittest discover -s tests -v`; 16 test pass. Linux bootstrap tạo venv stdlib-only thành công, nhưng live doctor request bị sandbox chặn. PowerShell/Windows và router thật chưa xác minh. Resume kiểm tra workspace, repo name/revision; task import từ repo không có Git revision bị từ chối. Model fallback cần cấu hình và operator-confirmed tool-calling flag. Xem `docs/TESTING.md` và `docs/PROGRESS.md`.
# Handoff — 2026-10-22

Người dùng đã duyệt local web UI và yêu cầu hỗ trợ mọi chức năng coding-agent hiện có. Triển khai xong theo `docs/plans/2026-10-22-local-web-ui.md` và `docs/specs/2026-10-22-local-web-ui.md`. Server đang chạy bằng `./run.sh web --no-browser --port 8765`, URL `http://127.0.0.1:8765/`; browser tab được giữ mở. 29 tests pass; compileall, bash syntax và JavaScript syntax pass. Live 9Router doctor pass; một `list_files` tool call hoàn tất qua Runtime trong workspace/SQLite tạm. Auth/model-not-found/timeout/provider outage chưa thử live; Windows chưa kiểm tra. Workspace không có Git metadata; không tạo được worktree/commit/diff. Web bao phủ coding-agent core; configure/export/import/update vẫn CLI; scheduler, docs ingestion, multi-agent, memory, deploy vẫn chưa triển khai đầy đủ. Xem `docs/TESTING.md` và `docs/PROGRESS.md`.


## Cập nhật UI-05 — 2026-10-22

Đầu trang web ghi “Workspace hiện tại”, tên thư mục và đường dẫn đầy đủ; nhấn đường dẫn để sao chép. `/api/status` trả thêm `workspace_name` bên cạnh đường dẫn `workspace`. Tests: 29/29 pass; `compileall` và `node --check` pass. Server đã được khởi động lại để dùng mã mới tại `http://127.0.0.1:8765/`.

## UI-06 — 2026-10-22: Workspace và tên task riêng

Composer cho nhập tên task, path tuyệt đối và mở bộ duyệt thư mục; mỗi task lưu tên/workspace trong SQLite. Runtime tạo/đọc/sửa/chạy lệnh trong workspace task và resume dùng lại workspace đó. API browse yêu cầu token, chỉ liệt kê tối đa 200 thư mục con; đường dẫn được chuẩn hóa/resolve và phải tồn tại. Migration giữ DB task cũ; export/import giữ tên task. 33 test pass; compileall, Node syntax và Bash syntax pass. Server đã restart và HTTP smoke browse directory thành công tại `http://127.0.0.1:8765/`.

## UI-07 design and plan — 2026-10-22

User yêu cầu component framework nhẹ, startup 9Router gate, chọn model live và CRUD hồ sơ Haness. Spec `docs/specs/2026-10-22-web-ui-and-model-catalog-design.md` và kế hoạch `docs/plans/2026-10-22-preact-router-model-catalog.md` đã được duyệt. Live `/v1/models` check trên execution host trả 24 IDs; `/health` ở base URL trả 404. Không in key. Node 24.18/npm 11.16; checkout không có Git metadata, Plannotator không cài.

## UI-07 completed — 2026-10-22

Kế hoạch UI-07 đã được duyệt và triển khai. Frontend Preact/Vite sources: `web-ui/src/`; locked deps: `web-ui/package-lock.json`; production bundle: `agent_harness/web/dist/`. Python server serves same-origin hashed static assets with existing local token/CSP protections. `GET /api/models` uses authenticated 9Router `GET /v1/models`; offline returns a disconnected state, no key/body. UI disables model picker, submit and resume unless connected. Backend independently revalidates before create/resume. The UI now reads the live 9Router catalog only; profile CRUD was removed in UI-08. Last selected model is stored in `settings`, each task pins its model in `tasks.model`, and resume validates it.

Verification: `npm ci`, Vitest 4/4, Vite build; Python unittest 40/40, compileall and Bash syntax pass. Earlier UI-07 browser smoke showed the live catalog; the UI-08 browser inspection attempt was blocked by browser URL policy. Python fake-provider tests verify disconnected gate/retry and disabled resume. Windows is not available and remains unverified. The server is running loopback at `http://127.0.0.1:8765/`, session 10139; browser tab was marked deliverable. Checkout still has no `.git`; no diff/commit is available. Continue with `./run.sh web`; run UI rebuild from `web-ui` with `npm ci && npm run build` when source changes.

## UI-08 latest

Model profile CRUD đã bị loại khỏi UI/API/store (bảng legacy trong DB cũ không bị xóa tự động để tránh mất dữ liệu). UI chỉ đọc model catalog live từ 9Router. Có Base URL field để dùng local hoặc server, connect/disconnect được lưu trong SQLite Haness, create/resume bị backend chặn khi ngắt. Kết nối thử GET `/models`, chỉ lưu URL khi thành công; API key không được trả ra browser, nhưng sẽ được gửi tới URL nhập khi Connect — UI nêu rõ điều này. Frontend tests 4/4 và build pass; Python suite cần lần chạy cuối sau cleanup. Final validation complete: full Python tests, built frontend, server restarted, and live local disconnect/reconnect API smoke passed. Chưa có URL server từ xa; Windows vẫn chưa kiểm tra.
