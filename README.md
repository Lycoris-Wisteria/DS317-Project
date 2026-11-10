# Đánh giá chất lượng dữ liệu Yelp thô

**Mục đích:** khảo sát một lần dữ liệu Yelp gốc (snapshot 19/01/2022) cho bài toán gợi ý POI kế tiếp (ST-GUGEN) theo 6 khía cạnh của Báo cáo đo lường CLDL (Đầy đủ, Duy nhất, Nhất quán, Kịp thời, Hợp lệ, Chính xác), để (1) biết lỗi ở bảng nào, nặng đến đâu; (2) quyết định xử lý (dùng trực tiếp / gắn cờ / sửa-điền / loại). Chỉ đánh giá dữ liệu thô, không đo lại sau làm sạch; không phải hệ thống giám sát tự động.

## Cấu trúc thư mục

```
DS317-Project/
├── README.md                     <- Mục đích, cách chạy, định nghĩa độ đo
├── danh_gia_cldl.py              <- Code: quy tắc từng bảng, hàm kiểm tra, tính điểm, sinh báo cáo, tự kiểm
├── requirements.txt              <- Thư viện cần cài
└── BaoCao_CLDL.ipynb         	  <- Báo cáo: kết quả, biểu đồ, ô lỗi mẫu đã chạy sẵn
```

## Cách chạy

```bash
pip install -r requirements.txt
python danh_gia_cldl.py --data-dir ../../archive #đường dẫn chứa file parquet
```

`--data-dir` ghi đè đường dẫn dữ liệu trong `CONFIG_YAML` (đường dẫn Windows trong YAML dùng nháy đơn hoặc `/`). Muốn thêm/bớt/đổi ngưỡng quy tắc thì sửa `CONFIG_YAML` ở đầu `danh_gia_cldl.py`.

Cơ sở các qui tắc của các khía cạnh dựa trên **Báo cáo đo lường CLDL** (Phần A: quy tắc, ngưỡng, cách tính; Phụ lục F: danh mục quy tắc) và **TEMPO-DQ** (Nguyen et al., *IP&M* 64(2), 2027, 105175, Eq. (1)–(4)) làm cơ sở khái niệm.

## Lưu ý

- Chính xác không đo (không có nguồn tham chiếu độc lập); S6–S8 chỉ đối chiếu chéo giữa các bảng
- Điểm làm tròn 6 chữ số: với quy tắc ★ đọc cột số ô vi phạm
- Notebook chạy sẵn cần `nbclient` và `ipykernel`; nếu thiếu, notebook vẫn được tạo, mở lên rồi Run All.

---

## 1. Ô và True / False / N/A

Đơn vị đếm của mọi khía cạnh là **ô** (một cột tại một dòng). Khóa ghép `(a, b)` là một ô; ô đa trị (`elite`, `friends`, `hours`) sai nếu bất kỳ phần tử nào sai. Mỗi quy tắc $r$ kiểm từng ô:

$$
\mathrm{chk}_r(x)=\begin{cases}\textbf{True} & \text{đạt}\\ \textbf{False} & \text{vi phạm}\\ \textbf{N/A} & \text{không xét (không vào tử số lẫn mẫu số)}\end{cases}
$$

Ô là N/A khi không thể kết luận (đã bị đếm ở quy tắc gốc khác: thiếu → Đầy đủ, sai kiểu → Hợp lệ-`dtype`; hoặc không tra được bản ghi tham chiếu). Nhờ vậy **một sai sót chỉ đếm một lần**.

## 2. Điểm và xếp hạng

