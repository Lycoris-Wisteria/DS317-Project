"""Hàm tiện ích dùng chung. Mọi hàm trả về mảng numpy theo VỊ TRÍ dòng (không theo nhãn index)."""
from __future__ import annotations

import numpy as np
import pandas as pd


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


# ----------------------------------------------------------------------------- bổ sung cho bộ quy tắc theo báo cáo CLDL
import ast
import json
import unicodedata


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
