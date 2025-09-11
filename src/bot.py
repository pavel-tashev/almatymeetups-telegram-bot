from telegram import BotCommand
from telegram.error import NetworkError, TimedOut
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

        # Admin approval handlers
        approve_handler = CallbackQueryHandler(
            self.admin_handlers.approve_request, pattern="^approve_"
        )
        decline_handler = CallbackQueryHandler(
            self.admin_handlers.decline_request, pattern="^decline_"
        )

        # Admin broadcast command
        broadcast_handler = CommandHandler(
            "broadcast", self.admin_handlers.broadcast_message
        )

        # Admin stats command
        stats_handler = CommandHandler("stats", self.admin_handlers.user_stats)

        # Help command (shows different options for admin vs regular users)
        help_handler = CommandHandler("help", self.admin_handlers.help_command)

        # Add command for users to add themselves to the user table
        add_handler = CommandHandler("add", self.app_handlers.add_command)

        # Add a general callback handler to catch unhandled callbacks
        general_callback_handler = CallbackQueryHandler(self.handle_general_callback)

        # Add handlers
        self.application.add_handler(main_conversation)
        self.application.add_handler(approve_handler)
        self.application.add_handler(decline_handler)
        self.application.add_handler(broadcast_handler)
        self.application.add_handler(stats_handler)
        self.application.add_handler(help_handler)
        self.application.add_handler(add_handler)
        self.application.add_handler(general_callback_handler)

        # Set bot commands
        self.application.post_init = self.set_bot_commands

        # Add error handler
        self.application.add_error_handler(self.error_handler)

    async def set_bot_commands(self, application):
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

    async def handle_general_callback(self, update, context):
        """Handle any callback queries that weren't caught by other handlers"""
        query = update.callback_query

        # Answer the callback to remove the loading state
        await query.answer(ACTION_NOT_AVAILABLE)

    async def error_handler(self, update, context):
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
