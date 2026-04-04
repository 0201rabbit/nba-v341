# =============================================================
# 🏀 NBA 戰情系統 V34.1 — 蒙地卡羅引擎篇 v2（修正版）
# 修正項目：
#   1. 得分預測公式（80:80 → 正常分數）
#   2. 崩潰模式觸發門檻（questionable 也計入）
#   3. EV / 勝率異常連帶修正
# =============================================================
# ⚠️ 前置條件：地基篇 v2 已執行完畢
# =============================================================


# ─────────────────────────────────────────────
# CELL 11：安裝 & 載入套件
# ─────────────────────────────────────────────
# !pip install numpy scipy --quiet

import numpy as np
from scipy import stats as scipy_stats
import sqlite3, json
from datetime import datetime

print("✅ numpy / scipy 載入完成")


# ─────────────────────────────────────────────
# 球隊中文名稱對照表
# ─────────────────────────────────────────────
TEAM_ZH = {
    "Atlanta Hawks":          "老鷹",
    "Boston Celtics":         "塞爾提克",
    "Brooklyn Nets":          "籃網",
    "Charlotte Hornets":      "黃蜂",
    "Chicago Bulls":          "公牛",
    "Cleveland Cavaliers":    "騎士",
    "Dallas Mavericks":       "獨行俠",
    "Denver Nuggets":         "金塊",
    "Detroit Pistons":        "活塞",
    "Golden State Warriors":  "勇士",
    "Houston Rockets":        "火箭",
    "Indiana Pacers":         "溜馬",
    "LA Clippers":            "快艇",
    "LA Lakers":              "湖人",
    "Los Angeles Clippers":   "快艇",
    "Los Angeles Lakers":     "湖人",
    "Memphis Grizzlies":      "灰熊",
    "Miami Heat":             "熱火",
    "Milwaukee Bucks":        "公鹿",
    "Minnesota Timberwolves": "灰狼",
    "New Orleans Pelicans":   "鵜鶘",
    "New York Knicks":        "尼克",
    "Oklahoma City Thunder":  "雷霆",
    "Orlando Magic":          "魔術",
    "Philadelphia 76ers":     "76人",
    "Phoenix Suns":           "太陽",
    "Portland Trail Blazers": "拓荒者",
    "Sacramento Kings":       "國王",
    "San Antonio Spurs":      "馬刺",
    "Toronto Raptors":        "暴龍",
    "Utah Jazz":              "爵士",
    "Washington Wizards":     "巫師",
}

def tn(name: str) -> str:
    """回傳「英文（中文）」格式"""
    zh = TEAM_ZH.get(name, '')
    return f"{name}（{zh}）" if zh else name


# ─────────────────────────────────────────────
# CELL 12：球隊基礎數據（靜態，每 1-2 週手動更新）
# ─────────────────────────────────────────────
TEAM_STATS = {
    # 數據來源：Basketball-Reference 2025-26（截至 2026/04/02）
    # 東區
    "Atlanta Hawks":          {"off_rtg": 115.8, "def_rtg": 113.9, "pace": 101.6, "home_adv": 2.8},
    "Boston Celtics":         {"off_rtg": 120.0, "def_rtg": 112.6, "pace":  94.7, "home_adv": 3.5},
    "Brooklyn Nets":          {"off_rtg": 109.0, "def_rtg": 118.7, "pace":  96.9, "home_adv": 1.8},
    "Charlotte Hornets":      {"off_rtg": 119.2, "def_rtg": 114.4, "pace":  97.0, "home_adv": 2.5},
    "Chicago Bulls":          {"off_rtg": 113.3, "def_rtg": 117.9, "pace": 102.2, "home_adv": 2.3},
    "Cleveland Cavaliers":    {"off_rtg": 119.0, "def_rtg": 115.0, "pace":  99.9, "home_adv": 3.2},
    "Detroit Pistons":        {"off_rtg": 117.5, "def_rtg": 109.6, "pace":  99.3, "home_adv": 3.5},
    "Indiana Pacers":         {"off_rtg": 110.8, "def_rtg": 119.1, "pace": 100.9, "home_adv": 2.2},
    "Miami Heat":             {"off_rtg": 115.9, "def_rtg": 113.6, "pace": 103.6, "home_adv": 3.0},
    "Milwaukee Bucks":        {"off_rtg": 112.6, "def_rtg": 118.8, "pace":  97.8, "home_adv": 2.5},
    "New York Knicks":        {"off_rtg": 119.5, "def_rtg": 113.3, "pace":  97.1, "home_adv": 3.8},
    "Orlando Magic":          {"off_rtg": 115.0, "def_rtg": 114.7, "pace":  99.5, "home_adv": 2.8},
    "Philadelphia 76ers":     {"off_rtg": 115.5, "def_rtg": 115.9, "pace":  99.4, "home_adv": 2.5},
    "Toronto Raptors":        {"off_rtg": 115.4, "def_rtg": 113.2, "pace":  98.5, "home_adv": 2.2},
    "Washington Wizards":     {"off_rtg": 110.8, "def_rtg": 122.0, "pace": 101.1, "home_adv": 1.5},
    # 西區
    "Dallas Mavericks":       {"off_rtg": 110.5, "def_rtg": 116.0, "pace": 101.6, "home_adv": 2.5},
    "Denver Nuggets":         {"off_rtg": 122.0, "def_rtg": 117.3, "pace":  98.3, "home_adv": 3.8},
    "Golden State Warriors":  {"off_rtg": 114.9, "def_rtg": 114.9, "pace":  99.3, "home_adv": 2.8},
    "Houston Rockets":        {"off_rtg": 117.8, "def_rtg": 113.2, "pace":  95.9, "home_adv": 2.8},
    "LA Clippers":            {"off_rtg": 117.5, "def_rtg": 116.1, "pace":  96.4, "home_adv": 2.5},
    "LA Lakers":              {"off_rtg": 118.5, "def_rtg": 116.4, "pace":  98.4, "home_adv": 2.8},
    "Los Angeles Clippers":   {"off_rtg": 117.5, "def_rtg": 116.1, "pace":  96.4, "home_adv": 2.5},
    "Los Angeles Lakers":     {"off_rtg": 118.5, "def_rtg": 116.4, "pace":  98.4, "home_adv": 2.8},
    "Memphis Grizzlies":      {"off_rtg": 113.3, "def_rtg": 117.6, "pace": 101.2, "home_adv": 2.5},
    "Minnesota Timberwolves": {"off_rtg": 116.7, "def_rtg": 112.9, "pace": 100.5, "home_adv": 3.0},
    "New Orleans Pelicans":   {"off_rtg": 114.4, "def_rtg": 118.7, "pace":  99.9, "home_adv": 2.3},
    "Oklahoma City Thunder":  {"off_rtg": 118.4, "def_rtg": 107.5, "pace":  99.2, "home_adv": 3.5},
    "Phoenix Suns":           {"off_rtg": 115.6, "def_rtg": 113.8, "pace":  97.2, "home_adv": 2.5},
    "Portland Trail Blazers": {"off_rtg": 114.1, "def_rtg": 114.8, "pace": 100.8, "home_adv": 2.2},
    "Sacramento Kings":       {"off_rtg": 111.0, "def_rtg": 121.4, "pace":  99.3, "home_adv": 2.5},
    "San Antonio Spurs":      {"off_rtg": 119.2, "def_rtg": 111.0, "pace": 100.1, "home_adv": 3.2},
    "Utah Jazz":              {"off_rtg": 114.3, "def_rtg": 122.2, "pace": 101.8, "home_adv": 2.0},
}


