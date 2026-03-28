# =============================================================
# 🏀 NBA V34.1 — 傷兵資料模組 v3
# 來源：NBA 官方傷兵報告 PDF（每 15 分鐘更新）
# 完全免費，無需任何 API Key
# =============================================================

import requests, io, re
from bs4 import BeautifulSoup

PDF_TEAM_MAP = {
    'AtlantaHawks':           'Atlanta Hawks',
    'BostonCeltics':          'Boston Celtics',
    'BrooklynNets':           'Brooklyn Nets',
    'CharlotteHornets':       'Charlotte Hornets',
    'ChicagoBulls':           'Chicago Bulls',
    'ClevelandCavaliers':     'Cleveland Cavaliers',
    'DallasMavericks':        'Dallas Mavericks',
    'DenverNuggets':          'Denver Nuggets',
    'DetroitPistons':         'Detroit Pistons',
    'GoldenStateWarriors':    'Golden State Warriors',
    'HoustonRockets':         'Houston Rockets',
    'IndianaPacers':          'Indiana Pacers',
    'LosAngelesClippers':     'LA Clippers',
    'LosAngelesLakers':       'LA Lakers',
    'MemphisGrizzlies':       'Memphis Grizzlies',
    'MiamiHeat':              'Miami Heat',
    'MilwaukeeBucks':         'Milwaukee Bucks',
    'MinnesotaTimberwolves':  'Minnesota Timberwolves',
    'NewOrleansPelicans':     'New Orleans Pelicans',
    'NewYorkKnicks':          'New York Knicks',
    'OklahomaCityThunder':    'Oklahoma City Thunder',
    'OrlandoMagic':           'Orlando Magic',
    'Philadelphia76ers':      'Philadelphia 76ers',
    'PhoenixSuns':            'Phoenix Suns',
    'PortlandTrailBlazers':   'Portland Trail Blazers',
    'SacramentoKings':        'Sacramento Kings',
    'SanAntonioSpurs':        'San Antonio Spurs',
    'TorontoRaptors':         'Toronto Raptors',
    'UtahJazz':               'Utah Jazz',
    'WashingtonWizards':      'Washington Wizards',
}

PLAYER_ROLES = {
    "Giannis Antetokounmpo": "superstar",
    "Nikola Jokic":          "superstar",
    "Luka Doncic":           "superstar",
    "Jayson Tatum":          "superstar",
    "Joel Embiid":           "superstar",
    "Stephen Curry":         "superstar",
    "Kevin Durant":          "superstar",
    "LeBron James":          "superstar",
    "Shai Gilgeous-Alexander": "superstar",
    "Victor Wembanyama":     "superstar",
    "Damian Lillard":        "allstar",
    "Kawhi Leonard":         "allstar",
    "Anthony Davis":         "allstar",
    "Jimmy Butler":          "allstar",
    "Bam Adebayo":           "allstar",
    "Jaylen Brown":          "allstar",
    "Devin Booker":          "allstar",
    "Trae Young":            "allstar",
    "Donovan Mitchell":      "allstar",
    "Darius Garland":        "allstar",
    "Tyrese Haliburton":     "allstar",
    "Cade Cunningham":       "allstar",
    "Paolo Banchero":        "allstar",
    "Jaren Jackson Jr.":     "allstar",
    "Jamal Murray":          "allstar",
    "Michael Porter Jr.":    "allstar",
    "Anthony Edwards":       "allstar",
    "Karl-Anthony Towns":    "allstar",
    "Jalen Brunson":         "allstar",
    "OG Anunoby":            "allstar",
    "LaMelo Ball":           "allstar",
    "Brandon Ingram":        "allstar",
    "Zion Williamson":       "allstar",
    "Alperen Sengun":        "allstar",
    "Evan Mobley":           "allstar",
    "Scottie Barnes":        "allstar",
    "Franz Wagner":          "allstar",
    "Tyrese Maxey":          "allstar",
    "De'Aaron Fox":          "allstar",
    "Domantas Sabonis":      "allstar",
    "Jrue Holiday":          "allstar",
    "Khris Middleton":       "allstar",
    "Klay Thompson":         "allstar",
    "Terry Rozier":          "allstar",
    "Paul George":           "allstar",
    "Desmond Bane":          "allstar",
    "Zach LaVine":           "allstar",
    "DeMar DeRozan":         "allstar",
    "Russell Westbrook":     "allstar",
    "Chris Paul":            "allstar",
    "Nikola Vucevic":        "allstar",
    "Fred VanVleet":         "allstar",
}

