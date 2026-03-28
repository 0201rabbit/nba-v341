# CELL 19-前置：確認地基篇變數已載入
# 請先執行：地基篇 v2 -> 蒙地卡羅引擎篇 v4，再執行此篇
required_vars = ["DEV_MODE","DB_PATH","TELEGRAM_TOKEN","TELEGRAM_CHAT_ID",
                 "now_est","shield","detect_line_moves","analyze_game",
                 "evaluate_early_bet","save_prediction","get_hit_rate"]
missing = [v for v in required_vars if v not in dir()]
if missing:
    raise RuntimeError("請先執行地基篇 v2 + 蒙地卡羅引擎篇 v4，缺少：" + str(missing))
print("✅ 前置變數確認完成")

# 中文隊名（從引擎篇繼承，這裡備份一份）
if 'TEAM_ZH' not in dir():
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
if 'tn' not in dir():
    def tn(name):
        zh = TEAM_ZH.get(name, '')
        return f"{name}（{zh}）" if zh else name



# CELL 19：Telegram 工具函數
# ─────────────────────────────────────────────

import requests
import json
from datetime import datetime
from zoneinfo import ZoneInfo

def tg_send(text: str, parse_mode: str = 'HTML') -> bool:
    """
    發送 Telegram 訊息
    DEV_MODE=True 時只印出，不真正發送
    """
    if DEV_MODE:
        print(f"\n{'─'*50}")
        print(f"📱 [DEV_MODE] Telegram 預覽（不真正發送）：")
        print(f"{'─'*50}")
        print(text)
        print(f"{'─'*50}")
        return True

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        else:
            print(f"❌ Telegram 發送失敗：{resp.status_code} — {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Telegram 網路錯誤：{e}")
        return False


def tg_test_connection() -> bool:
    """測試 Telegram Bot 連線"""
    if DEV_MODE:
        print("🔒 DEV_MODE：跳過 Telegram 連線測試")
        return True
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            bot_name = resp.json()['result']['username']
            print(f"✅ Telegram Bot 連線成功：@{bot_name}")
            return True
        else:
            print(f"❌ Telegram 連線失敗：{resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Telegram 連線錯誤：{e}")
        return False

tg_test_connection()
print("✅ Telegram 模組就緒")


# ─────────────────────────────────────────────
# CELL 20：訊息格式化模組
# ─────────────────────────────────────────────

def confidence_emoji(level: str) -> str:
    return {'HIGH': '🔥', 'MED': '⚡', 'LOW': '💧', 'SKIP': '⛔'}.get(level, '❓')

def format_bet_row(rank: int, pred: dict) -> str:
    """格式化單場投注列"""
    conf_e   = confidence_emoji(pred.get('confidence_level', 'LOW'))
    matchup  = f"{tn(pred['away_team'])} @ {tn(pred['home_team'])}"
    rec      = pred.get('recommended_bet', 'SKIP')
    ev       = pred.get('ev_value', 0)
    kelly    = pred.get('suggested_bet_pct', 0)
    ev_str   = f"{ev:+.1%}" if ev else '--'
    kelly_str= f"{kelly:.1%}" if kelly else '--'
    collapse = ' 💥崩潰' if pred.get('collapse_flag') else ''
    early    = ' ⚡早注' if pred.get('early_bet_signal') else ''

    return (
        f"{rank}. {conf_e} <b>{matchup}</b>{collapse}{early}\n"
        f"   推薦：{rec}\n"
        f"   EV：{ev_str}  Kelly：{kelly_str}"
    )

def format_morning_broadcast(predictions: list, game_date_est: str) -> str:
    """
    格式化早上 06:00 主推播訊息
    predictions: 已排序的預測清單（EV 由高到低）
    """
    tw_time = datetime.now(ZoneInfo('Asia/Taipei')).strftime('%m/%d %H:%M')
    est_time = datetime.now(ZoneInfo('America/New_York')).strftime('%m/%d %H:%M')

    lines = [
        f"🏀 <b>NBA 戰情系統 V34.1</b>",
        f"📅 {game_date_est}  |  台灣 {tw_time}  /  美東 {est_time}",
        f"{'─'*30}",
    ]

    # 過濾有效下注（非 SKIP），同一 game_id 只取 EV 最高的一筆
    seen = {}
    for p in sorted(predictions, key=lambda x: x.get('ev_value', 0) or 0, reverse=True):
        if p.get('recommended_bet', 'SKIP') != 'SKIP' and (p.get('ev_value', 0) or 0) > 0:
            key = p['home_team'] + '|' + p['away_team']  # 用球隊名稱去重，避免不同game_id同場比賽重複
            if key not in seen:
                seen[key] = p
    valid = list(seen.values())

    if not valid:
        lines.append("⛔ 今日無符合條件的下注機會")
    else:
        lines.append(f"🔥 <b>今日 TOP {min(len(valid), 5)} 推薦</b>")
        lines.append("")
        for i, pred in enumerate(valid[:5], start=1):
            lines.append(format_bet_row(i, pred))
            lines.append("")

    # 早下注信號提醒
    early_bets = [p for p in valid if p.get('early_bet_signal') == 1]
    if early_bets:
        lines.append(f"{'─'*30}")
        lines.append(f"⚡ <b>早下注信號（今晚可直接下注）</b>")
        for p in early_bets[:3]:
            lines.append(f"  • {p['away_team']} @ {p['home_team']}  →  {p.get('recommended_bet')}")

    lines.append(f"{'─'*30}")
    lines.append(f"⚠️ 僅供參考，風險自負")

    return "\n".join(lines)