# 聯盟平均（找不到球隊時使用）
LEAGUE_AVG = {"off_rtg": 114.0, "def_rtg": 114.0, "pace": 98.5, "home_adv": 2.5}

print(f"✅ 球隊基礎數據載入完成：{len(TEAM_STATS)} 支球隊")


# ─────────────────────────────────────────────
# CELL 13：傷兵影響評估
# ─────────────────────────────────────────────

INJURY_IMPACT = {
    "superstar": {"off": -6.0, "def": +4.0, "core": True},   # ✅ 計入崩潰
    "allstar":   {"off": -4.0, "def": +2.5, "core": True},   # ✅ 計入崩潰
    "starter":   {"off": -2.5, "def": +1.5, "core": False},  # 🔧 修正：不計入崩潰
    "rotation":  {"off": -1.2, "def": +0.8, "core": False},
    "bench":     {"off": -0.5, "def": +0.3, "core": False},
}

STATUS_MULTIPLIER = {
    "out":          1.0,
    "doubtful":     0.8,
    "questionable": 0.4,
    "gtd":          0.3,
    "probable":     0.1,
    "available":    0.0,
}

# ✅ 修正：核心缺陣門檻降為 0.4（questionable 以上都算進去）
CORE_MISSING_MIN_MULTIPLIER = 0.4

# 邊際遞減係數（第1名全扣，第2名扣80%，第3名扣50%，第4名以後扣20%）
MARGINAL_DECAY = [1.0, 0.8, 0.5, 0.2]

# 《改進 1》：球員 USG%（使用率）表—— 2025-26賽季
# USG% = 該球員上場時占用隊伍进攻回合的比例
# 依據 USG% 發尚罱居影響值的倍率（高 USG = 高影響）
PLAYER_USG = {
    # 超級星 (USG > 30%)
    "LeBron James":         30.2, "Giannis Antetokounmpo": 33.1,
    "Luka Doncic":          35.2, "Kevin Durant":           29.2,
    "Stephen Curry":        27.8, "Nikola Jokic":           29.0,
    "Joel Embiid":          33.5, "Jayson Tatum":           30.8,
    "Damian Lillard":       28.6, "Zion Williamson":        32.0,
    "Anthony Davis":        27.5, "Devin Booker":           30.2,
    "Donovan Mitchell":     30.0, "Shai Gilgeous-Alexander": 33.2,
    "Karl-Anthony Towns":   27.8, "Trae Young":             31.5,
    "James Harden":         26.5, "Jimmy Butler":           24.5,
    # 全明星 (USG 22-30%)
    "Jaylen Brown":         26.5, "Bam Adebayo":            22.0,
    "Tyrese Haliburton":    27.5, "Tyler Herro":            27.0,
    "Pascal Siakam":        24.5, "Darius Garland":         25.2,
    "Evan Mobley":          20.5, "Scottie Barnes":         24.8,
    "Paolo Banchero":       28.5, "Franz Wagner":           26.0,
    "Cade Cunningham":      28.5, "Jalen Brunson":          28.0,
    "OG Anunoby":           19.5, "De'Aaron Fox":           26.5,
    "Domantas Sabonis":     24.0, "Jalen Green":            27.5,
    "Anthony Edwards":      30.5, "Rudy Gobert":            17.5,
    "Lauri Markkanen":      24.5, "Victor Wembanyama":       29.5,
    "Brandon Ingram":       26.0, "CJ McCollum":            23.5,
    "Julius Randle":        25.5, "Jaren Jackson Jr":       21.5,
    "Ja Morant":            27.5, "Desmond Bane":           22.0,
    "Mikal Bridges":        21.5, "Khris Middleton":        23.0,
    "Kyrie Irving":         26.5, "Paul George":            23.5,
    "Norman Powell":        23.0, "Bradley Beal":           24.5,
    # 先發 (USG 18-22%)
    "Bogdan Bogdanovic":    20.5, "Tobias Harris":          20.0,
    "Brook Lopez":          18.5, "Robert Williams":        15.0,
    "Kristaps Porzingis":   22.0, "Al Horford":             15.5,
    "Marcus Smart":         17.5, "Jrue Holiday":           15.5,
}

# 依 USG% 計算影響倍率：USG=20%為基準(1.0)，每多 5% 加 25% 影響
def usg_multiplier(usg: float) -> float:
    return max(0.6, min(2.0, 1.0 + (usg - 20.0) / 20.0))

# 《改進 2》：背靠背（B2B）疲勞懲调
# NBA 研究：B2B 的區或需讓 on avg 覗 1–2分錢
B2B_HOME_OFF  = -2.0   # 主隊 B2B 時進攻效率下調
B2B_HOME_DEF  = +1.5   # 主隊 B2B 時防守效率下調
B2B_AWAY_OFF  = -3.0   # 客隊 B2B 的擁個更難（還要移動）
B2B_AWAY_DEF  = +2.0