CORE_MISSING_MIN_MULTIPLIER = 0.4
STATUS_MULTIPLIER = {
    "out": 1.0, "doubtful": 0.8, "questionable": 0.4,
    "gtd": 0.3, "probable": 0.1, "available": 0.0,
}

def get_player_role(name):
    return PLAYER_ROLES.get(name, "starter")

def _parse_name(token):
    if ',' not in token:
        return ''
    last, first = token.split(',', 1)
    first = first.strip()
    last  = last.strip()
    last = re.sub(r'Jr$', 'Jr.', last)
    last = re.sub(r'Sr$', 'Sr.', last)
    return f"{first} {last}"

def _extract_team_and_rest(text):
    for pdf_name, std_name in sorted(PDF_TEAM_MAP.items(), key=lambda x: -len(x[0])):
        if text.startswith(pdf_name):
            return std_name, text[len(pdf_name):].strip()
    return None, text

def _extract_players(text, team, result):
    if team not in result:
        result[team] = []
    tokens = text.split()
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if ',' in token and re.match(r'^[A-Za-z]', token):
            full_name = _parse_name(token)
            if not full_name:
                i += 1
                continue
            status = 'questionable'
            j = i + 1
            while j < len(tokens):
                t_lower = tokens[j].lower()
                if t_lower in ('out', 'doubtful', 'questionable', 'probable'):
                    status = t_lower
                    break
                if ',' in tokens[j] and re.match(r'^[A-Za-z]', tokens[j]):
                    break
                j += 1
            role = get_player_role(full_name)
            if not any(p['name'] == full_name for p in result[team]):
                result[team].append({
                    'name': full_name, 'role': role,
                    'status': status, 'raw': token,
                })
        i += 1

def _print_injury_summary(injuries):
    total = sum(len(v) for v in injuries.values())
    print(f"   📋 共 {total} 名傷兵，涉及 {len(injuries)} 支球隊")
    for team, players in sorted(injuries.items()):
        core = [p for p in players
                if p['role'] in ('superstar', 'allstar')
                and STATUS_MULTIPLIER.get(p['status'], 0) >= CORE_MISSING_MIN_MULTIPLIER]
        if core:
            names = ', '.join([f"{p['name']}({p['status'][:3]})" for p in core])
            print(f"   ⚠️  {team}：{names}")

