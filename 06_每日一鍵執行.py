# =============================================================
# 🏀 NBA V34.1 — 每日一鍵執行 Cell
# =============================================================
# 📅 使用時機：
#   【晚上】台灣時間每天下午 5點 ~ 晚上 10點
#           → 執行「今日分析」區塊
#   【早上】台灣時間隔天早上 8點 ~ 10點（比賽結束後）
#           → 執行「對獎結算」區塊
#
# ⚠️ 前置條件：地基篇 v3 + 引擎篇 v4 + Telegram篇 已執行完畢
# =============================================================

import json
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# ⚙️ 今天要分析的日期（通常不用改，自動抓美東今天）
# 如果要分析明天的比賽，改成：
# TARGET_DATE = (now_est() + timedelta(days=1)).strftime('%Y-%m-%d')
# ─────────────────────────────────────────────
TARGET_DATE = now_est().strftime('%Y-%m-%d')

print(f"{'='*55}")
print(f"🏀 NBA V34.1 每日一鍵執行")
print(f"{'='*55}")
print(f"📅 目標日期（美東）：{TARGET_DATE}")
print(f"⏰ 台灣時間：{now_tw().strftime('%Y-%m-%d %H:%M')}")
print(f"⏰ 美東時間：{now_est().strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*55}")


# ══════════════════════════════════════════════
# 【區塊 A】今日分析
# 台灣時間下午~晚上執行
# ══════════════════════════════════════════════
def run_today_analysis(target_date: str = TARGET_DATE):
    print(f"\n{'─'*55}")
    print(f"📡 區塊 A：今日分析 — {target_date}")
    print(f"{'─'*55}")

    # Step 1：抓取今日盤口
    print(f"\n📊 Step 1：抓取盤口...")
    odds_list = shield.fetch_odds(target_date, trigger='evening_check')

    if not odds_list:
        print("❌ 未取得任何盤口資料，請確認：")
        print("   1. DEV_MODE = False")
        print("   2. ODDS_API_KEY 正確設定")
        print("   3. 今日 NBA 有比賽（休賽期間無資料）")
        return

    print(f"✅ 取得 {len(odds_list)} 場比賽盤口：")
    for g in odds_list:
        print(f"   {g['away_team']} @ {g['home_team']}"
              f"  讓分:{g['spread_line']}  大小:{g['total_line']}")

    # Step 2：自動抓取今日傷兵資料
    print(f"\n🏥 Step 2：自動抓取傷兵資料...")
    INJURY_DATA = fetch_injuries_nba()
    save_injuries_to_db(INJURY_DATA, target_date)

    # ✅ 如果自動抓取失敗或想手動補充，可以在這裡覆寫：
    # INJURY_DATA["Boston Celtics"] = [
    #     {"name": "Kristaps Porzingis", "role": "starter", "status": "out"},
    # ]

    # Step 3：逐場蒙地卡羅分析
    print(f"\n🎲 Step 3：蒙地卡羅模擬分析...")
    results = []
    for odds in odds_list:
        home = odds['home_team']
        away = odds['away_team']
        home_inj = INJURY_DATA.get(home, [])
        away_inj = INJURY_DATA.get(away, [])

        result = analyze_game(
            game_id        = odds['game_id'],
            home_team      = home,
            away_team      = away,
            spread_line    = odds['spread_line'] or 0,
            total_line     = odds['total_line'] or 220,
            home_ml        = odds.get('home_ml'),
            away_ml        = odds.get('away_ml'),
            home_injuries  = home_inj,
            away_injuries  = away_inj,
            game_date_est  = target_date,
            trigger_session= 'evening',
            save_to_db     = True,
        )
        results.append(result)

    # Step 4：推播 Telegram
    print(f"\n📱 Step 4：推播 Telegram...")
    from datetime import datetime as dt
    predictions = get_todays_predictions(target_date)

    # 晚上推播（早下注信號）
    early_preds = [p for p in predictions if p.get('early_bet_signal') == 1]
    if early_preds:
        for p in early_preds:
            signal = {
                'early_bet_signal': True,
                'go': ['EV 達標', '盤口穩定', '無崩潰', '信心 HIGH'],
                'wait': []
            }
            msg = format_early_bet_alert(p, signal)
            tg_send(msg)
        print(f"⚡ 推播 {len(early_preds)} 個早下注信號")
    else:
        print("ℹ️  今日無早下注信號")

    # 預覽今日推薦
    main_msg = format_morning_broadcast(predictions, target_date)
    print(f"\n{'─'*40}")
    print("📋 今日預測預覽：")
    print(main_msg.replace('<b>','').replace('</b>',''))

    print(f"\n✅ 今日分析完成！")
    print(f"   共分析 {len(results)} 場比賽")
    print(f"   開啟 Streamlit 網頁查看詳細預測")
    return results


