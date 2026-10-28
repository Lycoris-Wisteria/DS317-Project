"""Lõi đánh giá, bám "Báo cáo đo lường CLDL" (Phần A.1) và TEMPO-DQ.

  điểm quy tắc   = 1 - (số ô False) / (số ô True + số ô False)                       [đơn vị = ô]
  điểm khía cạnh = trung bình các quy tắc CÙNG khía cạnh (bỏ quy tắc "chỉ báo cáo")   [báo cáo A.1]
  xếp hạng       = Tốt / Chú ý / Tệ theo ngưỡng (Bảng A.1); quy tắc ★ dùng ngưỡng cứng
  cờ ⚑           = khía cạnh bị gắn cờ nếu có quy tắc ★ rơi vào "Tệ" dù điểm trung bình cao

Điểm đối chiếu TEMPO-DQ (bổ sung, không dùng xếp hạng): trung bình cộng theo GRAIN (Eq.1-4) và Đầy đủ Eq.(2) trên mọi cột.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import ASPECTS
from .rules import SPECS, RuleCtx, RuleOut
from .utils import as_datetime, present, short

SUPP_EQ2 = "Đầy đủ (Eq.2, mọi cột)"
GOOD, WARN, BAD, REPORT, NOTE = "Tốt", "Chú ý", "Tệ", "Chỉ báo cáo", "N/A"
ACTION = {GOOD: "Dùng trực tiếp", WARN: "Ghi nhận, gắn cờ hoặc xử lý nhẹ", BAD: "Phải sửa / điền / loại trước khi dùng"}


def grade_of(score: float, good: float, bad: float) -> str:
    if score is None or np.isnan(score):
        return NOTE
    return GOOD if score >= good else (WARN if score >= bad else BAD)


def rule_thresholds(cfg: dict, r: dict) -> tuple[float, float]:
    th = cfg["thresholds"]
    base = th["star"] if r.get("level") == "star" else th["aspect"][r["aspect"]]
    merged = {**base, **(r.get("thresholds") or {})}
    return float(merged["good"]), float(merged["bad"])


class Acc:
    """Cộng dồn theo GRAIN (điểm đối chiếu TEMPO-DQ): số ô được xét và số ô vi phạm của từng grain."""

    def __init__(self, n: int):
        self.n, self.chk, self.fail = n, {}, {}

    def add(self, key: str, appl: np.ndarray, viol: np.ndarray):
        if key not in self.chk:
            self.chk[key] = np.zeros(self.n, dtype=np.float32)
            self.fail[key] = np.zeros(self.n, dtype=np.float32)
        self.chk[key] += appl.astype(np.float32)
        self.fail[key] += (viol & appl).astype(np.float32)

    def grain_score(self, key: str):
        if key not in self.chk:
            return None, 0
        m = self.chk[key] > 0
        if not m.any():
            return None, 0
        return float(np.mean(1.0 - self.fail[key][m].astype(np.float64) / self.chk[key][m])), int(m.sum())


@dataclass
class TableResult:
    table: str
    n_rows: int
    rules: list = field(default_factory=list)       # một dòng / quy tắc
    by_label: list = field(default_factory=list)    # một dòng / (quy tắc, cột)
    aspects: list = field(default_factory=list)     # một dòng / khía cạnh
    metrics: list = field(default_factory=list)     # số liệu tham khảo
    samples: list = field(default_factory=list)
    profile: list = field(default_factory=list)
    eq2_cols: list = field(default_factory=list)
    warnings: list = field(default_factory=list)   # vấn đề cấu hình/thiếu dữ liệu (quy tắc bị bỏ qua)
    notes: list = field(default_factory=list)      # thông tin, không phải lỗi


def _items(r: dict, df_cols: list[str], heavy: dict):
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
    spec = SPECS[r["type"]]
    mk = lambda p: RuleCtx(df=df, p=p, ctx=ctx, ref=ref, t_start=t_start, t_end=t_end, heavy=heavy)
    base = {k: v for k, v in r.items() if k not in ("columns", "columns_prefix")}
    items = _items(r, list(df.columns), heavy)
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
        extra_cols = [p.get(k) for k in ("key", "other", "state")]
        miss = [c for c in [col] + extra_cols if c and c not in df.columns and c not in heavy]
        if miss:
            warnings.append(f"{r['id']}: bỏ qua cột {miss} (không có trong bảng)")
            continue
        out = spec["fn"](mk(p))
        merged.cells.update(out.cells)
        merged.flagged += out.flagged
        merged.metrics += out.metrics
        merged.extra.update(out.extra)
    return merged if (merged.cells or merged.metrics) else None


def _label_values(df, label, keys, pos):
    if label in df.columns:
        return df[label].iloc[pos].tolist()
    inner = [k.strip() for k in label.strip("()").split(",")]
    if all(k in df.columns for k in inner):
        return ["; ".join(f"{k}={short(df[k].iloc[p], 25)}" for k in inner) for p in pos]
    return [None] * len(pos)


def evaluate_table(cfg: dict, table: str, df: pd.DataFrame, heavy: dict[str, np.ndarray], ctx) -> TableResult:
    tc, ref = cfg["tables"][table], cfg["reference"]
    n = len(df)
    res = TableResult(table=table, n_rows=n)
    t_start = pd.Timestamp(ref["T_start"])
    t_end = pd.Timestamp(ref["T_ref"]) + pd.Timedelta(days=1)
    n_sample = int(cfg["run"].get("n_sample", 20))
    keys = tc.get("keys", [])
    acc = Acc(n)

    # ------------------------------------------------------------ các quy tắc
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
        for label, t in out.cells.items():
            u, v = int((t >= 0).sum()), int((t == 0).sum())
            units, viol = units + u, viol + v
            res.by_label.append({"table": table, "rule_id": rid, "aspect": aspect, "label": label, "n_units": u, "n_violations": v,
                                 "score": 1 - v / u if u else np.nan})
            if level != "report":
                acc.add(aspect, t >= 0, t == 0)
            if v:
                pos_all = np.flatnonzero(t == 0)
                if label in df.columns:
                    vc = df[label].iloc[pos_all[:200_000]].astype(str).map(lambda x: short(x, 30)).value_counts().head(5)
                    tops.append(f"{label}: " + "; ".join(f"{k}×{c}" for k, c in vc.items()))
                pos = pos_all[:n_sample]
                vals = _label_values(df, label, keys, pos) if label not in heavy else ["<thiếu>"] * len(pos)
                kc = [k for k in keys if k in df.columns]
                ex = out.extra.get(label)
                for i, p in enumerate(pos):
                    res.samples.append({"table": table, "rule_id": rid, "aspect": aspect, "row_position": int(p),
                                        "record": "; ".join(f"{k}={short(df[k].iloc[p], 40)}" for k in kc),
                                        "cell": label, "value": short(vals[i]),
                                        "reference_name": ex[0] if ex else None,
                                        "reference_value": short(ex[1][p]) if ex else None})
        for m in out.metrics:
            res.metrics.append({"table": table, "rule_id": rid, **m})
        row.update(n_units=units, n_violations=viol, n_flagged=out.flagged, top_values=" | ".join(tops))
        if units:
            row["score"] = 1 - viol / units
        if level == "report":
            row["grade"] = REPORT
            row["action"] = REPORT
        elif units:
            row["grade"] = grade_of(row["score"], good, bad)
            row["action"] = "Xử lý mọi vi phạm (quy tắc ★)" if (level == "star" and viol) else (
                ACTION[GOOD] if level == "star" else ACTION[row["grade"]])
        res.rules.append(row)

    # ------------------------------------------------------------ Đầy đủ theo TEMPO-DQ Eq.(2) trên MỌI cột (đối chiếu)
    allow = set(tc.get("allow_empty_columns", []))
    c_rules = {}
    for rr in res.rules:
        if rr["aspect"] == "Đầy đủ" and rr["type"] == "not_null":
            for bl in res.by_label:
                if bl["table"] == table and bl["rule_id"] == rr["rule_id"]:
                    c_rules.setdefault(bl["label"], []).append(rr["rule_id"] + ("*" if rr["level"] == "star" else ""))
    for col in list(df.columns) + [c for c in heavy if c not in df.columns]:
        pres = heavy[col] if col in heavy else present(df[col], col in allow)
        acc.add(SUPP_EQ2, np.ones(n, dtype=bool), ~pres)
        res.eq2_cols.append({"table": table, "column": col, "n_missing": int((~pres).sum()), "ratio_missing": float((~pres).mean()) if n else np.nan,
                             "covered_by_rules": ",".join(c_rules.get(col, [])) or "—"})
    unc = [e["column"] for e in res.eq2_cols if e["covered_by_rules"] == "—"]
    if unc:
        res.notes.append(f"cột không thuộc quy tắc Đầy đủ nào của báo cáo (chỉ có trong điểm đối chiếu Eq.2): {', '.join(unc)}")

    # ------------------------------------------------------------ hồ sơ thời gian (thông tin)
    for col in tc.get("time_columns", []):
        if col not in df.columns:
            continue
        d = as_datetime(df[col], ref.get("datetime_format")).dropna()
        if len(d):
            # cận dưới riêng của quy tắc in_window trên cột này (vd. T2: 2004-07-01), nếu có
            own = next((r.get("t_start") for r in tc["rules"] if r.get("type") == "in_window" and r.get("column") == col and r.get("t_start")), None)
            lo = pd.Timestamp(own) if own else t_start
            yr = d.dt.year.value_counts().sort_index()
            res.profile.append({"table": table, "column": col, "n": int(len(d)), "min": d.min(), "max": d.max(),
                                "n_after_T_ref": int((d >= t_end).sum()), "n_before_T_start": int((d < lo).sum()),
                                "by_year": {int(k): int(v) for k, v in yr.items()}})

    # ------------------------------------------------------------ điểm khía cạnh
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
        units, viol = sum(r["n_units"] for r in rr), sum(r["n_violations"] for r in rr)
        gs, ng = acc.grain_score(aspect)
        row.update(status="Đo được", n_rules=len(rr), score=score, grade=grade_of(score, g, bd), flagged_rules=",".join(flagged),
                   flag=bool(flagged), min_rule_score=float(min(r["score"] for r in rr)),
                   n_units=units, n_violations=viol, score_pooled=1 - viol / units, score_grain_tempo=gs, n_grains=ng,
                   note=na.get(aspect, ""))
        res.aspects.append(row)
    gs, ng = acc.grain_score(SUPP_EQ2)
    res.aspects.append({"table": table, "aspect": SUPP_EQ2, "status": "Bổ sung", "score": gs, "n_grains": ng,
                        "note": "TEMPO-DQ Eq.(2): trung bình cộng theo grain trên mọi cột; không dùng để xếp hạng"})
    return res
