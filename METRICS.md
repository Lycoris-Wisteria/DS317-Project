# Định nghĩa các độ đo chất lượng dữ liệu Yelp (v2)

Cơ sở:
- **Báo cáo đo lường CLDL** (Phần A: quy tắc, ngưỡng, cách tính điểm; Phụ lục F: danh mục quy tắc). Phần B (kết quả đo) không dùng.
- **TEMPO-DQ** (Nguyen et al., *Information Processing & Management* 64(2), 2027, 105175), mục 5.2.1, Eq. (1)–(4), lớp *Conventional*. Dùng làm **cơ sở khái niệm và đối chiếu chéo** (mục 6). AccTEMPO (Eq. 5–7) chưa triển khai.

Danh mục quy tắc từng bảng (mã, cột, ngưỡng) nằm ở `RULES.md`, sinh tự động từ `config.yaml`. Tài liệu này định nghĩa **cách tính**; `config.yaml` định nghĩa **đo cái gì**.

---

## 1. Đơn vị đo: ô

| Ký hiệu | Ý nghĩa |
|---|---|
| ô $x$ | giá trị của một cột tại một dòng, là đơn vị đếm của **mọi** khía cạnh. |
| ô tổ hợp | khóa ghép (vd. `(user_id, business_id, date)`) được coi là **một** ô, nhãn `(a, b, …)`. |
| ô đa trị | ô chứa nhiều phần tử (`elite`, `friends`, `hours`): sai nếu **bất kỳ** phần tử nào sai. |
| $\mathrm{chk}_r(x)$ | hàm kiểm tra của quy tắc $r$, trả về **một trong ba giá trị** dưới đây. |

$$\mathrm{chk}_r(x)=\begin{cases}\textbf{True} & \text{ô đạt quy tắc}\\ \textbf{False} & \text{ô vi phạm quy tắc}\\ \textbf{N/A} & \text{ô không được xét: không vào tử số lẫn mẫu số}\end{cases}$$

Ô là **N/A** khi không thể kết luận đúng hay sai (giá trị thiếu đã bị tính ở Đầy đủ; giá trị sai kiểu đã bị tính ở Hợp lệ-`dtype`; khóa ghép thiếu một thành phần; không tra được bản ghi tham chiếu). Cách này đảm bảo **một sai sót chỉ bị đếm ở một quy tắc gốc**, không bị đếm lặp ở các quy tắc phụ thuộc.

## 2. Công thức điểm (báo cáo A.1)

**Điểm quy tắc** $r$:

$$S_r = 1-\frac{\sum_{x}\delta\big(\mathrm{chk}_r(x)=\text{False}\big)}{\sum_{x}\delta\big(\mathrm{chk}_r(x)\neq \text{N/A}\big)}\qquad (1)$$

Where:
- $x$ chạy trên mọi ô thuộc phạm vi của $r$;
- tử số = số ô vi phạm (`n_violations`); mẫu số = số ô được xét (`n_units`) = ô True + ô False.

**Điểm khía cạnh** $d$ của bảng $t$:

$$S_{t,d} = \frac{1}{|R_{t,d}|}\sum_{r\in R_{t,d}} S_r\qquad (2)$$

Where:
- $R_{t,d}$ = các quy tắc **xếp hạng** (`level` = `star` hoặc `general`) của khía cạnh $d$ trong bảng $t$ có ít nhất một ô được xét;
- quy tắc `report` (C7, C8, S6, T4) chỉ báo cáo, **không** vào $R_{t,d}$.

**Cờ quy tắc cứng ★:**

$$\mathrm{flag}_{t,d}=\exists\, r\in R_{t,d}:\ r\text{ là ★ và } S_r<\theta^{\star}_{bad}\qquad (3)$$

Cờ ⚑ báo khía cạnh có vấn đề **kể cả khi điểm trung bình (2) cao**, vì một quy tắc cứng hỏng bị trung bình che mất.

**Xếp hạng** theo Bảng A.1 (Tốt: $S\ge\theta_{good}$; Chú ý: $\theta_{bad}\le S<\theta_{good}$; Tệ: $S<\theta_{bad}$):

| Khía cạnh | Tốt ≥ | Tệ < | | Quy tắc ★ | Tốt ≥ | Tệ < |
|---|---|---|---|---|---|---|
| Đầy đủ | 0,98 | 0,95 | | (mọi ★) | 0,999 | 0,99 |
| Hợp lệ | 0,99 | 0,95 | | U1 ghi đè | **1,0** | 0,99 |
| Duy nhất | 0,99 | 0,95 | | S7, S8 | 0,90 | 0,80 |
| Nhất quán | 0,99 | 0,95 | | | | |
| Kịp thời | 0,99 | 0,95 | | | | |
| Chính xác | 0,90 | 0,80 | | | | |

Ngưỡng do báo cáo đặt (nhóm tự đặt theo thực tế dữ liệu, chưa kiểm chứng với tài liệu chính thức của Yelp). Ngưỡng riêng của từng quy tắc khai ở `thresholds:` trong `config.yaml`.

