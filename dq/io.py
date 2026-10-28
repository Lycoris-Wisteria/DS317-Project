"""Đọc parquet. Giữ NGUYÊN kiểu thô: không ép sai kiểu thành NaN ở bước nạp (tránh lỗi che khuất của notebook cũ).

Cột 'nặng' (vd. review.text) không nạp vào DataFrame; chỉ tính mặt nạ 'có giá trị' theo batch phục vụ Đầy đủ.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


def table_path(cfg: dict, table: str) -> Path:
    base = Path(cfg["run"]["data_dir"])
    return base / cfg["tables"][table]["file"]


def table_columns(cfg: dict, table: str) -> list[str]:
    return pq.ParquetFile(table_path(cfg, table)).schema_arrow.names


def read_columns(cfg: dict, table: str, columns: list[str]) -> pd.DataFrame:
    cols = [c for c in columns if c in table_columns(cfg, table)]
    return pd.read_parquet(table_path(cfg, table), columns=cols)


def heavy_present(cfg: dict, table: str, col: str, allow_empty: bool = False) -> np.ndarray:
    """Mặt nạ 'có giá trị' của một cột nặng, đọc theo batch để không tốn RAM."""
    pf = pq.ParquetFile(table_path(cfg, table))
    out = []
    for batch in pf.iter_batches(columns=[col], batch_size=200_000):
        arr = batch.column(0)
        ok = pc.is_valid(arr)
        if not allow_empty and (pa.types.is_string(arr.type) or pa.types.is_large_string(arr.type)):
            nonblank = pc.invert(pc.equal(pc.utf8_trim_whitespace(arr), ""))
            ok = pc.and_(ok, pc.fill_null(nonblank, False))
        out.append(ok.to_numpy(zero_copy_only=False).astype(bool))
    return np.concatenate(out) if out else np.zeros(0, dtype=bool)


def load_table(cfg: dict, table: str) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Trả về (DataFrame các cột nhẹ, {cột nặng: mặt nạ present})."""
    tc = cfg["tables"][table]
    heavy = list(tc.get("heavy_columns", []))
    all_cols = table_columns(cfg, table)
    light = [c for c in all_cols if c not in heavy]
    df = pd.read_parquet(table_path(cfg, table), columns=light)
    hp = {}
    for c in heavy:
        if c in all_cols:
            allow = bool(tc.get("columns", {}).get(c, {}).get("allow_empty", False))
            hp[c] = heavy_present(cfg, table, c, allow)
            if len(hp[c]) != len(df):
                raise ValueError(f"{table}.{c}: số dòng cột nặng {len(hp[c])} != {len(df)}")
    return df, hp
