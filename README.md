# yelp_dq — đánh giá chất lượng dữ liệu Yelp (báo cáo CLDL + TEMPO-DQ)

Đo 6 khía cạnh (Đầy đủ, Duy nhất, Nhất quán, Kịp thời, Hợp lệ, Chính xác) cho 5 bảng Yelp. Quy tắc, ngưỡng và cách tính điểm theo **Báo cáo đo lường CLDL** (Phần A, Phụ lục F); khái niệm theo TEMPO-DQ (lớp Conventional). Đơn vị đo là **ô**; hàm kiểm tra trả True / False / N/A cho từng ô (xem `METRICS.md`).

## Chạy

```bash
pip install -r requirements.txt
python -m dq.run --config config.yaml --data-dir "C:\Users\Yoga\OneDrive\Desktop\UIT code\ds317\archive" --out working_v0 --label KQ_v0
# sửa lại path nếu muốn chạy lại
# chỉ một vài bảng: --tables business,review      bỏ biểu đồ: --no-plots
# sau khi cải thiện dữ liệu, đo lại cùng bộ quy tắc rồi so sánh:
python -m dq.run --config config.yaml --data-dir <dữ liệu đã sửa> --out working_v1 --label KQ_v1
python -m dq.compare working_v0 working_v1 --out so_sanh.md
python -m pytest tests -q                              # kiểm thử trên dữ liệu tổng hợp
python -m dq.catalog --config config.yaml > RULES.md   # sinh lại danh mục quy tắc
```

Hoặc mở `Danh_gia_chat_luong_Yelp.ipynb`.

## Cấu trúc

| Tệp                                                         | Vai trò                                                                                                                                                                                                       |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `METRICS.md`                                               | **Định nghĩa độ đo**: ô, True/False/N/A và lý do, công thức (1)–(3) có chú thích, ngưỡng, ma trận áp dụng, giả định                                                               |
| `config.yaml`                                              | **Nguồn duy nhất của quy tắc**: $T_{ref}$, ngưỡng, từng quy tắc theo mã báo cáo (C1, V2, U1, S3, T1...). Thêm/bớt ở đây, không sửa code                                              |
| `RULES.md`                                                 | Danh mục luật, sinh tự động từ `config.yaml`                                                                                                                                                           |
| `dq/io.py`, `context.py`                                 | đọc parquet (giữ nguyên kiểu thô); dựng tham chiếu liên bảng một lần                                                                                                                               |
| `dq/utils.py`                                              | Hàm tiện ích dùng chung: nhận biết ô có giá trị, ép số / ép thời gian, tách danh sách năm, gộp kết quả ô đa trị về dòng, chuẩn hóa chữ, parse JSON. Trả mảng theo vị trí dòng |
| `dq/rules.py`                                              | các loại luật (`regex`, `range`, `fk`, `ref_match`, ...)                                                                                                                                            |
| `dq/engine.py`                                             | điểm ô → quy tắc → khía cạnh, cờ ★, xếp hạng                                                                                                                                                       |
| `dq/report.py`, `run.py`, `compare.py`, `catalog.py` | CSV, biểu đồ, `report.md`, CLI, so sánh KQ_v0/KQ_v1, sinh `RULES.md`                                                                                                                                   |
| `tests/`                                                   | dữ liệu tổng hợp tiêm lỗi với số lượng biết trước + kiểm thử                                                                                                                                    |

## Đầu ra (thư mục `--out`)

Đọc theo thứ tự: `report.md` → `results_aspects.csv` → `results_rules.csv` → `violation_samples.csv`.