## 3. Sáu khía cạnh: ô vi phạm là gì, hàm trả True/False vì sao

| Khía cạnh | Hàm (`type`) | **True** khi | **False** khi | **N/A** khi | Vì sao |
|---|---|---|---|---|---|
| **Đầy đủ** | `not_null` | ô có giá trị (không NaN/None, không rỗng/khoảng trắng, không là token thiếu như `"None"`) | ô thiếu | không có (mọi ô đều xét) | Eq.(2) paper: thiếu = null; báo cáo C3 coi text rỗng là thiếu |
| | `coverage` | (C8, chỉ báo cáo) tỷ lệ `business_id` của bảng nằm trong `business` | | | độ phủ POI |
| **Hợp lệ** | `dtype` | ô ép được sang kiểu yêu cầu | ô có giá trị nhưng không ép được | ô thiếu | Data Type; sai kiểu chỉ đếm ở đây |
| | `range`, `enum` | ô là số trong miền cho phép | ô là số nhưng ngoài miền | ô thiếu hoặc không phải số | Domain Range; ngưỡng từ từ điển dữ liệu của báo cáo |
| | `regex`, `str_type`, `json_object`, `hours_format` | ô đúng định dạng/kiểu | có giá trị nhưng sai định dạng | ô thiếu | định dạng id 22 ký tự, `state` 2 chữ hoa, `hours` dạng `H:M-H:M`... |
| | `id_list` | (V11 `friends`) danh sách rỗng (`None`, `''`, `[]`) hoặc mọi phần tử là id 22 ký tự | có phần tử sai định dạng, hoặc không đọc được thành danh sách | ô thiếu | dữ liệu lưu danh sách dạng chuỗi `"['id1', 'id2']"`; hàm bóc ngoặc/nháy rồi kiểm từng phần tử (cùng quy ước ô đa trị: sai nếu bất kỳ phần tử nào sai) |
| **Duy nhất** | `unique` | khóa xuất hiện **lần đầu** (hoặc duy nhất) | bản **thứ 2 trở đi** (bản dư thừa) | một thành phần của khóa thiếu | số lỗi = số bản ghi bị loại khi khử trùng: 3 review nhân đôi → **3 lỗi**, không phải 6 |
| **Nhất quán** | `fk` | giá trị có trong khóa bảng cha | có giá trị nhưng không có ở bảng cha (mồ côi) | ô thiếu | Foreign Key Integrity |
| | `date_ge_lookup` | ngày ≥ ngày tra cứu theo khóa (vd. `date ≥ yelping_since`) | sớm hơn | ô thiếu/sai kiểu, hoặc không tra được | logic thời gian liên bảng |
| | `elite_years` | mọi năm trong `elite` ∈ [năm `yelping_since`; năm $T_{ref}$] | có năm ngoài khoảng | rỗng hoặc không có năm hợp lệ | ràng buộc logic |
| | `ref_compare` | khớp số tính lại từ chính bộ dữ liệu (trong dung sai; `at_least`: ≥ tham chiếu) | lệch quá dung sai | thiếu giá trị/tham chiếu | S3, S4, S7, S8: đối chiếu chéo nội bộ, xếp ở Nhất quán theo báo cáo |
| | `city_spelling` | city dùng cách viết phổ biến nhất của nhóm cùng dạng chuẩn hóa | là cách viết khác (`'phoenix '`) | ô thiếu | một thành phố chỉ một cách viết |
| | `city_state` | cặp (city, state) không hiếm | cặp hiếm (Phoenix, PA) | ô thiếu, hoặc city quá ít dòng | thành phố trùng tên nhiều bang nên chỉ coi sai khi hiếm |
| **Kịp thời** | `in_window` | mốc thời gian ∈ [`T_start`; hết ngày `T_ref`] | ngoài khung | ô thiếu/sai kiểu | dữ liệu là **snapshot cố định**: kịp thời = đúng khung thời gian của snapshot; `T3` (checkin) chỉ xét cận trên; `T2` (user) dùng cận dưới riêng 2004-07-01 (Yelp thành lập 07/2004), vì người dùng đăng ký sớm hơn review đầu tiên (2005-02-16) |
| | `activity_rate` | (T4, chỉ báo cáo) POI đang mở có hoạt động trong 24 tháng trước `T_ref` | đang mở nhưng không hoạt động | POI đã đóng | độ "còn sống" của POI |
| **Chính xác** | — | **không đo** | | | không có nguồn tham chiếu độc lập tin cậy (báo cáo F.1); S7/S8 là đối chiếu chéo nên xếp Nhất quán |

Ghi chú: `true`, `false`, `na`, `why` của từng hàm nằm trong decorator `@rule_type` ở `dq/rules.py` và được in ra bảng cuối `RULES.md`; test kiểm tra không hàm nào thiếu mô tả.

## 4. Ví dụ

