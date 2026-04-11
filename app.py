import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import os
import json
import streamlit_authenticator as stauth

# --- 0. 基本設定 ---
EXAM_NAME_DEFAULT = "基本情報技術者"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1gRnwt0OMbJo1A9GCQAgBvnYXNwtrHxtQRaD34941mvQ/edit"
CONFIG_FILE = "config.json"

st.set_page_config(page_title="学習管理アプリ", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. 関数定義 ---
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

# --- 2. 初回ユーザー登録 ---
if not config["credentials"]["usernames"]:
    st.title("🔑 初期ユーザー設定")
    new_id = st.text_input("希望のログインID")
    new_pw = st.text_input("希望のパスワード", type="password")
    confirm_pw = st.text_input("パスワード（確認用）", type="password")
    if st.button("アカウントを作成して開始"):
        if new_id and new_pw == confirm_pw:
            hashed_pw = stauth.Hasher.hash(new_pw)
            config["credentials"]["usernames"] = {
                new_id: {"name": "管理者", "password": hashed_pw, "email": "admin@example.com"}
            }
            save_config(config)
            st.success("設定完了！再読み込みしてください。")
            st.rerun()
    st.stop()

# --- 3. ログイン認証 ---
authenticator = stauth.Authenticate(
    credentials=config["credentials"],
    cookie_name="study_record_cookie",
    key="abcdef",
    cookie_expiry_days=30
)
authenticator.login()

auth_status = st.session_state.get("authentication_status")

if auth_status:
    # ログイン成功後のメイン処理
    GOAL_HOURS = config.get("goal_hours", 120)
    EXAM_DATE = datetime.date.fromisoformat(config.get("exam_date", "2026-07-26"))
    EXAM_NAME = config.get("exam_name", EXAM_NAME_DEFAULT)
    SUBJECTS = {
        "AIリテラシー": "#ff8e8e", "基本情報技術者": "#ff8ec6", "HTML/CSS": "#ff8eff", 
        "Python": "#c68eff", "データベース": "#8e8eff", "クラウド接続": "#8ec6ff",
        "Java": "#8effff", "応用情報技術者": "#8effc6", "AWS認定試験": "#8eff8e",
        "プログラミング": "#c6ff8e", "その他検定": "#ffff8e", "その他": "#ffc68e"
    }

    # --- サイドバー：学習記録の入力 ---
    authenticator.logout("ログアウト", "sidebar")
    st.sidebar.divider()
    
    with st.sidebar.expander("⚙️ アプリ設定"):
        edit_exam_name = st.text_input("検定名", EXAM_NAME)
        edit_exam_date = st.date_input("試験日", EXAM_DATE)
        edit_goal = st.number_input("目標時間(h)", min_value=1, value=int(GOAL_HOURS))
        if st.button("設定を保存"):
            config["exam_name"] = edit_exam_name
            config["exam_date"] = edit_exam_date.isoformat()
            config["goal_hours"] = edit_goal
            save_config(config)
            st.rerun()

    st.sidebar.header("📝 今日の学習を記録")
    study_date = st.sidebar.date_input("勉強した日", datetime.date.today())
    subject = st.sidebar.selectbox("教科", list(SUBJECTS.keys()))
    hour = st.sidebar.number_input("勉強時間 (h)", min_value=0.0, step=0.5)
    note = st.sidebar.text_area("内容")
    
    if st.sidebar.button("記録を保存"):
        if note and hour > 0:
            # logsシートに追記
            current_logs = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="logs", ttl=0)
            new_row = pd.DataFrame([[study_date.strftime("%Y-%m-%d"), hour, subject, note]], 
                                   columns=["日付", "時間", "教科", "内容"])
            updated_logs = pd.concat([current_logs, new_row], ignore_index=True)
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet="logs", data=updated_logs)
            st.sidebar.success("スプレッドシートに保存しました！")
            st.rerun()

    # --- メイン画面 ---
    st.title(f"🛡️ {EXAM_NAME} 学習管理")

    # 1. カウントダウン
    st.subheader("🎯 目標カウントダウン")
    event_df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="events", ttl=0)
    if not event_df.empty:
        cols = st.columns(3)
        for i, row in event_df.iterrows():
            with cols[i % 3]:
                target = pd.to_datetime(row['target_date'])
                diff = (target - pd.to_datetime(datetime.date.today())).days
                if diff >= 0: st.metric(label=row['event_name'], value=f"あと {diff} 日")
                else: st.caption(f"✅ {row['event_name']} 完了")
    
    # 2. 学習ログの読み込みとサマリー
    df_log = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="logs", ttl=0)
    if not df_log.empty:
        df_log["日付"] = pd.to_datetime(df_log["日付"]).dt.date
        df_log["時間"] = pd.to_numeric(df_log["時間"])
        total_hours = df_log["時間"].sum()
    else:
        total_hours = 0

    c1, c2, c3 = st.columns(3)
    main_days_left = (EXAM_DATE - datetime.date.today()).days
    with c1: st.metric(f"{EXAM_NAME}まで", f"{main_days_left} 日")
    with c2: st.metric("合計学習時間", f"{total_hours:.1f} / {GOAL_HOURS}h")
    with c3:
        prog = min(100, int((total_hours / GOAL_HOURS) * 100))
        st.metric("目標達成率", f"{prog} %")
    st.progress(prog / 100)

    # 3. グラフと履歴
    t1, t2 = st.tabs(["📊 学習グラフ", "📋 全履歴"])
    with t1:
        if not df_log.empty:
            chart_data = df_log.groupby(["日付", "教科"])["時間"].sum().unstack().fillna(0)
            st.bar_chart(chart_data)
        else: st.info("データがありません")
    with t2:
        st.dataframe(df_log.sort_values(by="日付", ascending=False), use_container_width=True)

    # 4. イベント追加
    st.divider()
    with st.expander("➕ 新しいイベント・検定を追加する"):
        with st.form("event_form_v2", clear_on_submit=True):
            new_ev_name = st.text_input("イベント名")
            new_ev_date = st.date_input("日付")
            if st.form_submit_button("イベントを登録"):
                if new_ev_name:
                    current_events = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="events", ttl=0)
                    new_event = pd.DataFrame([{"event_name": new_ev_name, "target_date": new_ev_date.strftime("%Y-%m-%d")}])
                    updated_ev = pd.concat([current_events, new_event], ignore_index=True)
                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="events", data=updated_ev)
                    st.success("登録完了！")
                    st.rerun()

    # 5. イベント削除
    with st.expander("🗑️ 登録済みのイベントを削除する"):
        if not event_df.empty:
            del_target = st.selectbox("削除するイベントを選択", event_df["event_name"].tolist())
            if st.button("選択したイベントを削除"):
                updated_ev = event_df[event_df["event_name"] != del_target]
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="events", data=updated_ev)
                st.rerun()

    # 6. 学習記録の修正・削除 (スプレッドシート版)
    st.divider()
    with st.expander("🔧 学習記録の修正・削除"):
        if not df_log.empty:
            df_log_display = df_log.copy()
            df_log_display["display"] = df_log["日付"].astype(str) + " | " + df_log["教科"]
            target_idx = st.selectbox("修正・削除する記録を選択", df_log_display.index, format_func=lambda x: df_log_display.loc[x, "display"])
            
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                edit_sub = st.selectbox("教科", list(SUBJECTS.keys()), index=list(SUBJECTS.keys()).index(df_log.loc[target_idx, "教科"]))
                edit_h = st.number_input("時間 (h)", value=float(df_log.loc[target_idx, "時間"]), step=0.5)
            with col_e2:
                edit_d = st.date_input("日付", df_log.loc[target_idx, "日付"])
                edit_n = st.text_area("内容", value=df_log.loc[target_idx, "内容"])

            b1, b2 = st.columns(2)
            if b1.button("🆙 記録を更新する"):
                df_log.loc[target_idx, ["日付", "時間", "教科", "内容"]] = [edit_d.strftime("%Y-%m-%d"), edit_h, edit_sub, edit_n]
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="logs", data=df_log)
                st.rerun()
            if b2.button("🗑️ この記録を削除する"):
                df_log = df_log.drop(target_idx)
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="logs", data=df_log)
                st.rerun()

elif auth_status is False:
    st.error("IDまたはパスワードが間違っています")
else:
    st.warning("ログインしてください")