# 国会発言分析 Phase 1

> ペロシ訪台（2022年8月）前後の国会発言を政党別・キーワード別に分析するStreamlitアプリ

## ファイル構成

```
diet_analysis/
├── fetch_data.py       # ① APIからデータ取得 → data/speeches_raw.csv
├── analyze.py          # ② 集計・前処理    → data/freq_*.csv
├── make_demo_data.py   # ①②の代替（デモ用）
├── app.py              # ③ Streamlitアプリ
├── requirements.txt    # Streamlit Cloud用
└── data/               # ← 自動生成される
```

---

## 使い方

### A. 実データで動かす（推奨）

```bash
# 1. 依存インストール
pip install -r requirements.txt

# 2. APIからデータ取得（数分かかる）
python fetch_data.py

# 3. 集計
python analyze.py

# 4. アプリ起動
streamlit run app.py
```

### B. デモデータで動かす（API不要）

```bash
pip install -r requirements.txt
python make_demo_data.py   # モックデータ生成
streamlit run app.py
```

---

## Streamlit Cloudへのデプロイ

1. このディレクトリをGitHubリポジトリにプッシュ
2. [streamlit.io/cloud](https://streamlit.io/cloud) でリポジトリを連携
3. `app.py` を指定してデプロイ

**注意**：Streamlit Cloud上ではAPIへのアクセスができないため、  
`data/` ディレクトリのCSVファイルをあらかじめコミットしておくこと。

---

## アプリの機能（Phase 1）

| タブ | 内容 |
|------|------|
| 時系列トレンド | 月次 or 日次（7日移動平均）の頻度推移、ペロシ訪台マーカー付き |
| 前後比較 | 訪台前後の累計頻度・増加倍率の棒グラフ |
| キーワード比較 | 政党×キーワードのヒートマップ・構成比ドーナツ |
| データ概要 | 発言件数・発言者数・平均文字数のサマリ |

---

## Phase 2への接続ポイント

`data/speeches_clean.csv` の `speech_clean` 列を  
BERTのファインチューニング入力として使う。

```python
# analyze.py が出力するspeeches_clean.csvをそのまま使う
df = pd.read_csv("data/speeches_clean.csv")
texts = df["speech_clean"].tolist()   # → BERT入力
```
