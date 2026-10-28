# Danh mục quy tắc đo (sinh tự động từ `config.yaml` và `dq/rules.py`)

Mã quy tắc theo báo cáo CLDL. ★ = quy tắc cứng; *Chung* = ngưỡng chung của khía cạnh (Bảng A.1); *Chỉ báo cáo* = không xếp hạng, không vào điểm khía cạnh. Quy tắc có `from_report: false` là bổ sung ngoài báo cáo.

## Đầy đủ

| Mã | Bảng | Phạm vi | Quy tắc | Loại hàm | Cột / khóa | Ngưỡng |
|---|---|---|---|---|---|---|
| C1 | business | nội bảng | business_id, name, latitude, longitude, stars, review_count, is_open ≠ null | `not_null` | business_id, name, latitude, longitude, stars, review_count, is_open | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| C2 | business | nội bảng | city, state, postal_code, categories ≠ null | `not_null` | city, state, postal_code, categories | Chung (Tốt ≥ 0,98; Tệ < 0,95) |
| C3 | review | nội bảng | cả 9 trường ≠ null, text dài ≥ 1 | `not_null` | review_id, user_id, business_id, stars, useful, funny, cool, text, date | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| C4 | tip | nội bảng | user_id, business_id, text, date ≠ null | `not_null` | user_id, business_id, text, date | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| C5 | checkin | nội bảng | business_id ≠ null, mốc check-in không rỗng | `not_null` | business_id, checkin_time | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| C6 | user | nội bảng | user_id, yelping_since, review_count, average_stars ≠ null | `not_null` | user_id, yelping_since, review_count, average_stars | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| C7 | business | nội bảng | tỷ lệ thiếu của address, hours, attributes (chỉ báo cáo) | `not_null` | address, hours, attributes | Chỉ báo cáo |
| C7 | user | nội bảng | tỷ lệ 'không có' của elite ('' ) và friends ('None' hoặc '[]') sau chuẩn hóa (chỉ báo cáo) | `not_null` | elite, friends | Chỉ báo cáo |
| C8 | checkin | liên bảng | độ phủ checkin/business (chỉ báo cáo) | `coverage` | business_id | Chỉ báo cáo |

## Duy nhất

| Mã | Bảng | Phạm vi | Quy tắc | Loại hàm | Cột / khóa | Ngưỡng |
|---|---|---|---|---|---|---|
| U1 | business | nội bảng | business_id không trùng (Tốt = 1) | `unique` | business_id | ★ (Tốt ≥ 1; Tệ < 0,99) · Tốt = 1 |
| U1 | checkin | nội bảng | cặp (business_id, checkin_time) không trùng (Tốt = 1) | `unique` | business_id, checkin_time | ★ (Tốt ≥ 1; Tệ < 0,99) · Tốt = 1 |
| U1 | review | nội bảng | review_id không trùng (Tốt = 1) | `unique` | review_id | ★ (Tốt ≥ 1; Tệ < 0,99) · Tốt = 1 |
| U1 | user | nội bảng | user_id không trùng (Tốt = 1) | `unique` | user_id | ★ (Tốt ≥ 1; Tệ < 0,99) · Tốt = 1 |
| U2 | tip | nội bảng | tip không có khóa riêng nên bộ (user_id, business_id, date, text) không lặp | `unique` | user_id, business_id, date, text | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| U3 | business | nội bảng | bộ (name, address, postal_code) không lặp; name trùng riêng lẻ không tính lỗi | `unique` | name, address, postal_code | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| U4 | review | nội bảng | bộ (user_id, business_id, date) không lặp | `unique` | user_id, business_id, date | Chung (Tốt ≥ 0,99; Tệ < 0,95) |

## Nhất quán

