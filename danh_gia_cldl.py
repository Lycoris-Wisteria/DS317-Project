"""Đánh giá chất lượng dữ liệu (CLDL) Yelp thô: MỘT FILE, một lệnh -> notebook báo cáo.

    python danh_gia_cldl.py --data-dir <thư mục chứa 5 file .parquet>

Bố cục file:  1. Cấu hình (quy tắc từng bảng, ngưỡng)   2. Hàm kiểm tra (mỗi ô -> True/False/N/A)
              3. Đo (đọc dữ liệu, chạy quy tắc, tính điểm)   4. Báo cáo (một notebook duy nhất)
              5. Tự kiểm code (dữ liệu giả tiêm lỗi)   6. Chạy
Định nghĩa độ đo xem README.md.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import yaml

__version__ = "4.0.0"



# =====================================================================================
# 1. CẤU HÌNH (YAML nhúng): quy tắc từng bảng, ngưỡng, mốc thời gian - sửa ở đây
# =====================================================================================

CONFIG_YAML = r'''
# =====================================================================================
# Cấu hình đo chất lượng dữ liệu Yelp - bám theo "Báo cáo đo lường CLDL" (Phần A, Phụ lục F)
# và TEMPO-DQ (lớp Conventional). Đây là nguồn duy nhất của quy tắc: thêm/bớt/sửa ở đây, không sửa code.
#
# Mã quy tắc lấy đúng theo báo cáo: C=Đầy đủ  V=Hợp lệ  U=Duy nhất  S=Nhất quán  T=Kịp thời.
#   level: star    = quy tắc cứng ★ (ngưỡng Tốt >= 0,999 / Tệ < 0,99; mọi vi phạm đều cần xử lý)
#          general = dùng ngưỡng chung của khía cạnh (Bảng A.1)
#          report  = chỉ báo cáo, không xếp hạng, không vào điểm khía cạnh
#   scope: nội bảng | liên bảng           from_report: false = quy tắc BỔ SUNG ngoài báo cáo
#   thresholds: ngưỡng riêng của quy tắc (ví dụ U1 "Tốt = 1", S7/S8 theo ngưỡng Chính xác)
# =====================================================================================
run:
  data_dir: "C:/Users/Yoga/OneDrive/Desktop/UIT code/ds317/archive"   # đổi bằng --data-dir khi chạy
  out_dir: "."     # thư mục chứa notebook báo cáo; đổi bằng --out
  n_sample: 20              # số ô lỗi mẫu lưu cho mỗi quy tắc

reference:
  T_ref: "2022-01-19"             # ngày Yelp xuất dữ liệu (snapshot) - cận trên của khung Kịp thời
  T_start: "2005-02-16"           # cận dưới của khung Kịp thời theo báo cáo (T1, T2); nguồn cần xác nhận
  datetime_format: "%Y-%m-%d %H:%M:%S"

# Bảng A.1 - ngưỡng chung. Tốt: score >= good | Chú ý: bad <= score < good | Tệ: score < bad
thresholds:
  star: {good: 0.999, bad: 0.99}
  aspect:
    Đầy đủ:    {good: 0.98, bad: 0.95}
    Hợp lệ:    {good: 0.99, bad: 0.95}
    Duy nhất:  {good: 0.99, bad: 0.95}
    Nhất quán: {good: 0.99, bad: 0.95}
    Chính xác: {good: 0.90, bad: 0.80}
    Kịp thời:  {good: 0.99, bad: 0.95}

tables:
  # ------------------------------------------------------------------------- BUSINESS
  business:
    file: business.parquet
    grain: một cơ sở kinh doanh (POI)
    keys: [business_id, name]
    not_applicable:
      Chính xác: "không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1); S7 là đối chiếu chéo, xếp ở Nhất quán"
      Kịp thời: "bảng không có thuộc tính thời gian (chỉ có T4 tham khảo)"
    rules:
      - {id: C1, aspect: Đầy đủ, level: star, scope: nội bảng, type: not_null, columns: [business_id, name, latitude, longitude, stars, review_count, is_open], desc: "business_id, name, latitude, longitude, stars, review_count, is_open ≠ null"}
      - {id: C2, aspect: Đầy đủ, level: general, scope: nội bảng, type: not_null, columns: [city, state, postal_code, categories], desc: "city, state, postal_code, categories ≠ null"}
      - {id: C7, aspect: Đầy đủ, level: report, scope: nội bảng, type: not_null, columns: [address, hours, attributes], desc: "tỷ lệ thiếu của address, hours, attributes (chỉ báo cáo)"}
      - {id: V0, aspect: Hợp lệ, level: general, scope: nội bảng, type: dtype, kind: numeric, columns: [latitude, longitude, stars, review_count, is_open], from_report: false, desc: "(bổ sung) ô số phải ép được số, nếu không V2-V5 sẽ bỏ qua ô đó"}
      - {id: V1, aspect: Hợp lệ, level: star, scope: nội bảng, type: regex, column: business_id, pattern: '[A-Za-z0-9_-]{22}', desc: "business_id khớp chuỗi 22 ký tự [A-Za-z0-9_-]"}
      - {id: V2, aspect: Hợp lệ, level: star, scope: nội bảng, type: range, columns: {latitude: {min: 27, max: 54}, longitude: {min: -121, max: -74}}, desc: "latitude ∈ [27; 54], longitude ∈ [-121; -74]"}
      - {id: V3, aspect: Hợp lệ, level: star, scope: nội bảng, type: enum, column: stars, values: [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5], desc: "stars ∈ {1; 1,5; …; 5}"}
      - {id: V4, aspect: Hợp lệ, level: star, scope: nội bảng, type: range, column: review_count, min: 0, integer: true, desc: "review_count là số nguyên ≥ 0"}
      - {id: V5, aspect: Hợp lệ, level: star, scope: nội bảng, type: enum, column: is_open, values: [0, 1], desc: "is_open ∈ {0, 1}"}
      - {id: V8, aspect: Hợp lệ, level: general, scope: nội bảng, type: regex, column: state, pattern: '[A-Z]{2}', desc: "state là chuỗi 2 ký tự [A-Z] (ngoại lệ được ghi nhận riêng ở cột top_values)"}
      - {id: V10, aspect: Hợp lệ, level: general, scope: nội bảng, type: hours_format, column: hours, null_tokens: ["None"], desc: "hours có dạng H:M-H:M; khung 0:0-0:0 chỉ gắn nhãn 'cần kiểm chứng' (n_flagged), không tính lỗi"}
      - {id: V12a, aspect: Hợp lệ, level: general, scope: nội bảng, type: str_type, column: postal_code, desc: "postal_code giữ kiểu chuỗi"}
      - {id: V12b, aspect: Hợp lệ, level: general, scope: nội bảng, type: json_object, column: attributes, null_tokens: ["None"], desc: "attributes parse được thành object"}
      - {id: U1, aspect: Duy nhất, level: star, scope: nội bảng, type: unique, keys: [business_id], thresholds: {good: 1.0}, desc: "business_id không trùng (Tốt = 1)"}
      - {id: U3, aspect: Duy nhất, level: general, scope: nội bảng, type: unique, keys: [name, address, postal_code], desc: "bộ (name, address, postal_code) không lặp; name trùng riêng lẻ không tính lỗi"}
      - {id: S5a, aspect: Nhất quán, level: general, scope: nội bảng, type: city_spelling, column: city, desc: "city chỉ có một cách viết chuẩn sau chuẩn hóa (trim, lower, bỏ dấu)"}
      - {id: S5b, aspect: Nhất quán, level: general, scope: nội bảng, type: city_state, column: city, state: state, min_total: 20, share_min: 0.01, desc: "city thuộc đúng state (cặp city–state không hiếm; city >= 20 dòng, cặp chiếm >= 1%)"}
      - {id: S6, aspect: Nhất quán, level: report, scope: liên bảng, type: ref_compare, column: review_count, key: business_id, ref: review_n_by_business, fill_missing_ref: 0, tol_abs: 0, tol_rel: 0, aggregate: true, desc: "review_count so với số review trong file (chỉ báo cáo, chưa xếp hạng; kèm tổng và tỷ lệ)"}
      - {id: S7, aspect: Nhất quán, level: general, scope: liên bảng, type: ref_compare, column: stars, key: business_id, ref: review_mean_by_business, tol_abs: 0.5, thresholds: {good: 0.90, bad: 0.80}, desc: "stars lệch ≤ 0,5 so với trung bình review.stars của POI trong file review"}
      - {id: T4, aspect: Kịp thời, level: report, scope: liên bảng, type: activity_rate, column: is_open, key: business_id, months: 24, desc: "tỷ lệ POI is_open = 1 có ít nhất một review/tip/check-in trong 24 tháng trước T_ref (chỉ báo cáo)"}

  # ------------------------------------------------------------------------- CHECKIN (một dòng = một sự kiện check-in)
  # Nếu dữ liệu là dạng danh sách (mỗi business một dòng, cột date chứa nhiều mốc): đổi checkin_time -> date,
  # thêm `delimiter: ","` vào V6 và T3, và đổi khóa U1 thành [business_id].
  checkin:
    file: checkin_events.parquet
    grain: một sự kiện check-in (business_id, checkin_time)
    keys: [business_id, checkin_time]
    time_columns: [checkin_time]
    not_applicable:
      Chính xác: "không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1)"
    rules:
      - {id: C5, aspect: Đầy đủ, level: star, scope: nội bảng, type: not_null, columns: [business_id, checkin_time], desc: "business_id ≠ null, mốc check-in không rỗng"}
      - {id: C8, aspect: Đầy đủ, level: report, scope: liên bảng, type: coverage, column: business_id, ref: business.business_id, desc: "độ phủ checkin/business (chỉ báo cáo)"}
      - {id: V1, aspect: Hợp lệ, level: star, scope: nội bảng, type: regex, column: business_id, pattern: '[A-Za-z0-9_-]{22}', desc: "business_id khớp chuỗi 22 ký tự"}
      - {id: V6, aspect: Hợp lệ, level: star, scope: nội bảng, type: dtype, kind: datetime, column: checkin_time, desc: "mốc check-in đúng định dạng YYYY-MM-DD HH:MM:SS"}
      - {id: U1, aspect: Duy nhất, level: star, scope: nội bảng, type: unique, keys: [business_id, checkin_time], thresholds: {good: 1.0}, desc: "cặp (business_id, checkin_time) không trùng (Tốt = 1)"}
      - {id: S1, aspect: Nhất quán, level: star, scope: liên bảng, type: fk, column: business_id, ref: business.business_id, desc: "business_id ∈ business"}
      - {id: T3, aspect: Kịp thời, level: star, scope: nội bảng, type: in_window, column: checkin_time, use_start: false, desc: "mọi mốc check-in ≤ T_ref"}

  # ------------------------------------------------------------------------- REVIEW
  review:
    file: review.parquet
    grain: một review
    keys: [review_id, business_id]
    heavy_columns: [text]               # chỉ tính Đầy đủ theo batch, không nạp vào RAM
    time_columns: [date]
    not_applicable:
      Chính xác: "không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1)"
    rules:
      - {id: C3, aspect: Đầy đủ, level: star, scope: nội bảng, type: not_null, columns: [review_id, user_id, business_id, stars, useful, funny, cool, text, date], desc: "cả 9 trường ≠ null, text dài ≥ 1"}
      - {id: V0, aspect: Hợp lệ, level: general, scope: nội bảng, type: dtype, kind: numeric, columns: [stars, useful, funny, cool], from_report: false, desc: "(bổ sung) ô số phải ép được số"}
      - {id: V1, aspect: Hợp lệ, level: star, scope: nội bảng, type: regex, columns: [review_id, user_id, business_id], pattern: '[A-Za-z0-9_-]{22}', desc: "review_id, user_id, business_id khớp chuỗi 22 ký tự"}
      - {id: V3, aspect: Hợp lệ, level: star, scope: nội bảng, type: enum, column: stars, values: [1, 2, 3, 4, 5], desc: "review.stars ∈ {1…5} (số nguyên)"}
      - {id: V4, aspect: Hợp lệ, level: star, scope: nội bảng, type: range, columns: [useful, funny, cool], min: 0, integer: true, desc: "useful, funny, cool là số nguyên ≥ 0"}
      - {id: V6, aspect: Hợp lệ, level: star, scope: nội bảng, type: dtype, kind: datetime, column: date, desc: "date đúng định dạng YYYY-MM-DD HH:MM:SS"}
      - {id: U1, aspect: Duy nhất, level: star, scope: nội bảng, type: unique, keys: [review_id], thresholds: {good: 1.0}, desc: "review_id không trùng (Tốt = 1)"}
      - {id: U4, aspect: Duy nhất, level: general, scope: nội bảng, type: unique, keys: [user_id, business_id, date], desc: "bộ (user_id, business_id, date) không lặp"}
      - {id: S1, aspect: Nhất quán, level: star, scope: liên bảng, type: fk, columns: {business_id: {ref: business.business_id}, user_id: {ref: user.user_id}}, desc: "business_id ∈ business; user_id ∈ user"}
      - {id: S2, aspect: Nhất quán, level: general, scope: liên bảng, type: date_ge_lookup, column: date, key: user_id, lookup: user.yelping_since, tolerance_days: 0, desc: "review.date ≥ user.yelping_since của chính người viết"}
      - {id: T1, aspect: Kịp thời, level: star, scope: nội bảng, type: in_window, column: date, desc: "review.date ∈ [T_start; T_ref]"}

  # ------------------------------------------------------------------------- TIP
  tip:
    file: tip.parquet
    grain: một tip
    keys: [user_id, business_id]
    time_columns: [date]
    not_applicable:
      Chính xác: "không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1)"
    rules:
      - {id: C4, aspect: Đầy đủ, level: star, scope: nội bảng, type: not_null, columns: [user_id, business_id, text, date], desc: "user_id, business_id, text, date ≠ null"}
      - {id: V0, aspect: Hợp lệ, level: general, scope: nội bảng, type: dtype, kind: numeric, column: compliment_count, from_report: false, desc: "(bổ sung) ô số phải ép được số"}
      - {id: V1, aspect: Hợp lệ, level: star, scope: nội bảng, type: regex, columns: [user_id, business_id], pattern: '[A-Za-z0-9_-]{22}', desc: "user_id, business_id khớp chuỗi 22 ký tự"}
      - {id: V4, aspect: Hợp lệ, level: star, scope: nội bảng, type: range, column: compliment_count, min: 0, integer: true, desc: "compliment_count là số nguyên ≥ 0"}
      - {id: V6, aspect: Hợp lệ, level: star, scope: nội bảng, type: dtype, kind: datetime, column: date, desc: "date đúng định dạng YYYY-MM-DD HH:MM:SS"}
      - {id: U2, aspect: Duy nhất, level: general, scope: nội bảng, type: unique, keys: [user_id, business_id, date, text], desc: "tip không có khóa riêng nên bộ (user_id, business_id, date, text) không lặp"}
      - {id: S1, aspect: Nhất quán, level: star, scope: liên bảng, type: fk, columns: {business_id: {ref: business.business_id}, user_id: {ref: user.user_id}}, desc: "business_id ∈ business; user_id ∈ user"}
      - {id: S2, aspect: Nhất quán, level: general, scope: liên bảng, type: date_ge_lookup, column: date, key: user_id, lookup: user.yelping_since, tolerance_days: 0, desc: "tip.date ≥ user.yelping_since của chính người viết"}
      - {id: T1, aspect: Kịp thời, level: star, scope: nội bảng, type: in_window, column: date, desc: "tip.date ∈ [T_start; T_ref]"}

  # ------------------------------------------------------------------------- USER
  user:
    file: user.parquet
    grain: một người dùng
    keys: [user_id, name]
    time_columns: [yelping_since]
    allow_empty_columns: [elite]        # chỉ dùng cho điểm đối chiếu Eq.2: elite = '' nghĩa là chưa từng Elite
    not_applicable:
      Chính xác: "không có nguồn tham chiếu độc lập tin cậy (báo cáo mục F.1); S8 là đối chiếu chéo, xếp ở Nhất quán"
    rules:
      - {id: C6, aspect: Đầy đủ, level: star, scope: nội bảng, type: not_null, columns: [user_id, yelping_since, review_count, average_stars], desc: "user_id, yelping_since, review_count, average_stars ≠ null"}
      - {id: C7, aspect: Đầy đủ, level: report, scope: nội bảng, type: not_null, columns: {elite: {}, friends: {missing_tokens: ["None", "[]"]}}, desc: "tỷ lệ 'không có' của elite ('' ) và friends ('None' hoặc '[]') sau chuẩn hóa (chỉ báo cáo)"}
      - {id: V0, aspect: Hợp lệ, level: general, scope: nội bảng, type: dtype, kind: numeric, columns: [review_count, useful, funny, cool, fans, average_stars], columns_prefix: compliment_, from_report: false, desc: "(bổ sung) ô số phải ép được số"}
      - {id: V1, aspect: Hợp lệ, level: star, scope: nội bảng, type: regex, column: user_id, pattern: '[A-Za-z0-9_-]{22}', desc: "user_id khớp chuỗi 22 ký tự"}
      - {id: V4, aspect: Hợp lệ, level: star, scope: nội bảng, type: range, columns: [review_count, useful, funny, cool, fans], columns_prefix: compliment_, min: 0, integer: true, desc: "review_count, useful, funny, cool, fans, compliment_* là số nguyên ≥ 0"}
      - {id: V6, aspect: Hợp lệ, level: star, scope: nội bảng, type: dtype, kind: datetime, column: yelping_since, desc: "yelping_since đúng định dạng YYYY-MM-DD HH:MM:SS"}
      - {id: V7, aspect: Hợp lệ, level: star, scope: nội bảng, type: range, column: average_stars, min: 1, max: 5, desc: "average_stars ∈ [1; 5]"}
      - {id: V9, aspect: Hợp lệ, level: general, scope: nội bảng, type: regex, column: elite, allow_empty: true, pattern: '\s*(\d{4}(\s*,\s*\d{4})*)?\s*', desc: "elite là '' hoặc danh sách năm 4 chữ số (bắt lỗi dạng '20,20')"}
      - {id: V11, aspect: Hợp lệ, level: general, scope: nội bảng, type: id_list, column: friends, null_tokens: ["None"], desc: "friends là danh sách rỗng ('None', '[]') hoặc mọi phần tử là user_id đúng định dạng 22 ký tự (thêm max_rows để lấy mẫu nếu RAM hạn chế)"}
      - {id: U1, aspect: Duy nhất, level: star, scope: nội bảng, type: unique, keys: [user_id], thresholds: {good: 1.0}, desc: "user_id không trùng (Tốt = 1)"}
      - {id: S3, aspect: Nhất quán, level: general, scope: liên bảng, type: ref_compare, column: review_count, key: user_id, ref: review_n_by_user, fill_missing_ref: 0, mode: at_least, tol_abs: 0, tol_rel: 0, desc: "user.review_count ≥ số review của user đó có trong file review (file là tập con)"}
      - {id: S4, aspect: Nhất quán, level: general, scope: nội bảng, type: elite_years, column: elite, other: yelping_since, desc: "elite: mỗi năm ≥ năm của yelping_since và ≤ 2022"}
      - {id: S8, aspect: Nhất quán, level: general, scope: liên bảng, type: ref_compare, column: average_stars, key: user_id, ref: review_mean_by_user, tol_abs: 0.5, thresholds: {good: 0.90, bad: 0.80}, desc: "average_stars lệch ≤ 0,5 so với trung bình review.stars của user trong file review"}
      - {id: T2, aspect: Kịp thời, level: star, scope: nội bảng, type: in_window, column: yelping_since, t_start: "2004-07-01", desc: "user.yelping_since ∈ [2004-07-01; T_ref] (cận dưới là thời điểm Yelp thành lập 07/2004, sớm hơn T_start của review; cần nhóm xác nhận)"}
'''


# =====================================================================================
# 2. HÀM KIỂM TRA
# =====================================================================================

# ============================================================================= HÀM TIỆN ÍCH
# Mọi hàm trả về mảng numpy theo vị trí dòng (không theo nhãn index).

def present(s: pd.Series, allow_empty: bool = False) -> np.ndarray:
    """Mặt nạ 'có giá trị'. Thiếu = NaN/None; thêm chuỗi rỗng/khoảng trắng nếu allow_empty=False."""
    p = s.notna().to_numpy(dtype=bool).copy()
    if not allow_empty and (s.dtype == object or pd.api.types.is_string_dtype(s)):
        try:
            blank = s.str.strip().eq("").to_numpy(dtype=bool, na_value=False)
        except (AttributeError, TypeError):
            blank = s.map(lambda x: isinstance(x, str) and x.strip() == "").to_numpy(dtype=bool)
        p &= ~blank
    return p


def to_num(s: pd.Series) -> pd.Series:
    """Ép số; giá trị không ép được -> NaN (để luật Data Type bắt riêng, không nhầm với thiếu)."""
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        return s
    return pd.to_numeric(s, errors="coerce")


def as_datetime(s: pd.Series, fmt: str | None) -> pd.Series:
    """Ép thời gian; không parse được -> NaT. Trả về datetime64 không múi giờ."""
    if pd.api.types.is_datetime64_any_dtype(s):
        d = s
    else:
        d = pd.to_datetime(s, format=fmt, errors="coerce")
    if getattr(d.dt, "tz", None) is not None:
        d = d.dt.tz_convert(None)
    return d


def year_lists(s: pd.Series, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Tách chuỗi 'YYYY,YYYY,...' -> (vị trí dòng, năm) cho các dòng trong mask. Token không phải 4 chữ số bị bỏ."""
    pos = np.flatnonzero(mask)
    if len(pos) == 0:
        return pos, np.array([], dtype=np.int64)
    sub = pd.Series(s.to_numpy()[pos].astype(str), index=pos)
    tok = sub.str.split(",").explode().str.strip()
    ok = tok.str.fullmatch(r"\d{4}").fillna(False).to_numpy(dtype=bool)
    tok = tok[ok]
    return tok.index.to_numpy(), tok.astype(np.int64).to_numpy()


