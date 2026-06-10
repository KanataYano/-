"""
fetch_data.py
国会議事録検索システムAPIからデータを取得してCSVに保存する

使い方:
    python fetch_data.py

出力:
    data/speeches_raw.csv   ← 取得した発言データ
    data/fetch_log.txt      ← 取得ログ
"""

import requests
import pandas as pd
import time
import json
import os
from datetime import datetime

# ────────────────────────────────────────────
# 設定
# ────────────────────────────────────────────
API_BASE = "https://kokkai.ndl.go.jp/api/speech"

# 分析対象政党（APIのpartyパラメータに渡す文字列）
PARTIES = {
    "自民": "自由民主党",
    "立憲": "立憲民主党",
    "維新": "日本維新の会",
}

# 分析キーワード
KEYWORDS = ["台湾", "中国", "安全保障", "有事"]

# 分析期間（ペロシ訪台前後3ヶ月）
DATE_FROM = "2022-05-01"
DATE_UNTIL = "2022-11-30"

# 1リクエストあたりの最大件数（API上限100）
MAX_RECORDS = 100

# リクエスト間隔（秒）― API負荷対策
SLEEP_SEC = 1.0

OUTPUT_DIR = "data"
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "speeches_raw.csv")
LOG_FILE   = os.path.join(OUTPUT_DIR, "fetch_log.txt")


# ────────────────────────────────────────────
# API取得関数
# ────────────────────────────────────────────
def fetch_speeches(keyword: str, party: str, date_from: str, date_until: str) -> list[dict]:
    """
    指定キーワード×政党×期間の発言を全件取得して返す。
    ページネーションを自動処理。
    """
    results = []
    start_record = 1

    while True:
        params = {
            "keyword":        keyword,
            "party":          party,
            "from":           date_from,
            "until":          date_until,
            "maximumRecords": MAX_RECORDS,
            "startRecord":    start_record,
            "recordPacking":  "json",
        }

        try:
            resp = requests.get(API_BASE, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"  [ERROR] {e}")
            break
        except json.JSONDecodeError:
            print(f"  [ERROR] JSONパース失敗: {resp.text[:200]}")
            break

        speeches = data.get("speechRecord", [])
        if not speeches:
            break

        results.extend(speeches)

        # 次ページがあるか確認
        number_of_records = int(data.get("numberOfRecords", 0))
        if start_record + MAX_RECORDS - 1 >= number_of_records:
            break

        start_record += MAX_RECORDS
        time.sleep(SLEEP_SEC)

    return results


# ────────────────────────────────────────────
# メイン処理
# ────────────────────────────────────────────
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_rows = []
    log_lines = [f"取得開始: {datetime.now().isoformat()}"]

    total_combinations = len(KEYWORDS) * len(PARTIES)
    done = 0

    for keyword in KEYWORDS:
        for party_label, party_name in PARTIES.items():
            done += 1
            print(f"[{done}/{total_combinations}] キーワード='{keyword}' 政党='{party_name}' 取得中...")

            speeches = fetch_speeches(keyword, party_name, DATE_FROM, DATE_UNTIL)
            count = len(speeches)
            print(f"  → {count}件取得")
            log_lines.append(f"  {keyword} × {party_name}: {count}件")

            for s in speeches:
                all_rows.append({
                    "speech_id":    s.get("speechID", ""),
                    "date":         s.get("date", ""),
                    "session":      s.get("session", ""),        # 国会回次
                    "house":        s.get("nameOfHouse", ""),    # 院名
                    "meeting":      s.get("nameOfMeeting", ""),  # 委員会等
                    "speaker":      s.get("speaker", ""),        # 発言者名
                    "party":        s.get("speakerGroup", ""),   # 所属会派（APIの値をそのまま使う）
                    "party_label":  party_label,                 # 我々が指定したラベル
                    "keyword":      keyword,                     # どのキーワードでヒットしたか
                    "speech":       s.get("speech", ""),         # 発言本文
                    "speech_url":   s.get("speechURL", ""),      # 元URLへのリンク
                })

            time.sleep(SLEEP_SEC)

    # DataFrame化して保存
    df = pd.DataFrame(all_rows)

    # 重複除去（同じ発言が複数キーワードでヒットする場合がある）
    before = len(df)
    df_dedup = df.drop_duplicates(subset=["speech_id", "keyword"])
    after = len(df_dedup)
    print(f"\n重複除去: {before} → {after} 件")

    df_dedup.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"保存完了: {OUTPUT_CSV}")

    log_lines.append(f"合計: {before}件（重複除去後: {after}件）")
    log_lines.append(f"取得終了: {datetime.now().isoformat()}")

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    print(f"ログ保存: {LOG_FILE}")


if __name__ == "__main__":
    main()