def format_line_move_alert(alerts: list, game_date_est: str) -> str:
    """格式化盤口異動提醒訊息"""
    if not alerts:
        return None

    lines = [
        f"📊 <b>盤口異動警示</b> — {game_date_est}",
        f"{'─'*30}",
    ]
    for a in alerts:
        # 讓分絕對值變大代表主隊更被看好 → ▲
        eve_abs  = abs(a['spread_eve']  or 0)
        morn_abs = abs(a['spread_morn'] or 0)
        spread_dir = "▲" if morn_abs > eve_abs else "▼"
        lines.append(
            f"⚠️ <b>{a['matchup']}</b>\n"
            f"   讓分：{a['spread_eve']} → {a['spread_morn']} {spread_dir}  "
            f"（移動 {a['spread_move']:.1f} 分）\n"
            f"   大小：{a['total_eve']} → {a['total_morn']}"
        )
        lines.append("")

    lines.append("👉 盤口大幅移動，建議重新評估是否下注")
    return "\n".join(lines)


def format_parlay_suggestion(predictions: list) -> str:
    """
    生成 2-3 關串關建議
    條件：選 EV 最高的 2-3 場，信心等級 HIGH，無崩潰
    """
    # 篩選串關候選（HIGH 信心、無崩潰、有正 EV）
    candidates = [
        p for p in predictions
        if p.get('confidence_level') == 'HIGH'
        and not p.get('collapse_flag')
        and p.get('ev_value', 0) >= 0.08
        and p.get('recommended_bet', 'SKIP') != 'SKIP'
    ]

    # ✅ 去重：同一 game_id 只取 EV 最高的一筆，避免同場比賽串關
    seen_games = {}
    for p in sorted(candidates, key=lambda x: x.get('ev_value', 0), reverse=True):
        key = p['home_team'] + '|' + p['away_team']
        if key not in seen_games:
            seen_games[key] = p
    candidates = list(seen_games.values())

    if len(candidates) < 2:
        return None

    # 取最高 EV 的 2-3 場（不同比賽）
    candidates = sorted(candidates, key=lambda x: x.get('ev_value', 0), reverse=True)
    two_leg  = candidates[:2]
    three_leg= candidates[:3] if len(candidates) >= 3 else None

    def calc_parlay_odds(legs: list) -> float:
        """計算串關小數賠率"""
        result = 1.0
        for p in legs:
            # 讓分串關假設賠率 -110
            result *= (100/110 + 1)
        return round(result, 2)

    def calc_parlay_prob(legs: list) -> float:
        """計算串關理論勝率（各場勝率相乘）"""
        prob = 1.0
        for p in legs:
            prob *= p.get('win_prob_home', 0.5)
        return round(prob, 4)

    lines = [
        f"🎯 <b>串關建議</b>",
        f"{'─'*30}",
    ]

    # 2 關串關
    odds_2 = calc_parlay_odds(two_leg)
    prob_2 = calc_parlay_prob(two_leg)
    lines.append(f"<b>2 關串關</b>  賠率約 {odds_2:.2f}×  勝率 {prob_2:.1%}")
    for p in two_leg:
        lines.append(f"  ✓ {p['away_team']} @ {p['home_team']}  →  {p.get('recommended_bet')}")
    lines.append("")

    # 3 關串關
    if three_leg:
        odds_3 = calc_parlay_odds(three_leg)
        prob_3 = calc_parlay_prob(three_leg)
        lines.append(f"<b>3 關串關</b>  賠率約 {odds_3:.2f}×  勝率 {prob_3:.1%}")
        for p in three_leg:
            lines.append(f"  ✓ {p['away_team']} @ {p['home_team']}  →  {p.get('recommended_bet')}")
        lines.append("")

    lines.append("⚠️ 串關風險較高，建議小額試水")
    return "\n".join(lines)


