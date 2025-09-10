#!/usr/bin/env python3
"""
Simple test to verify bot token works
"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()


def test_bot():
    bot_token = os.getenv("BOT_TOKEN")

    if not bot_token:
        print("❌ BOT_TOKEN not found in .env file")
        return False

    print(f"🔍 Testing bot token: {bot_token[:10]}...")

    # Test getMe
    try:
        response = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe")
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                bot_info = result["result"]
                print(
                    f"✅ Bot found: {bot_info['first_name']} (@{bot_info['username']})"
                )
                return True
            else:
                print(f"❌ Bot API error: {result}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_bot()
