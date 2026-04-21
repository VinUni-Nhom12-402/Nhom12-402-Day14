# Reflection - Duong Chi Thanh

## 1. Vai trò được phân công
Trong bài lab này, tôi đảm nhiệm vai trò 'LLM Judge devloper' trong nhóm AI/Backend.
Nhiệm vụ chính của tôi là hoàn thiện 'engine/llm_judge.py', xây dựng multi-judge consensus
engine, tính agreement_rate, xử lý xung đột điểm số giữa các judge model, và đảm bảo kết 
quả judge được nối vào luồng benchmark de sinh report đúng theo yêu cầu trong README.md.
## 2. Công việc đã thực hiện
Tôi đã triển khai lại engine/llm_judge.py từ một file mock thành một judge engine có cấu
trúc rõ ràng hơn. Engine này hỗ trợ 3 judge model cấu hình sẵn: `gpt-4o`, `claude-3-5-sonnet`,
va `gemini-1.5-pro`.

Những phần tôi đã hoàn thành gồm:
- Định nghĩa rubric chấm điểm theo 3 tiêu chí: accuracy, professionalism, safety.
- Xây dựng hàm chấm điểm cho từng judge model với output chuẩn hoá gồm score, rubric_scores, reasoning.
- Implement evaluate_multi_judge() bằng `asyncio.gather()` để có thể chấm song song.
- Tính `agreement_rate` dựa trên độ lệch điểm giữa các judge.
- Phát hiện conflict, gọi judge thứ 3 để tie-break và lấy `median` làm `final_score`.
- Trả về đầy đủ các trường hợp cần thiết cho benchmark như `final_score`, `agreement_rate`, `individual_scores`, `judge_details`, `resolution_strategy`.

## 3. Lý do cho các lựa chọn kỹ thuật
Tôi chọn hướng thiết kế theo từng lớp nâng dần:
- Judge 1 dùng để tạo khung rubric và định dạng output.
- Judge 2 giúp xây dựng consensus thay vì phụ thuộc vào một model duy nhất.
- Judge 3 được dùng làm tie-breaker khi hai judge đầu mâu thuẫn.
Toi su dung `median` khi co 3 judge thay vi average don thuan, 
- vi median on dinh hon khi co mot model cho diem lech manh. 
- Day la cach phu hop voi yeu cau "xu ly xung dot diem so tu dong" trong de bai.
Tôi sử dụng 'median' khi có 3 judge thay vì average đơn thuần, vì median ổn định hơn khi có một
điểm lệch mạnh. Đây là cách phù hợp với yêu cầu "xử lý xung đột điểm số tự động"
Tôi cũng giữ interface của `evaluate_multi_judge(question, answer, ground_truth)` tương thích với engine/runner.py  để tránh sửa quá nhiều file và giảm ngua cơ gây lỗi regression.

## 4. Khó khăn gặp phải.
Khó khăn lớn nhất không nằm ở việc viết logi judge, mà nằm ở việc repo hiện tại có nhiều
thành phần mock. Lúc ầu main.py không gọi engine/llm_judge.py, nên nếu không đọc kỹ benchmark thì
rất dễ sửa đúng file nhưng output vẫn sai về mặt hệ thống.
Một khó khăn khác là môi trường hiện tại không sử dụng API thật và network bị hạn chế.
Vì vậy, tôi phải thiết kế judge engine theo hướng deterministic/mockable, tức là có logic
consensus đầy đủ nhưng vẫn chạy được offline. Cách này giúp bài lab có thể sinh report, kiểm 
tra format, và chứng minh được cấu trúc của multi-judge engine.
Tôi cũng gặp một lỗi nhỏ khi chạy check_lab.py trên windows console do encoding unicode.
Vấn đề này không nằm ở dữ liệu report mà do console mặc định, và có thể xử lý bằng cách chạy
với `PYTHONIOENCODING=utf-8`.
## 5. Điều tôi học được
Qua bài này, tôi rút ra 3 bài học kỹ thuật quan trọng.
Thứ nhất, trong bài toàn evaluation, tin vào một judge duy nhất là thiếu tin cậy. Multi-judge không chỉ để "có thêm model", mà để giảm độ lệch chủ quan và tăng khả năng calibration.
Thứ hai, agreement rate là một chỉ số quan trọng, vì nó cho thấy mức độ ổn định của hệ thống đánh giá. Nếu final score cao nhưng agreement thấp, kết quả vẫn cần được xem xét thận trọng. 
Thứ ba, việc nội dung component và pipeline quan trọng không kém việc viết logic, Một module viết đúng nhưng không được gọi trong luồng chạy thật thì gần như không có giá trị khi benchmarrk.                                                                                   

## 6.  Nếu có thêm thời gian tôi sẽ cải thiện gì
Nếu có thêm thời gian, tôi muốn cải tiến judge engine theo các hướng sau:
- Thay heuristic offline bằng API call thật tới OpenAI/Anthropic/Gemini để lấy score và reasonin từ model judge that.
- Tính agreement rate theo nhiều thang đo hơn, ví dụ pairwise agreement hoặc weighted agreement.
- Bổ sung position bias check đầy đủ để kiểm tra judge có thiên vị thứ tự response hay không .
- Thêm cost tracking cho từng judge model để phục vụ mục tiêu tối ưu chi phí eval trong README.
- Ghi rõ hơn thông tin conflict vào benchmark_results.json để nhóm analysyst có thẻ phân tích sau benchmak.

## 7. Tự đánh giá đóng góp cá nhân
Tôi đánh giá phần đóng góp của mình tập trung vào tính dùng của hệ thống đánh giá hơn là chỉ bổ sung một file.
Phần việc của tôi giúp repo đáp ứng đúng hướng yêu cầu multi-judge reliability trong đề bài, đồng thời
đảm bảo report cuối cùng có agreement_rate và có thể được script check_lab.py xác nhận hợp lệ.
Tôi có thể giải chích rõ lý do tách 3 commit theo 3 mốc phát triển:
- Judge model đầu tiên chuẩn hoá rubric và scoring.
- judge model thứ hai để tạo consensus.
- Judge model thứ 3 để giải quyết cònilict và ổn định final score.

## 8. Kết luận
Phần việc LLM Judge giúp em hiểu rõ hơn rừng evaluation engine không chỉ là chấm điểm
kết quả, mà là xây dựng một cơ chế đánh giá có thể giải thích, có độ tin cậy, và có khả 
năng mở rộng. Đây là thành phần quan trọng nếu muốn đưa AI system vào quy trình phát triển
và kiểm thử nghiêm túc.