# ══════════════════════════════════════════════
# 【區塊 B】早上推播（06:00 EST 前執行）
# 台灣時間下午 6-7 點
# ══════════════════════════════════════════════
def run_morning_push(target_date: str = TARGET_DATE):
    print(f"\n{'─'*55}")
    print(f"📡 區塊 B：早上推播 — {target_date}")
    print(f"{'─'*55}")

    # ── Step 1：抓早上盤口快照 ──
    print("📊 抓取早上盤口快照...")
    morning_odds = shield.fetch_odds(target_date, trigger='morning_check')
    morning_odds_map = {o['game_id']: o for o in morning_odds}

    # ── Step 2：重新抓最新傷兵名單 ──
    print("\n🏥 重新抓取最新傷兵名單（比賽前最終確認）...")
    INJURY_DATA_MORNING = fetch_injuries_nba()
    save_injuries_to_db(INJURY_DATA_MORNING, target_date)

    # ── Step 3：偵測盤口異動，觸發重新分析 ──
    print("\n🔍 比對盤口異動...")
    line_alerts = detect_line_moves(target_date)
    reanalyzed = 0

    for alert in line_alerts:
        if not alert.get('has_alert'):
            continue  # 未達門檻，跳過

        gid = alert['game_id']
        if gid not in morning_odds_map:
            continue

        odds = morning_odds_map[gid]
        home = odds['home_team']
        away = odds['away_team']
        home_inj = INJURY_DATA_MORNING.get(home, [])
        away_inj = INJURY_DATA_MORNING.get(away, [])

        print(f"\n  🔄 {alert['matchup']}")
        print(f"     讓分：{alert['spread_eve']} → {alert['spread_morn']}（移動 {alert['spread_move']:.1f}）")
        print(f"     → 使用最新盤口 + 最新傷兵重新分析...")

        # 重新跑蒙地卡羅，更新 DB
        analyze_game(
            game_id        = gid,
            home_team      = home,
            away_team      = away,
            spread_line    = odds['spread_line'] or 0,
            total_line     = odds['total_line'] or 220,
            home_ml        = odds.get('home_ml'),
            away_ml        = odds.get('away_ml'),
            home_injuries  = home_inj,
            away_injuries  = away_inj,
            game_date_est  = target_date,
            trigger_session= 'morning',
            save_to_db     = True,
        )
        reanalyzed += 1

    if reanalyzed > 0:
        print(f"\n✅ 已重新分析 {reanalyzed} 場（盤口異動 ≥ {LINE_MOVE_ALERT} 分）")
    else:
        print("  ✅ 所有盤口穩定，無需重新分析")

    # ── Step 4：執行早上推播 ──
    run_morning_broadcast(target_date)
    print("✅ 早上推播完成")




# ══════════════════════════════════════════════
# 【區塊 C】對獎結算（隔天早上執行）
# 台灣時間隔天早上 8-10 點
# ══════════════════════════════════════════════
def run_settlement(target_date: str = None):
    """
    對昨天的比賽進行結算
    預設對昨天（美東時間）進行對獎
    """
    if target_date is None:
        # 預設對昨天結算
        yesterday = (now_est() - timedelta(days=1)).strftime('%Y-%m-%d')
        target_date = yesterday

    print(f"\n{'─'*55}")
    print(f"🏁 區塊 C：對獎結算 — {target_date}")
    print(f"{'─'*55}")

    run_daily_pipeline(target_date)

    # 自動回補歷史缺漏（靜默模式：只補最近 14 天，避免太慢）
    print(f"\n{'─'*40}")
    print("🔄 檢查歷史缺漏...")
    backfill_settlements(days_back=14)

    print("✅ 結算完成，命中率已更新")


