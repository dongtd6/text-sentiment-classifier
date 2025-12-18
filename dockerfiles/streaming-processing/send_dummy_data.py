#!/usr/bin/env python3
import os
import random
import time
from datetime import datetime
import requests

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ASSETS = ["BTC", "ETH", "USDT"]
TRADE_TYPES = ["BUY", "SELL"]
STATUSES = ["PENDING", "COMPLETED"]
COUNTER_PARTS = ["Trader101", "Trader202", "Trader303"]

def now():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def send():
    asset = random.choice(ASSETS)
    trade_type = random.choice(TRADE_TYPES)

    trade_icon = "🟢" if trade_type == "BUY" else "🔴"
    event_icon = "🆕"

    order_id = f"ORD-{int(time.time())}"
    amount = round(random.uniform(0.001, 0.02), 6)
    unit_price = round(random.uniform(900_000_000, 1_200_000_000), 2)
    total_price = round(amount * unit_price, 2)

    message = (
        f"{event_icon} C2C TRADE ALERT {trade_icon}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 Order ID : {order_id}\n"
        f"🔁 Type     : {trade_type}\n"
        f"💰 Asset   : {asset}\n"
        f"📦 Amount  : {amount} {asset}\n"
        f"💵 Price   : {unit_price} VND\n"
        f"💲 Total   : {total_price} VND\n"
        f"📌 Status  : {random.choice(STATUSES)}\n"
        f"👤 Partner : {random.choice(COUNTER_PARTS)}\n"
        f"🕒 Time    : {now()}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    r = requests.post(url, json=payload, timeout=10)
    r.raise_for_status()

if __name__ == "__main__":
    print("🚀 Sending dummy C2C trades with icons to Telegram...")
    while True:
        try:
            send()
            print("✅ Sent")
        except Exception as e:
            print("❌ Error:", e)
        time.sleep(5)
