"""
app.py  ─  国会発言分析ダッシュボード
Streamlit Cloud へそのままデプロイ可能

起動方法:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
from collections import Counter
from datetime import datetime

# ────────────────────────────────────────────
# ページ設定
# ────────────────────────────────────────────
st.set_page_config(
    page_title="国会発言分析：台湾有事関連イベントと政党反応",
    page_icon="🏛️",
    layout="wide",
)

PELOSI_DATE  = "2022-08-02"
BASE_KEYWORDS = ["台湾", "中国", "安全保障", "有事"]
PARTY_COLORS  = {"自民": "#E63946", "立憲": "#457B9D", "維新": "#2A9D8F"}
DATA_DIR      = "data"


# ────────────────────────────────────────────
# speeches_raw.csv → 集計データを生成する関数
# (analyze.py の処理をインラインで実行)
# ────────────────────────────────────────────
def clean_speech(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"○.{1,10}君\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def analyze_raw(df_raw: pd.DataFrame, keywords: list[str]):
    """speeches_raw.csv から freq_daily / freq_monthly / summary を生成"""
    df = df_raw.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["speech_clean"] = df["speech"].apply(clean_speech)
    df = df[df["speech_clean"].str.len() > 10].copy()

    pelosi_dt = pd.to_datetime(PELOSI_DATE)
    df["period"]     = df["date"].apply(lambda d: "after" if d >= pelosi_dt else "before")
    df["year_month"] = df["date"].dt.to_period("M").astype(str)

    # キーワード頻度カラムを追加
    for kw in keywords:
        df[f"count_{kw}"] = df["speech_clean"].apply(
            lambda t: t.count(kw) if isinstance(t, str) else 0
        )

    count_cols = [f"count_{kw}" for kw in keywords]

    freq_daily = (
        df.groupby(["date", "party_label", "period"])[count_cols + ["speech_clean"]]
        .agg({**{c: "sum" for c in count_cols}, "speech_clean": lambda x: x.str.len().sum()})
        .reset_index()
        .rename(columns={"speech_clean": "speech_len"})
    )

    freq_monthly = (
        df.groupby(["year_month", "party_label", "period"])[count_cols + ["speech_clean"]]
        .agg({**{c: "sum" for c in count_cols}, "speech_clean": lambda x: x.str.len().sum()})
        .reset_index()
        .rename(columns={"speech_clean": "speech_len"})
    )

    summary = (
        df.groupby(["party_label", "period"])
        .agg(
            speech_count=("speech_id", "count"),
            unique_speakers=("speaker", "nunique"),
            avg_length=("speech_clean", lambda x: round(x.str.len().mean(), 1)),
        )
        .reset_index()
    )

    return freq_daily, freq_monthly, summary


# ────────────────────────────────────────────
# デフォルトデータ読み込み（CSVがある場合）
# ────────────────────────────────────────────
@st.cache_data
def load_default_data(keywords: tuple):
    keywords = list(keywords)
    paths = {
        "raw":     os.path.join(DATA_DIR, "speeches_raw.csv"),
        "daily":   os.path.join(DATA_DIR, "freq_daily.csv"),
        "monthly": os.path.join(DATA_DIR, "freq_monthly.csv"),
        "summary": os.path.join(DATA_DIR, "summary.csv"),
    }

    # speeches_raw.csv があれば再集計
    if os.path.exists(paths["raw"]):
        df_raw = pd.read_csv(paths["raw"], encoding="utf-8-sig")
        daily, monthly, summary = analyze_raw(df_raw, keywords)
        return daily, monthly, summary, []

    # 集計済みCSVがあればそのまま読む
    missing = [k for k in ["daily", "monthly", "summary"] if not os.path.exists(paths[k])]
    if missing:
        return None, None, None, missing

    daily   = pd.read_csv(paths["daily"],   encoding="utf-8-sig")
    monthly = pd.read_csv(paths["monthly"], encoding="utf-8-sig")
    summary = pd.read_csv(paths["summary"], encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"])
    return daily, monthly, summary, []


# ────────────────────────────────────────────
# ヘッダー
# ────────────────────────────────────────────
st.title("🏛️ 国会発言分析ダッシュボード")
st.markdown(
    "**ペロシ訪台（2022年8月2日）** 前後における政党別・キーワード別発言頻度を可視化します。"
)

# ────────────────────────────────────────────
# サイドバー
# ────────────────────────────────────────────
with st.sidebar:
    st.header("🔧 表示設定")

    # ── CSVアップロード ──────────────────────
    st.subheader("📂 データ読み込み")
    uploaded_file = st.file_uploader(
        "speeches_raw.csv をアップロード",
        type=["csv"],
        help="fetch_data.py で取得した speeches_raw.csv をアップロードしてください。アップロードするとその場で集計します。"
    )

    st.divider()

    # ── キーワード設定 ────────────────────────
    st.subheader("🔑 キーワード設定")
    st.caption("デフォルト4語は常に有効です")

    extra_input = st.text_input(
        "キーワードを追加（カンマ区切り）",
        placeholder="例：外交、抑止、連携",
        help="カンマ区切りで複数入力できます"
    )

    extra_keywords = []
    if extra_input.strip():
        extra_keywords = [k.strip() for k in extra_input.split(",") if k.strip()]

    all_keywords = BASE_KEYWORDS + extra_keywords

    selected_keyword = st.selectbox(
        "表示するキーワード",
        all_keywords,
        index=0,
    )

    st.divider()

    # ── その他フィルタ ─────────────────────────
    selected_parties = st.multiselect(
        "政党",
        options=["自民", "立憲", "維新"],
        default=["自民", "立憲", "維新"],
    )

    granularity = st.radio(
        "集計粒度",
        ["月次", "日次（7日移動平均）"],
        index=0,
    )

    st.divider()
    st.caption("📌 このアプリはPhase 1の成果物です")
    st.caption("データ：国会会議録検索システムAPI")


# ────────────────────────────────────────────
# データ決定：アップロード優先
# ────────────────────────────────────────────
if uploaded_file is not None:
    try:
        df_raw = pd.read_csv(uploaded_file, encoding="utf-8-sig")
        # 必須カラムチェック
        required_cols = {"speech_id", "date", "speaker", "party_label", "speech"}
        missing_cols = required_cols - set(df_raw.columns)
        if missing_cols:
            st.error(f"CSVに必要なカラムがありません：{missing_cols}")
            st.stop()

        with st.spinner("データを集計中..."):
            daily, monthly, summary = analyze_raw(df_raw, all_keywords)

        st.success(f"アップロード完了：{len(df_raw):,}件の発言を読み込みました")

    except Exception as e:
        st.error(f"CSVの読み込みに失敗しました：{e}")
        st.stop()
else:
    daily, monthly, summary, missing = load_default_data(tuple(all_keywords))

    if missing or daily is None:
        st.info(
            "左サイドバーから **speeches_raw.csv** をアップロードするか、\n\n"
            "`fetch_data.py` → `analyze.py` を実行してデータを用意してください。"
        )
        st.stop()

    # キーワード追加時は再集計
    if extra_keywords:
        raw_path = os.path.join(DATA_DIR, "speeches_raw.csv")
        if os.path.exists(raw_path):
            df_raw = pd.read_csv(raw_path, encoding="utf-8-sig")
            daily, monthly, summary = analyze_raw(df_raw, all_keywords)


if not selected_parties:
    st.info("左サイドバーで政党を1つ以上選択してください。")
    st.stop()


kw_col = f"count_{selected_keyword}"

# kw_colが存在しない場合のフォールバック
if kw_col not in daily.columns:
    st.warning(f"「{selected_keyword}」のデータがありません。キーワードを確認してください。")
    st.stop()


# ────────────────────────────────────────────
# タブ構成
# ────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 時系列トレンド",
    "⚖️ 前後比較",
    "🔄 キーワード比較",
    "📋 データ概要",
])


# ─── Tab 1: 時系列トレンド ───────────────────
with tab1:
    st.subheader(f"「{selected_keyword}」の発言頻度：時系列")

    if granularity == "月次":
        plot_df = monthly[monthly["party_label"].isin(selected_parties)].copy()
        plot_df = plot_df.rename(columns={"year_month": "period_label"})
        x_col       = "period_label"
        kw_col_plot = kw_col
        title       = f"「{selected_keyword}」月次発言頻度（政党別）"
    else:
        plot_df = daily[daily["party_label"].isin(selected_parties)].copy()
        plot_df = plot_df.sort_values("date")
        smoothed_rows = []
        for party, grp in plot_df.groupby("party_label"):
            grp = grp.copy()
            grp[f"{kw_col}_smooth"] = grp[kw_col].rolling(7, min_periods=1).mean()
            smoothed_rows.append(grp)
        plot_df     = pd.concat(smoothed_rows)
        kw_col_plot = f"{kw_col}_smooth"
        x_col       = "date"
        title       = f"「{selected_keyword}」日次発言頻度・7日移動平均（政党別）"

    fig = px.line(
        plot_df,
        x=x_col,
        y=kw_col_plot,
        color="party_label",
        color_discrete_map=PARTY_COLORS,
        markers=True if granularity == "月次" else False,
        title=title,
        labels={kw_col_plot: "頻度", x_col: ""},
    )

    pelosi_x = "2022-08" if granularity == "月次" else PELOSI_DATE
    fig.add_vline(x=pelosi_x, line_dash="dash")
    fig.add_annotation(x=pelosi_x, y=1, yref="paper", text="ペロシ訪台", showarrow=False)
    fig.update_layout(height=420, legend_title="政党")
    st.plotly_chart(fig, use_container_width=True)


# ─── Tab 2: 前後比較 ─────────────────────────
with tab2:
    st.subheader(f"「{selected_keyword}」：ペロシ訪台前後の比較")

    col_a, col_b = st.columns(2)

    monthly_filtered = monthly[monthly["party_label"].isin(selected_parties)].copy()
    before_df = monthly_filtered[monthly_filtered["period"] == "before"].groupby("party_label")[kw_col].sum().reset_index()
    after_df  = monthly_filtered[monthly_filtered["period"] == "after" ].groupby("party_label")[kw_col].sum().reset_index()
    before_df["period"] = "訪台前（5〜8/1）"
    after_df["period"]  = "訪台後（8/2〜11）"
    compare_df = pd.concat([before_df, after_df])

    with col_a:
        fig_bar = px.bar(
            compare_df,
            x="party_label", y=kw_col, color="period", barmode="group",
            color_discrete_sequence=["#A8DADC", "#E63946"],
            title="期間別・政党別 累計頻度",
            labels={kw_col: "累計頻度", "party_label": "政党", "period": "期間"},
        )
        fig_bar.update_layout(height=380, legend_title="期間")
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_b:
        surge_rows = []
        for party in selected_parties:
            b = before_df[before_df["party_label"] == party][kw_col].values
            a = after_df[ after_df["party_label"]  == party][kw_col].values
            b_val = b[0] if len(b) else 0
            a_val = a[0] if len(a) else 0
            ratio = round(a_val / b_val, 2) if b_val > 0 else float("nan")
            surge_rows.append({"政党": party, "訪台前": int(b_val), "訪台後": int(a_val), "増加倍率": ratio})

        surge_df = pd.DataFrame(surge_rows)

        fig_ratio = px.bar(
            surge_df, x="政党", y="増加倍率", color="政党",
            color_discrete_map=PARTY_COLORS,
            title="訪台後の増加倍率（訪台前比）", text="増加倍率",
        )
        fig_ratio.add_hline(y=1, line_dash="dot", line_color="gray", annotation_text="変化なし")
        fig_ratio.update_traces(texttemplate="%{text}x", textposition="outside")
        fig_ratio.update_layout(height=380, showlegend=False)
        st.plotly_chart(fig_ratio, use_container_width=True)

    st.subheader("数値テーブル")
    st.dataframe(surge_df.set_index("政党"), use_container_width=True)


# ─── Tab 3: キーワード比較 ───────────────────
with tab3:
    st.subheader("政党ごとのキーワード構成比較")

    monthly_all = monthly[monthly["party_label"].isin(selected_parties)].copy()
    kw_totals = []
    for kw in all_keywords:
        col = f"count_{kw}"
        if col not in monthly_all.columns:
            continue
        grp = monthly_all.groupby("party_label")[col].sum().reset_index()
        grp["keyword"] = kw
        grp = grp.rename(columns={col: "count"})
        kw_totals.append(grp)

    if kw_totals:
        kw_df = pd.concat(kw_totals)

        fig_heat = px.density_heatmap(
            kw_df, x="keyword", y="party_label", z="count",
            color_continuous_scale="Blues",
            title="政党 × キーワード ヒートマップ（全期間累計）",
            labels={"keyword": "キーワード", "party_label": "政党", "count": "頻度"},
        )
        fig_heat.update_layout(height=350)
        st.plotly_chart(fig_heat, use_container_width=True)

        st.subheader("政党別キーワード構成比")
        cols = st.columns(len(selected_parties))
        for i, party in enumerate(selected_parties):
            party_kw = kw_df[kw_df["party_label"] == party]
            fig_pie = px.pie(
                party_kw, names="keyword", values="count",
                hole=0.45, title=party,
            )
            fig_pie.update_layout(height=300, showlegend=True, margin=dict(t=40, b=10))
            cols[i].plotly_chart(fig_pie, use_container_width=True)


# ─── Tab 4: データ概要 ───────────────────────
with tab4:
    st.subheader("発言データ概要")

    if summary is not None:
        st.dataframe(
            summary.rename(columns={
                "party_label":     "政党",
                "period":          "期間",
                "speech_count":    "発言件数",
                "unique_speakers": "発言者数",
                "avg_length":      "平均文字数",
            }),
            use_container_width=True,
        )

    st.divider()
    st.subheader("日次データサンプル（先頭20行）")
    st.dataframe(daily.head(20), use_container_width=True)

    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("総レコード数（日次）", f"{len(daily):,}")
    col2.metric("分析期間", "2022-05〜11")
    col3.metric("キーワード数", len(all_keywords))
