"""Xuất kết quả: CSV, biểu đồ, báo cáo markdown TỰ SINH (mọi con số lấy từ lần chạy, không gõ tay)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import ASPECTS
from .engine import BAD, GOOD, NOTE, REPORT, SUPP_EQ2, WARN

INK, MUTED = "#1f2937", "#6b7280"
GRADE_COLOR = {GOOD: "#2a6fb0", WARN: "#b9770e", BAD: "#c0392b"}


def vn(x, d=6) -> str:
    """Số kiểu Việt Nam (dấu phẩy thập phân)."""
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}".replace(".", ",")


def build_frames(results: list) -> dict[str, pd.DataFrame]:
    rules = pd.DataFrame([r for tr in results for r in tr.rules])
    by_label = pd.DataFrame([r for tr in results for r in tr.by_label])
    aspects = pd.DataFrame([r for tr in results for r in tr.aspects])
    metrics = pd.DataFrame([r for tr in results for r in tr.metrics])
    samples = pd.DataFrame([r for tr in results for r in tr.samples])
    eq2 = pd.DataFrame([r for tr in results for r in tr.eq2_cols])
    prof = []
    for tr in results:
        for p in tr.profile:
            q = dict(p)
            q["by_year"] = json.dumps(q["by_year"])
            prof.append(q)
    rows = []
    main = aspects[aspects["aspect"].isin(ASPECTS) & (aspects["status"] == "Đo được")] if len(aspects) else aspects
    for a in ASPECTS:
        s = main[main["aspect"] == a] if len(main) else main
        if len(s) == 0:
            continue
        sc = float(s["score"].mean())
        g, b = float(s["good"].iloc[0]), float(s["bad"].iloc[0])
        from .engine import grade_of
        rows.append({"aspect": a, "n_tables": len(s), "tables": ",".join(s["table"]), "score": sc, "grade": grade_of(sc, g, b),
                     "flag": bool(s["flag"].any()), "flagged_tables": ",".join(s[s["flag"]]["table"])})
    return {"rules": rules, "by_label": by_label, "aspects": aspects, "dataset": pd.DataFrame(rows), "metrics": metrics,
            "samples": samples, "profile": pd.DataFrame(prof), "eq2": eq2}


FILES = {"rules": "results_rules.csv", "by_label": "results_by_cell_column.csv", "aspects": "results_aspects.csv",
         "dataset": "results_dataset.csv", "metrics": "results_metrics.csv", "samples": "violation_samples.csv",
         "profile": "temporal_profile.csv", "eq2": "tempo_dq_eq2_by_column.csv"}


def save_all(frames: dict[str, pd.DataFrame], out: Path, meta: dict):
    out.mkdir(parents=True, exist_ok=True)
    for k, fn in FILES.items():
        frames[k].to_csv(out / fn, index=False, encoding="utf-8-sig")
    (out / "run_metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def plot_table(aspects: pd.DataFrame, table: str, out: Path):
    """Biểu đồ chấm: mỗi khía cạnh một chấm tại điểm của nó (màu + chữ theo xếp hạng); vạch xám = ngưỡng Chú ý và Tốt của khía cạnh đó.
    Điểm dồn sát 1 nên trục bắt đầu gần ngưỡng thấp nhất (không dùng cột cụt gốc để tránh gây hiểu lầm)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

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
        ax.text(1.0 + (1 - lo) * 0.025, yi, f"{vn(v, 6)} · {r['grade']}" + ("  ⚑" if r["flag"] is True else ""), va="center", ha="left",
                color=INK, fontsize=10, fontweight="bold" if r["grade"] == BAD else "normal", clip_on=False)
    ax.set_yticks(y)
    ax.set_yticklabels(ASPECTS, color=INK)
    ax.set_xlim(lo, 1.0)
    ax.set_ylim(-0.6, len(ASPECTS) - 0.4)
    ax.set_xlabel("Điểm khía cạnh = trung bình điểm các quy tắc cùng khía cạnh. Vạch: ngưỡng Chú ý (nhạt) và Tốt (đậm). ⚑ = có quy tắc ★ ở mức Tệ", color=MUTED, fontsize=8)
    ax.set_title(f"Bảng {table}", loc="left", color=INK, fontsize=12, fontweight="bold")
    ax.grid(axis="x", color="#eef0f2", lw=0.8, zorder=0)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.subplots_adjust(left=0.13, right=0.78, top=0.90, bottom=0.17)
    fig.savefig(out / f"chart_{table}.png", dpi=150)
    plt.close(fig)


