"""
Telegram Bot with HTTP Health Check for Render
Prevents Render free tier from spinning down by providing a health endpoint
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

from aiohttp import web

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from bot import TelegramBot

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
        logger.info("Bot instance created successfully")

        # Initialize the bot application properly
        await bot_instance.application.initialize()
        await bot_instance.application.start()
        await bot_instance.application.updater.start_polling()
        logger.info("Bot started successfully with polling")

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        import traceback

        logger.error(f"Full traceback: {traceback.format_exc()}")


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
    logger.info("Starting Telegram bot with HTTP health check...")

    app = await init_app()

    # Start the web server
    runner = web.AppRunner(app)
    await runner.setup()

    # Use port 10000 (Render's default for free tier)
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    logger.info("HTTP server started on port 10000")
    logger.info("Health check available at: http://localhost:10000/health")
    logger.info("Bot is running and ready to receive messages!")

    # Keep the server running
    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        # Clean up bot
        if bot_instance:
            try:
                await bot_instance.application.updater.stop()
                await bot_instance.application.stop()
                await bot_instance.application.shutdown()
                logger.info("Bot shutdown completed")
            except Exception as e:
                logger.error(f"Error during bot shutdown: {e}")

        # Clean up web server
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
