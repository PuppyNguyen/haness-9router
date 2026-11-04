# Kế hoạch triển khai Agent Harness

Môi trường này là Linux trong sandbox; thư mục repo được giao ban đầu trống, không có hướng dẫn repo hay trạng thái Git sử dụng được. Python 3.14.4 có sẵn, Docker CLI có, PowerShell/Windows và kết nối localhost chưa xác minh. Tài liệu 9Router hiện tại mô tả OpenAI-compatible Chat Completions tại `/v1`, endpoint local mặc định `http://localhost:20128/v1`, khóa từ dashboard và model lấy từ router. Không tự chọn model; endpoint local không thể dò từ sandbox.

## Kiến trúc tối thiểu

Ứng dụng Python không phụ thuộc runtime bên ngoài; SQLite, urllib, argparse và subprocess từ thư viện chuẩn. Module config giữ cấu hình; `NineRouterClient` chỉ gọi API OpenAI Chat Completions; tool registry cung cấp file, tìm kiếm, git và command; policy giới hạn file vào workspace và kiểm soát lệnh; store lưu task, session, message, events/checkpoint bằng SQLite; runtime nối model/tool theo giới hạn, lưu từng bước trước khi tiếp tục. CLI nhận yêu cầu, resume, status, doctor, stop, export/import. Công cụ đường dẫn không phải sandbox: subprocess vẫn có quyền của tiến trình.

## Trạng thái theo giai đoạn

- [x] A — kiểm tra môi trường, repo, tài liệu 9Router công khai; lưu giới hạn máy thực thi.
- [x] B — coding agent CLI và tool adapter 9Router; kiểm thử provider giả lập. Request thật chờ môi trường có quyền localhost.
- [x] C — checkpoint/resume, giới hạn, quyền, structured events và che secret.
- [x] D — bootstrap Linux/Windows, launcher, backup/restore và hướng dẫn. Windows script chưa chạy.
- [x] E — hợp đồng mở rộng tài liệu, workflow/lịch, agent registry, memory và deployment; subsystem chưa triển khai.
- [x] UI-01 — đặc tả đã được duyệt; triển khai theo `docs/plans/2026-10-22-local-web-ui.md`, bao gồm UI cho toàn bộ luồng coding agent hiện có. Web UI mở tại `http://127.0.0.1:8765/`; 29 test pass. Live 9Router/Windows chưa kiểm tra.
- [x] UI-05 — hiển thị tên và đường dẫn đầy đủ workspace đang hoạt động ở thanh đầu trang; có thể nhấn để sao chép đường dẫn. API status trả tên + đường dẫn; 29 test pass.
- [x] UI-06 — workspace chọn riêng cho từng task (nhập đường dẫn hoặc duyệt folder), tên task tùy chỉnh, lưu bền vững và resume đúng workspace; 33 test pass.
- [x] UI-07 — Preact/Vite components, startup model-catalog gate, model picker, SQLite selection persistence, and backend fail-closed create/resume completed. Windows UI/runtime remains unverified.
- [x] UI-08 — removed Haness model-profile management; model selection reads the live 9Router catalog. Added persisted disconnect/reconnect and editable local/server Base URL, with backend gate and URL validation. Tests and local router smoke in `docs/TESTING.md`; Windows remains unverified.

## Kế hoạch bước nhỏ

1. `A-01` kiểm tra chỉ đọc và tra tài liệu 9Router. Kết quả: môi trường và giới hạn nêu trên.
2. `B-01` viết kiểm thử cho cấu hình, policy đường dẫn và client OpenAI-compatible bằng provider giả lập; chạy RED. Hoàn tất: import thất bại đúng vì module chưa tồn tại.
3. `B-02` triển khai package/config/client/tool registry và SQLite; chạy GREEN.
4. `B-03` triển khai runtime CLI với planner/tool loop, diff, kiểm tra và báo cáo; kiểm tra tích hợp giả.
5. `C-01` checkpoint theo bước, resume task, trạng thái, giới hạn request/time và phát hiện lặp; kiểm tra ngắt/resume.
6. `C-02` quyền lệnh/file, logging, che secret và test lỗi provider/retry; xác nhận hành động tool không tự retry.
7. `D-01` bootstrap bash/PowerShell idempotent, cấu hình an toàn, lệnh doctor/status/stop/resume/update, export/import.
8. `E-01` tài liệu hợp đồng module mở rộng và bảng mức hoàn thành.
9. `V-01` Hoàn tất phần có thể kiểm chứng: unit suite, compile, bash syntax, Linux launcher. Live 9Router/Windows chưa kiểm tra vì sandbox/môi trường không hỗ trợ.

Mỗi bước sẽ cập nhật `docs/PROGRESS.md`, `docs/TESTING.md` và trạng thái ở đây; checkpoint runtime là dữ liệu SQLite có cấu trúc, độc lập nhật ký Markdown.
