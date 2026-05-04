import feedparser
import os
import requests
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from google import genai
from groq import Groq

# ==========================================
# 1. 初始化
# ==========================================

load_dotenv()
if not os.getenv("GEMINI_API_KEY"):
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../reason-stock-agent/.env'))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ==========================================
# 2. 新聞來源設定
# ==========================================

NEWS_SOURCES = [
    {
        "id": "techcrunch_ai",
        "name": "TechCrunch (AI專區)",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "max_items": 15,
        "ai_focus": "這是一手的新創與 AI 商業新聞。請著重分析這些新技術或併購案，會連帶讓哪些【軟硬體供應鏈】受惠？具體點名台股或美股的潛在受惠公司。"
    },
    {
        "id": "hacker_news",
        "name": "Hacker News (矽谷開發者前沿)",
        "url": "https://news.ycombinator.com/rss",
        "max_items": 15,
        "ai_focus": "這是全球頂尖工程師的討論區。請著重挑選最具顛覆性的【開源專案或演算法突破】，並用一句話解釋這個技術未來可能取代或改變什麼商業模式。"
    },
    {
        "id": "yahoo_finance",
        "name": "Yahoo Finance (美股財經)",
        "url": "https://finance.yahoo.com/news/rssindex",
        "max_items": 15,
        "ai_focus": "這是美股財經新聞。請著重分析哪些【個股、產業或總經事件】對台股供應鏈有直接影響？具體點名可能受惠或受害的台股公司（含股票代號），並說明邏輯。"
    },
]

# ==========================================
# 3. 核心功能模組
# ==========================================

def fetch_rss_news(source_config):
    """抓取 RSS 新聞，只取昨天與今天的文章"""
    print(f"📡 抓取來源：{source_config['name']}...")
    feed = feedparser.parse(source_config['url'])

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    today = datetime.now(timezone.utc).date()
    valid_dates = {yesterday, today}

    news_items = []
    skipped = 0
    for entry in feed.entries[:source_config['max_items']]:
        pub = entry.get('published_parsed')
        if pub:
            pub_date = datetime(*pub[:6], tzinfo=timezone.utc).date()
            if pub_date not in valid_dates:
                skipped += 1
                continue
        title = entry.title
        link = entry.link
        summary = entry.get('summary', '')[:200]
        news_items.append(f"【標題】{title}\n【摘要】{summary}\n【連結】{link}\n")

    print(f"  ✅ 近2天文章：{len(news_items)} 篇，略過舊文章：{skipped} 篇")
    return "\n".join(news_items)


def analyze_source_with_ai(source_name, news_text, ai_focus):
    """用 AI 分析單一來源新聞，Gemini 失敗自動切換 Groq"""
    print(f"🧠 AI 正在分析：{source_name}...")

    prompt = f"""
    你是一位精通全球科技產業與資本市場的資深分析師。
    請閱讀以下來自【{source_name}】的最新外電情報：

    {news_text}

    【你的專屬分析任務】：
    {ai_focus}

    【輸出格式要求】(請嚴格遵守，為了在手機通訊軟體上好閱讀)：
    1. ❌ 絕對不要使用任何 Markdown 符號 (例如 **粗體**、# 標題 或 * 條列式)。
    2. 請挑選出 3 則最重要的新聞，每則新聞請嚴格按照以下格式排版：

    🔹 [請填入繁體中文標題]
    💡 重點：[請填入 50 字以內的精煉分析與受惠/受害供應鏈]
    🔗 連結：[請附上原始網址]

    3. ⚠️ 重要：每一則新聞與下一則新聞之間，請務必「空一整行」。
    """

    # Gemini 優先，失敗重試一次後切 Groq
    for attempt in range(1, 3):
        print(f"  🔄 嘗試：gemini-3.1-flash-lite-preview（第 {attempt} 次）")
        try:
            response = client.models.generate_content(
                model='gemini-3.1-flash-lite-preview',
                contents=prompt
            )
            print(f"  ✅ 成功使用：Gemini")
            return response.text
        except Exception as e:
            err = str(e)
            print(f"  ❗ Gemini 錯誤：{err[:150]}")
            if '503' in err or '429' in err or 'unavailable' in err.lower():
                if attempt < 2:
                    print(f"  ⏳ 等待 15 秒後重試...")
                    time.sleep(15)
            else:
                break

    # Gemini 全掛 → 改用 Groq
    for groq_model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        print(f"  🔄 嘗試：Groq / {groq_model}")
        try:
            resp = groq_client.chat.completions.create(
                model=groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            print(f"  ✅ 成功使用：Groq / {groq_model}")
            return resp.choices[0].message.content
        except Exception as e:
            print(f"  ❗ Groq [{groq_model}] 失敗：{str(e)[:100]}")

    return "❌ Gemini 與 Groq 均無法使用，請稍後再試。"


# ==========================================
# 4. Telegram 推播
# ==========================================

def send_telegram_message(text):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠️ 找不到 Telegram 設定，請檢查 .env 檔案！")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(
            url,
            data=payload,
            proxies={"http": None, "https": None},
            timeout=10
        )
        if response.status_code == 200:
            print("✅ 成功發送訊息到 Telegram！")
        else:
            print(f"❌ Telegram 發送失敗：{response.text}")
    except Exception as e:
        print(f"❌ 連線 Telegram 發生錯誤：{e}")


# ==========================================
# 5. 主流程
# ==========================================

def run_multi_source_agent():
    print("=" * 60)
    print(" 🤖 啟動多源情報 Agent...")
    print("=" * 60)

    full_daily_report = "<b>📰 【今日 AI 科技與市場前線日報】</b>\n\n"

    for source in NEWS_SOURCES:
        raw_news = fetch_rss_news(source)

        if not raw_news.strip():
            print(f"  ⚠️ {source['name']} 今日無近期文章，略過。")
            continue

        analysis_result = analyze_source_with_ai(source['name'], raw_news, source['ai_focus'])

        full_daily_report += f"<b>📍 來源板塊：{source['name']}</b>\n"
        full_daily_report += "➖" * 15 + "\n"
        safe_result = analysis_result.replace('<', '〈').replace('>', '〉')
        full_daily_report += f"{safe_result}\n\n"

        print("⏳ 休息 10 秒，避免觸發 API 頻率限制...")
        time.sleep(10)

    print(full_daily_report)
    print("📲 正在將報告推送到手機...")
    send_telegram_message(full_daily_report)


# 執行
run_multi_source_agent()
