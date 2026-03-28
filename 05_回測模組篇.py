# =============================================================
# 🏀 NBA 戰情系統 V34.1 — 回測模組篇
# 功能：
#   1. 自動抓取比賽實際比分（NBA 官方數據）
#   2. 每日命中率記錄（daily_performance 表）
#   3. 參數異常自動警示
#   4. 多參數組合回測（找最佳 σ / MARKET_WEIGHT）
#   5. 每週命中率週報推播
# =============================================================
# ⚠️ 前置條件：地基篇 v2 + 引擎篇 v4 + Telegram篇 已執行完畢
# =============================================================


# ─────────────────────────────────────────────
# CELL 24-前置：確認前置變數
# ─────────────────────────────────────────────
required_vars = ["DEV_MODE","DB_PATH","TELEGRAM_TOKEN","TELEGRAM_CHAT_ID",
                 "now_est","shield","tg_send","grade_result","get_hit_rate",
                 "run_monte_carlo","SIGMA_NORMAL","SIGMA_COLLAPSE",
                 "KELLY_FRACTION","MAX_BET_PCT","MARKET_WEIGHT" if "MARKET_WEIGHT" in dir() else "SIGMA_NORMAL"]
missing = [v for v in required_vars if v not in dir()]
if missing:
    raise RuntimeError("請先執行地基篇 v2 + 引擎篇 v4 + Telegram篇，缺少：" + str(missing))
print("✅ 前置變數確認完成")


