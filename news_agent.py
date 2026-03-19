NEWS_SOURCES = [
    {
        "id": "techcrunch_ai",
        "name": "TechCrunch (AI專區)",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "max_items": 15,
        # 針對這個來源的客製化指令
        "ai_focus": "這是一手的新創與 AI 商業新聞。請著重分析這些新技術或併購案，會連帶讓哪些【軟硬體供應鏈】受惠？具體點名台股或美股的潛在受惠公司。"
    },
    {
        "id": "hacker_news",
        "name": "Hacker News (矽谷開發者前沿)",
        "url": "https://news.ycombinator.com/rss",
        "max_items": 15,
        # 針對這個來源的客製化指令
        "ai_focus": "這是全球頂尖工程師的討論區。請著重挑選最具顛覆性的【開源專案或演算法突破】，並用一句話解釋這個技術未來可能取代或改變什麼商業模式。"
    },
    # 未來您可以輕鬆新增如 Yahoo Finance 或 Seeking Alpha 的 RSS，並給予不同的 ai_focus
]

# ==========================================
# 3. 核心功能模組
# ==========================================

def fetch_rss_news(source_config):
    """根據單一來源設定，抓取並整理新聞"""
    print(f"📡 抓取來源：{source_config['name']}...")
    feed = feedparser.parse(source_config['url'])
    
    news_items = []
    for entry in feed.entries[:source_config['max_items']]:
        title = entry.title
        link = entry.link
        # 嘗試抓取摘要，如果沒有就留空
        summary = entry.get('summary', '')[:200] 
        news_items.append(f"【標題】{title}\n【摘要】{summary}\n【連結】{link}\n")
        
    return "\n".join(news_items)

# def analyze_source_with_ai(source_name, news_text, ai_focus):
#     """套用專屬 Prompt，讓 Gemini 針對單一來源進行分析"""
#     print(f"🧠 AI 正在分析：{source_name}...")
    
#     prompt = f"""
#     你是一位精通全球科技產業與資本市場的資深分析師。
#     請閱讀以下來自【{source_name}】的最新外電情報：
    
#     {news_text}
    
#     【你的專屬分析任務】：
#     {ai_focus}
    
#     【輸出格式要求】：
#     1. 請將選出的重要新聞標題翻譯為繁體中文。
#     2. 根據「專屬分析任務」給出精煉的分析與見解（50 字以內）。
#     3. 附上原始連結。
#     請用清晰的條列式 (Bullet points) 呈現。
#     """
    
#     try:
#         response = client.models.generate_content(
#             model='gemini-3.1-flash-lite-preview',
#             contents=prompt
#         )
#         return response.text
#     except Exception as e:
#         return f"❌ AI 分析失敗: {e}"
    
def analyze_source_with_ai(source_name, news_text, ai_focus):
    """套用專屬 Prompt，讓 Gemini 針對單一來源進行分析 (手機排版優化版)"""
    print(f"🧠 AI 正在分析：{source_name}...")
    
    # 🌟 核心修改：在 Prompt 中加上極度嚴格的排版指令
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
    
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"❌ AI 分析失敗: {e}"



# ==========================================
# 4. 🚀 Agent 執行主流程
# ==========================================
def run_multi_source_agent():
    print("="*60)
    print(" 🤖 啟動多源情報 Agent...")
    print("="*60)
    
    final_reports = {}
    
    # 迴圈歷遍所有設定好的來源
    for source in NEWS_SOURCES:
        # Step 1: 抓取該來源的新聞
        raw_news = fetch_rss_news(source)
        
        if not raw_news.strip():
            final_reports[source['name']] = "⚠️ 此來源今日無更新或抓取失敗。"
            continue
            
        # Step 2: 傳入專屬的 ai_focus 讓 AI 獨立分析
        analysis_result = analyze_source_with_ai(source['name'], raw_news, source['ai_focus'])
        final_reports[source['name']] = analysis_result
        
    # Step 3: 彙整輸出結果
    print("\n" + "="*60)
    print(" 📰 【今日 AI 科技與市場前線日報】")
    print("="*60)
    
    for source_name, report in final_reports.items():
        print(f"\n📍 來源板塊：{source_name}")
        print("-" * 40)
        print(report)
        print("\n")


import feedparser
import os
import requests
import time  # 🌟 新增這行：用來控制時間暫停
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# ... (中間的 NEWS_SOURCES, fetch_rss_news, analyze_source_with_ai 保持不變) ...

# 🌟 新增：發送 Telegram 訊息的專屬函式
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
        # 讓連結可以在 Telegram 裡面直接點擊
        "parse_mode": "HTML", 
        "disable_web_page_preview": False
    }
    
    # try:
    #     response = requests.post(url, data=payload)
    #     if response.status_code == 200:
    #         print("✅ 成功發送訊息到 Telegram！")
    #     else:
    #         print(f"❌ Telegram 發送失敗：{response.text}")
    # except Exception as e:
    #     print(f"❌ 連線 Telegram 發生錯誤：{e}")


    try:
            # 加入 proxies={"http": None, "https": None} 強制繞過本機代理
            # 加入 timeout=10 避免程式卡死
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
# 🚀 修改：Agent 執行主流程
# ==========================================
def run_multi_source_agent():
    print("="*60)
    print(" 🤖 啟動多源情報 Agent...")
    print("="*60)
    
    full_daily_report = "<b>📰 【今日 AI 科技與市場前線日報】</b>\n\n"
    
    for source in NEWS_SOURCES:
        raw_news = fetch_rss_news(source)
        
        if not raw_news.strip():
            continue
            
        analysis_result = analyze_source_with_ai(source['name'], raw_news, source['ai_focus'])
        
        full_daily_report += f"<b>📍 來源板塊：{source['name']}</b>\n"
        full_daily_report += "➖" * 15 + "\n"
        safe_result = analysis_result.replace('<', '〈').replace('>', '〉')
        full_daily_report += f"{safe_result}\n\n"
        
        # 🌟 新增這行：讓程式強制休息 5 秒，避免被 Google API 封鎖！
        print("⏳ 休息 5 秒鐘，避免觸發 API 頻率限制...")
        time.sleep(5) 
        
    print(full_daily_report)
    
    print("📲 正在將報告推送到手機...")
    send_telegram_message(full_daily_report)

# 執行！
run_multi_source_agent()