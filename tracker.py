import os
import requests
import json
import re

# 從 GitHub Secrets 取得金鑰
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_tg_message(message):
    """發送訊息至 Telegram Bot"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("未設定 Telegram Token 或 Chat ID")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"發送 Telegram 訊息失敗: {e}")

def get_realtime_stock_price(stock_id):
    """取得證交所當日收盤價/最新價"""
    try:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock_id}.tw"
        res = requests.get(url, timeout=10)
        data = res.json()
        if 'msgArray' in data and len(data['msgArray']) > 0:
            info = data['msgArray'][0]
            price = float(info.get('z', info.get('y', 0)))
            return price
    except Exception as e:
        print(f"無法取得 {stock_id} 當前股價: {e}")
    return None

def fetch_anue_broker_news(keyword="目標價"):
    """
    自鉅亨網 (Anue) API 自動搜尋最新「目標價/外資/評等」新聞
    """
    news_items = []
    try:
        url = f"https://news.cnyes.com/api/v3/news/keyword?keyword={keyword}&page=1&limit=15"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            items = res.json().get('items', {}).get('data', [])
            for item in items:
                title = item.get('title', '')
                news_id = item.get('newsId', '')
                news_url = f"https://news.cnyes.com/news/id/{news_id}"
                news_items.append({"title": title, "url": news_url})
    except Exception as e:
        print(f"爬取鉅亨網新聞失敗: {e}")
    return news_items

def parse_target_price_from_title(title):
    """
    全台股通用解析版本：自動辨識任何 4 位數字股票代號與目標價
    例如：「外資看好台積電(2330)目標價喊上1280元」、「大摩調升聯達(6500)目標價至250元」
    """
    # 1. 自動抓取新聞中的 4 位數股票代號（例如 2330, 2317）
    stock_id_match = re.search(r'\(?(\d{4})\)?', title)
    # 2. 自動抓取券商名稱
    broker_match = re.search(r'(外資|大摩|小摩|高盛|美銀|野村|麥格理|瑞銀|元大|凱基|富邦|永豐|群益)', title)
    # 3. 自動抓取目標價數字
    price_match = re.search(r'(?:目標價|上看|喊上|調升至|調高至)\s*(\d{2,5})\s*元', title)
    
    if price_match:
        stock_id = stock_id_match.group(1) if stock_id_match else ""
        broker_name = broker_match.group(1) if broker_match else "法人/外資"
        target_price = float(price_match.group(1))
        
        # 從標題中擷取股票名稱（去除常見介詞）
        clean_title = re.sub(r'(外資|大摩|小摩|高盛|美銀|野村|麥格理|瑞銀)', '', title)
        
        return {
            "stock_id": stock_id,
            "stock_name": f"股票({stock_id})" if stock_id else "熱門焦點股",
            "broker": broker_name,
            "target_price": target_price,
            "title": title
        }
    return None

def run_tracker():
    print("開始執行全自動新聞目標價掃描...")
    
    # 1. 自動抓取最新新聞
    news_list = fetch_anue_broker_news(keyword="目標價")
    
    parsed_reports = []
    seen_stocks = set()
    
    for news in news_list:
        parsed = parse_target_price_from_title(news['title'])
        if parsed and parsed['stock_name'] not in seen_stocks:
            parsed_reports.append(parsed)
            seen_stocks.add(parsed['stock_name'])
            
    msg_lines = ["🤖 **[全自動新聞外資目標價動態掃描]**\n"]
    
    if parsed_reports:
        for item in parsed_reports:
            stock_id = item['stock_id']
            stock_name = item['stock_name']
            target_price = item['target_price']
            broker = item['broker']
            
            current_price = get_realtime_stock_price(stock_id) if stock_id else None
            
            if current_price and current_price > 0:
                upside_pct = ((target_price - current_price) / current_price) * 100
                msg_lines.append(
                    f"📈 **{stock_id} {stock_name}** ({broker})\n"
                    f"• 最新收盤價：`{current_price:,.1f}` 元\n"
                    f"• 新聞目標價：`{target_price:,.0f}` 元\n"
                    f"• 潛在隱含漲幅：▲ **{upside_pct:.1f}%**\n"
                    f"• 來源新聞：{item['title']}\n"
                )
            else:
                msg_lines.append(
                    f"📈 **{stock_name}** ({broker})\n"
                    f"• 新聞目標價：`{target_price:,.0f}` 元\n"
                    f"• 來源新聞：{item['title']}\n"
                )
    else:
        msg_lines.append("今日新聞中暫無最新自動解析之目標價變動。")
        
    full_msg = "\n".join(msg_lines)
    send_tg_message(full_msg)
    print("發送完畢！")

if __name__ == "__main__":
    run_tracker()
