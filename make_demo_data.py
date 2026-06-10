"""
make_demo_data.py
APIなしでStreamlitアプリの動作確認ができるデモデータを生成する

使い方:
    python make_demo_data.py

実際のAPIデータ取得後はこのスクリプトは不要。
"""

import pandas as pd
import numpy as np
import os

np.random.seed(42)
OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PARTIES     = ["自民", "立憲", "維新"]
KEYWORDS    = ["台湾", "中国", "安全保障", "有事"]
PELOSI_DATE = pd.Timestamp("2022-08-02")

# ────────────────────────────────────────────
# パラメータ（政党ごとの特性を模倣）
# ────────────────────────────────────────────
# ペロシ訪台後の発言増加倍率（モック値）
SURGE = {
    "自民": {"台湾": 3.5, "中国": 2.0, "安全保障": 2.8, "有事": 4.0},
    "立憲": {"台湾": 1.8, "中国": 1.5, "安全保障": 1.6, "有事": 1.4},
    "維新": {"台湾": 2.5, "中国": 1.8, "安全保障": 2.2, "有事": 2.8},
}
BASE = {
    "自民": {"台湾": 3, "中国": 5, "安全保障": 4, "有事": 1},
    "立憲": {"台湾": 2, "中国": 4, "安全保障": 3, "有事": 1},
    "維新": {"台湾": 2, "中国": 3, "安全保障": 2, "有事": 1},
}

dates = pd.date_range("2022-05-01", "2022-11-30", freq="D")

rows = []
for date in dates:
    is_after = date >= PELOSI_DATE
    for party in PARTIES:
        for kw in KEYWORDS:
            base_count = BASE[party][kw]
            surge      = SURGE[party][kw] if is_after else 1.0
            # ポアソン分布でランダム性を付加
            count = np.random.poisson(base_count * surge)
            rows.append({
                "date":        date.strftime("%Y-%m-%d"),
                "year_month":  date.strftime("%Y-%m"),
                "party_label": party,
                "period":      "after" if is_after else "before",
                f"count_{kw}": count,
                "speech_len":  np.random.randint(500, 3000),
            })

# pivot してキーワード列をまとめる
df = pd.DataFrame(rows)

# freq_daily（date × party_label）に集約
kw_cols = [f"count_{kw}" for kw in KEYWORDS]
freq_daily = (
    df.groupby(["date", "party_label", "period"])[kw_cols + ["speech_len"]]
    .sum()
    .reset_index()
)
freq_daily["date"] = pd.to_datetime(freq_daily["date"])

# freq_monthly
freq_monthly = (
    df.groupby(["year_month", "party_label", "period"])[kw_cols + ["speech_len"]]
    .sum()
    .reset_index()
)

# summary
summary_rows = []
for party in PARTIES:
    for period in ["before", "after"]:
        subset = freq_daily[(freq_daily["party_label"] == party) & (freq_daily["period"] == period)]
        summary_rows.append({
            "party_label":     party,
            "period":          period,
            "speech_count":    int(subset["speech_len"].count() * np.random.randint(5, 30)),
            "unique_speakers": np.random.randint(5, 25),
            "avg_length":      round(float(subset["speech_len"].mean()), 1),
        })
summary = pd.DataFrame(summary_rows)

freq_daily.to_csv(  os.path.join(OUTPUT_DIR, "freq_daily.csv"),   index=False, encoding="utf-8-sig")
freq_monthly.to_csv(os.path.join(OUTPUT_DIR, "freq_monthly.csv"), index=False, encoding="utf-8-sig")
summary.to_csv(     os.path.join(OUTPUT_DIR, "summary.csv"),      index=False, encoding="utf-8-sig")

print("デモデータ生成完了:")
print(f"  {OUTPUT_DIR}/freq_daily.csv   ({len(freq_daily)} 行)")
print(f"  {OUTPUT_DIR}/freq_monthly.csv ({len(freq_monthly)} 行)")
print(f"  {OUTPUT_DIR}/summary.csv      ({len(summary)} 行)")
