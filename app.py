import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import streamlit_authenticator as stauth

# --- 0. 基本設定 ---
SPREADSHEET_URL = "あなたのスプレッドシートURL"

st.set_page_config(page_title="みんなのセキュリティ学習管理", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. データ取得関数 ---
def get_all_users():
    try:
        df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="users", ttl=0)
        credentials = {"usernames": {}}
        for _, row in df.iterrows():
            credentials["usernames"][str(row["username"])] = {
                "name": str(row["name"]),
                "password": str(row["password"])
            }
        return credentials
    except: return {"usernames": {}}

def get_user_config(username):
    try:
        conf_df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="config", ttl=0)
        user_conf = conf_df[conf_df["username"] == username]
        if not user_conf.empty:
            row = user_conf.iloc[0]
            return row["exam_name"], datetime.date.fromisoformat(str(row["exam_date"])), int(row["goal_hours"])
    except: pass
    return "専門卒業までの勉強記録", datetime.date(2028, 3, 31), 1000

# ★追加：ユーザーごとの教科リストを取得
def get_user_subjects(username):
    try:
        sub_df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="user_subjects", ttl=0)
        user_subs = sub_df[sub_df["username"] == username]
        if not user_subs.empty:
            return dict(zip(user_subs["subject_name"], user_subs["color"]))
    except: pass
    # 初回登録用：デフォルト教科
    return {"Python": "#c68eff", "基本情報技術者": "#ff8ec6", "その他": "#ffc68e"}

# --- 2. 認証 ---
credentials = get_all_users()
authenticator = stauth.Authenticate(credentials, "study_app_session", "auth_key_12345", cookie_expiry_days=30)

st.sidebar.title("学習管理")
menu = ["ログイン", "新規ユーザー登録"]
choice = st.sidebar.selectbox("メニュー", menu)

# --- 3. 新規登録 ---
if choice == "新規ユーザー登録":
    st.title("新規アカウント作成")
    with st.form("signup_form"):
        new_user = st.text_input("ユーザーID")
        new_display_name = st.text_input("表示名")
        new_pw = st.text_input("パスワード", type="password")
        if st.form_submit_button("登録する"):
            if not new_user or not new_pw:
                st.error("入力してください")
            elif new_user in credentials["usernames"]:
                st.error("既に使われています")
            else:
                hashed_pw = stauth.Hasher.hash(new_pw)
                # users & config登録
                u_df = pd.DataFrame([{"username": new_user, "name": new_display_name, "password": hashed_pw}])
                c_df = pd.DataFrame([{"username": new_user, "exam_name": "専門卒業までの勉強記録", "exam_date": "2028-03-31", "goal_hours": 1000}])
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="users", data=pd.concat([conn.read(spreadsheet=SPREADSHEET_URL, worksheet="users", ttl=0), u_df]))
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="config", data=pd.concat([conn.read(spreadsheet=SPREADSHEET_URL, worksheet="config", ttl=0), c_df]))
                
                # ★初期教科を登録
                initial_subs = pd.DataFrame([
                    {"username": new_user, "subject_name": "Python", "color": "#c68eff"},
                    {"username": new_user, "subject_name": "基本情報技術者", "color": "#ff8ec6"},
                    {"username": new_user, "subject_name": "その他", "color": "#ffc68e"}
                ])
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="user_subjects", data=initial_subs)
                st.success("登録完了！")