$$
S_r = 1-\frac{\#\text{False}}{\#\text{True}+\#\text{False}}\ (1)\qquad S_{t,d}=\frac{1}{|R_{t,d}|}\sum_{r\in R_{t,d}}S_r\ (2)\qquad \mathrm{flag}_{t,d}=\exists r\in R_{t,d}:\ r\ \text{là ★},\ S_r<\theta^\star_{bad}\ (3)
$$

Where: $R_{t,d}$ = quy tắc xếp hạng (★ hoặc thường) của khía cạnh $d$ trong bảng $t$ có ô được xét; quy tắc *chỉ báo cáo* (C7, C8, S6, T4) không vào $R$. Cờ ⚑ báo vấn đề của quy tắc ★ dù điểm trung bình cao.

Xếp hạng theo Bảng A.1: Tốt $S\ge\theta_{good}$; Tệ $S<\theta_{bad}$; còn lại Chú ý. Đổi ở `thresholds:` trong `CONFIG_YAML` (đầu file `danh_gia_cldl.py`).

| Khía cạnh                                  | Tốt ≥ | Tệ < |  | Quy tắc ★ | Tốt ≥ | Tệ < |
| -------------------------------------------- | ------- | ----- | - | ----------- | ------- | ----- |
| Đầy đủ                                   | 0,98    | 0,95  |  | mọi ★     | 0,999   | 0,99  |
| Hợp lệ, Duy nhất, Nhất quán, Kịp thời | 0,99    | 0,95  |  | U1          | 1,0     | 0,99  |
| Chính xác                                  | 0,90    | 0,80  |  | S7, S8      | 0,90    | 0,80  |

## 3. Ô vi phạm là gì, hàm trả True/False vì sao

| Khía cạnh           | Hàm                                                       | True                                                                                                                  | False                                                                 | N/A                            |
| --------------------- | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------ |
| **Đầy đủ**  | `not_null`                                               | ô có giá trị (không NaN, rỗng, `"None"`)                                                                      | ô thiếu                                                             | -                             |
| **Hợp lệ**    | `dtype`                                                  | ép được sang kiểu yêu cầu                                                                                      | có giá trị nhưng không ép được                               | ô thiếu                      |
|                       | `range`, `enum`                                        | số trong miền cho phép                                                                                             | số ngoài miền                                                      | thiếu / không phải số      |
|                       | `regex`, `str_type`, `json_object`, `hours_format` | đúng định dạng                                                                                                   | sai định dạng                                                      | thiếu                         |
|                       | `id_list`                                                | `friends` rỗng hoặc mọi phần tử là id 22 ký tự (chuỗi `"['id', ...]"`)                                   | có phần tử sai                                                     | thiếu                         |
| **Duy nhất**   | `unique`                                                 | khóa xuất hiện lần đầu                                                                                          | bản thứ 2 trở đi (3 review nhân đôi → 3 lỗi, không phải 6) | một thành phần khóa thiếu |
| **Nhất quán** | `fk`                                                     | khóa có ở bảng cha                                                                                                | mồ côi                                                              | thiếu                         |
|                       | `date_ge_lookup`                                         | ngày ≥ ngày tra cứu (vd. `date ≥ yelping_since`)                                                               | sớm hơn                                                             | thiếu / không tra được    |
|                       | `elite_years`                                            | mọi năm `elite` ∈ [năm `yelping_since`; năm `T_ref`]                                                       | có năm ngoài khoảng                                               | rỗng                          |
|                       | `ref_compare`                                            | khớp số tính lại từ chính dữ liệu (S3, S4, S7, S8)                                                            | lệch quá dung sai                                                   | thiếu giá trị / tham chiếu |
|                       | `city_spelling`                                          | đúng cách viết phổ biến nhất của city                                                                         | cách viết khác                                                     | thiếu                         |
|                       | `city_state`                                             | cặp (city, state) không hiếm                                                                                       | cặp hiếm                                                            | thiếu / city quá ít dòng   |
| **Kịp thời**  | `in_window`                                              | mốc ∈ [`T_start`; hết ngày `T_ref`]                                                                           | ngoài khung                                                          | thiếu / sai kiểu             |
|                       | `activity_rate`                                          | (T4, báo cáo) POI mở có hoạt động trong 24 tháng                                                              | mở nhưng không hoạt động                                        | POI đóng                     |
| **Chính xác** | -                                                         | **không đo**: không có nguồn tham chiếu độc lập; S7/S8 là đối chiếu nội bộ nên xếp Nhất quán |                                                                       |                                |

Kịp thời: dữ liệu là snapshot cố định nên "kịp thời" = đúng khung thời gian snapshot. T3 (checkin) chỉ xét cận trên; T2 (user) dùng cận dưới 2004-07-01 (Yelp thành lập 07/2004). Bảng nào không có cột thời gian/không áp dụng khía cạnh nào thì ghi N/A kèm lý do ở `not_applicable` trong `CONFIG_YAML`. Mô tả đầy đủ True/False/N/A và lý do của từng hàm nằm trong notebook báo cáo (mục 1).

Ví dụ: `review_id = [A, B, B, B, C]` → `A` True, `B` True, `B` False, `B` False, `C` True → $S=1-2/5=0{,}6$. `review_count` `["3","abc","-1","2.5",None]` (số nguyên ≥ 0) → `True, N/A, False, False, N/A`.

## 4. Quan hệ với TEMPO-DQ

Eq.(2) Completeness ↔ `not_null`; Eq.(3) Consistency (domain, type, uniqueness, foreign key, logic) ↔ Hợp lệ + Duy nhất + Nhất quán; Eq.(4) Timeliness ↔ `in_window`; Eq.(1) Accuracy ↔ không đo. Khác paper có chủ ý: đơn vị là **ô** (không phải grain-dòng), điểm khía cạnh = trung bình điểm quy tắc, có cờ ★, Kịp thời theo khung snapshot. AccTEMPO (Eq. 5–7) không thuộc phạm vi.
