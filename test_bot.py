#!/usr/bin/env python3
"""
Simple test script to verify bot configuration and database setup
"""

import os
import sys

from dotenv import load_dotenv


def test_environment():
    """Test if all required environment variables are set"""
    load_dotenv()

    required_vars = ["BOT_TOKEN", "ADMIN_CHAT_ID", "TARGET_GROUP_ID"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please create a .env file with the required variables.")
        return False

    print("✅ All environment variables are set")
    return True


def test_database():
    """Test database initialization"""
    try:
        from database import Database

        db = Database()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False


def test_questions():
    """Test questions configuration"""
    try:
        from questions import get_all_questions

        questions = get_all_questions()
        if len(questions) > 0:
            print(f"✅ Questions loaded successfully ({len(questions)} questions)")
            return True
        else:
            print("❌ No questions found")
            return False
    except Exception as e:
        print(f"❌ Questions loading failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🧪 Testing Telegram Bot Configuration\n")

    tests = [
        ("Environment Variables", test_environment),
        ("Database", test_database),
        ("Questions", test_questions),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"Testing {test_name}...")
        if test_func():
            passed += 1
        print()

    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Your bot is ready to run.")
        return 0
    else:
        print("❌ Some tests failed. Please fix the issues before running the bot.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
