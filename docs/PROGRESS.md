# Nhật ký tiến độ

## 2026-10-21 16:01 UTC — A-01

1. Đã làm: Kiểm tra Linux, Python, Docker CLI, Git, PowerShell, dấu vết OpenClaw/9Router và biến môi trường chỉ in tên/trạng thái; không đọc secret. Tìm tài liệu 9Router chính thức.
2. File thay đổi: `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/TESTING.md`, `docs/DECISIONS.md`, `docs/HANDOFF.md`, `docs/DECISIONS.md`.
3. Kiểm tra: `uname -a`, `python3 --version`, `git --version`, `docker --version`, `git status`, process/env presence. Python 3.14.4, Linux x86_64; thư mục giao trống; không có endpoint vars/process; kết nối socket bị PermissionError của sandbox.
4. Bằng chứng bên ngoài: docs.9router.com nói endpoint tương thích OpenAI và local `http://localhost:20128/v1`; tài liệu integration yêu cầu API key dashboard. Model examples khác nhau giữa trang docs, nên không mặc định.
5. Vấn đề còn: phiên bản, endpoint/key/model thật và khả năng tool-calling chưa thể thử trên 9Router cài đặt. PowerShell/Windows chưa có.
6. Tiếp theo: viết kiểm thử RED cho contract cấu hình, workspace path và giao thức provider giả lập.

## 2026-10-21 16:03 UTC — B-01

1. Đã làm: Tạo test contract cho required model, config normalization, path traversal/symlink, OpenAI request shape và secret-safe provider errors.
2. File thay đổi: `tests/test_core.py`, cập nhật trạng thái `docs/PLAN.md`.
3. Kiểm tra: `python3 -m unittest discover -s tests -v` — FAIL mong đợi: `ModuleNotFoundError: No module named 'agent_harness'` (RED).
4. Vấn đề còn: module chưa được triển khai.
5. Tiếp theo: thêm implementation nhỏ để test xanh.

## 2026-10-21 16:09 UTC — B-02 đến E-01

1. Đã làm: Xây Python CLI/adapters/store/runtime; thêm list/search/read/write/exact patch/Git/command tools; SQLite task/session/events; giới hạn và resume; secret redaction; export/import; bootstrap shell và PowerShell; README và extension contracts.
2. File thay đổi: `agent_harness/`, `tests/test_core.py`, `scripts/`, `run.sh`, `run.ps1`, `.gitignore`, `requirements.lock`, `README.md`, `docs/EXTENSIONS.md`, docs tiến độ.
3. Kiểm tra: `python3 -m unittest discover -s tests -v` — 14 tests pass, gồm provider auth/model errors, retry, symlink traversal, root file listing, patch, command denial, tool-call checkpoints, action non-replay, revision mismatch, secret redaction, import/export path rebinding. `python3 -m compileall -q agent_harness tests` pass. `bash -n scripts/bootstrap.sh run.sh` pass. `AGENT_HARNESS_HOME=/tmp/haness-bootstrap-check ./run.sh status` exit 0.
4. Bootstrap: Linux `bash scripts/bootstrap.sh` tạo `.venv` (`--without-pip`, không external deps), chạy `doctor`, nhận lỗi kết nối 9Router (sandbox chặn socket); không xác minh request thật. Launcher chạy lại qua `run.sh status` thành công.
5. Vấn đề còn: phiên bản/model/tool calling 9Router thật chưa xác minh; PowerShell/Windows chưa chạy; workspace được giao không có nội dung dự án hay Git metadata. Không tuyên bố pass các mục đó.
6. Tiếp theo: trên máy có 9Router/Windows, chạy doctor, thử tool call trên repo có test, xác nhận PowerShell và cấu hình thực.

## 2026-10-21 16:10 UTC — V-01

1. Đã làm: Chạy lại kiểm thử sau khi bổ sung provider auth/model errors, root-level file listing, workspace revision guard và launcher PYTHONPATH. Hoàn tất tài liệu kiểm thử/handoff.
2. File thay đổi: `agent_harness/provider.py`, `agent_harness/tools.py`, `tests/test_core.py`, `run.sh`, `run.ps1`, `README.md`, `docs/PLAN.md`, `docs/TESTING.md`, `docs/HANDOFF.md`, file này.
3. Kiểm tra: `python3 -m unittest discover -s tests -v` — 15/15 pass; `python3 -m compileall -q agent_harness tests` — pass; `bash -n scripts/bootstrap.sh run.sh` — pass; `AGENT_HARNESS_HOME=/tmp/haness-bootstrap-check ./run.sh status` — exit 0.
4. Vấn đề còn: Windows/PowerShell và 9Router thật chưa thử; sandbox chặn localhost và repo không có source/Git history. Không thể xác nhận tool calling của model đang cấu hình.
5. Bước tiếp theo: chạy `doctor`, task nhỏ tool-call và test suite trên repo/Windows mục tiêu có quyền thực thi; không cài hay thay cấu hình router qua harness.

