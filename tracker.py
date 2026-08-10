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

def fetch_anue_broker_news():
    news_items = []
    # 使用多個關鍵字交替搜尋，避免單一關鍵字落空
    keywords = ["目標價", "外資喊"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for kw in keywords:
        try:
            url = f"https://news.cnyes.com/api/v3/news/keyword?keyword={kw}&page=1&limit=15"
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
    # 抓取 4 位數股票代號 (相容 1216-TW, 1216, (1216))
    stock_id_match = re.search(r'\(?(\d{4})(?:-TW)?\)?', title)
    # 抓取股票名稱
    stock_name_match = re.search(r'：([^\(\:]+)\(\d{4}', title)
    # 抓取券商/機構名稱
    broker_match = re.search(r'(Factset|FactSet|外資|大摩|小摩|高盛|美銀|野村|麥格理|瑞銀|元大|凱基|富邦|永豐|群益)', title, re.IGNORECASE)
    # 抓取目標價數字（支援小數點）
    price_match = re.search(r'(?:目標價|上看|喊上|調升至|調高至|為)\s*(\d+(?:\.\d+)?)\s*元', title)
    
    if price_match:
        stock_id = stock_id_match.group(1) if stock_id_match else ""
        stock_name = stock_name_match.group(1) if stock_name_match else (f"股票({stock_id})" if stock_id else "焦點股")
        broker_name = broker_match.group(1) if broker_match else "法人/外資"
        target_price = float(price_match.group(1))
        
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
    
    parsed_reports = []
    seen_stocks = set()
    seen_titles = set()
    
    for news in news_list:
        if news['title'] in seen_titles:
            continue
        seen_titles.add(news['title'])
        
        parsed = parse_target_price_from_title(news['title'])
        if parsed and parsed['stock_id'] and parsed['stock_id'] not in seen_stocks:
            parsed_reports.append(parsed)
            seen_stocks.add(parsed['stock_id'])
            
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
                    f"📈 **{stock_id} {stock_name}** ({broker})\n"
                    f"• 最新收盤價：`{current_price:,.1f}` 元\n"
                    f"• 新聞目標價：`{target_price:,.1f}` 元\n"
                    f"• 潛在隱含漲幅：▲ **{upside_pct:.1f}%**\n"
                    f"• 來源：{title}\n"
                )
            else:
                msg_lines.append(
                    f"📈 **{stock_id} {stock_name}** ({broker})\n"
                    f"• 新聞目標價：`{target_price:,.1f}` 元\n"
                    f"• 來源：{title}\n"
                )
    else:
        msg_lines.append("今日暫無符合「明確目標價數字」之新聞。\n")
        if news_list:
            msg_lines.append("**最新掃描的新聞標題摘要：**")
            # 取前 5 則不重複的新聞摘要顯示
            display_count = 0
            shown_summary = set()
            for n in news_list:
                clean_title = n['title'].replace('*', '').replace('_', '')
                if clean_title not in shown_summary:
                    msg_lines.append(f"• {clean_title}")
                    shown_summary.add(clean_title)
                    display_count += 1
                if display_count >= 5:
                    break
        
    full_msg = "\n".join(msg_lines)
    send_tg_message(full_msg)

if __name__ == "__main__":
    run_tracker()
