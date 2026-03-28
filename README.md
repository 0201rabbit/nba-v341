# 🏀 NBA 戰情系統 V34.1

NBA 投注輔助系統，運行於 Google Colab + Google Drive (SQLite)。

## 📋 執行順序

每次開啟 Colab，執行以下一行即可：

```python
!git clone https://github.com/YOUR_USERNAME/nba-v341.git /content/nba-v341 2>/dev/null || !git -C /content/nba-v341 pull
exec(open('/content/nba-v341/00_啟動全系統.py').read())
```

## ⚙️ 核心參數（版本鎖定）

| 參數 | 值 |
|------|-----|
| σ 正常/崩潰 | 12.0 / 15.0 |
| Kelly 係數 | 1/4 Kelly，上限 5% |
| 盤口錨定權重 | 35% |
| 崩潰門檻 | superstar+allstar 缺陣 ≥ 2 人 |

## 📅 每日流程

| 時間（台灣）| 動作 |
|------------|------|
| 下午 5-10 點 | `run_today_analysis()` |
| 早上起床 | `run_morning_push()` |
| 下午有空 | `run_settlement()` |
| 網址失效 | `restart_streamlit()` |

## 🔑 Colab Secrets 設定

- `ODDS_API_KEY`
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

## ⚠️ 每月維護

1. 更新 TEAM_STATS（引擎篇 CELL 12）
2. 更新 PLAYER_ROLES（傷兵模組）
3. 季後賽期間調整 home_adv

## 📁 檔案結構

```
00_啟動全系統.py      ← 一鍵啟動所有模組
01_地基篇_v3.py       ← DB + DataShield + API
02_引擎篇_v4.py       ← 蒙地卡羅 + EV + Kelly
03_傷兵模組_v3.py     ← NBA 官方 PDF 傷兵資料
04_Telegram推播篇.py  ← 推播格式
05_回測模組篇.py      ← 對獎 + 命中率
06_每日一鍵執行.py    ← 每日操作入口
07_啟動Streamlit.py   ← 網頁視覺化
```
