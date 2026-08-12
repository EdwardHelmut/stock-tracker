import os
import requests
import json
import re

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 擴充特徵對照表：[關鍵字/媒體用語] -> (股票代號, 正確股票簡稱)
KEYWORD_MAPPING = {
    # 媒體常見「標題黨」代稱與特徵
    "滑軌": ("2059", "川湖"),
    "1.5萬元神股": ("2059", "川湖"),
    "航空股": ("2618", "長榮航"),
    "這檔航空股": ("2618", "長榮航"),
    "晶圓代工龍頭": ("2330", "台積電"),
    "晶片龍頭": ("2454", "聯發科"),
    "組裝大廠": ("2317", "鴻海"),
    
    # 標準股票名稱與代號
    "台積電": ("2330", "台積電"),
    "聯發科": ("2454", "聯發科"),
    "鴻海": ("2317", "鴻海"),
    "廣達": ("2382", "廣達"),
    "緯創": ("3231", "緯創"),
    "技嘉": ("2376", "技嘉"),
    "長榮航": ("2618", "長榮航"),
    "華航": ("2610", "華航"),
    "長榮": ("2603", "長榮"),
    "陽明": ("2609", "陽明"),
    "萬海": ("2615", "萬海"),
    "川湖": ("2059", "川湖"),
    "台達電": ("2308", "台達電"),
    "富邦金": ("2881", "富邦金"),
    "國泰金": ("2882", "國泰金"),
    "中信金": ("2891", "中信金"),
    "世芯": ("3661", "世芯-KY"),
    "創意": ("3443", "創意"),
    "緯穎": ("6669", "緯穎"),
    "奇鋐": ("3017", "奇鋐"),
    "雙鴻": ("3324", "雙鴻"),
    "智邦": ("2345", "智邦"),
    "瑞昱": ("2379", "瑞昱")
}

def send_tg_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("未設定 Telegram Key")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram 發送失敗: {e}")

def get_realtime_stock_price(stock_id):
    if not stock_id:
        return None
    try:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock_id}.tw"
        res = requests.get(url, timeout=10)
        data = res.json()
        if 'msgArray' in data and len(data['msgArray']) > 0:
            info = data['msgArray'][0]
            price = float(info.get('z', info.get('y', 0)))
            return price
    except Exception:
        pass
    return None

def fetch_yahoo_stock_news():
    news_items = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # 優先抓取 Google News RSS 免費來源
    try:
        import xml.etree.ElementTree as ET
        rss_url = "https://news.google.com/rss/search?q=外資+目標價+台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        res_rss = requests.get(rss_url, headers=headers, timeout=10)
        if res_rss.status_code == 200:
            root = ET.fromstring(res_rss.text)
            for item in root.findall('.//item')[:15]:
                title = item.find('title').text
                if title:
                    clean_title = re.sub(r'\s*-\s*[^-]+$', '', title)
                    news_items.append({"title": clean_title})
    except Exception as e:
        print(f"RSS 新聞抓取失敗: {e}")

    return news_items

