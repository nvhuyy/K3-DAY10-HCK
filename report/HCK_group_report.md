# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K3              |
| Tên nhóm         | HCK     |
| Repository         | https://github.com/nvhuyy/K3-DAY10-HCK |
| Ngày hoàn thành | 2026-08-06               |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Văn Huy | 2A202601635 | Data foundation & pipeline | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py` |
| 2 | Nguyễn Mạnh Cường | 2A202601361 | Corruption, repair & pipeline integration | `src/pipelines/corruption_flow.py`, `script/run_corruption_flow.py` |
| 3 | Nguyễn Đức Nam Khánh | 2A202601103 | Observability & reporting | `src/observability/quality.py`, `data/reports/` |

## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm đã hoàn thành toàn bộ luồng data pipeline từ ingestion (lấy dữ liệu từ Crossref API), cleaning, tạo index, đến thiết lập hệ thống evaluation và observability. Baseline pipeline đã tạo ra các artifact quan trọng bao gồm dữ liệu dạng thô (`raw`), dữ liệu đã làm sạch (`clean`), index của ChromaDB và các báo cáo chất lượng cũng như baseline metrics. 

Trong quá trình thử nghiệm corruption, chúng tôi nhận thấy việc loại bỏ (drop) các record nằm trong frozen test set gây ảnh hưởng lớn nhất đến hệ thống (retrieval hit rate giảm từ 1.0 xuống 0.5, mean token F1 giảm đáng kể). Quá trình repair đã khôi phục lại hoàn toàn bằng cách lấy dữ liệu từ raw snapshot ban đầu thay vì gọi lại API để tránh dataset drift. Retrieval hit rate và token F1 sau đó đã phục hồi về mức baseline, quality và freshness check cũng vượt qua thành công. Blocker đáng kể nhất hiện tại là LLM judge chưa thực sự nhạy bén trong việc đánh giá câu trả lời extractive (accuracy luôn báo 0), cần phải tinh chỉnh prompt và tiêu chí chấm điểm trong tương lai.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> raw response/raw records
    -> cleaning và data modeling
    -> embedding + ChromaDB index
    -> evaluation baseline
    -> quality/freshness reports
    -> corruption
    -> re-index và re-evaluate
    -> repair từ dữ liệu nguồn
    -> comparison report
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref API | Fetch payload, lưu snapshot, parse records   | `data/raw/` | Nguyễn Văn Huy |
| Cleaning          | `data/raw/`        | Lọc missing, dedupe, chuẩn hóa dates, build ID     | `data/clean/` | Nguyễn Văn Huy |
| Embedding/index   | `data/clean/`        | Sinh embeddings (MiniLM), lưu vector collection       | `data/embeddings/`, `data/chroma/` | Nguyễn Mạnh Cường |
| Evaluation        | Chroma index, test set        | Chạy evaluator (hit rate, token F1, LLM judge)     | `data/results/` | Nguyễn Mạnh Cường |
| Observability     | `data/clean/`        | Đo completeness, uniqueness, freshness | `data/quality/` | Nguyễn Đức Nam Khánh |
| Corruption/repair | `data/clean/`, `data/raw/`        | Giả lập nhiễu, lỗi dữ liệu; khôi phục từ raw snapshot    | `data/results/corruption_log.json`, restored data | Nguyễn Mạnh Cường |
| Orchestration     | Toàn bộ system        | Gọi tuần tự các module thành một phase chạy chung           | Reports & artifacts        | Nguyễn Mạnh Cường |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | openai         |
| `LLM_MODEL`                | gpt-4o-mini         |
| Embedding model              | all-MiniLM-L6-v2         |
| Số lượng Crossref records | 24 (sau cleaning)         |
| Retrieval `top_k`           | 3         |
| Freshness threshold          | 180         |
| Random seed, nếu có        | 42         |

### Lệnh cài đặt

```bash
uv sync
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công | 2026-08-06 | `data/reports/phase1_report.md` |
| Corruption flow   | Thành công | 2026-08-06 | `data/reports/corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | api.crossref.org/works endpoint |
| Query/filter                | machine learning / query theo config                  |
| Thời điểm lấy dữ liệu | 2026-08-06                           |
| Số record nhận được    | 24 (số lượng hợp lệ)                         |
| Cơ chế retry/backoff      | Exponential backoff với 3 lần thử nếu gặp lỗi 429/503 |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | string         | Có | Định danh duy nhất (DOI) | Bỏ qua record nếu DOI trống        |
| `title` | string         | Có | Tên tài liệu | Bỏ qua record nếu trống       |
| `summary` | string         | Không | Tóm tắt tài liệu | Gán chuỗi rỗng nếu không có       |
| `published` | string/date         | Không | Ngày phát hành | Dùng fallback date hoặc null |
| `age_days` | integer | Có | Độ cũ của paper | Tính từ ngày hiện tại trừ đi `published` |
| `text_for_embedding` | string | Có | Nội dung gộp để đưa vào index | Trích xuất từ title + summary |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Loại bỏ record không có `paper_id` | Completeness  |              0 | Kiểm tra artifact log |
| Loại bỏ record không có `title` hoặc `title` rỗng | Completeness  |              0 | Kiểm tra quality checks JSON |
| Khử trùng lặp (dedupe) theo `paper_id` | Uniqueness  |              0 (ở baseline) | Số record duplicate là 0 trong baseline_quality.json |

Giải thích cách nhóm tạo `text_for_embedding`, document ID và `age_days`:

- `text_for_embedding`: Được nối từ `title`, các metadata chính như `authors`, `categories` và `summary`.
- `document ID`: Dùng trực tiếp DOI của tài liệu vì nó độc nhất.
- `age_days`: Tính từ ngày thực thi quá trình ingestion so với ngày `published`.

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 12                 |
| Các `question_type`                    | factual, summary, metadata                  |
| Ground-truth document ID                 | Được tham chiếu chính xác đến `paper_id`     |
| Embedding model                          | sentence-transformers/all-MiniLM-L6-v2                  |
| Vector store/collection                  | ChromaDB (`papers-baseline`, `papers-corrupted`, v.v.)                 |
| Retrieval `top_k`                       | 3                   |
| LLM provider/model                       | openai / gpt-4o-mini                   |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` |

