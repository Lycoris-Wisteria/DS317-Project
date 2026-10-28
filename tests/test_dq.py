"""Kiểm thử v2.

(1) end-to-end trên dữ liệu tổng hợp tiêm lỗi: số ô vi phạm của MỌI quy tắc khớp kỳ vọng tính độc lập, không dương tính giả;
(2) ngữ nghĩa từng hàm kiểm tra (True / False / N/A);
(3) cách tính điểm: ô -> quy tắc -> khía cạnh -> xếp hạng, quy tắc ★, quy tắc chỉ báo cáo;
(4) tài liệu hóa hàm, cấu hình hợp lệ, so sánh trước - sau.
"""
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from dq import ASPECTS                                   # noqa: E402
from dq.catalog import catalog                           # noqa: E402
from dq.compare import compare                           # noqa: E402
from dq.context import Context                           # noqa: E402
from dq.engine import evaluate_table                     # noqa: E402
from dq.rules import FALSE, NA, SPECS, TRUE, RuleCtx     # noqa: E402
from dq.run import load_config, run                      # noqa: E402
from make_synthetic import make                          # noqa: E402

FMT = "%Y-%m-%d %H:%M:%S"


# ============================================================================= (1) end-to-end
@pytest.fixture(scope="module")
def outcome(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    exp, aux = make(d)
    out = tmp_path_factory.mktemp("out")
    cfg = load_config(ROOT / "config.yaml", data_dir=str(d), out_dir=str(out), label="KQ_v0")
    for r in cfg["tables"]["business"]["rules"]:
        if r["id"] == "S5b":
            r["share_min"] = 0.03          # tập test chỉ ~50 POI/thành phố: cặp (Phoenix, PA) chiếm ~2% nên hạ ngưỡng 1% -> 3%
    cfg0 = copy.deepcopy(cfg)
    return exp, aux, run(cfg, verbose=False), out, cfg0, d


def _got(res):
    return {(r["table"], r["rule_id"]): int(r["n_violations"]) for _, r in res["frames"]["rules"].iterrows()}


def test_violating_cells_match_independent_expectation(outcome):
    exp, _, res, *_ = outcome
    got = _got(res)
    wrong = {k: (v, got.get(k)) for k, v in exp.items() if got.get(k) != v}
    assert not wrong, f"lệch (kỳ vọng, thực tế): {wrong}"
    extra = {k: v for k, v in got.items() if k not in exp and v != 0}
    assert not extra, f"dương tính giả: {extra}"


def test_every_configured_rule_ran(outcome):
    _, _, res, *_ = outcome
    assert not (res["frames"]["rules"]["grade"] == "BỎ QUA").any()
    for t in res["results"]:
        assert not t.warnings, t.warnings


def test_coverage_c8_and_s6_total_metrics(outcome):
    _, aux, res, *_ = outcome
    m = res["frames"]["metrics"]
    c8 = m[m["rule_id"] == "C8"].iloc[0]
    assert (c8["numerator"], c8["denominator"]) == (aux["coverage_num"], aux["coverage_den"])
    s6 = m[m["rule_id"] == "S6"].iloc[0]
    assert (s6["numerator"], s6["denominator"]) == (aux["biz_sum_review_count"], aux["n_reviews"])


def test_t4_reported_not_ranked(outcome):
    _, aux, res, *_ = outcome
    r = res["frames"]["rules"].set_index(["table", "rule_id"]).loc[("business", "T4")]
    assert (r["n_units"], r["n_violations"]) == (aux["T4_n"], aux["T4_violating"])
    assert r["grade"] == "Chỉ báo cáo"


def test_hours_zero_range_is_flagged_not_error(outcome):
    _, _, res, *_ = outcome
    r = res["frames"]["rules"].set_index(["table", "rule_id"]).loc[("business", "V10")]
    assert r["n_violations"] == 1 and r["n_flagged"] == 1          # '10-21' sai dạng = lỗi; '0:0-0:0' chỉ gắn nhãn cần kiểm chứng


def test_uniqueness_counts_surplus_copies_not_all_copies(outcome):
    _, aux, res, *_ = outcome
    rev = aux["frames"]["review"]
    assert rev["review_id"].duplicated(keep=False).sum() == 6      # 3 review gốc + 3 bản nhân đôi
    assert _got(res)[("review", "U1")] == 3                        # chỉ 3 bản dư thừa bị tính lỗi


def test_composite_key_is_one_cell_and_missing_part_is_na(outcome):
    _, _, res, *_ = outcome
    n = res["meta"]["rows"]["checkin"]
    r = res["frames"]["rules"].set_index(["table", "rule_id"]).loc[("checkin", "U1")]
    assert r["n_units"] == n - 2                                   # 2 sự kiện thiếu checkin_time: không kết luận được -> N/A


def test_rule_score_is_cell_ratio(outcome):
    _, _, res, *_ = outcome
    n = res["meta"]["rows"]["checkin"]
    r = res["frames"]["rules"].set_index(["table", "rule_id"]).loc[("checkin", "C5")]
    assert r["n_units"] == 2 * n and r["n_violations"] == 2        # 2 cột x n dòng = 2n ô
    assert r["score"] == pytest.approx(1 - 2 / (2 * n))


def test_aspect_score_is_mean_of_ranked_rules_and_flag_rule(outcome):
    _, _, res, *_ = outcome
    rl, asp = res["frames"]["rules"], res["frames"]["aspects"]
    for _, a in asp[asp["status"] == "Đo được"].iterrows():
        if a["aspect"] not in ASPECTS:
            continue
        rr = rl[(rl["table"] == a["table"]) & (rl["aspect"] == a["aspect"]) & (rl["level"] != "report") & (rl["n_units"] > 0)]
        assert a["score"] == pytest.approx(rr["score"].mean()), (a["table"], a["aspect"])
        bad_star = rr[(rr["level"] == "star") & (rr["grade"] == "Tệ")]
        assert bool(a["flag"]) == (len(bad_star) > 0), (a["table"], a["aspect"])
        assert set(filter(None, str(a["flagged_rules"]).replace("nan", "").split(","))) == set(bad_star["rule_id"])


def test_not_applicable_and_report_only_aspects(outcome):
    _, _, res, *_ = outcome
    asp = res["frames"]["aspects"]
    asp = asp[asp["aspect"].isin(ASPECTS)]
    assert set(zip(asp[asp.status == "N/A"].table, asp[asp.status == "N/A"].aspect)) == {(t, "Chính xác") for t in
                                                                                       ("business", "checkin", "review", "tip", "user")}
    assert set(zip(asp[asp.status == "Chỉ báo cáo"].table, asp[asp.status == "Chỉ báo cáo"].aspect)) == {("business", "Kịp thời")}
    assert not asp["note"].fillna("").str.contains("CHƯA CẤU HÌNH").any()


def test_outputs_written(outcome):
    _, _, res, out, *_ = outcome
    for f in ("results_rules.csv", "results_aspects.csv", "results_by_cell_column.csv", "results_dataset.csv", "results_metrics.csv",
              "violation_samples.csv", "temporal_profile.csv", "tempo_dq_eq2_by_column.csv", "run_metadata.json", "report.md",
              "chart_business.png", "chart_user.png"):
        assert (out / f).exists(), f
    assert "Điểm khía cạnh theo bảng" in res["report_md"]
    smp = res["frames"]["samples"]
    assert not smp.empty and {"record", "cell", "value"} <= set(smp.columns)


def test_compare_before_after_dedup(outcome, tmp_path):
    _, aux, res0, out0, cfg0, d = outcome
    d1 = tmp_path / "data1"
    d1.mkdir()
    for f in d.glob("*.parquet"):
        df = pd.read_parquet(f)
        if f.stem == "review":
            df = df.drop_duplicates("review_id", keep="first")
        df.to_parquet(d1 / f.name, index=False)
    cfg1 = copy.deepcopy(cfg0)
    cfg1["run"].update(data_dir=str(d1), out_dir=str(tmp_path / "out1"), label="KQ_v1")
    run(cfg1, verbose=False, plots=False)
    asp, rul, md = compare(out0, tmp_path / "out1")
    r = rul[(rul["table"] == "review") & (rul["rule_id"] == "U1")].iloc[0]
    assert (r["n_violations_trước"], r["n_violations_sau"], r["giảm_lỗi"]) == (3, 0, 3)
    assert "KQ_v0" in md and "KQ_v1" in md


# ============================================================================= (2) ngữ nghĩa hàm kiểm tra
def call(name, df, ctx=None, **p):
    rc = RuleCtx(df=df, p=p, ctx=ctx or Context(), ref={"datetime_format": FMT}, t_start=pd.Timestamp("2005-02-16"), t_end=pd.Timestamp("2022-01-20"))
    return SPECS[name]["fn"](rc)


def test_regex_true_false_na():
    df = pd.DataFrame({"x": ["A" * 22, "bad", None, "   "]})
    out = call("regex", df, column="x", pattern="[A-Za-z0-9_-]{22}").cells["x"]
    assert out.tolist() == [TRUE, FALSE, NA, NA]                    # rỗng/khoảng trắng là thiếu -> N/A (đã tính ở Đầy đủ)


def test_not_null_missing_tokens_and_blank_are_missing():
    df = pd.DataFrame({"f": ["None", "u1", None, ""]})
    out = call("not_null", df, column="f", missing_tokens=["None"]).cells["f"]
    assert out.tolist() == [FALSE, TRUE, FALSE, FALSE]              # mọi ô đều được xét (không có N/A)


def test_dtype_wrong_type_is_false_but_range_skips_it():
    df = pd.DataFrame({"x": ["3", "abc", None]})
    assert call("dtype", df, column="x", kind="numeric").cells["x"].tolist() == [TRUE, FALSE, NA]
    df2 = pd.DataFrame({"x": ["3", "abc", "-1", "2.5", None]})
    out = call("range", df2, column="x", min=0, integer=True).cells["x"]
    assert out.tolist() == [TRUE, NA, FALSE, FALSE, NA]            # 'abc' bị bắt ở dtype, range không đếm lại


def test_in_window_bounds_and_last_day_inclusive():
    df = pd.DataFrame({"d": ["2005-02-16 00:00:00", "2005-02-15 23:59:59", "2022-01-19 23:59:59", "2022-01-20 00:00:00", "zzz", None]})
    assert call("in_window", df, column="d").cells["d"].tolist() == [TRUE, FALSE, TRUE, FALSE, NA, NA]
    assert call("in_window", df, column="d", use_start=False).cells["d"].tolist() == [TRUE, TRUE, TRUE, FALSE, NA, NA]


def test_unique_keeps_first_flags_later_copies_and_na_for_missing_key():
    df = pd.DataFrame({"a": ["k", "k", "k", "m", None, None], "b": [1, 1, 2, 3, 4, 4]})
    out = call("unique", df, keys=["a", "b"]).cells
    assert list(out) == ["(a, b)"]                                  # khóa ghép = MỘT ô tổ hợp
    assert out["(a, b)"].tolist() == [TRUE, FALSE, TRUE, TRUE, NA, NA]


def test_fk_and_date_ge_lookup():
    ctx = Context()
    ctx.key_index["business.business_id"] = pd.Index(["a", "b"])
    assert call("fk", pd.DataFrame({"x": ["a", "z", None]}), ctx, column="x", ref="business.business_id").cells["x"].tolist() == [TRUE, FALSE, NA]
    ctx.series["user.yelping_since"] = pd.Series({"u1": pd.Timestamp("2010-01-01")})
    df = pd.DataFrame({"user_id": ["u1", "u1", "uX"], "date": ["2010-01-01 00:00:00", "2009-12-31 23:59:59", "2011-01-01 00:00:00"]})
    out = call("date_ge_lookup", df, ctx, column="date", key="user_id", lookup="user.yelping_since").cells["date"]
    assert out.tolist() == [TRUE, FALSE, NA]                        # user không tồn tại -> N/A (S1 mới bắt lỗi mồ côi)


def test_id_list_accepts_real_friend_formats_and_flags_bad_ids():
    a, b = "A" * 22, "b" * 22
    df = pd.DataFrame({"f": ["None", "[]", "", f"['{a}']", f"['{a}', '{b}']", f"['{a}' '{b}']", f"{a}, {b}", f"['{a}', 'bad']", "garbage", None]})
    out = call("id_list", df, column="f").cells["f"]
    assert out.tolist() == [TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, TRUE, FALSE, FALSE, NA]
    arr = pd.DataFrame({"f": pd.Series([np.array([a, b]), np.array([a, "bad"]), np.array([], dtype=str)], dtype=object)})
    assert call("id_list", arr, column="f").cells["f"].tolist() == [TRUE, FALSE, TRUE]           # list/mảng thật


def test_in_window_per_rule_t_start_override():
    df = pd.DataFrame({"d": ["2004-10-12 08:46:11", "2004-06-30 23:59:59", "2005-01-01 00:00:00"]})
    assert call("in_window", df, column="d").cells["d"].tolist() == [FALSE, FALSE, FALSE]       # T_start chung 2005-02-16
    assert call("in_window", df, column="d", t_start="2004-07-01").cells["d"].tolist() == [TRUE, FALSE, TRUE]


def test_elite_years_bounds():
    df = pd.DataFrame({"elite": ["2011,2012", "2009,2012", "2011,2030", "", "abc"], "ys": ["2010-05-05 00:00:00"] * 5})
    out = call("elite_years", df, column="elite", other="ys").cells["elite"]
    assert out.tolist() == [TRUE, FALSE, FALSE, NA, NA]            # 2009 < năm đăng ký; 2030 > 2022; '' và 'abc' không có năm hợp lệ


def test_ref_compare_at_least_and_two_sided():
    ctx = Context()
    ctx.series["ref"] = pd.Series({"a": 8.0, "b": 8.0})
    df = pd.DataFrame({"k": ["a", "b", "zz"], "v": [3, 20, 5]})
    assert call("ref_compare", df, ctx, column="v", key="k", ref="ref", mode="at_least", tol_abs=0).cells["v"].tolist() == [FALSE, TRUE, NA]
    assert call("ref_compare", df, ctx, column="v", key="k", ref="ref", mode="two_sided", tol_abs=0).cells["v"].tolist() == [FALSE, FALSE, NA]
    assert call("ref_compare", df, ctx, column="v", key="k", ref="ref", tol_abs=0, fill_missing_ref=0).cells["v"].tolist() == [FALSE, FALSE, FALSE]


def test_city_spelling_flags_non_canonical_variants():
    df = pd.DataFrame({"city": ["Phoenix"] * 5 + ["phoenix ", "PHOENIX"]})
    out = call("city_spelling", df, column="city").cells["city"]
    assert out.tolist() == [TRUE] * 5 + [FALSE, FALSE]


# ============================================================================= (3) cách tính điểm
def mini_cfg(rules):
    asp = {"Đầy đủ": (.98, .95), "Hợp lệ": (.99, .95), "Duy nhất": (.99, .95), "Nhất quán": (.99, .95), "Chính xác": (.9, .8), "Kịp thời": (.99, .95)}
    return {"run": {"n_sample": 5}, "reference": {"T_ref": "2022-01-19", "T_start": "2005-02-16", "datetime_format": FMT},
            "thresholds": {"star": {"good": .999, "bad": .99}, "aspect": {k: {"good": g, "bad": b} for k, (g, b) in asp.items()}},
            "tables": {"t": {"keys": ["a"], "rules": rules}}}


def _asp(r, name):
    return next(x for x in r.aspects if x["aspect"] == name)


def _rule(r, rid):
    return next(x for x in r.rules if x["rule_id"] == rid)


def test_star_rule_bad_flags_aspect_even_if_mean_is_good():
    df = pd.DataFrame({"a": [1] * 200, "b": [1] * 197 + [-1] * 3})
    rules = [{"id": "V4", "aspect": "Hợp lệ", "type": "range", "level": "star", "column": "b", "min": 0},       # 1 - 3/200 = 0,985 < 0,99 -> Tệ
             {"id": "V7", "aspect": "Hợp lệ", "type": "range", "level": "general", "column": "a", "min": 0}]   # 1,0
    r = evaluate_table(mini_cfg(rules), "t", df, {}, Context())
    a = _asp(r, "Hợp lệ")
    assert a["score"] == pytest.approx((0.985 + 1.0) / 2) and a["grade"] == "Tốt"
    assert a["flag"] is True and a["flagged_rules"] == "V4"
    v4 = _rule(r, "V4")
    assert v4["grade"] == "Tệ" and v4["action"].startswith("Xử lý mọi vi phạm")


def test_threshold_override_good_equals_one():
    df = pd.DataFrame({"a": list(range(999)) + [0]})                 # 1 bản dư thừa / 1000 ô
    rules = [{"id": "U1", "aspect": "Duy nhất", "type": "unique", "level": "star", "keys": ["a"], "thresholds": {"good": 1.0}}]
    u1 = _rule(evaluate_table(mini_cfg(rules), "t", df, {}, Context()), "U1")
    assert u1["n_violations"] == 1 and u1["score"] == pytest.approx(0.999) and u1["grade"] == "Chú ý"   # không ghi đè thì 0,999 là Tốt


def test_report_only_rule_does_not_enter_aspect_score():
    df = pd.DataFrame({"a": [1] * 100, "b": [-1] * 100})
    rules = [{"id": "V1", "aspect": "Hợp lệ", "type": "range", "level": "general", "column": "a", "min": 0},
             {"id": "V9", "aspect": "Hợp lệ", "type": "range", "level": "report", "column": "b", "min": 0}]
    r = evaluate_table(mini_cfg(rules), "t", df, {}, Context())
    a = _asp(r, "Hợp lệ")
    assert a["score"] == 1.0 and a["n_rules"] == 1
    assert _rule(r, "V9")["grade"] == "Chỉ báo cáo" and _rule(r, "V9")["n_violations"] == 100


def test_same_cell_failing_two_rules_counts_in_each_rule_and_aspect_is_mean_of_rules():
    df = pd.DataFrame({"a": [1, 2, 3, 5]})
    rules = [{"id": "V1", "aspect": "Hợp lệ", "type": "range", "level": "general", "column": "a", "max": 2},
             {"id": "V2", "aspect": "Hợp lệ", "type": "enum", "level": "general", "column": "a", "values": [1, 2]}]
    r = evaluate_table(mini_cfg(rules), "t", df, {}, Context())
    assert [_rule(r, x)["n_violations"] for x in ("V1", "V2")] == [2, 2]       # ô 3 và ô 5 trượt cả hai quy tắc
    assert _asp(r, "Hợp lệ")["score"] == pytest.approx(0.5)                    # điểm khía cạnh = trung bình điểm quy tắc (báo cáo A.1)


def test_aspect_without_rules_is_na_with_reason():
    df = pd.DataFrame({"a": [1, 2]})
    cfg = mini_cfg([{"id": "V1", "aspect": "Hợp lệ", "type": "range", "level": "general", "column": "a", "min": 0}])
    cfg["tables"]["t"]["not_applicable"] = {"Kịp thời": "không có thuộc tính thời gian"}
    r = evaluate_table(cfg, "t", df, {}, Context())
    assert _asp(r, "Kịp thời")["status"] == "N/A" and "thời gian" in _asp(r, "Kịp thời")["note"]
    assert "CHƯA CẤU HÌNH" in _asp(r, "Chính xác")["note"]


# ============================================================================= (4) tài liệu hóa và cấu hình
def test_every_rule_type_is_documented():
    for k, s in SPECS.items():
        for f in ("true", "false", "na", "why", "source"):
            assert s[f].strip(), (k, f)


def test_config_rules_are_valid_and_in_catalog():
    cfg = load_config(ROOT / "config.yaml")
    text = catalog(cfg)
    for t, tc in cfg["tables"].items():
        ids = [r["id"] for r in tc["rules"]]
        assert len(ids) == len(set(ids)), f"{t}: trùng mã quy tắc"
        for r in tc["rules"]:
            assert r["type"] in SPECS, (t, r["id"])
            assert r["aspect"] in SPECS[r["type"]]["aspects"], (t, r["id"])
            assert r.get("level", "general") in ("star", "general", "report"), (t, r["id"])
            assert r["type"] in text
    assert all(a in text for a in ASPECTS)
