"""So sánh trước - sau (báo cáo CLDL: KQ_v0 so với KQ_v1, như Bảng C.2).

    python -m dq.compare working_v0 working_v1 [--out so_sanh.md]

Dùng CÙNG bộ quy tắc cho hai lần đo; chỉ so sánh được khi hai lần đo cùng mã quy tắc.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import ASPECTS
from .report import vn


def compare(before: Path, after: Path) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    a0, a1 = (pd.read_csv(d / "results_aspects.csv") for d in (before, after))
    r0, r1 = (pd.read_csv(d / "results_rules.csv") for d in (before, after))
    m0, m1 = (json.loads((d / "run_metadata.json").read_text(encoding="utf-8")) for d in (before, after))
    key = ["table", "aspect"]
    asp = a0[a0["aspect"].isin(ASPECTS)][key + ["score", "grade"]].merge(
        a1[a1["aspect"].isin(ASPECTS)][key + ["score", "grade"]], on=key, how="outer", suffixes=("_trước", "_sau"))
    asp["thay_đổi"] = asp["score_sau"] - asp["score_trước"]
    rk = ["table", "rule_id"]
    rul = r0[rk + ["aspect", "level", "n_violations", "score", "grade"]].merge(
        r1[rk + ["n_violations", "score", "grade"]], on=rk, how="outer", suffixes=("_trước", "_sau"))
    rul["giảm_lỗi"] = rul["n_violations_trước"] - rul["n_violations_sau"]
    L = [f"# So sánh {m0.get('label', before.name)} → {m1.get('label', after.name)}", "",
         "## Điểm khía cạnh (trung bình các quy tắc cùng khía cạnh)", "",
         "| Bảng | Khía cạnh | Trước | Sau | Thay đổi |", "|---|---|---:|---:|---:|"]
    for _, r in asp.sort_values(["table", "aspect"], key=lambda s: s.map({a: i for i, a in enumerate(ASPECTS)}) if s.name == "aspect" else s).iterrows():
        if pd.isna(r["score_trước"]) and pd.isna(r["score_sau"]):
            continue
        L.append(f"| {r['table']} | {r['aspect']} | {vn(r['score_trước'])} ({r['grade_trước']}) | {vn(r['score_sau'])} ({r['grade_sau']}) | "
                 f"{'—' if pd.isna(r['thay_đổi']) else format(r['thay_đổi'], '+.6f').replace('.', ',')} |")
    chg = rul[rul["giảm_lỗi"].fillna(0) != 0]
    L += ["", "## Quy tắc có số lỗi thay đổi", ""]
    if len(chg):
        L += ["| Bảng | Mã | Lỗi trước | Lỗi sau | Giảm |", "|---|---|---:|---:|---:|"]
        for _, r in chg.iterrows():
            L.append(f"| {r['table']} | {r['rule_id']} | {r['n_violations_trước']:,.0f} | {r['n_violations_sau']:,.0f} | {r['giảm_lỗi']:+,.0f} |")
    else:
        L.append("Không có thay đổi.")
    return asp, rul, "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    asp, rul, md = compare(Path(a.before), Path(a.after))
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
        asp.to_csv(Path(a.out).with_suffix(".aspects.csv"), index=False, encoding="utf-8-sig")
        rul.to_csv(Path(a.out).with_suffix(".rules.csv"), index=False, encoding="utf-8-sig")
    print(md)


if __name__ == "__main__":
    main()