- **Duy nhất (U1, review).** `review_id` = `[A, B, B, B, C]`. Ô: `A` True, `B` (lần 1) True, `B` (lần 2, 3) False, `C` True → $S=1-2/5=0{,}6$. Nếu đếm tất cả bản của khóa trùng sẽ ra 3 lỗi và là sai (khử trùng chỉ loại 2 bản).
- **Hợp lệ (V4, `review_count` số nguyên ≥ 0).** `["3", "abc", "-1", "2.5", None]` → `True, N/A, False, False, N/A`. `"abc"` đã bị `dtype` (V0) đếm, ô thiếu đã bị Đầy đủ đếm.
- **Kịp thời (T1).** Với `T_start` = 2005-02-16, `T_ref` = 2022-01-19: `2022-01-19 23:59:59` True (hết ngày), `2022-01-20 00:00:00` False.
- **Nhất quán (S1).** `date ≥ yelping_since` của chính người viết; user không tồn tại → N/A (lỗi mồ côi do `fk` bắt).

## 5. Ma trận áp dụng (sinh từ `config.yaml`)

| Bảng | Đầy đủ | Duy nhất | Nhất quán | Kịp thời | Hợp lệ | Chính xác |
|---|---|---|---|---|---|---|
| business | C1, C2 (+C7) | U1, U3 | S5a, S5b, S7 (+S6) | chỉ T4 (báo cáo) | V0–V5, V8, V10, V12a, V12b | N/A |
| checkin | C5 (+C8) | U1 | S1 | T3 | V1, V6 | N/A |
| review | C3 | U1, U4 | S1, S2 | T1 | V0, V1, V3, V4, V6 | N/A |
| tip | C4 | U2 | S1, S2 | T1 | V0, V1, V4, V6 | N/A |
| user | C6 (+C7) | U1 | S3, S4, S8 | T2 | V0, V1, V4, V6, V7, V9, V11 | N/A |

(+X) = quy tắc chỉ báo cáo. Khía cạnh không áp dụng được ghi **N/A kèm lý do** trong `config.yaml` (`not_applicable`), không bị bỏ lặng lẽ.

## 6. Quan hệ với TEMPO-DQ (đối chiếu chéo, không dùng xếp hạng)

| TEMPO-DQ | Tương ứng trong v2 |
|---|---|
| Eq.(2) Completeness $=1-\frac{\sum\delta(a_i=\text{null})}{n}$ | quy tắc `not_null` (C*) |
| Eq.(3) Consistency, điều kiện Domain Range, Non-null, Data Type, Logical Constraints, Uniqueness $a_i\notin\text{duplicates}(A)$, Foreign Key | Hợp lệ (range/enum/dtype/regex), Duy nhất, Nhất quán (fk, logic) |
| Eq.(4) Timeliness `isOnTime` | `in_window` |
| Eq.(1) Accuracy (khớp tham chiếu) | không đo; xem N/A |
| Gộp bằng trung bình cộng theo grain | báo kèm `score_grain_tempo` (cột trong `results_aspects.csv`) và `tempo_dq_eq2_by_column.csv` |

Khác biệt cố ý so với paper: (i) đơn vị là **ô** thay vì grain-dòng; (ii) điểm khía cạnh là **trung bình điểm quy tắc** (báo cáo A.1) thay vì trung bình theo grain; (iii) có cờ ★; (iv) Kịp thời đo theo **khung snapshot** thay vì độ trễ so với một deadline.

## 7. Giả định và hạn chế cần nhóm xác nhận

1. `T_ref` = 2022-01-19 là ngày xuất dữ liệu; `T_start` = 2005-02-16 theo báo cáo (T1) nhưng **chưa xác nhận nguồn**. T2 (user) dùng cận dưới riêng 2004-07-01 = thời điểm Yelp thành lập (07/2004, nhóm nhớ; cần dẫn nguồn). Dữ liệu thật có `yelping_since` sớm nhất 2004-10-12, nằm trong khung.
2. Ngưỡng Bảng A.1 là của báo cáo; không kiểm chứng được với tài liệu chính thức của Yelp (không truy cập được).
3. Báo cáo **không nêu ngưỡng** cho `city_state` (S5b): `min_total = 20`, `share_min = 0.01` do công cụ đặt; T4 (24 tháng) cũng là tham số của công cụ.
4. S3 (`user.review_count` ≥ số review quan sát) bị **thổi phồng khi `review` còn bản trùng**, nên nên đo lại sau khử trùng (KQ_v1).
5. Khóa ghép là một ô: một dòng có khóa ghép trùng chỉ tính 1 lỗi, dù khóa gồm nhiều cột.
6. `friends` chỉ đo trên mẫu `max_rows` (mặc định 200.000 user) vì kích thước.
7. Chính xác không đo; kết quả "Tốt" của các khía cạnh khác không bảo đảm dữ liệu đúng thực tế.
8. **Chưa chạy trên dữ liệu Yelp thật** (không truy cập được ổ D); mới kiểm thử trên dữ liệu tổng hợp tiêm lỗi.
