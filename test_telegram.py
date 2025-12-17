#!/usr/bin/env python3
"""
Simple Telegram Bot Test Script
Sends a test message to verify bot token and chat ID are working
"""

import os
import sys
import requests
from datetime import datetime

def send_test_message():
    """Send a test message to Telegram"""
    
    # Get credentials from environment
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("❌ Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        print("\nUsage:")
        print("  export TELEGRAM_BOT_TOKEN='your_bot_token'")
        print("  export TELEGRAM_CHAT_ID='your_chat_id'")
        print("  python3 test_telegram.py")
        return False
    
    print("=" * 70)
    print("🧪 Testing Telegram Bot Connection")
    print("=" * 70)
    print(f"Bot Token: {bot_token[:10]}...")
    print(f"Chat ID: {chat_id}")
    print()
    
    # Test message
    message = (
        f"🧪 *Telegram Bot Test*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Connection successful!\n"
        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🤖 Bot is working correctly\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"\n"
        f"Ready to receive C2C trade notifications! 🚀"
    )
    
    # Telegram API endpoint
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        print("📤 Sending test message...")
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("ok"):
            print("✅ Message sent successfully!")
            print()
            print("Response details:")
            print(f"  Message ID: {result['result']['message_id']}")
            print(f"  Chat ID: {result['result']['chat']['id']}")
            print(f"  Chat Type: {result['result']['chat']['type']}")
            print()
            print("=" * 70)
            print("✅ Telegram bot is configured correctly!")
            print("=" * 70)
            return True
        else:
            print(f"❌ Telegram API returned error: {result}")
            return False
            
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        print(f"   Response: {e.response.text}")
        print()
        print("Common issues:")
        print("  - Invalid bot token")
        print("  - Bot blocked by user")
        print("  - Invalid chat ID")
        return False
    except requests.exceptions.Timeout:
        print("❌ Request timeout - check your internet connection")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = send_test_message()
    sys.exit(0 if success else 1)

