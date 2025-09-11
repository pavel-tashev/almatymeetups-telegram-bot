from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Conflict, Forbidden, NetworkError, TimedOut
from telegram.ext import ContextTypes, ConversationHandler

from config.questions import QUESTIONS
from config.settings import (
    ADMIN_CHAT_ID,
    CALLBACK_BACK,
    CALLBACK_COMPLETE,
    REQUEST_STATUS_PENDING,
    TIMEZONE,
)
from database.model import Model
from handlers.admin_handlers import is_admin_user
from messages.texts import (
    ADD_COMMAND_ALREADY_EXISTS,
    ADD_COMMAND_ERROR,
    ADD_COMMAND_SUCCESS,
    ADMIN_PANEL_MESSAGE,
    APPROVE_BUTTON,
    BACK_BUTTON,
    CANCELLED_MSG,
    COMPLETE_BUTTON,
    FALLBACK_QUESTION,
    PENDING_REQUEST_MSG,
    REJECT_BUTTON,
    REQUEST_NOT_FOUND,
    SUBMITTED_MSG,
    WELCOME_TEXT,
    admin_application_text,
    complete_prompt,
    unknown_option_explanation,
)

# Conversation states
WAITING_FOR_EXPLANATION, WAITING_FOR_ANSWER = range(2)

# Initialize database
db = Model()


