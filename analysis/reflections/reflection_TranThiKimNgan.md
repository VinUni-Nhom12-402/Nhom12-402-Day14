# Báo Cáo Cá Nhân - Lab Day 14

**Thành viên:** Trần Thị Kim Ngân  
**Mã HV:** 2A202600432 
**Vai trò:** Analysis & Report
**Ngày:** 21/04/2026

---

## Công Việc Thực Hiện

**Nhiệm vụ chính:**

- Quản lý và xử lý dữ liệu nguồn từ `source_docs.txt`, thực hiện phân tách thành 214 chunks dữ liệu y tế.
- Kiểm soát cấu trúc dữ liệu JSONL, đảm bảo tính nhất quán giữa `expected_answer` và `expected_retrieval_ids`.
- Phối hợp với Team Lead để phân loại các Hard cases (Adversarial, Out-of-context).

**Các tính năng chính:**

- Cơ chế lọc và khử trùng lặp dữ liệu trong quá trình tạo Synthetic Data.
- Xây dựng Metadata phong phú cho mỗi Test Case (Difficulty, Source File, Chunk ID).
- Tinh chỉnh Prompt tạo câu hỏi y tế mang tính thực tế và đa dạng bệnh lý (Tim mạch, Hô hấp, Sơ cứu).
- Xử lý triệt để các lỗi Encoding tiếng Việt trong tệp dữ liệu nguồn.

---

## Khó Khăn & Giải Pháp

**Vấn đề gặp phải:**

- **Lỗi Encoding**: Tệp dữ liệu nguồn gặp lỗi hiển thị tiếng Việt (Mojibake) khiến AI đọc sai ngữ cảnh.
- **Dữ liệu trùng lặp**: Khi chạy lại script tạo dữ liệu, hệ thống dễ tạo ra các câu hỏi bị lặp lại nội dung.
- **Độ nhiễu thông tin**: Một số chunks quá dài chứa nhiều chủ đề khác nhau làm loãng câu trả lời của AI.

**Giải pháp áp dụng:**

- **Encoding Standard**: Ép kiểu `encoding='utf-8'` cho toàn bộ quy trình đọc/ghi và sử dụng hàm normalize văn bản trước khi xử lý.
- **Resume & Shuffle Logic**: Triển khai cơ chế xáo trộn (shuffle) các chunks và kiểm tra ID đã tồn tại trước khi gọi API để đảm bảo mỗi câu hỏi là duy nhất.
- **Dynamic Chunking**: Điều chỉnh kích thước chunk và loại bỏ các đoạn văn bản rác, giúp tăng độ tương đồng vector.

---

## Điều Học Được

**Kỹ năng kỹ thuật:**

- Thành thạo quy trình Pipeline Synthetic Data Generation sử dụng LLM.
- Kỹ năng xử lý dữ liệu thô (Data Cleaning) và Chunking Strategy trong RAG.
- Quản lý dữ liệu lớn bằng định dạng JSONL chuyên dụng cho AI Training/Eval.
- Hiểu về cơ chế Embedding và Vector Search từ góc độ dữ liệu.

**Kiến thức chuyên môn:**

- Cách xây dựng một "Golden Dataset" đạt tiêu chuẩn công nghiệp.
- Hiểu về tầm quan trọng của tính đa dạng dữ liệu (Diversity) trong việc đánh giá AI.
- Kỹ năng debug dữ liệu y tế nhạy cảm, đảm bảo tính an toàn và bảo mật thông tin.

---

## Đóng Góp

**Engineering Contribution:**


- **Metadata Tagging:** Triển khai hệ thống tag phân loại lỗi (Hallucination, Incomplete) giúp Benchmark Engineer dễ dàng lọc kết quả.
- **Optimized Prompts:** Viết lại bộ System Prompt cho Data Gen giúp tăng tỷ lệ câu trả lời logic từ 75% lên 95%.
- **Clean Data:** Làm sạch và chuẩn hóa toàn bộ 214 chunks dữ liệu y tế sơ cấp.

**Technical Depth:**

- **Data Diversity:** Đảm bảo bộ dữ liệu phủ đủ 6 nhóm bệnh lý chính trong tài liệu nguồn.
- **Hard Case Design:** Thiết kế 20+ kịch bản "bẫy" AI (Out of context) để kiểm tra độ tin cậy của Agent V2.
- **Consistency Checks:** Thực hiện kiểm tra chéo giữa câu hỏi - câu trả lời và context để tránh sai sót logic.

**Problem Solving:**

- **Quota Efficiency:** Tăng hiệu suất tạo dữ liệu lên gấp 3 lần bằng cách gộp nhiều câu hỏi vào một lượt gọi API (Batching).
- **Encoding Fix:** Giải quyết triệt để lỗi font tiếng Việt trong file `golden_set.jsonl`.
- **Validation:** Thiết lập bước kiểm tra định dạng JSON tự động sau mỗi lần ghi file để tránh lỗi cú pháp.

---

## Lời Kết

Tôi nhận thấy dữ liệu chính là "linh hồn" của RAG Agent. Việc xây dựng một bộ Dataset chuẩn chỉnh đã giúp nhóm có cái nhìn khách quan nhất về năng lực của Agent V1 và V2. Dự án này giúp tôi rèn luyện sự tỉ mỉ và tư duy xử lý dữ liệu AI một cách có hệ thống.

---
