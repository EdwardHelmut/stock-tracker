import os
import requests
import json
import re

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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

def fetch_anue_broker_news(keyword="目標價"):
    news_items = []
    try:
        url = f"https://news.cnyes.com/api/v3/news/keyword?keyword={keyword}&page=1&limit=20"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            items = res.json().get('items', {}).get('data', [])
            for item in items:
                title = item.get('title', '')
                # 同時抓取新聞內文簡介 (summary)
                summary = item.get('summary', '')
                full_text = f"{title} {summary}"
                news_items.append({"title": title, "full_text": full_text})
    except Exception as e:
        print(f"爬取新聞失敗: {e}")
    return news_items

def parse_target_price_from_title(title):
    # 擴充匹配規則：支援更多動詞與格式
    stock_id_match = re.search(r'\(?(\d{4})\)?', title)
    broker_match = re.search(r'(外資|大摩|小摩|高盛|美銀|野村|麥格理|瑞銀|元大|凱基|富邦|永豐|群益|國泰)', title)
    # 匹配「目標價/上看/喊至/調高到 數字」
    price_match = re.search(r'(?:目標價|上看|喊上|調升至|調高至|上攻|升至)\s*(\d{2,5})\s*元?', title)
    
    if price_match:
        stock_id = stock_id_match.group(1) if stock_id_match else ""
        broker_name = broker_match.group(1) if broker_match else "法人/外資"
        target_price = float(price_match.group(1))
        
        return {
            "stock_id": stock_id,
            "broker": broker_name,
            "target_price": target_price,
            "title": title
        }
    return None

def run_tracker():
    print("開始執行新聞掃描...")
    news_list = fetch_anue_broker_news(keyword="目標價")
    
    parsed_reports = []
    seen_titles = set()
    
    for news in news_list:
        parsed = parse_target_price_from_title(news['title'])
        if parsed and parsed['title'] not in seen_titles:
            parsed_reports.append(parsed)
            seen_titles.add(parsed['title'])
            
    msg_lines = ["🤖 **[全自動新聞外資目標價動態掃描]**\n"]
    
    if parsed_reports:
        for item in parsed_reports:
            stock_id = item['stock_id']
            target_price = item['target_price']
            broker = item['broker']
            title = item['title']
            
            current_price = get_realtime_stock_price(stock_id) if stock_id else None
            
            if current_price and current_price > 0:
                upside_pct = ((target_price - current_price) / current_price) * 100
                msg_lines.append(
                    f"📈 **代號: {stock_id}** ({broker})\n"
                    f"• 最新收盤價：`{current_price:,.1f}` 元\n"
                    f"• 新聞目標價：`{target_price:,.0f}` 元\n"
                    f"• 潛在隱含漲幅：▲ **{upside_pct:.1f}%**\n"
                    f"• 來源：{title}\n"
                )
            else:
                msg_lines.append(
                    f"📈 **熱門焦點股** ({broker})\n"
                    f"• 新聞目標價：`{target_price:,.0f}` 元\n"
                    f"• 來源：{title}\n"
                )
    else:
        # 偵錯優化：當沒有解析到目標價時，列出最新 3 則新聞標題供查驗
        msg_lines.append("今日暫無符合「明確目標價數字」之新聞。\n\n**最新掃描的新聞標題摘要：**")
        for n in news_list[:3]:
            msg_lines.append(f"• {n['title']}")
        
    full_msg = "\n".join(msg_lines)
    send_tg_message(full_msg)

if __name__ == "__main__":
    run_tracker()