def parse_injuries(injury_list: list) -> dict:
    """
    還际遞減版傷兵計算（加入 USG% 校正）
    """
    if not injury_list:
        return {'off_impact': 0, 'def_impact': 0, 'core_missing': 0,
                'too_many_injuries': False, 'injury_count': 0}

    raw_impacts = []
    for p in injury_list:
        role       = p.get('role', 'rotation')
        status     = p.get('status', 'out').lower()
        name       = p.get('name', '?')
        impact     = INJURY_IMPACT.get(role, INJURY_IMPACT['rotation'])
        multiplier = STATUS_MULTIPLIER.get(status, 1.0)

        # USG% 加權：依球員發尚罱居動正影響大小
        usg = PLAYER_USG.get(name)
        usg_mult = usg_multiplier(usg) if usg else 1.0

        raw_off = impact['off'] * multiplier * usg_mult
        raw_def = impact['def'] * multiplier * usg_mult
        is_core = impact['core'] and multiplier >= CORE_MISSING_MIN_MULTIPLIER
        raw_impacts.append({
            'name': name, 'role': role, 'status': status,
            'raw_off': raw_off, 'raw_def': raw_def,
            'severity': abs(raw_off),
            'is_core': is_core,
            'usg': usg
        })

    raw_impacts.sort(key=lambda x: x['severity'], reverse=True)

    total_off = total_def = 0.0
    core_missing = 0

    for i, p in enumerate(raw_impacts):
        decay = MARGINAL_DECAY[i] if i < len(MARGINAL_DECAY) else MARGINAL_DECAY[-1]
        off_hit = p['raw_off'] * decay
        def_hit = p['raw_def'] * decay
        total_off += off_hit
        total_def += def_hit
        if p['is_core']:
            core_missing += 1
        usg_tag = f" USG={p['usg']:.0f}%" if p['usg'] else ""
        decay_str = f"{int(decay*100)}%"
        print(f"   🏥 {p['name']} ({p['role']}/{p['status']}{usg_tag})"
              f"  進攻:{off_hit:+.1f}  防守:{def_hit:+.1f}"
              f"  [遞減{decay_str}]"
              f"{'  ⚠️核心' if p['is_core'] else ''}")

    too_many = len(injury_list) >= 4
    if too_many:
        print(f"   ⚠️  傷兵人數過多（{len(injury_list)}人），預測可信度下降")

    return {'off_impact': total_off, 'def_impact': total_def,
            'core_missing': core_missing,
            'too_many_injuries': too_many,
            'injury_count': len(injury_list)}

print("✅ 傷兵評估模組就緒")
print(f"   核心缺陣門檻：status multiplier ≥ {CORE_MISSING_MIN_MULTIPLIER}（含 questionable）")


# ─────────────────────────────────────────────
# CELL 14：蒙地卡羅模擬引擎（修正得分公式）
# ─────────────────────────────────────────────