## 2026-10-21 16:11 UTC — V-02

1. Đã làm: Ràng buộc fallback theo tool-calling capability được operator xác nhận; từ chối fallback với lỗi auth/model-not-found. Thêm test fallback gate.
2. File thay đổi: `agent_harness/config.py`, `agent_harness/runtime.py`, `tests/test_core.py`, `README.md`, `docs/DECISIONS.md`, docs kiểm thử/handoff.
3. Kiểm tra: toàn bộ 16 unit tests pass; compileall, bash syntax, launcher status pass.
4. Vấn đề còn: xác nhận năng lực model phụ bằng router thật chưa thể làm trong sandbox.
5. Bước tiếp theo: bàn giao; trên máy có 9Router cần chạy thử model chính/phụ và tool call.
# 2026-10-22 — UI-01: Thiết kế giao diện web cục bộ

1. Thời gian/mã bước: 2026-10-22 (Asia/Bangkok), `UI-01`.
2. Đã làm: đọc runtime, store, CLI, tools, README và trạng thái handoff; soạn spec web UI loopback dùng lại backend hiện tại, một worker nền, API/UI, yêu cầu an toàn và tiêu chí nghiệm thu.
3. File thay đổi: `docs/specs/2026-10-22-local-web-ui.md`, `docs/PLAN.md`, `docs/PROGRESS.md`.
4. Kiểm tra: đối chiếu các API/method trong spec với `Runtime`, `Store`, `Tools` và `cli.py`; chưa chạy test vì bước này chỉ lập đặc tả, chưa đổi mã.
5. Còn tồn tại: spec cần người dùng duyệt trước khi bắt đầu triển khai theo quy trình thiết kế.
6. Tiếp theo: sau khi được duyệt, lập kế hoạch triển khai chi tiết rồi thêm server/API/UI, wiring CLI và kiểm tra theo tiêu chí spec.

## 2026-10-22 — UI-02: Được duyệt và lập kế hoạch triển khai

1. Thời gian/mã bước: 2026-10-22 (Asia/Bangkok), `UI-02`.
2. Đã làm: người dùng duyệt triển khai và yêu cầu web phục vụ các chức năng đã nêu; chốt phạm vi UI bao phủ toàn bộ coding-agent CLI hiện có. Lập implementation plan cho API/worker, UI, wiring CLI và nghiệm thu.
3. File thay đổi: `docs/plans/2026-10-22-local-web-ui.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/specs/2026-10-22-local-web-ui.md`.
4. Kiểm tra: đối chiếu kế hoạch với spec và API hiện hữu; chưa chạy test vì chưa có thay đổi runtime.
5. Vấn đề còn tồn tại: checkout không có `.git`, do đó không thể tạo worktree hoặc ghi commit; Windows và live 9Router chưa được kiểm tra ở bước này.
6. Bước tiếp theo: triển khai API/worker bảo mật và test provider giả, tiếp đó UI và lệnh CLI.

## 2026-10-22 — UI-03: API, worker, UI và CLI

1. Thời gian/mã bước: 2026-10-22 (Asia/Bangkok), `UI-03`.
2. Đã làm: thêm HTTP server loopback, session token, kiểm tra Host/Origin, giới hạn body/output, worker đơn, task APIs, stop/resume, startup recovery, doctor theo nút bấm, HTML/CSS/JS tiếng Việt, wiring `web` CLI. Bổ sung che secret cả trường task request trong SQLite. Sửa Git tools để trả thông báo ngắn ở workspace không có `.git`.
3. File thay đổi: `agent_harness/webserver.py`, `agent_harness/web/`, `agent_harness/cli.py`, `agent_harness/store.py`, `agent_harness/tools.py`, `tests/test_web.py`, `tests/test_core.py`, README và docs.
4. Kiểm tra: provider giả test task chạy nền/ghi file, doctor, status responsive, stop-resume không lặp tool, auth/token/origin/body limits, stale task recovery và secret response; browser mở trên `127.0.0.1:8765`, kiểm tra trang và Git fallback.
5. Kết quả: `python3 -m unittest discover -s tests -v` — 29 tests pass; `python3 -m compileall -q agent_harness tests` pass; `bash -n run.sh scripts/bootstrap.sh` pass; `node --check agent_harness/web/app.js` pass. Không gửi request tới 9Router thật.
6. Còn tồn tại: Windows và 9Router thật chưa xác minh; workspace không có metadata Git nên không thể kiểm tra diff/commit. Export/import/configure/update vẫn dùng CLI. Scheduler, document ingestion, multi-agent, long-term memory và deployment vẫn chưa triển khai đầy đủ.
7. Tiếp theo: dùng web UI đang chạy tại `http://127.0.0.1:8765/`; mở một coding task thực tế khi sẵn sàng. Dùng `Ctrl+C` ở terminal nếu cần dừng server.

