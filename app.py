import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. スプレッドシートへの接続設定
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 既存のデータを読み込む（スプレッドシートのURLをここに貼る）
# app.py
# URLからIDを抜き出し、末尾を /edit だけにする
ss_id = "1gRnwt0OMbJo1A9GCQAgBvnYXNwtrHxtQRaD34941mvQ" 
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1gRnwt0OMbJo1A9GCQAgBvnYXNwtrHxtQRaD34941mvQ/edit"

import streamlit as st
st.success("Googleスプレッドシートへの接続に成功しました！")

# 読み込み
existing_data = conn.read(spreadsheet=spreadsheet_url, usecols=[0, 1, 2])

# --- ここにあなたのログイン機能や入力フォームのコード ---

# 3. データを保存するボタンの処理（例）
if st.button("記録を保存する"):
    # 新しいデータを作成
    new_data = pd.DataFrame([{
        "date": st.session_state.get("date", "2026-04-11"),
        "subject": "セキュリティ勉強",
        "minutes": 60
    }])
    
    # 既存のデータと合体させる
    updated_df = pd.concat([existing_data, new_data], ignore_index=True)
    
    # スプレッドシートを更新！
    conn.update(spreadsheet=spreadsheet_url, data=updated_df)
    st.success("スプレッドシートに保存しました！")

import streamlit as st
import pandas as pd
import datetime
import os
import json
import streamlit_authenticator as stauth

# --- ファイルパス設定 ---
CSV_FILE = "study_log.csv"
CONFIG_FILE = "config.json"

# --- 設定・ユーザー情報の管理 ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "goal_hours": 120, 
        "exam_date": "2026-07-26", 
        "exam_name": "専門試験",
        "credentials": {"usernames": {}}
    }

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

config = load_config()

# --- 1. 初回ユーザー登録画面 ---
if not config["credentials"]["usernames"]:
    st.title("🔑 初期ユーザー設定")
    st.info("最初に使用するIDとパスワードを設定してください。")
    new_id = st.text_input("希望のログインID")
    new_pw = st.text_input("希望のパスワード", type="password")
    confirm_pw = st.text_input("パスワード（確認用）", type="password")
    
    if st.button("アカウントを作成して開始"):
        if new_id and new_pw == confirm_pw:
            hashed_pw = stauth.Hasher([new_pw]).generate()[0]
            config["credentials"]["usernames"] = {
                new_id: {"name": "管理者", "password": hashed_pw, "email": "admin@example.com"}
            }
            save_config(config)
            st.success("設定完了！再読み込みしてください。")
            st.rerun()
        else:
            st.error("入力内容を確認してください。")
    st.stop()

# --- 2. ログイン認証 ---
authenticator = stauth.Authenticate(
    credentials=config["credentials"],
    cookie_name="study_record_cookie",
    key="abcdef",
    cookie_expiry_days=30
)

authenticator.login()

auth_status = st.session_state.get("authentication_status")

if auth_status is False:
    st.error("IDまたはパスワードが間違っています")
elif auth_status is None:
    st.warning("ログインしてください")
elif auth_status:
    # --- ログイン成功後のメイン処理 ---
    
    # 共通変数の設定
    GOAL_HOURS = config.get("goal_hours", 120)
    EXAM_DATE = datetime.date.fromisoformat(config.get("exam_date", "2026-07-26"))
    EXAM_NAME = config.get("exam_name", "専門試験")
    SUBJECTS = {
        "AIリテラシー": "#ff8e8e", 
        "基本情報技術者": "#ff8ec6", 
        "HTML/CSS": "#ff8eff", 
        "Python": "#c68eff", 
        "データベース": "#8e8eff",
        "クラウド接続": "#8ec6ff",
        "Java": "#8effff",
        "応用情報技術者": "#8effc6",
        "AWS認定試験": "#8eff8e",
        "プログラミング": "#c6ff8e",
        "その他検定": "#ffff8e",
        "その他": "#ffc68e"
    }

    if not os.path.exists(CSV_FILE):
        pd.DataFrame(columns=["日付", "時間", "教科", "内容"]).to_csv(CSV_FILE, index=False, encoding="utf-8-sig")

    # --- サイドバー構成 ---
    authenticator.logout("ログアウト", "sidebar")
    st.sidebar.divider()
    
    # アプリ設定（検定名・目標など）
    with st.sidebar.expander("⚙️ アプリ設定"):
        edit_exam_name = st.text_input("検定名", EXAM_NAME)
        edit_exam_date = st.date_input("試験日", EXAM_DATE)
        edit_goal = st.number_input("目標時間(h)", min_value=1, value=int(GOAL_HOURS))
        if st.button("設定を保存"):
            config["exam_name"] = edit_exam_name
            config["exam_date"] = edit_exam_date.isoformat()
            config["goal_hours"] = edit_goal
            save_config(config)
            st.success("更新しました！")
            st.rerun()

    # 学習記録入力（ここを1回だけに整理）
    st.sidebar.header("📝 今日の学習を記録")
    today = datetime.date.today()
    study_date = st.sidebar.date_input("勉強した日", today)
    subject = st.sidebar.selectbox("教科", list(SUBJECTS.keys()))
    hour = st.sidebar.number_input("勉強時間 (h)", min_value=0.0, step=0.5)
    note = st.sidebar.text_area("内容")
    
    if st.sidebar.button("記録を保存"):
        if note and hour > 0:
            new_row = pd.DataFrame([[study_date, hour, subject, note]], columns=["日付", "時間", "教科", "内容"])
            new_row.to_csv(CSV_FILE, mode='a', header=False, index=False, encoding="utf-8-sig")
            st.sidebar.success("保存完了！")
            st.rerun()

    # --- メイン画面の表示 ---
    st.title(f"🛡️ {EXAM_NAME} 学習管理")

    df_log = pd.read_csv(CSV_FILE)
    if not df_log.empty:
        df_log["日付"] = pd.to_datetime(df_log["日付"]).dt.date
        total_hours = df_log["時間"].sum()
    else:
        total_hours = 0

    days_left = (EXAM_DATE - today).days

    # 指標カード
    col1, col2, col3 = st.columns(3)
    with col1: st.metric(f"{EXAM_NAME}まで", f"{days_left} 日")
    with col2: st.metric("合計学習時間", f"{total_hours:.1f} / {GOAL_HOURS}h")
    with col3:
        progress_per = min(100, int((total_hours / GOAL_HOURS) * 100))
        st.metric("目標達成率", f"{progress_per} %")
    st.progress(progress_per / 100)

    # タブ表示
    tab1, tab2 = st.tabs(["📊 学習グラフ", "📋 全履歴"])
    with tab1:
        if not df_log.empty:
            chart_data = df_log.groupby(["日付", "教科"])["時間"].sum().unstack().fillna(0)
            st.bar_chart(chart_data)
        else: st.info("データがありません")
    with tab2:
        st.dataframe(df_log.sort_values(by="日付", ascending=False), use_container_width=True)