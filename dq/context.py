"""Ngữ cảnh tham chiếu liên bảng, tính MỘT LẦN trước khi đánh giá từng bảng.

Nhờ đó thứ tự chạy do code đảm bảo (không còn phụ thuộc biến toàn cục giữa các cell như notebook cũ).
Chỉ đọc các cột cần thiết.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .io import read_columns, table_columns
from .utils import as_datetime, to_num


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
        tcols = tcfg["review"].get("time_columns", [])
        r = read_columns(cfg, "review", ["business_id", "user_id", "stars"] + tcols)
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
                dt = as_datetime(d[tc[0]], fmt)
                d = pd.DataFrame({"business_id": d["business_id"].to_numpy(), "t": dt.to_numpy()})
                d = d[d["t"].notna() & (d["t"] < t_end)]
                parts.append(d.groupby("business_id")["t"].max())
        if parts:
            ctx.series["last_activity_by_business"] = pd.concat(parts).groupby(level=0).max()
            ctx.notes.append(f"hoạt động gần nhất theo POI: {len(ctx.series['last_activity_by_business']):,} POI")
    return ctx
