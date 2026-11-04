# Mở rộng sau bản coding agent đầu tiên

Các contract bên dưới là điểm mở rộng; chưa có worker, scheduler, document ingest, vector database, memory store, multi-agent dispatcher hay deployment executor trong bản này.

## Tài liệu/kiến thức

Tạo adapter `DocumentLoader.load(source) -> Document(text, source_id, source_version, media_type)`; parser đầu tiên là Markdown/plain text. Metadata vị trí nguồn đi cùng mỗi chunk và kết quả retrieval. Nội dung nguồn là dữ liệu không đáng tin cậy, không thể thay system/developer policy. Kết quả trích xuất (yêu cầu ứng viên) tách khỏi quyết định được phép thực thi. Chỉ thêm embeddings khi đo được tìm kiếm từ khóa không đạt.

## Workflow và lịch

`Workflow(id, version, steps, dependencies, completion_criteria)` được lưu phiên bản và mỗi lần chạy có idempotency key. Scheduler độc lập phiên CLI, ghi timezone, trạng thái missed-run, lease/chống chạy chồng và chống trùng. Khi host/worker tắt, job lưu queued/missed và policy quyết định catch-up; không chạy ngầm nếu máy đã tắt. Ngày trong tài liệu chỉ gợi ý lịch, không kích hoạt lịch nếu chưa được ủy quyền.

## Agent registry

`AgentSpec(role, tools, permissions, model, budget, input_schema, output_schema, completion_criteria)` cùng giới hạn concurrency, depth, wall time. Một agent hiện tại là runtime; chưa có delegation. Không share write tree đồng thời; yêu cầu worktree hoặc serialization.

## Bộ nhớ

Tách session transcript, task/checkpoint, project memory, tài liệu và tùy chọn người dùng đã xác nhận. Record gồm source, scope, created/updated time, confidence/confirmed flag; hỗ trợ list/edit/delete/export. Không lưu secrets; truy xuất theo task và ngân sách context, không nạp toàn bộ.

## Deployment adapter

Contract cần target/environment/permission, preflight, reproducible build artifact/hash, health check, deployment history và rollback. Không có production deploy trong bản đầu.
