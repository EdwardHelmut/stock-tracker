import os
import requests
import json
import re
from urllib.parse import quote

# 從 GitHub Secrets 取得金鑰
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# 常見熱門股對照表（當新聞未寫出4位代號時自動對應）
STOCK_MAP = {
    "台積電": "2330", "聯發科": "2454", "鴻海": "2317", "廣達": "2382",
    "緯創": "3231", "技嘉": "2376", "長榮": "2603", "陽明": "2609",
    "台達電": "2308", "富邦金": "2881", "國泰金": "2882", "中信金": "2891",
    "世芯": "3661", "創意": "3443", "緯穎": "6669", "祥碩": "5269",
    "奇鋐": "3017", "雙鴻": "3324", "智邦": "2345", "瑞昱": "2379"
}

def send_tg_message(message):
    """發送訊息至 Telegram Bot"""
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
        res = requests.post(url, json=payload, timeout=10)
        print(f"Telegram 發送狀態: {res.status_code}")
    except Exception as e:
        print(f"Telegram 發送失敗: {e}")

def get_realtime_stock_price(stock_id):
    """取得證交所當日收盤價"""
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

def fetch_anue_broker_news():
    """爬取鉅亨網新聞（支援中文字串 URL 自動轉碼）"""
    news_items = []
    keywords = ["目標價", "外資", "評等"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for kw in keywords:
        try:
            # 關鍵字中文必須經過 quote 轉碼
            encoded_kw = quote(kw)
            url = f"https://news.cnyes.com/api/v3/news/keyword?keyword={encoded_kw}&page=1&limit=15"
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                items = res.json().get('items', {}).get('data', [])
                for item in items:
                    title = item.get('title', '')
                    if title:
                        news_items.append({"title": title, "newsId": item.get('newsId', '')})
        except Exception as e:
            print(f"爬取新聞({kw})失敗: {e}")
            
    return news_items

def parse_target_price_from_title(title):
    """放寬匹配邏輯，支援多種新聞標題格式"""
    # 1. 嘗試抓取 4 位數股票代號
    stock_id_match = re.search(r'\(?(\d{4})(?:-TW)?\)?', title)
    stock_id = stock_id_match.group(1) if stock_id_match else ""
    
    # 2. 嘗試比對股票名稱
    stock_name = "焦點股"
    for name, code in STOCK_MAP.items():
        if name in title:
            stock_name = name
            if not stock_id:
                stock_id = code
            break
            
    if not stock_id and stock_name == "焦點股":
        # 嘗試從鉅亨網標題提取名稱 (例如 統一(1216-TW))
        name_extract = re.search(r'：([^\(\:]+)\(\d{4}', title)
        if name_extract:
            stock_name = name_extract.group(1).strip()

    # 3. 抓取券商/機構名稱
    broker_match = re.search(r'(Factset|FactSet|外資|大摩|小摩|高盛|美銀|野村|麥格理|瑞銀|元大|凱基|富邦|永豐|群益|統一|中信)', title, re.IGNORECASE)
    broker_name = broker_match.group(1) if broker_match else "法人/外資"

    # 4. 超強放寬目標價數字抓取（相容 1280元、1280、723.5、喊至1280 等）
    price_match = re.search(r'(?:目標價|上看|喊上|喊至|調升至|調高至|為|上看|高至|估)\s*:?\s*(\d+(?:\.\d+)?)\s*元?', title)
    
    if price_match:
        target_price = float(price_match.group(1))
        # 過濾掉太小或不合常理的數字（避免誤抓 EPS 或百分比）
        if target_price > 10 and target_price < 20000:
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
    news_list = fetch_anue_broker_news()
    print(f"共抓取到 {len(news_list)} 條新聞")
    
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
            # 以 股票名稱+目標價 作為唯一值去重
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
            msg_lines.append("⚠️ 目前未擷取到任何新聞列表，請檢查 API 連線狀態。")
        
    full_msg = "\n".join(msg_lines)
    send_tg_message(full_msg)
    print("程式執行完畢，訊息已發送至 Telegram。")

if __name__ == "__main__":
    run_tracker()

