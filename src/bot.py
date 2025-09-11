from typing import Any, Dict, List

from telegram import BotCommand, Update
from telegram.error import Conflict, NetworkError, TimedOut
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

from config.settings import (
    BOT_TOKEN,
    CALLBACK_APPROVE_PREFIX,
    CALLBACK_BACK,
    CALLBACK_COMPLETE,
    CALLBACK_DECLINE_PREFIX,
    CALLBACK_OPTION_PREFIX,
    HTTP_CONNECT_TIMEOUT,
    HTTP_POOL_TIMEOUT,
    HTTP_READ_TIMEOUT,
    HTTP_WRITE_TIMEOUT,
)
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
    """
    Main Telegram bot class that handles all bot operations.

    This class manages the bot's lifecycle, handler setup, and provides
    centralized error handling and command management.
    """

    def __init__(self) -> None:
        """
        Initialize the Telegram bot with HTTP configuration and handlers.

        Sets up the bot application with optimized HTTP timeouts for the
        Render environment and initializes all necessary handlers.
        """
        # Configure HTTP client with higher timeouts for Render environment
        http_request = HTTPXRequest(
            connect_timeout=HTTP_CONNECT_TIMEOUT,
            read_timeout=HTTP_READ_TIMEOUT,
            write_timeout=HTTP_WRITE_TIMEOUT,
            pool_timeout=HTTP_POOL_TIMEOUT,
        )
        self.application = (
            Application.builder().token(BOT_TOKEN).request(http_request).build()
        )

        # Initialize handlers
        self.app_handlers = ApplicationHandlers()
        self.admin_handlers = AdminHandlers()

        self.setup_handlers()

    def _create_conversation_handlers(self) -> List[CallbackQueryHandler]:
        """
        Create callback handlers common to both conversation states.

        Returns:
            List[CallbackQueryHandler]: List of callback query handlers for
                option selection, back button, and complete application actions.
        """
        return [
            CallbackQueryHandler(
                self.app_handlers.handle_option_selection,
                pattern=f"^{CALLBACK_OPTION_PREFIX}",
            ),
            CallbackQueryHandler(
                self.app_handlers.handle_back_button, pattern=f"^{CALLBACK_BACK}$"
            ),
            CallbackQueryHandler(
                self.app_handlers.handle_complete_application,
                pattern=f"^{CALLBACK_COMPLETE}$",
            ),
        ]

    def _create_message_handlers(self) -> Dict[int, List[Any]]:
        """
        Create message handlers for different conversation states.

        Returns:
            Dict[int, List[Any]]: Dictionary mapping conversation states to their
                respective message handlers. Each state includes common callback
                handlers plus state-specific message handlers.
        """
        return {
            WAITING_FOR_EXPLANATION: [
                *self._create_conversation_handlers(),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    self.app_handlers.handle_explanation,
                ),
            ],
            WAITING_FOR_ANSWER: [
                *self._create_conversation_handlers(),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, self.app_handlers.handle_answer
                ),
            ],
        }

    def _create_main_conversation_handler(self) -> ConversationHandler:
        """
        Create the main conversation handler for user applications.

        Returns:
            ConversationHandler: The main conversation handler that manages the
                complete application flow from start to completion.
        """
        start_handler = CommandHandler("start", self.app_handlers.start_command)

        return ConversationHandler(
            entry_points=[start_handler],
            states=self._create_message_handlers(),
            fallbacks=[CommandHandler("cancel", self.app_handlers.cancel_application)],
        )

    def _create_admin_handlers(self) -> List[Any]:
        """
        Create admin-specific command and callback handlers.

        Returns:
            List[Any]: List of handlers for admin commands including approval,
                rejection, broadcast, stats, and help commands.
        """
        return [
            CallbackQueryHandler(
                self.admin_handlers.approve_request,
                pattern=f"^{CALLBACK_APPROVE_PREFIX}",
            ),
            CallbackQueryHandler(
                self.admin_handlers.decline_request,
                pattern=f"^{CALLBACK_DECLINE_PREFIX}",
            ),
            CommandHandler("broadcast", self.admin_handlers.broadcast_message),
            CommandHandler("stats", self.admin_handlers.user_stats),
            CommandHandler("help", self.admin_handlers.help_command),
        ]

    def _create_user_handlers(self) -> List[Any]:
        """
        Create user-specific command handlers.

        Returns:
            List[Any]: List of handlers for user commands like /add for
                self-registration.
        """
        return [
            CommandHandler("add", self.app_handlers.add_command),
        ]

    def _create_general_handlers(self) -> List[Any]:
        """
        Create general handlers for unhandled callbacks.

        Returns:
            List[Any]: List of general handlers that catch any callback queries
                not handled by specific conversation or admin handlers.
        """
        return [
            CallbackQueryHandler(self.handle_general_callback),
        ]

    def setup_handlers(self) -> None:
        """
        Setup all bot handlers and register them with the application.

        This method orchestrates the registration of all handlers including
        conversation handlers, admin handlers, user handlers, and general handlers.
        It also sets up the bot commands and error handler.
        """
        # Create and add main conversation handler
        main_conversation = self._create_main_conversation_handler()
        self.application.add_handler(main_conversation)

        # Add all other handlers
        all_handlers = (
            self._create_admin_handlers()
            + self._create_user_handlers()
            + self._create_general_handlers()
        )

        for handler in all_handlers:
            self.application.add_handler(handler)

        # Set bot commands
        self.application.post_init = self.set_bot_commands

        # Add error handler
        self.application.add_error_handler(self.error_handler)

    async def set_bot_commands(self, application: Application) -> None:
        """
        Set the bot commands menu for users.

        Args:
            application (Application): The bot application instance.

        Note:
            Telegram doesn't support per-user command menus, so we show the most
            common commands. Users will see different options based on their role
            when they use /help.
        """
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
    ) -> None:
        """
        Handle any callback queries that weren't caught by other handlers.

        Args:
            update (Update): The incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context object.

        This method serves as a fallback for unhandled callback queries,
        answering them with a generic "not available" message.
        """
        query = update.callback_query

        # Answer the callback to remove the loading state
        await query.answer(ACTION_NOT_AVAILABLE)

    async def error_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle errors that occur during bot operation.

        Args:
            update (Update): The incoming update that caused the error.
            context (ContextTypes.DEFAULT_TYPE): The context object.

        This method provides centralized error handling and attempts to notify
        users of temporary issues when possible.
        """
        # Get the error from context
        error = context.error

        # Handle specific error types
        if isinstance(error, Conflict):
            # Conflict usually means multiple bot instances - don't notify user
            print(f"Bot conflict detected: {error}")
            return
        elif isinstance(error, (NetworkError, TimedOut)):
            # Network issues - notify user if possible
            if update and update.effective_message:
                try:
                    await update.effective_message.reply_text(TEMPORARY_ERROR_MSG)
                except Exception:
                    pass
        else:
            # Other errors - log and notify user if possible
            print(f"Unexpected error: {error}")
            if update and update.effective_message:
                try:
                    await update.effective_message.reply_text(TEMPORARY_ERROR_MSG)
                except Exception:
                    pass

    async def run(self) -> None:
        """
        Start the bot and begin polling for updates.

        This method starts the bot's polling mechanism to receive and process
        incoming updates from Telegram.
        """
        try:
            await self.application.run_polling()
        except Conflict as e:
            print(f"Bot conflict detected during polling: {e}")
            print("This usually means multiple bot instances are running.")
            # Don't re-raise to allow the health check server to continue
        except Exception as e:
            print(f"Unexpected error during bot polling: {e}")
            # Don't re-raise to allow the health check server to continue


if __name__ == "__main__":
    bot = TelegramBot()
    bot.application.run_polling()