class ApplicationHandlers:
    """
    Handles the application flow and user-facing interactions.

    This class manages the complete user application process including welcome
    messages, option selection, conversation flow, and submission to admins.
    It also handles user self-registration and provides error handling for
    all user interactions.
    """

    async def _is_admin_user(self, bot: Any, user_id: int) -> bool:
        """
        Check if user is an admin of the admin group.

        Args:
            bot (Any): The bot instance.
            user_id (int): The user ID to check.

        Returns:
            bool: True if the user is an admin, False otherwise.
        """
        from handlers.admin_handlers import is_admin_user

        return await is_admin_user(bot, user_id)

    async def _handle_telegram_errors(
        self, operation: Callable, *args: Any, **kwargs: Any
    ) -> Optional[Any]:
        """
        Centralized Telegram error handling for all operations.

        Args:
            operation (Callable): The async operation to execute.
            *args: Positional arguments for the operation.
            **kwargs: Keyword arguments for the operation.

        Returns:
            Optional[Any]: The result of the operation if successful, None if
                an error occurred.

        This method handles common Telegram errors like timeouts, network issues,
        and forbidden operations gracefully.
        """
        try:
            return await operation(*args, **kwargs)
        except (TimedOut, NetworkError) as e:
            # Handle network issues - these are usually temporary
            print(f"Network error in user operation: {e}")
            return None
        except Forbidden as e:
            # Handle blocked users or permission issues
            print(f"Forbidden error in user operation: {e}")
            return None
        except BadRequest as e:
            # Handle malformed requests (e.g., invalid chat_id, message too long)
            print(f"Bad request in user operation: {e}")
            return None
        except Conflict as e:
            # Handle conflicts (e.g., multiple bot instances)
            print(f"Conflict in user operation: {e}")
            return None
        except Exception as e:
            # Handle unexpected errors
            print(f"Unexpected error in user operation: {e}")
            return None

    async def _safe_reply_text(
        self, update: Update, text: str, **kwargs: Any
    ) -> Optional[Any]:
        """
        Safely reply to a message with text, handling common errors.

        Args:
            update (Update): The update containing the message to reply to.
            text (str): The text to send as a reply.
            **kwargs: Additional keyword arguments for reply_text.

        Returns:
            Optional[Any]: The sent message if successful, None if an error occurred.
        """
        return await self._handle_telegram_errors(
            update.message.reply_text, text=text, **kwargs
        )

    async def _safe_edit_message_text(
        self, query: Any, text: str, **kwargs: Any
    ) -> Optional[Any]:
        """
        Safely edit a message's text, handling common errors.

        Args:
            query (Any): The callback query containing the message to edit.
            text (str): The new text for the message.
            **kwargs: Additional keyword arguments for edit_message_text.

        Returns:
            Optional[Any]: The edited message if successful, None if an error occurred.
        """
        return await self._handle_telegram_errors(
            query.edit_message_text, text=text, **kwargs
        )

    def _create_complete_keyboard(self) -> InlineKeyboardMarkup:
        """
        Create an inline keyboard with Complete and Back buttons.

        Returns:
            InlineKeyboardMarkup: A keyboard with Complete Application and Back buttons
                for the user to complete or go back in the conversation flow.
        """
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        COMPLETE_BUTTON, callback_data=CALLBACK_COMPLETE
                    )
                ],
                [InlineKeyboardButton(BACK_BUTTON, callback_data=CALLBACK_BACK)],
            ]
        )

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """
        Handle the /start command to begin the application process.

        Args:
            update (Update): The incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context object.

        Returns:
            int: The next conversation state (WAITING_FOR_EXPLANATION) or
                ConversationHandler.END if the user is admin or has a pending request.

        This method checks if the user is an admin (shows admin panel) or has a
        pending request (shows pending message), otherwise starts a new application.
        """
        user = update.effective_user

        # Check if user is admin
        is_admin = await self._is_admin_user(context.bot, user.id)
        if is_admin:
            await self._safe_reply_text(
                update, ADMIN_PANEL_MESSAGE, parse_mode="Markdown"
            )
            return ConversationHandler.END

        # Check if user already has a pending request
        existing_request = db.requests.get_by_user_id(user.id)

        if existing_request and existing_request["status"] == REQUEST_STATUS_PENDING:
            await self._safe_reply_text(update, PENDING_REQUEST_MSG)
            return ConversationHandler.END

        # Create new request
        request_id = db.requests.create(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        # Store request_id in context
        context.user_data["request_id"] = request_id

        # Send welcome message with options
        result = await self.send_welcome_message(update, context)
        if result is None:
            return ConversationHandler.END
        return WAITING_FOR_EXPLANATION

    async def send_welcome_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> Optional[Any]:
        """
        Send the welcome message with dynamic option buttons.

        Args:
            update (Update): The incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context object.

        Returns:
            Optional[Any]: The sent message if successful, None if an error occurred.

        This method creates a dynamic keyboard based on the QUESTIONS configuration
        and sends the welcome message with option buttons for the user to select.
        """
        user = update.effective_user

        welcome_text = WELCOME_TEXT

        # Dynamically create keyboard from configuration
        keyboard = []
        for option_key, option_config in QUESTIONS.items():
            button_text = option_config["button_text"]
            callback_data = f"option_{option_key}"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        button_text,
                        callback_data=callback_data,
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            result = await self._safe_edit_message_text(
                update.callback_query, text=welcome_text, reply_markup=reply_markup
            )
            if result is None:
                # Try to send a simple text message without markup
                await self._safe_edit_message_text(
                    update.callback_query, text=welcome_text
                )
        else:
            result = await self._safe_reply_text(
                update, text=welcome_text, reply_markup=reply_markup
            )
            if result is None:
                # Try to send a simple text message without markup
                await self._safe_reply_text(update, text=welcome_text)

    async def handle_option_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle when user selects an option"""
        query = update.callback_query
        user = query.from_user

        await query.answer()

        option = query.data.split("_")[1]

        # Store the selected option
        context.user_data["selected_option"] = option

        # Get question from configuration
        if option in QUESTIONS:
            question_text = QUESTIONS[option]["question"]
        else:
            # Fallback for unknown options
            question_text = FALLBACK_QUESTION

        keyboard = [[InlineKeyboardButton(BACK_BUTTON, callback_data=CALLBACK_BACK)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self._safe_edit_message_text(
            query, text=question_text, reply_markup=reply_markup
        )

    async def handle_back_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle when user clicks the Back button"""
        query = update.callback_query
        user = query.from_user

        await query.answer()

        # Return to welcome message
        await self.send_welcome_message(update, context)

    async def handle_explanation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle user's free-text explanation from the welcome screen"""
        user = update.effective_user
        explanation_text = update.message.text

        # Treat as 'other' path; store selection and answer
        context.user_data["selected_option"] = "other"
        context.user_data["answer"] = explanation_text

        # Show Complete Application button (same as after answering a follow-up)
        complete_text = complete_prompt(explanation_text)
        reply_markup = self._create_complete_keyboard()

        await self._safe_reply_text(
            update, text=complete_text, reply_markup=reply_markup, parse_mode="Markdown"
        )

        return WAITING_FOR_ANSWER

    async def handle_answer(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle user's answer to the follow-up question"""
        user = update.effective_user
        answer = update.message.text
        selected_option = context.user_data.get("selected_option", "unknown")

        # Store the answer
        context.user_data["answer"] = answer

        # Show Complete Application button
        complete_text = complete_prompt(answer)
        reply_markup = self._create_complete_keyboard()

        await self._safe_reply_text(
            update, text=complete_text, reply_markup=reply_markup, parse_mode="Markdown"
        )

        return WAITING_FOR_ANSWER

    async def handle_complete_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle when user completes their application"""
        query = update.callback_query
        user = query.from_user

        await query.answer()

        request_id = context.user_data["request_id"]
        selected_option = context.user_data.get("selected_option", "unknown")
        answer = context.user_data.get("answer", "")

        # Create the full explanation using configuration
        if selected_option in QUESTIONS:
            explanation = QUESTIONS[selected_option]["explanation_template"].format(
                answer=answer
            )
        else:
            # Fallback for unknown options
            explanation = unknown_option_explanation(selected_option, answer)

        # Save explanation to database
        db.requests.update_user_explanation(request_id, explanation)

        # Submit to admins
        await self.submit_to_admins(update, context, request_id, explanation)

        await self._safe_edit_message_text(query, text=SUBMITTED_MSG)

        return ConversationHandler.END

    async def submit_to_admins(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        request_id: int,
        explanation: str,
    ) -> None:
        """Submit application to admin chat"""
        user = update.effective_user

        # Create admin message with configured timezone (handles DST automatically)
        # Timezone with automatic DST handling
        almaty_tz = pytz.timezone(TIMEZONE)
        almaty_time = datetime.now(almaty_tz)

        admin_text = admin_application_text(
            first_name=user.first_name,
            username=user.username,
            user_id=user.id,
            when=almaty_time.strftime("%b %d, %Y at %I:%M %p"),
            explanation=explanation,
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    APPROVE_BUTTON, callback_data=f"approve_{request_id}"
                ),
                InlineKeyboardButton(
                    REJECT_BUTTON, callback_data=f"decline_{request_id}"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        admin_message = await self._handle_telegram_errors(
            context.bot.send_message,
            chat_id=ADMIN_CHAT_ID,
            text=admin_text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
        if admin_message:
            # Store admin message ID
            db.requests.update_status(
                request_id, REQUEST_STATUS_PENDING, admin_message.message_id
            )

    async def cancel_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancel the application process"""
        user = update.effective_user

        await self._safe_reply_text(update, CANCELLED_MSG)
        return ConversationHandler.END

    async def add_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle the /add command for user self-registration.

        Args:
            update (Update): The incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context object.

        This method allows users to add themselves to the user database for
        receiving broadcasts and being part of the community. It handles both
        new registrations and updates to existing user information.
        """
        user = update.effective_user

        # Add user to the users table (upsert operation)
        try:
            # Check if user already exists to provide appropriate message
            existing_user = db.users.get_by_id(user.id)

            user_db_id = db.users.upsert(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )

            if existing_user:
                message = ADD_COMMAND_ALREADY_EXISTS
            else:
                message = ADD_COMMAND_SUCCESS

            await self._safe_reply_text(update, message, parse_mode="Markdown")

        except Exception as e:
            print(f"Error in add_command: {e}")
            await self._safe_reply_text(
                update, ADD_COMMAND_ERROR, parse_mode="Markdown"
            )