def run_monte_carlo(
    home_team: str,
    away_team: str,
    home_injuries: list = None,
    away_injuries: list = None,
    n_simulations: int = 10000,
    custom_params: dict = None,
    verbose: bool = True,
    spread_line: float = None,
    b2b_home: bool = False,        # 主隊是否背靠背
    b2b_away: bool = False,        # 客隊是否背靠背
    rest_days_home: int = 1,       # 主隊距上次出賽天數（1=正常，3+=長休）
    rest_days_away: int = 1,       # 客隊距上次出賽天數
) -> dict:
    """
    ✅ 修正版得分公式：
    NBA 平均每隊得分 ≈ (off_rtg / 100) * (pace / 2)
    off_rtg=114, pace=98.5 → 114/100 * 49.25 ≈ 56.1... 不對

    正確公式：
    每隊得分 ≈ (自身 off_rtg + 對手 def_rtg 的補數) / 2
              × pace（兩隊平均）/ 100 × 48分鐘係數

    更簡單的業界做法：
    用 off_rtg 和 def_rtg 直接估算每 100 possessions 得分
    實際 possessions ≈ pace * 0.5（每隊）
    得分 = (off_rtg * 0.5 + (200 - def_rtg) * 0.5) / 2 * pace / 100
    → 約等於 (off_rtg + 200 - def_rtg) / 4 * pace / 100

    驗證：BOS off=122, MIA def=112, pace=97.9
    → (122 + 200 - 112) / 4 * 97.9 / 100 = 210/4 * 0.979 = 52.5 * 0.979 ≈ 51.4
    還是偏低...

    最終採用業界標準做法：
    每隊得分 = (自身 off_rtg * 對手 def_rtg) / LEAGUE_DEF_AVG * pace / 100
    LEAGUE_DEF_AVG = 114.0（聯盟平均防守效率）
    驗證：BOS: 122.1 * 112.1 / 114 * 97.9 / 100
        = 13691.5 / 114 * 0.979
        = 120.1 * 0.979 ≈ 117.5  ✅ 合理！
    """
    home_injuries = home_injuries or []
    away_injuries = away_injuries or []

    home_stats = TEAM_STATS.get(home_team, LEAGUE_AVG)
    away_stats = TEAM_STATS.get(away_team, LEAGUE_AVG)

    if home_team not in TEAM_STATS and verbose:
        print(f"   ⚠️  {home_team} 不在資料庫，使用聯盟平均")
    if away_team not in TEAM_STATS and verbose:
        print(f"   ⚠️  {away_team} 不在資料庫，使用聯盟平均")

    # 解析傷兵
    if verbose: print(f"\n  📋 {tn(home_team)} 傷兵：")
    home_inj = parse_injuries(home_injuries) if home_injuries else {'off_impact':0,'def_impact':0,'core_missing':0}
    if verbose: print(f"  📋 {tn(away_team)} 傷兵：")
    away_inj = parse_injuries(away_injuries) if away_injuries else {'off_impact':0,'def_impact':0,'core_missing':0}

    # 崩潰判斷
    sigma = custom_params.get('sigma_normal', SIGMA_NORMAL) if custom_params else SIGMA_NORMAL
    collapse_flag = False
    collapse_team = None

    if home_inj['core_missing'] >= COLLAPSE_THRESHOLD:
        collapse_flag = True
        collapse_team = home_team
        sigma = custom_params.get('sigma_collapse', SIGMA_COLLAPSE) if custom_params else SIGMA_COLLAPSE
        home_inj['off_impact'] *= COLLAPSE_PENALTY_MULT
        home_inj['def_impact'] *= COLLAPSE_PENALTY_MULT
        if verbose: print(f"\n  💥 崩潰模式！{tn(home_team)} 核心缺陣 {home_inj['core_missing']} 人 → σ={sigma}")

    if away_inj['core_missing'] >= COLLAPSE_THRESHOLD:
        collapse_flag = True
        collapse_team = (collapse_team + ' & ' + away_team) if collapse_team else away_team
        sigma = custom_params.get('sigma_collapse', SIGMA_COLLAPSE) if custom_params else SIGMA_COLLAPSE
        away_inj['off_impact'] *= COLLAPSE_PENALTY_MULT
        away_inj['def_impact'] *= COLLAPSE_PENALTY_MULT
        if verbose: print(f"\n  💥 崩潰模式！{tn(away_team)} 核心缺陣 {away_inj['core_missing']} 人 → σ={sigma}")

    # ✅ 修正後的得分公式
    # 請勿調高 LEAGUE_DEF_AVG：分母增大會讓預測得分變低，与我們的+6賽季校正相逆
    LEAGUE_DEF_AVG = 114.0
    # 季未動機：確定 tanking 或保休的隊伍進攻效率打折
    TANKING_TEAMS = {
        'Washington Wizards', 'Utah Jazz', 'Brooklyn Nets',
        'Portland Trail Blazers', 'New Orleans Pelicans',
    }
    TANKING_OFF_PENALTY = -2.0   # 確定 tanking 的隊伍進攻效率下調
    # 長休最（rest≥3天）的加成
    REST_BONUS_OFF = +1.5
    REST_BONUS_DEF = -1.0       # 防守允許率下降代表防守變好
    pace_used = (home_stats['pace'] + away_stats['pace']) / 2

    # 加入傷兵影響後的效率值
    home_off_adj = home_stats['off_rtg'] + home_inj['off_impact'] + home_stats['home_adv']
    home_def_adj = home_stats['def_rtg'] + home_inj['def_impact']
    away_off_adj = away_stats['off_rtg'] + away_inj['off_impact']
    away_def_adj = away_stats['def_rtg'] + away_inj['def_impact']

    # 《改進》: 背靠背疲勞懲調整
    if b2b_home:
        home_off_adj += B2B_HOME_OFF
        home_def_adj += B2B_HOME_DEF
        if verbose:
            print(f"   😴 {tn(home_team)} 背靠背：進攻{B2B_HOME_OFF:+.1f}  防守允許率{B2B_HOME_DEF:+.1f}")
    if b2b_away:
        away_off_adj += B2B_AWAY_OFF
        away_def_adj += B2B_AWAY_DEF
        if verbose:
            print(f"   😴 {tn(away_team)} 背靠背(客隊更難)：進攻{B2B_AWAY_OFF:+.1f}  防守允許率{B2B_AWAY_DEF:+.1f}")

    # 《改進》: 長休加成（3天+休息）
    if rest_days_home >= 3:
        home_off_adj += REST_BONUS_OFF
        home_def_adj += REST_BONUS_DEF
        if verbose:
            print(f"   💪 {tn(home_team)} 長休{rest_days_home}天：進攻{REST_BONUS_OFF:+.1f}  防守{REST_BONUS_DEF:+.1f}")
    if rest_days_away >= 3:
        away_off_adj += REST_BONUS_OFF
        away_def_adj += REST_BONUS_DEF
        if verbose:
            print(f"   💪 {tn(away_team)} 長休{rest_days_away}天：進攻{REST_BONUS_OFF:+.1f}  防守{REST_BONUS_DEF:+.1f}")

    # 《改進》: 季未 tanking 懲调
    if home_team in TANKING_TEAMS:
        home_off_adj += TANKING_OFF_PENALTY
        if verbose:
            print(f"   📩 {tn(home_team)} 確認 tanking 中：進攻{TANKING_OFF_PENALTY:+.1f}")
    if away_team in TANKING_TEAMS:
        away_off_adj += TANKING_OFF_PENALTY
        if verbose:
            print(f"   📩 {tn(away_team)} 確認 tanking 中：進攻{TANKING_OFF_PENALTY:+.1f}")

    # 預測得分（業界標準公式）
    # 主隊得分 = 主隊進攻效率 × 客隊防守允許率 / 聯盟均 × pace調整
    pred_home_base = (home_off_adj * away_def_adj) / LEAGUE_DEF_AVG * pace_used / 100
    pred_away_base = (away_off_adj * home_def_adj) / LEAGUE_DEF_AVG * pace_used / 100

    # ✅ 盤口錨定：將模型預測分差往市場盤口方向修正
    # 市場盤口是千萬資金定出來的，不能完全忽略
    # MARKET_WEIGHT=0.45：命中率低於50%，更信任市場盤口（由龐大資金定出）
    MARKET_WEIGHT = 0.45

    if spread_line is not None:
        model_spread   = pred_home_base - pred_away_base
        market_spread  = -spread_line  # 盤口讓分轉換（-6.5 代表主隊讓 6.5，即預期主贏 6.5）
        blended_spread = model_spread * (1 - MARKET_WEIGHT) + market_spread * MARKET_WEIGHT
        adjustment     = blended_spread - model_spread
        pred_home_base += adjustment / 2
        pred_away_base -= adjustment / 2
        if verbose:
            print(f"\n  📐 盤口錨定：模型分差 {model_spread:+.1f} → 錨定後 {blended_spread:+.1f}"
                  f"（盤口 {market_spread:+.1f} 佔 {int(MARKET_WEIGHT*100)}%）")

    # 蒙地卡羅模擬
    rng = np.random.default_rng(42)
    home_sims = rng.normal(pred_home_base, sigma, n_simulations)
    away_sims = rng.normal(pred_away_base, sigma, n_simulations)

    # 得分下限 80 分
    home_sims = np.maximum(home_sims, 80)
    away_sims = np.maximum(away_sims, 80)

    spread_sims = home_sims - away_sims

    win_prob_home = float(np.mean(home_sims > away_sims))
    win_prob_away = 1.0 - win_prob_home

    # ━━ OT 機率計算（三層模型） ━━
    # 層 1：基礎層 — P(|分差| ≤ 3) 直接從 MC 分布讀取
    ot_base_prob = float(np.mean(np.abs(spread_sims) <= 3.0))

    # 層 2：結構層 — Pace 係數
    if pace_used < 99:
        pace_coeff = 1.30   # 慢節奏 → 容易打平
    elif pace_used > 101:
        pace_coeff = 0.70   # 快節奏 → 分差波動大
    else:
        pace_coeff = 1.00

    # 層 3：行為層 — 球星終結能力係數
    # 強終結球串（容易絕殺不進 OT）的球隊
    CLUTCH_CLOSERS = {
        'Dallas Mavericks', 'Golden State Warriors',
        'Miami Heat', 'Denver Nuggets', 'Boston Celtics',
        'Milwaukee Bucks', 'Cleveland Cavaliers',
    }
    # 亂戰型 / 無球星終結 → OT 機率小幅升
    CHAOS_TEAMS = {
        'Washington Wizards', 'Detroit Pistons',
        'Charlotte Hornets', 'Portland Trail Blazers',
        'Memphis Grizzlies',
    }
    is_clutch = (home_team in CLUTCH_CLOSERS) or (away_team in CLUTCH_CLOSERS)
    is_chaos  = (home_team in CHAOS_TEAMS) or (away_team in CHAOS_TEAMS)
    behavior_coeff = 0.85 if is_clutch else (1.10 if is_chaos else 1.00)

    ot_prob = min(ot_base_prob * pace_coeff * behavior_coeff, 0.25)  # 上限 25%
    ot_risk_score = round(ot_prob * 100, 1)  # 0~100 分
    if ot_prob < 0.03:
        ot_risk_level = '✅ 安全盤'
    elif ot_prob < 0.06:
        ot_risk_level = '🟡 正常'
    else:
        ot_risk_level = '⚠️ 膠著盤'

    return {
        'home_team':         home_team,
        'away_team':         away_team,
        'pred_home':         round(float(np.mean(home_sims)), 1),
        'pred_away':         round(float(np.mean(away_sims)), 1),
        'pred_spread':       round(float(np.mean(spread_sims)), 1),
        'pred_total':        round(float(np.mean(home_sims + away_sims)) + 6.0, 1),  # 季末校正：實際比預測最多低 5.9 分
        'win_prob_home':     round(win_prob_home, 4),
        'win_prob_away':     round(win_prob_away, 4),
        'sigma_used':        sigma,
        'collapse_flag':     collapse_flag,
        'collapse_team':     collapse_team,
        'inj_impact_home':   abs(home_inj['off_impact'] + home_inj['def_impact']),
        'inj_impact_away':   abs(away_inj['off_impact'] + away_inj['def_impact']),
        'core_missing_home': home_inj['core_missing'],
        'core_missing_away': away_inj['core_missing'],
        'sim_spread_std':    round(float(np.std(spread_sims)), 2),
        'n_simulations':     n_simulations,
        'pace_used':         round(pace_used, 1),
        'pred_home_base':    round(pred_home_base, 1),
        'pred_away_base':    round(pred_away_base, 1),
        'too_many_injuries': home_inj.get('too_many_injuries', False) or away_inj.get('too_many_injuries', False),
        'ot_prob':           round(ot_prob, 4),
        'ot_risk_score':     ot_risk_score,
        'ot_risk_level':     ot_risk_level,
    }