| Mã | Bảng | Phạm vi | Quy tắc | Loại hàm | Cột / khóa | Ngưỡng |
|---|---|---|---|---|---|---|
| S1 | checkin | liên bảng | business_id ∈ business | `fk` | business_id | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| S1 | review | liên bảng | business_id ∈ business; user_id ∈ user | `fk` | business_id, user_id | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| S1 | tip | liên bảng | business_id ∈ business; user_id ∈ user | `fk` | business_id, user_id | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| S2 | review | liên bảng | review.date ≥ user.yelping_since của chính người viết | `date_ge_lookup` | date | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| S2 | tip | liên bảng | tip.date ≥ user.yelping_since của chính người viết | `date_ge_lookup` | date | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| S3 | user | liên bảng | user.review_count ≥ số review của user đó có trong file review (file là tập con) | `ref_compare` | review_count | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| S4 | user | nội bảng | elite: mỗi năm ≥ năm của yelping_since và ≤ 2022 | `elite_years` | elite | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| S5a | business | nội bảng | city chỉ có một cách viết chuẩn sau chuẩn hóa (trim, lower, bỏ dấu) | `city_spelling` | city | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| S5b | business | nội bảng | city thuộc đúng state (cặp city–state không hiếm; city >= 20 dòng, cặp chiếm >= 1%) | `city_state` | city | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| S6 | business | liên bảng | review_count so với số review trong file (chỉ báo cáo, chưa xếp hạng; kèm tổng và tỷ lệ) | `ref_compare` | review_count | Chỉ báo cáo |
| S7 | business | liên bảng | stars lệch ≤ 0,5 so với trung bình review.stars của POI trong file review | `ref_compare` | stars | Chung (Tốt ≥ 0,9; Tệ < 0,8) |
| S8 | user | liên bảng | average_stars lệch ≤ 0,5 so với trung bình review.stars của user trong file review | `ref_compare` | average_stars | Chung (Tốt ≥ 0,9; Tệ < 0,8) |

## Kịp thời

| Mã | Bảng | Phạm vi | Quy tắc | Loại hàm | Cột / khóa | Ngưỡng |
|---|---|---|---|---|---|---|
| T1 | review | nội bảng | review.date ∈ [T_start; T_ref] | `in_window` | date | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| T1 | tip | nội bảng | tip.date ∈ [T_start; T_ref] | `in_window` | date | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| T2 | user | nội bảng | user.yelping_since ∈ [2004-07-01; T_ref] (cận dưới là thời điểm Yelp thành lập 07/2004, sớm hơn T_start của review; cần nhóm xác nhận) | `in_window` | yelping_since | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| T3 | checkin | nội bảng | mọi mốc check-in ≤ T_ref | `in_window` | checkin_time | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| T4 | business | liên bảng | tỷ lệ POI is_open = 1 có ít nhất một review/tip/check-in trong 24 tháng trước T_ref (chỉ báo cáo) | `activity_rate` | is_open | Chỉ báo cáo |

Không áp dụng / không đo:
- **business**: bảng không có thuộc tính thời gian (chỉ có T4 tham khảo)

## Hợp lệ

| Mã | Bảng | Phạm vi | Quy tắc | Loại hàm | Cột / khóa | Ngưỡng |
|---|---|---|---|---|---|---|
| V0 | business | nội bảng | (bổ sung) ô số phải ép được số, nếu không V2-V5 sẽ bỏ qua ô đó *(bổ sung)* | `dtype` | latitude, longitude, stars, review_count, is_open | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| V0 | review | nội bảng | (bổ sung) ô số phải ép được số *(bổ sung)* | `dtype` | stars, useful, funny, cool | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| V0 | tip | nội bảng | (bổ sung) ô số phải ép được số *(bổ sung)* | `dtype` | compliment_count | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| V0 | user | nội bảng | (bổ sung) ô số phải ép được số *(bổ sung)* | `dtype` | review_count, useful, funny, cool, fans, average_stars, compliment_* | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| V1 | business | nội bảng | business_id khớp chuỗi 22 ký tự [A-Za-z0-9_-] | `regex` | business_id | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V1 | checkin | nội bảng | business_id khớp chuỗi 22 ký tự | `regex` | business_id | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V1 | review | nội bảng | review_id, user_id, business_id khớp chuỗi 22 ký tự | `regex` | review_id, user_id, business_id | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V1 | tip | nội bảng | user_id, business_id khớp chuỗi 22 ký tự | `regex` | user_id, business_id | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V1 | user | nội bảng | user_id khớp chuỗi 22 ký tự | `regex` | user_id | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V2 | business | nội bảng | latitude ∈ [27; 54], longitude ∈ [-121; -74] | `range` | latitude, longitude | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V3 | business | nội bảng | stars ∈ {1; 1,5; …; 5} | `enum` | stars | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V3 | review | nội bảng | review.stars ∈ {1…5} (số nguyên) | `enum` | stars | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V4 | business | nội bảng | review_count là số nguyên ≥ 0 | `range` | review_count | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V4 | review | nội bảng | useful, funny, cool là số nguyên ≥ 0 | `range` | useful, funny, cool | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V4 | tip | nội bảng | compliment_count là số nguyên ≥ 0 | `range` | compliment_count | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V4 | user | nội bảng | review_count, useful, funny, cool, fans, compliment_* là số nguyên ≥ 0 | `range` | review_count, useful, funny, cool, fans, compliment_* | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V5 | business | nội bảng | is_open ∈ {0, 1} | `enum` | is_open | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V6 | checkin | nội bảng | mốc check-in đúng định dạng YYYY-MM-DD HH:MM:SS | `dtype` | checkin_time | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V6 | review | nội bảng | date đúng định dạng YYYY-MM-DD HH:MM:SS | `dtype` | date | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V6 | tip | nội bảng | date đúng định dạng YYYY-MM-DD HH:MM:SS | `dtype` | date | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V6 | user | nội bảng | yelping_since đúng định dạng YYYY-MM-DD HH:MM:SS | `dtype` | yelping_since | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V7 | user | nội bảng | average_stars ∈ [1; 5] | `range` | average_stars | ★ (Tốt ≥ 0,999; Tệ < 0,99) |
| V8 | business | nội bảng | state là chuỗi 2 ký tự [A-Z] (ngoại lệ được ghi nhận riêng ở cột top_values) | `regex` | state | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| V9 | user | nội bảng | elite là '' hoặc danh sách năm 4 chữ số (bắt lỗi dạng '20,20') | `regex` | elite | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| V10 | business | nội bảng | hours có dạng H:M-H:M; khung 0:0-0:0 chỉ gắn nhãn 'cần kiểm chứng' (n_flagged), không tính lỗi | `hours_format` | hours | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| V11 | user | nội bảng | friends là danh sách rỗng ('None', '[]') hoặc mọi phần tử là user_id đúng định dạng 22 ký tự (thêm max_rows để lấy mẫu nếu RAM hạn chế) | `id_list` | friends | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| V12a | business | nội bảng | postal_code giữ kiểu chuỗi | `str_type` | postal_code | Chung (Tốt ≥ 0,99; Tệ < 0,95) |
| V12b | business | nội bảng | attributes parse được thành object | `json_object` | attributes | Chung (Tốt ≥ 0,99; Tệ < 0,95) |

