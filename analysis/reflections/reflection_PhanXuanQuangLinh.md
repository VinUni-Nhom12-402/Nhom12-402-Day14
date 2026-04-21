# Báo Cáo Cá Nhân - Lab Day 14

**Thành viên:** Phan Xuân Quang Linh  
**Mã HV:** 2A202600492
**Vai trò:** Agent optimizer
**Ngày:** 21/04/2026

---

## Công Việc Thực Hiện

**Nhiệm vụ chính:**

- Xây dựng `agent/main_agent.py` làm tác nhân chính cho hệ thống hỏi đáp RAG
- Thiết kế pipeline truy vấn gồm tiền xử lý câu hỏi, retrieval, rerank và sinh câu trả lời
- Tích hợp chế độ trả lời bằng LLM và cơ chế extractive fallback khi không dùng được LLM

**Key features:**

- `MainAgent` hỗ trợ truy vấn bất đồng bộ qua hàm `query`
- Kết hợp vector retrieval, lexical overlap và golden examples để tăng độ chính xác truy xuất
- Chuẩn hóa tiếng Việt không dấu, tách từ khóa và mở rộng truy vấn theo domain y tế
- Sinh metadata đầy đủ gồm nguồn dữ liệu, mô hình sử dụng, số token và chiến lược retrieval

---

## Khó Khăn & Giải Pháp

**Vấn đề:**

- Cần cải thiện độ chính xác retrieval khi câu hỏi ngắn hoặc nhiều cách diễn đạt khác nhau
- Phải bảo đảm hệ thống vẫn trả lời được khi thiếu API key hoặc LLM timeout
- Dữ liệu tiếng Việt có dấu và không dấu dễ gây lệch khi so khớp từ khóa

**Giải pháp:**

- Kết hợp nhiều tín hiệu chấm điểm gồm vector store, keyword overlap và similarity với golden set
- Thiết kế fallback extractive để hệ thống luôn có câu trả lời an toàn khi LLM không khả dụng
- Xây dựng hàm normalize, tokenize và stopwords để đồng nhất dữ liệu đầu vào

---

## Điều Học Được

**Kỹ năng kỹ thuật:**

- Thiết kế kiến trúc cho một RAG agent có khả năng mở rộng
- Lập trình bất đồng bộ với `asyncio` và kiểm soát timeout cho lời gọi LLM
- Xử lý text preprocessing cho tiếng Việt phục vụ retrieval
- Tổ chức code theo hướng dễ kiểm thử và tái sử dụng

**Kiến thức chuyên môn:**

- Cách kết hợp retrieval heuristic với few-shot examples từ golden set
- Nguyên tắc xây dựng câu trả lời bám sát context để giảm hallucination
- Vai trò của metadata trong đánh giá chất lượng và debug hệ thống RAG

---

## Đóng Góp

**Xây dựng:**

- Hoàn thiện file `main_agent.py` làm trung tâm xử lý cho luồng hỏi đáp
- Tạo cơ chế truy xuất thông minh dựa trên `SimpleVectorStore` và rerank theo ngữ nghĩa đơn giản
- Bổ sung chế độ trả lời linh hoạt giữa LLM và extractive fallback
- Hỗ trợ nạp `golden_set.jsonl` để tận dụng dữ liệu mẫu trong retrieval và generation

---

## Lời Kết

Quá trình phát triển `main_agent.py` giúp tôi hiểu rõ hơn cách xây dựng một tác nhân RAG hoàn chỉnh từ bước truy xuất dữ liệu đến sinh câu trả lời. Đây là phần việc quan trọng vì nó kết nối trực tiếp giữa dữ liệu, mô hình và trải nghiệm người dùng, đồng thời cho tôi thêm kinh nghiệm về thiết kế hệ thống AI thực tế.

---
