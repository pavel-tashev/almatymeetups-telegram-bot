"""
Bot handlers - separated from main bot class for better organization
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from database import Database
from questions import QUESTIONS
from texts import (
    BACK_BUTTON,
    COMPLETE_BUTTON,
    PENDING_REQUEST_MSG,
    REQUEST_NOT_FOUND,
    SUBMITTED_MSG,
    WELCOME_TEXT,
    complete_prompt,
)

# Conversation states
WAITING_FOR_EXPLANATION, WAITING_FOR_ANSWER = range(2)

# Initialize database
db = Database()


class ApplicationHandlers:
    """Handles the application flow (user-facing interactions)"""

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command"""
        user = update.effective_user

        # Check if user already has a pending request
        existing_request = db.get_request(user.id)
        if existing_request and existing_request["status"] == "pending":
            await update.message.reply_text(PENDING_REQUEST_MSG)
            return ConversationHandler.END

        # Create new request
        request_id = db.create_request(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        # Store request_id in context
        context.user_data["request_id"] = request_id

        # Send welcome message with options
        await self.send_welcome_message(update, context)
        return WAITING_FOR_EXPLANATION

    async def send_welcome_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Send the welcome message with dynamic options"""
        welcome_text = WELCOME_TEXT

        # Dynamically create keyboard from configuration
        keyboard = []
        for option_key, option_config in QUESTIONS.items():
            keyboard.append(
                [
                    InlineKeyboardButton(
                        option_config["button_text"],
                        callback_data=f"option_{option_key}",
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=welcome_text, reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text=welcome_text, reply_markup=reply_markup
            )

    async def handle_option_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle when user selects an option"""
        query = update.callback_query
        await query.answer()

        option = query.data.split("_")[1]

        # Store the selected option
        context.user_data["selected_option"] = option

        # Get question from configuration
        if option in QUESTIONS:
            question_text = QUESTIONS[option]["question"]
        else:
            # Fallback for unknown options
            question_text = "Please provide more details:"

        keyboard = [[InlineKeyboardButton(BACK_BUTTON, callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=question_text, reply_markup=reply_markup)

    async def handle_back_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle when user clicks the Back button"""
        query = update.callback_query
        await query.answer()

        # Return to welcome message
        await self.send_welcome_message(update, context)

    async def handle_explanation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
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

        await update.message.reply_text(
            text=complete_text, reply_markup=reply_markup, parse_mode="Markdown"
        )

    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

        await update.message.reply_text(
            text=complete_text, reply_markup=reply_markup, parse_mode="Markdown"
        )

    async def handle_complete_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle when user completes their application"""
        query = update.callback_query
        await query.answer()

        user = query.from_user
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
            explanation = f"Unknown option '{selected_option}': {answer}"

        # Save explanation to database
        db.update_user_explanation(request_id, explanation)

        # Submit to admins
        await self.submit_to_admins(update, context, request_id, explanation)

        await query.edit_message_text(text=SUBMITTED_MSG)

        return ConversationHandler.END

    async def submit_to_admins(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        request_id: int,
        explanation: str,
    ):
        """Submit application to admin chat"""
        from datetime import datetime

        from config import ADMIN_CHAT_ID
        from texts import APPROVE_BUTTON, REJECT_BUTTON, admin_application_text

        user = update.effective_user

        # Create admin message
        admin_text = admin_application_text(
            first_name=user.first_name,
            username=user.username,
            user_id=user.id,
            when=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            request_id=request_id,
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
            # Store admin message ID
            db.update_request_status(request_id, "pending", admin_message.message_id)
        except Exception:
            pass

    async def cancel_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Cancel the application process"""
        from texts import CANCELLED_MSG

        user = update.effective_user

        await update.message.reply_text(CANCELLED_MSG)
        return ConversationHandler.END