print("✅ 蒙地卡羅引擎就緒（修正版）")


# ─────────────────────────────────────────────
# CELL 15：EV 計算 + Kelly
# ─────────────────────────────────────────────

def american_to_decimal(odds: float) -> float:
    return (odds / 100 + 1) if odds > 0 else (100 / abs(odds) + 1)

def american_to_prob(odds: float) -> float:
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)

def calc_ev(win_prob: float, odds: float) -> float:
    dec = american_to_decimal(odds)
    return round(win_prob * (dec - 1) - (1 - win_prob), 4)

def calc_kelly(win_prob: float, odds: float) -> float:
    b = american_to_decimal(odds) - 1
    if b <= 0: return 0.0
    full_k = (b * win_prob - (1 - win_prob)) / b
    return round(min(max(full_k * KELLY_FRACTION, 0), MAX_BET_PCT), 4)

# ══════════════════════════════════════════════════════
# EV 計算參數（可調整）
# ══════════════════════════════════════════════════════
EV_MAX            = 0.15   # EV 上限 15%
ML_MAX_DIFF       = 0.20   # 獨贏：模型勝率 vs 市場限制 20%
ML_MAX_ODDS       = 600    # 獨贏：賠率 > +600 不推薦
SPREAD_WIN_MAX    = 0.85   # 讓分：勝率 > 85% 不推薦
HIGH_CONF_EV      = 0.10   # HIGH 最低 EV
HIGH_CONF_PROB    = 0.65   # HIGH 最低勝率（提高：-8.43% PnL 代表需更嚴格賠規）
TOO_MANY_INJ_CONF = 'MED'  # 傷兵過多時最高只能 MED

# 管 EV 校準係數
# 實際 PnL=-8.43%→實際命中率≈8%，模型預期 62%，需大幅萎縮
PROB_SHRINK  = 0.65   # 勝率向 50% 萎縮 35%（之前 0.80 不夠）
MIN_OVER_EV  = 0.10   # OVER 最低 EV 門檻（命中率只 47.4%，需進一步篩選）
MIN_UNDER_EV = 0.35   # UNDER 最低 EV 門檻（命中率只 22.2%，更嚴格限制）

