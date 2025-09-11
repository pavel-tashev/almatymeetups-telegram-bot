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

from handlers.admin_handlers import AdminHandlers
from config.settings import BOT_TOKEN
from messages.texts import COMMAND_START_DESC
from handlers.user_handlers import (
    WAITING_FOR_ANSWER,
    WAITING_FOR_EXPLANATION,
    ApplicationHandlers,
)


class TelegramBot:
    """Main bot class - orchestrates handlers and application setup"""

    def __init__(self):
        # Configure HTTP client with higher timeouts to avoid startup TimedOut
        http_request = HTTPXRequest(
            connect_timeout=20.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=10.0,
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

    async def set_bot_commands(self, application):
        """Set bot commands menu"""
        commands = [BotCommand("start", COMMAND_START_DESC)]
        try:
            await application.bot.set_my_commands(commands)
        except Exception:
            pass

    async def run(self):
        """Run the bot"""
        await self.application.run_polling()


if __name__ == "__main__":
    bot = TelegramBot()
    bot.application.run_polling()
