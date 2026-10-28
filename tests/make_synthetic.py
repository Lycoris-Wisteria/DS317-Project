"""Sinh bộ dữ liệu Yelp tổng hợp (cùng schema) với số lỗi TIÊM BIẾT TRƯỚC, theo bộ quy tắc của báo cáo CLDL.

`exp[(bảng, mã quy tắc)]` = số ô vi phạm kỳ vọng, tính tay từ cách tiêm lỗi (không dùng code của dq/).
Mọi quy tắc không có trong exp phải bằng 0 (kiểm tra không có dương tính giả).
Các chú thích "->" ghi quy tắc nào bắt lỗi đó.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FMT = "%Y-%m-%d %H:%M:%S"
UNKNOWN_B = "B" + "9" * 21
UNKNOWN_U = "U" + "9" * 21


def bid(i): return "B" + str(i).zfill(21)
def uid(i): return "U" + str(i).zfill(21)
def rid(i): return "R" + str(i).zfill(21)


def make(out_dir: Path, seed: int = 7):
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    exp: dict[tuple, int] = {}
    aux: dict = {}

    def e(table, rule, v=1): exp[(table, rule)] = exp.get((table, rule), 0) + v

    # ------------------------------------------------------------------ USER (80 user; 0..49 có review)
    n_u = 80
    ys = pd.Series(pd.Timestamp("2008-01-01") + pd.to_timedelta(rng.integers(0, 2800, n_u), unit="D") + pd.to_timedelta(rng.integers(0, 86000, n_u), unit="s"))
    users = pd.DataFrame({
        "user_id": [uid(i) for i in range(n_u)], "name": [f"User{i}" for i in range(n_u)],
        "review_count": [8 if i < 50 else 5 for i in range(n_u)], "yelping_since": ys.dt.strftime(FMT),
        "useful": 3, "funny": 2, "cool": 1, "fans": 0,
        "average_stars": [((2 * i) % 5 + 1) * 1.0 if i < 50 else 3.5 for i in range(n_u)],
    })
    users["elite"] = [f"{ys[i].year + 1},{ys[i].year + 2}" if i < 20 else "" for i in range(n_u)]
    users["friends"] = [("None" if i % 2 == 0 else f"{uid((i + 1) % 50)}, {uid((i + 2) % 50)}") for i in range(n_u)]
    for c in ["hot", "more", "profile", "cute", "list", "note", "plain", "cool", "funny", "writer", "photos"]:
        users[f"compliment_{c}"] = 1
    users.loc[0, "average_stars"] = 2.8;  e("user", "S8")                      # trung bình review thực = 1 -> lệch 1,8
    users.loc[1, "review_count"] = 3                                            # < 8 review quan sát được (S3 tính ở cuối)
    users.loc[2, "review_count"] = 20                                            # >= số quan sát: hợp lệ (cận dưới)
    users.loc[50, "yelping_since"] = "2003-05-01 00:00:00"; e("user", "T2")    # trước T_start
    users.loc[51, "yelping_since"] = "not a date";          e("user", "V6")    # sai định dạng (T2 không xét)
    users.loc[52, "yelping_since"] = "2023-02-01 00:00:00"; e("user", "T2")    # sau T_ref
    users.loc[53, ["yelping_since", "elite"]] = ["2010-03-03 10:00:00", "2019,2025"]; e("user", "S4")   # 2025 > 2022
    users.loc[54, ["yelping_since", "elite"]] = ["2010-03-03 10:00:00", "2005,2012"]; e("user", "S4")   # 2005 < 2010
    users.loc[56, "elite"] = "abc";                         e("user", "V9")
    users.loc[57, "average_stars"] = 7.0;                   e("user", "V7")
    users.loc[58, "compliment_hot"] = -1;                   e("user", "V4")
    users.loc[59, "name"] = None                                                  # name không thuộc quy tắc Đầy đủ nào
    users.loc[60, "friends"] = None; users.loc[61, "friends"] = None
    users.loc[62, "user_id"] = "short";                     e("user", "V1")
    users = pd.concat([users, users.iloc[[3, 4]]], ignore_index=True); e("user", "U1", 2)
    miss_elite = int((users["elite"].isna() | users["elite"].astype(str).str.strip().eq("")).sum())
    miss_friends = int((users["friends"].isna() | users["friends"].astype(str).str.strip().eq("None")).sum())
    e("user", "C7", miss_elite + miss_friends)                                   # chỉ báo cáo

    # ------------------------------------------------------------------ BUSINESS (62 dòng gốc, 0..49 Phoenix/AZ, 50..61 Philadelphia/PA)
    n_b = 62
    az = np.arange(n_b) < 50
    biz = pd.DataFrame({
        "business_id": [bid(i) for i in range(n_b)], "name": [f"Biz{i}" for i in range(n_b)], "address": "1 Main St",
        "city": np.where(az, "Phoenix", "Philadelphia"), "state": np.where(az, "AZ", "PA"), "postal_code": np.where(az, "85001", "19019"),
        "latitude": np.where(az, rng.uniform(32.8, 33.6, n_b), rng.uniform(39.9, 40.1, n_b)),
        "longitude": np.where(az, rng.uniform(-112.5, -111.5, n_b), rng.uniform(-75.3, -75.0, n_b)),
        "stars": [((2 * i) % 5 + 1) * 1.0 if i < 40 else 3.0 for i in range(n_b)],
        "review_count": [10 if i < 40 else 0 for i in range(n_b)], "is_open": 1,
        "attributes": '{"RestaurantsTakeOut": "True"}', "categories": "Food, Restaurants", "hours": '{"Monday": "10:0-21:0"}',
    })
    biz.loc[0, "review_count"] = 30                                              # lệch tham chiếu -> chỉ S6 (chỉ báo cáo, tính ở cuối)
    biz.loc[2, "stars"] = 1.0;            e("business", "S7")                    # trung bình review = 5
    biz.loc[3, "state"] = "az";           e("business", "V8")
    biz.loc[7, "longitude"] = -73.2;      e("business", "V2")                    # ví dụ POI ngoại lai ở báo cáo (> -74)
    biz.loc[8, "latitude"] = 99.0;        e("business", "V2")
    biz.loc[9, "stars"] = 4.3;            e("business", "V3")                    # không phải bội 0,5 (S7: lệch 0,3 <= 0,5 nên không lỗi)
    biz.loc[10, "is_open"] = 2;           e("business", "V5")
    biz.loc[11, "review_count"] = -4;     e("business", "V4")
    biz.loc[[13, 14, 15], "postal_code"] = None; e("business", "C2", 3)
    biz.loc[16, "name"] = None;           e("business", "C1")
    biz.loc[[17, 18], "address"] = None;  e("business", "C7", 2)
    biz.loc[[19, 20, 21, 22, 23], "hours"] = None; e("business", "C7", 5)
    biz.loc[20, "city"] = "phoenix ";     e("business", "S5a")                   # cách viết khác của Phoenix
    biz.loc[21, "city"] = "PHOENIX";      e("business", "S5a")
    biz.loc[22, "state"] = "PA";          e("business", "S5b")                   # Phoenix nhưng state PA
    biz.loc[25, "attributes"] = "{bad";   e("business", "V12b")
    biz.loc[26, "hours"] = '{"Monday": "10-21"}'; e("business", "V10")
    biz.loc[27, "hours"] = '{"Monday": "0:0-0:0"}'                              # chỉ gắn nhãn cần kiểm chứng
    biz.loc[45, "business_id"] = "x";     e("business", "V1")                    # business 45 không có review/tip/checkin tham chiếu
    biz = pd.concat([biz, biz.iloc[[5, 6]]], ignore_index=True); e("business", "U1", 2); e("business", "U3", 2)
    aux["flagged_hours"] = 1
    aux["biz_sum_review_count"] = int(biz.drop_duplicates("business_id")["review_count"].sum())

    # ------------------------------------------------------------------ REVIEW (400 dòng gốc)
    n_r = 400
    i_ = np.arange(n_r)
    u_idx, b_idx = i_ % 50, i_ % 40
    ys_dt = pd.to_datetime(users["yelping_since"].iloc[:50])
    date = ys_dt.to_numpy()[u_idx] + pd.to_timedelta(30 + (i_ * 37) % 2000, unit="D") + pd.to_timedelta((i_ * 911) % 86000, unit="s")
    rev = pd.DataFrame({
        "review_id": [rid(i) for i in i_], "user_id": [uid(u) for u in u_idx], "business_id": [bid(b) for b in b_idx],
        "stars": ((i_ * 7) % 5 + 1).astype(float), "useful": 1, "funny": 0, "cool": 0,
        "text": [f"review text {i}" for i in i_], "date": pd.Series(date).dt.strftime(FMT),
    })
    rev.loc[20:21, "business_id"] = UNKNOWN_B;  e("review", "S1", 2)
    rev.loc[30:33, "user_id"] = UNKNOWN_U;      e("review", "S1", 4)
    rev.loc[40:44, "date"] = "2023-03-01 10:00:00"; e("review", "T1", 5)         # sau T_ref
    rev.loc[50:51, "date"] = "2003-01-01 00:00:00"; e("review", "T1", 2); e("review", "S2", 2)   # trước T_start và trước yelping_since
    for k in (60, 61, 62):                                                       # sớm hơn yelping_since 400 ngày nhưng vẫn trong khung
        rev.loc[k, "date"] = (pd.Timestamp(users.loc[k % 50, "yelping_since"]) - pd.Timedelta(days=400)).strftime(FMT); e("review", "S2")
    for k in (72, 77, 82):                                                       # stars 5 -> 6: chỉ lệch 0,125 nên không gây lỗi S7/S8
        rev.loc[k, "stars"] = 6.0; e("review", "V3")
    rev.loc[90:91, "date"] = "garbage"; e("review", "V6", 2)
    rev.loc[[100, 101], "useful"] = -1; e("review", "V4", 2)
    rev.loc[[110, 111, 112, 113], "text"] = None; e("review", "C3", 4)
    rev.loc[120, "review_id"] = "short"; e("review", "V1")
    rev = pd.concat([rev, rev.iloc[[10, 11, 12]]], ignore_index=True); e("review", "U1", 3); e("review", "U4", 3)

    # ------------------------------------------------------------------ TIP (100 dòng gốc)
    n_t = 100
    j = np.arange(n_t)
    tdate = ys_dt.to_numpy()[(j * 3) % 50] + pd.to_timedelta(60 + j * 11, unit="D")
    tip = pd.DataFrame({"user_id": [uid((k * 3) % 50) for k in j], "business_id": [bid(k % 40) for k in j],
                        "text": [f"tip {k}" for k in j], "date": pd.Series(tdate).dt.strftime(FMT), "compliment_count": 0})
    tip.loc[[10, 11], "date"] = "2022-08-01 00:00:00"; e("tip", "T1", 2)
    tip.loc[12, "business_id"] = UNKNOWN_B; e("tip", "S1")
    tip.loc[13, "user_id"] = UNKNOWN_U;    e("tip", "S1")
    for k in (14, 15):
        tip.loc[k, "date"] = (pd.Timestamp(users.loc[(k * 3) % 50, "yelping_since"]) - pd.Timedelta(days=100)).strftime(FMT); e("tip", "S2")
    tip.loc[16, "compliment_count"] = -1; e("tip", "V4")
    tip.loc[17, "date"] = "n/a"; e("tip", "V6")
    tip.loc[[20, 21, 22], "text"] = None; tip.loc[23, "text"] = "   "; e("tip", "C4", 4)
    tip = pd.concat([tip, tip.iloc[[30, 31]]], ignore_index=True); e("tip", "U2", 2)

    # ------------------------------------------------------------------ CHECKIN (500 dòng gốc, mỗi dòng một sự kiện)
    c_ = np.arange(500)
    ck = pd.DataFrame({"business_id": [bid(k % 40) for k in c_],
                       "checkin_time": (pd.Timestamp("2020-01-01") + pd.to_timedelta(c_ * 61, unit="min")).strftime(FMT)})
    ck.loc[10:11, "business_id"] = UNKNOWN_B; e("checkin", "S1", 2)
    ck.loc[100:103, "checkin_time"] = "2022-06-01 08:00:00"; e("checkin", "T3", 4)
    ck.loc[110, "checkin_time"] = "2001-01-01 00:00:00"                          # T3 chỉ có cận trên (theo báo cáo) nên không lỗi
    ck.loc[111, "checkin_time"] = "xx"; e("checkin", "V6")
    ck.loc[[300, 301], "checkin_time"] = None; e("checkin", "C5", 2)
    ck = pd.concat([ck, ck.iloc[[200, 201, 202]]], ignore_index=True); e("checkin", "U1", 3)

    # ------------------------------------------------------------------ kỳ vọng tính ĐỘC LẬP bằng pandas thuần (không dùng dq/)
    # S3: user.review_count < số review quan sát được. Lưu ý 3 review bị nhân đôi làm user 10-12 có 9 review quan sát được
    #     trong khi review_count = 8, nên cũng bị bắt (đúng theo báo cáo: S3 không có dung sai).
    obs_u = rev.groupby("user_id").size()
    e("user", "S3", int((users["review_count"] < users["user_id"].map(obs_u).fillna(0)).sum()))
    # S6: business.review_count khác số review quan sát được (chỉ báo cáo)
    obs_b = rev.groupby("business_id").size()
    e("business", "S6", int((biz["review_count"] != biz["business_id"].map(obs_b).fillna(0)).sum()))
    # T4: business is_open = 1 mà không có review/tip/check-in nào trong 24 tháng trước T_ref (chỉ báo cáo)
    t_end = pd.Timestamp("2022-01-20")
    acts = pd.concat([rev[["business_id", "date"]].set_axis(["business_id", "t"], axis=1),
                      tip[["business_id", "date"]].set_axis(["business_id", "t"], axis=1),
                      ck[["business_id", "checkin_time"]].set_axis(["business_id", "t"], axis=1)])
    acts["t"] = pd.to_datetime(acts["t"], format=FMT, errors="coerce")
    last = acts[acts["t"].notna() & (acts["t"] < t_end)].groupby("business_id")["t"].max()
    opened = biz[pd.to_numeric(biz["is_open"]) == 1]
    recent = opened["business_id"].map(last) >= (t_end - pd.DateOffset(months=24))
    aux["T4_n"], aux["T4_violating"] = len(opened), int((~recent).sum())
    e("business", "T4", aux["T4_violating"])
    aux["n_reviews"] = len(rev)
    aux["coverage_num"] = 40                                                   # business 0..39 có check-in hợp lệ
    aux["coverage_den"] = int(biz["business_id"].nunique())

    for name, df in [("business", biz), ("user", users), ("review", rev), ("tip", tip), ("checkin_events", ck)]:
        df.to_parquet(out_dir / f"{name}.parquet", index=False)
    aux["frames"] = {"business": biz, "user": users, "review": rev, "tip": tip, "checkin": ck}
    return exp, aux
