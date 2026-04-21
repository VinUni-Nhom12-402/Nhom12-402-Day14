# Báo cáo Phản hồi Cá nhân (Individual Reflection) - Lab Day 14

**Họ và tên:** Nguyễn Trọng Thien Khôi
**Vai trò:** Retrieval Specialist
**Ngày:** 21/04/2026

---

## 1. Công Việc Thực Hiện

**Nhiệm vụ chính:**
- Hoàn thiện module `engine/retrieval_eval.py` từ skeleton có sẵn thành hệ thống đánh giá Retrieval thực sự.
- Xây dựng `SimpleVectorStore` dựa trên TF-IDF + Cosine Similarity chạy hoàn toàn local, không phụ thuộc API bên ngoài.
- Tích hợp Retrieval Evaluator vào pipeline chính (`main.py`) và `agent/main_agent.py` để Hit Rate & MRR được tính theo từng case thực tế.

**Các tính năng đã triển khai:**
- **SimpleVectorStore:** Index TF-IDF cho toàn bộ corpus, tìm kiếm bằng Cosine Similarity — đảm bảo pipeline chạy được ngay cả khi không có API key.
- **Hit Rate Calculation:** Kiểm tra xem ít nhất 1 `expected_retrieval_id` có nằm trong top-K kết quả trả về hay không.
- **MRR Calculation:** Tính nghịch đảo thứ hạng đầu tiên tìm thấy đúng, phản ánh chính xác hơn chất lượng xếp hạng của Retriever.
- **evaluate_batch():** Thay thế giá trị hardcode (`avg_hit_rate: 0.85`) bằng vòng lặp tính toán thực trên từng case trong dataset.
- **Tích hợp vào ExpertEvaluator:** `main.py` build một `RetrievalEvaluator` dùng chung cho cả Agent lẫn Evaluator, đảm bảo consistency.

---

## 2. Khó Khăn & Giải Pháp

**Vấn đề gặp phải:**
- **Không có API key thật:** Môi trường lab không thể gọi embedding model thực (OpenAI, Cohere...) để tính vector similarity.
- **Chunk ID không khớp:** Agent ban đầu trả về `sources` là tên file, không phải `chunk_id` — khiến Hit Rate không tính được.
- **Lỗi encoding trên Windows:** Terminal Git Bash mặc định dùng CP1252, gây `UnicodeEncodeError` khi in tiếng Việt và emoji.
- **Import conflict trong main.py:** File dùng `MultiModelJudge` nhưng class thực tế tên là `LLMJudge` trong `llm_judge.py`, gây `NameError` khi chạy.

**Giải pháp áp dụng:**
- **TF-IDF local:** Tự implement thuật toán TF-IDF + Cosine Similarity bằng thư viện chuẩn Python (`math`, `re`, `collections`) — không cần bất kỳ dependency nào thêm.
- **Chuẩn hoá trường `retrieved_ids`:** Cập nhật `MainAgent.query()` để trả về `retrieved_ids` là danh sách `chunk_id` thực từ vector store, thay vì tên file.
- **Fix encoding:** Thêm hướng dẫn chạy với `PYTHONIOENCODING=utf-8` và bỏ emoji trong print statement của module.
- **Fix import conflict:** Thêm dòng alias `MultiModelJudge = LLMJudge` trong `main.py` để giữ tên nhất quán mà không phải sửa phần còn lại của file.

---

## 3. Điều Học Được

**Kỹ năng kỹ thuật:**
- Hiểu sâu về cơ chế hoạt động của TF-IDF và Cosine Similarity — nền tảng của mọi hệ thống tìm kiếm văn bản.
- Kỹ năng tích hợp module vào pipeline async phức tạp: truyền shared state (vector store) giữa các component mà không gây race condition.
- Debug lỗi hệ thống đa module: phân biệt được lỗi logic, lỗi import, và lỗi encoding là ba loại hoàn toàn khác nhau.

**Kiến thức chuyên môn:**
- **Hit Rate vs MRR:** Hit Rate chỉ trả lời "có tìm thấy không", còn MRR trả lời "tìm thấy ở thứ hạng bao nhiêu" — cả hai đều cần thiết để đánh giá đầy đủ chất lượng Retriever.
- **Retrieval là giới hạn trên của Answer Quality:** Dù LLM có mạnh đến đâu, nếu Retriever đưa sai context thì câu trả lời chắc chắn sai hoặc hallucinate. Kết quả thực nghiệm trên 144 cases xác nhận: Hit Rate ~1.0, MRR ~0.90 → LLM Judge cho điểm cao (~4.5/5).
- **Position Bias trong Retrieval:** Chunk đúng xếp hạng 1 so với hạng 2 có thể tạo ra sự khác biệt lớn trong câu trả lời, vì LLM đọc context theo thứ tự.

---

## 4. Đóng Góp (Chi tiết theo Rubric)

### Engineering Contribution
- **Metrics Module:** Trực tiếp xây dựng và kiểm thử `calculate_hit_rate()` và `calculate_mrr()` trên 144 test cases thực. Đây là phần tạo ra các chỉ số quan trọng nhất trong `summary.json`.
- **SimpleVectorStore:** Thiết kế lớp vector store hoàn toàn độc lập, có thể tái sử dụng bởi bất kỳ component nào trong hệ thống — Agent, Evaluator, hoặc module ngoài.
- **Pipeline Integration:** Đảm bảo vector store được khởi tạo đúng một lần và dùng chung, tránh việc index lại nhiều lần gây tốn thời gian.

### Technical Depth
- **MRR (Mean Reciprocal Rank):** MRR = trung bình của `1 / rank` — trong đó rank là vị trí đầu tiên tìm thấy chunk đúng. MRR phản ánh chất lượng xếp hạng tốt hơn Hit Rate: hai hệ thống có cùng Hit Rate nhưng MRR khác nhau thì hệ thống có MRR cao hơn sẽ cho câu trả lời tốt hơn.
- **Cohen's Kappa:** Chỉ số đo độ đồng thuận giữa các Judge sau khi trừ đi xác suất đồng thuận ngẫu nhiên. Kappa = (P_observed - P_expected) / (1 - P_expected). Kappa > 0.6 được coi là đáng tin cậy.
- **Trade-off Chi phí và Chất lượng:** TF-IDF local không tốt bằng embedding model thật (bỏ sót ngữ nghĩa), nhưng tiết kiệm 100% chi phí API cho bước Retrieval Evaluation. Với dataset y tế có từ khoá chuyên ngành rõ ràng, TF-IDF đạt Hit Rate ~1.0 — chứng minh không phải lúc nào cũng cần giải pháp đắt tiền.

### Problem Solving
- **Debug end-to-end:** Phát hiện và sửa chuỗi lỗi liên hoàn: `NameError (MultiModelJudge)` → `retrieved_ids rỗng` → `Hit Rate = 0 hardcode` → kết quả báo cáo sai hoàn toàn.
- **Thiết kế backward-compatible:** Mọi thay đổi trong `retrieval_eval.py` và `main_agent.py` giữ nguyên interface cũ, không làm hỏng code của các thành viên khác trong nhóm.

---

## 5. Lời Kết

Đảm nhiệm vai trò Retrieval Specialist giúp tôi hiểu rõ tại sao Retrieval là thành phần quan trọng nhất trong hệ thống RAG — nó là nền tảng mà mọi chất lượng phía sau đều phụ thuộc vào. Việc xây dựng được một hệ thống đo lường Retrieval thực sự (thay vì hardcode) là điều kiện tiên quyết để nhóm có thể tin tưởng vào các con số trong báo cáo cuối cùng.