def evaluate_bet(mc: dict, spread_line: float, total_line: float,
                 home_ml: float = None, away_ml: float = None) -> dict:
    """
    計算最佳下注方向、EV、Kelly
    包含六項合理性過濾：
    1. 獨贏賠率差距過大 → 跳過
    2. 獨贏賠率超過 +600 → 跳過
    3. EV 超過上限 50% → 截斷
    4. 讓分勝率超過 85% → 跳過（模型偏差過大）
    5. 信心等級更嚴格
    6. 傷兵過多時降低信心等級
    """
    candidates = []
    
    # 傷兵與混亂度動態放大標準差 (Dynamic Sigma)
    impact_home = mc.get('inj_impact_home', 0)
    impact_away = mc.get('inj_impact_away', 0)
    impact_score = min((impact_home + impact_away) / 10.0, 0.30)
    if mc.get('collapse_flag'):
        impact_score = max(impact_score, 0.25)
        
    dynamic_sigma = mc['sigma_used'] * (1 + impact_score)
    cover_sigma = dynamic_sigma * np.sqrt(2)
    total_std   = dynamic_sigma * np.sqrt(2)

    # ── 讓分 ──
    if spread_line is not None:
        target_margin = -spread_line
        edge_gap = abs(mc['pred_spread'] - target_margin)
        
        if edge_gap <= 10.0:
            prob_home_cover = float(1 - scipy_stats.norm.cdf(
                target_margin, loc=mc['pred_spread'], scale=cover_sigma))
            prob_away_cover = 1 - prob_home_cover
            
            for direction, prob, desc in [
                ('HOME', prob_home_cover, f"{mc['home_team']} {spread_line:+.1f}"),
                ('AWAY', prob_away_cover, f"{mc['away_team']} {-spread_line:+.1f}"),
            ]:
                if prob > SPREAD_WIN_MAX:
                    continue
                # 📊 勝率校準：向 50% 萎縮，修正系統性高估
                prob_cal = 0.5 + (prob - 0.5) * PROB_SHRINK
                ev = min(calc_ev(prob_cal, -110), EV_MAX)
                
                # Margin Check：若預測分差連盤口的 60% 都沒到，大幅砍 EV
                if direction == 'HOME' and mc['pred_spread'] < abs(target_margin) * 0.6:
                    ev *= 0.3
                elif direction == 'AWAY' and -mc['pred_spread'] < abs(target_margin) * 0.6:
                    ev *= 0.3
                    
                if ev > 0:
                    candidates.append({
                        'bet_type': 'SPREAD', 'direction': direction,
                        'description': desc, 'win_prob': round(prob_cal, 4),
                        'ev': round(ev, 4), 'kelly': calc_kelly(prob_cal, -110), 'odds': -110
                    })

    # ── 大小分 ──
    if total_line is not None:
        prob_over  = float(1 - scipy_stats.norm.cdf(
            total_line, loc=mc['pred_total'], scale=total_std))
        prob_under = 1 - prob_over
        for direction, prob, desc in [
            ('OVER',  prob_over,  f"OVER {total_line}"),
            ('UNDER', prob_under, f"UNDER {total_line}"),
        ]:
            if prob > SPREAD_WIN_MAX:
                continue
            # 📊 勝率校準
            prob_cal = 0.5 + (prob - 0.5) * PROB_SHRINK
            ev = min(calc_ev(prob_cal, -110), EV_MAX)
            # ‘‘ OVER/UNDER 分別門檻（從歷史命中率調整）
            ev_min = MIN_UNDER_EV if direction == 'UNDER' else MIN_OVER_EV
            if ev > ev_min:
                candidates.append({
                    'bet_type': 'TOTAL', 'direction': direction,
                    'description': desc, 'win_prob': round(prob_cal, 4),
                    'ev': ev, 'kelly': calc_kelly(prob_cal, -110), 'odds': -110
                })

    # ── 獨贏 ──
    for team, prob, odds, direction in [
        (mc['home_team'], mc['win_prob_home'], home_ml, 'HOME'),
        (mc['away_team'], mc['win_prob_away'], away_ml, 'AWAY'),
    ]:
        if odds is None: continue
        if odds > ML_MAX_ODDS:
            continue
        market_prob = american_to_prob(odds)
        if abs(prob - market_prob) > ML_MAX_DIFF:
            continue
        # 📊 勝率校準（ML 也要校正）
        prob_cal = 0.5 + (prob - 0.5) * PROB_SHRINK
        ev = min(calc_ev(prob_cal, odds), EV_MAX)
        if ev > 0:
            candidates.append({
                'bet_type': 'MONEYLINE', 'direction': direction,
                'description': f"{team} ML",
                'win_prob': round(prob_cal, 4),
                'ev': ev, 'kelly': calc_kelly(prob_cal, odds), 'odds': odds
            })

    # 🎯 核心排序：勝率 × 期望值 的「綜合分」
    # 原理：只看勝率 → 會選賠率很差的主隊ML（贏但賺不多）
    #       只看EV   → 會選機率低但賠率好的冷門（賺很多但常輸）
    #       兩個都要好才能排前面：score = win_prob × ev
    if candidates:
        candidates.sort(key=lambda x: x['win_prob'] * x['ev'], reverse=True)

    best = candidates[0] if candidates else None
    ev   = best['ev'] if best else 0

    # 產生風險標籤 (Risk Tags)
    risk_tags = []
    
    # 1. Blowout risk (大勝垃圾時間)
    if spread_line is not None and abs(mc['pred_spread']) >= 12.0:
        risk_tags.append("⚠️ Blowout risk")
        
    # 2. Injury chaos (傷兵混亂)
    if mc.get('too_many_injuries') or mc.get('collapse_flag'):
        risk_tags.append("⚠️ Injury chaos")
        
    # 3. Market aligned (盤口已反映)
    # 📝 修正：原來門檻 0.8 點。但因為在前頭模型已經有 35% 往盤口位移 (MARKET_WEIGHT=0.35)
    # 所以原始差距 1.2 分以內就會被壓縮到 0.8 內。這裡將門檻下調至 0.5 點，保留一點彈性空間。
    if spread_line is not None:
        market_spread = -spread_line
        model_spread = mc['pred_spread']
        if abs(model_spread - market_spread) <= 0.5:
            risk_tags.append("⚠️ Market aligned")

    if not risk_tags:
        risk_tags.append("✅ Clean game")

    if not candidates:
        return {'best_bet': None, 'all_bets': [], 'confidence': 'SKIP', 'risk_tags': risk_tags}

    # 信心等級
    if ev >= HIGH_CONF_EV and best['win_prob'] >= HIGH_CONF_PROB:
        confidence = 'HIGH'
    elif ev >= 0.04:
        confidence = 'MED'
    else:
        confidence = 'LOW'

    # ✅ 只有 Blowout risk / Injury chaos 才觸發 HIGH→MED 降級
    # Market aligned 只顯示標籤，不影響信心等級
    demote_tags = {'⚠️ Blowout risk', '⚠️ Injury chaos'}
    has_demote_risk = any(t in demote_tags for t in risk_tags)
    if has_demote_risk and confidence == 'HIGH':
        confidence = 'MED'

    return {'best_bet': best, 'all_bets': candidates, 'confidence': confidence, 'risk_tags': risk_tags}

print("✅ EV + Kelly 計算模組就緒")


