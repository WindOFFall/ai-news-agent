# AI News Agent

每日自動抓取全球財經與科技外電，透過 Gemini AI 分析對台股供應鏈的影響，並將報告推送至 Telegram。由 GitHub Actions 排程，每天台灣時間早上 8 點自動執行。

---

## 功能

- 從 TechCrunch、Hacker News、Yahoo Finance 抓取前一天新聞
- 針對每個來源用 AI 分析，找出對台股 / 美股供應鏈的受惠或受害個股
- Gemini 額度用盡時自動切換至 Groq（llama-3.3-70b）備援
- 分析結果排版成手機易讀格式，推送到 Telegram

---

## 新聞來源與分析重點

| 來源 | 分析重點 |
|------|----------|
| TechCrunch AI | 新技術 / 併購案對軟硬體供應鏈的影響，點名台股受惠公司 |
| Hacker News | 最具顛覆性的開源專案或演算法突破，分析潛在商業衝擊 |
| Yahoo Finance | 美股個股 / 總經事件對台股供應鏈的直接影響 |

---

## 環境設定

### 1. 安裝套件

```bash
pip install -r requirements.txt
```

### 2. 建立 `.env` 檔案

```env
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. 本地執行

```bash
python news_agent.py
```

---

## GitHub Actions 自動排程

本專案使用 GitHub Actions 每天自動執行，不需要自己的伺服器。

### 設定步驟

1. 將 repo fork 或 push 到 GitHub
2. 進入 repo → **Settings → Secrets and variables → Actions**
3. 新增以下四個 Secret：

| Secret 名稱 | 說明 |
|-------------|------|
| `GEMINI_API_KEY` | Google AI Studio 取得 |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) 取得 |
| `TELEGRAM_BOT_TOKEN` | 向 Telegram BotFather 建立 Bot 取得 |
| `TELEGRAM_CHAT_ID` | 你的 Telegram 帳號 Chat ID |

4. 每天 UTC 00:00（台灣時間早上 8:00）自動執行
5. 也可在 GitHub Actions 頁面手動觸發（**Run workflow**）

---

## 專案結構

```
ai-news-agent/
├── news_agent.py              # 主程式（抓新聞、AI 分析、推 Telegram）
├── requirements.txt           # 套件清單
├── .env                       # 本地環境變數（不進 git）
└── .github/
    └── workflows/
        └── schedule.yml       # GitHub Actions 排程設定
```

---

## LLM 備援機制

Gemini 額度耗盡或服務異常時，自動切換至 Groq：

```
gemini-3.1-flash-lite-preview
    ↓ 失敗
Groq llama-3.3-70b-versatile
    ↓ 失敗
Groq llama-3.1-8b-instant
```
