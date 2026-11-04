# Quyết định kiến trúc

## ADR-001 — Python modular monolith, không phụ thuộc runtime package

- Bối cảnh: repo trống; Python 3.14 có sẵn; mục tiêu bootstrap cho Linux/Windows.
- Quyết định: Python stdlib cho CLI, SQLite, HTTP và subprocess; adapter OpenAI-compatible riêng; phụ thuộc bên ngoài bằng 0 để bootstrap hoạt động offline.
- Lý do: dễ cài và audit, không khóa framework/provider.
- Hệ quả: client HTTP/tool-call parsing do harness quản lý; chưa thử nghiệm mọi biến thể 9Router.

## ADR-002 — Tách dữ liệu runtime khỏi checkout

- Dùng `~/.haness-9router` (có thể override `AGENT_HARNESS_HOME`) cho SQLite/log/config; cấu hình bí mật chỉ từ env hoặc file cấu hình user không commit.
- Repository đích là workspace riêng; file tools kiểm tra root chuẩn hóa, symlink và loại file đặc biệt.

## ADR-003 — Mặc định an toàn, không tuyên bố sandbox

- Thay đổi workspace qua tool chỉ trong root cho phép; command execution bị tắt mặc định và chỉ chạy khi allowlist đã cấu hình.
- Path guard không giới hạn subprocess; subprocess kế thừa quyền OS. Không gọi thiết kế này là sandbox.
- Model request retry chỉ áp dụng request idempotent chưa phát tool action; mỗi tool action tối đa một lần, có event ID lưu bền vững.

## ADR-004 — 9Router không bị quản lý bởi harness

- Chỉ kết nối endpoint cấu hình; không cài, sửa, dừng hay ghi đè 9Router. Base URL default theo tài liệu (`http://localhost:20128/v1`), model để trống yêu cầu người dùng cấu hình.
- Tool calling tùy thuộc model/provider; cần doctor/integration thử thật để xác nhận.

## ADR-005 — Fallback cần xác nhận năng lực tool calling

- Runtime gửi tool schemas cho coding agent; model phụ chỉ được dùng nếu `AGENT_HARNESS_FALLBACK_MODEL` có giá trị và operator đã thử tool calling rồi đặt `AGENT_HARNESS_FALLBACK_TOOL_CALLING=true`.
- Lỗi 401/403/404 không trigger fallback; lỗi tạm thời có thể dùng model đã xác nhận. Harness không suy luận năng lực từ tên model.

## ADR-006 — UI chỉ đọc model catalog và điều khiển kết nối Haness

- Không lưu hồ sơ model riêng trong Haness; UI tải danh sách model từ 9Router và cho chọn trực tiếp.
- Base URL đang dùng và trạng thái disconnect lưu trong SQLite Haness; config file gốc của 9Router/Haness không bị ghi đè.
- Connect xác thực URL HTTP(S) và chỉ cập nhật endpoint sau khi catalog đọc thành công. API key vẫn ở backend nhưng sẽ được gửi đến Base URL do người dùng nhập, kể cả server từ xa; UI cảnh báo trước.
- Disconnect chặn task mới và resume ở UI lẫn backend. Task đang chạy không bị hủy cưỡng bức; dừng task vẫn dùng thao tác Stop riêng.
- Bảng model profile legacy nếu có từ bản cũ được giữ nguyên, không migrate/xóa dữ liệu người dùng tự động; app mới không tạo hay dùng bảng này.