def fetch_injuries_nba_official():
    """NBA 官方傷兵報告 PDF，每 15 分鐘更新，完全免費"""
    if DEV_MODE:
        print("🔒 DEV_MODE：回傳假傷兵資料")
        return {
            "Miami Heat": [{"name": "Jimmy Butler", "role": "allstar", "status": "out"}],
            "Denver Nuggets": [
                {"name": "Nikola Jokic",  "role": "superstar", "status": "questionable"},
                {"name": "Jamal Murray",  "role": "allstar",   "status": "out"},
            ],
        }

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    print("🌐 抓取 NBA 官方傷兵報告 PDF...")

    try:
        page = requests.get(
            "https://official.nba.com/nba-injury-report-2025-26-season/",
            headers=headers, timeout=15)
        soup = BeautifulSoup(page.text, 'html.parser')
        pdfs = sorted([a['href'] for a in soup.find_all('a', href=True)
                       if 'referee/injury/Injury-Report_' in a['href']])
        if not pdfs:
            print("   ❌ 找不到 PDF 連結")
            return {}
        latest = pdfs[-1]
        print(f"   📄 {latest.split('/')[-1]}")
    except Exception as e:
        print(f"   ❌ 取得 PDF 失敗：{e}")
        return {}

    try:
        pdf_resp = requests.get(latest, headers=headers, timeout=15)
        if pdf_resp.status_code != 200:
            print(f"   ❌ PDF 下載失敗：{pdf_resp.status_code}")
            return {}
    except Exception as e:
        print(f"   ❌ 下載錯誤：{e}")
        return {}

    # 解析 PDF
    import pdfplumber
    injuries_by_team = {}
    current_team = None
    team_pattern = re.compile(
        r'^(' + '|'.join(re.escape(k) for k in PDF_TEAM_MAP.keys()) + r')\s*')
    player_pattern = re.compile(r'^[A-Za-z]+,\s*[A-Za-z]')

    try:
        with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                for line in text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    if any(line.startswith(x) for x in
                           ['Injury Report', 'GameDate', 'Page', 'Game']):
                        continue

                    # 含日期的比賽行
                    if re.match(r'^\d{2}/\d{2}/\d{4}', line):
                        m = re.search(r'\w+@\w+\s+(.*)', line)
                        if m:
                            current_team, rest = _extract_team_and_rest(m.group(1))
                            if current_team and rest:
                                _extract_players(rest, current_team, injuries_by_team)
                        continue

                    # 只有時間的比賽行
                    if re.match(r'^\d{2}:\d{2}\(ET\)', line):
                        m = re.search(r'\w+@\w+\s+(.*)', line)
                        if m:
                            current_team, rest = _extract_team_and_rest(m.group(1))
                            if current_team and rest:
                                _extract_players(rest, current_team, injuries_by_team)
                        continue

                    # 球隊行
                    tm = team_pattern.match(line)
                    if tm:
                        current_team = PDF_TEAM_MAP.get(tm.group(1))
                        rest = line[tm.end():].strip()
                        if current_team and rest:
                            _extract_players(rest, current_team, injuries_by_team)
                        continue

                    # 純球員行
                    if current_team and player_pattern.match(line):
                        _extract_players(line, current_team, injuries_by_team)

    except Exception as e:
        print(f"   ❌ PDF 解析錯誤：{e}")
        import traceback; traceback.print_exc()
        return {}

    injuries_by_team = {k: v for k, v in injuries_by_team.items() if v}
    _print_injury_summary(injuries_by_team)
    return injuries_by_team


def save_injuries_to_db(injuries, game_date_est):
    import sqlite3, json
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS injury_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date_est   TEXT NOT NULL,
            team_name       TEXT NOT NULL,
            injuries_json   TEXT,
            fetched_at_est  TEXT DEFAULT (datetime('now')),
            UNIQUE(game_date_est, team_name)
        )
    ''')
    for team, players in injuries.items():
        conn.execute('''
            INSERT OR REPLACE INTO injury_snapshots
            (game_date_est, team_name, injuries_json)
            VALUES (?, ?, ?)
        ''', (game_date_est, team, json.dumps(players, ensure_ascii=False)))
    conn.commit()
    conn.close()
    print(f"   💾 傷兵快照存入 DB（{game_date_est}，{len(injuries)} 支球隊）")


def load_injuries_from_db(game_date_est):
    import sqlite3, json
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute('''
            SELECT team_name, injuries_json FROM injury_snapshots
            WHERE game_date_est = ?
        ''', (game_date_est,)).fetchall()
        conn.close()
        return {r[0]: json.loads(r[1]) for r in rows}
    except:
        conn.close()
        return {}


# 別名，讓每日一鍵執行可以直接呼叫
fetch_injuries_nba = fetch_injuries_nba_official

print("✅ 傷兵資料模組 v3 就緒")
print(f"   資料來源：NBA 官方傷兵報告 PDF（每 15 分鐘更新）")
print(f"   球員角色資料庫：{len(PLAYER_ROLES)} 名球員")
print(f"   完全免費，無需任何 API Key ✅")

if DEV_MODE:
    print("\n🧪 DEV 測試：傷兵抓取")
    injuries = fetch_injuries_nba_official()
    save_injuries_to_db(injuries, now_est().strftime('%Y-%m-%d'))
    loaded = load_injuries_from_db(now_est().strftime('%Y-%m-%d'))
    print(f"   ✅ 存取測試完成：{list(loaded.keys())}")
