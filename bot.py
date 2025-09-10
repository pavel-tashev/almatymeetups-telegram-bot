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
    ChatJoinRequestHandler,
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
                # No entry points needed - conversation starts from /start command
            ],
            states={
                ANSWERING_QUESTIONS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_answer)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_application)],
        )

        # Chat join request handler (for invite links)
        join_request_handler = ChatJoinRequestHandler(self.handle_chat_join_request)

        # Admin approval handlers
        approve_handler = CallbackQueryHandler(
            self.approve_request, pattern="^approve_"
        )
        decline_handler = CallbackQueryHandler(
            self.decline_request, pattern="^decline_"
        )

        # Verification message handler (for pre-filled messages)
        verification_message_handler = MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.handle_verification_message
        )

        # Add handlers
        self.application.add_handler(start_handler)
        self.application.add_handler(join_request_handler)
        self.application.add_handler(verification_message_handler)
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
        args = context.args

        logger.info(
            f"Start command received from user {user.id} ({user.first_name}) with args: {args}"
        )

        # Check if this is a verification deep-link
        if args and args[0].startswith("verify_"):
            user_id_from_link = int(args[0].split("_")[1])
            logger.info(f"Verification deep-link for user {user_id_from_link}")

            # Verify the user ID matches
            if user.id != user_id_from_link:
                logger.warning(f"User ID mismatch: {user.id} vs {user_id_from_link}")
                await update.message.reply_text(
                    "❌ This verification link is not for your account. Please use the correct link."
                )
                return

            # Check if user already has a pending request
            existing_request = db.get_request(user.id)
            if existing_request and existing_request["status"] == "pending":
                logger.info(f"User {user.id} already has pending request")
                await update.message.reply_text(
                    "You already have a pending request. Please wait for admin approval."
                )
                return

            # Start the application process directly
            await self.start_verification_process(update, context)
            return

        # Regular /start command (fallback)
        await update.message.reply_text(
            f"Hello {user.first_name}! 👋\n\n"
            "Welcome! To join our community, please use the invite link and follow the verification process."
        )

    async def handle_verification_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle pre-filled verification messages from users"""
        user = update.effective_user
        message_text = update.message.text

        logger.info(f"Verification message received from user {user.id}: {message_text}")

        # Check if this is a verification message (contains user ID)
        if "My user ID is" in message_text and str(user.id) in message_text:
            logger.info(f"User {user.id} sent verification message, starting verification process")
            
            # Check if user already has a pending request
            existing_request = db.get_request(user.id)
            if existing_request and existing_request["status"] == "pending":
                logger.info(f"User {user.id} already has pending request")
                await update.message.reply_text(
                    "⏳ You already have a pending request. Please wait for admin approval."
                )
                return

            # Start verification process
            return await self.start_verification_process(update, context)
        
        # If not a verification message, provide instructions
        await update.message.reply_text(
            "👋 Hello! To join our community, please use the invite link provided by an admin and click the verification button."
        )

    async def start_verification_process(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Start the verification process for a user who clicked the deep-link"""
        user = update.effective_user
        logger.info(f"Starting verification process for user {user.id}")

        # Create or update request in database
        request_id = db.create_request(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        logger.info(f"Created request {request_id} for user {user.id}")

        # Store request_id in context
        context.user_data["request_id"] = request_id
        context.user_data["current_question"] = 0
        context.user_data["answers"] = {}

        # Start with first question
        questions = get_all_questions()
        first_question = questions[0]
        logger.info(
            f"Starting questions for user {user.id}, question 1 of {len(questions)}"
        )

        await update.message.reply_text(
            f"🔐 **Verification Process Started**\n\n"
            f"Great! Let's get to know you better. Please answer the following questions:\n\n"
            f"**Question 1 of {len(questions)}:**\n"
            f"{first_question['question']}"
        )

        # Set conversation state
        return ANSWERING_QUESTIONS

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
        # This will open the bot chat with a pre-filled message
        verification_message = f"Hi! I'd like to join the group. My user ID is {user.id}."
        encoded_message = verification_message.replace(" ", "%20").replace("!", "%21")
        bot_link = f"https://t.me/{context.bot.username}?text={encoded_message}"
        
        # Create button with the pre-filled message link
        keyboard = [[InlineKeyboardButton("🔐 Start Verification", url=bot_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        verification_text = (
            f"👋 Hello @{user.username or user.first_name}!\n\n"
            "Thank you for requesting to join our community!\n\n"
            "To complete your membership, please click the button below to start the verification process.\n\n"
            "⚠️ **Important:** You must complete the verification within 24 hours or your request will be automatically declined."
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

    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user's answer to a question"""
        user = update.effective_user
        answer = update.message.text

        questions = get_all_questions()
        current_question_index = context.user_data["current_question"]
        current_question = questions[current_question_index]

        logger.info(
            f"User {user.id} answered question {current_question_index + 1}: {current_question['id']}"
        )

        # Store the answer
        context.user_data["answers"][current_question["id"]] = answer

        # Move to next question
        next_question_index = current_question_index + 1

        if next_question_index < len(questions):
            # More questions to ask
            next_question = questions[next_question_index]
            context.user_data["current_question"] = next_question_index
            logger.info(
                f"Moving to question {next_question_index + 1} for user {user.id}"
            )

            await update.message.reply_text(
                f"**Question {next_question_index + 1} of {len(questions)}:**\n"
                f"{next_question['question']}"
            )
        else:
            # All questions answered, submit to admins
            logger.info(
                f"All questions answered for user {user.id}, submitting to admins"
            )
            await self.submit_to_admins(update, context)
            return ConversationHandler.END

    async def submit_to_admins(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Submit the application to admin chat"""
        user = update.effective_user
        request_id = context.user_data["request_id"]
        answers = context.user_data["answers"]

        logger.info(
            f"Submitting application for user {user.id} (request {request_id}) to admin chat"
        )

        # Save all answers to database
        for question_id, answer in answers.items():
            db.add_response(request_id, question_id, answer)
        logger.info(
            f"Saved {len(answers)} answers to database for request {request_id}"
        )

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
            logger.info(f"Sending admin message to chat {ADMIN_CHAT_ID}")
            admin_message = await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
            logger.info(f"Successfully sent admin message {admin_message.message_id}")

            # Store admin message ID
            db.update_request_status(request_id, "pending", admin_message.message_id)
            logger.info(f"Updated request {request_id} status to pending")

            await update.message.reply_text(
                "✅ Your application has been submitted successfully!\n\n"
                "Our admins will review your application and get back to you soon. "
                "Please be patient while we process your request."
            )
            logger.info(f"Sent confirmation message to user {user.id}")

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
        logger.info(f"Admin approving request {request_id}")

        request = db.get_request_by_id(request_id)

        if not request:
            logger.error(f"Request {request_id} not found for approval")
            await query.edit_message_text("❌ Request not found.")
            return

        # Update request status
        db.update_request_status(request_id, "approved", query.message.message_id)
        logger.info(f"Updated request {request_id} status to approved")

        # Delete the admin message and send approval notification
        try:
            logger.info(f"Deleting admin message for request {request_id}")
            await query.delete_message()
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"✅ **{request['first_name']}** has been approved and added to the group!",
            )
            logger.info(f"Sent approval notification to admin chat")
        except TelegramError as e:
            logger.error(f"Failed to delete admin message: {e}")

        # Approve the chat join request
        try:
            logger.info(f"Approving chat join request for user {request['user_id']}")
            await context.bot.approve_chat_join_request(
                chat_id=TARGET_GROUP_ID, user_id=request["user_id"]
            )
            logger.info(
                f"Successfully approved chat join request for user {request['user_id']}"
            )

            # Notify user
            await context.bot.send_message(
                chat_id=request["user_id"],
                text="🎉 Congratulations! Your application has been approved!\n\n"
                "You have been added to our community. Welcome aboard!",
            )
            logger.info(f"Sent approval notification to user {request['user_id']}")

        except TelegramError as e:
            logger.error(
                f"Failed to approve chat join request for user {request['user_id']}: {e}"
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ Failed to approve request for user {request['first_name']}. "
                "Please approve manually.",
            )

    async def decline_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin decline"""
        query = update.callback_query
        await query.answer()

        request_id = int(query.data.split("_")[1])
        logger.info(f"Admin declining request {request_id}")

        request = db.get_request_by_id(request_id)

        if not request:
            logger.error(f"Request {request_id} not found for decline")
            await query.edit_message_text("❌ Request not found.")
            return

        # Update request status
        db.update_request_status(request_id, "declined", query.message.message_id)
        logger.info(f"Updated request {request_id} status to declined")

        # Delete the admin message and send decline notification
        try:
            logger.info(f"Deleting admin message for request {request_id}")
            await query.delete_message()
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ **{request['first_name']}**'s request has been declined.",
            )
            logger.info(f"Sent decline notification to admin chat")
        except TelegramError as e:
            logger.error(f"Failed to delete admin message: {e}")

        # Decline the chat join request
        try:
            logger.info(f"Declining chat join request for user {request['user_id']}")
            await context.bot.decline_chat_join_request(
                chat_id=TARGET_GROUP_ID, user_id=request["user_id"]
            )
            logger.info(
                f"Successfully declined chat join request for user {request['user_id']}"
            )

            # Notify user
            await context.bot.send_message(
                chat_id=request["user_id"],
                text="❌ Unfortunately, your application has been declined.\n\n"
                "Thank you for your interest in our community. "
                "You can try applying again in the future.",
            )
            logger.info(f"Sent decline notification to user {request['user_id']}")

        except TelegramError as e:
            logger.error(
                f"Failed to decline chat join request for user {request['user_id']}: {e}"
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ Failed to decline request for user {request['first_name']}. "
                "Please decline manually.",
            )

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
