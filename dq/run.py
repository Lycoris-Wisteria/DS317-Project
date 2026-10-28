"""Chạy toàn bộ: python -m dq.run --config config.yaml [--data-dir DIR] [--out DIR] [--tables a,b] [--label KQ_v1] [--no-plots]"""
from __future__ import annotations

import argparse
import hashlib
import time
from datetime import datetime
from pathlib import Path

import yaml

from . import __version__
from .context import build_context
from .engine import evaluate_table
from .io import load_table, table_path
from .report import build_frames, markdown_report, plot_table, save_all


def load_config(path: str | Path, data_dir: str | None = None, out_dir: str | None = None, label: str | None = None) -> dict:
    path = Path(path)
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["_path"] = str(path)
    cfg["_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if data_dir:
        cfg["run"]["data_dir"] = data_dir
    if out_dir:
        cfg["run"]["out_dir"] = out_dir
    if label:
        cfg["run"]["label"] = label
    return cfg


def run(cfg: dict, tables: list[str] | None = None, plots: bool = True, verbose: bool = True) -> dict:
    t0 = time.time()
    all_tables = list(cfg["tables"].keys())
    wanted = tables or all_tables
    cfg["_exists"] = {t: table_path(cfg, t).exists() for t in all_tables}
    absent = [t for t in wanted if not cfg["_exists"][t]]
    if absent:
        raise FileNotFoundError(f"Không thấy file dữ liệu của bảng {absent} trong {cfg['run']['data_dir']}")

    say = print if verbose else (lambda *a, **k: None)
    say("[1/3] Dựng ngữ cảnh tham chiếu liên bảng ...")
    ctx = build_context(cfg)
    for n in ctx.notes:
        say("   ", n)

    results = []
    say("[2/3] Đánh giá từng bảng ...")
    for t in wanted:
        ts = time.time()
        df, heavy = load_table(cfg, t)
        results.append(evaluate_table(cfg, t, df, heavy, ctx))
        say(f"    {t}: {len(df):,} dòng, {time.time() - ts:.1f}s")
        del df, heavy

    say("[3/3] Xuất báo cáo ...")
    out = Path(cfg["run"]["out_dir"])
    frames = build_frames(results)
    ref = cfg["reference"]
    meta = {"label": cfg["run"].get("label", ""), "run_at": datetime.now().isoformat(timespec="seconds"), "version": __version__,
            "config_path": cfg["_path"], "config_sha256": cfg["_sha256"], "T_ref": ref["T_ref"], "T_start": ref["T_start"],
            "thresholds": cfg["thresholds"], "tables": wanted, "rows": {r.table: r.n_rows for r in results},
            "elapsed_seconds": round(time.time() - t0, 1)}
    save_all(frames, out, meta)
    if plots:
        for t in wanted:
            plot_table(frames["aspects"], t, out)
    md = markdown_report(frames, results, meta, cfg)
    (out / "report.md").write_text(md, encoding="utf-8")
    say(f"Xong trong {meta['elapsed_seconds']}s. Kết quả ở: {out.resolve()}")
    return {"frames": frames, "results": results, "meta": meta, "report_md": md}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Đánh giá chất lượng dữ liệu Yelp (báo cáo CLDL + TEMPO-DQ)")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--data-dir")
    ap.add_argument("--out")
    ap.add_argument("--label", help="nhãn lần đo, vd. KQ_v0 (dữ liệu gốc), KQ_v1 (sau cải thiện)")
    ap.add_argument("--tables", help="danh sách bảng, cách nhau dấu phẩy (mặc định: tất cả)")
    ap.add_argument("--no-plots", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config(a.config, a.data_dir, a.out, a.label)
    run(cfg, a.tables.split(",") if a.tables else None, plots=not a.no_plots)


if __name__ == "__main__":
    main()