## 2026-10-22 — UI-04: Giới hạn output và kiểm tra trình duyệt

1. Thời gian/mã bước: 2026-10-22 (Asia/Bangkok), `UI-04`.
2. Đã làm: giới hạn tổng API response 512 KiB, giới hạn task/event text và số event trả về; sửa Git status/diff ngoài repository để không trả usage dài; hoàn tất docs/handoff.
3. File thay đổi: `agent_harness/webserver.py`, `agent_harness/tools.py`, `tests/test_web.py`, docs dự án.
4. Kiểm tra: 29 tests pass; compileall, Bash syntax, JavaScript syntax pass. CUA mở trang trên `127.0.0.1:8765`, status cho thấy `cx/gpt-6-luna`, command tắt; Git diff panel hiển thị trạng thái gọn. Doctor UI thành công với router thật; smoke task qua Runtime gọi `list_files` một lần, hoàn tất, dùng workspace/SQLite tạm và đã dọn.
5. Vấn đề còn: 9Router phiên bản cài đặt, auth/model-not-found/timeout/provider outage chưa thử trên router thật; Windows chưa kiểm tra; không có Git metadata trong checkout.
6. Bước tiếp theo: sử dụng web UI; nếu cần chạy lại, `./run.sh web` sau khi dừng process hiện tại.

## 2026-10-22 18:00 Asia/Bangkok — UI-05: Nhận biết workspace hiện tại

1. Thời gian/mã bước: 2026-10-22 18:00 Asia/Bangkok, `UI-05`.
2. Đã làm: làm rõ thanh đầu trang bằng nhãn “Workspace hiện tại”, tên thư mục và đường dẫn đầy đủ; nhấn đường dẫn để sao chép. `/api/status` trả thêm `workspace_name`, giữ `workspace` là đường dẫn cấu hình.
3. File thay đổi: `agent_harness/web/index.html`, `agent_harness/web/app.css`, `agent_harness/web/app.js`, `agent_harness/webserver.py`, `tests/test_web.py`, `docs/PLAN.md`, `docs/TESTING.md`, `docs/HANDOFF.md`.
4. Kiểm tra: `python3 -m unittest discover -s tests -v` — 29/29 pass; `python3 -m compileall -q agent_harness tests` — pass; `node --check agent_harness/web/app.js` — pass.
5. Vấn đề còn: chưa chạy kiểm tra hình ảnh ở kích thước desktop/mobile trong browser cho thay đổi này; đường dẫn dài có thể được cắt gọn trên thanh hẹp, nhưng vẫn đầy đủ trong API và clipboard.
6. Bước tiếp theo: dùng thanh workspace để xác nhận repo trước khi gửi tác vụ; tiếp tục cập nhật cả logic và UI cho tính năng mới theo yêu cầu người dùng.

## 2026-10-22 — UI-06: Chọn workspace và đặt tên task

1. Thời gian/mã bước: 2026-10-22 (Asia/Bangkok), `UI-06`.
2. Đã làm: thêm trường tên task và workspace riêng; migration SQLite thêm `name` và backfill task cũ; Runtime dùng workspace lưu trên task khi chạy/resume; API duyệt tối đa 200 thư mục con (POST có token), xác thực workspace tồn tại; UI đặt tên, nhập đường dẫn hoặc duyệt, hiển thị đường dẫn theo task và Git review đúng workspace. Export/import giữ lại tên task.
3. File thay đổi: `agent_harness/store.py`, `runtime.py`, `webserver.py`, `web/index.html`, `web/app.js`, `web/app.css`, `cli.py`, `tests/test_core.py`, `tests/test_web.py`, `README.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/TESTING.md`, `docs/HANDOFF.md`.
4. Kiểm tra: `python3 -m unittest discover -s tests -v` — 33/33 pass; `python3 -m compileall -q agent_harness tests` — pass; `node --check agent_harness/web/app.js` — pass; `bash -n run.sh scripts/bootstrap.sh` — pass.
5. Vấn đề còn: Directory browser liệt kê folder con trực tiếp, mỗi lần tối đa 200; có thể nhập path đầy đủ. Web server loopback không phải OS sandbox; quyền subprocess giữ nguyên như tiến trình Haness.
6. Bước tiếp theo: dùng composer để tạo từng task với tên và workspace phù hợp; các chức năng mới tiếp tục được bổ sung đồng thời vào logic và UI.


