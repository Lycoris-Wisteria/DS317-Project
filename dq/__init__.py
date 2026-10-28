"""yelp_dq - đánh giá chất lượng dữ liệu Yelp theo báo cáo đo lường CLDL (Phần A, F) và TEMPO-DQ (lớp Conventional).

Sáu khía cạnh: Đầy đủ, Duy nhất, Nhất quán, Kịp thời, Hợp lệ, Chính xác.
Công thức Eq.(1)-(4) của paper: xem METRICS.md.
"""
ASPECTS = ["Đầy đủ", "Duy nhất", "Nhất quán", "Kịp thời", "Hợp lệ", "Chính xác"]
__version__ = "2.0.0"
