"""Sinh RULES.md từ config.yaml + mô tả hàm trong rules.py:  python -m dq.catalog --config config.yaml > RULES.md"""
from __future__ import annotations

import argparse

import yaml

from . import ASPECTS
from .rules import SPECS


def _thr(cfg: dict, r: dict) -> str:
    th = cfg["thresholds"]
    lv = r.get("level", "general")
    if lv == "report":
        return "Chỉ báo cáo"
    base = th["star"] if lv == "star" else th["aspect"][r["aspect"]]
    m = {**base, **(r.get("thresholds") or {})}
    g = f"{m['good']:g}".replace(".", ",")
    b = f"{m['bad']:g}".replace(".", ",")
    txt = ("★ " if lv == "star" else "Chung ") + f"(Tốt ≥ {g}; Tệ < {b})"
    return txt + (" · Tốt = 1" if lv == "star" and float(m["good"]) == 1.0 else "")


def catalog(cfg: dict) -> str:
    L = ["# Danh mục quy tắc đo (sinh tự động từ `config.yaml` và `dq/rules.py`)", "",
         "Mã quy tắc theo báo cáo CLDL. ★ = quy tắc cứng; *Chung* = ngưỡng chung của khía cạnh (Bảng A.1); *Chỉ báo cáo* = không xếp hạng, không vào điểm khía cạnh. "
         "Quy tắc có `from_report: false` là bổ sung ngoài báo cáo.", ""]
    # ---- quy tắc theo khía cạnh (bố cục như Bảng F.1-F.5)
    for a in ASPECTS:
        L += [f"## {a}", ""]
        rows = [(t, r) for t, tc in cfg["tables"].items() for r in tc.get("rules", []) if r["aspect"] == a]
        if rows:
            L += ["| Mã | Bảng | Phạm vi | Quy tắc | Loại hàm | Cột / khóa | Ngưỡng |", "|---|---|---|---|---|---|---|"]
            for t, r in sorted(rows, key=lambda x: (x[1]["id"][0], int("".join(c for c in x[1]["id"] if c.isdigit()) or 0), x[1]["id"], x[0])):
                cols = r.get("columns")
                col = (", ".join(cols.keys() if isinstance(cols, dict) else cols) if cols else r.get("column") or ", ".join(r.get("keys", [])))
                if r.get("columns_prefix"):
                    col += (", " if col else "") + r["columns_prefix"] + "*"
                ex = "" if r.get("from_report", True) else " *(bổ sung)*"
                L.append(f"| {r['id']} | {t} | {r.get('scope', '')} | {r.get('desc', '')}{ex} | `{r['type']}` | {col} | {_thr(cfg, r)} |")
        else:
            L.append("Không có quy tắc.")
        na = [(t, tc["not_applicable"][a]) for t, tc in cfg["tables"].items() if (tc.get("not_applicable") or {}).get(a)]
        if na:
            L += ["", "Không áp dụng / không đo:"] + [f"- **{t}**: {why}" for t, why in na]
        L.append("")
    # ---- hàm kiểm tra
    L += ["## Hàm kiểm tra: trả về gì, vì sao", "",
          "Mỗi hàm trả về cho TỪNG Ô một trong ba giá trị: **True** (ô đạt), **False** (ô vi phạm), **N/A** (ô không được xét, không vào tử số lẫn mẫu số). "
          "Điểm quy tắc = 1 − (số ô False) / (số ô True + số ô False).", "",
          "| Loại | Hàm | Khía cạnh | Trả về True khi | Trả về False khi | N/A khi | Vì sao | Nguồn |", "|---|---|---|---|---|---|---|---|"]
    for name, s in SPECS.items():
        L.append(f"| `{name}` | `{s['func']}` | {', '.join(s['aspects'])} | {s['true']} | {s['false']} | {s['na']} | {s['why']} | {s['source']} |")
    return "\n".join(L).replace("|\n\n", "|\n\n") + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    a = ap.parse_args()
    print(catalog(yaml.safe_load(open(a.config, encoding="utf-8"))))


if __name__ == "__main__":
    main()