def format_early_bet_alert(pred: dict, signal: dict) -> str:
    """格式化晚上「早下注」提醒訊息"""
    matchup = f"{tn(pred['away_team'])} @ {tn(pred['home_team'])}"
    rec     = pred.get('recommended_bet', 'SKIP')
    ev      = pred.get('ev_value', 0)
    kelly   = pred.get('suggested_bet_pct', 0)

    lines = [
        f"⚡ <b>早下注信號</b>",
        f"{'─'*30}",
        f"🏀 {matchup}",
        f"推薦：<b>{rec}</b>",
        f"EV：{ev:+.1%}  Kelly：{kelly:.1%}",
        f"{'─'*30}",
    ]
    lines.append("✅ 符合早下注條件：")
    for r in signal.get('go', []):
        lines.append(f"  ✓ {r}")
    if signal.get('wait'):
        lines.append("⚠️ 注意事項：")
        for r in signal.get('wait', []):
            lines.append(f"  • {r}")

    lines.append(f"{'─'*30}")
    lines.append("⚠️ 仍建議明早確認傷兵報告後再行動")
    return "\n".join(lines)


print("✅ 訊息格式化模組就緒")


# ─────────────────────────────────────────────
# CELL 21：從 DB 讀取今日預測清單
# ─────────────────────────────────────────────

def get_todays_predictions(game_date_est: str = None) -> list:
    """
    從 DB 讀取指定日期的預測，回傳 list of dict
    每場只取最新一筆（避免重複分析產生重複記錄）
    """
    game_date_est = game_date_est or now_est().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_PATH)

    rows = conn.execute('''
        SELECT
            game_id, game_date_est, game_time_est,
            home_team, away_team,
            open_line, live_line, total_line,
            home_odds, away_odds,
            ai_score_home, ai_score_away,
            ai_spread, ai_total,
            win_prob_home, win_prob_away,
            ev_value, recommended_bet, confidence_level,
            kelly_fraction, suggested_bet_pct,
            early_bet_signal,
            sigma_used, collapse_flag, collapse_team,
            trigger_session, created_at_est
        FROM predictions
        WHERE game_date_est = ?
        GROUP BY game_id
        HAVING created_at_est = MAX(created_at_est)
        ORDER BY ev_value DESC NULLS LAST
    ''', (game_date_est,)).fetchall()
    conn.close()

    cols = [
        'game_id', 'game_date_est', 'game_time_est',
        'home_team', 'away_team',
        'open_line', 'live_line', 'total_line',
        'home_odds', 'away_odds',
        'ai_score_home', 'ai_score_away',
        'ai_spread', 'ai_total',
        'win_prob_home', 'win_prob_away',
        'ev_value', 'recommended_bet', 'confidence_level',
        'kelly_fraction', 'suggested_bet_pct',
        'early_bet_signal',
        'sigma_used', 'collapse_flag', 'collapse_team',
        'trigger_session', 'created_at_est'
    ]
    return [dict(zip(cols, r)) for r in rows]


print("✅ DB 讀取模組就緒")


# ─────────────────────────────────────────────
# CELL 22：主推播流程（早上 06:00 EST）
# ─────────────────────────────────────────────

def run_morning_broadcast(game_date_est: str = None):
    """
    早上推播主流程：
    1. 讀取今日預測
    2. 偵測盤口異動
    3. 發送主清單
    4. 發送串關建議
    """
    game_date_est = game_date_est or now_est().strftime('%Y-%m-%d')
    print(f"\n{'='*50}")
    print(f"📡 啟動早上推播 — {game_date_est}")
    print(f"{'='*50}")

    # 1. 讀取今日預測
    predictions = get_todays_predictions(game_date_est)
    print(f"📋 今日預測：{len(predictions)} 場")

    if not predictions:
        tg_send(f"🏀 NBA V34.1\n{game_date_est}\n\n今日無預測資料，請確認系統是否正常執行。")
        return

    # 2. 偵測盤口異動
    alerts = detect_line_moves(game_date_est)
    if alerts:
        alert_msg = format_line_move_alert(alerts, game_date_est)
        if alert_msg:
            tg_send(alert_msg)
            print(f"⚠️  發送盤口異動警示：{len(alerts)} 場")

    # 3. 主推播
    main_msg = format_morning_broadcast(predictions, game_date_est)
    tg_send(main_msg)
    print("✅ 主推播訊息已發送")

    # 4. 串關建議
    parlay_msg = format_parlay_suggestion(predictions)
    if parlay_msg:
        tg_send(parlay_msg)
        print("✅ 串關建議已發送")
    else:
        print("ℹ️  符合串關條件的場次不足，跳過串關建議")

    print(f"{'='*50}")
    print(f"✅ 早上推播完成")


