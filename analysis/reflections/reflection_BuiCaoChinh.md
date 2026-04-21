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
- **Tối ưu Async & Performance:** Phát triển module xử lý song song cho SDG, giúp xử lý 11 file y tế chuyên sâu với tốc độ cực nhanh, đáp ứng tiêu chuẩn hiệu năng của Lab.
- **Metrics Module Integration:** Trực tiếp đóng góp vào việc thiết lập Ground Truth cho các chỉ số **Hit Rate** và **MRR**, đảm bảo tính chính xác của hệ thống đánh giá Retrieval.
- **System Infrastructure:** Xây dựng tệp `.env.example` và quản lý dependencies, tạo nền tảng ổn định cho việc tích hợp các module Multi-Judge và Regression Testing của nhóm.

### Technical Depth
- **Giải thích các chỉ số Evaluation:**
    - **MRR (Mean Reciprocal Rank):** Đo lường vị trí trung bình của tài liệu đúng đầu tiên trong danh sách kết quả. Điểm số này giúp đánh giá không chỉ hệ thống có tìm thấy tài liệu hay không (Hit Rate) mà còn tài liệu đó có nằm ở vị trí cao nhất hay không.
    - **Cohen's Kappa:** Chỉ số đo lường độ đồng thuận (Agreement Rate) giữa các Judge trong hệ thống Multi-Judge, giúp loại bỏ yếu tố "đồng thuận ngẫu nhiên". Tôi đã áp dụng khái niệm này để xác định khi nào cần cơ chế xử lý xung đột.
    - **Position Bias:** Hiểu rõ hiện tượng mô hình LLM Judge có xu hướng ưu tiên các câu trả lời ở vị trí đầu hoặc cuối. Tôi đã đề xuất xáo trộn thứ tự các câu trả lời khi đưa vào Judge để giảm thiểu sai số này.
- **Trade-off giữa Chi phí và Chất lượng:** Chứng minh được việc sử dụng mô hình nhỏ (`gpt-4o-mini`) kết hợp với Prompt Engineering chặt chẽ và chọn lọc số lượng test case (111 cases) vẫn đạt độ tin cậy cao nều tối ưu được cấu trúc dữ liệu.

### Problem Solving
- **Resource Management:** Giải quyết bài toán chi phí và thời gian bằng cách cấu hình batch size và target count tối ưu.
- **Model Adaptability:** Chuyển đổi thành công hệ thống SDG từ các chủ đề tổng quát sang domain y tế lâm sàng theo yêu cầu thực tế.

---

## 5. Lời Kết

Đảm nhiệm vai trò Data Engineer giúp tôi làm chủ được quy trình xây dựng Golden Dataset đa nguồn và thực hiện stress-test hệ thống bằng Hard Cases. Đây là nền tảng quan trọng giúp tôi phát triển và đánh giá các hệ thống AI chuyên nghiệp, an toàn trong thực tế.
