# Báo cáo chất lượng dữ liệu Yelp — KQ_v0

- Chạy lúc 2026-10-28T22:01:03 · mốc snapshot T_ref = 2022-01-19 · khung Kịp thời [2005-02-16; 2022-01-19] · code 2.0.0
- Cấu hình `c:\Users\Yoga\OneDrive\Desktop\UIT code\ds317\mine\DS317-Project\config.yaml` (sha256 1f83eee8c825)
- **Cách tính** (báo cáo CLDL, A.1): điểm quy tắc = 1 − (số ô lỗi / tổng số ô được xét); điểm khía cạnh = trung bình các quy tắc cùng khía cạnh (bỏ quy tắc *chỉ báo cáo*); khía cạnh bị gắn cờ ⚑ nếu có quy tắc ★ ở mức Tệ dù điểm trung bình cao.
- **Xếp hạng** (Bảng A.1): Đầy đủ: Tốt ≥ 0,98, Tệ < 0,95; Hợp lệ: Tốt ≥ 0,99, Tệ < 0,95; Duy nhất: Tốt ≥ 0,99, Tệ < 0,95; Nhất quán: Tốt ≥ 0,99, Tệ < 0,95; Chính xác: Tốt ≥ 0,90, Tệ < 0,80; Kịp thời: Tốt ≥ 0,99, Tệ < 0,95; quy tắc ★: Tốt ≥ 0,999, Tệ < 0,99.

## 1. Điểm khía cạnh theo bảng

| Bảng (số dòng) | Đầy đủ | Duy nhất | Nhất quán | Kịp thời | Hợp lệ | Chính xác |
|---|---:|---:|---:|---:|---:|---:|
| business (150,346) | 0,999854 · Tốt | 0,999532 · Tốt | 0,994975 · Tốt | chỉ báo cáo | 0,999999 · Tốt | N/A |
| checkin (13,356,875) | 1,000000 · Tốt | 0,999735 · Tốt | 1,000000 · Tốt | 1,000000 · Tốt | 1,000000 · Tốt | N/A |
| review (6,990,280) | 1,000000 · Tốt | 0,999998 · Tốt | 0,999990 · Tốt | 1,000000 · Tốt | 1,000000 · Tốt | N/A |
| tip (908,915) | 1,000000 · Tốt | 0,999926 · Tốt | 1,000000 · Tốt | 1,000000 · Tốt | 1,000000 · Tốt | N/A |
| user (1,987,897) | 1,000000 · Tốt | 1,000000 · Tốt | 0,872512 · Tệ | 1,000000 · Tốt | 0,997131 · Tốt | N/A |

Mức bộ dữ liệu (trung bình cộng điểm các bảng đo được): Đầy đủ 0,999971 · Tốt; Duy nhất 0,999838 · Tốt; Nhất quán 0,973495 · Chú ý; Kịp thời 1,000000 · Tốt; Hợp lệ 0,999426 · Tốt.

## 2. Chi tiết từng quy tắc

Đơn vị = ô (khóa ghép U2–U4 tính một ô tổ hợp). `Vi phạm` = số ô False. ★ = quy tắc cứng.

### business