def run_evening_check(game_date_est: str = None):
    """
    晚上檢查流程：
    1. 抓取 evening 盤口快照
    2. 對每場比賽執行分析
    3. 如有早下注信號，立即推播
    """
    game_date_est = game_date_est or now_est().strftime('%Y-%m-%d')
    print(f"\n{'='*50}")
    print(f"🌙 啟動晚上檢查 — {game_date_est}")
    print(f"{'='*50}")

    # 抓取盤口
    odds_list = shield.fetch_odds(game_date_est, trigger='evening_check')
    print(f"📊 取得盤口：{len(odds_list)} 場")

    early_signals = []
    for odds in odds_list:
        # 這裡假設傷兵資料已手動輸入或由其他模組提供
        # 實際使用時請在 analyze_game 的 home_injuries / away_injuries 填入當天傷兵
        result = analyze_game(
            game_id       = odds['game_id'],
            home_team     = odds['home_team'],
            away_team     = odds['away_team'],
            spread_line   = odds['spread_line'] or 0,
            total_line    = odds['total_line'] or 220,
            home_ml       = odds.get('home_ml'),
            away_ml       = odds.get('away_ml'),
            game_date_est = game_date_est,
            trigger_session='evening',
            save_to_db    = True,
        )
        if result['early_signal']['early_bet_signal']:
            early_signals.append((result, odds))

    # 推播早下注信號
    for result, odds in early_signals:
        pred = {
            'away_team': odds['away_team'],
            'home_team': odds['home_team'],
            'recommended_bet': result['bet_eval']['best_bet']['description'] if result['bet_eval']['best_bet'] else 'SKIP',
            'ev_value': result['bet_eval']['best_bet']['ev'] if result['bet_eval']['best_bet'] else 0,
            'suggested_bet_pct': result['bet_eval']['best_bet']['kelly'] if result['bet_eval']['best_bet'] else 0,
        }
        alert = format_early_bet_alert(pred, result['early_signal'])
        tg_send(alert)
        print(f"⚡ 早下注信號推播：{odds['away_team']} @ {odds['home_team']}")

    print(f"{'='*50}")
    print(f"✅ 晚上檢查完成，早下注信號：{len(early_signals)} 場")


print("✅ 推播流程就緒")


# ─────────────────────────────────────────────
# CELL 23：DEV 測試 — 完整推播預覽
# ─────────────────────────────────────────────

if DEV_MODE:
    today_est = now_est().strftime('%Y-%m-%d')
    print("\n🧪 DEV 測試：完整推播預覽\n")

    # 讀取 DB 中的預測（由蒙地卡羅篇存入的測試資料）
    predictions = get_todays_predictions(today_est)
    print(f"✅ 讀取到 {len(predictions)} 筆預測")

    if predictions:
        # 預覽主推播
        main_msg = format_morning_broadcast(predictions, today_est)
        tg_send(main_msg)

        # 預覽盤口異動
        alerts = detect_line_moves(today_est)
        if alerts:
            alert_msg = format_line_move_alert(alerts, today_est)
            tg_send(alert_msg)
        else:
            print("ℹ️  無盤口異動（需 evening + morning 兩筆快照才能比對）")

        # 預覽串關
        parlay_msg = format_parlay_suggestion(predictions)
        if parlay_msg:
            tg_send(parlay_msg)
        else:
            print("ℹ️  無符合串關條件的場次")

        # 預覽早下注信號（取第一筆有信號的）
        early_preds = [p for p in predictions if p.get('early_bet_signal') == 1]
        if early_preds:
            p = early_preds[0]
            signal = {
                'early_bet_signal': True,
                'go': ['EV 達標', '盤口穩定', '無崩潰', '信心 HIGH'],
                'wait': []
            }
            early_msg = format_early_bet_alert(p, signal)
            tg_send(early_msg)

    else:
        print("ℹ️  DB 中無預測資料，請先執行蒙地卡羅引擎篇 DEV 測試")

    print("\n🎉 Telegram 推播篇測試完成！")
    print("   DEV_MODE=False 後，訊息將真正發送到你的 Telegram")
    print("\n   下一步：回測模組篇（參數微調 + 命中率分析）")