## 2026-10-22 — UI-07: Thiết kế framework và model catalog

1. Thời gian/mã bước: 2026-10-22 (Asia/Bangkok), `UI-07`.
2. Đã làm: đọc hướng dẫn repo/handoff, khảo sát UI/provider hiện có, xác minh runtime Node/npm, hỏi và nhận xác nhận rằng add/edit/delete model chỉ thay hồ sơ cục bộ Haness. Thử authenticated `GET {base_url}/models`: HTTP 200, 24 IDs; thử `/health`: 404. Chốt dự thảo Preact + Vite, live catalog read-only, SQLite profiles/settings, model action gate và task model pinning.
3. File thay đổi: `docs/specs/2026-10-22-web-ui-and-model-catalog-design.md`, `docs/plans/2026-10-22-preact-router-model-catalog.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/HANDOFF.md`.
4. Kiểm tra: data-first design checker — PASS; đối chiếu API model với tài liệu 9Router và response live, không in API key. Người dùng duyệt đặc tả. Kế hoạch chia 7 bước, gồm hợp đồng dữ liệu/API, test provider và SQLite, UI components, gate, serving, docs. Chưa sửa runtime/UI và chưa chạy test.
5. Vấn đề còn: Plannotator không cài; repo không có Git metadata. Model tools capability không được suy ra từ danh sách models endpoint. Đặc tả và kế hoạch đã được người dùng duyệt.
6. Bước tiếp theo: triển khai theo kế hoạch 7 bước đã duyệt.

### UI-07 implementation — bước 1 và 2

1. Thời gian/mã bước: 2026-10-22 (Asia/Bangkok), `UI-07-01/02`.
2. Đã làm: thêm `NineRouterClient.list_models()` với Bearer auth, GET `/models`, giới hạn đọc 1 MiB + 1 byte để phát hiện quá cỡ, xác thực cấu trúc `data[].id`, tối đa 1.000 ID duy nhất, retry transient riêng và thông báo lỗi không chứa body/key. Thêm migration SQLite cho `model_profiles` và `settings`, local profile CRUD có validation/unique ID/giới hạn 200, và setting `web.selected_model_id`.
3. File thay đổi: `agent_harness/provider.py`, `agent_harness/store.py`, `tests/test_core.py`, `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/TESTING.md`.
4. Kiểm tra: `python3 -m unittest tests.test_core.ProviderTests -v` — 7/7 pass; `python3 -m unittest tests.test_core.StoreMigrationTests -v` — 2/2 pass. Lỗi provider giả lập bao gồm auth, 404, 503, timeout, JSON rỗng/sai và giới hạn kích thước/số lượng; kiểm tra CRUD và reopen DB.
5. Vấn đề còn tồn tại: API/UI chưa nối catalog; chưa thử router thật sau phần code này; lỗi duplicate giới hạn qua API sẽ được hoàn thiện ở bước 3.
6. Bước tiếp theo: truyền model qua Runtime và API; revalidate catalog trước create/resume.

### UI-07 implementation — bước 3

1. Thời gian/mã bước: 2026-10-22 (Asia/Bangkok), `UI-07-03`.
2. Đã làm: Runtime nhận model theo task nhưng giữ mặc định CLI; thêm `/api/models`, local profile GET/POST/PUT/DELETE, model selection; API create/resume gọi catalog live và từ chối trước khi tạo task/worker nếu router lỗi hoặc model không còn khả dụng. Catalog API chỉ trả ID, profile và lỗi đã làm sạch.
3. File thay đổi: `agent_harness/runtime.py`, `agent_harness/webserver.py`, `tests/test_web.py`, `tests/test_core.py`, docs.
4. Kiểm tra: `python3 -m unittest discover -s tests -v` — 40/40 pass, gồm profile CRUD, lựa chọn model, create/resume offline, model vắng mặt và giữ trạng thái paused.
5. Vấn đề còn tồn tại: giao diện hiện tại chưa dùng API catalog mới; task UI cũ đang lấy model mặc định nhưng backend đã kiểm tra live. Chưa kiểm tra trên Windows.
6. Bước tiếp theo: thêm toolchain Preact/Vite và chia frontend thành component.