| Mã | Khía cạnh | Phạm vi | Quy tắc | Ô xét | Vi phạm | Điểm | Xếp hạng | Xử lý |
|---|---|---|---|---:|---:|---:|---|---|
| ★ C1 | Đầy đủ | nội bảng | business_id, name, latitude, longitude, stars, review_count, is_open ≠ null | 1,052,422 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| C2 | Đầy đủ | nội bảng | city, state, postal_code, categories ≠ null | 601,384 | 176 | 0,999707 | Tốt | Dùng trực tiếp |
| C7 | Đầy đủ | nội bảng | tỷ lệ thiếu của address, hours, attributes (chỉ báo cáo) | 451,038 | 42,094 | 0,906673 | Chỉ báo cáo | Chỉ báo cáo |
| V0 | Hợp lệ | nội bảng | (bổ sung) ô số phải ép được số, nếu không V2-V5 sẽ bỏ qua ô đó | 751,730 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V1 | Hợp lệ | nội bảng | business_id khớp chuỗi 22 ký tự [A-Za-z0-9_-] | 150,346 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V2 | Hợp lệ | nội bảng | latitude ∈ [27; 54], longitude ∈ [-121; -74] | 300,692 | 1 | 0,999997 | Tốt | Xử lý mọi vi phạm (quy tắc ★) |
| ★ V3 | Hợp lệ | nội bảng | stars ∈ {1; 1,5; …; 5} | 150,346 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V4 | Hợp lệ | nội bảng | review_count là số nguyên ≥ 0 | 150,346 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V5 | Hợp lệ | nội bảng | is_open ∈ {0, 1} | 150,346 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| V8 | Hợp lệ | nội bảng | state là chuỗi 2 ký tự [A-Z] (ngoại lệ được ghi nhận riêng ở cột top_values) | 150,346 | 1 | 0,999993 | Tốt | Dùng trực tiếp |
| V10 | Hợp lệ | nội bảng | hours có dạng H:M-H:M; khung 0:0-0:0 chỉ gắn nhãn 'cần kiểm chứng' (n_flagged), không tính lỗi (⚠ 31674 ô cần kiểm chứng) | 127,123 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| V12a | Hợp lệ | nội bảng | postal_code giữ kiểu chuỗi | 150,346 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| V12b | Hợp lệ | nội bảng | attributes parse được thành object | 136,602 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ U1 | Duy nhất | nội bảng | business_id không trùng (Tốt = 1) | 150,346 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| U3 | Duy nhất | nội bảng | bộ (name, address, postal_code) không lặp; name trùng riêng lẻ không tính lỗi | 145,202 | 136 | 0,999063 | Tốt | Dùng trực tiếp |
| S5a | Nhất quán | nội bảng | city chỉ có một cách viết chuẩn sau chuẩn hóa (trim, lower, bỏ dấu) | 150,346 | 1,791 | 0,988087 | Chú ý | Ghi nhận, gắn cờ hoặc xử lý nhẹ |
| S5b | Nhất quán | nội bảng | city thuộc đúng state (cặp city–state không hiếm; city >= 20 dòng, cặp chiếm >= 1%) | 147,615 | 35 | 0,999763 | Tốt | Dùng trực tiếp |
| S6 | Nhất quán | liên bảng | review_count so với số review trong file (chỉ báo cáo, chưa xếp hạng; kèm tổng và tỷ lệ) | 150,346 | 67,362 | 0,551953 | Chỉ báo cáo | Chỉ báo cáo |
| S7 | Nhất quán | liên bảng | stars lệch ≤ 0,5 so với trung bình review.stars của POI trong file review | 150,346 | 440 | 0,997073 | Tốt | Dùng trực tiếp |
| T4 | Kịp thời | liên bảng | tỷ lệ POI is_open = 1 có ít nhất một review/tip/check-in trong 24 tháng trước T_ref (chỉ báo cáo) | 119,698 | 14,045 | 0,882663 | Chỉ báo cáo | Chỉ báo cáo |

### checkin

| Mã | Khía cạnh | Phạm vi | Quy tắc | Ô xét | Vi phạm | Điểm | Xếp hạng | Xử lý |
|---|---|---|---|---:|---:|---:|---|---|
| ★ C5 | Đầy đủ | nội bảng | business_id ≠ null, mốc check-in không rỗng | 26,713,750 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| C8 | Đầy đủ | liên bảng | độ phủ checkin/business (chỉ báo cáo) | 0 | 0 | — | Chỉ báo cáo | Chỉ báo cáo |
| ★ V1 | Hợp lệ | nội bảng | business_id khớp chuỗi 22 ký tự | 13,356,875 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V6 | Hợp lệ | nội bảng | mốc check-in đúng định dạng YYYY-MM-DD HH:MM:SS | 13,356,875 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ U1 | Duy nhất | nội bảng | cặp (business_id, checkin_time) không trùng (Tốt = 1) | 13,356,875 | 3,543 | 0,999735 | Chú ý | Xử lý mọi vi phạm (quy tắc ★) |
| ★ S1 | Nhất quán | liên bảng | business_id ∈ business | 13,356,875 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ T3 | Kịp thời | nội bảng | mọi mốc check-in ≤ T_ref | 13,356,875 | 0 | 1,000000 | Tốt | Dùng trực tiếp |

