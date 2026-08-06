# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Nguyễn Mạnh Cường |
| MSSV | 2A202601361 |
| Khóa/Lớp | K3 |
| Tên nhóm | HCK |
| Vai trò chính | Corruption, repair & pipeline integration owner |
| Repository | https://github.com/nvhuyy/K3-DAY10-HCK |
| Ngày hoàn thành | 2026-08-06 |


## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Baseline orchestration | `src/pipelines/phase1.py`, `script/run_phase1.py` | Cấu hình, raw Crossref records | Clean data, index, test set, baseline metrics và report | Hoàn thành |
| Controlled corruption | `src/ingestion/corruption.py::corrupt_clean_dataframe` | Clean baseline và document IDs của frozen test set | Corrupted dataset và `corruption_log.json` | Hoàn thành |
| Repair và so sánh ba trạng thái | `src/pipelines/corruption_flow.py`, `script/run_corruption_flow.py` | Baseline artifacts, raw snapshot và cùng test set | Corrupted/repaired metrics, quality/freshness và comparison report | Hoàn thành |
| Báo cáo observability | `src/observability/quality.py`, `src/observability/reporting.py` | DataFrame và metrics của ba trạng thái | Quality/freshness JSON và báo cáo Markdown | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
|---|---|---|
| Tích hợp data contract | Cleaning, evaluation và retrieval | Giữ ổn định `paper_id`, schema clean, artifact paths và frozen test set xuyên suốt ba trạng thái |
| Kiểm tra cấu hình LLM | `src/core/config.py`, `src/retrieval/llm.py` | Chuẩn hóa provider/model và giới hạn output token; không đưa secret vào report |
| Tái hiện kết quả | Toàn bộ pipeline | Sinh đủ baseline, corrupted, repaired artifacts và bảng so sánh cuối |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
|---|---|---|---|
| Xây corruption có kiểm soát | `src/ingestion/corruption.py`; `data/results/corruption_log.json` | Tác động đúng 4 document IDs trong frozen test set; drop 2 record, blank 1 summary, stale 1 ngày, thêm noise và 1 duplicate | Đọc `corruption_log.json`, kiểm tra `overlaps_frozen_test_set: true` |
| Đánh giá trạng thái corrupted | `data/results/corrupted_metrics.json`; `data/quality/corrupted_quality.json` | Hit rate giảm từ 1.0 xuống 0.5; token F1 giảm từ 0.0668 xuống 0.0460; quality và freshness FAIL | Đối chiếu JSON metrics/quality/freshness |
| Repair từ nguồn ổn định | `src/pipelines/corruption_flow.py`; `data/clean/papers_clean_repaired.json` | Rebuild từ raw snapshot, không sửa trực tiếp corrupted data và không fetch API mới | Đối chiếu code và repaired artifacts |
| Xác minh phục hồi | `data/results/repaired_metrics.json`; `data/quality/repaired_quality.json` | Hit rate phục hồi 1.0, token F1 0.0668, quality/freshness PASS | Đọc `data/reports/corruption_report.md` |

Output tiêu biểu là `data/reports/corruption_report.md`, tổng hợp cùng một bảng các metric retrieval, answer quality, duplicate, stale rows và freshness cho baseline–corrupted–repaired.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần chứng minh bằng số liệu rằng lỗi dữ liệu ảnh hưởng đến RAG agent và một quy trình repair đúng có thể khôi phục chất lượng. Nếu corruption chọn ngẫu nhiên record không thuộc evaluation set, metric có thể không đổi và thí nghiệm không chứng minh được quan hệ nhân quả.

### Cách triển khai

Flow đọc `ground_truth_doc_ids` từ test set đã đóng băng rồi truyền chúng vào hàm corruption. Corruption mang tính xác định: loại một nửa target, làm rỗng summary, đổi ngày thành `2000-01-01`, thêm noise vào `text_for_embedding` và tạo duplicate. Sau đó pipeline rebuild Chroma index riêng, chạy lại evaluation và observability.

