import os
import requests
import pandas as pd

# 從 GitHub Secrets 取得金鑰
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_tg_message(message):
    """發送訊息至 Telegram Bot"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def get_realtime_stock_price(stock_id):
    """
    透過證交所 / 富果 / Open API 獲取真實收盤價
    (此處示範透過台灣證交所 API 獲取個股即時/當日收盤價)
    """
    try:
        url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock_id}.tw"
        res = requests.get(url, timeout=10)
        data = res.json()
        if 'msgArray' in data and len(data['msgArray']) > 0:
            info = data['msgArray'][0]
            # 'z' 為當日收盤價或最新成交價，若無則取 'y' (昨日收盤價)
            price = float(info.get('z', info.get('y', 0)))
            return price
    except Exception as e:
        print(f"無法取得 {stock_id} 當前股價: {e}")
    return None

def run_tracker():
    print("開始執行真實數據目標價追蹤...")
    
    # 在此處設定追蹤清單，或串接富邦/鉅亨網/FinMind 之券商研報調升 API
    # 範例列出核心追蹤個股與最新券商報告目標價 (可定期更新或由爬蟲自動帶入)
    target_reports = [
        {"stock_id": "2330", "name": "台積電", "broker": "摩根士丹利", "target_price": 1280, "rating": "買進"},
        {"stock_id": "2454", "name": "聯發科", "broker": "美銀證券", "target_price": 1500, "rating": "買進"},
    ]
    
    msg_lines = ["🚀 **[每日券商目標價與隱含漲幅追蹤]**\n"]
    
    for item in target_reports:
        stock_id = item['stock_id']
        current_price = get_realtime_stock_price(stock_id)
        
        if current_price and current_price > 0:
            target_price = item['target_price']
            # 計算隱含漲幅 = (目標價 - 當前收盤價) / 當前收盤價
            upside_pct = ((target_price - current_price) / current_price) * 100
            
            msg_lines.append(
                f"📈 **{stock_id} {item['name']}** ({item['broker']})\n"
                f"• 最新收盤價：`{current_price:,.1f}` 元\n"
                f"• 券商目標價：`{target_price:,.0f}` 元\n"
                f"• 評等：{item['rating']}\n"
                f"• 潛在隱含漲幅：▲ **{upside_pct:.1f}%**\n"
            )
        else:
            msg_lines.append(f"⚠️ **{stock_id} {item['name']}**：暫時無法取得最新收盤價\n")
            
    if len(msg_lines) > 1:
        full_msg = "\n".join(msg_lines)
        send_tg_message(full_msg)
        print("最新真實價格警報已發送！")

if __name__ == "__main__":
    run_tracker()

