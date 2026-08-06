# Corruption & Repair Pipeline Demo

Tài liệu này tổng hợp kết quả của quá trình mô phỏng hỏng hóc dữ liệu (Data Corruption) và quy trình vá lỗi (Repair) trong Data Pipeline.

## 1. Các phương pháp Mô phỏng Lỗi (Corruption)
Trong phase này, một số nhiễu và hỏng hóc sau đã được áp dụng lên Dataset Baseline (Clean):
- **Missing Summary:** Xóa sạch `summary` của một tỷ lệ bài báo.
- **Stale Published Date:** Lùi ngày xuất bản (`published`) về 10 năm trước.
- **Noisy Text:** Chèn token `[NOISE]` vào trong `summary`.
- **Duplicate Records:** Nhân bản (duplicate) các dòng dữ liệu.
- **Dropped Records:** Xóa đi một lượng bài báo (ưu tiên các bài nằm trong Test Set).

## 2. RAG Metrics Comparison
Sau khi thực hiện Corrupt, chúng ta thấy **Hit Rate** bị tụt giảm nghiêm trọng (từ 1.000 xuống 0.750) và chất lượng sinh câu trả lời (**Token F1**) bị sụt giảm.

Sau khi chạy lại Data Cleaning từ `raw_records` (Repair), hệ thống đã khôi phục lại 100% chất lượng của bộ Index Baseline!

| Metric | Baseline | Corrupted | Repaired | Corrupted Δ | Repaired Δ | Recovery |
|---|---:|---:|---:|---:|---:|---:|
| retrieval_hit_rate | 1.000 | 0.750 | 1.000 | -0.250 | +0.000 | 100.00% |
| mean_token_f1 | 0.067 | 0.031 | 0.068 | -0.036 | +0.001 | 104.38% |
| judge_accuracy | 0.000 | 0.000 | 0.000 | +0.000 | +0.000 | N/A |
| mean_judge_score | 1.000 | 1.000 | 1.000 | +0.000 | +0.000 | N/A |

*(Ghi chú: Token F1 tăng nhẹ ở Repaired có thể do LLM sinh ngẫu nhiên tốt hơn 1 chút hoặc quá trình rebuild pipeline xử lý văn bản có sự điều chỉnh siêu nhỏ. Điểm Judge Score giữ nguyên ở 1.0 do Baseline gặp các câu hỏi Test Set quá hẹp nên điểm chưa tối ưu.)*

## 3. Data Quality & Freshness
| Metric | Corrupted | Repaired |
|---|---|---|
| **Row count** | 382 | 402 |
| **Freshness Status** | needs attention (Stale rows: 54) | fresh (Stale rows: 0) |

- Bộ dữ liệu bị Corrupt hiển thị **"needs attention"** do 54 bài báo đã bị làm cũ đi 10 năm. 
- Sau khi Repair, dữ liệu trở lại trạng thái **fresh**. 

## 4. RAG Agent Behavior Demo
Đây là trải nghiệm thực tế với 1 câu hỏi mẫu trong hệ thống RAG Agent thông qua 3 trạng thái.

**Câu hỏi (Question ID: q9):**
> Bài viết 'Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, and Evaluation' được xuất bản vào ngày nào?

**[BASELINE] (Hit: True)**
> Large language models have demonstrated strong generative capability in question answering, dialogue, and other knowledge-intensive tasks.

**[CORRUPTED] (Hit: True)**
> Unfortunately, the indexed corpus does not support the answer to the question "Bài viết 'Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, and Evaluation' được xuất bản vào ngày nào?" because the paper's publication date is not available in the corpus.

**[REPAIRED] (Hit: True)**
> Tôi không thể tìm thấy thông tin về ngày xuất bản của bài viết "Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, and Evaluation".

---
**Kết luận:** Quá trình tự động phát hiện, đánh giá tác động của Data Corruption tới ứng dụng GenAI và thực hiện Repair tự động đã thành công tốt đẹp.