| File                           | Nội dung                                                                                                                                                                                                                            | Dùng để                                             |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `report.md`                  | Báo cáo tự sinh: điểm khía cạnh theo bảng, chi tiết từng quy tắc, quy tắc cần xử lý, chỉ số chỉ báo cáo, khía cạnh N/A, hồ sơ thời gian, đối chiếu TEMPO-DQ                                              | Đọc tổng quan, dán vào báo cáo                  |
| `results_aspects.csv`        | Mỗi dòng là một (bảng × khía cạnh): điểm, xếp hạng Tốt/Chú ý/Tệ, cờ ⚑ (có quy tắc ★ ở mức Tệ), danh sách quy tắc bị cờ, trạng thái (Đo được / N/A / Chỉ báo cáo) và lý do                     | Ma trận điểm 5 bảng × 6 khía cạnh               |
| `results_rules.csv`          | Mỗi dòng là một quy tắc: số ô được xét (`n_units`), số ô vi phạm (`n_violations`), số ô chỉ gắn nhãn (`n_flagged`), điểm, xếp hạng, hành động đề xuất, giá trị lỗi phổ biến (`top_values`) | Biết quy tắc nào kéo điểm xuống                 |
| `violation_samples.csv`      | Ô lỗi mẫu (mặc định 20 ô mỗi quy tắc), kèm khóa bản ghi, tên cột, giá trị                                                                                                                                            | Tra lại dữ liệu gốc để kiểm chứng lỗi         |
| `results_by_cell_column.csv` | Số ô xét và ô vi phạm tách theo từng cột của quy tắc                                                                                                                                                                      | Biết cột nào gây lỗi trong quy tắc nhiều cột   |
| `results_dataset.csv`        | Điểm mức bộ dữ liệu: trung bình các bảng theo từng khía cạnh                                                                                                                                                             | Đánh giá toàn bộ dữ liệu                        |
| `results_metrics.csv`        | Chỉ số chỉ báo cáo: C8 (độ phủ), S6 (tổng `review_count` so với số review), T4 (tỷ lệ POI còn hoạt động)                                                                                                          | Số liệu tham khảo, không vào điểm               |
| `temporal_profile.csv`       | Mốc sớm nhất/muộn nhất, số mốc ngoài khung, phân bố theo năm của các cột thời gian                                                                                                                                    | Thông tin, không tính điểm                        |
| `tempo_dq_eq2_by_column.csv` | Tỷ lệ thiếu theo từng cột (Eq.2 của TEMPO-DQ), kèm cột có thuộc quy tắc Đầy đủ nào không                                                                                                                            | Đối chiếu chéo với paper                          |
| `run_metadata.json`          | Nhãn lần đo, thời điểm chạy, phiên bản code, mã băm `config.yaml`, ngưỡng, số dòng từng bảng                                                                                                                      | Truy vết: biết kết quả sinh ra từ cấu hình nào |
| `chart_<bảng>.png`          | Biểu đồ điểm từng quy tắc của bảng, tô màu theo xếp hạng                                                                                                                                                                | Đưa vào báo cáo                                   |

`--label` (KQ_v0, KQ_v1...) được ghi vào `report.md` và `run_metadata.json`; `python -m dq.compare` dùng hai file `results_*.csv` của hai lần đo để so sánh trước/sau.

## Lưu ý quan trọng

- **Chạy từ thư mục chứa `dq/`**, vì lệnh `python -m dq.run` cần thấy package `dq`.
- **Đường dẫn Windows trong `config.yaml`:** đặt trong nháy đơn (`'C:\...'`) hoặc dùng `/`; nháy kép làm YAML hiểu `\U` là ký tự escape và báo lỗi. Cách đơn giản nhất là truyền `--data-dir`, giá trị này ghi đè `config.yaml`.
- **Tên file dữ liệu** khai ở khóa `file:` của từng bảng trong `config.yaml` (checkin là `checkin_events.parquet`). Đổi tên file thì sửa ở đây.
- **Tham số do nhóm đặt, báo cáo CLDL không nêu:** `city_state` (`min_total` = 20, `share_min` = 0.01), T4 (24 tháng). `T_start` = 2005-02-16 (T1); T2 dùng cận riêng 2004-07-01 (Yelp thành lập 07/2004). Đổi các giá trị này thì ghi lại và chạy lại toàn bộ.
- **Chính xác không đo** (không có nguồn tham chiếu độc lập). S7, S8 chỉ là đối chiếu chéo nội bộ, xếp ở Nhất quán. Điểm "Tốt" của các khía cạnh khác không bảo đảm dữ liệu đúng thực tế.
- **S3, S6, S8 phụ thuộc bảng `review`:** nếu `review` còn bản trùng thì các số này bị ảnh hưởng. Nên khử trùng rồi đo lại (KQ_v1) và so sánh.
- **Quy tắc ★ cần đọc cột `n_violations`, không chỉ điểm:** điểm làm tròn 6 chữ số nên 7 ô lỗi trên 21 triệu ô vẫn hiện 1,000000, nhưng quy tắc ★ yêu cầu xử lý mọi vi phạm.
- **Kịp thời của `business` không đo được** (không có cột thời gian), chỉ có T4 tham khảo.
- **Ô lỗi mẫu** trong `violation_samples.csv` chỉ là mẫu (`n_sample` trong `config.yaml`); số lỗi đầy đủ ở `results_rules.csv`.
- **Thêm quy tắc:** sửa `config.yaml`, sinh lại `RULES.md` bằng `python -m dq.catalog`, rồi chạy `pytest` để chắc code không hỏng.
- Chưa có AccTEMPO (Eq. 5–7).
