from telegram import BotCommand, Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
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
from messages.texts import (
    ACTION_NOT_AVAILABLE,
    COMMAND_HELP_DESC,
    COMMAND_START_DESC,
    TEMPORARY_ERROR_MSG,
)


class TelegramBot:
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
        # Create conversation handler
        start_handler = CommandHandler("start", self.app_handlers.start_command)

        conversation_handler = ConversationHandler(
            entry_points=[start_handler],
            states={
                WAITING_FOR_EXPLANATION: [
                    CallbackQueryHandler(
                        self.app_handlers.handle_option_selection, pattern="^option_"
                    ),
                    CallbackQueryHandler(
                        self.app_handlers.handle_back_button, pattern="^back$"
                    ),
                    CallbackQueryHandler(
                        self.app_handlers.handle_complete_application,
                        pattern="^complete$",
                    ),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.app_handlers.handle_explanation,
                    ),
                ],
                WAITING_FOR_ANSWER: [
                    CallbackQueryHandler(
                        self.app_handlers.handle_option_selection, pattern="^option_"
                    ),
                    CallbackQueryHandler(
                        self.app_handlers.handle_back_button, pattern="^back$"
                    ),
                    CallbackQueryHandler(
                        self.app_handlers.handle_complete_application,
                        pattern="^complete$",
                    ),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.app_handlers.handle_answer
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.app_handlers.cancel_application)],
        )

        # Add conversation handler
        self.application.add_handler(conversation_handler)

        # Add admin handlers
        self.application.add_handler(
            CallbackQueryHandler(
                self.admin_handlers.approve_request, pattern="^approve_"
            )
        )
        self.application.add_handler(
            CallbackQueryHandler(
                self.admin_handlers.decline_request, pattern="^decline_"
            )
        )
        self.application.add_handler(
            CommandHandler("broadcast", self.admin_handlers.broadcast_message)
        )
        self.application.add_handler(
            CommandHandler("stats", self.admin_handlers.user_stats)
        )
        self.application.add_handler(
            CommandHandler("help", self.admin_handlers.help_command)
        )

        # Add user handlers
        self.application.add_handler(
            CommandHandler("add", self.app_handlers.add_command)
        )

        # Add general callback handler
        self.application.add_handler(CallbackQueryHandler(self.handle_general_callback))

        # Set bot commands
        self.application.post_init = self.set_bot_commands

        # Add error handler
        self.application.add_error_handler(self.error_handler)

    async def set_bot_commands(self, application: Application):
        """Set bot commands menu"""
        # Note: Telegram doesn't support per-user command menus, so we show the most common commands
        # Users will see different options based on their role when they use /help
        commands = [
            BotCommand("help", COMMAND_HELP_DESC),
            BotCommand("start", COMMAND_START_DESC),
        ]
        try:
            await application.bot.set_my_commands(commands)
        except Exception:
            pass

    async def handle_general_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle any callback queries that weren't caught by other handlers"""
        query = update.callback_query

        # Answer the callback to remove the loading state
        await query.answer(ACTION_NOT_AVAILABLE)

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors that occur during bot operation"""
        # Try to notify user if possible
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(TEMPORARY_ERROR_MSG)
            except Exception:
                pass

    async def run(self):
        """Run the bot"""
        await self.application.run_polling()


if __name__ == "__main__":
    bot = TelegramBot()
    bot.application.run_polling()