# --- 4. メインコンテンツ ---
elif choice == "ログイン":
    name, auth_status, username = authenticator.login("main")

    if auth_status:
        EXAM_NAME, EXAM_DATE, GOAL_HOURS = get_user_config(username)
        SUBJECTS = get_user_subjects(username) # スプレッドシートから読み込み

        st.sidebar.write(f"こんにちは、{name} さん")
        authenticator.logout("ログアウト", "sidebar")
        
        # --- ★追加：教科登録機能 ---
        with st.sidebar.expander("教科の追加・編集"):
            new_sub_name = st.text_input("新しい教科名")
            new_sub_color = st.color_picker("教科の色を選択", "#8effff")
            if st.button("教科を追加"):
                if new_sub_name and new_sub_name not in SUBJECTS:
                    sub_history = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="user_subjects", ttl=0)
                    new_sub_row = pd.DataFrame([{"username": username, "subject_name": new_sub_name, "color": new_sub_color}])
                    conn.update(spreadsheet=SPREADSHEET_URL, worksheet="user_subjects", data=pd.concat([sub_history, new_sub_row]))
                    st.cache_data.clear()
                    st.rerun()

        # --- アプリ設定 (目標変更) ---
        with st.sidebar.expander("目標設定"):
            edit_exam_name = st.text_input("目標タイトル", EXAM_NAME)
            edit_exam_date = st.date_input("目標日", EXAM_DATE)
            edit_goal = st.number_input("目標時間(h)", value=int(GOAL_HOURS))
            if st.button("設定を保存"):
                conf_df = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="config", ttl=0)
                conf_df.loc[conf_df["username"] == username, ["exam_name", "exam_date", "goal_hours"]] = [edit_exam_name, edit_exam_date.isoformat(), edit_goal]
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="config", data=conf_df)
                st.cache_data.clear()
                st.rerun()

        # 学習入力
        st.sidebar.header("記録")
        study_date = st.sidebar.date_input("勉強日", datetime.date.today())
        subject = st.sidebar.selectbox("教科", list(SUBJECTS.keys()))
        hour = st.sidebar.number_input("時間(h)", min_value=0.0, step=0.5)
        note = st.sidebar.text_area("内容")
        if st.sidebar.button("保存"):
            if note and hour > 0:
                all_logs = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="logs", ttl=0)
                new_row = pd.DataFrame([[username, study_date.strftime("%Y-%m-%d"), hour, subject, note]], columns=["username", "日付", "時間", "教科", "内容"])
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="logs", data=pd.concat([all_logs, new_row]))
                st.cache_data.clear()
                st.rerun()

        # --- 表示部分 ---
        st.title(f"{EXAM_NAME}")
        all_logs = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="logs", ttl=60)
        df_log = all_logs[all_logs["username"] == username].copy() if not all_logs.empty else pd.DataFrame()

        if not df_log.empty:
            df_log["時間"] = pd.to_numeric(df_log["時間"])
            total_h = df_log["時間"].sum()
        else: total_h = 0

        c1, c2, c3 = st.columns(3)
        with c1: st.metric("目標まで", f"{(EXAM_DATE - datetime.date.today()).days} 日")
        with c2: st.metric("合計時間", f"{total_h:.1f} / {GOAL_HOURS}h")
        with c3: 
            prog = min(100, int((total_h / GOAL_HOURS) * 100)) if GOAL_HOURS > 0 else 0
            st.metric("達成率", f"{prog}%")
        st.progress(prog / 100)

        t1, t2, t3 = st.tabs(["推移", "分析", "履歴"])
        with t1:
            if not df_log.empty:
                chart_data = df_log.groupby(["日付", "教科"])["時間"].sum().unstack().fillna(0)
                # ユーザーが登録した教科の色を適用
                color_list = [SUBJECTS.get(sub, "#cccccc") for sub in chart_data.columns]
                st.bar_chart(chart_data, color=color_list)
        with t2:
            if not df_log.empty:
                target_sub = st.selectbox("分析する教科", list(SUBJECTS.keys()))
                sub_df = df_log[df_log["教科"] == target_sub]
                if not sub_df.empty:
                    st.line_chart(sub_df.set_index("日付")["時間"])
        with t3:
            st.dataframe(df_log.sort_values("日付", ascending=False), use_container_width=True)

    elif auth_status is False: st.error("ログイン失敗")
    else: st.warning("ログインしてください")