### review

| Mã | Khía cạnh | Phạm vi | Quy tắc | Ô xét | Vi phạm | Điểm | Xếp hạng | Xử lý |
|---|---|---|---|---:|---:|---:|---|---|
| ★ C3 | Đầy đủ | nội bảng | cả 9 trường ≠ null, text dài ≥ 1 | 62,912,520 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| V0 | Hợp lệ | nội bảng | (bổ sung) ô số phải ép được số | 27,961,120 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V1 | Hợp lệ | nội bảng | review_id, user_id, business_id khớp chuỗi 22 ký tự | 20,970,840 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V3 | Hợp lệ | nội bảng | review.stars ∈ {1…5} (số nguyên) | 6,990,280 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V4 | Hợp lệ | nội bảng | useful, funny, cool là số nguyên ≥ 0 | 20,970,840 | 7 | 1,000000 | Tốt | Xử lý mọi vi phạm (quy tắc ★) |
| ★ V6 | Hợp lệ | nội bảng | date đúng định dạng YYYY-MM-DD HH:MM:SS | 6,990,280 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ U1 | Duy nhất | nội bảng | review_id không trùng (Tốt = 1) | 6,990,280 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| U4 | Duy nhất | nội bảng | bộ (user_id, business_id, date) không lặp | 6,990,280 | 25 | 0,999996 | Tốt | Dùng trực tiếp |
| ★ S1 | Nhất quán | liên bảng | business_id ∈ business; user_id ∈ user | 13,980,560 | 33 | 0,999998 | Tốt | Xử lý mọi vi phạm (quy tắc ★) |
| S2 | Nhất quán | liên bảng | review.date ≥ user.yelping_since của chính người viết | 6,990,247 | 117 | 0,999983 | Tốt | Dùng trực tiếp |
| ★ T1 | Kịp thời | nội bảng | review.date ∈ [T_start; T_ref] | 6,990,280 | 0 | 1,000000 | Tốt | Dùng trực tiếp |

### tip

| Mã | Khía cạnh | Phạm vi | Quy tắc | Ô xét | Vi phạm | Điểm | Xếp hạng | Xử lý |
|---|---|---|---|---:|---:|---:|---|---|
| ★ C4 | Đầy đủ | nội bảng | user_id, business_id, text, date ≠ null | 3,635,660 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| V0 | Hợp lệ | nội bảng | (bổ sung) ô số phải ép được số | 908,915 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V1 | Hợp lệ | nội bảng | user_id, business_id khớp chuỗi 22 ký tự | 1,817,830 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V4 | Hợp lệ | nội bảng | compliment_count là số nguyên ≥ 0 | 908,915 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V6 | Hợp lệ | nội bảng | date đúng định dạng YYYY-MM-DD HH:MM:SS | 908,915 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| U2 | Duy nhất | nội bảng | tip không có khóa riêng nên bộ (user_id, business_id, date, text) không lặp | 908,915 | 67 | 0,999926 | Tốt | Dùng trực tiếp |
| ★ S1 | Nhất quán | liên bảng | business_id ∈ business; user_id ∈ user | 1,817,830 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| S2 | Nhất quán | liên bảng | tip.date ≥ user.yelping_since của chính người viết | 908,915 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ T1 | Kịp thời | nội bảng | tip.date ∈ [T_start; T_ref] | 908,915 | 0 | 1,000000 | Tốt | Dùng trực tiếp |

### user

