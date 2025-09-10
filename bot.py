import asyncio
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import ADMIN_CHAT_ID, BOT_TOKEN, REQUEST_TIMEOUT_HOURS, TARGET_GROUP_ID
from database import Database
from questions import get_all_questions, get_question_by_id

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(WAITING_FOR_APPLICATION, ANSWERING_QUESTIONS) = range(2)

# Global variables
db = Database()
scheduler = AsyncIOScheduler()


class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
        self.setup_scheduler()

    def setup_handlers(self):
        """Setup all bot handlers"""

        # Start command
        start_handler = CommandHandler("start", self.start_command)

        # Join request conversation
        join_conversation = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.start_application, pattern="^join_group$")
            ],
            states={
                ANSWERING_QUESTIONS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_answer)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_application)],
        )

        # Group join handler (separate from conversation)
        join_handler = MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS, self.handle_new_member
        )

        # Admin approval handlers
        approve_handler = CallbackQueryHandler(
            self.approve_request, pattern="^approve_"
        )
        decline_handler = CallbackQueryHandler(
            self.decline_request, pattern="^decline_"
        )

        # Add handlers
        self.application.add_handler(start_handler)
        self.application.add_handler(join_handler)
        self.application.add_handler(join_conversation)
        self.application.add_handler(approve_handler)
        self.application.add_handler(decline_handler)

        # Set bot commands
        self.application.post_init = self.set_bot_commands

    async def set_bot_commands(self, application):
        """Set bot commands menu"""
        commands = [
            BotCommand("start", "Start the bot and see available options"),
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
        """Handle /start command"""
        user = update.effective_user

        # Check if user already has a pending request
        existing_request = db.get_request(user.id)
        if existing_request and existing_request["status"] == "pending":
            await update.message.reply_text(
                "You already have a pending request. Please wait for admin approval."
            )
            return

        # Create join request button
        keyboard = [
            [InlineKeyboardButton("Join Our Community", callback_data="join_group")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = (
            f"Hello {user.first_name}! 👋\n\n"
            "Welcome to our community! To join our group, please click the button below "
            "and complete a short application form.\n\n"
            "We'll review your application and get back to you soon!"
        )

        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

    async def handle_new_member(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle new members joining the group"""
        logger.info(f"New member detected: {update.message.new_chat_members}")
        for member in update.message.new_chat_members:
            # Skip if the new member is the bot itself
            if member.id == context.bot.id:
                continue

            # Check if user already has a pending request
            existing_request = db.get_request(member.id)
            if existing_request and existing_request["status"] == "pending":
                await update.message.reply_text(
                    f"Welcome {member.first_name}! You already have a pending request. Please wait for admin approval."
                )
                continue

            # Send message to user in private chat
            await self.send_join_request_to_user(update, context, member)

    async def send_join_request_to_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE, member):
        """Send join request message to user in private chat"""
        try:
            # Create join request button
            keyboard = [
                [InlineKeyboardButton("Start Application Process", callback_data="join_group")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            welcome_text = (
                f"Hello {member.first_name}! 👋\n\n"
                "Thank you for your interest in joining our community!\n\n"
                "To complete your membership, you need to go through our approval process. "
                "Please click the button below to start the application.\n\n"
                "We'll review your application and get back to you soon!"
            )

            # Send message to user in private chat
            await context.bot.send_message(
                chat_id=member.id,
                text=welcome_text,
                reply_markup=reply_markup
            )
            
            # Remove user from group immediately
            try:
                await context.bot.ban_chat_member(
                    chat_id=update.effective_chat.id,
                    user_id=member.id
                )
                await context.bot.unban_chat_member(
                    chat_id=update.effective_chat.id,
                    user_id=member.id
                )
            except Exception as e:
                logger.error(f"Failed to remove user from group: {e}")
                
        except Exception as e:
            logger.error(f"Failed to send message to user {member.id}: {e}")

    async def start_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Start the application process"""
        query = update.callback_query
        await query.answer()

        user = update.effective_user

        # Create or update request in database
        request_id = db.create_request(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        # Store request_id in context
        context.user_data["request_id"] = request_id
        context.user_data["current_question"] = 0
        context.user_data["answers"] = {}

        # Start with first question
        questions = get_all_questions()
        first_question = questions[0]

        await query.edit_message_text(
            f"Great! Let's get to know you better. Please answer the following questions:\n\n"
            f"**Question 1 of {len(questions)}:**\n"
            f"{first_question['question']}"
        )

        return ANSWERING_QUESTIONS

    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user's answer to a question"""
        user = update.effective_user
        answer = update.message.text

        questions = get_all_questions()
        current_question_index = context.user_data["current_question"]
        current_question = questions[current_question_index]

        # Store the answer
        context.user_data["answers"][current_question["id"]] = answer

        # Move to next question
        next_question_index = current_question_index + 1

        if next_question_index < len(questions):
            # More questions to ask
            next_question = questions[next_question_index]
            context.user_data["current_question"] = next_question_index

            await update.message.reply_text(
                f"**Question {next_question_index + 1} of {len(questions)}:**\n"
                f"{next_question['question']}"
            )
        else:
            # All questions answered, submit to admins
            await self.submit_to_admins(update, context)
            return ConversationHandler.END

    async def submit_to_admins(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Submit the application to admin chat"""
        user = update.effective_user
        request_id = context.user_data["request_id"]
        answers = context.user_data["answers"]

        # Save all answers to database
        for question_id, answer in answers.items():
            db.add_response(request_id, question_id, answer)

        # Create admin message
        admin_text = f"🔔 **New Join Request**\n\n"
        admin_text += f"**User:** {user.first_name}"
        if user.last_name:
            admin_text += f" {user.last_name}"
        if user.username:
            admin_text += f" (@{user.username})"
        admin_text += f"\n**User ID:** {user.id}\n\n"

        # Add answers
        questions = get_all_questions()
        for question in questions:
            if question["id"] in answers:
                admin_text += (
                    f"**{question['question']}**\n{answers[question['id']]}\n\n"
                )

        # Create approval buttons
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Approve", callback_data=f"approve_{request_id}"
                ),
                InlineKeyboardButton(
                    "❌ Decline", callback_data=f"decline_{request_id}"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send to admin chat
        try:
            admin_message = await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

            # Store admin message ID
            db.update_request_status(request_id, "pending", admin_message.message_id)

            await update.message.reply_text(
                "✅ Your application has been submitted successfully!\n\n"
                "Our admins will review your application and get back to you soon. "
                "Please be patient while we process your request."
            )

        except TelegramError as e:
            logger.error(f"Failed to send message to admin chat: {e}")
            await update.message.reply_text(
                "❌ Sorry, there was an error submitting your application. "
                "Please try again later or contact an admin."
            )

    async def approve_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin approval"""
        query = update.callback_query
        await query.answer()

        request_id = int(query.data.split("_")[1])
        request = db.get_request_by_id(request_id)

        if not request:
            await query.edit_message_text("❌ Request not found.")
            return

        # Update request status
        db.update_request_status(request_id, "approved", query.message.message_id)

        # Delete the admin message and send approval notification
        try:
            await query.delete_message()
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"✅ **{request['first_name']}** has been approved and added to the group!",
            )
        except TelegramError as e:
            logger.error(f"Failed to delete admin message: {e}")

        # Add user to group
        try:
            await context.bot.add_chat_member(
                chat_id=TARGET_GROUP_ID, user_id=request["user_id"]
            )

            # Notify user
            await context.bot.send_message(
                chat_id=request["user_id"],
                text="🎉 Congratulations! Your application has been approved!\n\n"
                "You have been added to our community. Welcome aboard!",
            )

        except TelegramError as e:
            logger.error(f"Failed to add user to group: {e}")
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ Failed to add user {request['first_name']} to the group. "
                "Please add them manually.",
            )

    async def decline_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin decline"""
        query = update.callback_query
        await query.answer()

        request_id = int(query.data.split("_")[1])
        request = db.get_request_by_id(request_id)

        if not request:
            await query.edit_message_text("❌ Request not found.")
            return

        # Update request status
        db.update_request_status(request_id, "declined", query.message.message_id)

        # Delete the admin message and send decline notification
        try:
            await query.delete_message()
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ **{request['first_name']}**'s request has been declined.",
            )
        except TelegramError as e:
            logger.error(f"Failed to delete admin message: {e}")

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=request["user_id"],
                text="❌ Unfortunately, your application has been declined.\n\n"
                "Thank you for your interest in our community. "
                "You can try applying again in the future.",
            )
        except TelegramError as e:
            logger.error(f"Failed to notify user of decline: {e}")

    async def cancel_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Cancel the application process"""
        await update.message.reply_text(
            "Application cancelled. You can start a new application anytime with /start"
        )
        return ConversationHandler.END

    async def check_expired_requests(self):
        """Check for expired requests and auto-reject them"""
        expired_requests = db.get_expired_requests()

        for request in expired_requests:
            logger.info(
                f"Auto-rejecting expired request from user {request['user_id']}"
            )

            # Update status
            db.update_request_status(
                request["id"], "expired", request["admin_message_id"]
            )

            # Delete admin message if it exists
            if request["admin_message_id"]:
                try:
                    await self.application.bot.delete_message(
                        chat_id=ADMIN_CHAT_ID, message_id=request["admin_message_id"]
                    )
                    await self.application.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=f"⏰ **{request['first_name']}**'s request has expired and been automatically rejected.",
                    )
                except TelegramError as e:
                    logger.error(f"Failed to delete expired admin message: {e}")

            # Notify user
            try:
                await self.application.bot.send_message(
                    chat_id=request["user_id"],
                    text="⏰ Your application has expired (24 hours passed without admin action).\n\n"
                    "You can submit a new application anytime with /start",
                )
            except TelegramError as e:
                logger.error(f"Failed to notify user of expiration: {e}")

    def run(self):
        """Run the bot"""
        logger.info("Starting bot...")
        self.application.run_polling()


if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()
