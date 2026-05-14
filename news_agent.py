import feedparser
import os
import re
import requests
import time
import urllib3
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from google import genai
from groq import Groq

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. 初始化
# ==========================================

load_dotenv()

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

def fetch_llm_stats_news() -> list[dict]:
    """爬取 llm-stats.com/ai-news RSC 資料，回傳最近 36 小時內的新聞 list[{title, url, source}]"""
    from email.utils import parsedate_to_datetime
    cutoff = datetime.now(timezone.utc) - timedelta(hours=36)
    print(f"📡 抓取來源：LLM Stats（最近 36 小時，自 {cutoff.strftime('%Y-%m-%d %H:%M')} UTC）...")

    url = "https://llm-stats.com/ai-news"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "RSC": "1",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20, verify=False)
        resp.raise_for_status()
        text = resp.text

        raw_items = re.findall(
            r'\{"id":"[^"]+","title":"([^"]{5,300})","description":"[^"]*","link":"([^"]+)","source":"([^"]+)","pubDate":"([^"]+)"',
            text
        )

        seen_urls, seen_titles, items = set(), set(), []
        for title, link, source, pub_date in raw_items:
            try:
                dt = parsedate_to_datetime(pub_date)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except Exception:
                continue
            if link in seen_urls or title in seen_titles:
                continue
            seen_urls.add(link)
            seen_titles.add(title)
            items.append({"title": title, "url": link, "source": source})

        print(f"  ✅ 抓取完成：{len(items)} 則")
        return items
    except Exception as e:
        print(f"  ❌ llm-stats 抓取失敗：{e}")
        return []


def translate_titles_with_llm(articles: list[dict]) -> list[dict]:
    """用 LLM 批次翻譯英文標題為繁體中文，Gemini 優先，失敗切 Groq"""
    print("🧠 翻譯標題中...")
    titles_text = "\n".join(f"{i+1}. {a['title']}" for i, a in enumerate(articles))
    prompt = (
        "請將以下英文新聞標題逐一翻譯成繁體中文。\n"
        "只輸出翻譯結果，每行一則，格式為「序號. 繁體中文標題」，不要加任何說明。\n\n"
        f"{titles_text}"
    )

    raw = ""
    for attempt in range(1, 3):
        try:
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            raw = response.text.strip()
            print("  ✅ 翻譯成功（Gemini）")
            break
        except Exception as e:
            err = str(e)
            print(f"  ❗ Gemini 錯誤：{err[:100]}")
            if attempt < 2 and ('503' in err or '429' in err or 'unavailable' in err.lower()):
                time.sleep(15)

    if not raw:
        for groq_model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
            try:
                resp = groq_client.chat.completions.create(
                    model=groq_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                raw = resp.choices[0].message.content.strip()
                print(f"  ✅ 翻譯成功（Groq / {groq_model}）")
                break
            except Exception as e:
                print(f"  ❗ Groq [{groq_model}] 失敗：{str(e)[:80]}")

    # 解析翻譯結果，對應回原始 articles
    translated = []
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    for i, article in enumerate(articles):
        zh_title = article["title"]  # fallback 英文
        for line in lines:
            if line.startswith(f"{i+1}."):
                zh_title = line[len(f"{i+1}."):].strip()
                break
        translated.append({"title_zh": zh_title, "url": article.get("url", ""), "source": article.get("source", "")})
    return translated


def send_llm_stats_report(articles: list[dict]):
    """將翻譯後的 AI 新聞分段推播到 TG（每段最多 3800 字元）"""
    if not articles:
        return

    header = "<b>🤖 【今日 AI 產業動態 — LLM Stats】</b>\n\n"
    lines = []
    for i, a in enumerate(articles, 1):
        line = f"🔹 {i}. {a['title_zh']}"
        if a.get("url"):
            line += f"\n🔗 {a['url']}"
        lines.append(line)

    current = header
    for line in lines:
        chunk = line + "\n\n"
        if len(current) + len(chunk) > 3800:
            send_telegram_message(current)
            time.sleep(2)
            current = chunk
        else:
            current += chunk
    if current.strip():
        send_telegram_message(current)


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

    # RSS 來源暫時關閉
    # full_daily_report = "<b>📰 【今日 AI 科技與市場前線日報】</b>\n\n"
    # for source in NEWS_SOURCES:
    #     raw_news = fetch_rss_news(source)
    #     if not raw_news.strip():
    #         print(f"  ⚠️ {source['name']} 今日無近期文章，略過。")
    #         continue
    #     analysis_result = analyze_source_with_ai(source['name'], raw_news, source['ai_focus'])
    #     full_daily_report += f"<b>📍 來源板塊：{source['name']}</b>\n"
    #     full_daily_report += "➖" * 15 + "\n"
    #     safe_result = analysis_result.replace('<', '〈').replace('>', '〉')
    #     full_daily_report += f"{safe_result}\n\n"
    #     print("⏳ 休息 10 秒，避免觸發 API 頻率限制...")
    #     time.sleep(10)
    # print(full_daily_report)
    # print("📲 正在將報告推送到手機...")
    # send_telegram_message(full_daily_report)

    # LLM Stats：AI 產業動態（RSC → 翻譯標題 → 分段推播）
    llm_stats_articles = fetch_llm_stats_news()
    if llm_stats_articles:
        translated = translate_titles_with_llm(llm_stats_articles)
        send_llm_stats_report(translated)
    else:
        print("  ⚠️ LLM Stats 今日無資料，略過。")


# 執行
run_multi_source_agent()
