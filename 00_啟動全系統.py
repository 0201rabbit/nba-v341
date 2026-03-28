# =============================================================
# 🏀 NBA 戰情系統 V34.1 — 一鍵啟動
# =============================================================
# 使用方式：在 Colab 執行以下指令
#
#   !git clone https://github.com/0201rabbit/nba-v341.git /content/nba-v341 2>/dev/null || git -C /content/nba-v341 pull
#   exec(open('/content/nba-v341/00_啟動全系統.py').read())
#
# =============================================================

import subprocess, sys, os, shutil, json, time

REPO_DIR  = '/content/nba-v341'
APP_SRC   = os.path.join(REPO_DIR, '07_啟動Streamlit.py')
APP_DST   = '/content/streamlit_app.py'
CFG_PATH  = '/content/streamlit_config.json'

print("🏀 NBA 戰情系統 V34.1 啟動中...")
print("=" * 50)

# ── Step 1：Git Pull（自動抓最新版）────────────────────────
print("\n🔄 Step 1：同步最新程式碼 (git pull)...")
r = subprocess.run(
    ['git', '-C', REPO_DIR, 'pull', '--rebase', '--autostash'],
    capture_output=True, text=True
)
if 'Already up to date' in r.stdout:
    print("   ✅ 已是最新版本")
else:
    print(f"   📥 {r.stdout.strip() or r.stderr.strip()}")

# ── Step 2：複製最新 Streamlit 到執行位置 ──────────────────
print("\n📋 Step 2：更新 streamlit_app.py...")
if os.path.exists(APP_SRC):
    shutil.copy2(APP_SRC, APP_DST)
    print(f"   ✅ 已複製 {APP_SRC} → {APP_DST}")
else:
    print(f"   ❌ 找不到 {APP_SRC}，請確認 git pull 成功")
    sys.exit(1)

# ── Step 3：讀取 API Token 設定 ────────────────────────────
_tok, _chat = None, None
if os.path.exists(CFG_PATH):
    with open(CFG_PATH) as _f:
        _cfg = json.load(_f)
    _tok  = _cfg.get('TELEGRAM_TOKEN')
    _chat = _cfg.get('TELEGRAM_CHAT_ID')

def _tg(msg):
    if not _tok or not _chat:
        return
    try:
        import urllib.parse, requests as _r
        _r.get(
            f"https://api.telegram.org/bot{_tok}/sendMessage",
            params={"chat_id": _chat, "text": msg}, timeout=5
        )
    except Exception:
        pass

# ── Step 4：安裝套件 ───────────────────────────────────────
print("\n📦 Step 3：安裝套件...")
pkgs = ['requests', 'pdfplumber', 'beautifulsoup4', 'streamlit', 'plotly', 'pyngrok']
subprocess.run(['pip', 'install', *pkgs, '--quiet'], capture_output=True)
print("   ✅ 套件安裝完成")

# ── Step 5：依序載入各模組 ─────────────────────────────────
modules = [
    ('01_地基篇_v3.py',      '地基篇 v3'),
    ('02_引擎篇_v4.py',      '引擎篇 v4'),
    ('03_傷兵模組_v3.py',    '傷兵模組 v3'),
    ('04_Telegram推播篇.py', 'Telegram 推播篇'),
    ('05_回測模組篇.py',     '回測模組篇'),
    ('06_每日一鍵執行.py',   '每日一鍵執行'),
]

print("\n📡 Step 4：載入模組...")
for filename, name in modules:
    path = os.path.join(REPO_DIR, filename)
    if os.path.exists(path):
        print(f"   ▶  {name}...")
        exec(open(path).read(), globals())
        print(f"   ✅ {name} 完成")
    else:
        print(f"   ❌ 找不到 {path}")
        sys.exit(1)

print("\n" + "=" * 50)
print("🎉 所有模組載入完成！")
print("=" * 50)

# ── Step 6：啟動 Streamlit + ngrok ────────────────────────
print("\n🌐 Step 5：啟動 Streamlit + ngrok...")

PORT = 8501
subprocess.Popen(
    ['streamlit', 'run', APP_DST,
     '--server.port', str(PORT),
     '--server.headless', 'true'],
    stdout=open('/content/streamlit.log', 'w'),
    stderr=subprocess.STDOUT
)

time.sleep(4)  # 等 Streamlit 起來

try:
    from pyngrok import ngrok as _ngrok
    public_url = _ngrok.connect(PORT).public_url
    print(f"\n🔗 公開網址：{public_url}")
    print("   ↑ 手機/電腦直接開這個連結即可！\n")
    _tg("\n".join([
        "🏀 NBA 戰情系統 V34.1 已啟動！",
        f"🔗 連結：{public_url}",
        "📱 用手機瀏覽器打開即可查看今日戰情！",
    ]))
    print("📲 Telegram 連結已推播！")
except Exception as _ng_err:
    print(f"⚠️  ngrok 啟動失敗（{_ng_err}），請手動從 Colab 左側取得連結")

print("\n💡 可用指令：")
print("   run_today_analysis()    ← 今日分析")
print("   run_morning_push()      ← 早上推播")
print("   run_settlement()        ← 對獎結算")

