# =============================================================
# 🏀 Streamlit 啟動 Cell v2（修正版）
# =============================================================

# ── Step 1：安裝套件 ──
import subprocess
subprocess.run(['pip', 'install', 'streamlit', 'plotly', '--quiet'],
               capture_output=True)
print("✅ 套件安裝完成")

# ── Step 2：直接把 streamlit app 寫入 Colab 本地 ──
# （不依賴 Drive 路徑，直接內嵌）
import os

APP_CODE = '''
import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import os, json as _json2
import urllib.parse
import traceback
import requests

_cfg_path = '/content/streamlit_config.json'
if os.path.exists(_cfg_path):
    with open(_cfg_path) as _f2:
        _cfg2 = _json2.load(_f2)
    IS_DEV  = _cfg2.get('IS_DEV', False)
    DB_PATH = _cfg2.get('DB_PATH', '/content/drive/MyDrive/NBA_V341/nba_strategy.db')
    GEMINI_API_KEY = _cfg2.get('GEMINI_API_KEY')
    TELEGRAM_TOKEN = _cfg2.get('TELEGRAM_TOKEN')
    TELEGRAM_CHAT_ID = _cfg2.get('TELEGRAM_CHAT_ID')
else:
    IS_DEV  = False
    DB_PATH = '/content/drive/MyDrive/NBA_V341/nba_strategy.db'
    GEMINI_API_KEY = None
    TELEGRAM_TOKEN = None
    TELEGRAM_CHAT_ID = None

if not GEMINI_API_KEY:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not TELEGRAM_TOKEN:
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_CHAT_ID:
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

TZ_TW   = ZoneInfo('Asia/Taipei')
TZ_EST  = ZoneInfo('America/New_York')

# 中文隊名對照
TEAM_ZH = {
    "Atlanta Hawks":"老鷹","Boston Celtics":"塞爾提克","Brooklyn Nets":"籃網",
    "Charlotte Hornets":"黃蜂","Chicago Bulls":"公牛","Cleveland Cavaliers":"騎士",
    "Dallas Mavericks":"獨行俠","Denver Nuggets":"金塊","Detroit Pistons":"活塞",
    "Golden State Warriors":"勇士","Houston Rockets":"火箭","Indiana Pacers":"溜馬",
    "LA Clippers":"快艇","LA Lakers":"湖人","Los Angeles Clippers":"快艇",
    "Los Angeles Lakers":"湖人","Memphis Grizzlies":"灰熊","Miami Heat":"熱火",
    "Milwaukee Bucks":"公鹿","Minnesota Timberwolves":"灰狼",
    "New Orleans Pelicans":"鵜鶘","New York Knicks":"尼克",
    "Oklahoma City Thunder":"雷霆","Orlando Magic":"魔術",
    "Philadelphia 76ers":"76人","Phoenix Suns":"太陽",
    "Portland Trail Blazers":"拓荒者","Sacramento Kings":"國王",
    "San Antonio Spurs":"馬刺","Toronto Raptors":"暴龍",
    "Utah Jazz":"爵士","Washington Wizards":"巫師",
}
def tn(name):
    if not name: return name or ""
    zh = TEAM_ZH.get(name, "")
    return f"{name}（{zh}）" if zh else name

def tg_send(lines: list, token=None, chat_id=None) -> bool:
    """
    安全發送 Telegram 訊息。
    lines: 字串清單，每條會自動加换行，完全避免 f-string 換行問題。
    """
    import urllib.parse, requests as _r
    _tok  = token   or TELEGRAM_TOKEN
    _chat = chat_id or TELEGRAM_CHAT_ID
    if not _tok or not _chat:
        return False
    try:
        msg = chr(10).join(str(l) for l in lines)
        url = f"https://api.telegram.org/bot{_tok}/sendMessage"
        _r.get(url, params={"chat_id": _chat, "text": msg}, timeout=5)
        return True
    except Exception as _e:
        print(f"[tg_send] 失敗: {_e}")
        return False

st.set_page_config(
    page_title="🏀 NBA 戰情系統 V34.1" + (" [測試版]" if IS_DEV else ""),
    page_icon="🧪" if IS_DEV else "🏀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
div[data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 16px;
}
</style>
""", unsafe_allow_html=True)

def query(sql, params=()):
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(sql, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        st.error(f"DB 錯誤：{e}")
        return pd.DataFrame()

# ── Sidebar ──
with st.sidebar:
    st.markdown("## 🏀 NBA V34.1")
    if IS_DEV:
        st.warning("🧪 測試模式｜資料來自 DEV DB｜請勿用於實際下注")
    else:
        st.success("🏆 正式模式｜資料來自正式 DB")
    st.markdown("---")
    now_tw  = datetime.now(TZ_TW).strftime("%m/%d %H:%M")
    now_est = datetime.now(TZ_EST).strftime("%m/%d %H:%M")
    st.markdown(f"🕐 台灣：**{now_tw}**")
    st.markdown(f"🕐 美東：**{now_est}**")
    st.markdown("---")
    page = st.selectbox("📋 頁面選擇", [
        "🏠 今日戰情",
        "📅 選擇日期",
        "💰 我的下注記錄",
        "📈 ROI 曲線",
        "🏁 歷史對獎",
        "📊 命中率日曆",
        "📷 場中截圖分析",
        "🔬 參數調整",
    ])
    st.markdown("---")
    today = datetime.now(TZ_EST).date()
    sel_date   = st.date_input("查看日期", value=today)
    date_start = st.date_input("開始日期", value=today - timedelta(days=30))
    date_end   = st.date_input("結束日期", value=today)
    st.markdown("---")
    if st.button("🔄 重新整理"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("---")
    filter_clean = st.checkbox("🛡️ 僅顯示乾淨盤 (Clean Game)", value=False, help="過濾有大勝、傷兵過多或誘餌盤口風險的比賽")
    st.markdown("#### ⚙️ 參數滑桿")
    sigma_n   = st.slider("σ 正常",   8.0, 16.0, 12.0, 0.5)
    sigma_c   = st.slider("σ 崩潰",  10.0, 20.0, 15.0, 0.5)
    mkt_w     = st.slider("盤口錨定", 0.0,  0.6,  0.35, 0.05)
    ev_thresh = st.slider("EV 門檻",  0.04, 0.30, 0.08, 0.01)

# ══════════════════════════════════════
# 頁面 1：今日戰情
# ══════════════════════════════════════
if page == "🏠 今日戰情":
    st.title("🏀 今日戰情")
    today_str = datetime.now(TZ_EST).strftime("%Y-%m-%d")
    st.caption(f"比賽日期（美東）：{today_str}  |  台灣時間：{now_tw}")
    st.markdown("---")

    df = query("""
        SELECT home_team, away_team, game_time_est,
               recommended_bet, confidence_level,
               ev_value, suggested_bet_pct,
               win_prob_home, win_prob_away,
               ai_score_home, ai_score_away,
               ai_spread, ai_total,
               collapse_flag, early_bet_signal, sigma_used,
               injury_snapshot, pace_home, pace_away,
               open_line, live_line, total_line, risk_tags, ot_prob, playoff_mode
        FROM predictions
        WHERE game_date_est = ?
        GROUP BY home_team, away_team
        HAVING created_at_est = MAX(created_at_est)
        ORDER BY ev_value DESC
    """, (today_str,))

    if df.empty:
        st.info("📭 今日尚無預測資料，請先執行蒙地卡羅引擎篇")
    else:
        if filter_clean:
            df = df[df['risk_tags'].apply(lambda x: 'Clean game' in str(x) if pd.notna(x) else False)]
            if df.empty:
                st.warning("🛡️ 目前無符合「乾淨盤」條件的賽事")

        # ══════════════════════════════════════
        # NO_BET_DECISION_ENGINE（四層決策）
        # ══════════════════════════════════════
        bet_df = df[df["recommended_bet"] != "SKIP"]

        # ① 高Edge場次（EV > 15%）
        high_edge_games = len(bet_df[bet_df["ev_value"] > 0.15])

        # ② 市場定價錯誤場次（沒有 Market aligned 標記 = 有套利空間）
        def has_market_aligned(tags_json):
            try:
                tags = json.loads(tags_json) if pd.notna(tags_json) else []
                return any("Market aligned" in t for t in tags)
            except:
                return False
        mispriced_games = len(bet_df[~bet_df["risk_tags"].apply(has_market_aligned)])

        # ③ 安全場次（無任何 ⚠️ 風險標記）
        def is_safe_game(tags_json):
            try:
                tags = json.loads(tags_json) if pd.notna(tags_json) else []
                return not any("⚠️" in t for t in tags)
            except:
                return False
        safe_games = len(bet_df[bet_df["risk_tags"].apply(is_safe_game)])

        # ④ 結構穩定性（sigma_used 平均）
        avg_sigma = df["sigma_used"].mean() if len(df) > 0 else 12.0

        # 最終決策
        if high_edge_games == 0:
            nb_decision, nb_color, nb_icon = "NO BET 今天直接休息", "error", "❌"
            nb_reason = f"無高 EV 場次（EV>15% 共 {high_edge_games} 場）"
        elif mispriced_games <= 1:
            nb_decision, nb_color, nb_icon = "NO BET 市場已吃掉優勢", "error", "❌"
            nb_reason = f"市場定價幾乎無誤差（有套利空間場次 {mispriced_games} 場）"
        elif safe_games <= 1:
            nb_decision, nb_color, nb_icon = "NO BET 幾乎全是地雷盤", "error", "❌"
            nb_reason = f"乾淨無風險場次僅 {safe_games} 場"
        elif avg_sigma > 13:
            nb_decision, nb_color, nb_icon = "LIMITED 小注 1–2 場即可", "warning", "⚠️"
            nb_reason = f"結構波動偏高（avg σ = {avg_sigma:.1f}），爆冷機率提升"
        elif high_edge_games >= 2 and safe_games >= 2:
            nb_decision, nb_color, nb_icon = "PLAY 今日可以下注", "success", "✅"
            nb_reason = f"高Edge {high_edge_games} 場 ✦ 安全場次 {safe_games} 場 ✦ avg σ = {avg_sigma:.1f}"
        else:
            nb_decision, nb_color, nb_icon = "LIMITED 謹慎小注", "warning", "⚠️"
            nb_reason = f"高Edge {high_edge_games} 場 ✦ 安全場次 {safe_games} 場 ✦ avg σ = {avg_sigma:.1f}"

        nb_detail = (
            f"① 高Edge場次（EV>15%）：{high_edge_games} 場　"
            f"② 有套利空間：{mispriced_games} 場　"
            f"③ 乾淨無風險：{safe_games} 場　"
            f"④ 平均 σ：{avg_sigma:.1f}"
        )
        nb_header = nb_icon + " **NO_BET DECISION ENGINE**  " + nb_decision
        if nb_color == "error":
            st.error(nb_header)
        elif nb_color == "warning":
            st.warning(nb_header)
        else:
            st.success(nb_header)
        st.caption(nb_reason)
        st.caption(nb_detail)
        st.markdown("---")

        valid = df[df["recommended_bet"] != "SKIP"]
        high  = valid[valid["confidence_level"] == "HIGH"]
        early = valid[valid["early_bet_signal"] == 1]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📋 今日場次", len(df))
        c2.metric("💰 有效下注", len(valid))
        c3.metric("🔥 HIGH信心", len(high))
        c4.metric("⚡ 早下注信號", len(early))
        st.markdown("---")


        for _, row in df.iterrows():
            conf_e    = {"HIGH":"🔥","MED":"⚡","LOW":"💧","SKIP":"⛔"}.get(row["confidence_level"],"❓")
            collapse  = " 💥崩潰" if row["collapse_flag"] else ""
            early_tag = " ⚡早注" if row["early_bet_signal"] else ""
            _ev_raw   = row["ev_value"]
            if pd.isna(_ev_raw) or _ev_raw is None:
                ev_str = "--"
            else:
                ev_str = f"{_ev_raw:+.1%}"
            kelly_str = f"{row['suggested_bet_pct']:.1%}" if row["suggested_bet_pct"] else "--"
            matchup   = f"{tn(row['away_team'])} @ {tn(row['home_team'])}"
            r_tags    = json.loads(row.get('risk_tags') or '[]') if pd.notna(row.get('risk_tags')) else []
            risk_str  = " ".join([t.split(" ")[0] for t in r_tags]) if r_tags else ""

            with st.expander(
                f"{conf_e} **{matchup}**{collapse}{early_tag}　EV {ev_str} {risk_str}",
                expanded=(row["confidence_level"] == "HIGH")
            ):
                # ── 主要指標 ──
                pred_home = row.get('ai_score_home', 0)
                pred_away = row.get('ai_score_away', 0)
                zh_home = TEAM_ZH.get(row['home_team'], row['home_team'])
                zh_away = TEAM_ZH.get(row['away_team'], row['away_team'])
                pred_winner_zh = zh_home if pred_home > pred_away else zh_away
                pred_score_str = f"{zh_away} {pred_away:.0f} : {pred_home:.0f} {zh_home}"

                col1, col2, col3 = st.columns(3)
                col1.metric("推薦下注", row["recommended_bet"])
                col2.metric("預測勝負比分", pred_score_str, delta=f"🏆 {pred_winner_zh} 勝", delta_color="off")
                col3.metric("Kelly 建議", kelly_str)

                rec_upper = str(row.get("recommended_bet", "")).upper()
                is_away_bet = row['away_team'].upper().replace(' ', '') in rec_upper.replace(' ', '') or \
                              row['away_team'].split()[-1].upper() in rec_upper
                bettor_win_prob = row.get('win_prob_away', 0) if is_away_bet else row.get('win_prob_home', 0)
                if 'ML' in rec_upper and bettor_win_prob < 0.45:
                    st.info("💡 此為賠率套利推薦（Value Bet）：模型預測對手更容易獲勝，但市場賠率錯誤低估了此隊實際勝率。推薦是因為賠率超額回報，而非從預測勝者。")

                if rec_upper == "SKIP":
                    _ev_v    = row.get("ev_value")
                    _wp      = row.get("win_prob_home")
                    _ev_nan  = pd.isna(_ev_v) or _ev_v is None
                    _mc_fail = pd.isna(_wp) or _wp is None
                    if _mc_fail:
                        st.warning("⛔ SKIP 原因：DATA ERROR — 蒙地卡羅模型未成功執行（球隊/傷兵資料缺失）")
                    elif _ev_nan:
                        st.info("⛔ SKIP 原因：NO BET — 模型正常，但無任何投注選項通過正 EV 門檻")
                    elif _ev_v <= 0:
                        st.info("⛔ SKIP 原因：NO BET — EV 為負值，不具優勢")
                    else:
                        st.info("⛔ SKIP 原因：LOW CONF — 信心不足或風險標籤過多")

                if r_tags:
                    st.markdown(f"**🛡️ 盤口風險標籤：** {', '.join(r_tags)}")

                col4, col5, col6 = st.columns(3)
                col4.metric("主隊勝率", f"{row['win_prob_home']:.1%}")
                col5.metric("EV", ev_str)
                col6.metric("σ 使用", row["sigma_used"])
                # OT Risk Score
                ot_p = row.get('ot_prob') or 0.0
                ot_score = round(ot_p * 100, 1)
                if ot_p < 0.03:
                    ot_lv = '✅ 安全盤'
                elif ot_p < 0.06:
                    ot_lv = '🟡 正常'
                else:
                    ot_lv = '⚠️ 膠著盤'
                st.markdown(f"⏱️ **OT 風險分數**：{ot_lv} `{ot_score}/100`（OT 機率 {ot_p:.1%}）")

                # ── 詳細預測數據 ──
                st.markdown("**📊 模型分析詳情**")
                d1, d2, d3 = st.columns(3)
                spread_val = row.get('ai_spread')
                total_val  = row.get('ai_total')
                pace_h     = row.get('pace_home')
                pace_a     = row.get('pace_away')
                open_line  = row.get('open_line')
                live_line  = row.get('live_line')
                total_line = row.get('total_line')

                d1.metric("預測分差",
                    f"{spread_val:+.1f}" if pd.notna(spread_val) else "--",
                    delta=f"盤口 {open_line:+.1f}" if pd.notna(open_line) else None)
                d2.metric("預測總分",
                    f"{total_val:.1f}" if pd.notna(total_val) else "--",
                    delta=f"大小 {total_line:.1f}" if pd.notna(total_line) else None)
                d3.metric("Pace",
                    f"{((pace_h or 0)+(pace_a or 0))/2:.1f}" if pd.notna(pace_h) else "--")

                # ── 傷兵詳情 ──
                try:
                    inj = json.loads(row.get("injury_snapshot") or "{}")
                    home_inj = inj.get("home", [])
                    away_inj = inj.get("away", [])
                    cp = inj.get("collapse_players", {})

                    if home_inj or away_inj:
                        st.markdown("**🏥 傷兵資料**")
                        i1, i2 = st.columns(2)
                        with i1:
                            st.markdown(f"**{tn(row['home_team'])}（主隊）**")
                            if home_inj:
                                for p in home_inj:
                                    role_e = {"superstar":"⭐⭐","allstar":"⭐","starter":"🔵","rotation":"⚪"}.get(p.get('role',''), "⚪")
                                    status_e = {"out":"❌","doubtful":"🟠","questionable":"🟡","probable":"🟢"}.get(p.get('status',''), "❓")
                                    st.markdown(f"{role_e} {status_e} {p.get('name','')}")
                            else:
                                st.markdown("✅ 無傷兵")
                        with i2:
                            st.markdown(f"**{tn(row['away_team'])}（客隊）**")
                            if away_inj:
                                for p in away_inj:
                                    role_e = {"superstar":"⭐⭐","allstar":"⭐","starter":"🔵","rotation":"⚪"}.get(p.get('role',''), "⚪")
                                    status_e = {"out":"❌","doubtful":"🟠","questionable":"🟡","probable":"🟢"}.get(p.get('status',''), "❓")
                                    st.markdown(f"{role_e} {status_e} {p.get('name','')}")
                            else:
                                st.markdown("✅ 無傷兵")
                except:
                    pass

                if row["collapse_flag"]:
                    try:
                        names = []
                        if cp.get("home"): names.append(f"{tn(row['home_team'])}：{', '.join(cp['home'])}")
                        if cp.get("away"): names.append(f"{tn(row['away_team'])}：{', '.join(cp['away'])}")
                        msg = "💥 崩潰模式 — " + "  /  ".join(names) if names else "💥 崩潰模式：核心球員缺陣 ≥ 2 名"
                    except:
                        msg = "💥 崩潰模式：核心球員缺陣 ≥ 2 名"
                    st.warning(msg)
                if row["early_bet_signal"]:
                    st.success("⚡ 早下注信號：今晚條件符合，可考慮直接下注")

# ══════════════════════════════════════
# 頁面 2：選擇日期查看
# ══════════════════════════════════════
elif page == "📅 選擇日期":
    st.title("📅 指定日期戰情")
    sel_str = sel_date.strftime("%Y-%m-%d")
    st.caption(f"查看日期（美東）：{sel_str}")
    st.markdown("---")

    df = query("""
        SELECT home_team, away_team, game_time_est,
               recommended_bet, confidence_level,
               ev_value, suggested_bet_pct,
               win_prob_home, win_prob_away,
               ai_score_home, ai_score_away,
               collapse_flag, early_bet_signal, sigma_used,
               injury_snapshot, risk_tags, ot_prob, playoff_mode
        FROM predictions
        WHERE game_date_est = ?
        GROUP BY home_team, away_team
        HAVING created_at_est = MAX(created_at_est)
        ORDER BY ev_value DESC
    """, (sel_str,))

    # 同時查該日結果
    df_res = query("""
        SELECT home_team, away_team,
               actual_score_home, actual_score_away,
               spread_result, ou_result, bet_hit, pnl
        FROM results WHERE game_date_est = ?
    """, (sel_str,))

    if df.empty:
        st.info(f"📭 {sel_str} 無預測資料")
    else:
        if filter_clean:
            df = df[df['risk_tags'].apply(lambda x: 'Clean game' in str(x) if pd.notna(x) else False)]
            if df.empty:
                st.warning("🛡️ 此日無符合「乾淨盤」條件的賽事")

        st.markdown(f"**共 {len(df)} 場比賽**")
        for _, row in df.iterrows():
            conf_e   = {"HIGH":"🔥","MED":"⚡","LOW":"💧","SKIP":"⛔"}.get(row["confidence_level"],"❓")
            _ev_raw2 = row["ev_value"]
            if pd.isna(_ev_raw2) or _ev_raw2 is None:
                ev_str = "--"
            else:
                ev_str = f"{_ev_raw2:+.1%}"
            matchup  = f"{tn(row['away_team'])} @ {tn(row['home_team'])}"
            collapse = " 💥崩潰" if row["collapse_flag"] else ""
            r_tags   = json.loads(row.get('risk_tags') or '[]') if pd.notna(row.get('risk_tags')) else []
            risk_str = " ".join([t.split(" ")[0] for t in r_tags]) if r_tags else ""
            playoff_str = " 🏆季後賽" if row.get("playoff_mode") == 1 else ""

            # 找對應結果
            res = df_res[
                (df_res["home_team"]==row["home_team"]) &
                (df_res["away_team"]==row["away_team"])
            ]
            if not res.empty:
                r = res.iloc[0]
                result_str = f"  →  **{r['actual_score_home']:.0f}:{r['actual_score_away']:.0f}**"
                hit_str = " ✅" if r["bet_hit"]==1 else " ❌" if r["bet_hit"]==0 else " ⏳"
            else:
                result_str = "  →  待定"
                hit_str = ""

            with st.expander(
                f"{conf_e} **{matchup}**{collapse}{playoff_str}　{row['recommended_bet']}  EV {ev_str}{result_str}{hit_str} {risk_str}",
            ):
                pred_home = row.get('ai_score_home', 0)
                pred_away = row.get('ai_score_away', 0)
                zh_home = TEAM_ZH.get(row['home_team'], row['home_team'])
                zh_away = TEAM_ZH.get(row['away_team'], row['away_team'])
                pred_winner_zh = zh_home if pred_home > pred_away else zh_away
                pred_score_str = f"{zh_away} {pred_away:.0f} : {pred_home:.0f} {zh_home}"

                col1, col2, col3 = st.columns(3)
                col1.metric("預測勝負比分", pred_score_str, delta=f"🏆 {pred_winner_zh} 勝", delta_color="off")
                col2.metric("EV", ev_str)
                col3.metric("Kelly", f"{row['suggested_bet_pct']:.1%}" if row["suggested_bet_pct"] else "--")

                if r_tags:
                    st.markdown(f"**🛡️ 盤口風險標籤：** {', '.join(r_tags)}")
                ot_p2 = row.get('ot_prob') or 0.0
                ot_s2 = round(ot_p2 * 100, 1)
                if ot_p2 < 0.03:
                    ot_l2 = '✅ 安全盤'
                elif ot_p2 < 0.06:
                    ot_l2 = '🟡 正常'
                else:
                    ot_l2 = '⚠️ 膠著盤'
                st.markdown(f"⏱️ **OT 風險分數**：{ot_l2} `{ot_s2}/100`（OT 機率 {ot_p2:.1%}）")
                if not res.empty:
                    r = res.iloc[0]
                    col4, col5, col6 = st.columns(3)
                    if pd.notna(r['actual_score_home']):
                        act_home = r['actual_score_home']
                        act_away = r['actual_score_away']
                        act_winner_zh = zh_home if act_home > act_away else zh_away
                        act_score_str = f"{zh_away} {act_away:.0f} : {act_home:.0f} {zh_home}"
                        col4.metric("實際比分", act_score_str, delta=f"👑 {act_winner_zh} 勝", delta_color="off")
                    else:
                        col4.metric("實際比分", "--")
                    col5.metric("讓分結果", r['spread_result'] or "--")
                    col6.metric("大小分", r['ou_result'] or "--")

# ══════════════════════════════════════
# 頁面 3：我的下注記錄
# ══════════════════════════════════════
elif page == "💰 我的下注記錄":
    st.title("💰 我的下注記錄")
    st.markdown("---")

    # 建立下注記錄資料表
    def init_bet_log():
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS my_bets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                bet_date        TEXT NOT NULL,
                game_date_est   TEXT,
                matchup         TEXT,
                bet_type        TEXT NOT NULL,
                bet_direction   TEXT,
                odds            REAL,
                stake           REAL,
                result          TEXT DEFAULT 'pending',
                payout          REAL DEFAULT 0,
                profit          REAL DEFAULT 0,
                note            TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)
        # 自動擴增串關所需欄位（舊表格若已建立則加上新欄位）
        for col, dtype in [("odds_total", "REAL"), ("is_parlay", "INTEGER"), ("is_forced", "INTEGER")]:
            try:
                conn.execute(f"ALTER TABLE my_bets ADD COLUMN {col} {dtype}")
            except sqlite3.OperationalError:
                pass

        conn.commit()
        conn.close()
    init_bet_log()

    # ── 新增下注 ──
    st.subheader("➕ 新增下注")

    # 放在 form 外面，才能即時反應
    bet_date  = st.date_input("下注日期（台灣）", value=datetime.now(TZ_TW).date())
    is_parlay = st.checkbox("🔗 過關投注（串 2 關以上）")
    is_forced = st.checkbox("⚠️ 強制過關（運彩強制串關）") if is_parlay else False
    n_legs    = int(st.number_input("幾關過關？", min_value=2, max_value=8,
                    value=2, step=1)) if is_parlay else 1

    st.markdown("---")
    legs_data  = []
    total_odds = 1.0

    for leg_i in range(n_legs):
        st.markdown(f"**第 {leg_i+1} 關**" if is_parlay else "**下注內容**")
        lc1, lc2 = st.columns(2)
        with lc1:
            game_date_l     = st.date_input("比賽日期（美東）",
                                value=datetime.now(TZ_EST).date(), key=f"gd_{leg_i}")
            game_date_str_l = str(game_date_l)
            df_games_l = query("""
                SELECT DISTINCT home_team, away_team, recommended_bet, ev_value
                FROM predictions WHERE game_date_est = ?
                GROUP BY home_team, away_team
                HAVING created_at_est = MAX(created_at_est)
                ORDER BY ev_value DESC
            """, (game_date_str_l,))
            if not df_games_l.empty:
                opts = ["（手動輸入）"] + [
                    f"{tn(r['away_team'])} @ {tn(r['home_team'])}  [{r['recommended_bet']}  EV:{r['ev_value']:+.1%}]"
                    for _, r in df_games_l.iterrows()
                ]
            else:
                opts = ["（手動輸入）"]
                st.caption(f"⚠️ {game_date_str_l} 尚無預測資料")
            sel = st.selectbox("選擇比賽", opts, key=f"sg_{leg_i}")

        with lc2:
            if sel == "（手動輸入）":
                matchup_l = st.text_input("對戰組合", key=f"mu_{leg_i}",
                    placeholder="e.g. 籃網 @ 國王")
                bet_dir_l = st.text_input("下注方向", key=f"bd_{leg_i}",
                    placeholder="e.g. 國王 -4.5 / 大 218.5")
            else:
                idx_l     = opts.index(sel) - 1
                row_gl    = df_games_l.iloc[idx_l]
                matchup_l = f"{row_gl['away_team']} @ {row_gl['home_team']}"
                st.markdown(f"🏀 **{tn(row_gl['away_team'])} @ {tn(row_gl['home_team'])}**")
                bet_dir_l = st.text_input("下注方向（可修改）",
                    value=row_gl['recommended_bet'], key=f"bd_{leg_i}")
            odds_tw_l = st.number_input("台灣運彩賠率（如 1.85）",
                min_value=1.01, value=1.72, step=0.01,
                key=f"od_{leg_i}", format="%.2f")
            total_odds *= odds_tw_l

        legs_data.append({
            'game_date': game_date_str_l,
            'matchup':   matchup_l,
            'bet_dir':   bet_dir_l,
            'odds_tw':   odds_tw_l,
        })
        if is_parlay and leg_i < n_legs - 1:
            st.markdown("---")

    st.markdown("---")
    lc1, lc2 = st.columns(2)
    with lc1:
        stake = st.number_input("投注金額（NT$）", value=100, min_value=10, step=10)
    with lc2:
        note = st.text_input("備註", placeholder="選填，如：強制過關、模型推薦")

    # 即時計算
    potential = stake * total_odds - stake
    st.info(
        f"💡 總賠率：**×{total_odds:.2f}**　｜　"
        f"若全中，獲利 **NT$ {potential:,.0f}**，含本金共 **NT$ {stake * total_odds:,.0f}**"
    )

    if st.button("💾 新增下注記錄", type="primary"):
        all_filled = all(l.get('matchup','').strip() and l.get('bet_dir','').strip() for l in legs_data)
        if all_filled:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.execute("""
                INSERT INTO my_bets (
                    bet_date, game_date_est, matchup, bet_direction, odds, 
                    bet_type, stake, odds_total, is_parlay, is_forced, note
                ) VALUES (?, '串關明細', '見關卡明細', '見明細', 1.0, ?, ?, ?, ?, ?, ?)
            """, (str(bet_date),
                  f"{'強制' if is_forced else ''}{'過關' if is_parlay else '單式'}",
                  stake, round(total_odds, 4),
                  1 if is_parlay else 0, 1 if is_forced else 0, note))
            bet_id = cur.lastrowid
            for l in legs_data:
                conn.execute("""
                    INSERT INTO my_bet_legs
                    (bet_id, game_date_est, matchup, bet_direction, odds_tw)
                    VALUES (?,?,?,?,?)
                """, (bet_id, l['game_date'], l['matchup'], l['bet_dir'], l['odds_tw']))
            conn.commit()
            conn.close()
            tag = f"過關 {n_legs} 關  " if is_parlay else ""
            st.success(f"✅ 已新增！{tag}NT$ {stake:,.0f}  ×{total_odds:.2f}  若中獲利 NT$ {potential:,.0f}")
            st.rerun()
        else:
            st.warning("⚠️ 請填寫所有關次的對戰組合和下注方向")
    st.markdown("---")

    # ── 統計 ──
    df_bets = query("""
        SELECT id, bet_date, bet_type, stake, odds_total,
               result, payout, profit, is_parlay, is_forced, note
        FROM my_bets ORDER BY bet_date DESC, created_at DESC
    """)

    if df_bets.empty:
        st.info("📭 尚無下注記錄，請先新增！")
    else:
        total_stake  = df_bets["stake"].sum()
        total_profit = df_bets["profit"].sum()
        wins    = (df_bets["result"] == "win").sum()
        loses   = (df_bets["result"] == "lose").sum()
        pending = (df_bets["result"] == "pending").sum()
        roi = total_profit / total_stake if total_stake > 0 else 0

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("💵 總投入", f"NT$ {total_stake:,.0f}")
        c2.metric("💰 總盈虧", f"NT$ {total_profit:+,.0f}")
        c3.metric("📈 ROI", f"{roi:+.1%}")
        c4.metric("✅ 戰績", f"{wins}W {loses}L")
        c5.metric("⏳ 待定", f"{pending} 張")
        st.markdown("---")

        # ── 更新結果 ──
        pending_bets = df_bets[df_bets["result"] == "pending"]
        if not pending_bets.empty:
            st.subheader("✏️ 更新下注結果")
            with st.form("update_bet"):
                bet_id = st.selectbox(
                    "選擇待更新的投注單",
                    options=pending_bets["id"].tolist(),
                    format_func=lambda x: (
                        pending_bets[pending_bets["id"]==x]["bet_date"].values[0] + "  " +
                        pending_bets[pending_bets["id"]==x]["bet_type"].values[0] + "  " +
                        f"NT$ {pending_bets[pending_bets['id']==x]['stake'].values[0]:,.0f}  " +
                        f"x{pending_bets[pending_bets['id']==x]['odds_total'].values[0]:.2f}"
                    )
                )
                row_p   = pending_bets[pending_bets["id"]==bet_id].iloc[0]
                stake_p = row_p["stake"]
                odds_p  = row_p["odds_total"]
                win_amt = stake_p * odds_p - stake_p
                legs_p  = query("SELECT matchup, bet_direction, odds_tw FROM my_bet_legs WHERE bet_id=?", (bet_id,))
                if not legs_p.empty:
                    for _, lrow in legs_p.iterrows():
                        st.markdown(f"  • {lrow['matchup']} — **{lrow['bet_direction']}**  賠率 {lrow['odds_tw']:.2f}")
                st.info(f"若全中：獲利 NT$ {win_amt:.0f}，含本金共 NT$ {stake_p * odds_p:.0f}")
                result  = st.radio("結果", ["win ✅ 全中","lose ❌ 未中","push 退水💫"], horizontal=True)
                payout  = st.number_input("實際獲得金額（NT$，含本金；輸了填 0）",
                    min_value=0.0,
                    value=float(stake_p * odds_p) if "win" in result else 0.0, step=10.0)
                if st.form_submit_button("✅ 確認更新"):
                    profit_val = payout - stake_p if "push" not in result else 0
                    result_val = "win" if "win" in result else "push" if "push" in result else "lose"
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("UPDATE my_bets SET result=?, payout=?, profit=? WHERE id=?",
                                 (result_val, payout, profit_val, bet_id))
                    conn.execute("UPDATE my_bet_legs SET leg_result=? WHERE bet_id=?",
                                 (result_val, bet_id))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ 已更新！盈虧：NT$ {profit_val:+,.0f}")
                    st.rerun()

        # ── 刪除記錄 ──
        st.subheader("🗑️ 刪除記錄")
        with st.form("delete_bet"):
            del_id = st.selectbox(
                "選擇要刪除的投注單",
                options=df_bets["id"].tolist(),
                format_func=lambda x: (
                    df_bets[df_bets["id"]==x]["bet_date"].values[0] + "  " +
                    df_bets[df_bets["id"]==x]["bet_type"].values[0] + "  " +
                    f"NT$ {df_bets[df_bets['id']==x]['stake'].values[0]:,.0f}"
                )
            )
            confirm = st.checkbox("確認刪除（此操作不可復原）")
            if st.form_submit_button("🗑️ 刪除", type="secondary"):
                if confirm:
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("DELETE FROM my_bet_legs WHERE bet_id=?", (del_id,))
                    conn.execute("DELETE FROM my_bets WHERE id=?", (del_id,))
                    conn.commit()
                    conn.close()
                    st.success("✅ 已刪除！")
                    st.rerun()
                else:
                    st.warning("⚠️ 請先勾選確認刪除")

        # ── 所有記錄 ──
        st.subheader("📋 所有投注單")
        for _, b in df_bets.iterrows():
            result_e   = {"win":"✅","lose":"❌","push":"💫","pending":"⏳"}.get(b["result"],"❓")
            parlay_tag = f" 🔗{b['bet_type']}" if b["is_parlay"] else ""
            forced_tag = " ⚠️強制" if b["is_forced"] else ""
            profit_str = f"NT$ {b['profit']:+,.0f}" if b["result"] != "pending" else "待定"
            with st.expander(
                f"{result_e} {b['bet_date']}{parlay_tag}{forced_tag}　"
                f"NT$ {b['stake']:,.0f} × {b['odds_total']:.2f}　{profit_str}"
            ):
                legs = query(
                    "SELECT matchup, bet_direction, odds_tw, leg_result FROM my_bet_legs WHERE bet_id=?",
                    (b["id"],))
                if not legs.empty:
                    for _, l in legs.iterrows():
                        lr = {"win":"✅","lose":"❌","push":"💫","pending":"⏳"}.get(l["leg_result"],"⏳")
                        st.markdown(f"{lr} {l['matchup']} — **{l['bet_direction']}**  賠率 {l['odds_tw']:.2f}")
                if b["note"]:
                    st.caption(f"備註：{b['note']}")

        csv_b = df_bets.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("⬇️ 匯出 CSV", csv_b, file_name="my_bets.csv", mime="text/csv")

# ══════════════════════════════════════
# 頁面 4：ROI 曲線
# ══════════════════════════════════════
elif page == "📈 ROI 曲線":
    st.title("📈 ROI 累積曲線")
    st.markdown("---")

    df = query("""
        SELECT date_est, daily_pnl, cumulative_pnl, hit_rate, games_bet
        FROM daily_performance
        WHERE date_est BETWEEN ? AND ?
        ORDER BY date_est
    """, (str(date_start), str(date_end)))

    if df.empty:
        st.info("📭 此範圍無績效資料，請先執行回測模組篇累積資料")
    else:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("💰 累積 PnL",   f"{df['daily_pnl'].sum():+.2%}")
        c2.metric("🎯 平均命中率", f"{df['hit_rate'].mean():.1%}" if df["hit_rate"].notna().any() else "--")
        c3.metric("📋 下注場次",   int(df["games_bet"].sum()))
        c4.metric("📅 統計天數",   len(df))
        st.markdown("---")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["date_est"], y=df["cumulative_pnl"]*100,
            mode="lines+markers", name="累積 PnL (%)",
            line=dict(color="#58a6ff", width=2),
            fill="tozeroy", fillcolor="rgba(88,166,255,0.1)"
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="#f85149", opacity=0.5)
        fig.update_layout(title="累積 PnL 曲線", xaxis_title="日期",
            yaxis_title="PnL (%)", plot_bgcolor="#161b22",
            paper_bgcolor="#0d1117", font=dict(color="#c9d1d9"))
        st.plotly_chart(fig, use_container_width=True)

        colors = ["#3fb950" if v>=0 else "#f85149" for v in df["daily_pnl"]]
        fig2 = go.Figure(go.Bar(
            x=df["date_est"], y=df["daily_pnl"]*100, marker_color=colors))
        fig2.update_layout(title="每日 PnL", xaxis_title="日期",
            yaxis_title="PnL (%)", plot_bgcolor="#161b22",
            paper_bgcolor="#0d1117", font=dict(color="#c9d1d9"))
        st.plotly_chart(fig2, use_container_width=True)

        df_v = df.dropna(subset=["hit_rate"])
        if not df_v.empty:
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=df_v["date_est"], y=df_v["hit_rate"]*100,
                mode="lines+markers", line=dict(color="#3fb950", width=2)))
            fig3.add_hline(y=52.4, line_dash="dash", line_color="#d29922",
                          annotation_text="損益平衡 52.4%")
            fig3.update_layout(title="命中率走勢", xaxis_title="日期",
                yaxis_title="命中率 (%)", yaxis=dict(range=[0,100]),
                plot_bgcolor="#161b22", paper_bgcolor="#0d1117",
                font=dict(color="#c9d1d9"))
            st.plotly_chart(fig3, use_container_width=True)

# ══════════════════════════════════════
# 頁面 4：歷史對獎
# ══════════════════════════════════════
elif page == "🏁 歷史對獎":
    st.title("🏁 歷史對獎記錄")
    st.markdown("---")

    c1,c2,c3,c4 = st.columns(4)
    with c1:
        filter_conf = st.multiselect("信心等級", ["HIGH","MED","LOW"], default=["HIGH","MED","LOW"])
    with c2:
        filter_result = st.selectbox("下注結果", ["全部","命中","未中","退水"])
    with c3:
        filter_type = st.selectbox("推薦類型", ["全部","讓分","大小分","獨贏"])
    with c4:
        filter_win_conf = st.multiselect("勝負信心", ["HIGH","MED","LOW"], default=["HIGH","MED","LOW"],
                                         help="模型對勝負方向的把握度（≥65%=HIGH，≥55%=MED）")

    df = query("""
        SELECT p.game_date_est, p.home_team, p.away_team,
               p.recommended_bet, p.confidence_level,
               p.ev_value, p.suggested_bet_pct, p.collapse_flag,
               p.ai_score_home, p.ai_score_away,
               p.win_prob_home, p.win_prob_away,
               p.live_line, p.win_pred_confidence,
               r.actual_score_home, r.actual_score_away,
               r.spread_result, r.ou_result, r.bet_hit, r.pnl
        FROM predictions p
        LEFT JOIN results r ON p.game_id = r.game_id
        WHERE p.game_date_est BETWEEN ? AND ?
        GROUP BY p.home_team, p.away_team, p.game_date_est
        HAVING p.created_at_est = MAX(p.created_at_est)
        ORDER BY p.game_date_est DESC
    """, (str(date_start), str(date_end)))

    if df.empty:
        st.info("📭 此範圍無對獎資料")
    else:
        if filter_conf:
            df = df[df["confidence_level"].isin(filter_conf)]
        if filter_result == "命中":  df = df[df["bet_hit"]==1]
        elif filter_result == "未中": df = df[df["bet_hit"]==0]
        elif filter_result == "退水": df = df[df["bet_hit"].isna()]
        if filter_type == "讓分":
            df = df[~df["recommended_bet"].str.contains("OVER|UNDER|ML", na=False)]
        elif filter_type == "大小分":
            df = df[df["recommended_bet"].str.contains("OVER|UNDER", na=False)]
        elif filter_type == "獨贏":
            df = df[df["recommended_bet"].str.contains("ML", na=False)]
        # 勝負信心篩選
        if filter_win_conf and len(filter_win_conf) < 3:
            df = df[df["win_pred_confidence"].isin(filter_win_conf) | df["win_pred_confidence"].isna()]

        def check_ml_hit(row):
            if pd.isna(row["actual_score_home"]) or pd.isna(row["actual_score_away"]):
                return None
            if row["actual_score_home"] == row["actual_score_away"]:
                return None
            return 1.0 if (row["ai_score_home"] > row["ai_score_away"]) == (row["actual_score_home"] > row["actual_score_away"]) else 0.0

        df["ml_hit"] = df.apply(check_ml_hit, axis=1)

        graded = df[df["bet_hit"].notna()]
        hits   = (graded["bet_hit"]==1).sum()
        rate   = hits/len(graded) if len(graded)>0 else 0
        pnl    = graded["pnl"].sum()
        
        ml_graded = df[df["ml_hit"].notna()]
        ml_hits = (ml_graded["ml_hit"]==1).sum()
        ml_rate = ml_hits/len(ml_graded) if len(ml_graded)>0 else 0

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("📋 總場次", len(df))
        c2.metric("✅ 推薦命中", int(hits))
        c3.metric("🎯 推薦命中率", f"{rate:.1%}" if len(graded)>0 else "--")
        c4.metric("🏆 勝負預測命中率", f"{ml_rate:.1%}" if len(ml_graded)>0 else "--")
        c5.metric("💰 總 PnL", f"{pnl:+.2%}" if len(graded)>0 else "--")
        st.markdown("---")

        disp = df.copy()
        disp["對戰"] = disp["away_team"].apply(tn) + " @ " + disp["home_team"].apply(tn)
        disp["預測比分"] = disp.apply(
            lambda r: f"{r['ai_score_away']:.0f}:{r['ai_score_home']:.0f}"
                      if pd.notna(r["ai_score_home"]) else "--", axis=1)
        disp["實際比分"] = disp.apply(
            lambda r: f"{r['actual_score_away']:.0f}:{r['actual_score_home']:.0f}"
                      if pd.notna(r["actual_score_home"]) else "待定", axis=1)
        disp["推薦命中"] = disp["bet_hit"].map({1.0:"✅",0.0:"❌"}).fillna("⏳")
        disp["勝負預測命中"] = disp["ml_hit"].map({1.0:"✅",0.0:"❌"}).fillna("⏳")
        disp["PnL"]  = disp["pnl"].apply(lambda x: f"{x:+.2%}" if pd.notna(x) else "--")
        disp["EV"]   = disp["ev_value"].apply(lambda x: f"{x:+.1%}" if pd.notna(x) else "--")

        # ✅ 讓分結果加上盤口標注（讓讀者一目了然）
        def fmt_spread_result(row):
            sr = row.get("spread_result")
            if not sr or pd.isna(sr):
                return "待定"
            ll = row.get("live_line")
            if pd.notna(ll):
                # live_line 是主隊讓分，負數=主隊讓分，正數=主隊獲讓
                direction = f"主讓 {ll:+.1f}"
                return f"{sr}（{direction}）"
            return sr
        disp["讓分結果"] = disp.apply(fmt_spread_result, axis=1)

        # ✅ 勝負信心顯示
        wpc_icon = {"HIGH":"🎯 HIGH", "MED":"⚡ MED", "LOW":"💧 LOW"}
        disp["勝負信心"] = disp["win_pred_confidence"].map(wpc_icon).fillna("--")

        st.dataframe(
            disp[["game_date_est","對戰","recommended_bet",
                  "confidence_level","勝負信心","預測比分","實際比分","讓分結果","推薦命中","勝負預測命中","PnL","EV"]]
            .rename(columns={"game_date_est":"日期","recommended_bet":"推薦",
                             "confidence_level":"信心"}),
            use_container_width=True, hide_index=True)

        csv = disp.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("⬇️ 匯出 CSV", csv,
            file_name=f"nba_{date_start}_{date_end}.csv", mime="text/csv")

# ══════════════════════════════════════
# 頁面 5：命中率日曆
# ══════════════════════════════════════
elif page == "📊 命中率日曆":
    st.title("📊 命中率日曆")
    st.markdown("---")

    df = query("""
        SELECT date_est, hit_rate, daily_pnl, games_bet,
               high_conf_hits, high_conf_total, ml_hits, ml_total
        FROM daily_performance
        WHERE date_est BETWEEN ? AND ?
        ORDER BY date_est
    """, (str(date_start), str(date_end)))

    if df.empty:
        st.info("📭 此範圍無績效資料")
    else:
        df["hit_pct"] = df["hit_rate"] * 100

        fig = go.Figure(go.Heatmap(
            x=df["date_est"], y=["命中率"],
            z=[df["hit_pct"].tolist()],
            colorscale=[[0,"#f85149"],[0.45,"#d29922"],[0.55,"#3fb950"],[1,"#1f6feb"]],
            zmin=0, zmax=100,
            text=[df["hit_pct"].apply(lambda x: f"{x:.0f}%").tolist()],
            texttemplate="%{text}",
        ))
        fig.update_layout(title="命中率熱圖", height=200,
            plot_bgcolor="#161b22", paper_bgcolor="#0d1117",
            font=dict(color="#c9d1d9"))
        st.plotly_chart(fig, use_container_width=True)

        fig2 = go.Figure(go.Scatter(
            x=df["hit_pct"], y=df["daily_pnl"]*100,
            mode="markers+text",
            text=df["date_est"].str[5:], textposition="top center",
            marker=dict(size=10, color=df["hit_pct"],
                       colorscale="RdYlGn", showscale=True)
        ))
        fig2.add_hline(y=0, line_dash="dash", line_color="#f85149", opacity=0.5)
        fig2.add_vline(x=52.4, line_dash="dash", line_color="#d29922",
                      annotation_text="52.4%損益平衡")
        fig2.update_layout(title="命中率 vs 每日 PnL",
            xaxis_title="命中率(%)", yaxis_title="PnL(%)",
            plot_bgcolor="#161b22", paper_bgcolor="#0d1117",
            font=dict(color="#c9d1d9"))
        st.plotly_chart(fig2, use_container_width=True)

        disp = df[["date_est","hit_pct","daily_pnl","games_bet",
                   "high_conf_hits","high_conf_total", "ml_hits", "ml_total"]].copy()
        disp["命中率"] = disp["hit_pct"].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "--")
        disp["PnL"]   = disp["daily_pnl"].apply(lambda x: f"{x:+.2%}" if pd.notna(x) else "--")
        disp["HIGH"]  = disp["high_conf_hits"].astype(str)+"/"+disp["high_conf_total"].astype(str)
        
        def fmt_ml(r):
            if pd.notna(r.get("ml_total")) and r["ml_total"] > 0:
                return f"{int(r['ml_hits'])}/{int(r['ml_total'])} ({r['ml_hits']/r['ml_total']:.1%})"
            return "--"
        disp["勝負預測"] = disp.apply(fmt_ml, axis=1)

        st.dataframe(
            disp[["date_est","勝負預測","命中率","PnL","games_bet","HIGH"]]
            .rename(columns={"date_est":"日期","games_bet":"下注場次", "命中率":"買牌命中", "PnL":"買牌PnL"}),
            use_container_width=True, hide_index=True)

# ══════════════════════════════════════
# 頁面 6：參數調整
# ══════════════════════════════════════
# ══════════════════════════════════════
# 頁面 X：場中截圖分析
# ══════════════════════════════════════
elif page == "📷 場中截圖分析":
    st.title("📷 視覺化場中分析 (Beta)")
    st.markdown("---")
    
    if not GEMINI_API_KEY:
        st.warning("⚠️ 尚未設定 `GEMINI_API_KEY`。請在環境變數或 Colab Secrets 中新增 `GEMINI_API_KEY` 以啟用截圖辨識功能。")
    else:
        try:
            import google.generativeai as genai
            import PIL.Image
            genai.configure(api_key=GEMINI_API_KEY)
        except ImportError:
            st.error("⚠️ 尚未安裝 Google Generative AI 套件。請執行 `pip install google-generativeai pillow`。")
            st.stop()
            
        st.info("💡 請上傳台灣運彩「場中投注」的賽事截圖。系統將自動辨識比分、時間與即時賠率，並結合賽前 AI 預估模型，即時計算場中投注的期望值 (EV)！")
        
        uploaded_files = st.file_uploader("上傳賽事截圖 (支援多張)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        
        if uploaded_files:
            col_img, col_res = st.columns([1, 1.5])
            with col_img:
                for img_file in uploaded_files:
                    st.image(img_file, caption=f"上傳截圖: {img_file.name}", use_container_width=True)
            
            with col_res:
                if st.button("🔍 開始截圖辨識並計算 EV", type="primary"):
                    with st.spinner("🧠 正在使用 Gemini Vision 解析場中數據..."):
                        try:
                            # 準備給預測模型的內容 (加入所有圖片)
                            imgs_to_process = [PIL.Image.open(f) for f in uploaded_files]
                            
                            # 自動尋找可用模型，徹底解決 404 Not Found 問題
                            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                            best_model = None
                            # 優先順序：1.5-flash -> 1.5-pro -> 其他任何包含 1.5/vision 的模型
                            for preferred in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro-vision']:
                                if preferred in available_models:
                                    best_model = preferred
                                    break
                                elif preferred.replace('models/', '') in available_models:
                                    best_model = preferred.replace('models/', '')
                                    break
                                    
                            if not best_model:
                                for m in available_models:
                                    if '1.5' in m or 'vision' in m:
                                        best_model = m
                                        break
                            if not best_model and available_models:
                                best_model = available_models[0] # 最後的備案
                                
                            model = genai.GenerativeModel(best_model)
                            prompt = """請辨識這張台灣運彩的 NBA 場中截圖。
需盡可能將比賽球隊名稱轉為「標準的 NBA 英文名」（例如 Los Angeles Lakers）。
找出目前客隊和主隊的比分、目前第幾節（quarter，1到4，OT填5）、該節剩餘時間（字串如 05:12）。
還要尋找畫面上的「不讓分」目前賠率（客隊 away_ml, 主隊 home_ml）。
尋找「讓分」盤口數字（以主隊角度：-5.5 代表主隊讓5.5分。若沒有顯示填 null）。
尋找「大小分」目前的盤口總分數字（例如：225.5，若沒有顯示填 null，鍵名為 live_total_line）。
請"只"回傳嚴格的 JSON 格式，不要包含 markdown 標籤或多餘文字：
{
  "away_team": "客隊英文名", "home_team": "主隊英文名",
  "away_score": 客隊分數(整數), "home_score": 主隊分數(整數),
  "quarter": 節次(整數), "time_remaining": "分:秒 字串",
  "away_ml": 客隊賠率(浮點數或 null), "home_ml": 主隊賠率(浮點數或 null),
  "spread_line": 主隊讓分數字(浮點數或 null),
  "live_total_line": 主客隊大小分盤口數字(浮點數或 null)
}"""
                            # 把文字提示語與所有圖片物件合併為清單送出
                            request_contents = [prompt] + imgs_to_process
                            response = model.generate_content(request_contents)
                            res_text = response.text.replace('```json', '').replace('```', '').strip()
                            data = json.loads(res_text)
                            
                            away_name = data.get('away_team', 'Unknown')
                            home_name = data.get('home_team', 'Unknown')
                            away_s = int(data.get('away_score') or 0)
                            home_s = int(data.get('home_score') or 0)
                            q = int(data.get('quarter') or 1)
                            time_rem = data.get('time_remaining', '00:00')
                            
                            st.subheader("📊 辨識結果")
                            st.write(f"**對戰組合：** {away_name} @ {home_name}")
                            c1, c2, c3 = st.columns(3)
                            c1.metric("客隊比分", away_s)
                            c2.metric("主隊比分", home_s)
                            c3.metric("時間", f"Q{q} - {time_rem}")
                            
                            c4, c5, c6 = st.columns(3)
                            c4.metric("客隊 ML 賠率", data.get('away_ml') or '-')
                            c5.metric("主隊 ML 賠率", data.get('home_ml') or '-')
                            c6.metric("大小分盤口", data.get('live_total_line') or '-')
                            
                            # ✨ 自動抓取 ESPN API 轉換命中率 ✨
                            fg_pct, three_pct = 0.47, 0.36
                            with st.spinner("⚡ 正在背景自動抓取 ESPN API 真實命中率..."):
                                try:
                                    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
                                    resp = requests.get(url, timeout=5)
                                    espn_data = resp.json()
                                    h_key = home_name.split()[-1].lower() if ' ' in home_name else home_name.lower()
                                    a_key = away_name.split()[-1].lower() if ' ' in away_name else away_name.lower()
                                    
                                    found_espn = False
                                    for event in espn_data.get('events', []):
                                        competitors = event['competitions'][0]['competitors']
                                        espn_home = next(c for c in competitors if c['homeAway'] == 'home')
                                        espn_away = next(c for c in competitors if c['homeAway'] == 'away')
                                        h_name_e = espn_home['team']['displayName'].lower()
                                        a_name_e = espn_away['team']['displayName'].lower()
                                        
                                        if h_key in h_name_e or a_key in a_name_e:
                                            h_stats = {s['name']: s['displayValue'] for s in espn_home.get('statistics', [])}
                                            a_stats = {s['name']: s['displayValue'] for s in espn_away.get('statistics', [])}
                                            h_fg = float(h_stats.get('fieldGoalPct', 47.0)) / 100.0
                                            h_3pt = float(h_stats.get('threePointFieldGoalPct', 36.0)) / 100.0
                                            a_fg = float(a_stats.get('fieldGoalPct', 47.0)) / 100.0
                                            a_3pt = float(a_stats.get('threePointFieldGoalPct', 36.0)) / 100.0
                                            fg_pct = (h_fg + a_fg) / 2.0
                                            three_pct = (h_3pt + a_3pt) / 2.0
                                            st.success(f"✅ 成功從 ESPN 抓取即時命中率！ (平均 FG%: **{fg_pct:.1%}**, 3PT%: **{three_pct:.1%}**)")
                                            found_espn = True
                                            break
                                    if not found_espn:
                                        st.warning("⚠️ ESPN 當前未提供此場景數據，使用聯盟平均命中率 47% / 36% 帶入。")
                                except Exception as e:
                                    st.warning(f"⚠️ ESPN API 抓取失敗 ({e})，使用聯盟平均帶入。")
                                    
                            c_fg, c_3pt = st.columns(2)
                            fg_pct = c_fg.number_input("平均 FG% (可手動修改)", min_value=0.0, max_value=1.0, value=fg_pct, step=0.01)
                            three_pct = c_3pt.number_input("平均 3PT% (可手動修改)", min_value=0.0, max_value=1.0, value=three_pct, step=0.01)
                            
                            # 查詢今日這兩支球隊的賽前 AI 預測
                            today_str = datetime.now(TZ_EST).strftime("%Y-%m-%d")
                            # 為了模糊匹配，只取隊名最後一個單字
                            h_key = home_name.split()[-1] if ' ' in home_name else home_name
                            a_key = away_name.split()[-1] if ' ' in away_name else away_name
                            
                            df_pred = query("""
                                SELECT win_prob_home, win_prob_away, ai_score_home, ai_score_away, recommended_bet, ev_value
                                FROM predictions 
                                WHERE game_date_est=? 
                                  AND home_team LIKE ? AND away_team LIKE ?
                                ORDER BY created_at_est DESC LIMIT 1
                            """, (today_str, f"%{h_key}%", f"%{a_key}%"))
                            
                            if df_pred.empty:
                                st.warning(f"⚠️ 找不到今日 {away_name} @ {home_name} 的賽前預測記錄，無法計算場中 EV。")
                            else:
                                pre = df_pred.iloc[0]
                                st.markdown("---")
                                
                                # ── 時間換算與推估邏輯 ──
                                try:
                                    m, s = map(int, time_rem.split(':'))
                                    if q <= 4:
                                        time_elapsed = (q - 1) * 12 + (12 - m - s/60.0)
                                        total_time = 48.0
                                    else:
                                        time_elapsed = 48 + (q - 5) * 5 + (5 - m - s/60.0)
                                        total_time = 48.0 + (q - 4) * 5
                                    time_pct = min(time_elapsed / total_time, 1.0)
                                except:
                                    time_elapsed = 24.0
                                    time_pct = 0.5
                                    total_time = 48.0

                                if time_elapsed < 1.0: time_elapsed = 1.0
                                rem_pct = max(1.0 - time_pct, 0.01)

                                # 純按節奏推估 (Pace-based)
                                pace_proj_home = (home_s / time_elapsed) * total_time
                                pace_proj_away = (away_s / time_elapsed) * total_time
                                
                                # 模型預估剩下時間得分
                                model_proj_home = home_s + pre['ai_score_home'] * rem_pct
                                model_proj_away = away_s + pre['ai_score_away'] * rem_pct

                                # 時間打越久，純節奏推估的權重越高
                                live_proj_home = pace_proj_home * (time_pct**2) + model_proj_home * (1 - time_pct**2)
                                live_proj_away = pace_proj_away * (time_pct**2) + model_proj_away * (1 - time_pct**2)

                                # 動態勝率推估 (假設勝負常態分佈)
                                import math
                                from scipy.stats import norm
                                
                                diff = home_s - away_s
                                # 賽前預估的分差 (主視角)
                                expected_rem_diff = (pre['ai_score_home'] - pre['ai_score_away']) * rem_pct
                                rem_sigma = 13.0 * math.sqrt(rem_pct)
                                if rem_sigma < 0.5: rem_sigma = 0.5
                                
                                live_win_home = float(1 - norm.cdf(-diff, loc=expected_rem_diff, scale=rem_sigma))
                                live_win_away = 1.0 - live_win_home

                                # 🔥 FAKE OVER / UNDER 偵測邏輯 🔥
                                live_line = float(data.get('live_total_line') or pre['ai_total']) # 若畫面無盤口，預設帶入賽前預測盤
                                pace_diff = (live_proj_home + live_proj_away) - live_line
                                
                                hot = fg_pct > 0.52 or three_pct > 0.40
                                cold = fg_pct < 0.42
                                pace_fast = (live_proj_home + live_proj_away) > (live_line + 8)
                                
                                signal = "NO BET"
                                if pace_diff > 12 and hot:
                                    signal = "FAKE_OVER"
                                elif pace_fast and cold:
                                    signal = "FAKE_UNDER"
                                
                                regression_score = (fg_pct - 0.47) + (three_pct - 0.36)
                                confidence_adj = 1.0
                                if time_pct < 0.25:
                                    confidence_adj = 0.6
                                elif time_pct < 0.50:
                                    confidence_adj = 0.8
                                    
                                st.markdown("---")
                                st.subheader("🎯 場中假大小分 (Fake O/U) 狙擊系統")
                                c_s1, c_s2, c_s3 = st.columns(3)
                                c_s1.metric("全場推估總分", f"{live_proj_home + live_proj_away:.1f}")
                                c_s2.metric("即時大小盤", f"{live_line:.1f}")
                                c_s3.metric("Pace 偏差", f"{pace_diff:+.1f}")
                                
                                ou_alert = ""
                                if signal == "FAKE_OVER":
                                    ext_warning = " (超級強烈信號)" if regression_score > 0.08 else ""
                                    st.error(f"🚨 **【假大分信號 (Fake Over)】觸發！** {ext_warning}\\n目前的超高比分是**異常命中率發燒**加上過快節奏所疊加的虛假現象！\\n\\n👉 **強力建議反打：全場【小分】 (UNDER)** (防第一節雷區信心倍率: {confidence_adj}x)")
                                    ou_alert = f"\\n🚨 【假大分信號】建議打小 (UNDER) (信心: {confidence_adj}x)\\n👉 推估得分大幅拉爆盤口，且命中率過熱，回歸機率極高！"
                                elif signal == "FAKE_UNDER":
                                    st.success(f"🧊 **【假小分信號 (Fake Under)】觸發！**\\n比賽節奏其實非常快，但目前全體打鐵陷入得分荒！\\n\\n👉 **強力建議反打：全場【大分】 (OVER)** (防第一節雷區信心倍率: {confidence_adj}x)")
                                    ou_alert = f"\\n🧊 【假小分信號】建議打大 (OVER) (信心: {confidence_adj}x)\\n👉 節奏極快但全體打鐵，一旦回歸正常命中率將突破大分！"
                                else:
                                    st.info("💡 目前沒有明顯的大小分異常信號 (得分與命中率符合預期)。")
                                
                                st.markdown("---")
                                st.subheader("⚡ 場中勝負 EV 分析")
                                
                                st.write(f"⏱️ 比賽已進行 **{time_pct:.1%}**。結合模型推算，最終預測比分：**{live_proj_away:.1f}** @ **{live_proj_home:.1f}**")
                                
                                live_odds_home = float(data.get('home_ml') or 0.0)
                                live_odds_away = float(data.get('away_ml') or 0.0)
                                
                                alert_msg = None
                                
                                c_h, c_a = st.columns(2)
                                with c_h:
                                    st.write(f"🏠 **主隊 ({home_name})**")
                                    st.write(f"即時勝率估計：{live_win_home:.1%}")
                                    ev_h = min((live_win_home * live_odds_home) - 1 if live_odds_home > 0 else 0, 0.40)  # 場中 EV 上限 40%
                                    st.write(f"即時賠率：**{live_odds_home}**")
                                    if ev_h > 0:
                                        st.success(f"📈 預期 EV：**+{ev_h:.1%}**")
                                    else:
                                        st.error(f"📉 預期 EV：**{ev_h:.1%}**")
                                        
                                    if ev_h > 0.10 or (signal != "NO BET" and confidence_adj > 0.7):
                                        if ev_h > 0.10: st.error(f"🎯 **建議下注：主隊不讓分**")
                                        alert_msg = f"🔥 【場中重注警示】\\n🏀 {away_name} @ {home_name}\\n" \
                                                    f"📊 目前比分：{away_s} - {home_s} (Q{q} {time_rem})\\n" \
                                                    f"💡 主隊 ML 建議 @ {live_odds_home} (EV: +{ev_h:.1%})\\n" \
                                                    f"{ou_alert}"
                                
                                with c_a:
                                    st.write(f"✈️ **客隊 ({away_name})**")
                                    st.write(f"即時勝率估計：{live_win_away:.1%}")
                                    ev_a = min((live_win_away * live_odds_away) - 1 if live_odds_away > 0 else 0, 0.40)  # 場中 EV 上限 40%
                                    st.write(f"即時賠率：**{live_odds_away}**")
                                    if ev_a > 0:
                                        st.success(f"📈 預期 EV：**+{ev_a:.1%}**")
                                    else:
                                        st.error(f"📉 預期 EV：**{ev_a:.1%}**")
                                        
                                    if ev_a > 0.10 or (signal != "NO BET" and confidence_adj > 0.7 and alert_msg is None):
                                        if ev_a > 0.10: st.error(f"🎯 **建議下注：客隊不讓分**")
                                        alert_msg = f"🔥 【場中重注警示】\\n🏀 {away_name} @ {home_name}\\n" \
                                                    f"📊 目前比分：{away_s} - {home_s} (Q{q} {time_rem})\\n" \
                                                    f"💡 客隊 ML 建議 @ {live_odds_away} (EV: +{ev_a:.1%})\\n" \
                                                    f"{ou_alert}"
                                
                                # 🏆 黃金入注時窗偵測
                                is_golden_window = 0.15 <= time_pct <= 0.30
                                best_ev = max(ev_h, ev_a)
                                best_side = "主隊" if ev_h >= ev_a else "客隊"
                                best_odds = live_odds_home if ev_h >= ev_a else live_odds_away
                                
                                if is_golden_window and best_ev >= 0.15:
                                    golden_lines = [
                                        "🌟⚛️ 【黃金入注時窗口】觸發！",
                                        f"🏀 {away_name} @ {home_name}",
                                        f"⏱️ 已進行 {time_pct:.1%}（Q{q} {time_rem}）",
                                        f"📊 目前比分：{away_s} - {home_s}",
                                        f"💡 建議立刻下注：『{best_side}』 賠率 {best_odds} (EV: +{best_ev:.1%})",
                                        "⚠️ 盤口可能在半場前鎖定，請立即行動！",
                                    ]
                                    st.warning(f"🌟 **黃金入注時窗口！**（比賽進行中 {time_pct:.1%}）建議立刻指定{best_side}！盤口可能將封")
                                    if tg_send(golden_lines):
                                        st.info("📲 黃金時窗強力 Telegram 已發送！")

                                if alert_msg:
                                    st.warning("傳送 Telegram 推播中...")
                                    if tg_send(alert_msg):
                                        st.success("📱 Telegram 警示已發送！")
                                    
                        except Exception as e:
                            st.error(f"辨識或計算失敗：{e}")
                            st.write(traceback.format_exc())

elif page == "🔬 參數調整":
    st.title("🔬 參數調整與回測")
    st.markdown("---")

    st.subheader("⚙️ 目前參數")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("σ 正常", sigma_n)
    c2.metric("σ 崩潰", sigma_c)
    c3.metric("盤口錨定", f"{mkt_w:.0%}")
    c4.metric("EV 門檻",  f"{ev_thresh:.0%}")
    st.markdown("---")

    st.subheader("📊 回測記錄")
    df_bt = query("""
        SELECT run_name, date_range_start, date_range_end,
               total_games, overall_hit_rate, roi, params_json, run_at_est
        FROM backtest_runs ORDER BY run_at_est DESC LIMIT 50
    """)

    if df_bt.empty:
        st.info("📭 尚無回測記錄")
    else:
        df_bt["params"] = df_bt["params_json"].apply(lambda x: json.loads(x) if x else {})
        df_bt["σ"]   = df_bt["params"].apply(lambda x: f"{x.get('sigma_normal','?')}/{x.get('sigma_collapse','?')}")
        df_bt["MW"]  = df_bt["params"].apply(lambda x: x.get("market_weight","?"))
        df_bt["命中率"] = df_bt["overall_hit_rate"].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "--")
        df_bt["ROI"] = df_bt["roi"].apply(lambda x: f"{x:+.2%}" if pd.notna(x) else "--")
        st.dataframe(
            df_bt[["run_at_est","σ","MW","total_games","命中率","ROI"]]
            .rename(columns={"run_at_est":"時間","total_games":"場次","MW":"盤口權重"}),
            use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("⚠️ 參數警示")
    df_al = query("""
        SELECT alert_time_est, alert_type, description,
               suggested_action, is_resolved
        FROM param_alerts ORDER BY alert_time_est DESC LIMIT 20
    """)
    if df_al.empty:
        st.success("✅ 無未解決警示，模型運作正常")
    else:
        for _, row in df_al.iterrows():
            icon = "✅" if row["is_resolved"]==1 else "⚠️"
            with st.expander(f"{icon} {row['description'][:60]}..."):
                st.write(f"**建議：** {row['suggested_action']}")

st.markdown("---")
_mode_str = "🧪 測試模式（DEV DB）" if IS_DEV else "🏆 正式模式"
st.caption(f"🏀 NBA 戰情系統 V34.1　｜　{_mode_str}　｜　僅供參考，投注請自負風險")

'''

