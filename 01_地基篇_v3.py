# =============================================================
# 🏀 NBA 戰情系統 V34.1 — 完整使用說明
# =============================================================
#
# ⚠️  【每月定期維護提醒】每月 1 日檢查一次
# ─────────────────────────────────────────────
#
# 1. TEAM_STATS 更新（引擎篇 CELL 12）
#    更新各隊 off_rtg / def_rtg / pace / home_adv
#    參考：https://www.nba.com/stats/teams/advanced
#
# 2. PLAYER_ROLES 更新（傷兵資料模組）
#    有新崛起球星記得加進去，例如：
#    "Cason Wallace": "allstar"
#    參考：每月全明星票選排名或上場數據
#
# 3. 季後賽期間
#    home_adv 可考慮調高 0.5-1.0 分
#    σ 可考慮調低（季後賽節奏較慢、比賽更謹慎）
#
# 4. 球員轉隊
#    PLAYER_ROLES 只記錄「球員等級」不記錄球隊
#    所以轉隊不影響系統，NBA 官方 PDF 會自動對應正確球隊
#    不需要手動修改！
#
# =============================================================
#
# 🏀 NBA 戰情系統 V34.1 — 完整使用說明
# =============================================================
#
# ⚠️  每次開啟 Colab 前，先確認 CELL 3 的設定：
#     DEV_MODE = False   ← 正式模式（接真實 API）
#     DEV_MODE = True    ← 測試模式（不消耗任何 API 次數）
#
# ─────────────────────────────────────────────
# 📋 執行順序（每次開啟 Colab 都要依序跑完）
# ─────────────────────────────────────────────
#
#   Step 1：地基篇_v3.py             ← 你現在在這裡
#   Step 2：蒙地卡羅引擎篇_v4.py
#   Step 3：傷兵資料模組_v2.py       ← NBA 官方傷兵來源
#   Step 4：Telegram推播篇.py
#   Step 5：回測模組篇.py
#   Step 6：每日一鍵執行.py          ← 最後執行，看提示操作
#
# ─────────────────────────────────────────────
# 📅 每日操作流程
# ─────────────────────────────────────────────
#
#   【台灣晚上】執行完 Step 1-6 後：
#     run_today_analysis()    ← 抓盤口 + 傷兵 + 分析 + 推播早下注信號
#
#   【台灣早上起床】重新執行 Step 1-6 後：
#     run_morning_push()      ← 抓早上盤口 + 比對異動 + 推播今日清單
#
#   【台灣下午，比賽結束後】：
#     run_settlement()        ← 自動對獎 + 記錄命中率
#
#   【Streamlit 網址失效】：
#     restart_streamlit()     ← 重啟網頁，並推播新網址到 Telegram
#
# ─────────────────────────────────────────────
# 🔑 Colab Secrets 設定（左側鑰匙圖示）
# ─────────────────────────────────────────────
#
#   ODDS_API_KEY        ← The Odds API 金鑰
#   TELEGRAM_TOKEN      ← Telegram Bot Token
#   TELEGRAM_CHAT_ID    ← 你的 Telegram Chat ID
#
# ─────────────────────────────────────────────
# 💡 常用指令速查
# ─────────────────────────────────────────────
#
#   run_today_analysis()              ← 今日分析（晚上）
#   run_today_analysis('2026-03-22')  ← 指定日期分析
#   run_morning_push()                ← 早上推播
#   run_settlement()                  ← 對獎結算（昨天）
#   run_settlement('2026-03-21')      ← 指定日期結算
#   restart_streamlit()               ← 重啟網頁介面
#   get_hit_rate()                    ← 查看目前命中率
#   check_param_alerts()              ← 查看參數警示
#   run_backtest('2026-03-01','2026-03-31')  ← 執行回測
#
# =============================================================

# =============================================================
# 🏀 NBA 戰情系統 V34.1 — 地基篇 v2（修正版）
# Schema + Cache 保護層 + The Odds API 串接
# =============================================================
# 使用說明：
# 1. 在 Colab 左側 🔑 Secrets 新增：
#    - ODDS_API_KEY
#    - TELEGRAM_TOKEN
#    - TELEGRAM_CHAT_ID
# 2. 每個「# ────」分隔區塊就是一個 Cell
# 3. 依序執行，DEV_MODE=True 不會消耗任何 API 次數
# =============================================================