Giải thích vì sao test set được giữ nguyên khi đánh giá baseline, corrupted và repaired:

Giữ nguyên test set giúp biến độc lập duy nhất của thí nghiệm là trạng thái của index/dữ liệu. Nếu test set hoặc các câu hỏi thay đổi qua ba lần chạy, chúng ta sẽ không thể xác định được sự khác biệt trong metric đánh giá là do lỗi dữ liệu (corruption) hay là do độ khó câu hỏi (confounding factor).

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/`                          | Có | Chứa snapshot |
| Cleaned dataset          | `data/clean/`                        | Có | |
| Embedding manifest/index | `data/embeddings/`                   | Có | |
| Evaluation set           | `data/eval/`                         | Có | Đã frozen |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | 12 samples |
| Quality/freshness        | `data/quality/`                      | Có | Pass các check |
| Baseline report          | `data/reports/phase1_report.md`      | Có | |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |     1.000 | Tỉ lệ tìm thấy đúng document ID trong top_k là 100%  |
| `mean_token_f1`      |     0.0668 | Phản ánh mức độ trùng lặp từ vựng giữa answer và ground truth                           |
| `judge_accuracy`     |     0.000 | LLM chấm điểm quá khắt khe, đang được xem xét lại prompt |
| `mean_judge_score`   |     1.000 | Cùng lý do với judge_accuracy                           |
| Ragas, nếu có        | N/A | Được bỏ qua do setup yêu cầu `RUN_RAGAS=1` chậm |

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| Title, summary completeness | Completeness       | 1.0         | Pass (1.0) | `baseline_quality.json`   |
| ID uniqueness | Uniqueness       | Duplicate = 0         | Pass (0 duplicates) | `baseline_quality.json`   |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | `data/clean/` dataset            |
| Timestamp mới nhất       | (Theo metadata thực tế từ Crossref)                         |
| Ngưỡng freshness         | 180 ngày                         |
| Trạng thái baseline      | Fresh               |
| Lý do                     | `max_age_days` cao nhất ở baseline là 161 (nhỏ hơn 180) nên toàn bộ index đạt chuẩn fresh. |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| Drop target records | Xóa row theo ID  |          2 | Completeness giảm, Hit rate giảm | Hit rate còn 0.5     | Khôi phục bằng raw snapshot |
| Noise & missing summary | Thêm random text, làm rỗng summary  |          1 | Chất lượng text giảm | Giảm semantic match     | Khôi phục bằng raw snapshot |
| Stale date | Chỉnh published date thành quá khứ |          1 | Freshness FAIL | max_age_days lên 9714 | Khôi phục bằng raw snapshot |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi nhận đầy đủ 4 trường hợp tác động đúng vào các target có trong frozen test set (`overlaps_frozen_test_set`: true).

Giải thích cách repair đảm bảo dữ liệu được phục hồi từ nguồn đáng tin cậy thay vì chỉ che kết quả lỗi:

Repair được thực hiện bằng cách khởi chạy lại quá trình reading và cleaning thông qua dữ liệu thô `data/raw/crossref_records.json` (được snapshot ở baseline). Nếu ta thay vào đó gọi lại API, dữ liệu nguồn có thể thay đổi (dataset drift). Việc tái lập pipeline từ raw bảo đảm clean data được tái tạo nguyên bản như trước khi dính corruption.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   |      1.000 |       0.500 |      1.000 |                      -0.5 |             +0.5 | Nhạy bén rõ rệt |
| `mean_token_f1`        |      0.067 |       0.046 |      0.067 |                      -0.021 |             +0.021 | Chịu ảnh hưởng xấu từ nhiễu |
| `judge_accuracy`       |      0.000 |       0.000 |      0.000 |                      0 |             0 | LLM Judge chưa hiệu quả |
| `mean_judge_score`     |      1.000 |       1.000 |      1.000 |                      0 |             0 | Cần cải thiện prompt đánh giá |
| Quality checks pass/fail |      PASS |       FAIL |      PASS |                      Thay đổi trạng thái |             Khôi phục hoàn toàn | Corrupted thiếu summary, trùng lặp |
| Freshness status         |      PASS |       FAIL |      PASS |                      Thay đổi trạng thái |             Khôi phục hoàn toàn | Corrupted có age = 9714 ngày |

Nêu ít nhất hai kết luận có quan hệ nhân quả được hỗ trợ bởi artifacts:

1. Data missing (xóa document ID) → hit rate giảm mạnh (50%) → agent thiếu context dẫn đến suy giảm metric trả lời (`mean_token_f1` giảm 31.2%).
2. Khôi phục (re-ingestion) từ raw snapshot cố định → freshness và uniqueness checks trở lại trạng thái PASS → hit rate và agent metrics khôi phục hoàn toàn do toàn bộ ground-truth documents xuất hiện trở lại trong vector store.

## 11. Vấn đề tích hợp quan trọng

Mô tả một vấn đề phát sinh khi ghép các module trong pipeline và cách nhóm xử lý:

- **Triệu chứng:** Pipeline báo cáo corruption metric suy giảm không đáng kể ban đầu.
- **Nguyên nhân:** Quá trình corruption tự động đã lấy ra các ID ngẫu nhiên không thuộc tập frozen test set để tác động. Evaluation lại chỉ kiểm tra bằng test set này, kết quả là những tài liệu bị lỗi hoàn toàn không được dùng tới.
- **Cách xử lý:** Cập nhật lại `corrupt_clean_dataframe` để nhận tham số danh sách các target IDs trong test set nhằm corrupt trúng đích.
- **Cách xác minh:** Xác thực field `overlaps_frozen_test_set: true` trong file log và `retrieval_hit_rate` giảm đúng như thiết kế.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| LLM Judge accuracy = 0          | Điểm số đánh giá tự động chưa hữu dụng | Tinh chỉnh lại prompt chấm điểm của judge, dùng test tập nhỏ tự làm tay để calibrating LLM.                              |
| Pipeline orchestrator đồng bộ          | Chạy evaluation tốn khá nhiều thời gian | Tách quá trình tính embedding và đánh giá ra chạy đa luồng hoặc caching API calls.                              |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