# ─────────────────────────────────────────────
# CELL 16：整合函數 — 一鍵分析一場比賽
# ─────────────────────────────────────────────

def analyze_game(
    game_id, home_team, away_team,
    spread_line, total_line,
    home_ml=None, away_ml=None,
    home_injuries=None, away_injuries=None,
    game_date_est=None, game_time_est=None,
    trigger_session='evening',
    save_to_db=True,
    n_simulations=10000,
) -> dict:

    game_date_est = game_date_est or now_est().strftime('%Y-%m-%d')
    print(f"\n{'='*55}")
    print(f"🏀 分析：{tn(away_team)} @ {tn(home_team)}")
    print(f"   日期：{game_date_est}  盤口：{spread_line:+.1f}  大小：{total_line}")
    print(f"{'='*55}")

    mc       = run_monte_carlo(home_team, away_team, home_injuries, away_injuries, n_simulations,
                             spread_line=spread_line)
    bet_eval = evaluate_bet(mc, spread_line, total_line, home_ml, away_ml)
    best     = bet_eval['best_bet']

    # ✅ 勝負預測信心（純看模型對勝負的把握度，與下注信心分開）
    wph = mc['win_prob_home']
    wpa = mc['win_prob_away']
    max_wp = max(wph, wpa)
    if max_wp >= 0.65:
        win_pred_conf = 'HIGH'   # ≥ 65% 把握
    elif max_wp >= 0.55:
        win_pred_conf = 'MED'    # ≥ 55% 把握
    else:
        win_pred_conf = 'LOW'    # 接近 50/50

    pred_for_signal = {
        'ev_value': best['ev'] if best else 0,
        'collapse_flag': mc['collapse_flag'],
        'collapse_team': mc['collapse_team'],
        'confidence_level': bet_eval['confidence'],
    }
    early = evaluate_early_bet(pred_for_signal, odds_stable=True)

    # 印出結果
    print(f"\n  📊 模擬結果（{n_simulations:,} 次）")
    print(f"     預測比分：{tn(home_team)} {mc['pred_home']} : {mc['pred_away']} {tn(away_team)}")
    print(f"     預測分差：{mc['pred_spread']:+.1f}（主隊視角）  盤口讓分：{spread_line:+.1f}")
    print(f"     預測總分：{mc['pred_total']:.1f}  盤口大小：{total_line}")
    print(f"     主隊勝率：{mc['win_prob_home']:.1%}  客隊勝率：{mc['win_prob_away']:.1%}")
    print(f"     σ：{mc['sigma_used']}  Pace：{mc['pace_used']}  模擬次數：{n_simulations:,}")

    if mc['collapse_flag']:
        print(f"\n  💥 ⚠️  體系崩潰：{tn(mc['collapse_team']) if mc['collapse_team'] else ''}")
    if mc.get('too_many_injuries'):
        print(f"  ⚠️  傷兵人數過多，預測分差可信度下降，建議搭配盤口異動一起判斷")

    if best:
        print(f"\n  💰 最佳下注建議")
        print(f"     方向：{best['description']}")
        print(f"     勝率：{best['win_prob']:.1%}  EV：{best['ev']:+.1%}")
        print(f"     Kelly 建議：{best['kelly']:.1%} 本金  信心：{bet_eval['confidence']}")
        print(f"     🛡️ 盤口風險標籤：{', '.join(bet_eval['risk_tags'])}")
        if len(bet_eval['all_bets']) > 1:
            others = [b['description'] + ' EV:' + '{:+.1%}'.format(b['ev']) for b in bet_eval['all_bets'][1:3]]
            print(f"     其他選項：{others}")
    else:
        print(f"\n  ⛔ 無正期望值，建議跳過")
        print(f"     🛡️ 盤口風險標籤：{', '.join(bet_eval['risk_tags'])}")
    print(f"     ⏱️ OT 風險：{mc.get('ot_risk_level','')} {mc.get('ot_risk_score',0):.1f}/100  (OT機率 {mc.get('ot_prob',0):.1%})")

    print(f"\n  📡 {early['summary']}")

    if save_to_db:
        model_params = {
            'sigma_normal': SIGMA_NORMAL, 'sigma_collapse': SIGMA_COLLAPSE,
            'collapse_threshold': COLLAPSE_THRESHOLD,
            'collapse_penalty_mult': COLLAPSE_PENALTY_MULT,
            'kelly_fraction': KELLY_FRACTION, 'max_bet_pct': MAX_BET_PCT,
            'core_missing_min_mult': CORE_MISSING_MIN_MULTIPLIER,
            'n_simulations': n_simulations, 'version': 'V34.1'
        }
        save_prediction({
            'game_id': game_id, 'game_date_est': game_date_est,
            'game_time_est': game_time_est, 'home_team': home_team, 'away_team': away_team,
            'open_line': spread_line, 'live_line': spread_line,
            'total_line': total_line, 'home_odds': home_ml, 'away_odds': away_ml,
            'ai_score_home': mc['pred_home'], 'ai_score_away': mc['pred_away'],
            'ai_spread': mc['pred_spread'], 'ai_total': mc['pred_total'],
            'win_prob_home': mc['win_prob_home'], 'win_prob_away': mc['win_prob_away'],
            'ev_value': best['ev'] if best else None,
            'recommended_bet': best['description'] if best else 'SKIP',
            'confidence_level': bet_eval['confidence'],
            'kelly_fraction': best['kelly'] if best else 0,
            'suggested_bet_pct': best['kelly'] if best else 0,
            'early_bet_signal': 1 if early['early_bet_signal'] else 0,
            'sigma_used': mc['sigma_used'], 'collapse_flag': 1 if mc['collapse_flag'] else 0,
            'collapse_team': mc['collapse_team'],
            'injury_snapshot': json.dumps({
                'home': home_injuries or [],
                'away': away_injuries or [],
                'collapse_players': {
                    'home': [p['name'] for p in (home_injuries or [])
                             if INJURY_IMPACT.get(p.get('role','rotation'),{}).get('core')
                             and STATUS_MULTIPLIER.get(p.get('status','out').lower(),0)
                             >= CORE_MISSING_MIN_MULTIPLIER],
                    'away': [p['name'] for p in (away_injuries or [])
                             if INJURY_IMPACT.get(p.get('role','rotation'),{}).get('core')
                             and STATUS_MULTIPLIER.get(p.get('status','out').lower(),0)
                             >= CORE_MISSING_MIN_MULTIPLIER],
                }
            }),
            'pace_home': TEAM_STATS.get(home_team, LEAGUE_AVG).get('pace'),
            'pace_away': TEAM_STATS.get(away_team, LEAGUE_AVG).get('pace'),
            'mc_simulations': n_simulations,
            'model_params_json': json.dumps(model_params),
            'trigger_session': trigger_session,
            'risk_tags': json.dumps(bet_eval['risk_tags']),
            'ot_prob': mc.get('ot_prob', 0.0),
            'win_pred_confidence': win_pred_conf,
        })

    return {'mc': mc, 'bet_eval': bet_eval, 'early_signal': early}