def markdown_report(frames: dict[str, pd.DataFrame], results: list, meta: dict, cfg: dict) -> str:
    asp, rl, ds, mt, pf = frames["aspects"], frames["rules"], frames["dataset"], frames["metrics"], frames["profile"]
    th = cfg["thresholds"]
    L = [f"# Báo cáo chất lượng dữ liệu Yelp — {meta['label']}", "",
         f"- Chạy lúc {meta['run_at']} · mốc snapshot T_ref = {meta['T_ref']} · khung Kịp thời [{meta['T_start']}; {meta['T_ref']}] · code {meta['version']}",
         f"- Cấu hình `{meta['config_path']}` (sha256 {meta['config_sha256'][:12]})",
         "- **Cách tính** (báo cáo CLDL, A.1): điểm quy tắc = 1 − (số ô lỗi / tổng số ô được xét); điểm khía cạnh = trung bình các quy tắc cùng khía cạnh "
         "(bỏ quy tắc *chỉ báo cáo*); khía cạnh bị gắn cờ ⚑ nếu có quy tắc ★ ở mức Tệ dù điểm trung bình cao.",
         "- **Xếp hạng** (Bảng A.1): " + "; ".join(f"{a}: Tốt ≥ {vn(v['good'], 2)}, Tệ < {vn(v['bad'], 2)}" for a, v in th["aspect"].items())
         + f"; quy tắc ★: Tốt ≥ {vn(th['star']['good'], 3)}, Tệ < {vn(th['star']['bad'], 2)}.",
         "", "## 1. Điểm khía cạnh theo bảng", ""]
    L.append("| Bảng (số dòng) | " + " | ".join(ASPECTS) + " |")
    L.append("|---|" + "---:|" * len(ASPECTS))
    for tr in results:
        cells = []
        for a in ASPECTS:
            r = asp[(asp["table"] == tr.table) & (asp["aspect"] == a)].iloc[0]
            if r["status"] == "Đo được":
                cells.append(f"{vn(r['score'])} · {r['grade']}" + (" ⚑" if r["flag"] else ""))
            else:
                cells.append("N/A" if r["status"] == NOTE else "chỉ báo cáo")
        L.append(f"| {tr.table} ({tr.n_rows:,}) | " + " | ".join(cells) + " |")
    if len(ds):
        L += ["", "Mức bộ dữ liệu (trung bình cộng điểm các bảng đo được): " + "; ".join(
            f"{r['aspect']} {vn(r['score'])} · {r['grade']}" + (" ⚑" if r["flag"] else "") for _, r in ds.iterrows()) + "."]
    L += ["", "## 2. Chi tiết từng quy tắc", "",
          "Đơn vị = ô (khóa ghép U2–U4 tính một ô tổ hợp). `Vi phạm` = số ô False. ★ = quy tắc cứng.", ""]
    for tr in results:
        sub = rl[rl["table"] == tr.table]
        L += [f"### {tr.table}", "", "| Mã | Khía cạnh | Phạm vi | Quy tắc | Ô xét | Vi phạm | Điểm | Xếp hạng | Xử lý |", "|---|---|---|---|---:|---:|---:|---|---|"]
        for _, r in sub.iterrows():
            mark = "★ " if r["level"] == "star" else ""
            extra = f" (⚠ {int(r['n_flagged'])} ô cần kiểm chứng)" if r["n_flagged"] else ""
            L.append(f"| {mark}{r['rule_id']} | {r['aspect']} | {r['scope']} | {r['desc']}{extra} | {int(r['n_units']):,} | {int(r['n_violations']):,} | "
                     f"{vn(r['score'])} | {r['grade']} | {r['action']} |")
        L.append("")
    need = rl[(rl["grade"] == BAD) | ((rl["level"] == "star") & (rl["n_violations"] > 0))]
    L += ["## 3. Quy tắc cần xử lý", ""]
    if len(need):
        L += ["| Bảng | Mã | Khía cạnh | Vi phạm | Điểm | Xếp hạng | Giá trị vi phạm phổ biến |", "|---|---|---|---:|---:|---|---|"]
        for _, r in need.sort_values("n_violations", ascending=False).iterrows():
            L.append(f"| {r['table']} | {'★ ' if r['level'] == 'star' else ''}{r['rule_id']} | {r['aspect']} | {int(r['n_violations']):,} | {vn(r['score'])} | {r['grade']} | {r['top_values'] or '—'} |")
    else:
        L.append("Không có quy tắc ★ nào bị vi phạm và không có quy tắc nào ở mức Tệ.")
    rep = rl[rl["level"] == "report"]
    L += ["", "## 4. Chỉ báo cáo (không xếp hạng)", ""]
    for _, r in rep.iterrows():
        if r["n_units"]:
            L.append(f"- **{r['table']} · {r['rule_id']}** — {r['desc']}: {int(r['n_violations']):,}/{int(r['n_units']):,} ô → tỷ lệ đạt {vn(r['score'], 4)}.")
    for _, m in mt.iterrows():
        L.append(f"- **{m['table']} · {m['rule_id']}** — {m['metric']}: {vn(m['value'], 4)} ({m['numerator']:,.0f}/{m['denominator']:,.0f}); {m['note']}.")
    L += ["", "## 5. Khía cạnh không áp dụng và cảnh báo cấu hình", ""]
    for _, r in asp[asp["aspect"].isin(ASPECTS) & (asp["status"] != "Đo được")].iterrows():
        L.append(f"- **{r['table']} · {r['aspect']}**: {r['note']}")
    for tr in results:
        for w in tr.warnings:
            L.append(f"- ⚠ **{tr.table}**: {w}")
    for tr in results:
        for w in tr.notes:
            L.append(f"- ℹ **{tr.table}**: {w}")
    if len(pf):
        L += ["", "## 6. Hồ sơ thời gian (thông tin)", "", "| Bảng | Cột | Số mốc | Sớm nhất | Muộn nhất | Sau T_ref | Trước T_start |", "|---|---|---:|---|---|---:|---:|"]
        for _, r in pf.iterrows():
            L.append(f"| {r['table']} | {r['column']} | {int(r['n']):,} | {r['min']} | {r['max']} | {int(r['n_after_T_ref']):,} | {int(r['n_before_T_start']):,} |")
    eq = asp[asp["aspect"] == SUPP_EQ2]
    L += ["", "## 7. Đối chiếu với TEMPO-DQ (không dùng xếp hạng)", "",
          "Điểm Đầy đủ Eq.(2) trung bình cộng theo grain trên **mọi** cột, và điểm theo grain của các khía cạnh (Eq.1–4):", "",
          "| Bảng | Đầy đủ Eq.(2) | " + " | ".join(f"{a} (grain)" for a in ASPECTS) + " |", "|---|---:|" + "---:|" * len(ASPECTS)]
    for tr in results:
        e = eq[eq["table"] == tr.table]
        a = asp[(asp["table"] == tr.table) & asp["aspect"].isin(ASPECTS)].set_index("aspect")
        cells = [vn(a.loc[x, "score_grain_tempo"]) if a.loc[x, "status"] == "Đo được" else "N/A" for x in ASPECTS]
        L.append(f"| {tr.table} | {vn(e.iloc[0]['score'] if len(e) else None)} | " + " | ".join(cells) + " |")
    L += ["", "Mẫu ô lỗi: `violation_samples.csv`. Định nghĩa độ đo: `METRICS.md`. Danh mục quy tắc: `RULES.md`.", ""]
    return "\n".join(L)