# ─────────────────────────────────────────────
# CELL 0：掛載 Google Drive
# ─────────────────────────────────────────────
from google.colab import drive
drive.mount('/content/drive')

import os
DB_DIR = '/content/drive/MyDrive/NBA_V341'
os.makedirs(DB_DIR, exist_ok=True)

# ✅ DEV/正式 使用不同資料庫，完全隔離
DB_PATH_PROD = os.path.join(DB_DIR, 'nba_strategy.db')      # 正式資料
DB_PATH_DEV  = os.path.join(DB_DIR, 'nba_strategy_DEV.db')  # 測試資料
DB_PATH = DB_PATH_PROD  # 預設，CELL 3 後會根據 DEV_MODE 自動切換

def _update_db_path():
    global DB_PATH
    DB_PATH = DB_PATH_DEV if DEV_MODE else DB_PATH_PROD
    mode = "🧪 測試模式" if DEV_MODE else "🏆 正式模式"
    print(f"📁 資料庫：{DB_PATH}  [{mode}]")
    # 自動建立資料表（新 DB 或切換後都安全）
    init_database(DB_PATH)

print(f"✅ Google Drive 掛載完成")
print(f"📁 DB 路徑將在 CELL 3 設定 DEV_MODE 後確認")


# ─────────────────────────────────────────────
# CELL 1：讀取 Secrets
# ─────────────────────────────────────────────
from google.colab import userdata

try:
    ODDS_API_KEY     = userdata.get('ODDS_API_KEY')
    TELEGRAM_TOKEN   = userdata.get('TELEGRAM_TOKEN')
    TELEGRAM_CHAT_ID = userdata.get('TELEGRAM_CHAT_ID')
    GEMINI_API_KEY   = userdata.get('GEMINI_API_KEY')
    print("✅ Secrets 讀取成功")
    print(f"   ODDS_API_KEY    : {'*'*8}{ODDS_API_KEY[-4:] if ODDS_API_KEY else '⚠️ 未設定'}")
    print(f"   TELEGRAM_TOKEN  : {'*'*8}{TELEGRAM_TOKEN[-4:] if TELEGRAM_TOKEN else '⚠️ 未設定'}")
    print(f"   TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else '⚠️ 未設定'}")
    print(f"   GEMINI_API_KEY  : {'*'*8}{GEMINI_API_KEY[-4:] if GEMINI_API_KEY else '⚠️ 未設定'}")
except Exception as e:
    print(f"⚠️  Secrets 讀取失敗：{e}")
    ODDS_API_KEY = TELEGRAM_TOKEN = TELEGRAM_CHAT_ID = GEMINI_API_KEY = None


# ─────────────────────────────────────────────
# CELL 2：安裝 & 載入套件
# ─────────────────────────────────────────────
# !pip install requests pytz --quiet

import sqlite3
import requests
import json
from datetime import datetime
from zoneinfo import ZoneInfo

print("✅ 套件載入完成")


# ─────────────────────────────────────────────
# CELL 3：全域設定（所有參數集中在這裡）
# ─────────────────────────────────────────────

# ⚠️ 最重要的開關：測試時 True，正式抓資料時才改 False
DEV_MODE = False

# 時區
TZ_EST = ZoneInfo("America/New_York")
TZ_TW  = ZoneInfo("Asia/Taipei")

def now_est():
    return datetime.now(TZ_EST)

def now_tw():
    return datetime.now(TZ_TW)

def ts():
    return now_est().strftime('%Y-%m-%d %H:%M:%S EST')

# 蒙地卡羅參數（版本鎖定）
SIGMA_NORMAL              = 12.0
SIGMA_COLLAPSE            = 15.0
COLLAPSE_PENALTY_MULT     = 1.2
COLLAPSE_THRESHOLD        = 2    # 幾名核心缺陣觸發崩潰

# Kelly 資金管理
KELLY_FRACTION  = 0.25   # 1/4 Kelly
MAX_BET_PCT     = 0.05   # 單場最大 5%

# 盤口異動警示門檻
LINE_MOVE_ALERT = 1.5    # 讓分移動超過 1.5 分就警示

print(f"{'='*50}")
print(f"🏀 NBA 戰情系統 V34.1 初始化")
print(f"{'='*50}")
_mode_str = '← 測試模式，不呼叫 API' if DEV_MODE else '← 正式模式'
print(f"⚙️  DEV_MODE     : {DEV_MODE}  {_mode_str}")
print(f"📐 σ 正常/崩潰  : {SIGMA_NORMAL} / {SIGMA_COLLAPSE}")
print(f"💰 Kelly        : 1/{int(1/KELLY_FRACTION)} Kelly，上限 {int(MAX_BET_PCT*100)}%")
print(f"⏰ 美東時間     : {ts()}")
print(f"⏰ 台灣時間     : {now_tw().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*50}")


