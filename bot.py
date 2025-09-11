import logging
import os
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import ADMIN_CHAT_ID, BOT_TOKEN, REQUEST_TIMEOUT_HOURS, TARGET_GROUP_ID
from database import Database

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_EXPLANATION, WAITING_FOR_ANSWER = range(2)

# Initialize database and scheduler
db = Database()
scheduler = AsyncIOScheduler()


class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
        self.setup_scheduler()

    def setup_handlers(self):
        """Setup all bot handlers"""
        # Start command handler
        start_handler = CommandHandler("start", self.start_command)

        # Chat join request handler (for invite links)
        join_request_handler = ChatJoinRequestHandler(self.handle_chat_join_request)

        # Main conversation handler
        main_conversation = ConversationHandler(
            entry_points=[start_handler],
            states={
                WAITING_FOR_EXPLANATION: [
                    CallbackQueryHandler(
                        self.handle_option_selection, pattern="^option_"
                    ),
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.handle_explanation
                    ),
                ],
                WAITING_FOR_ANSWER: [
                    CallbackQueryHandler(self.handle_back_button, pattern="^back$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_answer),
                    CallbackQueryHandler(
                        self.handle_complete_application, pattern="^complete$"
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_application)],
        )

        # Admin approval handlers
        approve_handler = CallbackQueryHandler(
            self.approve_request, pattern="^approve_"
        )
        decline_handler = CallbackQueryHandler(
            self.decline_request, pattern="^decline_"
        )

        # Add handlers
        self.application.add_handler(join_request_handler)
        self.application.add_handler(main_conversation)
        self.application.add_handler(approve_handler)
        self.application.add_handler(decline_handler)

        # Set bot commands
        self.application.post_init = self.set_bot_commands

    async def set_bot_commands(self, application):
        """Set bot commands menu"""
        commands = [
            BotCommand("start", "Start the application process"),
        ]
        await application.bot.set_my_commands(commands)

    def setup_scheduler(self):
        """Setup the scheduler for auto-rejection"""
        scheduler.add_job(
            self.check_expired_requests,
            trigger=IntervalTrigger(hours=1),  # Check every hour
            id="expired_requests_check",
        )
        scheduler.start()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command"""
        user = update.effective_user
        logger.info(f"Start command received from user {user.id} ({user.first_name})")

        # Check if user already has a pending request
        existing_request = db.get_request(user.id)
        if existing_request and existing_request["status"] == "pending":
            logger.info(f"User {user.id} already has pending request")
            await update.message.reply_text(
                "⏳ You already have a pending request. Please wait for admin approval."
            )
            return ConversationHandler.END

        # Create new request
        request_id = db.create_request(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        logger.info(f"Created new request {request_id} for user {user.id}")

        # Store request_id in context
        context.user_data["request_id"] = request_id

        # Send welcome message with options
        await self.send_welcome_message(update, context)
        return WAITING_FOR_EXPLANATION

    async def send_welcome_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Send the welcome message with three options"""
        welcome_text = (
            "👋 Welcome to our community!\n\n"
            "To join our group, please tell us how you found out about us:"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🏠 Couchsurfing", callback_data="option_couchsurfing"
                )
            ],
            [
                InlineKeyboardButton(
                    "👥 Someone invited me", callback_data="option_invited"
                )
            ],
            [InlineKeyboardButton("🔍 Other", callback_data="option_other")],
        ]
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
        logger.info(f"User {query.from_user.id} selected option: {option}")

        # Store the selected option
        context.user_data["selected_option"] = option

        # Ask the appropriate follow-up question
        if option == "couchsurfing":
            question_text = "What's your Couchsurfing account?"
        elif option == "invited":
            question_text = "What is the Telegram username of the person who invited you to the group?"
        else:  # other
            question_text = (
                "How you found out about the group, please let us know your name?"
            )

        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=question_text, reply_markup=reply_markup)

        return WAITING_FOR_ANSWER

    async def handle_back_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle when user clicks the Back button"""
        query = update.callback_query
        await query.answer()

        logger.info(f"User {query.from_user.id} clicked back button")

        # Return to welcome message
        await self.send_welcome_message(update, context)
        return WAITING_FOR_EXPLANATION

    async def handle_explanation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user's free-text explanation from the welcome screen"""
        user = update.effective_user
        explanation_text = update.message.text

        logger.info(
            f"User {user.id} provided free-text explanation from welcome: {explanation_text}"
        )

        # Treat as 'other' path; store selection and answer
        context.user_data["selected_option"] = "other"
        context.user_data["answer"] = explanation_text

        # Show Complete Application button (same as after answering a follow-up)
        complete_text = (
            f"✅ Thank you for your answer!\n\n"
            f"Your response: {explanation_text}\n\n"
            f"Click the button below to complete your application:"
        )

        keyboard = [
            [InlineKeyboardButton("✅ Complete Application", callback_data="complete")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text=complete_text, reply_markup=reply_markup)

        return WAITING_FOR_ANSWER

    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user's answer to the follow-up question"""
        user = update.effective_user
        answer = update.message.text
        selected_option = context.user_data.get("selected_option", "unknown")

        logger.info(f"User {user.id} answered: {answer} for option: {selected_option}")

        # Store the answer
        context.user_data["answer"] = answer

        # Show Complete Application button
        complete_text = (
            f"✅ Thank you for your answer!\n\n"
            f"Your response: {answer}\n\n"
            f"Click the button below to complete your application:"
        )

        keyboard = [
            [InlineKeyboardButton("✅ Complete Application", callback_data="complete")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text=complete_text, reply_markup=reply_markup)

        return WAITING_FOR_ANSWER

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

        logger.info(f"User {user.id} completed application for request {request_id}")

        # Create the full explanation
        if selected_option == "couchsurfing":
            explanation = f"Found through Couchsurfing. Account: {answer}"
        elif selected_option == "invited":
            explanation = f"Invited by: {answer}"
        else:  # other
            explanation = f"Other: {answer}"

        # Save explanation to database
        db.update_user_explanation(request_id, explanation)

        # Submit to admins
        await self.submit_to_admins(update, context, request_id, explanation)

        await query.edit_message_text(
            text="✅ Your application has been submitted! We'll review it and get back to you soon."
        )

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
        logger.info(
            f"Submitting application for user {user.id} (request {request_id}) to admin chat"
        )

        # Create admin message
        admin_text = (
            f"📝 **New Join Request**\n\n"
            f"👤 **User:** {user.first_name}"
            f"{f' (@{user.username})' if user.username else ''}\n"
            f"🆔 **User ID:** `{user.id}`\n"
            f"📅 **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"💬 **Explanation:**\n{explanation}\n\n"
            f"⏰ **Request ID:** {request_id}"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Approve", callback_data=f"approve_{request_id}"
                ),
                InlineKeyboardButton(
                    "❌ Reject", callback_data=f"decline_{request_id}"
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
            logger.info(f"Successfully sent admin message for request {request_id}")

            # Store admin message ID
            db.update_request_status(request_id, "pending", admin_message.message_id)

        except Exception as e:
            logger.error(f"Failed to send admin message for request {request_id}: {e}")

    async def handle_chat_join_request(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle chat join requests from invite links"""
        join_request = update.chat_join_request
        user = join_request.from_user
        chat = join_request.chat

        logger.info(
            f"Chat join request received from user {user.id} ({user.first_name}) for chat {chat.id}"
        )

        # Check if user already has a pending request
        existing_request = db.get_request(user.id)
        if existing_request and existing_request["status"] == "pending":
            logger.info(f"User {user.id} already has pending request")
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"@{user.username or user.first_name} already has a pending request. Please wait for admin approval.",
            )
            return

        # Create pre-filled message link for verification
        verification_message = (
            f"Hi! I'd like to join the group. My user ID is {user.id}."
        )
        encoded_message = verification_message.replace(" ", "%20").replace("!", "%21")
        bot_link = f"https://t.me/{context.bot.username}?text={encoded_message}"

        # Create button with the pre-filled message link
        keyboard = [[InlineKeyboardButton("🔐 Start Application", url=bot_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        verification_text = (
            f"👋 Hello @{user.username or user.first_name}!\n\n"
            "Thank you for requesting to join our community!\n\n"
            "To complete your membership, please click the button below to start the application process.\n\n"
            "⚠️ **Important:** You must complete the application within 24 hours or your request will be automatically declined."
        )

        try:
            logger.info(
                f"Posting verification message for user {user.id} in chat {chat.id}"
            )
            await context.bot.send_message(
                chat_id=chat.id, text=verification_text, reply_markup=reply_markup
            )
            logger.info(f"Successfully posted verification message for user {user.id}")
        except Exception as e:
            logger.error(f"Failed to post verification message for user {user.id}: {e}")

    async def approve_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin approval"""
        query = update.callback_query
        await query.answer()

        request_id = int(query.data.split("_")[1])
        logger.info(f"Admin approving request {request_id}")

        request = db.get_request_by_id(request_id)
        if not request:
            await query.edit_message_text("❌ Request not found.")
            return

        try:
            # Approve the chat join request
            await context.bot.approve_chat_join_request(
                chat_id=TARGET_GROUP_ID, user_id=request["user_id"]
            )
            logger.info(
                f"Successfully approved chat join request for user {request['user_id']}"
            )

            # Update request status
            db.update_request_status(request_id, "approved", query.message.message_id)

            # Delete the admin message and send confirmation
            await query.delete_message()
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"✅ **{request['first_name']}** has been **approved** and added to the group!",
                parse_mode="Markdown",
            )

            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=request["user_id"],
                    text="🎉 Congratulations! Your application has been approved. Welcome to our community!",
                )
            except Exception as e:
                logger.error(f"Failed to notify user {request['user_id']}: {e}")

        except TelegramError as e:
            logger.error(
                f"Failed to approve chat join request for user {request['user_id']}: {e}"
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ Failed to approve user {request['user_id']}: {e}",
            )

    async def decline_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin rejection"""
        query = update.callback_query
        await query.answer()

        request_id = int(query.data.split("_")[1])
        logger.info(f"Admin declining request {request_id}")

        request = db.get_request_by_id(request_id)
        if not request:
            await query.edit_message_text("❌ Request not found.")
            return

        try:
            # Decline the chat join request
            await context.bot.decline_chat_join_request(
                chat_id=TARGET_GROUP_ID, user_id=request["user_id"]
            )
            logger.info(
                f"Successfully declined chat join request for user {request['user_id']}"
            )

            # Update request status
            db.update_request_status(request_id, "declined", query.message.message_id)

            # Delete the admin message and send confirmation
            await query.delete_message()
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ **{request['first_name']}** has been **declined**.",
                parse_mode="Markdown",
            )

            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=request["user_id"],
                    text="❌ Unfortunately, your application has been declined. Thank you for your interest in our community.",
                )
            except Exception as e:
                logger.error(f"Failed to notify user {request['user_id']}: {e}")

        except TelegramError as e:
            logger.error(
                f"Failed to decline chat join request for user {request['user_id']}: {e}"
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ Failed to decline user {request['user_id']}: {e}",
            )

    async def cancel_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Cancel the application process"""
        user = update.effective_user
        logger.info(f"User {user.id} cancelled application")

        await update.message.reply_text(
            "❌ Application cancelled. You can start again anytime with /start"
        )
        return ConversationHandler.END

    async def check_expired_requests(self):
        """Check for expired requests and auto-decline them"""
        logger.info("Checking for expired requests...")
        expired_requests = db.get_expired_requests()

        for request in expired_requests:
            logger.info(
                f"Auto-declining expired request {request['id']} for user {request['user_id']}"
            )

            try:
                # Decline the chat join request
                await self.application.bot.decline_chat_join_request(
                    chat_id=TARGET_GROUP_ID, user_id=request["user_id"]
                )

                # Update request status
                db.update_request_status(request["id"], "expired")

                # Notify user
                await self.application.bot.send_message(
                    chat_id=request["user_id"],
                    text="⏰ Your application has expired and been automatically declined. You can apply again anytime.",
                )

                logger.info(f"Successfully auto-declined request {request['id']}")

            except Exception as e:
                logger.error(f"Failed to auto-decline request {request['id']}: {e}")

    async def run(self):
        """Run the bot"""
        logger.info("Starting bot...")
        await self.application.run_polling()


if __name__ == "__main__":
    bot = TelegramBot()
    bot.application.run_polling()