def row_any(n: int, row_idx: np.ndarray, flag: np.ndarray) -> np.ndarray:
    """Gộp cờ mức phần tử lên mức dòng: dòng có ít nhất một phần tử cờ True."""
    out = np.zeros(n, dtype=bool)
    if len(row_idx):
        out[row_idx[flag]] = True
    return out


def row_has(n: int, row_idx: np.ndarray) -> np.ndarray:
    out = np.zeros(n, dtype=bool)
    if len(row_idx):
        out[row_idx] = True
    return out


def short(x, max_len: int = 80) -> str:
    t = repr(x) if isinstance(x, str) else str(x)
    t = t.replace("\n", " ")
    return t if len(t) <= max_len else t[: max_len - 3] + "..."


def norm_text(s: pd.Series) -> pd.Series:
    """Chuẩn hóa để so sánh cách viết: trim, lower, bỏ dấu (NFKD), bỏ ký tự không phải chữ-số, gộp khoảng trắng."""
    t = s.astype("string").str.normalize("NFKD")
    t = t.str.replace(r"[̀-ͯ]", "", regex=True).str.lower()
    t = t.str.replace(r"[^0-9a-z\s]", " ", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()
    return t


def parse_object(x, null_tokens=("None",)):
    """Parse một ô thành dict. Trả (ok, obj). ok=None nghĩa là ô rỗng/null (N/A)."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None, None
    if isinstance(x, dict):
        return True, x
    if isinstance(x, str):
        t = x.strip()
        if t == "" or t in null_tokens:
            return None, None
        for loader in (json.loads, ast.literal_eval):
            try:
                v = loader(t)
                return (True, v) if isinstance(v, dict) else (False, None)
            except Exception:
                continue
        return False, None
    try:                                  # struct/map của pyarrow đã về dict-like
        return True, dict(x)
    except Exception:
        return False, None


TRUE, FALSE, NA = 1, 0, -1
SPECS: dict[str, dict] = {}


def rule_type(name, *, aspects, true, false, na, why):
    def deco(fn):
        SPECS[name] = dict(fn=fn, aspects=tuple(aspects), true=true, false=false, na=na, why=why)
        return fn
    return deco


@dataclass
class RuleCtx:
    df: pd.DataFrame
    p: dict
    ctx: object
    ref: dict
    t_start: pd.Timestamp
    t_end: pd.Timestamp          # T_ref + 1 ngày (mốc loại trừ)
    heavy: dict = field(default_factory=dict)
    n: int = 0

    def __post_init__(self):
        self.n = len(self.df)

    @property
    def col(self) -> str:
        return self.p["column"]

    @property
    def fmt(self):
        return self.ref.get("datetime_format")


@dataclass
class RuleOut:
    cells: dict                                   # nhãn ô -> mảng int8 {1, 0, -1}
    flagged: int = 0                              # số ô "cần kiểm chứng" (không tính là lỗi)
    metrics: list = field(default_factory=list)   # số liệu tham khảo (dict)
    extra: dict = field(default_factory=dict)     # nhãn ô -> (tên tham chiếu, mảng giá trị tham chiếu)


def tri(applicable, violated) -> np.ndarray:
    applicable = np.asarray(applicable, dtype=bool)
    violated = np.asarray(violated, dtype=bool)
    out = np.full(len(applicable), NA, dtype=np.int8)
    out[applicable] = TRUE
    out[applicable & violated] = FALSE
    return out


def _one(label, applicable, violated, **kw) -> RuleOut:
    return RuleOut(cells={label: tri(applicable, violated)}, **kw)


# ============================================================================= ĐẦY ĐỦ
@rule_type("not_null", aspects=["Đầy đủ"],
           true="ô có giá trị: khác NaN/None, không rỗng/khoảng trắng và không thuộc `missing_tokens`",
           false="ô thiếu (NaN/None, chuỗi rỗng/khoảng trắng, hoặc đúng bằng một `missing_tokens`)",
           na="không có: mọi ô của cột đều được xét",
           why="'Thiếu' là NaN/None (paper Eq.2). Chuỗi rỗng cũng là thiếu vì báo cáo C3 yêu cầu text dài >= 1. "
               "`missing_tokens` chuẩn hóa giá trị mang nghĩa 'không có' (elite = '' ; friends = 'None') trước khi tính tỷ lệ thiếu (ghi chú C7).")
def is_not_missing(c: RuleCtx) -> RuleOut:
    col = c.col
    if col in c.heavy:
        pres = c.heavy[col].copy()
    else:
        s = c.df[col]
        pres = present(s, False)
        tokens = c.p.get("missing_tokens")
        if tokens:
            pos = np.flatnonzero(pres)
            hit = s.iloc[pos].astype(str).str.strip().isin([str(t) for t in tokens]).to_numpy(dtype=bool)
            pres[pos[hit]] = False
    return _one(col, np.ones(c.n, dtype=bool), ~pres)


@rule_type("coverage", aspects=["Đầy đủ"],
           true="(không tạo ô; chỉ báo cáo)", false="(không tạo ô; chỉ báo cáo)", na="(không tạo ô)",
           why="Độ phủ = số business_id khác nhau của bảng này nằm trong business / tổng số business. Cho biết bảng này không phủ hết POI.")
def coverage(c: RuleCtx) -> RuleOut:
    ref = c.ctx.index(c.p["ref"])
    have = pd.Index(c.df[c.col].dropna().unique())
    n = int(have.isin(ref).sum())
    return RuleOut(cells={}, metrics=[{"metric": "độ phủ", "value": n / len(ref), "numerator": n, "denominator": len(ref),
                                       "note": f"{c.col} khác nhau nằm trong {c.p['ref']}"}])


# ============================================================================= HỢP LỆ
@rule_type("dtype", aspects=["Hợp lệ"],
           true="ô có giá trị ép được sang kiểu `kind` (numeric: ép được số; datetime: đúng định dạng thời gian). Với `delimiter`: MỌI phần tử đều ép được",
           false="ô có giá trị nhưng không ép được (vd. 'n/a', '20,20' trong cột ngày)",
           na="ô thiếu (đã tính ở Đầy đủ)",
           why="Data Type của paper. Giá trị sai kiểu chỉ bị đếm ở đây, không bị biến thành NaN rồi đếm ở Đầy đủ.")
def is_type_ok(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    pres = present(s, False)
    kind = c.p["kind"]
    if kind == "numeric":
        ok = (np.ones(c.n, bool) if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
              else to_num(s).notna().to_numpy(dtype=bool))
        return _one(c.col, pres, pres & ~ok)
    if kind == "datetime":
        delim = c.p.get("delimiter")
        if not delim:
            return _one(c.col, pres, pres & ~as_datetime(s, c.fmt).notna().to_numpy(dtype=bool))
        pos = np.flatnonzero(pres)
        tok = pd.Series(s.to_numpy()[pos].astype(str), index=pos).str.split(delim).explode().str.strip()
        bad = ~as_datetime(tok, c.fmt).notna().to_numpy(dtype=bool)
        return _one(c.col, pres, row_any(c.n, tok.index.to_numpy(), bad))
    raise ValueError(f"dtype.kind không hỗ trợ: {kind}")


@rule_type("range", aspects=["Hợp lệ"],
           true="ô là số trong [min; max] (đóng hai đầu); nếu integer=true thì phải là số nguyên",
           false="ô là số nhưng ngoài [min; max], hoặc không nguyên khi integer=true",
           na="ô thiếu hoặc không ép được số (sai kiểu đã bị bắt ở `dtype`)",
           why="Domain Range của paper. Ngưỡng cụ thể lấy từ từ điển dữ liệu của nhóm (báo cáo CLDL).")
def is_in_range(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    v = to_num(s)
    x = v.to_numpy(dtype=float, na_value=np.nan)
    appl = ~np.isnan(x) & present(s, False)
    bad = np.zeros(c.n, dtype=bool)
    with np.errstate(invalid="ignore"):
        if c.p.get("min") is not None:
            bad |= x < c.p["min"]
        if c.p.get("max") is not None:
            bad |= x > c.p["max"]
        if c.p.get("integer"):
            bad |= (x % 1) != 0
    return _one(c.col, appl, bad)


@rule_type("enum", aspects=["Hợp lệ"],
           true="ô là số thuộc tập `values`", false="ô là số nhưng không thuộc tập `values`",
           na="ô thiếu hoặc không ép được số",
           why="Domain Range dạng tập rời rạc (stars nửa sao; stars review nguyên; is_open nhị phân).")
def is_in_set(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    v = to_num(s)
    appl = v.notna().to_numpy(dtype=bool) & present(s, False)
    return _one(c.col, appl, ~v.isin(c.p["values"]).to_numpy(dtype=bool))


@rule_type("regex", aspects=["Hợp lệ"],
           true="toàn bộ chuỗi khớp `pattern` (fullmatch)", false="ô có giá trị nhưng không khớp pattern",
           na="ô thiếu (với allow_empty=true thì chuỗi rỗng vẫn được xét)",
           why="Kiểm định dạng. Id Yelp là chuỗi 22 ký tự [A-Za-z0-9_-]; state là 2 chữ in hoa; elite là danh sách năm 4 chữ số; friends là 'None' hoặc danh sách id.")
def is_format_ok(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    appl = present(s, bool(c.p.get("allow_empty", False)))
    pos = np.flatnonzero(appl)
    if c.p.get("max_rows") and len(pos) > int(c.p["max_rows"]):      # tùy chọn lấy mẫu cho cột rất nặng
        keep = np.random.default_rng(42).choice(pos, size=int(c.p["max_rows"]), replace=False)
        appl = np.zeros(c.n, dtype=bool)
        appl[keep] = True
        pos = np.flatnonzero(appl)
    viol = np.zeros(c.n, dtype=bool)
    if len(pos):
        ok = s.iloc[pos].astype(str).str.fullmatch(c.p["pattern"]).to_numpy(dtype=bool)
        viol[pos] = ~ok
    return _one(c.col, appl, viol)


@rule_type("id_list", aspects=["Hợp lệ"],
           true="ô là danh sách rỗng ('None', '', '[]') HOẶC mọi phần tử khớp `id_pattern`. Chấp nhận cả chuỗi 'a, b', chuỗi dạng danh sách \"['a', 'b']\" và list/mảng thật",
           false="ô có ít nhất một phần tử không khớp `id_pattern`, hoặc không đọc được thành danh sách",
           na="ô thiếu (NaN/None)",
           why="friends là danh sách user_id nên mỗi phần tử phải đúng định dạng id 22 ký tự. Dữ liệu thực tế lưu danh sách dạng chuỗi \"['id1', 'id2']\", "
               "nên hàm bóc ngoặc và dấu nháy trước khi kiểm từng phần tử, thay vì giả định một dạng phân cách cố định.")
def is_id_list_ok(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    idp = c.p.get("id_pattern", r"[A-Za-z0-9_-]{22}")
    nulls = {str(t) for t in c.p.get("null_tokens", ["None"])}
    appl = s.notna().to_numpy(dtype=bool).copy()
    pos = np.flatnonzero(appl)
    if c.p.get("max_rows") and len(pos) > int(c.p["max_rows"]):       # tùy chọn lấy mẫu cho cột rất nặng
        keep = np.random.default_rng(42).choice(pos, size=int(c.p["max_rows"]), replace=False)
        appl = np.zeros(c.n, dtype=bool)
        appl[keep] = True
        pos = np.flatnonzero(appl)
    viol = np.zeros(c.n, dtype=bool)
    if not len(pos):
        return _one(c.col, appl, viol)
    vals = s.to_numpy()[pos]
    is_str = np.fromiter((isinstance(v, str) for v in vals), dtype=bool, count=len(vals))
    q = r"""['"]?"""
    whole = re.compile(rf"\s*\[?\s*(?:{q}{idp}{q}(?:[\s,]+{q}{idp}{q})*)?\s*,?\s*\]?\s*")
    one = re.compile(idp)
    if is_str.any():
        ser = pd.Series(vals[is_str]).str.strip()
        ok = (ser.isin(nulls) | ser.str.fullmatch(whole)).to_numpy(dtype=bool)
        viol[pos[is_str]] = ~ok
    for j in np.flatnonzero(~is_str):                                   # list / mảng thật (hiếm): kiểm từng phần tử
        v = vals[j]
        try:
            viol[pos[j]] = not all(one.fullmatch(str(x).strip()) for x in v)
        except TypeError:
            viol[pos[j]] = True
    return _one(c.col, appl, viol)


@rule_type("str_type", aspects=["Hợp lệ"],
           true="giá trị là chuỗi (str)", false="giá trị có mặt nhưng không phải chuỗi (vd. mã bưu chính bị đọc thành số, mất số 0 đầu)",
           na="ô thiếu",
           why="postal_code phải giữ kiểu chuỗi vì có số 0 đầu và mã Canada có chữ.")
def is_string_type(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    appl = s.notna().to_numpy(dtype=bool)
    if pd.api.types.is_string_dtype(s) and s.dtype != object:
        return _one(c.col, appl, np.zeros(c.n, dtype=bool))
    is_str = s.map(lambda x: isinstance(x, str)).to_numpy(dtype=bool)
    return _one(c.col, appl, ~is_str)


@rule_type("json_object", aspects=["Hợp lệ"],
           true="giá trị là dict hoặc chuỗi JSON/dict parse được thành object", false="giá trị có mặt nhưng không parse được thành object",
           na="ô thiếu hoặc thuộc `null_tokens` (mặc định 'None')",
           why="Cột attributes lồng nhau phải parse được thì mới dùng làm đặc trưng.")
def is_object_ok(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    toks = tuple(c.p.get("null_tokens", ["None"]))
    res = [parse_object(x, toks)[0] for x in s.to_numpy()]
    appl = np.array([r is not None for r in res], dtype=bool)
    ok = np.array([bool(r) for r in res], dtype=bool)
    return _one(c.col, appl, appl & ~ok)


@rule_type("hours_format", aspects=["Hợp lệ"],
           true="mọi giá trị trong hours có dạng H:M-H:M (vd. '10:0-21:0')",
           false="có ít nhất một giá trị sai dạng, hoặc hours không parse được",
           na="ô thiếu hoặc thuộc `null_tokens`",
           why="Khung '0:0-0:0' KHÔNG tính là lỗi mà được gắn nhãn 'cần kiểm chứng' (đếm riêng ở n_flagged).")
def is_hours_ok(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    toks = tuple(c.p.get("null_tokens", ["None"]))
    pat = re.compile(r"\d{1,2}:\d{1,2}-\d{1,2}:\d{1,2}")
    appl, viol, flagged = np.zeros(c.n, bool), np.zeros(c.n, bool), 0
    for i, x in enumerate(s.to_numpy()):
        ok, obj = parse_object(x, toks)
        if ok is None:
            continue
        appl[i] = True
        if not ok:
            viol[i] = True
            continue
        vals = [str(v).strip() for v in obj.values()]
        if any(pat.fullmatch(v) is None for v in vals):
            viol[i] = True
        elif any(v == "0:0-0:0" for v in vals):
            flagged += 1
    return _one(c.col, appl, viol, flagged=flagged)


# ============================================================================= DUY NHẤT
@rule_type("unique", aspects=["Duy nhất"],
           true="khóa là bản xuất hiện ĐẦU TIÊN hoặc xuất hiện đúng một lần",
           false="khóa là bản thứ 2 trở đi của một khóa đã xuất hiện (bản DƯ THỪA)",
           na="một thành phần của khóa bị thiếu (không thể kết luận trùng)",
           why="Đếm số bản dư thừa = số bản ghi sẽ bị loại khi khử trùng, nên 3 review bị nhân đôi cho 3 lỗi (không phải 6). "
               "Khóa ghép được coi là MỘT ô tổ hợp nên không bị nhân đôi theo số cột khóa.")
def is_unique_key(c: RuleCtx) -> RuleOut:
    keys = list(c.p["keys"])
    label = keys[0] if len(keys) == 1 else "(" + ", ".join(keys) + ")"
    appl = np.ones(c.n, dtype=bool)
    for k in keys:
        appl &= present(c.df[k], False)
    dup = np.zeros(c.n, dtype=bool)
    pos = np.flatnonzero(appl)
    if len(pos):
        dup[pos] = c.df.iloc[pos].duplicated(subset=keys, keep="first").to_numpy(dtype=bool)
    return _one(label, appl, dup)


# ============================================================================= NHẤT QUÁN
@rule_type("fk", aspects=["Nhất quán"],
           true="giá trị có trong khóa của bảng cha", false="giá trị có mặt nhưng KHÔNG có trong bảng cha (mồ côi)",
           na="ô thiếu",
           why="Toàn vẹn khóa ngoại: dòng mồ côi không nối được vào đồ thị user-POI.")
def is_in_reference(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    return _one(c.col, present(s, False), ~s.isin(c.ctx.index(c.p["ref"])).to_numpy(dtype=bool))


@rule_type("date_ge_lookup", aspects=["Nhất quán"],
           true="mốc thời gian của ô >= giá trị tra cứu theo khóa (vd. review.date >= yelping_since của chính người viết)",
           false="mốc của ô sớm hơn giá trị tra cứu", na="ô thiếu/không parse được, hoặc không tra được giá trị (user không tồn tại)",
           why="Người dùng không thể viết review/tip trước khi đăng ký. Lỗi gắn vào ô date của dòng con (review/tip); yelping_since chỉ là tham chiếu.")
def is_not_before_lookup(c: RuleCtx) -> RuleOut:
    d = as_datetime(c.df[c.col], c.fmt)
    r = pd.to_datetime(c.df[c.p["key"]].map(c.ctx.get(c.p["lookup"])))
    tol = pd.Timedelta(days=float(c.p.get("tolerance_days", 0)))
    appl = (d.notna() & r.notna()).to_numpy(dtype=bool)
    return _one(c.col, appl, (d < (r - tol)).to_numpy(dtype=bool), extra={c.col: (c.p["lookup"], r.to_numpy())})


@rule_type("ref_compare", aspects=["Nhất quán", "Chính xác"],
           true="|giá trị - tham chiếu| <= max(tol_abs, tol_rel·|tham chiếu|); với mode='at_least': giá trị >= tham chiếu - dung sai",
           false="lệch quá dung sai", na="ô thiếu, không có tham chiếu (trừ khi có fill_missing_ref), hoặc tham chiếu dựa trên < min_n dòng",
           why="Đối chiếu chéo với số liệu tính lại từ chính bộ dữ liệu (số review, trung bình sao). at_least dùng khi file review là tập con nên review_count chỉ có thể >= số quan sát.")
def is_close_to_reference(c: RuleCtx) -> RuleOut:
    p = c.p
    a = to_num(c.df[c.col]).to_numpy(dtype=float, na_value=np.nan)
    keys = c.df[p["key"]]
    r = keys.map(c.ctx.get(p["ref"])).to_numpy(dtype=float, na_value=np.nan)
    if p.get("fill_missing_ref") is not None:
        r = np.where(np.isnan(r), float(p["fill_missing_ref"]), r)
    appl = ~np.isnan(a) & ~np.isnan(r)
    if p.get("n_ref"):
        n = keys.map(c.ctx.get(p["n_ref"])).to_numpy(dtype=float, na_value=0.0)
        appl &= np.nan_to_num(n, nan=0.0) >= int(p.get("min_n", 1))
    tol = np.maximum(float(p.get("tol_abs", 0.0)), float(p.get("tol_rel", 0.0)) * np.abs(np.nan_to_num(r)))
    diff = a - r
    with np.errstate(invalid="ignore"):
        bad = (diff < -tol) if p.get("mode", "two_sided") == "at_least" else (np.abs(diff) > tol)
    out = _one(c.col, appl, np.nan_to_num(bad, nan=False).astype(bool), extra={c.col: (p["ref"], r)})
    if p.get("aggregate"):          # S6: so tổng (mỗi khóa tính một lần)
        first = ~keys.duplicated(keep="first").to_numpy(dtype=bool)
        sum_a = float(np.nansum(np.where(first, a, np.nan)))
        sum_r = float(c.ctx.get(p["ref"]).sum())
        out.metrics.append({"metric": "tổng giá trị / tổng tham chiếu", "value": sum_a / sum_r if sum_r else np.nan,
                            "numerator": sum_a, "denominator": sum_r,
                            "note": f"Σ {c.col} (mỗi {p['key']} một lần) so với Σ {p['ref']}; chênh {sum_r - sum_a:,.0f}"})
    return out


@rule_type("elite_years", aspects=["Nhất quán"],
           true="mọi năm trong danh sách >= năm của yelping_since VÀ <= max_year (mặc định: năm của T_ref)",
           false="có ít nhất một năm sớm hơn năm đăng ký hoặc muộn hơn max_year",
           na="ô không có năm hợp lệ nào (rỗng hoặc sai định dạng - đã bắt ở V9); cận dưới chỉ xét khi yelping_since parse được",
           why="Một người không thể là Elite trước khi đăng ký hay sau thời điểm xuất dữ liệu.")
def is_elite_consistent(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    rows, years = year_lists(s, present(s, True))
    ys = as_datetime(c.df[c.p["other"]], c.fmt).dt.year.to_numpy(dtype=float, na_value=np.nan)
    max_year = int(c.p.get("max_year") or (c.t_end - pd.Timedelta(days=1)).year)
    bad = (years > max_year) | (years < ys[rows])
    appl = np.zeros(c.n, dtype=bool)
    appl[rows] = True
    return _one(c.col, appl, row_any(c.n, rows, bad))


def _norm_state(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.upper()


@rule_type("city_spelling", aspects=["Nhất quán"],
           true="cách viết của city trùng cách viết phổ biến nhất trong nhóm các cách viết cùng dạng chuẩn hóa (trim, lower, bỏ dấu, bỏ ký tự đặc biệt)",
           false="city là một cách viết KHÁC của cùng một thành phố (vd. 'phoenix ', 'PHOENIX')", na="ô thiếu",
           why="Cùng một thành phố chỉ nên có một cách viết để nhóm/join theo thành phố không bị tách đôi.")
def is_city_spelling_ok(c: RuleCtx) -> RuleOut:
    raw = c.df[c.col].astype("string")
    pres = present(c.df[c.col], False)
    norm = norm_text(raw)
    t = pd.DataFrame({"n": norm[pres].to_numpy(), "r": raw[pres].to_numpy()})
    cnt = t.groupby(["n", "r"]).size().rename("c").reset_index()
    canon = cnt.sort_values(["n", "c", "r"], ascending=[True, False, True]).drop_duplicates("n").set_index("n")["r"]
    expected = norm.map(canon)
    viol = (raw != expected).fillna(False).to_numpy(dtype=bool)
    return _one(c.col, pres, viol)


@rule_type("city_state", aspects=["Nhất quán"],
           true="cặp (city chuẩn hóa, state) chiếm >= share_min của các dòng có city đó",
           false="cặp (city, state) hiếm: chiếm < share_min (vd. 'Phoenix' nhưng state = 'PA')",
           na="ô thiếu, hoặc city có < min_total dòng (không đủ căn cứ kết luận)",
           why="city phải thuộc đúng state. Vì có thành phố trùng tên ở nhiều bang nên chỉ coi là sai khi cặp (city, state) rất hiếm so với phần còn lại.")
def is_city_state_ok(c: RuleCtx) -> RuleOut:
    cities = c.df[c.col].astype("string")
    states = _norm_state(c.df[c.p["state"]])
    pres = present(c.df[c.col], False) & present(c.df[c.p["state"]], False)
    norm = norm_text(cities)
    t = pd.DataFrame({"n": norm.to_numpy(), "s": states.to_numpy()})[pres]
    pair = t.groupby(["n", "s"]).size().rename("pair")
    total = t.groupby("n").size().rename("total")
    j = pd.DataFrame({"n": norm.to_numpy(), "s": states.to_numpy()}).join(pair, on=["n", "s"]).join(total, on="n")
    appl = pres & (j["total"].fillna(0) >= int(c.p.get("min_total", 20))).to_numpy(dtype=bool)
    share = (j["pair"] / j["total"]).to_numpy(dtype=float)
    return _one(c.col, appl, np.nan_to_num(share, nan=1.0) < float(c.p.get("share_min", 0.01)))


# ============================================================================= KỊP THỜI
@rule_type("in_window", aspects=["Kịp thời"],
           true="mốc thời gian nằm trong khung snapshot [T_start; T_ref] (hết ngày T_ref). Với use_start=false chỉ xét cận trên; `t_start` (nếu có) thay cho T_start chung. Với `delimiter`: MỌI mốc đều trong khung",
           false="mốc ngoài khung (sớm hơn T_start hoặc muộn hơn ngày xuất dữ liệu)", na="ô thiếu hoặc không parse được (đã bắt ở `dtype`)",
           why="Dữ liệu cố định (snapshot) nên 'kịp thời' là 'đúng khung thời gian của snapshot', không phải 'cập nhật trong 12 tháng so với hôm nay' "
               "(lấy hôm nay làm mốc thì mọi bản ghi đều quá hạn). isOnTime của paper so với 'reference timestamp' = ngày xuất dữ liệu.")
def is_on_time(c: RuleCtx) -> RuleOut:
    lo = (pd.Timestamp(c.p["t_start"]) if c.p.get("t_start") else c.t_start) if c.p.get("use_start", True) else None
    s = c.df[c.col]
    delim = c.p.get("delimiter")
    if delim:
        pres = present(s, False)
        pos = np.flatnonzero(pres)
        tok = pd.Series(s.to_numpy()[pos].astype(str), index=pos).str.split(delim).explode().str.strip()
        d = as_datetime(tok, c.fmt)
        parsed = d.notna().to_numpy(dtype=bool)
        out_of = parsed & (((d >= c.t_end) | ((d < lo) if lo is not None else False)).to_numpy(dtype=bool))
        idx = tok.index.to_numpy()
        appl = np.zeros(c.n, dtype=bool)
        appl[idx[parsed]] = True
        return _one(c.col, appl, row_any(c.n, idx, out_of))
    d = as_datetime(s, c.fmt)
    bad = (d >= c.t_end)
    if lo is not None:
        bad = bad | (d < lo)
    return _one(c.col, d.notna().to_numpy(dtype=bool), bad.to_numpy(dtype=bool))


@rule_type("activity_rate", aspects=["Kịp thời"],
           true="POI đang mở (is_open = 1) có ít nhất một review/tip/check-in trong `months` tháng trước T_ref",
           false="POI đang mở nhưng không có hoạt động nào trong khung đó", na="POI đã đóng (is_open = 0) hoặc thiếu is_open",
           why="Thước đo độ 'còn hoạt động' của POI; chỉ tham khảo, dùng khi bài toán cần doanh nghiệp còn hoạt động.")
def is_recently_active(c: RuleCtx) -> RuleOut:
    last = c.df[c.p["key"]].map(c.ctx.get("last_activity_by_business"))
    start = c.t_end - pd.DateOffset(months=int(c.p.get("months", 24)))
    s = to_num(c.df[c.col])
    appl = (s == 1).to_numpy(dtype=bool)
    recent = (last >= start).fillna(False).to_numpy(dtype=bool)
    return _one(c.col, appl, ~recent)


# =====================================================================================
# 3. ĐO
# =====================================================================================

ASPECTS = ["Đầy đủ", "Duy nhất", "Nhất quán", "Kịp thời", "Hợp lệ", "Chính xác"]
GOOD, WARN, BAD, REPORT, NOTE = "Tốt", "Chú ý", "Tệ", "Chỉ báo cáo", "N/A"
ACTION = {GOOD: "Dùng trực tiếp", WARN: "Ghi nhận, gắn cờ hoặc xử lý nhẹ", BAD: "Phải sửa / điền / loại trước khi dùng"}


# ============================================================================= (1) ĐỌC DỮ LIỆU
# Giữ NGUYÊN kiểu thô (không ép sai kiểu thành NaN lúc đọc, để quy tắc Hợp lệ còn bắt được).
def table_path(cfg: dict, table: str) -> Path:
    return Path(cfg["run"]["data_dir"]) / cfg["tables"][table]["file"]


def table_columns(cfg: dict, table: str) -> list[str]:
    return pq.ParquetFile(table_path(cfg, table)).schema_arrow.names


def read_columns(cfg: dict, table: str, columns: list[str]) -> pd.DataFrame:
    cols = [c for c in columns if c in table_columns(cfg, table)]
    return pd.read_parquet(table_path(cfg, table), columns=cols)


def heavy_present(cfg: dict, table: str, col: str, allow_empty: bool = False) -> np.ndarray:
    """Mặt nạ 'có giá trị' của một cột nặng (vd. review.text), đọc theo batch để không tốn RAM."""
    out = []
    for batch in pq.ParquetFile(table_path(cfg, table)).iter_batches(columns=[col], batch_size=200_000):
        arr = batch.column(0)
        ok = pc.is_valid(arr)
        if not allow_empty and (pa.types.is_string(arr.type) or pa.types.is_large_string(arr.type)):
            nonblank = pc.invert(pc.equal(pc.utf8_trim_whitespace(arr), ""))
            ok = pc.and_(ok, pc.fill_null(nonblank, False))
        out.append(ok.to_numpy(zero_copy_only=False).astype(bool))
    return np.concatenate(out) if out else np.zeros(0, dtype=bool)


def load_table(cfg: dict, table: str) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Trả về (DataFrame các cột nhẹ, {cột nặng: mặt nạ 'có giá trị'})."""
    tc = cfg["tables"][table]
    heavy = list(tc.get("heavy_columns", []))
    all_cols = table_columns(cfg, table)
    df = pd.read_parquet(table_path(cfg, table), columns=[c for c in all_cols if c not in heavy])
    hp = {}
    for c in heavy:
        if c in all_cols:
            allow = bool(tc.get("columns", {}).get(c, {}).get("allow_empty", False))
            hp[c] = heavy_present(cfg, table, c, allow)
            if len(hp[c]) != len(df):
                raise ValueError(f"{table}.{c}: số dòng cột nặng {len(hp[c])} != {len(df)}")
    return df, hp


# ============================================================================= (2) THAM CHIẾU LIÊN BẢNG
# Dựng MỘT LẦN trước khi đo từng bảng (khóa ngoại, ngày đăng ký, số review thực...), nên thứ tự bảng không quan trọng.
@dataclass
class Context:
    key_index: dict = field(default_factory=dict)   # "business.business_id" -> pd.Index
    series: dict = field(default_factory=dict)      # tên tham chiếu -> pd.Series (index = khóa)
    notes: list = field(default_factory=list)

    def index(self, name: str) -> pd.Index:
        if name not in self.key_index:
            raise KeyError(f"chưa có tham chiếu khóa '{name}' (bảng nguồn không có file)")
        return self.key_index[name]

    def get(self, name: str) -> pd.Series:
        if name not in self.series:
            raise KeyError(f"chưa có tham chiếu '{name}'")
        return self.series[name]


def _unique_index(s: pd.Series) -> pd.Index:
    return pd.Index(s.dropna().unique())


def _needs(cfg: dict, rule_type: str) -> bool:
    return any(r.get("type") == rule_type for tc in cfg["tables"].values() for r in tc.get("rules", []))


def build_context(cfg: dict) -> Context:
    ctx = Context()
    ref = cfg["reference"]
    fmt = ref.get("datetime_format")
    t_end = pd.Timestamp(ref["T_ref"]) + pd.Timedelta(days=1)
    tcfg, ex = cfg["tables"], cfg.get("_exists", {})

    if "business" in tcfg and ex.get("business", True):
        b = read_columns(cfg, "business", ["business_id"])
        ctx.key_index["business.business_id"] = _unique_index(b["business_id"])
        ctx.notes.append(f"business: {len(ctx.key_index['business.business_id']):,} business_id duy nhất")

    if "user" in tcfg and ex.get("user", True):
        u = read_columns(cfg, "user", ["user_id", "yelping_since"])
        ctx.key_index["user.user_id"] = _unique_index(u["user_id"])
        ys = pd.Series(as_datetime(u["yelping_since"], fmt).to_numpy(), index=u["user_id"].to_numpy())
        ctx.series["user.yelping_since"] = ys[~ys.index.duplicated(keep="first")]
        ctx.notes.append(f"user: {len(ctx.key_index['user.user_id']):,} user_id duy nhất")

    if "review" in tcfg and ex.get("review", True):
        r = read_columns(cfg, "review", ["business_id", "user_id", "stars"] + tcfg["review"].get("time_columns", []))
        r["stars"] = to_num(r["stars"])
        for key in ("business_id", "user_id"):
            g = r.groupby(key)["stars"]
            ctx.series[f"review_n_by_{key[:-3]}"] = g.size()
            ctx.series[f"review_mean_by_{key[:-3]}"] = g.mean()
        ctx.notes.append(f"review: {len(r):,} dòng làm tham chiếu (số review, trung bình sao)")

    if _needs(cfg, "activity_rate"):
        parts = []
        for t in ("review", "tip", "checkin"):
            if t in tcfg and ex.get(t, True):
                tc = tcfg[t].get("time_columns", [])
                if not tc or "business_id" not in table_columns(cfg, t):
                    continue
                d = read_columns(cfg, t, ["business_id", tc[0]])
                d = pd.DataFrame({"business_id": d["business_id"].to_numpy(), "t": as_datetime(d[tc[0]], fmt).to_numpy()})
                parts.append(d[d["t"].notna() & (d["t"] < t_end)].groupby("business_id")["t"].max())
        if parts:
            ctx.series["last_activity_by_business"] = pd.concat(parts).groupby(level=0).max()
            ctx.notes.append(f"hoạt động gần nhất theo POI: {len(ctx.series['last_activity_by_business']):,} POI")
    return ctx


# ============================================================================= (3) CHẠY QUY TẮC
@dataclass
class TableResult:
    table: str
    n_rows: int
    rules: list = field(default_factory=list)      # một dòng / quy tắc
    aspects: list = field(default_factory=list)    # một dòng / khía cạnh
    metrics: list = field(default_factory=list)    # số liệu tham khảo (độ phủ, tổng review...)
    samples: list = field(default_factory=list)    # ô lỗi mẫu
    warnings: list = field(default_factory=list)   # quy tắc bị bỏ qua do thiếu cột/bảng


def grade_of(score: float, good: float, bad: float) -> str:
    if score is None or np.isnan(score):
        return NOTE
    return GOOD if score >= good else (WARN if score >= bad else BAD)


def rule_thresholds(cfg: dict, r: dict) -> tuple[float, float]:
    th = cfg["thresholds"]
    base = th["star"] if r.get("level") == "star" else th["aspect"][r["aspect"]]
    merged = {**base, **(r.get("thresholds") or {})}
    return float(merged["good"]), float(merged["bad"])


def _items(r: dict, df_cols: list[str]):
    """Mở rộng `columns` (list hoặc dict ghi đè tham số) và `columns_prefix` thành [(cột, ghi đè)]."""
    cols, pre = r.get("columns"), r.get("columns_prefix")
    if cols is None and pre is None:
        return None
    items = [(c, {}) for c in cols] if isinstance(cols, list) else [(c, (v or {})) for c, v in (cols or {}).items()]
    if pre:
        have = {c for c, _ in items}
        items += [(c, {}) for c in df_cols if c.startswith(pre) and c not in have]
    return items


def run_rule(r: dict, df: pd.DataFrame, heavy: dict, ctx, ref: dict, t_start, t_end, warnings: list) -> RuleOut | None:
    """Gọi hàm kiểm tra theo `type` của quy tắc; quy tắc nhiều cột thì chạy từng cột rồi gộp."""
    spec = SPECS[r["type"]]
    mk = lambda p: RuleCtx(df=df, p=p, ctx=ctx, ref=ref, t_start=t_start, t_end=t_end, heavy=heavy)
    base = {k: v for k, v in r.items() if k not in ("columns", "columns_prefix")}
    items = _items(r, list(df.columns))
    if items is None:
        need = [base.get(k) for k in ("column", "key", "other", "state")] + list(base.get("keys", []))
        miss = [c for c in need if c and c not in df.columns and c not in heavy]
        if miss:
            warnings.append(f"{r['id']}: bỏ qua vì thiếu cột {miss}")
            return None
        return spec["fn"](mk(base))
    merged = RuleOut(cells={})
    for col, ov in items:
        p = {**base, **ov, "column": col}
        miss = [c for c in [col, p.get("key"), p.get("other"), p.get("state")] if c and c not in df.columns and c not in heavy]
        if miss:
            warnings.append(f"{r['id']}: bỏ qua cột {miss} (không có trong bảng)")
            continue
        out = spec["fn"](mk(p))
        merged.cells.update(out.cells)
        merged.flagged += out.flagged
        merged.metrics += out.metrics
        merged.extra.update(out.extra)
    return merged if (merged.cells or merged.metrics) else None


def _cell_values(df, label, pos):
    if label in df.columns:
        return df[label].iloc[pos].tolist()
    inner = [k.strip() for k in label.strip("()").split(",")]        # khóa ghép "(a, b)"
    if all(k in df.columns for k in inner):
        return ["; ".join(f"{k}={short(df[k].iloc[p], 25)}" for k in inner) for p in pos]
    return [None] * len(pos)


def evaluate_table(cfg: dict, table: str, df: pd.DataFrame, heavy: dict[str, np.ndarray], ctx) -> TableResult:
    tc, ref = cfg["tables"][table], cfg["reference"]
    res = TableResult(table=table, n_rows=len(df))
    t_start = pd.Timestamp(ref["T_start"])
    t_end = pd.Timestamp(ref["T_ref"]) + pd.Timedelta(days=1)
    n_sample = int(cfg["run"].get("n_sample", 20))
    keys = [k for k in tc.get("keys", []) if k in df.columns]

    for r in tc.get("rules", []):
        rid, aspect, rtype, level = r["id"], r["aspect"], r["type"], r.get("level", "general")
        if rtype not in SPECS:
            raise ValueError(f"{table}.{rid}: type '{rtype}' chưa được hỗ trợ")
        if aspect not in SPECS[rtype]["aspects"]:
            raise ValueError(f"{table}.{rid}: type '{rtype}' chỉ dùng cho {SPECS[rtype]['aspects']}, không phải '{aspect}'")
        if level not in ("star", "general", "report"):
            raise ValueError(f"{table}.{rid}: level '{level}' không hợp lệ")
        try:
            out = run_rule(r, df, heavy, ctx, ref, t_start, t_end, res.warnings)
        except KeyError as e:
            res.warnings.append(f"{rid}: bỏ qua - {e}")
            out = None
        good, bad = rule_thresholds(cfg, r)
        row = {"table": table, "rule_id": rid, "aspect": aspect, "level": level, "scope": r.get("scope", ""),
               "type": rtype, "from_report": r.get("from_report", True), "desc": r.get("desc", ""),
               "n_units": 0, "n_violations": 0, "n_flagged": 0, "score": np.nan, "good": good, "bad": bad,
               "grade": NOTE, "action": "", "top_values": ""}
        if out is None:
            row["grade"] = "BỎ QUA"
            res.rules.append(row)
            continue

        units = viol = 0
        tops = []
        for label, t in out.cells.items():                 # t: mảng {1 True, 0 False, -1 N/A} theo từng ô
            units += int((t >= 0).sum())
            n_bad = int((t == 0).sum())
            viol += n_bad
            if not n_bad:
                continue
            pos_all = np.flatnonzero(t == 0)
            if label in df.columns:                         # giá trị vi phạm phổ biến nhất
                vc = df[label].iloc[pos_all[:200_000]].astype(str).map(lambda x: short(x, 30)).value_counts().head(5)
                tops.append(f"{label}: " + "; ".join(f"{k}×{c}" for k, c in vc.items()))
            pos = pos_all[:n_sample]                        # ô lỗi mẫu để tra lại dữ liệu gốc
            vals = ["<thiếu>"] * len(pos) if label in heavy else _cell_values(df, label, pos)
            ex = out.extra.get(label)
            for i, p in enumerate(pos):
                res.samples.append({"table": table, "rule_id": rid, "aspect": aspect, "row_position": int(p),
                                    "record": "; ".join(f"{k}={short(df[k].iloc[p], 40)}" for k in keys),
                                    "cell": label, "value": short(vals[i]),
                                    "reference_name": ex[0] if ex else None,
                                    "reference_value": short(ex[1][p]) if ex else None})
        for m in out.metrics:
            res.metrics.append({"table": table, "rule_id": rid, **m})

        row.update(n_units=units, n_violations=viol, n_flagged=out.flagged, top_values=" | ".join(tops))
        if units:
            row["score"] = 1 - viol / units
        if level == "report":
            row["grade"] = row["action"] = REPORT
        elif units:
            row["grade"] = grade_of(row["score"], good, bad)
            row["action"] = "Xử lý mọi vi phạm (quy tắc ★)" if (level == "star" and viol) else (
                ACTION[GOOD] if level == "star" else ACTION[row["grade"]])
        res.rules.append(row)

    # ========================================================================= (4) ĐIỂM KHÍA CẠNH
    na = tc.get("not_applicable", {}) or {}
    asp_thr = cfg["thresholds"]["aspect"]
    for aspect in ASPECTS:
        rr = [r for r in res.rules if r["aspect"] == aspect and r["level"] != "report" and r["n_units"] > 0]
        has_report = any(r["aspect"] == aspect and r["level"] == "report" and r["grade"] != "BỎ QUA" for r in res.rules)
        skipped = [r["rule_id"] for r in res.rules if r["aspect"] == aspect and r["grade"] == "BỎ QUA"]
        g, bd = float(asp_thr[aspect]["good"]), float(asp_thr[aspect]["bad"])
        row = {"table": table, "aspect": aspect, "good": g, "bad": bd}
        if not rr:
            why = na.get(aspect) or ("chỉ có quy tắc chỉ báo cáo" if has_report else "CHƯA CẤU HÌNH quy tắc nào")
            if skipped:
                why = f"quy tắc {','.join(skipped)} bị BỎ QUA (thiếu cột/bảng tham chiếu, xem cảnh báo)"
            row.update(status=REPORT if has_report else NOTE, note=why)
            res.aspects.append(row)
            continue
        score = float(np.mean([r["score"] for r in rr]))
        flagged = [r["rule_id"] for r in rr if r["level"] == "star" and r["grade"] == BAD]
        row.update(status="Đo được", n_rules=len(rr), score=score, grade=grade_of(score, g, bd),
                   flagged_rules=",".join(flagged), flag=bool(flagged), min_rule_score=float(min(r["score"] for r in rr)),
                   n_units=sum(r["n_units"] for r in rr), n_violations=sum(r["n_violations"] for r in rr), note=na.get(aspect, ""))
        res.aspects.append(row)
    return res


# =====================================================================================
# 4. BÁO CÁO
# =====================================================================================


PURPOSE = """\
**Đây là lần khảo sát một lần trên dữ liệu Yelp *thô*, snapshot xuất ngày {t_ref}**, phục vụ bài toán gợi ý POI kế tiếp (ST-GUGEN). Báo cáo trả lời hai câu hỏi:

1. **Dữ liệu thô đang có lỗi gì, ở bảng nào, nặng đến đâu** theo 6 khía cạnh của báo cáo đo lường CLDL (Đầy đủ, Duy nhất, Nhất quán, Kịp thời, Hợp lệ, Chính xác).
2. **Mỗi lỗi nên xử lý thế nào** trước khi tiền xử lý thành chuỗi ghé thăm: dùng trực tiếp, gắn cờ, sửa/điền, hay loại.

**Không thuộc phạm vi:** giám sát liên tục/tự động; đo lại sau làm sạch; đo ảnh hưởng của chất lượng dữ liệu lên độ chính xác mô hình (AccTEMPO); kiểm tra dữ liệu có đúng với thực tế ngoài đời hay không (khía cạnh *Chính xác* chỉ kiểm tra đối chiếu nội bộ giữa các bảng/cột).
"""

LIMITS = """\
- **Mốc thời gian**: T_ref = {t_ref} (ngày xuất snapshot), khung Kịp thời bắt đầu {t_start} theo báo cáo (nguồn cần xác nhận); riêng T2 dùng 01/07/2004 (Yelp thành lập 07/2004).
- **Ngưỡng** lấy từ Bảng A.1 của báo cáo CLDL; nhóm có thể đổi trong `CONFIG_YAML` (mục `thresholds`) trong `danh_gia_cldl.py`.
- **Đơn vị đo là ô**: khóa ghép (U2–U4) tính một ô tổ hợp; ô nhiều giá trị (vd. `friends`) sai nếu có một phần tử sai; vi phạm trùng lặp đếm số bản sao thừa.
- **Quy tắc đối chiếu** (S6–S8, giá trị tính từ bảng khác) chỉ nói *hai nguồn có khớp nhau không*, chưa chứng minh nguồn nào đúng; xem ô "cần kiểm chứng" nếu có.
- Điểm dồn sát 1 nên biểu đồ không bắt đầu từ 0; đọc cùng bảng điểm và số ô vi phạm.
"""


# ----------------------------------------------------------------------------- cấu hình
def load_config(data_dir: str | None = None, out_dir: str | None = None) -> dict:
    cfg = yaml.safe_load(CONFIG_YAML)
    cfg["_sha256"] = hashlib.sha256(CONFIG_YAML.encode("utf-8")).hexdigest()
    for k, v in (("data_dir", data_dir), ("out_dir", out_dir)):
        if v:
            cfg["run"][k] = v
    return cfg


# ----------------------------------------------------------------------------- kết quả -> bảng
def build_frames(results: list) -> dict[str, pd.DataFrame]:
    rules = pd.DataFrame([r for tr in results for r in tr.rules])
    aspects = pd.DataFrame([r for tr in results for r in tr.aspects])
    metrics = pd.DataFrame([r for tr in results for r in tr.metrics])
    samples = pd.DataFrame([r for tr in results for r in tr.samples])
    rows = []
    ok = aspects[aspects["status"] == "Đo được"]
    for a in ASPECTS:
        s = ok[ok["aspect"] == a]
        if len(s) == 0:
            continue
        sc = float(s["score"].mean())
        rows.append({"aspect": a, "n_tables": len(s), "tables": ",".join(s["table"]), "score": sc,
                     "grade": grade_of(sc, float(s["good"].iloc[0]), float(s["bad"].iloc[0])),
                     "flag": bool(s["flag"].any()), "flagged_tables": ",".join(s[s["flag"]]["table"])})
    return {"rules": rules, "aspects": aspects, "dataset": pd.DataFrame(rows), "metrics": metrics, "samples": samples}


# ----------------------------------------------------------------------------- biểu đồ
INK, MUTED = "#1f2937", "#6b7280"
GRADE_COLOR = {GOOD: "#2a6fb0", WARN: "#b9770e", BAD: "#c0392b"}


def vn(x, d=6) -> str:
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}".replace(".", ",")


def plot_table(aspects: pd.DataFrame, table: str):
    """Mỗi khía cạnh một chấm tại điểm của nó; vạch xám = ngưỡng Chú ý (nhạt) và Tốt (đậm). Mã hàm này được chép vào notebook."""
    s = aspects[(aspects["table"] == table) & aspects["aspect"].isin(ASPECTS)].set_index("aspect").reindex(ASPECTS)
    vals = s["score"].astype(float).to_numpy()
    fin = vals[~np.isnan(vals)]
    lo = min(0.78, (fin.min() - 0.01) if len(fin) else 0.78)
    lo = max(0.0, np.floor(lo * 50) / 50)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    y = np.arange(len(ASPECTS))[::-1]
    for yi, a in zip(y, ASPECTS):
        r = s.loc[a]
        v = r["score"]
        if pd.isna(v):
            ax.text(lo + 0.004, yi, "không áp dụng" if r["status"] == NOTE else "chỉ báo cáo", va="center", ha="left", color=MUTED, fontsize=10)
            continue
        ax.plot([r["bad"]] * 2, [yi - 0.28, yi + 0.28], color="#aeb4bb", lw=1.2, zorder=1)
        ax.plot([r["good"]] * 2, [yi - 0.28, yi + 0.28], color="#6b7280", lw=1.6, zorder=1)
        ax.plot([v, 1.0], [yi, yi], color="#c9ced4", lw=3, solid_capstyle="round", zorder=1)
        ax.scatter([v], [yi], s=95, color=GRADE_COLOR.get(r["grade"], INK), zorder=3)
        ax.text(1.0 + (1 - lo) * 0.025, yi, f"{vn(v, 6)} · {r['grade']}" + ("  ⚑" if (not pd.isna(r["flag"]) and bool(r["flag"])) else ""), va="center", ha="left",
                color=INK, fontsize=10, fontweight="bold" if r["grade"] == BAD else "normal", clip_on=False)
    ax.set_yticks(y)
    ax.set_yticklabels(ASPECTS, color=INK)
    ax.set_xlim(lo, 1.004)
    ax.set_ylim(-0.6, len(ASPECTS) - 0.4)
    ax.set_xlabel("Điểm khía cạnh = trung bình điểm các quy tắc cùng khía cạnh. Vạch: ngưỡng Chú ý (nhạt) và Tốt (đậm). ⚑ = có quy tắc ★ ở mức Tệ", color=MUTED, fontsize=8)
    ax.set_title(f"Bảng {table}", loc="left", color=INK, fontsize=12, fontweight="bold")
    ax.grid(axis="x", color="#eef0f2", lw=0.8, zorder=0)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.subplots_adjust(left=0.13, right=0.78, top=0.90, bottom=0.17)
    plt.show()


# ----------------------------------------------------------------------------- notebook báo cáo
# Mã chạy trong notebook: kết quả đã nhúng sẵn (DATA), notebook không tính lại gì và không cần file nào khác.
_SETUP = '''\
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import HTML, Markdown, display

ASPECTS = ["Đầy đủ", "Duy nhất", "Nhất quán", "Kịp thời", "Hợp lệ", "Chính xác"]
GOOD, WARN, BAD, NOTE = "Tốt", "Chú ý", "Tệ", "N/A"
INK, MUTED = "#1f2937", "#6b7280"
GRADE_COLOR = {GOOD: "#2a6fb0", WARN: "#b9770e", BAD: "#c0392b"}

DATA = json.loads(@@DATA@@)       # kết quả đo, do danh_gia_cldl.py nhúng vào lúc sinh notebook
rules, aspects, dataset = (pd.DataFrame(DATA[k]) for k in ("rules", "aspects", "dataset"))
metrics, samples = pd.DataFrame(DATA["metrics"]), pd.DataFrame(DATA["samples"])
meta = DATA["meta"]

def vn(x, d=6):
    return "-" if x is None or pd.isna(x) else f"{x:.{d}f}".replace(".", ",")

def md(lines):
    display(Markdown("\\n".join(lines)))

@@PLOT@@

TABLES = list(meta["rows"])
'''

_MATRIX = '''\
L = ["| Bảng (số dòng) | " + " | ".join(ASPECTS) + " |", "|---|" + "---:|" * len(ASPECTS)]
for t in TABLES:
    cells = []
    for a in ASPECTS:
        r = aspects[(aspects.table == t) & (aspects.aspect == a)].iloc[0]
        if r.status == "Đo được":
            cells.append(f"{vn(r.score)} · {r.grade}" + (" ⚑" if r.flag else ""))
        else:
            cells.append("N/A" if r.status == "N/A" else "chỉ báo cáo")
    L.append(f"| {t} ({meta['rows'][t]:,}) | " + " | ".join(cells) + " |")
md(L)
if len(dataset):
    md(["", "**Mức bộ dữ liệu** (trung bình điểm các bảng đo được): " + "; ".join(
        f"{r.aspect} {vn(r.score)} · {r.grade}" + (" ⚑" if r.flag else "") for r in dataset.itertuples()) + "."])
'''

_NA = '''\
na = aspects[aspects.aspect.isin(ASPECTS) & (aspects.status != "Đo được")]
md([f"- **{r.table} · {r.aspect}**: {r.note}" for r in na.itertuples()] or ["Không có."])
'''

_TABLE_DETAIL = '''\
def show_table(t):
    sub = rules[rules.table == t]
    L = ["| Mã | Khía cạnh | Phạm vi | Quy tắc | Ô xét | Vi phạm | Điểm | Xếp hạng |", "|---|---|---|---|---:|---:|---:|---|"]
    for r in sub.itertuples():
        mark = "★ " if r.level == "star" else ""
        extra = f" (⚠ {int(r.n_flagged):,} ô cần kiểm chứng)" if r.n_flagged else ""
        L.append(f"| {mark}{r.rule_id} | {r.aspect} | {r.scope if isinstance(r.scope, str) else ''} | {r.desc}{extra} | "
                 f"{int(r.n_units):,} | {int(r.n_violations):,} | {vn(r.score)} | {r.grade} |")
    md(L)
    plot_table(aspects, t)

show_table("{TABLE}")
'''

_ACTIONS = '''\
need = rules[(rules.grade == "Tệ") | ((rules.level == "star") & (rules.n_violations > 0)) | (rules.grade == "Chú ý")]
order = need.grade.map({"Tệ": 0, "Chú ý": 2}).fillna(1)      # Tệ trước, rồi quy tắc ★ có vi phạm, rồi Chú ý
need = need.assign(_o=order).sort_values(["_o", "n_violations"], ascending=[True, False]).drop(columns="_o")
if len(need):
    L = ["| Bảng | Mã | Khía cạnh | Vi phạm | Điểm | Xếp hạng | Hướng xử lý | Giá trị vi phạm phổ biến |", "|---|---|---|---:|---:|---|---|---|"]
    for r in need.itertuples():
        top = r.top_values if isinstance(r.top_values, str) and r.top_values else "—"
        L.append(f"| {r.table} | {'★ ' if r.level == 'star' else ''}{r.rule_id} | {r.aspect} | {int(r.n_violations):,} | {vn(r.score)} | {r.grade} | {r.action} | {top} |")
    md(L)
else:
    md(["Không có quy tắc nào ở mức Chú ý/Tệ và không có quy tắc ★ nào bị vi phạm: dùng trực tiếp."])
'''

_REPORT_ONLY = '''\
L = []
for r in rules[rules.level == "report"].itertuples():
    if r.n_units:
        L.append(f"- **{r.table} · {r.rule_id}** — {r.desc}: {int(r.n_violations):,}/{int(r.n_units):,} ô → tỷ lệ đạt {vn(r.score, 4)}.")
for m in metrics.itertuples():
    L.append(f"- **{m.table} · {m.rule_id}** — {m.metric}: {vn(m.value, 4)} ({m.numerator:,.0f}/{m.denominator:,.0f}); {m.note}.")
md(L or ["Không có."])
'''

_SELFTEST = '''\
st = meta.get("selftest") or []
md([f"**{sum(c['ok'] for c in st)}/{len(st)} kiểm tra đạt** (dữ liệu giả có tiêm lỗi biết trước, chạy cùng bộ quy tắc):", ""]
   + [f"- {'✅' if c['ok'] else '❌'} {c['name']}" + ("" if c["ok"] else f" - {c['detail']}") for c in st] if st else ["Chưa chạy tự kiểm (--no-selftest)."])
'''

_SAMPLES = '''\
cols = ["rule_id", "record", "cell", "value", "reference_name", "reference_value"]
if len(samples):
    for t, g in samples.groupby("table", sort=False):
        display(HTML(f"<details><summary><b>{t}</b>: {len(g)} ô lỗi mẫu (bấm để mở)</summary>"
                     + g[cols].to_html(index=False, max_rows=None, na_rep="") + "</details>"))
else:
    md(["Không có ô lỗi."])
'''


def _method_md(cfg: dict) -> str:
    th = cfg["thresholds"]
    used = sorted({r["type"] for tc in cfg["tables"].values() for r in tc.get("rules", [])})
    L = ["**Đơn vị đo là ô.** Mỗi quy tắc kiểm tra từng ô và trả về **True** (đạt), **False** (vi phạm) hoặc **N/A** (không xét, không tính vào tử số lẫn mẫu số).", "",
         "- Điểm quy tắc = 1 − (số ô False) / (số ô True + số ô False)",
         "- Điểm khía cạnh của một bảng = trung bình điểm các quy tắc cùng khía cạnh (bỏ quy tắc *chỉ báo cáo*)",
         "- Xếp hạng theo Bảng A.1: " + "; ".join(f"{a}: Tốt ≥ {vn(v['good'], 2)}, Tệ < {vn(v['bad'], 2)}" for a, v in th["aspect"].items())
         + f"; quy tắc ★: Tốt ≥ {vn(th['star']['good'], 3)}, Tệ < {vn(th['star']['bad'], 2)}",
         "- Khía cạnh gắn cờ ⚑ nếu có quy tắc ★ rơi vào *Tệ* dù điểm trung bình cao", "",
         "**Các loại kiểm tra đã dùng** (ô nào là True/False/N/A và vì sao):", "",
         "| Loại | Khía cạnh | True | False | N/A | Vì sao |", "|---|---|---|---|---|---|"]
    for t in used:
        s = SPECS[t]
        L.append(f"| `{t}` | {', '.join(s['aspects'])} | {s['true']} | {s['false']} | {s['na']} | {s['why']} |")
    return "\n".join(L)


def build_notebook(cfg: dict, tables: list[str], out: Path, frames: dict, meta: dict) -> Path:
    """Sinh notebook DUY NHẤT: kết quả nhúng vào ô setup, biểu đồ vẽ bằng chính mã plot_table."""
    import inspect
    import nbformat as nbf
    ref = cfg["reference"]
    data = {k: json.loads(frames[k].to_json(orient="records", force_ascii=False)) for k in frames}
    data["meta"] = meta
    setup = (_SETUP.replace("@@DATA@@", repr(json.dumps(data, ensure_ascii=False, default=str)))
                   .replace("@@PLOT@@", inspect.getsource(plot_table)))
    nb = nbf.v4.new_notebook()
    md = lambda s: nbf.v4.new_markdown_cell(s)
    code = lambda s: nbf.v4.new_code_cell(s)
    cells = [md("# Báo cáo chất lượng dữ liệu Yelp thô"),
             md("## 0. Mục đích và phạm vi\n\n" + PURPOSE.format(t_ref=ref["T_ref"])),
             md("## 1. Cách đo\n\n" + _method_md(cfg)),
             code(setup),
             md("## 2. Điểm theo bảng và khía cạnh"), code(_MATRIX),
             md("**Khía cạnh không áp dụng / không đo được:**"), code(_NA),
             md("## 3. Chi tiết từng bảng")]
    for t in tables:
        cells += [md(f"### {t}"), code(_TABLE_DETAIL.replace("{TABLE}", t))]
    cells += [md("## 4. Việc cần xử lý\n\nQuy tắc ở mức Chú ý/Tệ hoặc quy tắc ★ có vi phạm, kèm hướng xử lý đề xuất (dùng trực tiếp / gắn cờ / sửa-điền / loại)."),
              code(_ACTIONS),
              md("**Chỉ báo cáo (không xếp hạng):**"), code(_REPORT_ONLY),
              md("**Ô lỗi mẫu** (tối đa 20 ô mỗi quy tắc, kèm khóa bản ghi để tra lại dữ liệu gốc):"), code(_SAMPLES),
              md("## 5. Giới hạn và tham số cần xác nhận\n\n" + LIMITS.format(t_ref=ref["T_ref"], t_start=ref["T_start"])),
              md("## 6. Kiểm tra code"), code(_SELFTEST)]
    nb["cells"] = cells
    nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}
    out.mkdir(parents=True, exist_ok=True)
    path = out / "BaoCao_CLDL.ipynb"
    nbf.write(nb, path)
    try:
        from nbclient import NotebookClient
        NotebookClient(nb, timeout=300, kernel_name="python3", resources={"metadata": {"path": str(out)}}).execute()
        nbf.write(nb, path)
    except Exception as e:  # không có kernel: giữ bản chưa chạy, người dùng mở và Run All
        print(f"    (chưa chạy sẵn notebook: {type(e).__name__}: {str(e)[:120]}; hãy mở và Run All)")
    return path


# ----------------------------------------------------------------------------- chạy
def measure(cfg: dict, tables: list[str], say=print) -> tuple[list, dict]:
    """Đo các bảng `tables`: trả (kết quả từng bảng, các DataFrame kết quả)."""
    say("[1/3] Dựng tham chiếu liên bảng ...")
    ctx = build_context(cfg)
    results = []
    say("[2/3] Đo từng bảng ...")
    for t in tables:
        ts = time.time()
        df, heavy = load_table(cfg, t)
        results.append(evaluate_table(cfg, t, df, heavy, ctx))
        say(f"    {t}: {len(df):,} dòng, {time.time() - ts:.1f}s")
        del df, heavy
    return results, build_frames(results)


def run(cfg: dict, tables: list[str] | None = None, check: bool = True, verbose: bool = True) -> dict:
    t0 = time.time()
    wanted = tables or list(cfg["tables"])
    absent = [t for t in wanted if not table_path(cfg, t).exists()]
    if absent:
        raise FileNotFoundError(f"Không thấy file dữ liệu của bảng {absent} trong {cfg['run']['data_dir']}")
    say = print if verbose else (lambda *a, **k: None)
    checks = selftest(cfg) if check else []
    if check:
        say(f"[0/3] Tự kiểm code: {sum(c['ok'] for c in checks)}/{len(checks)} đạt")
    results, frames = measure(cfg, wanted, say)

    say("[3/3] Sinh notebook báo cáo ...")
    ref = cfg["reference"]
    meta = {"run_at": datetime.now().isoformat(timespec="seconds"), "version": __version__,
            "config_sha256": cfg["_sha256"], "T_ref": ref["T_ref"], "T_start": ref["T_start"],
            "thresholds": cfg["thresholds"], "tables": wanted, "rows": {r.table: r.n_rows for r in results},
            "warnings": {r.table: r.warnings for r in results if r.warnings}, "selftest": checks,
            "elapsed_seconds": round(time.time() - t0, 1)}
    nb_path = build_notebook(cfg, wanted, Path(cfg["run"]["out_dir"]), frames, meta)
    for r in results:
        for w in r.warnings:
            say(f"    ⚠ {r.table}: {w}")
    say(f"Xong trong {meta['elapsed_seconds']}s. Báo cáo: {nb_path.resolve()}")
    return {"frames": frames, "results": results, "meta": meta}


# =====================================================================================
# 5. TỰ KIỂM CODE
# =====================================================================================

FMT = "%Y-%m-%d %H:%M:%S"
UNKNOWN_B = "B" + "9" * 21
UNKNOWN_U = "U" + "9" * 21


def bid(i): return "B" + str(i).zfill(21)
def uid(i): return "U" + str(i).zfill(21)
def rid(i): return "R" + str(i).zfill(21)


def make_synthetic(out_dir: Path, seed: int = 7):
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    exp: dict[tuple, int] = {}
    aux: dict = {}

    def e(table, rule, v=1): exp[(table, rule)] = exp.get((table, rule), 0) + v

    # ------------------------------------------------------------------ USER (80 user; 0..49 có review)
    n_u = 80
    ys = pd.Series(pd.Timestamp("2008-01-01") + pd.to_timedelta(rng.integers(0, 2800, n_u), unit="D") + pd.to_timedelta(rng.integers(0, 86000, n_u), unit="s"))
    users = pd.DataFrame({
        "user_id": [uid(i) for i in range(n_u)], "name": [f"User{i}" for i in range(n_u)],
        "review_count": [8 if i < 50 else 5 for i in range(n_u)], "yelping_since": ys.dt.strftime(FMT),
        "useful": 3, "funny": 2, "cool": 1, "fans": 0,
        "average_stars": [((2 * i) % 5 + 1) * 1.0 if i < 50 else 3.5 for i in range(n_u)],
    })
    users["elite"] = [f"{ys[i].year + 1},{ys[i].year + 2}" if i < 20 else "" for i in range(n_u)]
    def _fr(i):                                    # 4 dạng thật thường gặp: None | [] | "['a', 'b']" | "a, b"
        a, b = uid((i + 1) % 50), uid((i + 2) % 50)
        return ["None", "[]", f"['{a}', '{b}']", f"{a}, {b}"][i % 4]
    users["friends"] = [_fr(i) for i in range(n_u)]
    for c in ["hot", "more", "profile", "cute", "list", "note", "plain", "cool", "funny", "writer", "photos"]:
        users[f"compliment_{c}"] = 1
    users.loc[0, "average_stars"] = 2.8;  e("user", "S8")                      # trung bình review thực = 1 -> lệch 1,8
    users.loc[1, "review_count"] = 3                                            # < 8 review quan sát được (S3 tính ở cuối)
    users.loc[2, "review_count"] = 20                                            # >= số quan sát: hợp lệ (cận dưới)
    users.loc[50, "yelping_since"] = "2003-05-01 00:00:00"; e("user", "T2")    # trước T_start
    users.loc[51, "yelping_since"] = "not a date";          e("user", "V6")    # sai định dạng (T2 không xét)
    users.loc[52, "yelping_since"] = "2023-02-01 00:00:00"; e("user", "T2")    # sau T_ref
    users.loc[53, ["yelping_since", "elite"]] = ["2010-03-03 10:00:00", "2019,2025"]; e("user", "S4")   # 2025 > 2022
    users.loc[54, ["yelping_since", "elite"]] = ["2010-03-03 10:00:00", "2005,2012"]; e("user", "S4")   # 2005 < 2010
    users.loc[56, "elite"] = "abc";                         e("user", "V9")
    users.loc[57, "average_stars"] = 7.0;                   e("user", "V7")
    users.loc[58, "compliment_hot"] = -1;                   e("user", "V4")
    users.loc[59, "name"] = None                                                  # name không thuộc quy tắc Đầy đủ nào
    users.loc[60, "friends"] = None; users.loc[61, "friends"] = None
    users.loc[62, "user_id"] = "short";                     e("user", "V1")
    users.loc[63, "friends"] = f"['{uid(1)}', 'bad_id']";   e("user", "V11")   # một phần tử sai định dạng
    users.loc[55, "yelping_since"] = "2004-10-12 08:46:11"                      # trước T_start chung nhưng sau 2004-07-01: HỢP LỆ với T2
    users = pd.concat([users, users.iloc[[3, 4]]], ignore_index=True); e("user", "U1", 2)
    miss_elite = int((users["elite"].isna() | users["elite"].astype(str).str.strip().eq("")).sum())
    miss_friends = int((users["friends"].isna() | users["friends"].astype(str).str.strip().isin(["None", "[]"])).sum())
    e("user", "C7", miss_elite + miss_friends)                                   # chỉ báo cáo

    # ------------------------------------------------------------------ BUSINESS (62 dòng gốc, 0..49 Phoenix/AZ, 50..61 Philadelphia/PA)
    n_b = 62
    az = np.arange(n_b) < 50
    biz = pd.DataFrame({
        "business_id": [bid(i) for i in range(n_b)], "name": [f"Biz{i}" for i in range(n_b)], "address": "1 Main St",
        "city": np.where(az, "Phoenix", "Philadelphia"), "state": np.where(az, "AZ", "PA"), "postal_code": np.where(az, "85001", "19019"),
        "latitude": np.where(az, rng.uniform(32.8, 33.6, n_b), rng.uniform(39.9, 40.1, n_b)),
        "longitude": np.where(az, rng.uniform(-112.5, -111.5, n_b), rng.uniform(-75.3, -75.0, n_b)),
        "stars": [((2 * i) % 5 + 1) * 1.0 if i < 40 else 3.0 for i in range(n_b)],
        "review_count": [10 if i < 40 else 0 for i in range(n_b)], "is_open": 1,
        "attributes": '{"RestaurantsTakeOut": "True"}', "categories": "Food, Restaurants", "hours": '{"Monday": "10:0-21:0"}',
    })
    biz.loc[0, "review_count"] = 30                                              # lệch tham chiếu -> chỉ S6 (chỉ báo cáo, tính ở cuối)
    biz.loc[2, "stars"] = 1.0;            e("business", "S7")                    # trung bình review = 5
    biz.loc[3, "state"] = "az";           e("business", "V8")
    biz.loc[7, "longitude"] = -73.2;      e("business", "V2")                    # ví dụ POI ngoại lai ở báo cáo (> -74)
    biz.loc[8, "latitude"] = 99.0;        e("business", "V2")
    biz.loc[9, "stars"] = 4.3;            e("business", "V3")                    # không phải bội 0,5 (S7: lệch 0,3 <= 0,5 nên không lỗi)
    biz.loc[10, "is_open"] = 2;           e("business", "V5")
    biz.loc[11, "review_count"] = -4;     e("business", "V4")
    biz.loc[[13, 14, 15], "postal_code"] = None; e("business", "C2", 3)
    biz.loc[16, "name"] = None;           e("business", "C1")
    biz.loc[[17, 18], "address"] = None;  e("business", "C7", 2)
    biz.loc[[19, 20, 21, 22, 23], "hours"] = None; e("business", "C7", 5)
    biz.loc[20, "city"] = "phoenix ";     e("business", "S5a")                   # cách viết khác của Phoenix
    biz.loc[21, "city"] = "PHOENIX";      e("business", "S5a")
    biz.loc[22, "state"] = "PA";          e("business", "S5b")                   # Phoenix nhưng state PA
    biz.loc[25, "attributes"] = "{bad";   e("business", "V12b")
    biz.loc[26, "hours"] = '{"Monday": "10-21"}'; e("business", "V10")
    biz.loc[27, "hours"] = '{"Monday": "0:0-0:0"}'                              # chỉ gắn nhãn cần kiểm chứng
    biz.loc[45, "business_id"] = "x";     e("business", "V1")                    # business 45 không có review/tip/checkin tham chiếu
    biz = pd.concat([biz, biz.iloc[[5, 6]]], ignore_index=True); e("business", "U1", 2); e("business", "U3", 2)
    aux["flagged_hours"] = 1
    aux["biz_sum_review_count"] = int(biz.drop_duplicates("business_id")["review_count"].sum())

    # ------------------------------------------------------------------ REVIEW (400 dòng gốc)
    n_r = 400
    i_ = np.arange(n_r)
    u_idx, b_idx = i_ % 50, i_ % 40
    ys_dt = pd.to_datetime(users["yelping_since"].iloc[:50])
    date = ys_dt.to_numpy()[u_idx] + pd.to_timedelta(30 + (i_ * 37) % 2000, unit="D") + pd.to_timedelta((i_ * 911) % 86000, unit="s")
    rev = pd.DataFrame({
        "review_id": [rid(i) for i in i_], "user_id": [uid(u) for u in u_idx], "business_id": [bid(b) for b in b_idx],
        "stars": ((i_ * 7) % 5 + 1).astype(float), "useful": 1, "funny": 0, "cool": 0,
        "text": [f"review text {i}" for i in i_], "date": pd.Series(date).dt.strftime(FMT),
    })
    rev.loc[20:21, "business_id"] = UNKNOWN_B;  e("review", "S1", 2)
    rev.loc[30:33, "user_id"] = UNKNOWN_U;      e("review", "S1", 4)
    rev.loc[40:44, "date"] = "2023-03-01 10:00:00"; e("review", "T1", 5)         # sau T_ref
    rev.loc[50:51, "date"] = "2003-01-01 00:00:00"; e("review", "T1", 2); e("review", "S2", 2)   # trước T_start và trước yelping_since
    for k in (60, 61, 62):                                                       # sớm hơn yelping_since 400 ngày nhưng vẫn trong khung
        rev.loc[k, "date"] = (pd.Timestamp(users.loc[k % 50, "yelping_since"]) - pd.Timedelta(days=400)).strftime(FMT); e("review", "S2")
    for k in (72, 77, 82):                                                       # stars 5 -> 6: chỉ lệch 0,125 nên không gây lỗi S7/S8
        rev.loc[k, "stars"] = 6.0; e("review", "V3")
    rev.loc[90:91, "date"] = "garbage"; e("review", "V6", 2)
    rev.loc[[100, 101], "useful"] = -1; e("review", "V4", 2)
    rev.loc[[110, 111, 112, 113], "text"] = None; e("review", "C3", 4)
    rev.loc[120, "review_id"] = "short"; e("review", "V1")
    rev = pd.concat([rev, rev.iloc[[10, 11, 12]]], ignore_index=True); e("review", "U1", 3); e("review", "U4", 3)

    # ------------------------------------------------------------------ TIP (100 dòng gốc)
    n_t = 100
    j = np.arange(n_t)
    tdate = ys_dt.to_numpy()[(j * 3) % 50] + pd.to_timedelta(60 + j * 11, unit="D")
    tip = pd.DataFrame({"user_id": [uid((k * 3) % 50) for k in j], "business_id": [bid(k % 40) for k in j],
                        "text": [f"tip {k}" for k in j], "date": pd.Series(tdate).dt.strftime(FMT), "compliment_count": 0})
    tip.loc[[10, 11], "date"] = "2022-08-01 00:00:00"; e("tip", "T1", 2)
    tip.loc[12, "business_id"] = UNKNOWN_B; e("tip", "S1")
    tip.loc[13, "user_id"] = UNKNOWN_U;    e("tip", "S1")
    for k in (14, 15):
        tip.loc[k, "date"] = (pd.Timestamp(users.loc[(k * 3) % 50, "yelping_since"]) - pd.Timedelta(days=100)).strftime(FMT); e("tip", "S2")
    tip.loc[16, "compliment_count"] = -1; e("tip", "V4")
    tip.loc[17, "date"] = "n/a"; e("tip", "V6")
    tip.loc[[20, 21, 22], "text"] = None; tip.loc[23, "text"] = "   "; e("tip", "C4", 4)
    tip = pd.concat([tip, tip.iloc[[30, 31]]], ignore_index=True); e("tip", "U2", 2)

    # ------------------------------------------------------------------ CHECKIN (500 dòng gốc, mỗi dòng một sự kiện)
    c_ = np.arange(500)
    ck = pd.DataFrame({"business_id": [bid(k % 40) for k in c_],
                       "checkin_time": (pd.Timestamp("2020-01-01") + pd.to_timedelta(c_ * 61, unit="min")).strftime(FMT)})
    ck.loc[10:11, "business_id"] = UNKNOWN_B; e("checkin", "S1", 2)
    ck.loc[100:103, "checkin_time"] = "2022-06-01 08:00:00"; e("checkin", "T3", 4)
    ck.loc[110, "checkin_time"] = "2001-01-01 00:00:00"                          # T3 chỉ có cận trên (theo báo cáo) nên không lỗi
    ck.loc[111, "checkin_time"] = "xx"; e("checkin", "V6")
    ck.loc[[300, 301], "checkin_time"] = None; e("checkin", "C5", 2)
    ck = pd.concat([ck, ck.iloc[[200, 201, 202]]], ignore_index=True); e("checkin", "U1", 3)

    # ------------------------------------------------------------------ kỳ vọng tính ĐỘC LẬP bằng pandas thuần (không dùng dq/)
    # S3: user.review_count < số review quan sát được. Lưu ý 3 review bị nhân đôi làm user 10-12 có 9 review quan sát được
    #     trong khi review_count = 8, nên cũng bị bắt (đúng theo báo cáo: S3 không có dung sai).
    obs_u = rev.groupby("user_id").size()
    e("user", "S3", int((users["review_count"] < users["user_id"].map(obs_u).fillna(0)).sum()))
    # S6: business.review_count khác số review quan sát được (chỉ báo cáo)
    obs_b = rev.groupby("business_id").size()
    e("business", "S6", int((biz["review_count"] != biz["business_id"].map(obs_b).fillna(0)).sum()))
    # T4: business is_open = 1 mà không có review/tip/check-in nào trong 24 tháng trước T_ref (chỉ báo cáo)
    t_end = pd.Timestamp("2022-01-20")
    acts = pd.concat([rev[["business_id", "date"]].set_axis(["business_id", "t"], axis=1),
                      tip[["business_id", "date"]].set_axis(["business_id", "t"], axis=1),
                      ck[["business_id", "checkin_time"]].set_axis(["business_id", "t"], axis=1)])
    acts["t"] = pd.to_datetime(acts["t"], format=FMT, errors="coerce")
    last = acts[acts["t"].notna() & (acts["t"] < t_end)].groupby("business_id")["t"].max()
    opened = biz[pd.to_numeric(biz["is_open"]) == 1]
    recent = opened["business_id"].map(last) >= (t_end - pd.DateOffset(months=24))
    aux["T4_n"], aux["T4_violating"] = len(opened), int((~recent).sum())
    e("business", "T4", aux["T4_violating"])
    aux["n_reviews"] = len(rev)
    aux["coverage_num"] = 40                                                   # business 0..39 có check-in hợp lệ
    aux["coverage_den"] = int(biz["business_id"].nunique())

    for name, df in [("business", biz), ("user", users), ("review", rev), ("tip", tip), ("checkin_events", ck)]:
        df.to_parquet(out_dir / f"{name}.parquet", index=False)
    aux["frames"] = {"business": biz, "user": users, "review": rev, "tip": tip, "checkin": ck}
    return exp, aux


def selftest(cfg: dict) -> list[dict]:
    """Chạy bộ quy tắc trên dữ liệu giả tiêm lỗi và so với số lỗi đã tiêm. Trả danh sách {name, ok, detail}."""
    import copy
    out: list[dict] = []
    add = lambda name, ok, detail="": out.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    with tempfile.TemporaryDirectory() as d:
        exp, aux = make_synthetic(Path(d))
        c = copy.deepcopy(cfg)
        c["run"]["data_dir"] = d
        for r in c["tables"]["business"]["rules"]:
            if r["id"] == "S5b":
                r["share_min"] = 0.03                      # dữ liệu giả chỉ ~50 POI/thành phố
        results, fr = measure(c, list(c["tables"]), lambda *a, **k: None)
    rl = fr["rules"].set_index(["table", "rule_id"])
    got = {k: int(v) for k, v in rl["n_violations"].items()}
    add("Số ô vi phạm của MỌI quy tắc khớp số lỗi đã tiêm", not {k: (v, got.get(k)) for k, v in exp.items() if got.get(k) != v},
        {k: (v, got.get(k)) for k, v in exp.items() if got.get(k) != v})
    add("Không dương tính giả (quy tắc không tiêm lỗi thì phải bằng 0)", not {k: v for k, v in got.items() if k not in exp and v},
        {k: v for k, v in got.items() if k not in exp and v})
    add("Mọi quy tắc trong cấu hình đều chạy được", not any(r.warnings for r in results), [w for r in results for w in r.warnings])
    m = fr["metrics"].set_index("rule_id")
    add("Chỉ số tham chiếu C8 (độ phủ) và S6 (tổng review_count) khớp tính tay",
        (m.loc["C8", "numerator"], m.loc["C8", "denominator"], m.loc["S6", "numerator"], m.loc["S6", "denominator"])
        == (aux["coverage_num"], aux["coverage_den"], aux["biz_sum_review_count"], aux["n_reviews"]))
    t4 = rl.loc[("business", "T4")]
    add("Quy tắc chỉ báo cáo (T4) không xếp hạng", (t4["n_units"], t4["n_violations"], t4["grade"]) == (aux["T4_n"], aux["T4_violating"], REPORT))
    add("Duy nhất chỉ đếm bản dư thừa (6 dòng thuộc khóa trùng, 3 lỗi)",
        aux["frames"]["review"]["review_id"].duplicated(keep=False).sum() == 6 and got[("review", "U1")] == 3)
    n = next(r.n_rows for r in results if r.table == "checkin")
    c5, u1 = rl.loc[("checkin", "C5")], rl.loc[("checkin", "U1")]
    add("Điểm quy tắc = 1 − False/(True+False); ô N/A không được xét",
        c5["n_units"] == 2 * n and abs(c5["score"] - (1 - 2 / (2 * n))) < 1e-12 and u1["n_units"] == n - 2, (c5["n_units"], u1["n_units"], n))
    ok, why = True, []
    for _, a in fr["aspects"][fr["aspects"]["status"] == "Đo được"].iterrows():
        rr = fr["rules"][(fr["rules"]["table"] == a["table"]) & (fr["rules"]["aspect"] == a["aspect"]) & (fr["rules"]["level"] != "report") & (fr["rules"]["n_units"] > 0)]
        star_bad = ((rr["level"] == "star") & (rr["grade"] == BAD)).any()
        if abs(a["score"] - rr["score"].mean()) > 1e-12 or bool(a["flag"]) != bool(star_bad):
            ok = False
            why.append((a["table"], a["aspect"]))
    add("Điểm khía cạnh = trung bình điểm các quy tắc xếp hạng; cờ ⚑ đúng khi có quy tắc ★ ở mức Tệ", ok, why)
    na = fr["aspects"][fr["aspects"]["status"] == "N/A"]
    add("Khía cạnh không áp dụng đều có lý do (Chính xác ở cả 5 bảng)",
        set(na["aspect"]) == {"Chính xác"} and len(na) == 5 and na["note"].astype(str).str.len().gt(10).all())

    # ngữ nghĩa từng hàm kiểm tra: ô nào True / False / N/A
    FMT = cfg["reference"]["datetime_format"]

    def call(name, df, ctx=None, **p):
        rc = RuleCtx(df=df, p=p, ctx=ctx or Context(), ref={"datetime_format": FMT}, t_start=pd.Timestamp("2005-02-16"), t_end=pd.Timestamp("2022-01-20"))
        return SPECS[name]["fn"](rc).cells
    ctx = Context()
    ctx.key_index["business.business_id"] = pd.Index(["a", "b"])
    ctx.series["user.yelping_since"] = pd.Series({"u1": pd.Timestamp("2010-01-01")})
    ctx.series["ref"] = pd.Series({"a": 8.0, "b": 8.0})
    x = pd.DataFrame({"x": ["3", "abc", "-1", "2.5", None]})
    dts = pd.DataFrame({"d": ["2005-02-16 00:00:00", "2005-02-15 23:59:59", "2022-01-19 23:59:59", "2022-01-20 00:00:00", "zzz", None]})
    T, F, N = TRUE, FALSE, NA
    cases = [
        ("Đầy đủ/Hợp lệ: ô thiếu hoặc rỗng là N/A ở regex; sai kiểu chỉ bị dtype bắt, range bỏ qua ô không phải số",
         call("regex", pd.DataFrame({"x": ["A" * 22, "bad", None, "   "]}), column="x", pattern="[A-Za-z0-9_-]{22}")["x"].tolist() == [T, F, N, N]
         and call("dtype", x, column="x", kind="numeric")["x"].tolist() == [T, F, T, T, N]
         and call("range", x, column="x", min=0, integer=True)["x"].tolist() == [T, N, F, F, N]),
        ("Kịp thời: gồm hết ngày T_ref, cận dưới riêng của T2",
         call("in_window", dts, column="d")["d"].tolist() == [T, F, T, F, N, N]
         and call("in_window", dts, column="d", t_start="2004-07-01")["d"].tolist() == [T, T, T, F, N, N]),
        ("Duy nhất: khóa ghép là một ô; lần đầu True, bản sau False, khóa thiếu N/A",
         call("unique", pd.DataFrame({"a": ["k", "k", "k", "m", None, None], "b": [1, 1, 2, 3, 4, 4]}), keys=["a", "b"])["(a, b)"].tolist() == [T, F, T, T, N, N]),
        ("Nhất quán: khóa ngoại (mồ côi False) và ngày ≥ ngày tra cứu",
         call("fk", pd.DataFrame({"x": ["a", "z", None]}), ctx, column="x", ref="business.business_id")["x"].tolist() == [T, F, N]
         and call("date_ge_lookup", pd.DataFrame({"user_id": ["u1", "u1", "uX"], "date": ["2010-01-01 00:00:00", "2009-12-31 23:59:59", "2011-01-01 00:00:00"]}),
                  ctx, column="date", key="user_id", lookup="user.yelping_since")["date"].tolist() == [T, F, N]),
        ("Nhất quán: đối chiếu số liệu liên bảng (at_least / two_sided)",
         call("ref_compare", pd.DataFrame({"k": ["a", "b", "zz"], "v": [3, 20, 5]}), ctx, column="v", key="k", ref="ref", mode="at_least", tol_abs=0)["v"].tolist() == [F, T, N]
         and call("ref_compare", pd.DataFrame({"k": ["a", "b", "zz"], "v": [3, 20, 5]}), ctx, column="v", key="k", ref="ref", mode="two_sided", tol_abs=0)["v"].tolist() == [F, F, N]),
    ]
    for name, ok in cases:
        add(name, ok)
    # quy tắc ★ Tệ gắn cờ khía cạnh dù điểm trung bình vẫn Tốt
    asp = {k: {"good": g, "bad": b} for k, (g, b) in {"Đầy đủ": (.98, .95), "Hợp lệ": (.99, .95), "Duy nhất": (.99, .95), "Nhất quán": (.99, .95), "Chính xác": (.9, .8), "Kịp thời": (.99, .95)}.items()}
    mini = {"run": {"n_sample": 5}, "reference": cfg["reference"], "thresholds": {"star": {"good": .999, "bad": .99}, "aspect": asp},
            "tables": {"t": {"keys": ["a"], "rules": [
                {"id": "V4", "aspect": "Hợp lệ", "type": "range", "level": "star", "column": "b", "min": 0},
                {"id": "V7", "aspect": "Hợp lệ", "type": "range", "level": "general", "column": "a", "min": 0}]}}}
    r = evaluate_table(mini, "t", pd.DataFrame({"a": [1] * 200, "b": [1] * 197 + [-1] * 3}), {}, Context())
    a = next(x for x in r.aspects if x["aspect"] == "Hợp lệ")
    add("Quy tắc ★ ở mức Tệ gắn cờ ⚑ dù điểm trung bình khía cạnh vẫn Tốt",
        abs(a["score"] - (0.985 + 1.0) / 2) < 1e-9 and a["grade"] == GOOD and a["flag"] is True, (a["score"], a["grade"], a["flag"]))
    add("Mỗi loại kiểm tra đều có mô tả True/False/N/A và lý do", all(str(s_[f]).strip() for s_ in SPECS.values() for f in ("true", "false", "na", "why")))
    return out


# =====================================================================================
# 6. CHẠY
# =====================================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="Đánh giá CLDL thô cho dữ liệu Yelp, sinh notebook báo cáo")
    ap.add_argument("--data-dir", help="thư mục chứa 5 file .parquet (mặc định: run.data_dir trong CONFIG_YAML)")
    ap.add_argument("--out", help="thư mục chứa notebook báo cáo (mặc định: thư mục hiện tại)")
    ap.add_argument("--tables", help="chỉ đo vài bảng, cách nhau dấu phẩy")
    ap.add_argument("--no-selftest", action="store_true", help="bỏ qua bước tự kiểm code")
    ap.add_argument("--selftest", action="store_true", help="chỉ tự kiểm code bằng dữ liệu giả rồi thoát")
    a = ap.parse_args(argv)
    cfg = load_config(a.data_dir, a.out)
    if a.selftest:
        res = selftest(cfg)
        for c in res:
            print(("[OK]  " if c["ok"] else "[LỖI] ") + c["name"] + ("" if c["ok"] else f"  -> {c['detail']}"))
        print(f"{sum(c['ok'] for c in res)}/{len(res)} đạt")
        raise SystemExit(0 if all(c["ok"] for c in res) else 1)
    run(cfg, a.tables.split(",") if a.tables else None, check=not a.no_selftest)


if __name__ == "__main__":
    main()