Repair không dùng corrupted DataFrame. Pipeline đọc lại `data/raw/crossref_records.json`, chạy lại cleaning, build một index riêng và đánh giá bằng chính test set cũ. Cách này tránh giữ lại lỗi và tránh dataset drift do gọi Crossref lần nữa.

### Input, output và contract

| Thành phần | Mô tả |
|---|---|
| Input | Clean DataFrame có `paper_id`, `title`, `summary`, `published`, `age_days`, `text_for_embedding`; frozen test set có `ground_truth_doc_ids` |
| Output | Corrupted/repaired CSV và JSON, embedding manifests, Chroma collections, answers, metrics, quality/freshness reports và comparison Markdown |
| Module phụ thuộc | `ingestion.cleaning`, `evaluation.metrics`, `retrieval.index`, `observability.quality` |
| Module sử dụng output | `observability.reporting` và báo cáo nộp bài |
| Điều kiện lỗi cần xử lý | Thiếu baseline artifact, DataFrame rỗng, thiếu cột bắt buộc, raw snapshot rỗng hoặc cleaning repair trả về rỗng |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** hai lệnh sinh đủ artifact; corrupted suy giảm và repair phục hồi theo cùng test set.
- **Kết quả thực tế:** 24 baseline rows, 23 corrupted rows, 24 repaired rows; hit rate `1.0 → 0.5 → 1.0`; quality/freshness `PASS → FAIL → PASS`.
- **Artifact/log:** `data/results/*.json`, `data/quality/*.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** cần repair dữ liệu sau corruption nhưng vẫn bảo đảm so sánh công bằng và tái lập.
- **Các phương án đã cân nhắc:** (1) sửa trực tiếp các dòng corrupted; (2) fetch lại Crossref; (3) rebuild từ raw snapshot đã lưu ở baseline.
- **Phương án đã chọn:** rebuild từ raw snapshot `data/raw/crossref_records.json`.
- **Lý do:** sửa tại chỗ dễ bỏ sót lỗi; fetch mới có thể trả về tập record khác vì Crossref là nguồn sống. Raw snapshot giữ nguyên source population và cho phép tái tạo lại clean data bằng contract ban đầu.
- **Bằng chứng:** repaired có 24 rows, completeness 1.0, không duplicate, không stale; retrieval và token F1 trở về đúng mức baseline.

## 6. Một lỗi/blocker đã xử lý

- **Triệu chứng:** corruption ban đầu có thể tác động vào record không nằm trong test set nên evaluation metric hầu như không thay đổi, dù quality report phát hiện lỗi.
- **Bước tái hiện:** chạy corruption với cách chọn record độc lập với `ground_truth_doc_ids`, rồi so sánh retrieval hit rate.
- **Nguyên nhân gốc:** population bị corrupt và population được evaluation quan sát không giao nhau chắc chắn.
- **Cách xử lý:** lấy frozen IDs từ `data/eval/test_set.json`, truyền vào `corrupt_clean_dataframe`, ghi cả requested/affected IDs và cờ overlap vào corruption log.
- **Cách xác minh sau khi sửa:** `overlaps_frozen_test_set` bằng `true`; cả 4 target IDs bị tác động; hit rate giảm `1.0 → 0.5`.
- **Điều học được:** corruption test phải có phạm vi xác định và liên kết trực tiếp với evaluation contract; nếu không, “metric không đổi” chưa đủ để kết luận dữ liệu lỗi không ảnh hưởng agent.

## 7. Hiểu biết về luồng end-to-end

1. Crossref API trả metadata paper; response và parsed records được lưu ở `data/raw`. Cleaning chuẩn hóa schema, loại record không hợp lệ, tạo `text_for_embedding` và `age_days`. MiniLM mã hóa văn bản, còn ChromaDB lưu vector cùng metadata để agent semantic search và lookup.
2. Test set chứa câu hỏi, ground truth và `ground_truth_doc_ids`. Retrieval hit khi top-k chứa ID đúng; câu trả lời được so với ground truth bằng token F1 và LLM judge.
3. Quality checks đo completeness, uniqueness và tính hợp lệ trên dataset. Freshness monitoring tập trung vào phân bố ngày xuất bản, số stale rows và ngưỡng 180 ngày; freshness là một signal trong observability nhưng không thay thế các dimension khác.
4. Cùng test set giúp biến độc lập duy nhất là trạng thái dữ liệu/index. Đổi câu hỏi hoặc ground truth giữa ba lần chạy sẽ gây confounding và không thể quy chênh lệch metric cho corruption/repair.
5. Repair thành công khi repaired clean/index được tạo từ raw snapshot, quality và freshness trở lại PASS, đồng thời retrieval/answer metrics phục hồi về baseline. Trong lần chạy này, hit rate và token F1 phục hồi hoàn toàn; judge metrics không đổi và vì vậy không cung cấp thêm bằng chứng phân biệt.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | 1.000 | 0.500 | 1.000 | Nhạy rõ với việc loại target document và phục hồi hoàn toàn |
| `mean_token_f1` | 0.0668 | 0.0460 | 0.0668 | Giảm khoảng 31.2% tương đối rồi trở lại baseline |
| `judge_accuracy` | 0.000 | 0.000 | 0.000 | Không phân biệt được ba trạng thái trong lần chạy này |
| `mean_judge_score` | 1.000 | 1.000 | 1.000 | Không đổi; cần cải thiện judge/prompt trước khi dùng làm signal chính |
| Quality checks | PASS | FAIL | PASS | Corrupted có summary completeness 0.913, 1 duplicate và 1 stale row |
| Freshness status | PASS | FAIL | PASS | Stale rows `0 → 1 → 0`; max age corrupted là 9714 ngày |

### Kết luận từ số liệu

1. Drop 2 frozen-target records, blank/noise và stale/duplicate → completeness giảm, uniqueness và freshness thất bại → retrieval hit rate giảm 50%, token F1 giảm từ 0.0668 còn 0.0460.
2. Rebuild từ raw baseline snapshot → 24 rows, completeness 1.0, duplicate và stale rows về 0 → hit rate và token F1 phục hồi đúng baseline.

Corruption ảnh hưởng rõ nhất là `drop_records`, vì hai ground-truth documents biến mất hoàn toàn khỏi index; retrieval không thể trả về bằng chứng không còn tồn tại. Blank summary và noise làm embedding/answer yếu hơn, còn duplicate và stale date thể hiện rõ nhất ở observability.

Kết quả khác kỳ vọng là LLM judge không thay đổi: accuracy luôn 0 và mean score luôn 1. Điều này cho thấy judge hiện tại có thể quá nghiêm, prompt/output parser chưa phù hợp, hoặc câu trả lời extractive chưa khớp tiêu chí. Vì vậy kết luận chính dựa trên retrieval hit rate, token F1 và quality/freshness artifacts thay vì diễn giải quá mức judge metrics.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Pipeline tái lập cần lưu raw snapshot, cố định test set và tách artifact theo từng trạng thái.
2. Data quality phải đo nhiều dimension: completeness, uniqueness và freshness có thể phản ứng với các corruption khác nhau.
3. RAG phụ thuộc trực tiếp vào độ phủ của index; mất ground-truth document gây tác động lớn hơn việc chỉ làm xấu metadata không tham gia retrieval.

### Nếu có thêm thời gian

Tôi sẽ bổ sung test tự động cho corruption invariants và evaluation invariants: input không bị mutate, target overlap luôn đúng, raw snapshot hash không đổi, cùng test-set hash được dùng ở cả ba trạng thái và repaired metrics không thấp hơn baseline ngoài một tolerance định trước. Đồng thời tôi sẽ hiệu chỉnh LLM judge trên một tập câu trả lời gán nhãn nhỏ; tiêu chí thành công là judge có phân bố điểm hữu ích và tương quan cùng chiều với token F1/retrieval hit rate.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Mạnh Cường
**Ngày xác nhận:** 2026-08-06