with open('/content/streamlit_app.py', 'w') as f:
    f.write(APP_CODE)
print("✅ streamlit_app.py 寫入完成")

# ── Step 3：啟動 Streamlit ──
import threading, time

def run_streamlit():
    os.system(
        'streamlit run /content/streamlit_app.py '
        '--server.port 8501 '
        '--server.headless true '
        '--server.enableCORS false '
        '--server.enableXsrfProtection false '
        '> /content/streamlit.log 2>&1'
    )

import json as _json
_cfg = {'IS_DEV': bool(DEV_MODE), 'DB_PATH': str(DB_PATH)}
try:
    from google.colab import userdata
    _cfg['GEMINI_API_KEY'] = userdata.get('GEMINI_API_KEY')
    _cfg['TELEGRAM_TOKEN'] = userdata.get('TELEGRAM_TOKEN')
    _cfg['TELEGRAM_CHAT_ID'] = userdata.get('TELEGRAM_CHAT_ID')
except Exception:
    pass

with open('/content/streamlit_config.json', 'w') as _f:
    _json.dump(_cfg, _f)
print(f"   Streamlit 模式：{'🧪 測試' if DEV_MODE else '🏆 正式'} | DB：{DB_PATH}")

t = threading.Thread(target=run_streamlit, daemon=True)
t.start()
time.sleep(5)
print("✅ Streamlit 啟動中...")

# ── Step 4：Colab 內建網址（不需要 ngrok）──
from google.colab.output import eval_js
try:
    url = eval_js("google.colab.kernel.proxyPort(8501)")
    print(f"\n{'='*50}")
    print(f"🌐 網頁介面已開啟！")
    print(f"👉 點擊連結：{url}")
    print(f"{'='*50}")
except Exception as e:
    print(f"❌ 無法取得網址：{e}")
    print("   請點擊 Colab 右上角 → 埠口(Ports) → 8501")

# ── 確認啟動狀態 ──
time.sleep(2)
if os.path.exists('/content/streamlit.log'):
    log = open('/content/streamlit.log').read()
    if 'Error' in log:
        print(f"\n❌ 啟動 log：\n{log[:400]}")
    else:
        print("✅ Streamlit 運作正常")
