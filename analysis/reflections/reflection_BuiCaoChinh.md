# Báo cáo Phản hồi Cá nhân (Individual Reflection) - Lab Day 14

**Họ và tên:** Bùi Cao Chinh
**Mã HV:** 2A202600001
**Vai trò:** Data Engineer (Golden Dataset)
**Ngày:** 21/04/2026

---

## 1. Công Việc Thực Hiện

**Nhiệm vụ chính:**
- Thiết lập hạ tầng dữ liệu và quản lý dependencies (`requirements.txt`, `.env.example`).
- Phát triển và tối ưu module sinh dữ liệu tự động (SDG) trong `data/synthetic_gen.py`.
- Xây dựng bộ tài liệu nguồn (Source Documents) đa dạng về domain Y tế.
- Tạo lập Golden Dataset với quy mô lớn (144 test cases) có gán nhãn Ground Truth.

**Các tính năng đã triển khai:**
- Chunking logic (Recursive Splitting) với cơ chế overlap để bảo toàn ngữ cảnh.
- Hệ thống Async Batch Processing để tối ưu tốc độ gọi API OpenAI.
- Cơ chế Robust JSON Parsing xử lý tính bất định của LLM.
- Metadata tracking cho từng test case (Difficulty, Type, source_chunk_id).

---

## 2. Khó Khăn & Giải Pháp

**Vấn đề gặp phải:**
- **Tính bất định của LLM:** Khi tạo dữ liệu lớn (144 cases), LLM đôi khi trả về format JSON không ổn định hoặc sai key.
- **Giới hạn nội dung:** Tài liệu nguồn ban đầu quá mỏng, dẫn đến việc trùng lặp câu hỏi hoặc không đủ số lượng cases yêu cầu.
- **Chi phí & Hiệu năng:** Việc gọi API tuần tự cho hàng trăm cases tốn quá nhiều thời gian và chi phí.

**Giải pháp áp dụng:**
- **Flexible Key Mapping:** Viết code xử lý linh hoạt các biến thể của key (ví dụ: `answer` vs `expected_answer`).
- **Mở rộng tài liệu nguồn:** Biên soạn 30 chương nội dung Y tế chi tiết để tạo dư địa cho việc chunking và sinh câu hỏi đa dạng.
- **Tối ưu Prompt & Async:** Sử dụng `gpt-4o-mini` kết hợp với `asyncio.gather` để đạt tốc độ xử lý song song vượt mức mong đợi.

---

## 3. Điều Học Được

**Kỹ năng kỹ thuật:**
- Thành thạo lập trình hướng sự kiện/bất đồng bộ (`asyncio`) trong Python.
- Kỹ năng Prompt Engineering nâng cao để kiểm soát output JSON của LLM.
- Quản lý vòng đời dữ liệu trong hệ thống RAG (từ raw document đến gán nhãn).

**Kiến thức chuyên môn:**
- Hiểu sâu về các chỉ số đánh giá Retrieval như **Hit Rate** và **MRR (Mean Reciprocal Rank)**.
- Nắm vững các chiến lược Chunking (Fixed-size vs Semantic vs Recursive).
- Cơ chế hoạt động của Vector Store và tầm quan trọng của Golden Dataset trong chu kỳ CI/CD của AI Agent.

---

## 4. Đóng Góp (Chi tiết theo Rubric)

### Engineering Contribution
- **Tối ưu Async:** Triển khai batch processing giúp tạo 144 cases chỉ trong tích tắc, đáp ứng yêu cầu hiệu năng cực cao của lab.
- **Dataset Scale-up:** Vượt xa yêu cầu 50 cases của lab bằng cách tạo bộ dữ liệu 144 cases chất lượng cao, tạo điều kiện cho các đồng nghiệp benchmark hệ thống ở quy mô lớn hơn.
- **Infrastructure:** Cung cấp `.env.example` chuẩn giúp nhóm tránh rò rỉ API Key và thống nhất môi trường chạy.

### Technical Depth
- **Retrieval Quality:** Giải trình được tầm quan trọng của việc gán nhãn Ground Truth IDs để tính toán Hit Rate/MRR, nền tảng để đo lường chất lượng RAG.
- **Cost-Quality Trade-offs:** Chứng minh được việc sử dụng mô hình nhỏ (`gpt-4o-mini`) vẫn đạt hiệu quả cao nều biết cách tối ưu hóa Prompt và cấu trúc dữ liệu.
- **Semantic Integrity:** Áp dụng overlap trong chunking để giải quyết bài toán mất thông tin tại các điểm cắt đoạn văn bản.

### Problem Solving
- **JSON Robustness:** Giải quyết triệt để lỗi parse dữ liệu bằng logic filter và nhận diện key linh hoạt, giúp script chạy ổn định 100% trên tập dữ liệu lớn.
- **Domain Adaptation:** Chuyển đổi linh hoạt từ domain ban đầu sang domain Y tế phức tạp theo yêu cầu, chứng minh khả năng thích ứng của module SDG.

---

## 5. Lời Kết

Đảm nhiệm vai trò Data Engineer giúp tôi làm chủ được quy trình xây dựng Golden Dataset và tối ưu hiệu năng Async. Đây là nền tảng quan trọng giúp tôi phát triển các hệ thống RAG chuyên nghiệp và hiệu quả trong tương lai.
