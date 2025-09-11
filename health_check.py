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
    return web.json_response(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "bot_active": bot_instance is not None,
        }
    )


async def start_bot():
    """Start the Telegram bot"""
    global bot_instance
    try:
        bot_instance = TelegramBot()

        # Initialize the bot application properly
        await bot_instance.application.initialize()
        await bot_instance.application.start()
        await bot_instance.application.updater.start_polling()

    except Exception as e:
        # Log the error for debugging
        print(f"Failed to start bot: {e}")
        # Don't re-raise to allow the health check server to continue
        pass


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