| Mã | Khía cạnh | Phạm vi | Quy tắc | Ô xét | Vi phạm | Điểm | Xếp hạng | Xử lý |
|---|---|---|---|---:|---:|---:|---|---|
| ★ C6 | Đầy đủ | nội bảng | user_id, yelping_since, review_count, average_stars ≠ null | 7,951,588 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| C7 | Đầy đủ | nội bảng | tỷ lệ 'không có' của elite ('' ) và friends ('None' hoặc '[]') sau chuẩn hóa (chỉ báo cáo) | 3,975,794 | 2,775,250 | 0,301963 | Chỉ báo cáo | Chỉ báo cáo |
| V0 | Hợp lệ | nội bảng | (bổ sung) ô số phải ép được số | 33,794,249 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V1 | Hợp lệ | nội bảng | user_id khớp chuỗi 22 ký tự | 1,987,897 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V4 | Hợp lệ | nội bảng | review_count, useful, funny, cool, fans, compliment_* là số nguyên ≥ 0 | 31,806,352 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V6 | Hợp lệ | nội bảng | yelping_since đúng định dạng YYYY-MM-DD HH:MM:SS | 1,987,897 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ V7 | Hợp lệ | nội bảng | average_stars ∈ [1; 5] | 1,987,897 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| V9 | Hợp lệ | nội bảng | elite là '' hoặc danh sách năm 4 chữ số (bắt lỗi dạng '20,20') | 1,987,897 | 39,929 | 0,979914 | Chú ý | Ghi nhận, gắn cờ hoặc xử lý nhẹ |
| V11 | Hợp lệ | nội bảng | friends là danh sách rỗng ('None', '[]') hoặc mọi phần tử là user_id đúng định dạng 22 ký tự (thêm max_rows để lấy mẫu nếu RAM hạn chế) | 1,987,897 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| ★ U1 | Duy nhất | nội bảng | user_id không trùng (Tốt = 1) | 1,987,897 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| S3 | Nhất quán | liên bảng | user.review_count ≥ số review của user đó có trong file review (file là tập con) | 1,987,897 | 17,665 | 0,991114 | Tốt | Dùng trực tiếp |
| S4 | Nhất quán | nội bảng | elite: mỗi năm ≥ năm của yelping_since và ≤ 2022 | 90,979 | 0 | 1,000000 | Tốt | Dùng trực tiếp |
| S8 | Nhất quán | liên bảng | average_stars lệch ≤ 0,5 so với trung bình review.stars của user trong file review | 1,987,897 | 742,635 | 0,626422 | Tệ | Phải sửa / điền / loại trước khi dùng |
| ★ T2 | Kịp thời | nội bảng | user.yelping_since ∈ [2004-07-01; T_ref] (cận dưới là thời điểm Yelp thành lập 07/2004, sớm hơn T_start của review; cần nhóm xác nhận) | 1,987,897 | 0 | 1,000000 | Tốt | Dùng trực tiếp |

## 3. Quy tắc cần xử lý

| Bảng | Mã | Khía cạnh | Vi phạm | Điểm | Xếp hạng | Giá trị vi phạm phổ biến |
|---|---|---|---:|---:|---|---|
| user | S8 | Nhất quán | 742,635 | 0,626422 | Tệ | average_stars: '3.0'×13481; '4.0'×10970; '3.67'×8970; '2.33'×4544; '3.5'×4093 |
| checkin | ★ U1 | Duy nhất | 3,543 | 0,999735 | Chú ý | — |
| review | ★ S1 | Nhất quán | 33 | 0,999998 | Tốt | user_id: 'lzpM_Vf2rKA4ivGtAIOH4w'×2; 'tquAg8GqbhN5k6Hkd23M0A'×1; '5iBVQ3OeK8lV4Z_4PXc1Xw'×1; 'u8cq-5zzD7dPSa3LR8rIMw'×1; '433BzxUeQAmRmK0g06UAfA'×1 |
| review | ★ V4 | Hợp lệ | 7 | 1,000000 | Tốt | useful: '-1'×4 | funny: '-1'×2 | cool: '-1'×1 |
| business | ★ V2 | Hợp lệ | 1 | 0,999997 | Tốt | longitude: '-73.2004570502'×1 |

## 4. Chỉ báo cáo (không xếp hạng)

