"""
Keep-alive script to prevent Render free tier from spinning down
Uses a simple HTTP server that can be pinged externally
"""

import asyncio
import logging
from datetime import datetime

from aiohttp import web

from src.bot import TelegramBot

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global bot instance
bot_instance = None


async def health_check(request):
    """Health check endpoint"""
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
        logger.info("Bot instance created successfully")

        # Start the bot in the background
        asyncio.create_task(bot_instance.run())
        logger.info("Bot started successfully")

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")


async def init_app():
    """Initialize the web application"""
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/", health_check)  # Root endpoint

    # Start the bot when the app starts
    await start_bot()

    return app


async def main():
    """Main function"""
    logger.info("Starting keep-alive service with HTTP server...")

    app = await init_app()

    # Start the web server
    runner = web.AppRunner(app)
    await runner.setup()

    # Use port 10000 (Render's default for free tier)
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    logger.info("HTTP server started on port 10000")
    logger.info("Health check available at: http://localhost:10000/health")

    # Keep the server running
    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
