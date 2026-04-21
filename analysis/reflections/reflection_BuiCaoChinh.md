# Báo cáo Phản hồi Cá nhân (Individual Reflection) - Lab Day 14

**Họ và tên:** Bùi Cao Chinh
**Mã HV:** 2A202600001
**Vai trò:** Data Engineer (Golden Dataset)
**Ngày:** 21/04/2026

---

## 1. Công Việc Thực Hiện

**Nhiệm vụ chính:**
- Thiết lập hạ tầng dữ liệu và quản lý dependencies (`requirements.txt`, `.env.example`).
- Nâng cấp module sinh dữ liệu tự động (SDG) hỗ trợ xử lý đa tệp nguồn (Multi-source).
- Triển khai logic tạo **Hard Cases** chuyên sâu bám sát `HARD_CASES_GUIDE.md`.
- Xây dựng bộ Golden Dataset cân bằng giữa độ phủ kiến thức và hiệu năng thực thi.

**Các tính năng đã triển khai:**
- **Multi-source Ingestion:** Tự động quét và xử lý toàn bộ 11 file văn bản y tế trong thư mục `data/`.
- **Hard Case Algorithm:** Chế độ tạo câu hỏi hóc búa (Adversarial, Goal Hijacking, Conflicting Info...).
- **Metadata Source Tracking:** Gán nhãn file nguồn (`source_file`) cho từng case để phục vụ truy vết.
- **Dataset Optimization:** Điều chỉnh quy mô bộ dữ liệu xuống **111 cases** để tối ưu hóa thời gian benchmark.

---

## 2. Khó Khăn & Giải Pháp

**Vấn đề gặp phải:**
- **Độ phức tạp của dữ liệu:** Khi kết hợp 11 file nguồn khác nhau, việc duy trì tính nhất quán của metadata và gán nhãn Ground Truth trở nên phức tạp hơn.
- **Thử thách từ Hard Cases:** Các câu hỏi mập mờ hoặc hướng mục tiêu sai khiến Agent dễ bị lạc hướng và làm giảm các chỉ số truyền thống như Hit Rate.
- **Thời gian Benchmark:** Bộ dữ liệu quá lớn (250+ cases) làm chậm quá trình CI/CD và tốn kém chi phí API.

**Giải pháp áp dụng:**
- **Flexible Key Mapping:** Thuật toán parse JSON linh hoạt giúp xử lý triệt để sự bất định của LLM khi tạo hàng trăm cases từ nhiều nguồn.
- **Cân bằng Hybrid Dataset:** Quyết định chọn lọc **111 cases** (60 Standard + 51 Hard), giúp giảm 50% thời gian chạy (từ 85s xuống 44s) mà vẫn đảm bảo độ phủ 100% các kịch bản khó.
- **Hit Rate Analysis:** Chấp nhận sự sụt giảm Hit Rate như một dấu hiệu tích cực của việc tăng độ khó và độ nhiễu thực tế trong bộ test.

---

## 3. Điều Học Được

**Kỹ năng kỹ thuật:**
- Thành thạo xử lý dữ liệu quy mô lớn với `asyncio` và Batch Processing.
- Kỹ năng thiết kế Test Cases nâng cao: Tấn công prompt, tạo điều kiện biên và mâu thuẫn dữ liệu.
- Quản lý vòng đời dữ liệu đa nguồn trong hệ thống RAG thực tế.

**Kiến thức chuyên môn:**
- Hiểu sâu về sự khác biệt giữa **Standard RAG Evaluation** và **Adversarial Evaluation**.
- Nắm vững bài toán đánh đổi (trade-off) giữa độ phủ của bộ test và tốc độ phản hồi của hệ thống CI/CD.
- Cách sử dụng Golden Dataset để "stress test" Agent trước khi release.

---

## 4. Đóng Góp (Chi tiết theo Rubric)

### Engineering Contribution
- **Multi-Source Support:** Phát triển mã nguồn xử lý 11 file y tế chuyên sâu, vượt xa quy mô ban đầu của dự án.
- **Hard Case Engine:** Triển khai module tạo 51 hard cases theo chuẩn quốc tế (Adversarial, Multi-turn simulation), nâng cao đáng kể độ tin cậy của benchmark.
- **System Performance:** Tối ưu hóa chu kỳ benchmark xuống còn 44 giây, giúp quy trình phát triển linh hoạt hơn.

### Technical Depth
- **Adversarial Testing Mastery:** Chứng minh khả năng thiết kế các kịch bản Prompt Injection và Goal Hijacking để kiểm thử tính an toàn của mô hình.
- **Metrics Contextualization:** Giải trình được vì sao Hit Rate giảm khi thêm Hard Cases là một phần của quy trình kiểm soát chất lượng nghiêm ngặt.
- **Data Integrity:** Đảm bảo 100% cases có Ground Truth IDs chuẩn xác kể cả khi dữ liệu đến từ nhiều tệp nguồn khác nhau.

### Problem Solving
- **Resource Management:** Giải quyết bài toán chi phí và thời gian bằng cách cấu hình batch size và target count tối ưu.
- **Model Adaptability:** Chuyển đổi thành công hệ thống SDG từ các chủ đề tổng quát sang domain y tế lâm sàng theo yêu cầu thực tế.

---

## 5. Lời Kết

Đảm nhiệm vai trò Data Engineer giúp tôi làm chủ được quy trình xây dựng Golden Dataset đa nguồn và thực hiện stress-test hệ thống bằng Hard Cases. Đây là nền tảng quan trọng giúp tôi phát triển và đánh giá các hệ thống AI chuyên nghiệp, an toàn trong thực tế.
