# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Nguyễn Văn Huy |
| MSSV | 2A202601635 |
| Khóa/Lớp | K3 |
| Tên nhóm | HCK |
| Vai trò chính | Data foundation & pipeline (ingestion, cleaning, repair, orchestration) |
| Repository | https://github.com/nvhuyy/K3-DAY10-HCK |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Ingestion & Snapshot | `src/ingestion/crossref.py` | API endpoints, config params | Raw payload, raw records dataset (`data/raw/`) | Hoàn thành |
| Data Cleaning & Normalization | `src/ingestion/cleaning.py` | Raw dataset | Cleaned dataset (`data/clean/`) | Hoàn thành |
| Integration & Repair orchestration | `src/pipelines/phase1.py` (hỗ trợ) | Raw snapshot, clean schema | Cấu trúc baseline cho phần index và evaluation | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
|---|---|---|
| Chốt data contract | Team (RAG & Evaluation) | Định nghĩa rõ ràng ID (paper_id) làm anchor point để dedupe, build embeddings và ground-truth. |
| Cơ chế snapshot dữ liệu | Corruption & Repair (Cường) | Đảm bảo source data (raw snapshot) không bao giờ bị ghi đè, làm nền tảng vững chắc cho luồng repair có thể truy xuất. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
|---|---|---|---|
| Tích hợp Ingestion | `data/raw/crossref_records.json` | 24 raw records được lấy thành công từ API, lưu snapshot an toàn trước khi chuyển qua bước kế tiếp. | Kiểm tra metadata API trong dữ liệu thô. |
| Chuẩn hóa (Cleaning) | `data/clean/papers_clean_baseline.json` | 24 records sạch, đã tạo `age_days` (max = 161) và `text_for_embedding` (đã loại bỏ null summary). | Check completeness = 1.0 tại JSON output. |
| Tạo pipeline khôi phục dữ liệu | `src/ingestion/cleaning.py::process_raw_to_clean` | Dữ liệu sau repair có chất lượng tương đương lúc chạy baseline. | Quality report PASS ở baseline và repaired. |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Nguồn cấp dữ liệu gốc (Crossref API) thường xuyên thay đổi và có thể xảy ra trường hợp các query giống hệt nhau sẽ trả về dữ liệu mới ở các thời điểm khác nhau. Việc thiếu vắng dữ liệu sạch và nhất quán sẽ dẫn đến việc eval ở phase sau bị phụ thuộc vào external factors, phá vỡ nguyên lý của reproducible experiment.

### Cách triển khai

Tại pha Ingestion, thay vì chỉ truyền dữ liệu trong bộ nhớ, một JSON raw snapshot được lưu xuống đĩa. Sau đó, pha Cleaning sẽ load từ snapshot này. Cleaning áp dụng các cơ chế:
1. Xác nhận `paper_id` tồn tại, làm định danh duy nhất.
2. Chuẩn hóa title và summary (trám rỗng nếu missing).
3. Parsing string date sang datetime object, sau đó tính toán `age_days` dựa trên today timestamp tại thời điểm khởi tạo pipeline.
4. Tổng hợp `text_for_embedding` làm văn bản cốt lõi cho ChromaDB.

Khi xảy ra quá trình repair ở bước sau, flow không fetch lại từ Crossref mà bắt đầu từ việc đọc lại raw snapshot. Do đó, dataset drift là 0.

### Cách xác minh

```bash
uv run python script/run_phase1.py
```
- **Kết quả mong đợi:** Output tạo thành công `data/raw/` và `data/clean/`, log in ra cho thấy số lượng duplicates bị loại bỏ hoặc missing field được điền tự động.
- **Kết quả thực tế:** Pipeline chạy ra đủ 24 records cho cả baseline raw và clean.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Làm thế nào để đảm bảo dữ liệu sau repair hoàn toàn khớp với baseline?
- **Phương án đã chọn:** Tách rời logic ingestion từ mạng (`fetch_api`) và logic xử lý raw payload (`process_raw`). Lưu trữ ngay payload thô xuống ổ cứng trước khi parse. 
- **Lý do:** Điều này cho phép pipeline "tái sinh" dữ liệu sạch ở pha repair từ đúng 1 tệp tin gốc không thay đổi. Nếu ta parse rồi lưu file JSON đã mất mát metadata thì quá trình khôi phục có thể không đầy đủ bằng.
- **Bằng chứng:** Sau lệnh chạy repair, lượng tài liệu phục hồi về 24 records với schema 100% giống baseline.

## 6. Một lỗi/blocker đã xử lý

- **Triệu chứng:** Trong lúc tính toán `age_days`, nếu date `published` bị khuyết, pipeline văng Exception.
- **Nguyên nhân gốc:** Không phải API response nào cũng tuân thủ format metadata chuẩn.
- **Cách xử lý:** Bắt exception và dùng fallback date mặc định, hoặc tự động assign `age_days = 0` và log lại. 

## 7. Hiểu biết về luồng end-to-end

1. API trả về payload thô, tôi phụ trách lưu và parse.
2. Từ dữ liệu raw, clean pipeline loại bỏ rác, tạo ID ổn định để đồng đội ở pha Index (MiniLM, Chroma) xây dựng hệ thống nhúng.
3. Đồng đội phụ trách eval chạy test qua index và đếm metric. Cùng lúc đó, Observability sẽ giám sát schema từ file JSON output của tôi để chốt xem dataset có pass quality gate hay không.
4. Cuối cùng, luồng repair sử dụng chính module ingestion của tôi (nhưng ở chế độ offline, đọc snapshot đĩa) để cứu dữ liệu.

## 8. Điều học được và hướng cải thiện

1. Dữ liệu bên ngoài (thế giới thực) luôn bẩn. Data pipeline chỉ bền bỉ nếu quy tắc (data contract) đủ rõ ràng giữa các nhóm.
2. Lưu trữ snapshot của dữ liệu chưa đụng tới (raw data) là kĩ năng sống còn để audit và debug sau này.
3. Nếu có thời gian, tôi sẽ bổ sung schema validator (như Pydantic) ở cấp độ clean dataset để quăng exception sớm nhất khi có cột không phù hợp.

## 9. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.

**Họ và tên:** Nguyễn Văn Huy
**Ngày xác nhận:** 2026-08-06
