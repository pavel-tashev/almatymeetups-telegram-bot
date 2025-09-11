"""
Telegram Bot with HTTP Health Check for Render
Prevents Render free tier from spinning down by providing a health endpoint
"""

import asyncio
import os
import sys
from datetime import datetime

from aiohttp import web

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from bot import TelegramBot

# Global bot instance
bot_instance = None


async def health_check(request):
    """Health check endpoint - Render will ping this to keep instance alive"""
    bot_status = "active" if bot_instance is not None else "inactive"

    return web.json_response(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "bot_status": bot_status,
            "bot_active": bot_instance is not None,
        }
    )


async def start_bot():
    """Start the Telegram bot with conflict handling"""
    global bot_instance
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            print(f"Attempting to start bot (attempt {attempt + 1}/{max_retries})")
            bot_instance = TelegramBot()

            # Initialize the bot application properly
            await bot_instance.application.initialize()
            await bot_instance.application.start()
            await bot_instance.application.updater.start_polling()

            print("Bot started successfully!")
            return

        except Exception as e:
            print(f"Failed to start bot (attempt {attempt + 1}/{max_retries}): {e}")

            # If it's a conflict error, wait longer before retrying
            if "Conflict" in str(e) or "terminated by other getUpdates" in str(e):
                if attempt < max_retries - 1:
                    print(
                        f"Conflict detected, waiting {retry_delay} seconds before retry..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print("Max retries reached for conflict resolution")
            else:
                # For other errors, don't retry
                break

    print(
        "Failed to start bot after all retries. Health check server will continue without bot."
    )


async def init_app():
    """Initialize the web application"""
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/", health_check)  # Root endpoint

    # Start the bot when the app starts
    await start_bot()

    return app


async def main():
    """Main function - starts both HTTP server and Telegram bot"""
    app = await init_app()

    # Start the web server
    runner = web.AppRunner(app)
    await runner.setup()

    # Use port 10000 (Render's default for free tier)
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    # Keep the server running
    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        pass
    finally:
        # Clean up bot
        if bot_instance:
            try:
                await bot_instance.application.updater.stop()
                await bot_instance.application.stop()
                await bot_instance.application.shutdown()
            except Exception:
                pass

        # Clean up web server
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
