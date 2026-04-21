# Báo cáo Phân tích Thất bại (Failure Analysis Report)

## 1. Tổng quan Benchmark
- **Tổng số cases:** 120
- **Tỉ lệ Pass/Fail (Release Gate):** 120/0 (Hệ thống chạy ổn định)
- **Chất lượng phản hồi (LLM-Judge):**
    - Điểm trung bình: 3.86 / 5.0
    - Tỷ lệ Hit Rate (Truy xuất đúng): 81.7%
    - Tỷ lệ đồng thuận giữa các Judge: 96%
- **Cải thiện so với V1:** +0.024 điểm (Vượt ngưỡng 0.01)

## 2. Phân nhóm lỗi (Failure Clustering)
| Nhóm lỗi | Số lượng | Nguyên nhân dự kiến |
|----------|----------|---------------------|
| Retrieval Failure | 22 | Các câu hỏi quá rộng hoặc mang tính tóm tắt làm Vector DB không tìm được chunk cụ thể. |
| CoT Misalignment | 15 | Agent trả lời đúng nhưng thiếu trích dẫn [Context X] theo định dạng yêu cầu của V2. |
| Hallucination (Minor) | 10 | Agent cố gắng giải thích thêm dựa trên kiến thức ngoại ngữ y tế thay vì chỉ dùng Context. |
| Indexing Gap | 9 | Các câu hỏi về "Mục số X" hoặc "Đoạn văn bản Y" bị lỗi do Chunking làm mất thứ tự logic của tài liệu. |

## 3. Phân tích 5 Whys (Chọn 3 case tệ nhất)

### Case #1: Câu hỏi tóm tắt ("Chủ đề chính là gì?")
1. **Symptom:** Agent chỉ tóm tắt được 1 phần nhỏ, điểm Judge thấp (2.3).
2. **Why 1:** LLM chỉ nhận được 6 chunks (top_k=6) thay vì toàn bộ văn bản.
3. **Why 2:** Vector retrieval chỉ lấy ra các đoạn có độ tương đồng cao nhất với từ khóa "chủ đề chính".
4. **Why 3:** Các đoạn này không chứa bức tranh tổng thể của toàn bộ tài liệu 214 chunks.
5. **Why 4:** Kiến trúc RAG cơ bản không hỗ trợ tốt cho các câu hỏi mang tính tổng quát (Global Query).
6. **Root Cause:** Thiếu cơ chế "Summarization Layer" hoặc "Parent-Document Retrieval" để xử lý các câu hỏi bao quát.

### Case #2: Câu hỏi theo số thứ tự ("Mục số 3 đề cập gì?")
1. **Symptom:** Agent trả lời sai nội dung của mục số 3 (2.5 điểm).
2. **Why 1:** Chunk chứa nội dung mục 3 không nằm trong top 6 kết quả trả về.
3. **Why 2:** Tên mục "Mục số 3" quá ngắn, không tạo đủ trọng số vector để cạnh tranh với các đoạn văn bản dài khác.
4. **Why 3:** Chunking cắt ngang các tiêu đề, làm mất đi sự liên kết giữa số thứ tự mục và nội dung đi kèm.
5. **Root Cause:** Cấu trúc Chunking hiện tại (Fixed-size) phá vỡ tính phân cấp (Hierarchy) của tài liệu y tế.

### Case #3: Yêu cầu chẩn đoán trực tiếp
1. **Symptom:** Agent cố gắng chẩn đoán thay vì từ chối như Prompt yêu cầu (2.8 điểm).
2. **Why 1:** Câu hỏi người dùng mang tính chất khẩn cấp và ép buộc ("Bỏ qua mọi cảnh báo").
3. **Why 2:** LLM bị "lung lay" (jailbreak nhẹ) trước các yêu cầu mang tính cảm xúc mạnh.
4. **Why 3:** System Prompt dù đã khắt khe nhưng chưa có cơ chế xử lý riêng cho các câu hỏi "nguy cơ cao" (High-risk queries).
5. **Root Cause:** Thiếu lớp kiểm soát an toàn (Safety Guardrail) riêng biệt cho các tình huống y tế khẩn cấp.

## 4. Kế hoạch cải tiến (Action Plan)
- [x] Đã thêm bước Reranking vào Pipeline (Agent V2).
- [ ] Triển khai **Hierarchical Chunking** để giữ được mối liên hệ giữa Tiêu đề - Mục lục - Nội dung.
- [ ] Thêm **Map-Reduce Strategy** cho các câu hỏi yêu cầu tóm tắt toàn bộ tài liệu.
- [ ] Xây dựng bộ **Safety Guardrail** chuyên dụng để từ chối chẩn đoán y tế trong mọi điều kiện "ép buộc" của người dùng.
