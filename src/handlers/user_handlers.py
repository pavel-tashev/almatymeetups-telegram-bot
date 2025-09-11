from datetime import datetime

import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Forbidden, NetworkError, TimedOut
from telegram.ext import ContextTypes, ConversationHandler

from config.questions import QUESTIONS
from config.settings import ADMIN_CHAT_ID, TIMEZONE
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
    """Handles the application flow (user-facing interactions)"""

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle the /start command"""
        user = update.effective_user

        # Check if user is admin
        is_admin = await is_admin_user(context.bot, user.id)
        if is_admin:
            await update.message.reply_text(ADMIN_PANEL_MESSAGE, parse_mode="Markdown")
            return ConversationHandler.END

        # Check if user already has a pending request
        existing_request = db.requests.get_by_user_id(user.id)

        if existing_request and existing_request["status"] == "pending":
            await update.message.reply_text(PENDING_REQUEST_MSG)
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
    ):
        """Send the welcome message with dynamic options"""
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
            try:
                await update.callback_query.edit_message_text(
                    text=welcome_text, reply_markup=reply_markup
                )
            except (TimedOut, NetworkError):
                # Try to send a simple text message without markup
                try:
                    await update.callback_query.edit_message_text(text=welcome_text)
                except Exception:
                    pass
        else:
            try:
                await update.message.reply_text(
                    text=welcome_text, reply_markup=reply_markup
                )
            except (TimedOut, NetworkError):
                # Try to send a simple text message without markup
                try:
                    await update.message.reply_text(text=welcome_text)
                except Exception:
                    pass

    async def handle_option_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
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

        keyboard = [[InlineKeyboardButton(BACK_BUTTON, callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(text=question_text, reply_markup=reply_markup)
        except (TimedOut, NetworkError):
            pass

    async def handle_back_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
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
        keyboard = [
            [InlineKeyboardButton(COMPLETE_BUTTON, callback_data="complete")],
            [InlineKeyboardButton(BACK_BUTTON, callback_data="back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await update.message.reply_text(
                text=complete_text, reply_markup=reply_markup, parse_mode="Markdown"
            )
        except (TimedOut, NetworkError):
            pass

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
        keyboard = [
            [InlineKeyboardButton(COMPLETE_BUTTON, callback_data="complete")],
            [InlineKeyboardButton(BACK_BUTTON, callback_data="back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await update.message.reply_text(
                text=complete_text, reply_markup=reply_markup, parse_mode="Markdown"
            )
        except (TimedOut, NetworkError):
            pass

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

        try:
            await query.edit_message_text(text=SUBMITTED_MSG)
        except (TimedOut, NetworkError):
            pass

        return ConversationHandler.END

    async def submit_to_admins(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        request_id: int,
        explanation: str,
    ):
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

        try:
            admin_message = await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
            if admin_message:
                # Store admin message ID
                db.requests.update_status(
                    request_id, "pending", admin_message.message_id
                )
        except (TimedOut, NetworkError, Forbidden):
            pass

    async def cancel_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Cancel the application process"""
        user = update.effective_user

        try:
            await update.message.reply_text(CANCELLED_MSG)
        except (TimedOut, NetworkError):
            pass
        return ConversationHandler.END

    async def add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /add command - add user to the user table"""
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

            await update.message.reply_text(message, parse_mode="Markdown")

        except Exception:
            await update.message.reply_text(ADD_COMMAND_ERROR, parse_mode="Markdown")
