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

# --- 1. 関数定義 (ログイン情報用) ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "credentials": {"usernames": {}}
    }

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

login_config = load_config()

# --- 2. 初回ユーザー登録 ---
if not login_config["credentials"]["usernames"]:
    st.title("🔑 初期ユーザー設定")
    new_id = st.text_input("希望のログインID")
    new_pw = st.text_input("希望 of パスワード", type="password")
    confirm_pw = st.text_input("パスワード（確認用）", type="password")
    if st.button("アカウントを作成して開始"):
        if new_id and new_pw == confirm_pw:
            hashed_pw = stauth.Hasher.hash(new_pw)
            login_config["credentials"]["usernames"] = {
                new_id: {"name": "管理者", "password": hashed_pw, "email": "admin@example.com"}
            }
            save_config(login_config)
            st.success("設定完了！再読み込みしてください。")
            st.rerun()
    st.stop()

# --- 3. ログイン認証 ---
authenticator = stauth.Authenticate(
    credentials=login_config["credentials"],
    cookie_name="study_record_cookie",
    key="abcdef",
    cookie_expiry_days=30
)
authenticator.login()

auth_status = st.session_state.get("authentication_status")

if auth_status:
    # --- アプリ設定の読み込み (スプレッドシートのconfigシートから) ---
    try:
        conf_df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="config", ttl=0)
        if not conf_df.empty:
            # 1行目のデータを使用
            row = conf_df.iloc[0]
            EXAM_NAME = row["exam_name"]
            EXAM_DATE = datetime.date.fromisoformat(str(row["exam_date"]))
            GOAL_HOURS = int(row["goal_hours"])
        else:
            EXAM_NAME, EXAM_DATE, GOAL_HOURS = EXAM_NAME_DEFAULT, datetime.date(2026, 7, 26), 120
    except Exception as e:
        st.error(f"設定読み込みエラー: {e}")
        EXAM_NAME, EXAM_DATE, GOAL_HOURS = EXAM_NAME_DEFAULT, datetime.date(2026, 7, 26), 120

    SUBJECTS = {
        "AIリテラシー": "#ff8e8e", "基本情報技術者": "#ff8ec6", "HTML/CSS": "#ff8eff", 
        "Python": "#c68eff", "データベース": "#8e8eff", "クラウド接続": "#8ec6ff",
        "Java": "#8effff", "応用情報技術者": "#8effc6", "AWS認定試験": "#8eff8e",
        "プログラミング": "#c6ff8e", "その他検定": "#ffff8e", "その他": "#ffc68e"
    }

    # --- サイドバー構成 ---
    authenticator.logout("ログアウト", "sidebar")
    st.sidebar.divider()
    
    with st.sidebar.expander("⚙️ アプリ設定"):
        edit_exam_name = st.text_input("検定名", EXAM_NAME)
        edit_exam_date = st.date_input("試験日", EXAM_DATE)
        edit_goal = st.number_input("目標時間(h)", min_value=1, value=int(GOAL_HOURS))
        if st.button("設定を保存"):
            # スプレッドシートのconfigシートを更新（1行だけのデータフレームとして上書き）
            new_conf = pd.DataFrame([{
                "exam_name": edit_exam_name,
                "exam_date": edit_exam_date.isoformat(),
                "goal_hours": edit_goal
            }])
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet="config", data=new_conf)
            st.success("スプレッドシートの設定を更新しました！")
            st.rerun()

    st.sidebar.header("📝 今日の学習を記録")
    study_date = st.sidebar.date_input("勉強した日", datetime.date.today())
    subject = st.sidebar.selectbox("教科", list(SUBJECTS.keys()))
    hour = st.sidebar.number_input("勉強時間 (h)", min_value=0.0, step=0.5)
    note = st.sidebar.text_area("内容")
    
    if st.sidebar.button("記録を保存"):
        if note and hour > 0:
            current_logs = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="logs", ttl=0)
            new_row = pd.DataFrame([[study_date.strftime("%Y-%m-%d"), hour, subject, note]], 
                                   columns=["日付", "時間", "教科", "内容"])
            updated_logs = pd.concat([current_logs, new_row], ignore_index=True)
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet="logs", data=updated_logs)
            st.sidebar.success("保存完了！")
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
    
    # 2. 学習状況サマリー
    df_log = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="logs", ttl=0)
    if not df_log.empty:
        df_log["日付"] = pd.to_datetime(df_log["日付"]).dt.date
        df_log["時間"] = pd.to_numeric(df_log["時間"])
        total_hours = df_log["時間"].sum()
    else:
        total_hours = 0

    c1, c2, c3 = st.columns(3)
    main_days_left = (EXAM_DATE - datetime.date.today()).days
    with c1: st.metric(f"{EXAM_NAME}まで", f"{max(0, main_days_left)} 日")
    with c2: st.metric("合計学習時間", f"{total_hours:.1f} / {GOAL_HOURS}h")
    with c3:
        prog = min(100, int((total_hours / GOAL_HOURS) * 100)) if GOAL_HOURS > 0 else 0
        st.metric("目標達成率", f"{prog} %")
    st.progress(prog / 100)

    # 3. グラフと履歴
    # 3. グラフと履歴 (タブを3つに増やします)
    t1, t2, t3 = st.tabs(["📊 学習グラフ", "🔍 教科別分析", "📋 全履歴"])
    
    with t1:
        if not df_log.empty:
            chart_data = df_log.groupby(["日付", "教科"])["時間"].sum().unstack().fillna(0)
            st.bar_chart(chart_data)
        else: st.info("データがありません")

    with t2:
        if not df_log.empty:
            st.subheader("特定教科の深掘り分析")
            # 分析したい教科を選択
            target_sub = st.selectbox("分析する教科を選んでください", list(SUBJECTS.keys()))
            
            # 選択された教科のデータだけを抽出 (フィルタリング)
            sub_df = df_log[df_log["教科"] == target_sub].sort_values("日付")
            
            if not sub_df.empty:
                col_sub1, col_sub2 = st.columns(2)
                sub_total = sub_df["時間"].sum()
                sub_count = len(sub_df)
                
                with col_sub1:
                    st.metric(f"{target_sub} の合計時間", f"{sub_total:.1f} h")
                with col_sub2:
                    st.metric("学習回数", f"{sub_count} 回")
                
                # その教科だけの推移グラフ
                st.line_chart(sub_df.set_index("日付")["時間"])
                
                # その教科の学習内容メモ一覧
                st.write(f"📝 {target_sub} の学習メモ")
                st.dataframe(sub_df[["日付", "時間", "内容"]].sort_values("日付", ascending=False), use_container_width=True)
            else:
                st.info(f"{target_sub} の記録はまだありません。")
        else:
            st.info("データがありません")

    with t3:
        st.dataframe(df_log.sort_values(by="日付", ascending=False), use_container_width=True)
        
    # 4. イベント追加・削除
    st.divider()
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        with st.expander("➕ 新しいイベントを追加"):
            with st.form("event_form_v2", clear_on_submit=True):
                new_ev_name = st.text_input("イベント名")
                new_ev_date = st.date_input("日付")
                if st.form_submit_button("登録"):
                    if new_ev_name:
                        current_events = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="events", ttl=0)
                        new_ev = pd.DataFrame([{"event_name": new_ev_name, "target_date": new_ev_date.strftime("%Y-%m-%d")}])
                        conn.update(spreadsheet=SPREADSHEET_URL, worksheet="events", data=pd.concat([current_events, new_ev], ignore_index=True))
                        st.rerun()
    with col_f2:
        with st.expander("🗑️ イベントを削除"):
            if not event_df.empty:
                del_target = st.selectbox("削除対象", event_df["event_name"].tolist())
                if st.button("削除"):
                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="events", data=event_df[event_df["event_name"] != del_target])
                    st.rerun()

    # 5. 記録の修正・削除
    with st.expander("🔧 学習記録の修正・削除"):
        if not df_log.empty:
            df_log_display = df_log.copy()
            df_log_display["display"] = df_log["日付"].astype(str) + " | " + df_log["教科"]
            target_idx = st.selectbox("選択", df_log_display.index, format_func=lambda x: df_log_display.loc[x, "display"])
            
            ce1, ce2 = st.columns(2)
            with ce1:
                edit_sub = st.selectbox("教科 ", list(SUBJECTS.keys()), index=list(SUBJECTS.keys()).index(df_log.loc[target_idx, "教科"]))
                edit_h = st.number_input("時間 (h) ", value=float(df_log.loc[target_idx, "時間"]), step=0.5)
            with ce2:
                edit_d = st.date_input("日付 ", df_log.loc[target_idx, "日付"])
                edit_n = st.text_area("内容 ", value=df_log.loc[target_idx, "内容"])

            if st.button("🆙 修正を保存"):
                df_log.loc[target_idx, ["日付", "時間", "教科", "内容"]] = [edit_d.strftime("%Y-%m-%d"), edit_h, edit_sub, edit_n]
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="logs", data=df_log)
                st.rerun()
            if st.button("🗑️ 記録を削除"):
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="logs", data=df_log.drop(target_idx))
                st.rerun()

elif auth_status is False:
    st.error("IDまたはパスワードが間違っています")
else:
    st.warning("ログインしてください")