- **business · C7** — tỷ lệ thiếu của address, hours, attributes (chỉ báo cáo): 42,094/451,038 ô → tỷ lệ đạt 0,9067.
- **business · S6** — review_count so với số review trong file (chỉ báo cáo, chưa xếp hạng; kèm tổng và tỷ lệ): 67,362/150,346 ô → tỷ lệ đạt 0,5520.
- **business · T4** — tỷ lệ POI is_open = 1 có ít nhất một review/tip/check-in trong 24 tháng trước T_ref (chỉ báo cáo): 14,045/119,698 ô → tỷ lệ đạt 0,8827.
- **user · C7** — tỷ lệ 'không có' của elite ('' ) và friends ('None' hoặc '[]') sau chuẩn hóa (chỉ báo cáo): 2,775,250/3,975,794 ô → tỷ lệ đạt 0,3020.
- **business · S6** — tổng giá trị / tổng tham chiếu: 0,9650 (6,745,508/6,990,280); Σ review_count (mỗi business_id một lần) so với Σ review_n_by_business; chênh 244,772.
- **checkin · C8** — độ phủ: 0,8775 (131,930/150,346); business_id khác nhau nằm trong business.business_id.

## 5. Khía cạnh không áp dụng và cảnh báo cấu hình

- **business · Kịp thời**: bảng không có thuộc tính thời gian (chỉ có T4 tham khảo)
- **business · Chính xác**: không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1); S7 là đối chiếu chéo, xếp ở Nhất quán
- **checkin · Chính xác**: không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1)
- **review · Chính xác**: không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1)
- **tip · Chính xác**: không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1)
- **user · Chính xác**: không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1); S8 là đối chiếu chéo, xếp ở Nhất quán
- ℹ **business**: cột không thuộc quy tắc Đầy đủ nào của báo cáo (chỉ có trong điểm đối chiếu Eq.2): categories_list
- ℹ **tip**: cột không thuộc quy tắc Đầy đủ nào của báo cáo (chỉ có trong điểm đối chiếu Eq.2): compliment_count
- ℹ **user**: cột không thuộc quy tắc Đầy đủ nào của báo cáo (chỉ có trong điểm đối chiếu Eq.2): useful, funny, cool, fans, compliment_hot, compliment_more, compliment_profile, compliment_cute, compliment_list, compliment_note, compliment_plain, compliment_cool, compliment_funny, compliment_writer, compliment_photos

## 6. Hồ sơ thời gian (thông tin)

| Bảng | Cột | Số mốc | Sớm nhất | Muộn nhất | Sau T_ref | Trước T_start |
|---|---|---:|---|---|---:|---:|
| checkin | checkin_time | 13,356,875 | 2009-12-30 02:53:27 | 2022-01-19 16:48:37 | 0 | 0 |
| review | date | 6,990,280 | 2005-02-16 03:23:22 | 2022-01-19 19:48:45 | 0 | 0 |
| tip | date | 908,915 | 2009-04-16 13:11:49 | 2022-01-19 20:38:55 | 0 | 0 |
| user | yelping_since | 1,987,897 | 2004-10-12 08:46:11 | 2022-01-19 17:15:47 | 0 | 0 |

## 7. Đối chiếu với TEMPO-DQ (không dùng xếp hạng)

Điểm Đầy đủ Eq.(2) trung bình cộng theo grain trên **mọi** cột, và điểm theo grain của các khía cạnh (Eq.1–4):

| Bảng | Đầy đủ Eq.(2) | Đầy đủ (grain) | Duy nhất (grain) | Nhất quán (grain) | Kịp thời (grain) | Hợp lệ (grain) | Chính xác (grain) |
|---|---:|---:|---:|---:|---:|---:|---:|
| business | 0,981211 | 0,999894 | 0,999548 | 0,994914 | N/A | 0,999999 | N/A |
| checkin | 1,000000 | 1,000000 | 0,999735 | 1,000000 | 1,000000 | 1,000000 | N/A |
| review | 1,000000 | 1,000000 | 0,999998 | 0,999992 | 1,000000 | 1,000000 | N/A |
| tip | 1,000000 | 1,000000 | 0,999926 | 1,000000 | 1,000000 | 1,000000 | N/A |
| user | 1,000000 | 1,000000 | 1,000000 | 0,811444 | 1,000000 | 0,999471 | N/A |

Mẫu ô lỗi: `violation_samples.csv`. Định nghĩa độ đo: `METRICS.md`. Danh mục quy tắc: `RULES.md`.