### UI-07 implementation — bước 4–7 (hoàn tất)

1. Thời gian/mã bước: 2026-10-22 (Asia/Bangkok), `UI-07-04/05/06/07`.
2. Đã làm: thêm Preact/Vite với phiên bản chính xác và npm lockfile; tách App, ConnectionBanner, TaskSidebar, TaskComposer, WorkspacePicker, ModelPicker, ModelProfileManager, TaskDetail và GitReview; gate UI ở trạng thái checking/disconnected; startup và retry chỉ gọi `/api/models`; model selection nhớ trong SQLite và gửi model ID trong task; local profile create/edit/delete; server phục vụ bundle hash cùng origin, giới hạn đường dẫn và giữ CSP/session token/loopback guards; bổ sung README, testing và handoff.
3. File thay đổi: `web-ui/`, `agent_harness/web/dist/`, `agent_harness/webserver.py`, `agent_harness/runtime.py`, `agent_harness/provider.py`, `agent_harness/store.py`, `tests/`, `.gitignore`, `README.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/TESTING.md`, `docs/HANDOFF.md`.
4. Kiểm tra: `npm ci --no-audit --no-fund` — pass; `npm test` — 4/4 pass; `npm run build` — pass (bundle 31.75 kB JS, 15.45 kB CSS trước gzip); `python3 -m unittest discover -s tests -v` — 40/40 pass; `python3 -m compileall -q agent_harness tests` — pass; `bash -n run.sh scripts/bootstrap.sh` — pass. Trình duyệt thật mở UI loopback với model catalog 9Router live; thao tác tạo/sửa/xóa profile thử nghiệm hoàn tất và profile thử đã xóa.
5. Vấn đề còn tồn tại: Windows chưa kiểm tra. Chưa có browser-level outage injection; trạng thái offline và retry được kiểm tra component/API với provider giả. Checkout không có Git metadata; không thể tạo diff/commit. Bundle runtime Node-free; rebuild UI cần Node.js 24+ và npm.
6. Bước tiếp theo: tiếp tục dùng `./run.sh web`; task mới bị khóa khi 9Router không kết nối; resume kiểm tra model pin trên task.

### UI-08 — kết nối router và danh mục model chỉ đọc

1. Thời gian/mã bước: 2026-10-22 (Asia/Bangkok), `UI-08`.
2. Đã làm: bỏ CRUD hồ sơ model khỏi API, store và UI; model picker chỉ đọc các ID từ catalog 9Router. Thêm điều khiển Base URL, connect/disconnect; trạng thái và URL lưu trong SQLite Haness. Khi disconnect, API chặn task/resume; reconnect chỉ lưu URL sau khi thử catalog thành công. UI cảnh báo API key cấu hình trong Haness sẽ được gửi đến URL đã nhập.
3. File thay đổi: `agent_harness/store.py`, `agent_harness/webserver.py`, `tests/test_core.py`, `tests/test_web.py`, `web-ui/src/App.jsx`, `web-ui/src/App.test.jsx`, `web-ui/src/components/ModelPicker.jsx`, `web-ui/src/components/TaskComposer.jsx`, `web-ui/src/components/RouterConnection.jsx`, `web-ui/src/components/ModelProfileManager.jsx` (xóa), `web-ui/src/styles.css`, `agent_harness/web/dist/`, `README.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/TESTING.md`, `docs/HANDOFF.md`.
4. Kiểm tra: `python3 -m compileall -q agent_harness tests` và `bash -n run.sh scripts/bootstrap.sh` — pass; `./.venv/bin/python -m unittest discover -s tests -v` — 43/43 pass; từ `web-ui/`, `npm test` — 4/4 pass và `npm run build` — pass (JS 30.57 kB/CSS 15.09 kB trước gzip). Live API smoke local `/v1/models`: 24 models; disconnect chuyển offline; reconnect cùng URL khôi phục 24 models. HTTP xác nhận bundle UI-08 được serve.
5. Vấn đề còn tồn tại: Windows chưa kiểm tra. Endpoint server từ xa chưa có để thử; khi người dùng nhập URL server, cần kiểm tra địa chỉ vì API key sẽ được gửi đến đó. Browser URL policy chặn xem trang trong phiên này nên UI được xác minh bằng frontend tests/build và API smoke.
6. Bước tiếp theo: có thể dùng Web UI mới tại `http://127.0.0.1:8765/`; kiểm thử Windows và endpoint server khi có môi trường/URL phù hợp.
