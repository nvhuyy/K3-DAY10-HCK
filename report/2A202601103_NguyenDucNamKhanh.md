# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Nguyễn Đức Nam Khánh |
| MSSV | 2A202601103 |
| Khóa/Lớp | K3 |
| Tên nhóm | HCK |
| Vai trò chính | Observability & reporting (quality, freshness, evidence, reports) |
| Repository | https://github.com/nvhuyy/K3-DAY10-HCK |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Check chất lượng dữ liệu | `src/observability/quality.py` | DataFrames (baseline, corrupted, repaired) | JSON reports (tính toàn vẹn, tính độc nhất) | Hoàn thành |
| Giám sát độ tươi (Freshness) | `src/observability/freshness.py` | Clean DataFrames, age_days | Freshness JSON logs | Hoàn thành |
| Tổng hợp Artifacts và Report | `src/observability/reporting.py` | Các JSON metrics từ Eval và Quality | Các file markdown report cuối cùng | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
|---|---|---|
| Phân tích impact metrics | Cường (Corruption/Repair) | Đồng bộ các metric giữa quality signals và RAG metrics để làm rõ quan hệ nhân quả trong báo cáo cuối. |
| Data contract validations | Huy (Cleaning) | Cung cấp chuẩn đầu ra mong muốn để script cleaning có thể đảm bảo pass 100% metrics ở baseline. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
|---|---|---|---|
| Kiểm tra chất lượng (Quality checks) | `data/quality/*_quality.json` | Cả 3 file baseline, corrupted, repaired quality json với các dimension completeness, uniqueness. | Đọc file corrupted_quality.json có `status: FAIL`. |
| Đo lường Freshness | `data/quality/*_freshness.json` | Ngưỡng 180 ngày; phát hiện ra lỗi freshness bị stale (9714 ngày) trong lần chạy corrupted. | Kiểm tra attribute `max_age_days`. |
| Sinh Markdown Report Tự động | `data/reports/corruption_report.md` | Báo cáo comparison 3 trạng thái có đủ chỉ số RAG (Hit rate, Token F1) và Observability. | Mở xem nội dung md để đối chiếu. |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Một data pipeline tốt không chỉ cần luồng code chạy thông suốt mà phải có hệ thống cảnh báo, giám sát xem dữ liệu ở các điểm chạm có bị lỗi, mất mát hoặc cũ kĩ (stale) hay không. Đặc biệt, ta cần chỉ ra cho các kỹ sư rằng, khi chất lượng dữ liệu suy giảm (Quality Fails), hiệu năng của GenAI (Agent Metrics) cũng giảm theo tương ứng.

### Cách triển khai

Module Observability được chạy độc lập 3 lần ứng với ba bộ dataset của ba pha: Baseline, Corrupted, và Repaired. 
- **Quality Module**: Sử dụng logic kiểm tra DataFrame: lấy lượng NULL chia tổng số records cho *completeness*; gom nhóm theo `paper_id` để tìm các documents bị duplicates cho *uniqueness*.
- **Freshness Module**: Đọc cột `age_days` (đã được tính toán lúc Cleaning) và đối chiếu với hằng số threshold `180` ngày. Nếu bất kỳ row nào vi phạm, trạng thái is_fresh của dataset thành `false`.
- **Reporting Module**: Là nơi tập hợp toàn bộ JSON từ hai pipeline song song là Evaluation (Hit rate, F1) và Observability, format thành Markdown tables, giúp dễ dàng tích hợp và đọc hiểu.

### Cách xác minh

```bash
uv run python script/run_corruption_flow.py
```
- **Kết quả mong đợi:** Xuất hiện các logs và artifacts chất lượng tại `data/quality/` tương ứng với mỗi pha. 
- **Kết quả thực tế:** Tại `baseline_quality.json`, `is_fresh = true`, `completeness = 1.0`. Nhưng qua file `corrupted_quality.json`, ta thấy rành rành 1 record trùng lặp và summary completeness bị giảm xuống 0.913.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Xây dựng hệ thống report markdown từ các file kết quả.
- **Phương án đã chọn:** Tách report generator ra thành một phase chạy riêng lẻ ở cuối đường ống. Tất cả đầu vào của report phải là các file JSON (không truyền bằng bộ nhớ).
- **Lý do:** Điều này cho phép ta debug từng phần nhỏ lẻ. Nếu chạy RAG evaluation bị văng ở phần gọi LLM chấm điểm (LLM as a Judge), ta vẫn còn log quality/freshness JSON an toàn ở trên ổ cứng và hoàn toàn có thể render ra report cục bộ.
- **Bằng chứng:** Hệ thống đã tự động xuất file `data/reports/corruption_report.md` thành công ngay cả khi `judge_accuracy` bằng 0.

## 6. Một lỗi/blocker đã xử lý

- **Triệu chứng:** Pipeline báo cáo freshness là FAIL ở baseline nhưng số liệu thực tế lại không có bài báo nào quá cũ.
- **Nguyên nhân gốc:** Logic tính ngưỡng bị sai, vô tình gán mốc quá khắt khe, hoặc format date ở ingestion truyền qua khiến `age_days` bị âm/sai.
- **Cách xử lý:** Thống nhất lại với người phụ trách Ingestion (Huy) về đơn vị của `age_days` là int. Chốt hard-code ngưỡng an toàn là 180 ngày và điều chỉnh thuật toán cho chuẩn xác.

## 7. Hiểu biết về luồng end-to-end

1. Huy tải dữ liệu (raw) và chuyển thành dữ liệu sạch (clean).
2. Cường dùng dữ liệu đó tính index nhúng và chạy pipeline Evaluation cho RAG để ra được hiệu năng Agent. Đồng thời tạo dữ liệu nhiễu (corrupted).
3. Song song quá trình trên, phần Observability của tôi liên tục quét qua dataset ở mỗi trạm. Nếu Huy sơ suất loại bỏ quá nhiều document, completeness báo lỗi. Nếu Cường tạo ra dữ liệu hỏng cũ rích, freshness báo cáo stale (lên đến 9714 ngày).
4. Khâu báo cáo tổng hợp cuối cùng gom cả kết quả đánh giá (hit rate) và kết quả chất lượng để làm nên báo cáo đối sánh so sánh sự thật (RAG cần chất lượng data).

## 8. Điều học được và hướng cải thiện

1. Quan hệ nhân quả giữa Data Quality và AI Performance là rất trực quan. Nếu pipeline không có Observable Metrics (Freshness/Completeness), ta không thể biết tại sao hôm nay Hit Rate của LLM Agent lại tụt xuống 50%.
2. Nếu có thời gian, tôi sẽ tích hợp thư viện `Great Expectations` (GX) đầy đủ hơn để có giao diện dashboard trực quan và viết các rule kiểm tra (expectation) linh động, thay vì tự code python thuần.

## 9. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.

**Họ và tên:** Nguyễn Đức Nam Khánh
**Ngày xác nhận:** 2026-08-06