def parse_target_price_from_title(title):
    # 1. 先確認新聞標題中是否帶有「%」或「百分之」，避免把「毛利率90%」或「狂升155%」抓成目標價
    # 先清理掉所有跟「%」相關的數字字串
    clean_title = re.sub(r'\d+(?:\.\d+)?\s*[%％％]', '', title)
    clean_title = re.sub(r'\d+(?:\.\d+)?\s*成', '', clean_title)

    # 2. 自動比對代號與公司真實名稱
    stock_id = ""
    stock_name = ""
    
    # 先找括號內的 4 位數字代號
    stock_id_match = re.search(r'\(?(\d{4})(?:-TW)?\)?', clean_title)
    if stock_id_match:
        stock_id = stock_id_match.group(1)

    # 搜尋對照表中的特徵關鍵字
    for kw, (code, name) in KEYWORD_MAPPING.items():
        if kw in clean_title:
            if not stock_id:
                stock_id = code
            stock_name = name
            break

    # 若未對應到，給預設文字
    if not stock_name:
        stock_name = f"個股({stock_id})" if stock_id else "熱門個股"

    # 3. 抓取券商/機構名稱
    broker_match = re.search(r'(Factset|FactSet|外資|大摩|小摩|高盛|美銀|野村|麥格理|瑞銀|元大|凱基|富邦|永豐|群益|統一|中信|花旗)', clean_title, re.IGNORECASE)
    broker_name = broker_match.group(1) if broker_match else "法人/外資"

    # 4. 精準抓取目標價（必須帶有「目標價/上看/喊至/喊上/調升至」等動作字，且過濾非價格數字）
    price_match = re.search(r'(?:目標價|上看|喊上|喊至|調升至|調高至|叫價|喊到)\s*:?\s*(\d+(?:\.\d+)?)\s*元?', clean_title)
    
    if price_match:
        target_price = float(price_match.group(1))
        # 排除不合理過小的價格數字（避免誤抓小數點 EPS 或微幅變動）
        if target_price > 10 and target_price < 30000:
            return {
                "stock_id": stock_id,
                "stock_name": stock_name,
                "broker": broker_name,
                "target_price": target_price,
                "title": title
            }
            
    return None

def run_tracker():
    print("開始執行新聞掃描...")
    news_list = fetch_yahoo_stock_news()
    print(f"共成功抓取到 {len(news_list)} 條新聞")
    
    parsed_reports = []
    seen_keys = set()
    seen_titles = set()
    
    for news in news_list:
        t = news['title']
        if t in seen_titles:
            continue
        seen_titles.add(t)
        
        parsed = parse_target_price_from_title(t)
        if parsed:
            dedup_key = f"{parsed['stock_name']}_{parsed['target_price']}"
            if dedup_key not in seen_keys:
                parsed_reports.append(parsed)
                seen_keys.add(dedup_key)
            
    msg_lines = ["🤖 **[全自動新聞外資目標價動態掃描]**\n"]
    
    if parsed_reports:
        for item in parsed_reports:
            stock_id = item['stock_id']
            stock_name = item['stock_name']
            target_price = item['target_price']
            broker = item['broker']
            title = item['title']
            
            current_price = get_realtime_stock_price(stock_id) if stock_id else None
            
            if current_price and current_price > 0:
                upside_pct = ((target_price - current_price) / current_price) * 100
                msg_lines.append(
                    f"📈 **{stock_id if stock_id else ''} {stock_name}** ({broker})\n"
                    f"• 最新收盤價：`{current_price:,.1f}` 元\n"
                    f"• 新聞目標價：`{target_price:,.1f}` 元\n"
                    f"• 潛在隱含漲幅：▲ **{upside_pct:.1f}%**\n"
                    f"• 來源：{title}\n"
                )
            else:
                msg_lines.append(
                    f"📈 **{stock_id if stock_id else ''} {stock_name}** ({broker})\n"
                    f"• 新聞目標價：`{target_price:,.1f}` 元\n"
                    f"• 來源：{title}\n"
                )
    else:
        msg_lines.append("今日暫無符合「明確目標價數字」之新聞。\n")
        if news_list:
            msg_lines.append("**最新掃描的新聞標題摘要：**")
            shown_summary = set()
            count = 0
            for n in news_list:
                clean_title = n['title'].replace('*', '').replace('_', '').replace('`', '')
                if clean_title not in shown_summary:
                    msg_lines.append(f"• {clean_title}")
                    shown_summary.add(clean_title)
                    count += 1
                if count >= 5:
                    break
        else:
            msg_lines.append("⚠️ 暫無擷取到最新新聞列表。")
        
    full_msg = "\n".join(msg_lines)
    send_tg_message(full_msg)
    print("執行完畢！")

if __name__ == "__main__":
    run_tracker()