## Chính xác

Không có quy tắc.

Không áp dụng / không đo:
- **business**: không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1); S7 là đối chiếu chéo, xếp ở Nhất quán
- **checkin**: không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1)
- **review**: không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1)
- **tip**: không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1)
- **user**: không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1); S8 là đối chiếu chéo, xếp ở Nhất quán

## Hàm kiểm tra: trả về gì, vì sao

Mỗi hàm trả về cho TỪNG Ô một trong ba giá trị: **True** (ô đạt), **False** (ô vi phạm), **N/A** (ô không được xét, không vào tử số lẫn mẫu số). Điểm quy tắc = 1 − (số ô False) / (số ô True + số ô False).

| Loại | Hàm | Khía cạnh | Trả về True khi | Trả về False khi | N/A khi | Vì sao | Nguồn |
|---|---|---|---|---|---|---|---|
| `not_null` | `is_not_missing` | Đầy đủ | ô có giá trị: khác NaN/None, không rỗng/khoảng trắng và không thuộc `missing_tokens` | ô thiếu (NaN/None, chuỗi rỗng/khoảng trắng, hoặc đúng bằng một `missing_tokens`) | không có: mọi ô của cột đều được xét | 'Thiếu' là NaN/None (paper Eq.2). Chuỗi rỗng cũng là thiếu vì báo cáo C3 yêu cầu text dài >= 1. `missing_tokens` chuẩn hóa giá trị mang nghĩa 'không có' (elite = '' ; friends = 'None') trước khi tính tỷ lệ thiếu (ghi chú C7). | Báo cáo CLDL C1-C7; TEMPO-DQ Eq.(2) |
| `coverage` | `coverage` | Đầy đủ | (không tạo ô; chỉ báo cáo) | (không tạo ô; chỉ báo cáo) | (không tạo ô) | Độ phủ = số business_id khác nhau của bảng này nằm trong business / tổng số business. Cho biết bảng này không phủ hết POI. | Báo cáo CLDL C8 (chỉ báo cáo) |
| `dtype` | `is_type_ok` | Hợp lệ | ô có giá trị ép được sang kiểu `kind` (numeric: ép được số; datetime: đúng định dạng thời gian). Với `delimiter`: MỌI phần tử đều ép được | ô có giá trị nhưng không ép được (vd. 'n/a', '20,20' trong cột ngày) | ô thiếu (đã tính ở Đầy đủ) | Data Type của paper. Giá trị sai kiểu chỉ bị đếm ở đây, không bị biến thành NaN rồi đếm ở Đầy đủ. | Báo cáo CLDL V6; TEMPO-DQ Eq.(3) 'Data Type' |
| `range` | `is_in_range` | Hợp lệ | ô là số trong [min; max] (đóng hai đầu); nếu integer=true thì phải là số nguyên | ô là số nhưng ngoài [min; max], hoặc không nguyên khi integer=true | ô thiếu hoặc không ép được số (sai kiểu đã bị bắt ở `dtype`) | Domain Range của paper. Ngưỡng cụ thể lấy từ từ điển dữ liệu của nhóm (báo cáo CLDL). | Báo cáo CLDL V2, V4, V7; TEMPO-DQ Eq.(3) 'Domain Range' |
| `enum` | `is_in_set` | Hợp lệ | ô là số thuộc tập `values` | ô là số nhưng không thuộc tập `values` | ô thiếu hoặc không ép được số | Domain Range dạng tập rời rạc (stars nửa sao; stars review nguyên; is_open nhị phân). | Báo cáo CLDL V3, V5 |
| `regex` | `is_format_ok` | Hợp lệ | toàn bộ chuỗi khớp `pattern` (fullmatch) | ô có giá trị nhưng không khớp pattern | ô thiếu (với allow_empty=true thì chuỗi rỗng vẫn được xét) | Kiểm định dạng. Id Yelp là chuỗi 22 ký tự [A-Za-z0-9_-]; state là 2 chữ in hoa; elite là danh sách năm 4 chữ số; friends là 'None' hoặc danh sách id. | Báo cáo CLDL V1, V8, V9, V11 |
| `id_list` | `is_id_list_ok` | Hợp lệ | ô là danh sách rỗng ('None', '', '[]') HOẶC mọi phần tử khớp `id_pattern`. Chấp nhận cả chuỗi 'a, b', chuỗi dạng danh sách "['a', 'b']" và list/mảng thật | ô có ít nhất một phần tử không khớp `id_pattern`, hoặc không đọc được thành danh sách | ô thiếu (NaN/None) | friends là danh sách user_id nên mỗi phần tử phải đúng định dạng id 22 ký tự. Dữ liệu thực tế lưu danh sách dạng chuỗi "['id1', 'id2']", nên hàm bóc ngoặc và dấu nháy trước khi kiểm từng phần tử, thay vì giả định một dạng phân cách cố định. | Báo cáo CLDL V11 |
| `str_type` | `is_string_type` | Hợp lệ | giá trị là chuỗi (str) | giá trị có mặt nhưng không phải chuỗi (vd. mã bưu chính bị đọc thành số, mất số 0 đầu) | ô thiếu | postal_code phải giữ kiểu chuỗi vì có số 0 đầu và mã Canada có chữ. | Báo cáo CLDL V12 (postal_code) |
| `json_object` | `is_object_ok` | Hợp lệ | giá trị là dict hoặc chuỗi JSON/dict parse được thành object | giá trị có mặt nhưng không parse được thành object | ô thiếu hoặc thuộc `null_tokens` (mặc định 'None') | Cột attributes lồng nhau phải parse được thì mới dùng làm đặc trưng. | Báo cáo CLDL V12 (attributes) |
| `hours_format` | `is_hours_ok` | Hợp lệ | mọi giá trị trong hours có dạng H:M-H:M (vd. '10:0-21:0') | có ít nhất một giá trị sai dạng, hoặc hours không parse được | ô thiếu hoặc thuộc `null_tokens` | Khung '0:0-0:0' KHÔNG tính là lỗi mà được gắn nhãn 'cần kiểm chứng' (đếm riêng ở n_flagged). | Báo cáo CLDL V10 |
| `unique` | `is_unique_key` | Duy nhất | khóa là bản xuất hiện ĐẦU TIÊN hoặc xuất hiện đúng một lần | khóa là bản thứ 2 trở đi của một khóa đã xuất hiện (bản DƯ THỪA) | một thành phần của khóa bị thiếu (không thể kết luận trùng) | Đếm số bản dư thừa = số bản ghi sẽ bị loại khi khử trùng, nên 3 review bị nhân đôi cho 3 lỗi (không phải 6). Khóa ghép được coi là MỘT ô tổ hợp nên không bị nhân đôi theo số cột khóa. | TEMPO-DQ Eq.(3) 'Uniqueness: a_i ∉ duplicates(A)'; cách đếm bản dư thừa do nhóm chọn; Báo cáo CLDL U1-U4 |
| `fk` | `is_in_reference` | Nhất quán | giá trị có trong khóa của bảng cha | giá trị có mặt nhưng KHÔNG có trong bảng cha (mồ côi) | ô thiếu | Toàn vẹn khóa ngoại: dòng mồ côi không nối được vào đồ thị user-POI. | Báo cáo CLDL S1; TEMPO-DQ Eq.(3) 'Foreign Key Integrity' |
| `date_ge_lookup` | `is_not_before_lookup` | Nhất quán | mốc thời gian của ô >= giá trị tra cứu theo khóa (vd. review.date >= yelping_since của chính người viết) | mốc của ô sớm hơn giá trị tra cứu | ô thiếu/không parse được, hoặc không tra được giá trị (user không tồn tại) | Người dùng không thể viết review/tip trước khi đăng ký. Lỗi gắn vào ô date của dòng con (review/tip); yelping_since chỉ là tham chiếu. | Báo cáo CLDL S2; TEMPO-DQ Eq.(3) 'Logical Constraints' |
| `ref_compare` | `is_close_to_reference` | Nhất quán, Chính xác | |giá trị - tham chiếu| <= max(tol_abs, tol_rel·|tham chiếu|); với mode='at_least': giá trị >= tham chiếu - dung sai | lệch quá dung sai | ô thiếu, không có tham chiếu (trừ khi có fill_missing_ref), hoặc tham chiếu dựa trên < min_n dòng | Đối chiếu chéo với số liệu tính lại từ chính bộ dữ liệu (số review, trung bình sao). at_least dùng khi file review là tập con nên review_count chỉ có thể >= số quan sát. | Báo cáo CLDL S3, S6, S7, S8 |
| `elite_years` | `is_elite_consistent` | Nhất quán | mọi năm trong danh sách >= năm của yelping_since VÀ <= max_year (mặc định: năm của T_ref) | có ít nhất một năm sớm hơn năm đăng ký hoặc muộn hơn max_year | ô không có năm hợp lệ nào (rỗng hoặc sai định dạng - đã bắt ở V9); cận dưới chỉ xét khi yelping_since parse được | Một người không thể là Elite trước khi đăng ký hay sau thời điểm xuất dữ liệu. | Báo cáo CLDL S4 |
| `city_spelling` | `is_city_spelling_ok` | Nhất quán | cách viết của city trùng cách viết phổ biến nhất trong nhóm các cách viết cùng dạng chuẩn hóa (trim, lower, bỏ dấu, bỏ ký tự đặc biệt) | city là một cách viết KHÁC của cùng một thành phố (vd. 'phoenix ', 'PHOENIX') | ô thiếu | Cùng một thành phố chỉ nên có một cách viết để nhóm/join theo thành phố không bị tách đôi. | Báo cáo CLDL S5 (vế 'một cách viết chuẩn') |
| `city_state` | `is_city_state_ok` | Nhất quán | cặp (city chuẩn hóa, state) chiếm >= share_min của các dòng có city đó | cặp (city, state) hiếm: chiếm < share_min (vd. 'Phoenix' nhưng state = 'PA') | ô thiếu, hoặc city có < min_total dòng (không đủ căn cứ kết luận) | city phải thuộc đúng state. Vì có thành phố trùng tên ở nhiều bang nên chỉ coi là sai khi cặp (city, state) rất hiếm so với phần còn lại. | Báo cáo CLDL S5 (vế 'thuộc đúng state'). Báo cáo KHÔNG nêu ngưỡng; share_min/min_total do công cụ đặt, cần nhóm xác nhận |
| `in_window` | `is_on_time` | Kịp thời | mốc thời gian nằm trong khung snapshot [T_start; T_ref] (hết ngày T_ref). Với use_start=false chỉ xét cận trên; `t_start` (nếu có) thay cho T_start chung. Với `delimiter`: MỌI mốc đều trong khung | mốc ngoài khung (sớm hơn T_start hoặc muộn hơn ngày xuất dữ liệu) | ô thiếu hoặc không parse được (đã bắt ở `dtype`) | Dữ liệu cố định (snapshot) nên 'kịp thời' là 'đúng khung thời gian của snapshot', không phải 'cập nhật trong 12 tháng so với hôm nay' (lấy hôm nay làm mốc thì mọi bản ghi đều quá hạn). isOnTime của paper so với 'reference timestamp' = ngày xuất dữ liệu. | Báo cáo CLDL T1-T3; TEMPO-DQ Eq.(4) |
| `activity_rate` | `is_recently_active` | Kịp thời | POI đang mở (is_open = 1) có ít nhất một review/tip/check-in trong `months` tháng trước T_ref | POI đang mở nhưng không có hoạt động nào trong khung đó | POI đã đóng (is_open = 0) hoặc thiếu is_open | Thước đo độ 'còn hoạt động' của POI; chỉ tham khảo, dùng khi bài toán cần doanh nghiệp còn hoạt động. | Báo cáo CLDL T4 (chỉ báo cáo) |

