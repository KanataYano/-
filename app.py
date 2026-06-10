"""
app.py  ─  国会発言分析ダッシュボード
Streamlit Cloud へそのままデプロイ可能

起動方法:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# ────────────────────────────────────────────
# ページ設定
# ────────────────────────────────────────────
st.set_page_config(
    page_title="国会発言分析：台湾有事関連イベントと政党反応",
    page_icon="🏛️",
    layout="wide",
)

PELOSI_DATE = "2022-08-02"
KEYWORDS    = ["台湾", "中国", "安全保障", "有事"]
PARTY_COLORS = {"自民": "#E63946", "立憲": "#457B9D", "維新": "#2A9D8F"}
DATA_DIR    = "data"


# ────────────────────────────────────────────
# データ読み込み
# ────────────────────────────────────────────
@st.cache_data
def load_data():
    paths = {
        "daily":   os.path.join(DATA_DIR, "freq_daily.csv"),
        "monthly": os.path.join(DATA_DIR, "freq_monthly.csv"),
        "summary": os.path.join(DATA_DIR, "summary.csv"),
    }
    missing = [k for k, p in paths.items() if not os.path.exists(p)]
    if missing:
        return None, None, None, missing

    daily   = pd.read_csv(paths["daily"],   encoding="utf-8-sig")
    monthly = pd.read_csv(paths["monthly"], encoding="utf-8-sig")
    summary = pd.read_csv(paths["summary"], encoding="utf-8-sig")

    daily["date"] = pd.to_datetime(daily["date"])
    return daily, monthly, summary, []


daily, monthly, summary, missing = load_data()


# ────────────────────────────────────────────
# ヘッダー
# ────────────────────────────────────────────
st.title("🏛️ 国会発言分析ダッシュボード")
st.markdown(
    "**ペロシ訪台（2022年8月2日）** 前後における政党別・キーワード別発言頻度を可視化します。"
)

if missing:
    st.warning(
        f"データファイルが見つかりません：{missing}\n\n"
        "先に `make_demo_data.py`（デモ）または `fetch_data.py` + `analyze.py` を実行してください。"
    )
    st.stop()


# ────────────────────────────────────────────
# サイドバー（フィルタ）
# ────────────────────────────────────────────
with st.sidebar:
    st.header("🔧 表示設定")

    selected_keyword = st.selectbox(
        "キーワード",
        KEYWORDS,
        index=0,
    )

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


if not selected_parties:
    st.info("左サイドバーで政党を1つ以上選択してください。")
    st.stop()


kw_col = f"count_{selected_keyword}"


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
        x_col   = "period_label"
        title   = f"「{selected_keyword}」月次発言頻度（政党別）"
    else:
        plot_df = daily[daily["party_label"].isin(selected_parties)].copy()
        # 7日移動平均
        plot_df = plot_df.sort_values("date")
        smoothed_rows = []
        for party, grp in plot_df.groupby("party_label"):
            grp = grp.copy()
            grp[f"{kw_col}_smooth"] = grp[kw_col].rolling(7, min_periods=1).mean()
            smoothed_rows.append(grp)
        plot_df = pd.concat(smoothed_rows)
        kw_col_plot = f"{kw_col}_smooth"
        x_col  = "date"
        title  = f"「{selected_keyword}」日次発言頻度・7日移動平均（政党別）"

    if granularity == "月次":
        kw_col_plot = kw_col

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

    # ペロシ訪台の縦線
    pelosi_x = "2022-08" if granularity == "月次" else PELOSI_DATE
    fig.add_vline(
        x=pelosi_x,
        line_dash="dash",
        line_color="orange",
        annotation_text="ペロシ訪台",
        annotation_position="top right",
    )
    fig.update_layout(height=420, legend_title="政党")
    st.plotly_chart(fig, use_container_width=True)

    st.caption("※ デモデータを使用している場合、値はモック値です。")


# ─── Tab 2: 前後比較 ─────────────────────────
with tab2:
    st.subheader(f"「{selected_keyword}」：ペロシ訪台前後の比較")

    col_a, col_b = st.columns(2)

    # 棒グラフ：前後比較
    monthly_filtered = monthly[monthly["party_label"].isin(selected_parties)].copy()
    before_df = monthly_filtered[monthly_filtered["period"] == "before"].groupby("party_label")[kw_col].sum().reset_index()
    after_df  = monthly_filtered[monthly_filtered["period"] == "after" ].groupby("party_label")[kw_col].sum().reset_index()
    before_df["period"] = "訪台前（5〜8/1）"
    after_df["period"]  = "訪台後（8/2〜11）"
    compare_df = pd.concat([before_df, after_df])

    with col_a:
        fig_bar = px.bar(
            compare_df,
            x="party_label",
            y=kw_col,
            color="period",
            barmode="group",
            color_discrete_sequence=["#A8DADC", "#E63946"],
            title="期間別・政党別 累計頻度",
            labels={kw_col: "累計頻度", "party_label": "政党", "period": "期間"},
        )
        fig_bar.update_layout(height=380, legend_title="期間")
        st.plotly_chart(fig_bar, use_container_width=True)

    # 増加倍率
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
            surge_df,
            x="政党",
            y="増加倍率",
            color="政党",
            color_discrete_map=PARTY_COLORS,
            title="訪台後の増加倍率（訪台前比）",
            text="増加倍率",
        )
        fig_ratio.add_hline(y=1, line_dash="dot", line_color="gray", annotation_text="変化なし")
        fig_ratio.update_traces(texttemplate="%{text}x", textposition="outside")
        fig_ratio.update_layout(height=380, showlegend=False)
        st.plotly_chart(fig_ratio, use_container_width=True)

    # 数値テーブル
    st.subheader("数値テーブル")
    st.dataframe(surge_df.set_index("政党"), use_container_width=True)


# ─── Tab 3: キーワード比較 ───────────────────
with tab3:
    st.subheader("政党ごとのキーワード構成比較")

    monthly_all = monthly[monthly["party_label"].isin(selected_parties)].copy()
    kw_totals = []
    for kw in KEYWORDS:
        col = f"count_{kw}"
        grp = monthly_all.groupby("party_label")[col].sum().reset_index()
        grp["keyword"] = kw
        grp = grp.rename(columns={col: "count"})
        kw_totals.append(grp)

    kw_df = pd.concat(kw_totals)

    fig_heat = px.density_heatmap(
        kw_df,
        x="keyword",
        y="party_label",
        z="count",
        color_continuous_scale="Blues",
        title="政党 × キーワード ヒートマップ（全期間累計）",
        labels={"keyword": "キーワード", "party_label": "政党", "count": "頻度"},
    )
    fig_heat.update_layout(height=350)
    st.plotly_chart(fig_heat, use_container_width=True)

    # ドーナツチャートを政党ごとに並べる
    st.subheader("政党別キーワード構成比")
    cols = st.columns(len(selected_parties))
    for i, party in enumerate(selected_parties):
        party_kw = kw_df[kw_df["party_label"] == party]
        fig_pie = px.pie(
            party_kw,
            names="keyword",
            values="count",
            hole=0.45,
            color="keyword",
            title=party,
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
    col3.metric("対象政党", len(selected_parties))