# ─────────────────────────────────────────────
# CELL 24：建立回測相關資料表
# ─────────────────────────────────────────────
import sqlite3, json, time
import numpy as np
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def init_backtest_tables():
    """建立回測模組需要的額外資料表"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 每日績效記錄
    c.execute('''
    CREATE TABLE IF NOT EXISTS daily_performance (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        date_est            TEXT NOT NULL UNIQUE,   -- YYYY-MM-DD
        total_games         INTEGER DEFAULT 0,       -- 當日總場次
        games_predicted     INTEGER DEFAULT 0,       -- 有預測的場次
        games_bet           INTEGER DEFAULT 0,       -- 實際下注場次（非SKIP）
        hits                INTEGER DEFAULT 0,       -- 命中數
        hit_rate            REAL,                    -- 命中率
        spread_hits         INTEGER DEFAULT 0,       -- 讓分命中
        spread_total        INTEGER DEFAULT 0,
        ou_hits             INTEGER DEFAULT 0,       -- 大小分命中
        ou_total            INTEGER DEFAULT 0,
        high_conf_hits      INTEGER DEFAULT 0,       -- HIGH信心命中
        high_conf_total     INTEGER DEFAULT 0,
        collapse_hits       INTEGER DEFAULT 0,       -- 崩潰模式命中
        collapse_total      INTEGER DEFAULT 0,
        daily_pnl           REAL DEFAULT 0,          -- 當日 PnL（%本金）
        cumulative_pnl      REAL DEFAULT 0,          -- 累積 PnL
        avg_ev              REAL,                    -- 當日平均 EV
        params_snapshot     TEXT,                    -- 當日使用的參數快照
        notes               TEXT,
        created_at          TEXT DEFAULT (datetime('now'))
    )''')
    
    # 向後相容：自動新增欄位
    try:
        c.execute("ALTER TABLE daily_performance ADD COLUMN ml_hits INTEGER DEFAULT 0")
        c.execute("ALTER TABLE daily_performance ADD COLUMN ml_total INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # 參數警示記錄
    c.execute('''
    CREATE TABLE IF NOT EXISTS param_alerts (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_time_est      TEXT DEFAULT (datetime('now')),
        alert_type          TEXT,    -- 'low_hit_rate'/'ev_mismatch'/'collapse_overshoot'
        description         TEXT,
        current_value       REAL,
        threshold           REAL,
        suggested_action    TEXT,
        is_resolved         INTEGER DEFAULT 0
    )''')

    conn.commit()
    conn.close()
    print("✅ 回測資料表建立完成")
    print("   📋 daily_performance — 每日命中率記錄")
    print("   📋 param_alerts      — 參數異常警示")

init_backtest_tables()


# ─────────────────────────────────────────────
# CELL 25：自動抓取比賽實際比分
# ─────────────────────────────────────────────

def fetch_actual_scores(game_date_est: str) -> list:
    """
    從 NBA 官方 S3 端點抓取比賽結果
    完全免費，無需任何 API Key ✅
    同時支援今天和昨天的比賽結果
    """
    if DEV_MODE:
        print(f"🔒 DEV_MODE：回傳假比分資料")
        return [
            {'home_team': 'Boston Celtics',  'away_team': 'Miami Heat',
             'home_score': 117, 'away_score': 108, 'status': 'Final'},
            {'home_team': 'Denver Nuggets',  'away_team': 'Phoenix Suns',
             'home_score': 109, 'away_score': 118, 'status': 'Final'},
            {'home_team': 'LA Lakers',       'away_team': 'Golden State Warriors',
             'home_score': 121, 'away_score': 115, 'status': 'Final'},
        ]

    import requests
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    # NBA S3 端點（可抓今天和近期歷史比賽）
    ENDPOINTS = [
        "https://nba-prod-us-east-1-mediaops-stats.s3.amazonaws.com/NBA/liveData/scoreboard/todaysScoreboard_00.json",
        "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json",
    ]

    # 目標日期的 gcode 前綴（格式：YYYYMMDD）
    target_prefix = game_date_est.replace('-', '')

    for url in ENDPOINTS:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue

            data  = resp.json()
            games = data.get('scoreboard', {}).get('games', [])

            if not games:
                continue

            results = []
            for g in games:
                # 過濾指定日期（用 gameCode 的日期前綴判斷）
                game_code = g.get('gameCode', '')
                if not game_code.startswith(target_prefix):
                    continue

                # 只取已結束的比賽
                if g.get('gameStatus') != 3:
                    continue

                home = g.get('homeTeam', {})
                away = g.get('awayTeam', {})

                home_name = _normalize_nba_team(
                    f"{home.get('teamCity','')} {home.get('teamName','')}".strip())
                away_name = _normalize_nba_team(
                    f"{away.get('teamCity','')} {away.get('teamName','')}".strip())

                results.append({
                    'home_team':  home_name,
                    'away_team':  away_name,
                    'home_score': home.get('score', 0),
                    'away_score': away.get('score', 0),
                    'status':     g.get('gameStatusText', 'Final'),
                    'game_id':    g.get('gameId', ''),
                })

            if results:
                print(f"   ✅ NBA 官方取得 {len(results)} 場結果（{game_date_est}）")
                return results

        except Exception as e:
            print(f"   ⚠️  端點失敗：{e}")
            continue

    print(f"   ❌ 無法取得 {game_date_est} 的比賽結果")
    return []


def _normalize_nba_team(name: str) -> str:
    """將 NBA API 回傳的球隊名稱標準化"""
    mapping = {
        'Atlanta Hawks': 'Atlanta Hawks',
        'Boston Celtics': 'Boston Celtics',
        'Brooklyn Nets': 'Brooklyn Nets',
        'Charlotte Hornets': 'Charlotte Hornets',
        'Chicago Bulls': 'Chicago Bulls',
        'Cleveland Cavaliers': 'Cleveland Cavaliers',
        'Dallas Mavericks': 'Dallas Mavericks',
        'Denver Nuggets': 'Denver Nuggets',
        'Detroit Pistons': 'Detroit Pistons',
        'Golden State Warriors': 'Golden State Warriors',
        'Houston Rockets': 'Houston Rockets',
        'Indiana Pacers': 'Indiana Pacers',
        # ✅ Clippers/Lakers 有兩種寫法都要對應
        'Los Angeles Clippers': 'Los Angeles Clippers',
        'LA Clippers': 'Los Angeles Clippers',
        'Los Angeles Lakers': 'Los Angeles Lakers',
        'LA Lakers': 'Los Angeles Lakers',
        'Memphis Grizzlies': 'Memphis Grizzlies',
        'Miami Heat': 'Miami Heat',
        'Milwaukee Bucks': 'Milwaukee Bucks',
        'Minnesota Timberwolves': 'Minnesota Timberwolves',
        'New Orleans Pelicans': 'New Orleans Pelicans',
        'New York Knicks': 'New York Knicks',
        'Oklahoma City Thunder': 'Oklahoma City Thunder',
        'Orlando Magic': 'Orlando Magic',
        'Philadelphia 76ers': 'Philadelphia 76ers',
        'Phoenix Suns': 'Phoenix Suns',
        'Portland Trail Blazers': 'Portland Trail Blazers',
        'Sacramento Kings': 'Sacramento Kings',
        'San Antonio Spurs': 'San Antonio Spurs',
        'Toronto Raptors': 'Toronto Raptors',
        'Utah Jazz': 'Utah Jazz',
        'Washington Wizards': 'Washington Wizards',
    }
    # 先試精確匹配，找不到就試 city+name 拆分比對
    if name in mapping:
        return mapping[name]
    # 模糊匹配：取球隊暱稱最後一個詞比對
    last_word = name.split()[-1] if name else ''
    for key, val in mapping.items():
        if key.split()[-1] == last_word:
            return val
    return name


def match_and_grade(game_date_est: str) -> dict:
    """
    比對當日預測與實際結果，自動對獎
    回傳當日統計摘要
    """
    print(f"\n{'='*50}")
    print(f"🏁 自動對獎 — {game_date_est}")
    print(f"{'='*50}")

    # 讀取當日預測
    conn = sqlite3.connect(DB_PATH)
    preds = conn.execute('''
        SELECT game_id, home_team, away_team, recommended_bet
        FROM predictions
        WHERE game_date_est = ?
        GROUP BY home_team, away_team
        HAVING created_at_est = MAX(created_at_est)
    ''', (game_date_est,)).fetchall()
    conn.close()

    if not preds:
        print(f"  ℹ️  {game_date_est} 無預測資料")
        return {}

    # 抓實際比分
    actual_scores = fetch_actual_scores(game_date_est)
    if not actual_scores:
        print(f"  ℹ️  {game_date_est} 比賽尚未結束或無法取得比分")
        return {}

    # 比對配對（用球隊名稱模糊匹配）
    graded = 0
    for pred in preds:
        game_id, home, away, rec = pred
        # 找對應的實際比分
        match = next(
            (s for s in actual_scores
             if _team_match(s['home_team'], home) and _team_match(s['away_team'], away)),
            None
        )
        if match and str(match.get('status', '')).startswith('Final'):
            grade_result(
                game_id=game_id,
                actual_score_home=match['home_score'],
                actual_score_away=match['away_score'],
                data_source='auto'
            )
            graded += 1

    print(f"\n  ✅ 完成對獎：{graded}/{len(preds)} 場")
    return {'graded': graded, 'total_preds': len(preds)}


def _team_match(name1: str, name2: str) -> bool:
    """球隊名稱模糊匹配（取最後一個詞比對）"""
    n1 = name1.lower().strip().split()[-1]
    n2 = name2.lower().strip().split()[-1]
    return n1 == n2

print("✅ 自動對獎模組就緒")


# ─────────────────────────────────────────────
# CELL 26：每日績效計算與記錄
# ─────────────────────────────────────────────

def calculate_daily_performance(game_date_est: str) -> dict:
    """
    計算並儲存當日完整績效指標
    包含：整體命中率、分組命中率（HIGH/MED/崩潰）、PnL
    """
    conn = sqlite3.connect(DB_PATH)

    # 聯合查詢 predictions + results
    rows = conn.execute('''
        SELECT
            p.game_id,
            p.confidence_level,
            p.collapse_flag,
            p.ev_value,
            p.suggested_bet_pct,
            p.recommended_bet,
            r.spread_result,
            r.ou_result,
            r.bet_hit,
            r.pnl,
            p.ai_score_home,
            p.ai_score_away,
            r.actual_score_home,
            r.actual_score_away
        FROM predictions p
        LEFT JOIN results r ON p.game_id = r.game_id
        WHERE p.game_date_est = ?
        GROUP BY p.home_team, p.away_team
        HAVING p.created_at_est = MAX(p.created_at_est)
    ''', (game_date_est,)).fetchall()

    if not rows:
        conn.close()
        return {}

    # 計算各項指標
    total = len(rows)
    bet_rows    = [r for r in rows if r[5] and r[5] != 'SKIP']
    graded_rows = [r for r in rows if r[8] is not None]

    hits         = sum(1 for r in graded_rows if r[8] == 1)
    hit_rate     = hits / len(graded_rows) if graded_rows else None
    daily_pnl    = sum(r[9] or 0 for r in graded_rows)
    
    # 計算純勝負預測 (Moneyline) 命中率
    ml_hits = 0
    ml_total = 0
    for r in rows:
        ai_h, ai_a, act_h, act_a = r[10], r[11], r[12], r[13]
        if ai_h is not None and ai_a is not None and act_h is not None and act_a is not None:
            if act_h != act_a:
                ml_total += 1
                if (ai_h > ai_a) == (act_h > act_a):
                    ml_hits += 1

    # 分組命中率
    high_rows     = [r for r in graded_rows if r[1] == 'HIGH']
    collapse_rows = [r for r in graded_rows if r[2] == 1]
    spread_rows   = [r for r in graded_rows if r[6] is not None and r[6] != 'PUSH']
    ou_rows       = [r for r in graded_rows if r[7] is not None and r[7] != 'PUSH']

    high_hits     = sum(1 for r in high_rows if r[8] == 1)
    collapse_hits = sum(1 for r in collapse_rows if r[8] == 1)
    spread_hits   = sum(1 for r in spread_rows if r[6] == 'WIN')
    ou_hits       = sum(1 for r in ou_rows if r[7] in ('OVER','UNDER'))

    avg_ev = sum(r[3] or 0 for r in bet_rows) / len(bet_rows) if bet_rows else 0

    # 計算累積 PnL（加上歷史）
    prev = conn.execute('''
        SELECT cumulative_pnl FROM daily_performance
        ORDER BY date_est DESC LIMIT 1
    ''').fetchone()
    cumulative_pnl = (prev[0] or 0) + daily_pnl if prev else daily_pnl

    # 參數快照
    params_snap = json.dumps({
        'sigma_normal': SIGMA_NORMAL,
        'sigma_collapse': SIGMA_COLLAPSE,
        'kelly_fraction': KELLY_FRACTION,
        'market_weight': 0.35,
        'version': 'V34.1'
    })

    # 存入 DB（UPSERT）
    conn.execute('''
        INSERT INTO daily_performance (
            date_est, total_games, games_predicted, games_bet,
            hits, hit_rate,
            spread_hits, spread_total,
            ou_hits, ou_total,
            high_conf_hits, high_conf_total,
            collapse_hits, collapse_total,
            daily_pnl, cumulative_pnl, avg_ev, params_snapshot,
            ml_hits, ml_total
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(date_est) DO UPDATE SET
            hits=excluded.hits, hit_rate=excluded.hit_rate,
            daily_pnl=excluded.daily_pnl,
            cumulative_pnl=excluded.cumulative_pnl,
            ml_hits=excluded.ml_hits, ml_total=excluded.ml_total
    ''', (
        game_date_est, total, total, len(bet_rows),
        hits, hit_rate,
        spread_hits, len(spread_rows),
        ou_hits, len(ou_rows),
        high_hits, len(high_rows),
        collapse_hits, len(collapse_rows),
        daily_pnl, cumulative_pnl, avg_ev, params_snap,
        ml_hits, ml_total
    ))
    conn.commit()
    conn.close()

    perf = {
        'date': game_date_est,
        'total': total, 'graded': len(graded_rows),
        'hits': hits, 'hit_rate': hit_rate,
        'high_hit_rate': high_hits/len(high_rows) if high_rows else None,
        'collapse_hit_rate': collapse_hits/len(collapse_rows) if collapse_rows else None,
        'daily_pnl': daily_pnl,
        'cumulative_pnl': cumulative_pnl,
        'avg_ev': avg_ev
    }

    # 印出報告
    ml_rate_str = f"{ml_hits/ml_total:.1%}" if ml_total > 0 else "--"
    print(f"\n{'='*50}")
    print(f"📈 每日績效 — {game_date_est}")
    print(f"{'='*50}")
    print(f"  總預測：{total}  已對獎：{len(graded_rows)}")
    print(f"  純勝負預測命中：{ml_hits}/{ml_total} ({ml_rate_str})")
    print(f"  投資總命中率：{hit_rate:.1%}" if hit_rate is not None else "  投資總命中率：--")
    print(f"  HIGH信心：{high_hits}/{len(high_rows)}  {'({:.1%})'.format(high_hits/len(high_rows)) if high_rows else '--'}")
    print(f"  崩潰模式：{collapse_hits}/{len(collapse_rows)}  {'({:.1%})'.format(collapse_hits/len(collapse_rows)) if collapse_rows else '--'}")
    print(f"  當日 PnL：{daily_pnl:+.2%}  累積 PnL：{cumulative_pnl:+.2%}")
    print(f"{'='*50}")

    return perf

print("✅ 每日績效模組就緒")


# ─────────────────────────────────────────────
# CELL 27：參數異常自動警示
# ─────────────────────────────────────────────

# 警示觸發閾值（可調整）
ALERT_THRESHOLDS = {
    'consecutive_low_hitrate': {'days': 5,  'rate': 0.50},  # 連續N天命中率低於X
    'high_conf_low_hitrate':   {'min_games': 10, 'rate': 0.52},  # HIGH信心命中率
    'collapse_overshoot':      {'min_games': 8,  'rate': 0.60},  # 崩潰模式準確過頭
    'ev_pnl_mismatch':         {'ev_min': 0.10, 'pnl_max': -0.02},  # 高EV但負PnL
}

def check_param_alerts() -> list:
    """
    分析最近績效，自動偵測需要調整參數的信號
    回傳警示清單
    """
    conn = sqlite3.connect(DB_PATH)
    alerts = []

    # 讀取最近 14 天績效
    rows = conn.execute('''
        SELECT date_est, hit_rate, high_conf_hits, high_conf_total,
               collapse_hits, collapse_total, daily_pnl, avg_ev
        FROM daily_performance
        WHERE date_est >= date('now', '-14 days')
        ORDER BY date_est DESC
    ''').fetchall()
    conn.close()

    if len(rows) < 3:
        print("  ℹ️  資料不足（需至少 3 天），暫不觸發警示")
        return []

    # ── 警示1：連續低命中率 ──────────────────
    threshold = ALERT_THRESHOLDS['consecutive_low_hitrate']
    recent = [r for r in rows[:threshold['days']] if r[1] is not None]
    if len(recent) >= threshold['days']:
        avg_rate = sum(r[1] for r in recent) / len(recent)
        if avg_rate < threshold['rate']:
            alert = {
                'type': 'low_hit_rate',
                'desc': f"最近 {threshold['days']} 天平均命中率 {avg_rate:.1%}，低於門檻 {threshold['rate']:.0%}",
                'value': avg_rate,
                'threshold': threshold['rate'],
                'action': f"建議將 MARKET_WEIGHT 從 0.35 調高至 0.45，讓預測更貼近市場盤口"
            }
            alerts.append(alert)
            print(f"  ⚠️  {alert['desc']}")
            print(f"       → {alert['action']}")

    # ── 警示2：HIGH信心命中率偏低 ───────────
    threshold = ALERT_THRESHOLDS['high_conf_low_hitrate']
    total_high = sum(r[3] or 0 for r in rows)
    hits_high  = sum(r[2] or 0 for r in rows)
    if total_high >= threshold['min_games']:
        rate = hits_high / total_high
        if rate < threshold['rate']:
            alert = {
                'type': 'high_conf_low_hitrate',
                'desc': f"HIGH信心命中率 {rate:.1%}（{hits_high}/{total_high}），低於門檻 {threshold['rate']:.0%}",
                'value': rate,
                'threshold': threshold['rate'],
                'action': "建議將 EV 門檻從 10% 提高至 15%，減少低品質下注"
            }
            alerts.append(alert)
            print(f"  ⚠️  {alert['desc']}")
            print(f"       → {alert['action']}")

    # ── 警示3：崩潰模式命中率過高（σ設太保守）─
    threshold = ALERT_THRESHOLDS['collapse_overshoot']
    total_col = sum(r[5] or 0 for r in rows)
    hits_col  = sum(r[4] or 0 for r in rows)
    if total_col >= threshold['min_games']:
        rate = hits_col / total_col
        if rate > threshold['rate']:
            alert = {
                'type': 'collapse_overshoot',
                'desc': f"崩潰模式命中率 {rate:.1%}（{hits_col}/{total_col}），高於 {threshold['rate']:.0%}",
                'value': rate,
                'threshold': threshold['rate'],
                'action': f"崩潰時 σ=15 可能過於保守，可考慮調回 13.0"
            }
            alerts.append(alert)
            print(f"  📊  {alert['desc']}")
            print(f"       → {alert['action']}")

    # ── 警示4：高EV但實際PnL為負 ────────────
    recent_pnl = sum(r[6] or 0 for r in rows[:7])
    recent_ev  = sum(r[7] or 0 for r in rows[:7] if r[7]) / max(len([r for r in rows[:7] if r[7]]), 1)
    t = ALERT_THRESHOLDS['ev_pnl_mismatch']
    if recent_ev > t['ev_min'] and recent_pnl < t['pnl_max']:
        alert = {
            'type': 'ev_pnl_mismatch',
            'desc': f"近7天平均EV {recent_ev:.1%} 但累積PnL {recent_pnl:+.2%}，EV可能高估",
            'value': recent_ev,
            'threshold': t['ev_min'],
            'action': "建議檢查傷兵扣分邏輯，EV計算可能過於樂觀"
        }
        alerts.append(alert)
        print(f"  ⚠️  {alert['desc']}")
        print(f"       → {alert['action']}")

    # 存入 DB
    if alerts:
        conn = sqlite3.connect(DB_PATH)
        for a in alerts:
            conn.execute('''
                INSERT INTO param_alerts
                (alert_type, description, current_value, threshold, suggested_action)
                VALUES (?,?,?,?,?)
            ''', (a['type'], a['desc'], a['value'], a['threshold'], a['action']))
        conn.commit()
        conn.close()
        # 推播警示到 Telegram
        alert_lines = [f"⚠️ <b>參數調整警示</b>\n{'─'*30}"]
        for a in alerts:
            alert_lines.append(f"🔸 {a['desc']}\n   👉 {a['action']}")
        tg_send("\n".join(alert_lines))
    else:
        print("  ✅ 無參數警示，模型表現正常")

    return alerts

print("✅ 參數警示模組就緒")


# ─────────────────────────────────────────────
# CELL 28：多參數回測引擎
# ─────────────────────────────────────────────

def run_backtest(
    date_start: str,
    date_end: str,
    param_grid: list = None,
    run_name: str = None
) -> list:
    """
    用歷史存下的資料重跑不同參數組合
    param_grid 格式：
    [
        {'sigma_normal': 12.0, 'sigma_collapse': 15.0, 'market_weight': 0.35},
        {'sigma_normal': 11.0, 'sigma_collapse': 14.0, 'market_weight': 0.40},
        ...
    ]
    回傳每組參數的命中率結果
    """
    if param_grid is None:
        # 預設網格搜尋範圍
        param_grid = [
            {'sigma_normal': s, 'sigma_collapse': s+3, 'market_weight': w}
            for s in [10.0, 11.0, 12.0, 13.0]
            for w in [0.25, 0.35, 0.45]
        ]

    run_name = run_name or f"backtest_{date_start}_{date_end}"
    print(f"\n{'='*55}")
    print(f"🔬 回測引擎啟動")
    print(f"   日期範圍：{date_start} ~ {date_end}")
    print(f"   參數組合：{len(param_grid)} 組")
    print(f"{'='*55}")

    # 讀取歷史預測原始資料（含 injury_snapshot、pace、open_line）
    conn = sqlite3.connect(DB_PATH)
    hist = conn.execute('''
        SELECT
            p.game_id, p.game_date_est,
            p.home_team, p.away_team,
            p.open_line, p.total_line,
            p.home_odds, p.away_odds,
            p.injury_snapshot,
            p.pace_home, p.pace_away,
            r.spread_result, r.ou_result,
            r.actual_spread, r.actual_total,
            r.actual_winner
        FROM predictions p
        JOIN results r ON p.game_id = r.game_id
        WHERE p.game_date_est BETWEEN ? AND ?
        AND r.is_final = 1
        GROUP BY p.home_team, p.away_team, p.game_date_est
        HAVING p.created_at_est = MAX(p.created_at_est)
    ''', (date_start, date_end)).fetchall()
    conn.close()

    if not hist:
        print("  ⚠️  此日期範圍無歷史對獎資料")
        return []

    print(f"  📋 找到 {len(hist)} 場歷史對獎記錄")

    results = []
    for i, params in enumerate(param_grid):
        sigma_n = params['sigma_normal']
        sigma_c = params['sigma_collapse']
        mw      = params['market_weight']

        hits = total = 0
        pnl_sum = 0.0

        for row in hist:
            (game_id, game_date, home, away,
             open_line, total_line, home_ml, away_ml,
             injury_json, pace_h, pace_a,
             spread_res, ou_res,
             actual_spread, actual_total, actual_winner) = row

            injuries = json.loads(injury_json) if injury_json else {'home':[],'away':[]}

            # 用歷史傷兵資料重跑蒙地卡羅（新參數）
            try:
                mc = run_monte_carlo(
                    home_team=home, away_team=away,
                    home_injuries=injuries.get('home', []),
                    away_injuries=injuries.get('away', []),
                    n_simulations=5000,  # 回測用較少次數加速
                    custom_params={'sigma_normal': sigma_n, 'sigma_collapse': sigma_c},
                    verbose=False,
                    spread_line=open_line
                )

                # 套用盤口錨定（新 market_weight）
                if open_line:
                    model_spread  = mc['pred_spread']
                    market_spread = -open_line
                    blended = model_spread * (1-mw) + market_spread * mw
                    mc['pred_spread'] = blended

                # 簡單判斷是否蓋盤
                bet_hit = None
                if open_line and actual_spread is not None:
                    pred_cover = mc['pred_spread'] > open_line
                    actual_cover = actual_spread > open_line
                    bet_hit = 1 if pred_cover == actual_cover else 0

                if bet_hit is not None:
                    total += 1
                    hits += bet_hit
                    pnl = (100/110) * 0.03 if bet_hit == 1 else -0.03
                    pnl_sum += pnl

            except Exception:
                continue

        hit_rate = hits / total if total > 0 else 0
        roi = pnl_sum

        result = {
            'params': params,
            'total_games': total,
            'hits': hits,
            'hit_rate': round(hit_rate, 4),
            'roi': round(roi, 4),
            'run_name': run_name
        }
        results.append(result)

        print(f"  [{i+1:2d}/{len(param_grid)}] σ={sigma_n}/{sigma_c}  MW={mw}"
              f"  命中率:{hit_rate:.1%}  ROI:{roi:+.2%}  ({hits}/{total}場)")

        # 存入 backtest_runs
        conn = sqlite3.connect(DB_PATH)
        conn.execute('''
            INSERT INTO backtest_runs
            (run_name, date_range_start, date_range_end,
             total_games, games_bet, overall_hit_rate, roi, params_json)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (run_name, date_start, date_end,
              total, total, hit_rate, roi, json.dumps(params)))
        conn.commit()
        conn.close()

    # 找最佳參數
    if results:
        best = max(results, key=lambda x: x['hit_rate'])
        print(f"\n{'='*55}")
        print(f"🏆 最佳參數組合：")
        print(f"   σ = {best['params']['sigma_normal']} / {best['params']['sigma_collapse']}")
        print(f"   MARKET_WEIGHT = {best['params']['market_weight']}")
        print(f"   命中率：{best['hit_rate']:.1%}  ROI：{best['roi']:+.2%}")
        print(f"{'='*55}")

        # 推播回測結果
        msg = (
            f"🔬 <b>回測完成</b> {date_start}~{date_end}\n"
            f"{'─'*30}\n"
            f"測試 {len(param_grid)} 組參數  共 {len(hist)} 場\n\n"
            f"🏆 最佳組合：\n"
            f"  σ = {best['params']['sigma_normal']}/{best['params']['sigma_collapse']}\n"
            f"  MARKET_WEIGHT = {best['params']['market_weight']}\n"
            f"  命中率：{best['hit_rate']:.1%}  ROI：{best['roi']:+.2%}"
        )
        tg_send(msg)

    return results

print("✅ 回測引擎就緒")


# ─────────────────────────────────────────────
# CELL 29：每週績效週報
# ─────────────────────────────────────────────

def send_weekly_report():
    """
    生成並推播上週命中率週報
    包含：7天命中率、PnL曲線摘要、最佳/最差日期
    """
    today = now_est()
    week_end   = today.strftime('%Y-%m-%d')
    week_start = (today - timedelta(days=7)).strftime('%Y-%m-%d')

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('''
        SELECT date_est, hit_rate, daily_pnl, cumulative_pnl,
               games_bet, high_conf_hits, high_conf_total,
               collapse_hits, collapse_total
        FROM daily_performance
        WHERE date_est BETWEEN ? AND ?
        ORDER BY date_est
    ''', (week_start, week_end)).fetchall()
    conn.close()

    if not rows:
        tg_send(f"📊 週報 {week_start}~{week_end}\n\n本週無績效資料")
        return

    valid_rows  = [r for r in rows if r[1] is not None]
    avg_rate    = sum(r[1] for r in valid_rows) / len(valid_rows) if valid_rows else 0
    total_pnl   = sum(r[2] or 0 for r in rows)
    total_games = sum(r[4] or 0 for r in rows)
    last_cum    = rows[-1][3] or 0

    best_day  = max(valid_rows, key=lambda x: x[1]) if valid_rows else None
    worst_day = min(valid_rows, key=lambda x: x[1]) if valid_rows else None

    # HIGH 信心累積
    high_hits  = sum(r[5] or 0 for r in rows)
    high_total = sum(r[6] or 0 for r in rows)
    high_rate  = high_hits / high_total if high_total > 0 else 0

    # 每日命中率列表
    daily_lines = []
    for r in rows:
        rate_str = f"{r[1]:.0%}" if r[1] is not None else "--"
        pnl_str  = f"{r[2]:+.1%}" if r[2] is not None else "--"
        emoji    = "🟢" if (r[1] or 0) >= 0.55 else "🔴" if (r[1] or 0) < 0.45 else "🟡"
        daily_lines.append(f"  {emoji} {r[0][5:]}  命中:{rate_str}  PnL:{pnl_str}")

    msg_lines = [
        f"📊 <b>週報</b> {week_start} ~ {week_end}",
        f"{'─'*30}",
        f"總場次：{total_games}  平均命中：{avg_rate:.1%}",
        f"本週 PnL：{total_pnl:+.2%}  累積 PnL：{last_cum:+.2%}",
        f"HIGH信心：{high_hits}/{high_total} ({high_rate:.1%})",
        f"{'─'*30}",
        "<b>每日明細：</b>",
    ] + daily_lines + [
        f"{'─'*30}",
    ]

    if best_day:
        msg_lines.append(f"🏆 最佳：{best_day[0][5:]}  {best_day[1]:.0%}")
    if worst_day and worst_day != best_day:
        msg_lines.append(f"📉 最差：{worst_day[0][5:]}  {worst_day[1]:.0%}")

    tg_send("\n".join(msg_lines))
    print("✅ 週報已發送")

print("✅ 週報模組就緒")


# ─────────────────────────────────────────────
# CELL 30：完整每日流程（一鍵執行）
# ─────────────────────────────────────────────

def run_daily_pipeline(game_date_est: str = None):
    """
    每天執行一次的完整流程：
    1. 自動對獎（抓實際比分）
    2. 計算每日績效
    3. 檢查參數警示
    4. 若為週一，發送週報
    """
    game_date_est = game_date_est or now_est().strftime('%Y-%m-%d')
    print(f"\n{'='*55}")
    print(f"🔄 每日流程啟動 — {game_date_est}")
    print(f"{'='*55}")

    # 1. 自動對獎
    grade_summary = match_and_grade(game_date_est)

    # 2. 每日績效
    if grade_summary.get('graded', 0) > 0:
        perf = calculate_daily_performance(game_date_est)
    else:
        print("  ℹ️  無對獎資料，跳過績效計算")
        perf = {}

    # 3. 參數警示
    print(f"\n{'─'*40}")
    print("🔍 參數警示檢查...")
    alerts = check_param_alerts()

    # 4. 週一發週報
    weekday = datetime.strptime(game_date_est, '%Y-%m-%d').weekday()
    if weekday == 0:  # 週一
        print(f"\n{'─'*40}")
        print("📊 週一週報...")
        send_weekly_report()

    print(f"\n✅ 每日流程完成 — {game_date_est}")
    return {'grade': grade_summary, 'perf': perf, 'alerts': alerts}


print("✅ 每日流程模組就緒")


# ─────────────────────────────────────────────
# CELL 31：DEV 測試
# ─────────────────────────────────────────────

if DEV_MODE:
    today_est = now_est().strftime('%Y-%m-%d')
    print(f"\n🧪 DEV 測試開始...\n")

    # 測試1：自動對獎
    print("── 測試1：自動對獎 ──")
    match_and_grade(today_est)

    # 測試2：每日績效
    print("\n── 測試2：每日績效 ──")
    perf = calculate_daily_performance(today_est)

    # 測試3：參數警示（資料不足，預期顯示「資料不足」）
    print("\n── 測試3：參數警示 ──")
    check_param_alerts()

    # 測試4：回測引擎（用現有少量資料）
    print("\n── 測試4：回測引擎（小規模）──")
    bt_results = run_backtest(
        date_start = today_est,
        date_end   = today_est,
        param_grid = [
            {'sigma_normal': 12.0, 'sigma_collapse': 15.0, 'market_weight': 0.35},
            {'sigma_normal': 11.0, 'sigma_collapse': 14.0, 'market_weight': 0.40},
            {'sigma_normal': 13.0, 'sigma_collapse': 16.0, 'market_weight': 0.30},
        ],
        run_name = 'DEV_TEST'
    )

    # 測試5：週報格式
    print("\n── 測試5：週報預覽 ──")
    send_weekly_report()

    # 最終命中率
    get_hit_rate()

    print(f"\n🎉 回測模組篇測試完成！")
    print(f"   下一步：Streamlit 視覺化篇")