# ══════════════════════════════════════════════
# 【執行區】選擇要執行哪個區塊
# ══════════════════════════════════════════════

# 現在幾點？決定執行哪個區塊
tw_hour = now_tw().hour

print(f"\n🕐 台灣現在時間：{now_tw().strftime('%H:%M')}")
print(f"{'─'*40}")

if 5 <= tw_hour < 18:
    # 早上 5點 ~ 下午 6點 → 對昨天結算
    print("📌 建議執行：【區塊 C】對獎結算（昨天比賽）")
    print()
    print("執行方式：在下方新增 Cell，貼上：")
    print("  run_settlement()")
elif 18 <= tw_hour <= 23:
    # 下午 6點 ~ 晚上 11點 → 今日分析
    print("📌 建議執行：【區塊 A】今日分析 + 【區塊 B】早上推播")
    print()
    print("執行方式：在下方新增兩個 Cell，分別貼上：")
    print("  run_today_analysis()  ← 先填傷兵再執行")
    print("  run_morning_push()    ← 分析完後執行")
else:
    # 深夜 0點 ~ 早上 5點
    print("📌 深夜時段，比賽正在進行中")
    print("   等明天早上 8點 再執行對獎結算")

print(f"{'─'*40}")
print(f"\n💡 也可以直接呼叫任一區塊：")
print(f"   run_today_analysis()  ← 今日分析")
print(f"   run_morning_push()    ← 早上推播")
print(f"   run_settlement()      ← 對獎結算（昨天）")
print(f"   run_settlement('{TARGET_DATE}')  ← 對指定日期結算")
print(f"   backfill_settlements()  ← 回補所有歷史缺漏")
print(f"   backfill_settlements(dry_run=True)  ← 先看有哪些缺漏")
print(f"   restart_streamlit()   ← Streamlit 網址失效時重啟")


# ══════════════════════════════════════════════
# 【區塊 D】重新啟動 Streamlit（網址失效時用）
# ══════════════════════════════════════════════
def restart_streamlit():
    """
    Streamlit 網址失效時執行這個重新取得新網址
    不需要重新安裝套件或寫入 app 檔案
    """
    import os, threading, time
    from google.colab.output import eval_js

    print("🔄 重新啟動 Streamlit...")

    # 確認 app 檔案存在
    if not os.path.exists('/content/streamlit_app.py'):
        print("⚠️  找不到 /content/streamlit_app.py")
        print("   請重新執行「啟動Streamlit_v2」的完整 Cell")
        return

    def run():
        os.system(
            'streamlit run /content/streamlit_app.py '
            '--server.port 8501 '
            '--server.headless true '
            '--server.enableCORS false '
            '--server.enableXsrfProtection false '
            '> /content/streamlit.log 2>&1'
        )

    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(5)

    try:
        url = eval_js("google.colab.kernel.proxyPort(8501)")
        print(f"\n{'='*50}")
        print(f"🌐 Streamlit 已重新啟動！")
        print(f"👉 新網址：{url}")
        print(f"{'='*50}")

        # 推播新網址到 Telegram
        tw_time = datetime.now(TZ_TW).strftime('%m/%d %H:%M')
        tg_send(
            f"🌐 <b>Streamlit 網頁已啟動</b>\n"
            f"{'─'*30}\n"
            f"⏰ {tw_time}（台灣）\n"
            f"👉 <a href=\"{url}\">點擊開啟戰情網頁</a>\n"
            f"{'─'*30}\n"
            f"⚠️ 此網址於 Colab 斷線後失效"
        )
        print("📱 網址已推播到 Telegram")

    except Exception as e:
        print(f"❌ 無法取得網址：{e}")
        print("   請點擊 Colab 右上角 → 埠口(Ports) → 8501")


# ── 提示更新 ──
print("   restart_streamlit() ← Streamlit 網址失效時重啟")