# ─────────────────────────────────────────────
# CELL 4：建立資料庫與所有資料表
# ─────────────────────────────────────────────

# 球隊中文名稱對照表（供顯示用）
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

def tn(name: str) -> str:
    zh = TEAM_ZH.get(name, '')
    return f"{name}（{zh}）" if zh else name


def init_database(db_path: str):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 表1：預測記錄
    c.execute('''
    CREATE TABLE IF NOT EXISTS predictions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id             TEXT NOT NULL,
        game_date_est       TEXT NOT NULL,
        game_time_est       TEXT,
        home_team           TEXT NOT NULL,
        away_team           TEXT NOT NULL,
        open_line           REAL,
        live_line           REAL,
        total_line          REAL,
        home_odds           REAL,
        away_odds           REAL,
        ai_score_home       REAL,
        ai_score_away       REAL,
        ai_spread           REAL,
        ai_total            REAL,
        win_prob_home       REAL,
        win_prob_away       REAL,
        ev_value            REAL,
        recommended_bet     TEXT,
        confidence_level    TEXT,
        kelly_fraction      REAL,
        suggested_bet_pct   REAL,
        early_bet_signal    INTEGER DEFAULT 0,
        sigma_used          REAL,
        collapse_flag       INTEGER DEFAULT 0,
        collapse_team       TEXT,
        injury_snapshot     TEXT,
        pace_home           REAL,
        pace_away           REAL,
        mc_simulations      INTEGER DEFAULT 10000,
        model_params_json   TEXT,
        created_at_est      TEXT DEFAULT (datetime('now')),
        trigger_session     TEXT,
        win_pred_confidence TEXT
    )''')

    # 表2：比賽實際結果（對獎）
    c.execute('''
    CREATE TABLE IF NOT EXISTS results (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id             TEXT NOT NULL UNIQUE,
        game_date_est       TEXT NOT NULL,
        home_team           TEXT NOT NULL,
        away_team           TEXT NOT NULL,
        actual_score_home   INTEGER,
        actual_score_away   INTEGER,
        actual_spread       REAL,
        actual_total        INTEGER,
        actual_winner       TEXT,
        spread_result       TEXT,
        ou_result           TEXT,
        bet_hit             INTEGER,
        pnl                 REAL,
        data_source         TEXT DEFAULT 'api',
        fetched_at_est      TEXT DEFAULT (datetime('now')),
        is_final            INTEGER DEFAULT 0
    )''')

    # 表3：盤口快照（偵測晚上→早上異動）
    c.execute('''
    CREATE TABLE IF NOT EXISTS odds_snapshots (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id             TEXT NOT NULL,
        game_date_est       TEXT NOT NULL,
        home_team           TEXT NOT NULL,
        away_team           TEXT NOT NULL,
        spread_line         REAL,
        total_line          REAL,
        home_ml             REAL,
        away_ml             REAL,
        bookmaker           TEXT,
        snapshot_time_est   TEXT DEFAULT (datetime('now')),
        trigger             TEXT,
        is_locked           INTEGER DEFAULT 0
    )''')

    # 表4：API 使用次數記錄（保護 quota）
    c.execute('''
    CREATE TABLE IF NOT EXISTS api_usage_log (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        api_name            TEXT NOT NULL,
        endpoint            TEXT,
        request_time_est    TEXT DEFAULT (datetime('now')),
        response_status     INTEGER,
        remaining_quota     INTEGER,
        game_date_est       TEXT,
        notes               TEXT
    )''')

    # 表5：回測記錄（不同參數組合的命中率）
    c.execute('''
    CREATE TABLE IF NOT EXISTS backtest_runs (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        run_name            TEXT,
        date_range_start    TEXT,
        date_range_end      TEXT,
        total_games         INTEGER,
        games_bet           INTEGER,
        spread_hit_rate     REAL,
        ou_hit_rate         REAL,
        overall_hit_rate    REAL,
        roi                 REAL,
        params_json         TEXT,
        run_at_est          TEXT DEFAULT (datetime('now')),
        notes               TEXT
    )''')

    # 建立索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_pred_game_id ON predictions(game_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_pred_date    ON predictions(game_date_est)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_res_game_id  ON results(game_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_odds_game_id ON odds_snapshots(game_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_odds_date    ON odds_snapshots(game_date_est)')

    try:
        c.execute('ALTER TABLE predictions ADD COLUMN risk_tags TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute('ALTER TABLE predictions ADD COLUMN ot_prob REAL')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute('ALTER TABLE predictions ADD COLUMN win_pred_confidence TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute('ALTER TABLE predictions ADD COLUMN playoff_mode INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.commit()
    conn.close()

    print("✅ 資料庫建立完成")
    print("   📋 predictions    — 模型預測記錄")
    print("   📋 results        — 比賽實際結果（對獎）")
    print("   📋 odds_snapshots — 盤口快照（異動偵測）")
    print("   📋 api_usage_log  — API 使用次數保護")
    print("   📋 backtest_runs  — 回測參數命中率記錄")

init_database(DB_PATH)


# ─────────────────────────────────────────────
# CELL 5：數據盾牌 DataShield
# ─────────────────────────────────────────────

class DataShield:
    """
    所有外部 API 呼叫都必須通過這裡
    DEV_MODE=True  → 完全不發 HTTP，強制讀 DB
    DEV_MODE=False → 檢查快取，沒有才打 API
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _log(self, api_name, endpoint, status, remaining=None, game_date=None):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT INTO api_usage_log
            (api_name, endpoint, response_status, remaining_quota, game_date_est)
            VALUES (?, ?, ?, ?, ?)
        ''', (api_name, endpoint, status, remaining, game_date))
        conn.commit()
        conn.close()

    def get_usage_today(self, api_name: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        today = now_est().strftime('%Y-%m-%d')
        row = conn.execute('''
            SELECT COUNT(*), MIN(remaining_quota)
            FROM api_usage_log
            WHERE api_name=? AND date(request_time_est)=? AND response_status=200
        ''', (api_name, today)).fetchone()
        conn.close()
        return {'calls_today': row[0] or 0, 'remaining': row[1]}

    def has_snapshot(self, game_date_est: str, trigger: str) -> bool:
        """快取有效期 24 小時"""
        conn = sqlite3.connect(self.db_path)
        n = conn.execute('''
            SELECT COUNT(*) FROM odds_snapshots
            WHERE game_date_est=? AND trigger=?
            AND snapshot_time_est >= datetime('now', '-24 hours')
        ''', (game_date_est, trigger)).fetchone()[0]
        conn.close()
        return n > 0

    def read_cached_odds(self, game_date_est: str) -> list:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute('''
            SELECT game_id, home_team, away_team,
                   spread_line, total_line, home_ml, away_ml,
                   bookmaker, snapshot_time_est, trigger
            FROM odds_snapshots
            WHERE game_date_est=?
            ORDER BY snapshot_time_est DESC
        ''', (game_date_est,)).fetchall()
        conn.close()
        seen, result = set(), []
        for r in rows:
            if r[0] not in seen:
                seen.add(r[0])
                result.append({
                    'game_id': r[0], 'home_team': r[1], 'away_team': r[2],
                    'spread_line': r[3], 'total_line': r[4],
                    'home_ml': r[5], 'away_ml': r[6],
                    'bookmaker': r[7], 'snapshot_time': r[8], 'trigger': r[9]
                })
        return result

    def fetch_odds(self, game_date_est: str, trigger: str = 'manual') -> list:
        if DEV_MODE:
            print(f"🔒 DEV_MODE：讀取 {game_date_est} 盤口快取（不呼叫 API）")
            return self.read_cached_odds(game_date_est)

        if self.has_snapshot(game_date_est, trigger):
            print(f"✅ 快取命中：{game_date_est} {trigger}，直接讀 DB")
            return self.read_cached_odds(game_date_est)

        # 快取不存在才打 API
        usage = self.get_usage_today('odds_api')
        print(f"🌐 呼叫 The Odds API（今日已用 {usage['calls_today']} 次）...")

        if usage['remaining'] and usage['remaining'] < 50:
            print(f"⚠️  剩餘額度不足 50 次，請謹慎！")

        url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
        params = {
            'apiKey': ODDS_API_KEY,
            'regions': 'us',
            'markets': 'spreads,totals,h2h',
            'oddsFormat': 'american',
            'dateFormat': 'iso',
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            remaining = int(resp.headers.get('x-requests-remaining', -1))
            self._log('odds_api', '/v4/sports/basketball_nba/odds/',
                      resp.status_code, remaining, game_date_est)

            if resp.status_code != 200:
                print(f"❌ API 錯誤 {resp.status_code}：{resp.text[:200]}")
                return []

            print(f"✅ API 成功，剩餘額度：{remaining} 次")
            saved = self._save_odds(resp.json(), game_date_est, trigger)
            print(f"💾 存入 DB：{saved} 場")
            return self.read_cached_odds(game_date_est)

        except Exception as e:
            print(f"❌ 網路錯誤：{e}")
            return []

    def _save_odds(self, games: list, game_date_est: str, trigger: str) -> int:
        """
        只存指定日期的比賽，自動過濾其他日期
        避免 API 回傳多天比賽時混入 DB
        同一場比賽若已存在則跳過（防止重複）
        """
        from datetime import datetime
        from zoneinfo import ZoneInfo
        conn = sqlite3.connect(self.db_path)
        saved = skipped = filtered = 0

        for game in games:
            gid  = game.get('id')
            home = game.get('home_team')
            away = game.get('away_team')

            # ✅ 修正2a：從 API 回傳的 commence_time 判斷真實比賽日期
            commence = game.get('commence_time', '')
            try:
                dt_utc = datetime.fromisoformat(commence.replace('Z', '+00:00'))
                dt_est = dt_utc.astimezone(ZoneInfo('America/New_York'))
                real_date = dt_est.strftime('%Y-%m-%d')
            except:
                real_date = game_date_est

            # ✅ 修正2b：只存指定日期的比賽，其他日期跳過
            if real_date != game_date_est:
                filtered += 1
                continue

            # ✅ 修正2c：同一場比賽同一個 trigger 已存在則跳過
            existing = conn.execute('''
                SELECT COUNT(*) FROM odds_snapshots
                WHERE game_id=? AND trigger=?
                AND snapshot_time_est >= datetime('now', '-24 hours')
            ''', (gid, trigger)).fetchone()[0]
            if existing > 0:
                skipped += 1
                continue

            spread = total = home_ml = away_ml = None
            bk = None
            for bookmaker in game.get('bookmakers', []):
                bk = bookmaker.get('key')
                for mkt in bookmaker.get('markets', []):
                    if mkt['key'] == 'spreads':
                        for o in mkt['outcomes']:
                            if o['name'] == home:
                                spread = o.get('point')
                    elif mkt['key'] == 'totals':
                        for o in mkt['outcomes']:
                            if o['name'] == 'Over':
                                total = o.get('point')
                    elif mkt['key'] == 'h2h':
                        for o in mkt['outcomes']:
                            if o['name'] == home: home_ml = o.get('price')
                            elif o['name'] == away: away_ml = o.get('price')
                break  # 只取第一個 bookmaker

            conn.execute('''
                INSERT INTO odds_snapshots
                (game_id, game_date_est, home_team, away_team,
                 spread_line, total_line, home_ml, away_ml, bookmaker, trigger)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            ''', (gid, game_date_est, home, away,
                  spread, total, home_ml, away_ml, bk, trigger))
            saved += 1

        conn.commit()
        conn.close()
        if filtered > 0:
            print(f"   🗓️  過濾掉其他日期比賽：{filtered} 場")
        if skipped > 0:
            print(f"   ⏭️  跳過重複快照：{skipped} 場")
        return saved


shield = DataShield(DB_PATH)
_dev_str = 'ON（安全）' if DEV_MODE else 'OFF（正式）'
print(f"✅ DataShield 初始化完成 — DEV_MODE={_dev_str}")


# ─────────────────────────────────────────────
# CELL 6：盤口異動偵測
# ─────────────────────────────────────────────

def detect_line_moves(game_date_est: str) -> list:
    """比對 evening vs morning 盤口差異，有異動就警示"""
    conn = sqlite3.connect(DB_PATH)

    def get_snap(trigger):
        rows = conn.execute('''
            SELECT game_id, home_team, away_team, spread_line, total_line
            FROM odds_snapshots WHERE game_date_est=? AND trigger=?
        ''', (game_date_est, trigger)).fetchall()
        return {r[0]: {'home':r[1],'away':r[2],'spread':r[3],'total':r[4]} for r in rows}

    eve  = get_snap('evening_check')
    morn = get_snap('morning_check')
    conn.close()

    alerts = []
    for gid, e in eve.items():
        if gid not in morn:
            continue
        m = morn[gid]
        s_move = abs((m['spread'] or 0) - (e['spread'] or 0))
        t_move = abs((m['total']  or 0) - (e['total']  or 0))
        has_alert = s_move >= LINE_MOVE_ALERT or t_move >= 3.0
        alerts.append({
            'game_id': gid,
            'matchup': f"{e['away']} @ {e['home']}",
            'spread_eve': e['spread'], 'spread_morn': m['spread'], 'spread_move': s_move,
            'total_eve':  e['total'],  'total_morn':  m['total'],  'total_move':  t_move,
            'has_alert': has_alert
        })

    print(f"\n{'='*50}")
    print(f"📊 盤口異動報告 — {game_date_est}")
    print(f"{'='*50}")
    if not alerts:
        print("  （尚無比較資料，需先分別執行 evening + morning 抓取）")
    for a in alerts:
        icon = "⚠️ " if a['has_alert'] else "✅ "
        print(f"\n{icon}{a['matchup']}")
        print(f"   讓分：{a['spread_eve']} → {a['spread_morn']}  移動 {a['spread_move']:.1f}")
        print(f"   大小：{a['total_eve']}  → {a['total_morn']}   移動 {a['total_move']:.1f}")
        if a['has_alert']:
            print(f"   🔴 異動超過門檻，建議重新評估")

    return [a for a in alerts if a['has_alert']]


# ─────────────────────────────────────────────
# CELL 7：早下注信號評估
# ─────────────────────────────────────────────

def evaluate_early_bet(pred: dict, odds_stable: bool) -> dict:
    """
    判斷是否建議今晚直接下注（不等明早）
    全部條件都滿足才發出信號
    """
    EV_MIN = 0.15  # EV 至少 15%

    go, wait = [], []

    if pred.get('ev_value', 0) >= EV_MIN:
        go.append(f"EV {pred['ev_value']:.1%} ≥ {EV_MIN:.0%}")
    else:
        wait.append(f"EV {pred.get('ev_value',0):.1%} 低於門檻 {EV_MIN:.0%}")

    if odds_stable:
        go.append("盤口穩定無大異動")
    else:
        wait.append(f"盤口移動 ≥ {LINE_MOVE_ALERT} 分，觀望")

    if not pred.get('collapse_flag'):
        go.append("無體系崩潰風險")
    else:
        wait.append(f"⚠️ 崩潰模式：{pred.get('collapse_team','未知')}")

    if pred.get('confidence_level') == 'HIGH':
        go.append("信心等級 HIGH")
    else:
        wait.append(f"信心等級 {pred.get('confidence_level','?')}，建議觀望")

    early = len(wait) == 0
    return {
        'early_bet_signal': early,
        'go': go, 'wait': wait,
        'summary': '✅ 建議今晚直接下注' if early else '⏳ 建議等明早確認再行動'
    }


# ─────────────────────────────────────────────
# CELL 8：存取工具
# ─────────────────────────────────────────────

def save_prediction(pred: dict):
    # 防呆：確保新欄位有預設值，避免 You did not supply a value 給 binding parameter 的報錯
    pred.setdefault('ot_prob', 0.0)
    pred.setdefault('win_pred_confidence', 'LOW')
    pred.setdefault('risk_tags', '[]')
    pred.setdefault('playoff_mode', False)

    conn = sqlite3.connect(DB_PATH)

    # ── 防重複：同一場賽事同一天只保留最新一筆（覆蓋舊預測）──
    existing = conn.execute(
        'SELECT COUNT(*) FROM predictions WHERE game_id=? AND game_date_est=?',
        (pred.get('game_id'), pred.get('game_date_est'))
    ).fetchone()[0]
    if existing > 0:
        conn.execute(
            'DELETE FROM predictions WHERE game_id=? AND game_date_est=?',
            (pred.get('game_id'), pred.get('game_date_est'))
        )
        print(f"🔄 覆蓋舊預測：{pred.get('away_team')} @ {pred.get('home_team')} ({pred.get('game_date_est')})")

    conn.execute('''
        INSERT INTO predictions (
            game_id, game_date_est, game_time_est, home_team, away_team,
            open_line, live_line, total_line, home_odds, away_odds,
            ai_score_home, ai_score_away, ai_spread, ai_total,
            win_prob_home, win_prob_away, ev_value,
            recommended_bet, confidence_level,
            kelly_fraction, suggested_bet_pct, early_bet_signal,
            sigma_used, collapse_flag, collapse_team,
            injury_snapshot, pace_home, pace_away, mc_simulations,
            model_params_json, trigger_session, risk_tags, ot_prob,
            win_pred_confidence, playoff_mode
        ) VALUES (
            :game_id, :game_date_est, :game_time_est, :home_team, :away_team,
            :open_line, :live_line, :total_line, :home_odds, :away_odds,
            :ai_score_home, :ai_score_away, :ai_spread, :ai_total,
            :win_prob_home, :win_prob_away, :ev_value,
            :recommended_bet, :confidence_level,
            :kelly_fraction, :suggested_bet_pct, :early_bet_signal,
            :sigma_used, :collapse_flag, :collapse_team,
            :injury_snapshot, :pace_home, :pace_away, :mc_simulations,
            :model_params_json, :trigger_session, :risk_tags, :ot_prob,
            :win_pred_confidence, :playoff_mode
        )
    ''', pred)
    conn.commit()
    conn.close()
    print(f"💾 預測存入：{tn(pred.get('away_team',''))} @ {tn(pred.get('home_team',''))}")


def save_result(result: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT OR REPLACE INTO results (
            game_id, game_date_est, home_team, away_team,
            actual_score_home, actual_score_away, actual_spread,
            actual_total, actual_winner,
            spread_result, ou_result, bet_hit, pnl,
            data_source, is_final
        ) VALUES (
            :game_id, :game_date_est, :home_team, :away_team,
            :actual_score_home, :actual_score_away, :actual_spread,
            :actual_total, :actual_winner,
            :spread_result, :ou_result, :bet_hit, :pnl,
            :data_source, :is_final
        )
    ''', result)
    conn.commit()
    conn.close()
    print(f"✅ 結果存入：{tn(result.get('away_team',''))} @ {tn(result.get('home_team',''))} "
          f"({result.get('actual_score_away')}-{result.get('actual_score_home')})")


def get_hit_rate():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('''
        SELECT COUNT(*),
               SUM(CASE WHEN bet_hit=1 THEN 1 ELSE 0 END),
               SUM(CASE WHEN pnl IS NOT NULL THEN pnl ELSE 0 END)
        FROM results WHERE is_final=1
    ''').fetchone()
    conn.close()
    total, hits, pnl = row[0] or 0, row[1] or 0, row[2] or 0
    print(f"\n{'='*40}")
    print(f"📈 命中率統計")
    print(f"   總場次：{total}  命中：{hits}  命中率：{hits/total:.1%}" if total else "   尚無資料")
    print(f"   累積 PnL：{pnl:+.2f}%")
    print(f"{'='*40}")
    return {'total': total, 'hits': hits, 'hit_rate': hits/total if total else 0, 'pnl': pnl}


# ─────────────────────────────────────────────
# CELL 9：系統自檢
# ─────────────────────────────────────────────

def system_check():
    print(f"\n{'='*50}")
    print(f"🔍 系統自檢 — {ts()}")
    print(f"{'='*50}")

    # DB
    try:
        conn = sqlite3.connect(DB_PATH)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        pred_n  = conn.execute('SELECT COUNT(*) FROM predictions').fetchone()[0]
        result_n= conn.execute('SELECT COUNT(*) FROM results').fetchone()[0]
        odds_n  = conn.execute('SELECT COUNT(*) FROM odds_snapshots').fetchone()[0]
        conn.close()
        print(f"✅ DB 連線正常")
        print(f"   資料表：{tables}")
        print(f"   predictions:{pred_n}  results:{result_n}  odds_snapshots:{odds_n}")
    except Exception as e:
        print(f"❌ DB 錯誤：{e}")

    # API 使用量
    usage = shield.get_usage_today('odds_api')
    print(f"📊 The Odds API 今日：{usage['calls_today']} 次  剩餘：{usage['remaining'] or '未知'}")
    _dev_str2 = 'ON ← 安全測試中' if DEV_MODE else 'OFF ← 正式模式'
    print(f"⚙️  DEV_MODE：{_dev_str2}")
    _update_db_path()  # ✅ 根據 DEV_MODE 切換正確的 DB
    print(f"{'='*50}")
    print(f"✅ 系統自檢完成，V34.1 地基就緒！")

system_check()


# ─────────────────────────────────────────────
# CELL 10：DEV 測試 — 注入假資料驗證整個流程
# ─────────────────────────────────────────────

if DEV_MODE:
    print("\n🧪 DEV 測試：注入假資料驗證流程...")
    today_est = now_est().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_PATH)

    # 假盤口（evening）
    fake_games = [
        ('TEST_001', today_est, 'Boston Celtics',  'Miami Heat',         -6.5, 215.0, -280,  230),
        ('TEST_002', today_est, 'LA Lakers',        'Golden State Warriors', 4.5, 225.5,  160, -190),
        ('TEST_003', today_est, 'Denver Nuggets',   'Phoenix Suns',       -3.0, 220.0, -145,  125),
    ]
    for g in fake_games:
        conn.execute('''
            INSERT OR IGNORE INTO odds_snapshots
            (game_id, game_date_est, home_team, away_team,
             spread_line, total_line, home_ml, away_ml, bookmaker, trigger)
            VALUES (?,?,?,?,?,?,?,?,'test','evening_check')
        ''', g)

    # 假盤口（morning，TEST_001 有移動）
    fake_morning = [
        ('TEST_001', today_est, 'Boston Celtics',  'Miami Heat',         -8.0, 215.0, -310,  250),  # 讓分從-6.5移到-8.0
        ('TEST_002', today_est, 'LA Lakers',        'Golden State Warriors', 4.5, 225.5,  160, -190),
        ('TEST_003', today_est, 'Denver Nuggets',   'Phoenix Suns',       -3.0, 221.0, -145,  125),
    ]
    for g in fake_morning:
        conn.execute('''
            INSERT OR IGNORE INTO odds_snapshots
            (game_id, game_date_est, home_team, away_team,
             spread_line, total_line, home_ml, away_ml, bookmaker, trigger)
            VALUES (?,?,?,?,?,?,?,?,'test','morning_check')
        ''', g)
    conn.commit()
    conn.close()
    print(f"✅ 注入 {len(fake_games)} 場假盤口（evening + morning）")

    # 讀取快取
    cached = shield.fetch_odds(today_est, 'evening_check')
    print(f"✅ 快取讀取：{len(cached)} 場")
    for g in cached:
        print(f"   {g['away_team']} @ {g['home_team']}  讓分:{g['spread_line']}  大小:{g['total_line']}")

    # 盤口異動偵測
    detect_line_moves(today_est)

    # 假預測 + 早下注信號
    test_pred = {
        'game_id': 'TEST_001', 'game_date_est': today_est, 'game_time_est': '19:30',
        'home_team': 'Boston Celtics', 'away_team': 'Miami Heat',
        'open_line': -6.5, 'live_line': -6.5, 'total_line': 215.0,
        'home_odds': -280, 'away_odds': 230,
        'ai_score_home': 112.4, 'ai_score_away': 105.1,
        'ai_spread': 7.3, 'ai_total': 217.5,
        'win_prob_home': 0.714, 'win_prob_away': 0.286,
        'ev_value': 0.182, 'recommended_bet': 'HOME -6.5', 'confidence_level': 'HIGH',
        'kelly_fraction': 0.031, 'suggested_bet_pct': 0.031, 'early_bet_signal': 1,
        'sigma_used': SIGMA_NORMAL, 'collapse_flag': 0, 'collapse_team': None,
        'injury_snapshot': json.dumps({'home': [], 'away': ['Butler (knee - out)']}),
        'pace_home': 98.2, 'pace_away': 95.7, 'mc_simulations': 10000,
        'model_params_json': json.dumps({
            'sigma_normal': SIGMA_NORMAL, 'sigma_collapse': SIGMA_COLLAPSE,
            'kelly_fraction': KELLY_FRACTION, 'max_bet_pct': MAX_BET_PCT,
            'version': 'V34.1'
        }),
        'trigger_session': 'evening',
        'risk_tags': json.dumps(['✅ Clean game'])
    }
    save_prediction(test_pred)

    signal = evaluate_early_bet(test_pred, odds_stable=False)  # TEST_001 有盤口移動
    print(f"\n📡 早下注信號：{signal['summary']}")
    for r in signal['go']:   print(f"   ✅ {r}")
    for r in signal['wait']: print(f"   ⛔ {r}")

    system_check()
    print("\n🎉 DEV 測試全部通過！地基建設完成。")
    print("   下一步：蒙地卡羅引擎篇")
