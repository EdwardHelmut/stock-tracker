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

def run_tracker():
    print("開始執行目標價追蹤...")
    
    # 模擬爬取到的法人目標價變動資料
    # 實務上可在此串接 FinMind API 或 BeautifulSoup 爬取新聞/網頁
    data = [
        {"stock": "2330 台積電", "broker": "摩根士丹利", "old_price": 1080, "new_price": 1280, "rating": "買進"},
        {"stock": "2454 聯發科", "broker": "美銀證券", "old_price": 1300, "new_price": 1500, "rating": "買進"},
    ]
    
    msg_lines = ["🚀 **[今日券商目標價調升警報]**\n"]
    
    for item in data:
        diff_pct = ((item['new_price'] - item['old_price']) / item['old_price']) * 100
        # 條件過濾：僅篩選調升幅度大於 10% 的標的
        if diff_pct >= 10:
            msg_lines.append(
                f"📈 **{item['stock']}** ({item['broker']})\n"
                f"• 評等：{item['rating']}\n"
                f"• 目標價：`{item['old_price']}` ➔ `{item['new_price']}` (▲ {diff_pct:.1f}%)\n"
            )
            
    if len(msg_lines) > 1:
        full_msg = "\n".join(msg_lines)
        send_tg_message(full_msg)
        print("警報已發送！")
    else:
        print("今日無符合過濾條件的目標價變動。")

if __name__ == "__main__":
    run_tracker()
