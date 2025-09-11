"""
Refactored Telegram Bot - Clean separation of concerns
"""

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from config.settings import BOT_TOKEN
from handlers.admin_handlers import AdminHandlers
from handlers.user_handlers import (
    WAITING_FOR_ANSWER,
    WAITING_FOR_EXPLANATION,
    ApplicationHandlers,
)
from messages.texts import COMMAND_START_DESC


class TelegramBot:
    """Main bot class - orchestrates handlers and application setup"""

    def __init__(self):
        # Configure HTTP client with higher timeouts for Render environment
        http_request = HTTPXRequest(
            connect_timeout=60.0,
            read_timeout=120.0,
            write_timeout=60.0,
            pool_timeout=30.0,
        )
        self.application = (
            Application.builder().token(BOT_TOKEN).request(http_request).build()
        )

        # Initialize handlers
        self.app_handlers = ApplicationHandlers()
        self.admin_handlers = AdminHandlers()

        self.setup_handlers()

    def setup_handlers(self):
        """Setup all bot handlers"""
        # Start command handler
        start_handler = CommandHandler("start", self.app_handlers.start_command)

        # Main conversation handler
        main_conversation = ConversationHandler(
            entry_points=[start_handler],
            states={
                WAITING_FOR_EXPLANATION: [
                    CallbackQueryHandler(
                        self.app_handlers.handle_option_selection, pattern="^option_"
                    ),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.app_handlers.handle_explanation,
                    ),
                ],
                WAITING_FOR_ANSWER: [
                    CallbackQueryHandler(
                        self.app_handlers.handle_back_button, pattern="^back$"
                    ),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.app_handlers.handle_answer
                    ),
                    CallbackQueryHandler(
                        self.app_handlers.handle_complete_application,
                        pattern="^complete$",
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.app_handlers.cancel_application)],
        )

        # Admin approval handlers
        approve_handler = CallbackQueryHandler(
            self.admin_handlers.approve_request, pattern="^approve_"
        )
        decline_handler = CallbackQueryHandler(
            self.admin_handlers.decline_request, pattern="^decline_"
        )

        # Add handlers
        self.application.add_handler(main_conversation)
        self.application.add_handler(approve_handler)
        self.application.add_handler(decline_handler)

        # Set bot commands
        self.application.post_init = self.set_bot_commands

        # Add error handler
        self.application.add_error_handler(self.error_handler)

    async def set_bot_commands(self, application):
        """Set bot commands menu"""
        commands = [BotCommand("start", COMMAND_START_DESC)]
        try:
            await application.bot.set_my_commands(commands)
        except Exception:
            pass

    async def error_handler(self, update, context):
        """Handle errors that occur during bot operation"""
        from telegram.error import NetworkError, TimedOut

        error = context.error
        print(f"Bot error: {error}")

        # Handle specific error types
        if isinstance(error, (TimedOut, NetworkError)):
            print(f"Network/timeout error: {error}")
        else:
            print(f"Unexpected error: {error}")

        # Try to notify user if possible
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "Sorry, there was a temporary issue. Please try again in a moment."
                )
            except Exception:
                pass

    async def run(self):
        """Run the bot"""
        await self.application.run_polling()


if __name__ == "__main__":
    bot = TelegramBot()
    bot.application.run_polling()
