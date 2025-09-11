from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from config.questions import QUESTIONS
from database.model import Model
from messages.texts import (
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
db = Model()


class ApplicationHandlers:
    """Handles the application flow (user-facing interactions)"""

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command"""
        import logging

        from telegram.error import Forbidden, NetworkError, TimedOut

        from config.settings import ADMIN_CHAT_ID

        logger = logging.getLogger(__name__)
        user = update.effective_user

        logger.info(
            f"START command received from user {user.id} (@{user.username}) - {user.first_name}"
        )

        # Check if user is admin
        from handlers.admin_handlers import is_admin_user

        is_admin = await is_admin_user(context.bot, user.id)
        if is_admin:
            admin_message = (
                "🔧 **Admin Panel**\n\n"
                "You're logged in as an admin! Here are your available commands:\n\n"
                "📊 `/stats` - View user statistics\n"
                "📢 `/broadcast <message>` - Send message to all approved users\n"
                "❓ `/help` - Show detailed help"
            )
            try:
                await update.message.reply_text(admin_message, parse_mode="Markdown")
                logger.info(f"Admin message sent to user {user.id}")
            except (TimedOut, NetworkError, Forbidden) as e:
                logger.error(f"Error sending admin message to user {user.id}: {e}")
            return ConversationHandler.END

        # Check if user already has a pending request
        existing_request = db.requests.get_by_user_id(user.id)
        logger.info(f"Checking existing request for user {user.id}: {existing_request}")

        if existing_request and existing_request["status"] == "pending":
            logger.info(f"User {user.id} has pending request, sending pending message")
            try:
                await update.message.reply_text(PENDING_REQUEST_MSG)
                logger.info(f"Pending message sent successfully to user {user.id}")
            except (TimedOut, NetworkError, Forbidden) as e:
                logger.error(f"Error sending pending message to user {user.id}: {e}")
            return ConversationHandler.END

        # Create new request
        logger.info(f"Creating new request for user {user.id}")
        request_id = db.requests.create(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        logger.info(f"Created request {request_id} for user {user.id}")

        # Store request_id in context
        context.user_data["request_id"] = request_id

        # Send welcome message with options
        logger.info(f"Sending welcome message to user {user.id}")
        try:
            await self.send_welcome_message(update, context)
            logger.info(f"Welcome message sent successfully to user {user.id}")
            return WAITING_FOR_EXPLANATION
        except (TimedOut, NetworkError, Forbidden) as e:
            logger.error(f"Error in start command for user {user.id}: {e}")
            # Don't try to send fallback message if user blocked the bot
            if isinstance(e, Forbidden):
                logger.error(f"User {user.id} has blocked the bot")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Unexpected error in start command for user {user.id}: {e}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            return ConversationHandler.END

    async def send_welcome_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Send the welcome message with dynamic options"""
        import logging

        from telegram.error import NetworkError, TimedOut

        logger = logging.getLogger(__name__)
        user = update.effective_user
        logger.info(f"Preparing welcome message for user {user.id}")

        welcome_text = WELCOME_TEXT
        logger.info(f"Welcome text length: {len(welcome_text)} characters")

        # Dynamically create keyboard from configuration
        keyboard = []
        logger.info(f"Available questions: {list(QUESTIONS.keys())}")
        for option_key, option_config in QUESTIONS.items():
            button_text = option_config["button_text"]
            callback_data = f"option_{option_key}"
            logger.info(f"Creating button: '{button_text}' -> '{callback_data}'")
            keyboard.append(
                [
                    InlineKeyboardButton(
                        button_text,
                        callback_data=callback_data,
                    )
                ]
            )

        reply_markup = InlineKeyboardMarkup(keyboard)
        logger.info(f"Created keyboard with {len(keyboard)} options")
        logger.info(f"Keyboard rows: {len(keyboard)}")

        try:
            if update.callback_query:
                logger.info(f"Editing message for user {user.id} (callback query)")
                await update.callback_query.edit_message_text(
                    text=welcome_text, reply_markup=reply_markup
                )
            else:
                logger.info(f"Sending new message to user {user.id}")
                logger.info(f"Message text: {welcome_text[:100]}...")
                logger.info(
                    f"Keyboard structure: {[btn.text for row in keyboard for btn in row]}"
                )
                result = await update.message.reply_text(
                    text=welcome_text, reply_markup=reply_markup
                )
                logger.info(f"Message sent with ID: {result.message_id}")
            logger.info(f"Welcome message sent successfully to user {user.id}")
        except (TimedOut, NetworkError) as e:
            logger.error(
                f"Network error sending welcome message to user {user.id}: {e}"
            )
            # Try to send a simple text message without markup
            try:
                if update.callback_query:
                    logger.info(f"Sending fallback message (edit) to user {user.id}")
                    await update.callback_query.edit_message_text(text=welcome_text)
                else:
                    logger.info(f"Sending fallback message (new) to user {user.id}")
                    await update.message.reply_text(text=welcome_text)
                logger.info(f"Fallback message sent successfully to user {user.id}")
            except Exception as fallback_error:
                logger.error(
                    f"Fallback message also failed for user {user.id}: {fallback_error}"
                )
        except Exception as e:
            logger.error(
                f"Unexpected error sending welcome message to user {user.id}: {e}"
            )
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")

    async def handle_option_selection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle when user selects an option"""
        import logging

        logger = logging.getLogger(__name__)

        query = update.callback_query
        user = query.from_user
        logger.info(f"Option selection callback from user {user.id}: {query.data}")

        await query.answer()

        option = query.data.split("_")[1]
        logger.info(f"Selected option: {option}")

        # Store the selected option
        context.user_data["selected_option"] = option

        # Get question from configuration
        if option in QUESTIONS:
            question_text = QUESTIONS[option]["question"]
            logger.info(f"Using configured question for {option}")
        else:
            # Fallback for unknown options
            question_text = "Please provide more details:"
            logger.warning(f"Unknown option {option}, using fallback question")

        keyboard = [[InlineKeyboardButton(BACK_BUTTON, callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        logger.info(f"Sending question to user {user.id}: {question_text[:50]}...")
        await query.edit_message_text(text=question_text, reply_markup=reply_markup)
        logger.info(f"Question sent successfully to user {user.id}")

    async def handle_back_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle when user clicks the Back button"""
        import logging

        logger = logging.getLogger(__name__)

        query = update.callback_query
        user = query.from_user
        logger.info(f"Back button callback from user {user.id}: {query.data}")

        await query.answer()

        # Return to welcome message
        logger.info(f"Returning to welcome message for user {user.id}")
        await self.send_welcome_message(update, context)
        logger.info(f"Welcome message sent to user {user.id} via back button")

    async def handle_explanation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle user's free-text explanation from the welcome screen"""
        import logging

        logger = logging.getLogger(__name__)

        user = update.effective_user
        explanation_text = update.message.text
        logger.info(
            f"Handle explanation from user {user.id}: {explanation_text[:50]}..."
        )

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
        logger.info(f"Complete application prompt sent to user {user.id}")

        return WAITING_FOR_ANSWER

    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user's answer to the follow-up question"""
        import logging

        logger = logging.getLogger(__name__)

        user = update.effective_user
        answer = update.message.text
        selected_option = context.user_data.get("selected_option", "unknown")
        logger.info(
            f"Handle answer from user {user.id} for option {selected_option}: {answer[:50]}..."
        )

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
        logger.info(f"Complete application prompt sent to user {user.id}")

        return WAITING_FOR_ANSWER

    async def handle_complete_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle when user completes their application"""
        import logging

        logger = logging.getLogger(__name__)

        query = update.callback_query
        user = query.from_user
        logger.info(f"Complete application callback from user {user.id}: {query.data}")

        await query.answer()

        request_id = context.user_data["request_id"]
        selected_option = context.user_data.get("selected_option", "unknown")
        answer = context.user_data.get("answer", "")

        logger.info(
            f"Completing application for user {user.id}, request {request_id}, option: {selected_option}"
        )

        # Create the full explanation using configuration
        if selected_option in QUESTIONS:
            explanation = QUESTIONS[selected_option]["explanation_template"].format(
                answer=answer
            )
            logger.info(f"Using configured explanation template for {selected_option}")
        else:
            # Fallback for unknown options
            explanation = f"Unknown option '{selected_option}': {answer}"
            logger.warning(
                f"Unknown option {selected_option}, using fallback explanation"
            )

        logger.info(f"Generated explanation: {explanation[:100]}...")

        # Save explanation to database
        db.requests.update_user_explanation(request_id, explanation)
        logger.info(f"Saved explanation to database for request {request_id}")

        # Submit to admins
        logger.info(f"Submitting to admins for user {user.id}")
        await self.submit_to_admins(update, context, request_id, explanation)
        logger.info(f"Submitted to admins successfully for user {user.id}")

        await query.edit_message_text(text=SUBMITTED_MSG)
        logger.info(f"Application completed successfully for user {user.id}")

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

        from config.settings import ADMIN_CHAT_ID
        from messages.texts import APPROVE_BUTTON, REJECT_BUTTON, admin_application_text

        user = update.effective_user

        # Create admin message with Almaty timezone (handles DST automatically)
        import pytz

        # Almaty timezone with automatic DST handling
        almaty_tz = pytz.timezone("Asia/Almaty")
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
            # Store admin message ID
            db.requests.update_status(request_id, "pending", admin_message.message_id)
        except Exception:
            pass

    async def cancel_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Cancel the application process"""
        from messages.texts import CANCELLED_MSG

        user = update.effective_user

        await update.message.reply_text(CANCELLED_MSG)
        return ConversationHandler.END

    async def add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /add command - add user to the user table"""
        import logging

        from telegram.error import Forbidden, NetworkError, TimedOut

        logger = logging.getLogger(__name__)
        user = update.effective_user

        logger.info(
            f"ADD command received from user {user.id} (@{user.username}) - {user.first_name}"
        )

        # Add user to the users table (upsert operation)
        try:
            # Check if user already exists to provide appropriate message
            existing_user = db.users.get_by_id(user.id)

            user_db_id = db.users.upsert_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )

            if existing_user:
                message = (
                    "✅ **You're already in our community!**\n\n"
                    "You're already registered in our user database. "
                    "Your information has been updated. "
                    "You'll receive community updates and announcements."
                )
                logger.info(
                    f"User {user.id} already existed, updated record with ID {user_db_id}"
                )
            else:
                message = (
                    "🎉 **Welcome to our community!**\n\n"
                    "You've been successfully added to our user database. "
                    "You'll now receive community updates, announcements, and meetup notifications.\n\n"
                    "Thank you for joining Almaty Meetups! 🇰🇿"
                )
                logger.info(f"User {user.id} added to users table with ID {user_db_id}")

            await update.message.reply_text(message, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error upserting user {user.id} to users table: {e}")
            error_message = (
                "❌ **Something went wrong**\n\n"
                "We couldn't add you to our community database right now. "
                "Please try again later or contact an admin for assistance."
            )
            try:
                await update.message.reply_text(error_message, parse_mode="Markdown")
            except Exception as reply_error:
                logger.error(
                    f"Error sending error message to user {user.id}: {reply_error}"
                )
