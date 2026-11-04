# Agent Harness cá nhân cho 9Router

Agent Harness là coding agent CLI dạng modular monolith, kết nối tới 9Router hiện có qua API Chat Completions tương thích OpenAI. Harness không cài, thay cấu hình hay quản lý vòng đời 9Router.

## Yêu cầu

- Python 3.11 trở lên.
- 9Router đang chạy hoặc endpoint tương thích được cấp quyền; API key lấy từ dashboard.
- Model ID phải tồn tại trong cấu hình 9Router và hỗ trợ tool calling để agent có thể dùng file tools. Trang docs 9Router liệt kê các model thay đổi theo cấu hình; không có model mặc định trong harness.
- Runtime riêng `.venv`, tạo bằng Python `venv --without-pip`; không cần tải package bên ngoài vì dùng thư viện chuẩn. `requirements.lock` ghi rõ dependency bằng không.

Trang [tài liệu 9Router](https://docs.9router.com/) mô tả endpoint local `http://localhost:20128/v1`, API OpenAI-compatible; [hướng dẫn tích hợp](https://github.com/decolua/9router/blob/master/gitbook/content/en/integration/other-tools.md) nêu API key từ dashboard và model ID do cài đặt chọn. Cần kiểm tra lại với phiên bản router đang dùng vì docs/model thay đổi.

## Cài đặt nhanh

Linux Bash:

```bash
bash scripts/bootstrap.sh
```

Windows PowerShell:

```powershell
.\scripts\bootstrap.ps1
```

Bootstrap tạo `.venv` trong checkout, hỏi Base URL, model ID và API key (ẩn khi nhập), lưu cấu hình ở `~/.haness-9router/config.env` (Windows: `%USERPROFILE%\.haness-9router\config.env`), rồi thử một request thật tới 9Router. Nếu Python chưa có, cần cài Python thủ công; bootstrap không tải runtime hệ thống. Không cần admin, Docker Desktop hay WSL. Chế độ chạy từ repo cục bộ hoạt động; URL phát hành chưa được cấu hình, nên update không tự tải binary/repo.

Sau cài đặt, chạy lại:

```bash
./run.sh run "Tìm và sửa lỗi ..."
```

Launcher có thể gọi bằng đường dẫn đầy đủ từ thư mục khác; workspace mặc định là thư mục hiện tại của shell.

```powershell
.\run.ps1 run "Tìm và sửa lỗi ..."
```

PowerShell cần cho phép chạy script theo chính sách máy; nếu policy chặn, dùng `powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1` theo quy định của máy. Không có Windows để xác minh ở phiên này.

## Cấu hình

Bootstrap lưu cấu hình ngoài repo, không commit. Có thể override bằng biến môi trường:

| Biến | Mặc định / nghĩa |
|---|---|
| `AGENT_HARNESS_BASE_URL` | `http://localhost:20128/v1` theo docs 9Router |
| `AGENT_HARNESS_API_KEY` | API key dashboard; không ghi log |
| `AGENT_HARNESS_MODEL` | Bắt buộc; model ID đúng như router cấu hình |
| `AGENT_HARNESS_FALLBACK_MODEL` | Tùy chọn, do người dùng chọn; có thể không tương đương về năng lực |
| `AGENT_HARNESS_FALLBACK_TOOL_CALLING` | Mặc định `false`; chỉ đặt `true` sau khi đã thử tool calling cho model phụ |
| `AGENT_HARNESS_TIMEOUT` | 60 giây mỗi request |
| `AGENT_HARNESS_RETRIES` | 2 lần retry request provider cho lỗi tạm thời |
| `AGENT_HARNESS_MAX_REQUESTS` | 24 lượt model mỗi task |
| `AGENT_HARNESS_MAX_SECONDS` | 900 giây mỗi lần chạy task |
| `AGENT_HARNESS_WORKSPACE` | Workspace hiện tại; mặc định thư mục lệnh chạy |
| `AGENT_HARNESS_HOME` | Dữ liệu/config; mặc định `~/.haness-9router` |
| `AGENT_HARNESS_ALLOW_COMMANDS` | Tên executable phân cách dấu phẩy; mặc định rỗng, tức tắt command tool |

Lệnh `configure` không ghi đè file đã có. Linux đặt mode file cấu hình là `0600`; Windows dùng ACL kế thừa user profile. Có thể dùng secret manager rồi chỉ inject API key qua environment thay vì lưu key trong file.

## Vận hành

```bash
./run.sh doctor
./run.sh status
./run.sh run "Thêm kiểm tra cho hàm parse_config"
./run.sh resume <task-id>
./run.sh stop <task-id>
./run.sh export backup.json
./run.sh import backup.json
./run.sh update
```

### Giao diện web cục bộ

Sau khi bootstrap đã tạo runtime và cấu hình 9Router, chạy:

```bash
./run.sh web
```

Lệnh mở giao diện trong trình duyệt tại `http://127.0.0.1:8765/`. Nhấn `Ctrl+C` trong terminal để dừng. Có thể dùng `./run.sh web --no-browser` để chỉ in URL hoặc `./run.sh web --port 8766` nếu cổng mặc định đang bận. PowerShell dùng `.\run.ps1 web` với các tùy chọn tương tự. Chỉ bind loopback; địa chỉ mạng như `0.0.0.0` bị từ chối.


Frontend được viết bằng Preact và build tĩnh bằng Vite. Chỉ cần Python runtime để chạy Haness; Node.js/npm chỉ cần khi sửa UI hoặc rebuild bundle. Sau khi thay UI, dùng Node.js 24.18+:

```bash
cd web-ui
npm ci
npm test
npm run build
```

Build được ghi vào `agent_harness/web/dist` và Python server phục vụ cùng origin. Không tải framework từ CDN và không cần sửa mã nguồn để đổi model.

Web UI dùng chung coding-agent runtime, task/session/checkpoint SQLite và quyền đang cấu hình. Khi mở, Haness kiểm tra `GET /v1/models` của 9Router; đến khi kết nối thành công, không thể chọn model, gửi task hay resume. Bộ chọn chỉ hiển thị danh sách model hiện có từ router, không tạo hồ sơ model trong Haness. Có thể ngắt kết nối trong UI; trạng thái ngắt được lưu và backend từ chối task mới/resume cho đến khi kết nối lại. Đổi Base URL cho phép dùng 9Router local hoặc server tương thích; Haness thử `GET /models` trước và chỉ lưu địa chỉ sau khi thành công. API key lấy từ cấu hình hiện có của Haness, không gửi xuống trình duyệt; khi bấm kết nối, key được gửi đến Base URL đã nhập, vì vậy hãy xác minh địa chỉ trước khi kết nối tới server từ xa. Task mới lưu ID model đã chọn, resume xác thực lại ID đó. Có thể gửi yêu cầu coding (agent dùng các file/search/patch/command tools hiện có theo policy), theo dõi event và câu trả lời, dừng/tiếp tục task, xem Git status/diff. Trước khi gửi, đặt tên task và chọn thư mục làm việc riêng cho task; nhập đường dẫn tuyệt đối hoặc duyệt thư mục con. Workspace đã chọn được lưu cùng task, hiển thị trong chi tiết, và dùng lại khi resume. Chọn workspace chỉ giới hạn các file tools; command được bật vẫn chạy bằng quyền OS của tiến trình Haness, không phải sandbox. Một task chạy tại một thời điểm để tránh hai agent sửa cùng working tree. Dừng là cooperative: request model đang chạy có thể cần kết thúc hoặc timeout trước khi runtime dừng ở ranh bước. Nếu tiến trình bị tắt đột ngột, task còn `running` sẽ thành `paused` khi mở web lần sau; task có tool call dở dang vẫn bị từ chối resume theo quy tắc hiện có. Export/import, configure, update và bootstrap vẫn chạy từ CLI/launcher; không có release URL để tự cập nhật.

Server tạo token ngẫu nhiên theo phiên, kiểm tra Host/Origin, không bật CORS và không ghi request vào access log. API key không được gửi xuống trình duyệt. Đây là giao diện cục bộ, không có đăng nhập cho nhiều người dùng và không phải OS sandbox: các công cụ/subprocess vẫn chạy với quyền của tài khoản hiện tại. Web UI không tự bật command tool; `AGENT_HARNESS_ALLOW_COMMANDS` tiếp tục mặc định rỗng. Giao diện này bao phủ các chức năng coding-agent hiện có; scheduler, ingest tài liệu, multi-agent, memory dài hạn và deploy vẫn là các extension tương lai, chưa hoạt động.

Lệnh PowerShell tương đương dùng `.\run.ps1`. Task ID và session ID được in khi tạo. SQLite ở `~/.haness-9router/state.sqlite3` (WAL); không nằm trong checkout, nên thay checkout không xóa trạng thái. `stop` ghi trạng thái dừng; request mạng đồng bộ kết thúc hoặc timeout trước khi bước mới dừng. `resume` dùng workspace đã lưu trên task, so sánh tên repo và Git revision đã ghi, và từ chối nếu checkout thay đổi. Task import cần có Git revision để xác minh; nếu nguồn không phải Git repo, phải kiểm tra thủ công và tạo task mới. Trạng thái tool call không xác định bị từ chối để tránh lặp tác dụng phụ. Task đã hoàn tất không chạy lại.

`export` tạo JSON lịch sử task/checkpoint, loại bỏ workspace root; `import` đưa task về workspace hiện tại ở trạng thái paused (không tự chạy). Credential, cookie đăng nhập và config không được export. Tránh đưa secret vào prompt/task hoặc repository vì lịch sử cần thiết cho resume được lưu trong SQLite. Có thể xóa task qua SQLite/backup theo chính sách retention cá nhân; lệnh xóa chưa có trong CLI bản này.

### Quyền thực thi

File tools gồm list, search, read, write (diff preview), Git status/diff và command. File tools kiểm tra đường dẫn chuẩn hóa và symlink bên ngoài workspace. Command tool bị tắt mặc định; chỉ cho phép khi executable đầu tiên khớp `AGENT_HARNESS_ALLOW_COMMANDS`, ví dụ `AGENT_HARNESS_ALLOW_COMMANDS=python3,git`. Lệnh chạy với quyền của người dùng hệ điều hành và không bị giới hạn ở workspace; path guard không phải sandbox. Chỉ bật executable cần thiết và không đưa input không tin cậy vào lệnh.

Agent đọc `AGENTS.md` và hướng dẫn repo liên quan trước khi sửa; tuy nhiên tool command bị tắt mặc định nên kiểm thử/build chỉ chạy khi người vận hành bật allowlist phù hợp. Agent phải báo rõ lệnh nào chưa chạy. Retry áp dụng cho request model; không retry tool action. Hành động có event ID và kết quả được lưu trước lượt kế tiếp.

### 9Router và lỗi provider

`doctor` gọi Chat Completions model đã cấu hình để kiểm tra endpoint, xác thực và model. Điều này phát sinh một request đến provider. Khi test thật thất bại, doctor in hướng xử lý tổng quát, không in header/key/body response. Kiểm tra tool calling bằng task nhỏ thực tế; model có thể từ chối/không hỗ trợ tools. Streaming chưa dùng. Fallback chỉ dùng cho lỗi tạm thời nếu có model phụ và `AGENT_HARNESS_FALLBACK_TOOL_CALLING=true`; lỗi auth/model-not-found không fallback. Người vận hành phải thử tool calling cho model phụ trước vì harness không thể suy ra năng lực từ tên model.

### Chuyển máy/khôi phục

1. Chạy `export` ở máy cũ và chuyển file JSON qua kênh riêng.
2. Cài repo/runtime và cấu hình router trên máy mới; không sao chép key/config hay `.venv` cũ.
3. Chạy `import` tại checkout mới; task được gắn với workspace hiện tại, paused và cần kiểm tra repo/revision thủ công trước `resume`.

Không resume nếu checkout khác nội dung mong muốn. Update thủ công bằng Git/checkout mới; dữ liệu ở thư mục user riêng. `update` hiện chỉ hướng dẫn, không tự tải vì chưa có release URL.

## Trạng thái tính năng

| Khả năng | Trạng thái |
|---|---|
| Coding agent CLI, OpenAI-compatible 9Router adapter | Đã triển khai; Chat Completions và một `list_files` tool call xác minh thật thành công; router version/error cases chưa kiểm tra |
| Web UI Preact/Vite cho coding task, workspace, tiến trình, stop/resume, Git review, model catalog và 9Router connect/disconnect | Đã triển khai; kiểm thử local 9Router ghi trong `docs/TESTING.md`; Windows chưa kiểm tra |
| List/search/read/write/Git tools | Đã triển khai, có giới hạn đầu ra và workspace path checks |
| Command với timeout/allowlist | Đã triển khai; mặc định tắt; không phải OS sandbox |
| SQLite task/session/events/checkpoint, resume/stop | Đã triển khai; resume từ tool call không rõ kết quả bị từ chối |
| Retry lỗi model, fallback tùy chọn, logging model | Đã triển khai; tool actions không tự retry |
| Bootstrap Linux | Có script; kiểm tra runtime trong môi trường hiện tại, chưa chạy end-to-end bootstrap sạch |
| Bootstrap Windows | Có PowerShell script; chưa kiểm tra trên Windows |
| Tài liệu ingest, workflow scheduler, multi-agent, memory, deploy | Mới có interface/phác thảo trong [docs/EXTENSIONS.md](docs/EXTENSIONS.md) |
| Docker, vector DB, distributed services | Chưa có; chưa cần cho bản đầu |

## Kiểm thử

```bash
python3 -m unittest discover -s tests -v
```

Kết quả và phần chưa kiểm chứng ghi trong [docs/TESTING.md](docs/TESTING.md); tiến độ bàn giao ở [docs/HANDOFF.md](docs/HANDOFF.md).
