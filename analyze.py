"""
analyze.py
speeches_raw.csv を読み込んで集計・可視化用データを生成する

使い方:
    python analyze.py

出力:
    data/speeches_clean.csv     ← 前処理済みデータ
    data/freq_daily.csv         ← 政党別・日次キーワード頻度
    data/freq_monthly.csv       ← 政党別・月次キーワード頻度
    data/topwords_by_party.csv  ← 政党別トップ単語（MeCabがない場合はスキップ）
"""

import pandas as pd
import numpy as np
import os
import re
from collections import Counter

INPUT_CSV  = "data/speeches_raw.csv"
OUTPUT_DIR = "data"

# ペロシ訪台日
PELOSI_DATE = "2022-08-02"

# ────────────────────────────────────────────
# 前処理
# ────────────────────────────────────────────
def clean_speech(text: str) -> str:
    """発言テキストの基本クリーニング"""
    if not isinstance(text, str):
        return ""
    # HTMLタグ除去
    text = re.sub(r"<[^>]+>", "", text)
    # 議長・委員長の定型句を除去
    text = re.sub(r"○.{1,10}君\s*", "", text)
    # 余分な空白を整理
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_and_clean(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    print(f"読み込み: {len(df)} 行")

    # 日付をdatetimeに変換
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # テキストクリーニング
    df["speech_clean"] = df["speech"].apply(clean_speech)

    # 空発言を除去
    df = df[df["speech_clean"].str.len() > 10].copy()

    # ペロシ訪台前後フラグ
    pelosi_dt = pd.to_datetime(PELOSI_DATE)
    df["period"] = df["date"].apply(
        lambda d: "after" if d >= pelosi_dt else "before"
    )

    # 年月カラム
    df["year_month"] = df["date"].dt.to_period("M").astype(str)

    print(f"クリーニング後: {len(df)} 行")
    return df


# ────────────────────────────────────────────
# 集計1：日次・月次キーワード頻度
# ────────────────────────────────────────────
def count_keyword_occurrences(text: str, keyword: str) -> int:
    """テキスト中のキーワード出現回数"""
    if not isinstance(text, str):
        return 0
    return text.count(keyword)


def build_frequency_tables(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    政党別×期間別のキーワード出現頻度テーブルを返す
    Returns: (daily_df, monthly_df)
    """
    keywords = df["keyword"].unique().tolist()

    records = []
    for _, row in df.iterrows():
        base = {
            "date":       row["date"],
            "year_month": row["year_month"],
            "party_label":row["party_label"],
            "period":     row["period"],
            "speech_len": len(row["speech_clean"]),
        }
        for kw in keywords:
            base[f"count_{kw}"] = count_keyword_occurrences(row["speech_clean"], kw)
        records.append(base)

    detail_df = pd.DataFrame(records)

    # 日次集計
    freq_daily = (
        detail_df
        .groupby(["date", "party_label", "period"])
        [[f"count_{kw}" for kw in keywords] + ["speech_len"]]
        .sum()
        .reset_index()
    )

    # 月次集計
    freq_monthly = (
        detail_df
        .groupby(["year_month", "party_label", "period"])
        [[f"count_{kw}" for kw in keywords] + ["speech_len"]]
        .sum()
        .reset_index()
    )

    return freq_daily, freq_monthly


# ────────────────────────────────────────────
# 集計2：政党別発言件数サマリ
# ────────────────────────────────────────────
def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby(["party_label", "period"])
        .agg(
            speech_count=("speech_id", "count"),
            unique_speakers=("speaker", "nunique"),
            avg_length=("speech_clean", lambda x: x.str.len().mean()),
        )
        .round(1)
        .reset_index()
    )
    return summary


# ────────────────────────────────────────────
# 集計3：頻出単語（MeCabがある場合のみ）
# ────────────────────────────────────────────
def build_topwords(df: pd.DataFrame, top_n: int = 30) -> pd.DataFrame | None:
    try:
        import MeCab
    except ImportError:
        print("MeCabが見つかりません。topwords集計をスキップします。")
        return None

    tagger = MeCab.Tagger("-Owakati")
    stop_pos = {"助詞", "助動詞", "記号", "接続詞", "感動詞"}

    def extract_nouns(text):
        node = tagger.parseToNode(text)
        words = []
        while node:
            features = node.feature.split(",")
            pos = features[0]
            if pos not in stop_pos and len(node.surface) > 1:
                words.append(node.surface)
            node = node.next
        return words

    rows = []
    for party_label, group in df.groupby("party_label"):
        all_text = " ".join(group["speech_clean"].tolist())
        words = extract_nouns(all_text)
        counter = Counter(words)
        for word, cnt in counter.most_common(top_n):
            rows.append({"party_label": party_label, "word": word, "count": cnt})

    return pd.DataFrame(rows)


# ────────────────────────────────────────────
# メイン
# ────────────────────────────────────────────
def main():
    if not os.path.exists(INPUT_CSV):
        print(f"[ERROR] {INPUT_CSV} が見つかりません。先に fetch_data.py を実行してください。")
        return

    df = load_and_clean(INPUT_CSV)
    df.to_csv(os.path.join(OUTPUT_DIR, "speeches_clean.csv"), index=False, encoding="utf-8-sig")

    freq_daily, freq_monthly = build_frequency_tables(df)
    freq_daily.to_csv(  os.path.join(OUTPUT_DIR, "freq_daily.csv"),   index=False, encoding="utf-8-sig")
    freq_monthly.to_csv(os.path.join(OUTPUT_DIR, "freq_monthly.csv"), index=False, encoding="utf-8-sig")

    summary = build_summary(df)
    summary.to_csv(os.path.join(OUTPUT_DIR, "summary.csv"), index=False, encoding="utf-8-sig")

    topwords = build_topwords(df)
    if topwords is not None:
        topwords.to_csv(os.path.join(OUTPUT_DIR, "topwords_by_party.csv"), index=False, encoding="utf-8-sig")

    print("\n=== 集計完了 ===")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
