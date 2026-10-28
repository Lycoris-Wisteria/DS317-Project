"""Các hàm kiểm tra (rule type). MỖI HÀM TRẢ VỀ MỘT MẢNG BA TRẠNG THÁI cho từng ô được xét:

    1  = True  : ô ĐẠT quy tắc
    0  = False : ô VI PHẠM quy tắc
   -1  = N/A   : ô không được xét (không tính vào tử số lẫn mẫu số)

Đơn vị đếm là Ô (một giá trị của một cột trong một dòng), trừ khóa ghép (U2-U4) coi bộ cột khóa của
một dòng là MỘT ô tổ hợp. Điểm quy tắc = 1 - (số ô False) / (số ô True + số ô False).

Mỗi hàm gắn @rule_type(...) ghi rõ: khi nào True, khi nào False, khi nào N/A, VÌ SAO, và NGUỒN của quy tắc.
`python -m dq.catalog` in các mô tả này ra RULES.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .utils import as_datetime, norm_text, parse_object, present, row_any, to_num

TRUE, FALSE, NA = 1, 0, -1
SPECS: dict[str, dict] = {}


def rule_type(name, *, aspects, true, false, na, why, source):
    def deco(fn):
        SPECS[name] = dict(fn=fn, func=fn.__name__, aspects=tuple(aspects), true=true, false=false, na=na, why=why, source=source)
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
               "`missing_tokens` chuẩn hóa giá trị mang nghĩa 'không có' (elite = '' ; friends = 'None') trước khi tính tỷ lệ thiếu (ghi chú C7).",
           source="Báo cáo CLDL C1-C7; TEMPO-DQ Eq.(2)")
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
           why="Độ phủ = số business_id khác nhau của bảng này nằm trong business / tổng số business. Cho biết bảng này không phủ hết POI.",
           source="Báo cáo CLDL C8 (chỉ báo cáo)")
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
           why="Data Type của paper. Giá trị sai kiểu chỉ bị đếm ở đây, không bị biến thành NaN rồi đếm ở Đầy đủ.",
           source="Báo cáo CLDL V6; TEMPO-DQ Eq.(3) 'Data Type'")
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
           why="Domain Range của paper. Ngưỡng cụ thể lấy từ từ điển dữ liệu của nhóm (báo cáo CLDL).",
           source="Báo cáo CLDL V2, V4, V7; TEMPO-DQ Eq.(3) 'Domain Range'")
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
           why="Domain Range dạng tập rời rạc (stars nửa sao; stars review nguyên; is_open nhị phân).",
           source="Báo cáo CLDL V3, V5")
def is_in_set(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    v = to_num(s)
    appl = v.notna().to_numpy(dtype=bool) & present(s, False)
    return _one(c.col, appl, ~v.isin(c.p["values"]).to_numpy(dtype=bool))


@rule_type("regex", aspects=["Hợp lệ"],
           true="toàn bộ chuỗi khớp `pattern` (fullmatch)", false="ô có giá trị nhưng không khớp pattern",
           na="ô thiếu (với allow_empty=true thì chuỗi rỗng vẫn được xét)",
           why="Kiểm định dạng. Id Yelp là chuỗi 22 ký tự [A-Za-z0-9_-]; state là 2 chữ in hoa; elite là danh sách năm 4 chữ số; friends là 'None' hoặc danh sách id.",
           source="Báo cáo CLDL V1, V8, V9, V11")
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
               "nên hàm bóc ngoặc và dấu nháy trước khi kiểm từng phần tử, thay vì giả định một dạng phân cách cố định.",
           source="Báo cáo CLDL V11")
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
           why="postal_code phải giữ kiểu chuỗi vì có số 0 đầu và mã Canada có chữ.",
           source="Báo cáo CLDL V12 (postal_code)")
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
           why="Cột attributes lồng nhau phải parse được thì mới dùng làm đặc trưng.",
           source="Báo cáo CLDL V12 (attributes)")
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
           why="Khung '0:0-0:0' KHÔNG tính là lỗi mà được gắn nhãn 'cần kiểm chứng' (đếm riêng ở n_flagged).",
           source="Báo cáo CLDL V10")
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
               "Khóa ghép được coi là MỘT ô tổ hợp nên không bị nhân đôi theo số cột khóa.",
           source="TEMPO-DQ Eq.(3) 'Uniqueness: a_i ∉ duplicates(A)'; cách đếm bản dư thừa do nhóm chọn; Báo cáo CLDL U1-U4")
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
           why="Toàn vẹn khóa ngoại: dòng mồ côi không nối được vào đồ thị user-POI.",
           source="Báo cáo CLDL S1; TEMPO-DQ Eq.(3) 'Foreign Key Integrity'")
def is_in_reference(c: RuleCtx) -> RuleOut:
    s = c.df[c.col]
    return _one(c.col, present(s, False), ~s.isin(c.ctx.index(c.p["ref"])).to_numpy(dtype=bool))


@rule_type("date_ge_lookup", aspects=["Nhất quán"],
           true="mốc thời gian của ô >= giá trị tra cứu theo khóa (vd. review.date >= yelping_since của chính người viết)",
           false="mốc của ô sớm hơn giá trị tra cứu", na="ô thiếu/không parse được, hoặc không tra được giá trị (user không tồn tại)",
           why="Người dùng không thể viết review/tip trước khi đăng ký. Lỗi gắn vào ô date của dòng con (review/tip); yelping_since chỉ là tham chiếu.",
           source="Báo cáo CLDL S2; TEMPO-DQ Eq.(3) 'Logical Constraints'")
def is_not_before_lookup(c: RuleCtx) -> RuleOut:
    d = as_datetime(c.df[c.col], c.fmt)
    r = pd.to_datetime(c.df[c.p["key"]].map(c.ctx.get(c.p["lookup"])))
    tol = pd.Timedelta(days=float(c.p.get("tolerance_days", 0)))
    appl = (d.notna() & r.notna()).to_numpy(dtype=bool)
    return _one(c.col, appl, (d < (r - tol)).to_numpy(dtype=bool), extra={c.col: (c.p["lookup"], r.to_numpy())})


@rule_type("ref_compare", aspects=["Nhất quán", "Chính xác"],
           true="|giá trị - tham chiếu| <= max(tol_abs, tol_rel·|tham chiếu|); với mode='at_least': giá trị >= tham chiếu - dung sai",
           false="lệch quá dung sai", na="ô thiếu, không có tham chiếu (trừ khi có fill_missing_ref), hoặc tham chiếu dựa trên < min_n dòng",
           why="Đối chiếu chéo với số liệu tính lại từ chính bộ dữ liệu (số review, trung bình sao). at_least dùng khi file review là tập con nên review_count chỉ có thể >= số quan sát.",
           source="Báo cáo CLDL S3, S6, S7, S8")
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
           why="Một người không thể là Elite trước khi đăng ký hay sau thời điểm xuất dữ liệu.",
           source="Báo cáo CLDL S4")
def is_elite_consistent(c: RuleCtx) -> RuleOut:
    from .utils import year_lists
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
           why="Cùng một thành phố chỉ nên có một cách viết để nhóm/join theo thành phố không bị tách đôi.",
           source="Báo cáo CLDL S5 (vế 'một cách viết chuẩn')")
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
           why="city phải thuộc đúng state. Vì có thành phố trùng tên ở nhiều bang nên chỉ coi là sai khi cặp (city, state) rất hiếm so với phần còn lại.",
           source="Báo cáo CLDL S5 (vế 'thuộc đúng state'). Báo cáo KHÔNG nêu ngưỡng; share_min/min_total do công cụ đặt, cần nhóm xác nhận")
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
               "(lấy hôm nay làm mốc thì mọi bản ghi đều quá hạn). isOnTime của paper so với 'reference timestamp' = ngày xuất dữ liệu.",
           source="Báo cáo CLDL T1-T3; TEMPO-DQ Eq.(4)")
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
           why="Thước đo độ 'còn hoạt động' của POI; chỉ tham khảo, dùng khi bài toán cần doanh nghiệp còn hoạt động.",
           source="Báo cáo CLDL T4 (chỉ báo cáo)")
def is_recently_active(c: RuleCtx) -> RuleOut:
    last = c.df[c.p["key"]].map(c.ctx.get("last_activity_by_business"))
    start = c.t_end - pd.DateOffset(months=int(c.p.get("months", 24)))
    s = to_num(c.df[c.col])
    appl = (s == 1).to_numpy(dtype=bool)
    recent = (last >= start).fillna(False).to_numpy(dtype=bool)
    return _one(c.col, appl, ~recent)