# ─────────────────────────────────────────────
# CELL 17：對獎函數
# ─────────────────────────────────────────────

def grade_result(game_id, actual_score_home, actual_score_away, data_source='manual'):
    conn = sqlite3.connect(DB_PATH)
    pred = conn.execute('''
        SELECT home_team, away_team, game_date_est,
               recommended_bet, live_line, total_line, suggested_bet_pct
        FROM predictions WHERE game_id=?
        ORDER BY created_at_est DESC LIMIT 1
    ''', (game_id,)).fetchone()

    if not pred:
        print(f"⚠️  找不到 game_id={game_id}")
        conn.close(); return

    home_team, away_team, game_date = pred[0], pred[1], pred[2]
    recommended_bet = pred[3] or ''
    spread_line     = pred[4]
    total_line      = pred[5]
    bet_pct         = pred[6] or 0

    actual_spread = actual_score_home - actual_score_away
    actual_total  = actual_score_home + actual_score_away
    actual_winner = 'HOME' if actual_score_home > actual_score_away else 'AWAY'

    spread_result = ou_result = None
    if spread_line is not None:
        diff = actual_spread - spread_line
        spread_result = 'WIN' if diff > 0 else 'LOSE' if diff < 0 else 'PUSH'
    if total_line is not None:
        ou_result = 'OVER' if actual_total > total_line else \
                    'UNDER' if actual_total < total_line else 'PUSH'

    rec = recommended_bet.upper()
    bet_hit = None
    pnl = 0.0
    if rec and rec != 'SKIP':
        if 'OVER' in rec:
            if   ou_result == 'OVER':  bet_hit = 1
            elif ou_result == 'PUSH':  bet_hit = None
            else:                      bet_hit = 0
        elif 'UNDER' in rec:
            if   ou_result == 'UNDER': bet_hit = 1
            elif ou_result == 'PUSH':  bet_hit = None
            else:                      bet_hit = 0
        elif 'ML' in rec:
            if actual_winner == 'HOME' and home_team.upper() in rec:   bet_hit = 1
            elif actual_winner == 'AWAY' and away_team.upper() in rec: bet_hit = 1
            else:                                                        bet_hit = 0
        else:
            is_away_bet = (away_team.upper() in rec)
            if is_away_bet:
                if   spread_result == 'LOSE': bet_hit = 1
                elif spread_result == 'PUSH': bet_hit = None
                else:                         bet_hit = 0
            else:
                if   spread_result == 'WIN':  bet_hit = 1
                elif spread_result == 'PUSH': bet_hit = None
                else:                         bet_hit = 0

        if bet_hit == 1:   pnl =  bet_pct * (100/110)
        elif bet_hit == 0: pnl = -bet_pct

    save_result({
        'game_id': game_id, 'game_date_est': game_date,
        'home_team': home_team, 'away_team': away_team,
        'actual_score_home': actual_score_home, 'actual_score_away': actual_score_away,
        'actual_spread': actual_spread, 'actual_total': actual_total,
        'actual_winner': actual_winner,
        'spread_result': spread_result, 'ou_result': ou_result,
        'bet_hit': bet_hit, 'pnl': round(pnl, 4),
        'data_source': data_source, 'is_final': 1
    })

    print(f"\n{'='*50}")
    print(f"🏁 對獎：{tn(away_team)} @ {tn(home_team)}")
    print(f"   比分：{actual_score_home}:{actual_score_away}  ({actual_winner} 贏)")
    print(f"   讓分：{spread_result}   大小：{ou_result}")
    hit_str = '✅ 命中' if bet_hit==1 else '❌ 未中' if bet_hit==0 else '↩️ 退水' if bet_hit is None else '－'
    print(f"   推薦：{hit_str}  PnL：{pnl:+.2%}")
    print(f"{'='*50}")
    conn.close()


# ─────────────────────────────────────────────
# CELL 18：DEV 測試
# ─────────────────────────────────────────────

if DEV_MODE:
    today_est = now_est().strftime('%Y-%m-%d')
    print("\n🧪 DEV 測試開始...\n")

    # 場次1：BOS vs MIA（Butler 確定缺陣）
    r1 = analyze_game(
        game_id='TEST_MC_001', home_team='Boston Celtics', away_team='Miami Heat',
        spread_line=-6.5, total_line=215.0, home_ml=-280, away_ml=230,
        home_injuries=[],
        away_injuries=[
            {"name": "Jimmy Butler",  "role": "allstar",  "status": "out"},
            {"name": "Terry Rozier",  "role": "starter",  "status": "questionable"},
        ],
        game_date_est=today_est, game_time_est='19:30',
    )

    print("\n" + "─"*55)

    # 場次2：DEN vs PHX（Jokic questionable + Murray out → 應觸發崩潰）
    r2 = analyze_game(
        game_id='TEST_MC_002', home_team='Denver Nuggets', away_team='Phoenix Suns',
        spread_line=-3.0, total_line=220.0,
        home_injuries=[
            {"name": "Nikola Jokic",  "role": "superstar", "status": "questionable"},
            {"name": "Jamal Murray",  "role": "allstar",   "status": "out"},
        ],
        away_injuries=[],
        game_date_est=today_est, game_time_est='21:00',
    )

    print("\n" + "─"*55)

    # 對獎測試（BOS 117:108 贏 MIA）
    grade_result('TEST_MC_001', 117, 108)

    # 命中率
    get_hit_rate()

    print("\n🎉 引擎測試完成！預測分數應在 100-125 分之間")
    print("   如分數合理 → 下一步：Telegram 推播篇")
