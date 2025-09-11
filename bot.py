from datetime import datetime

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
from telegram.request import HTTPXRequest

from config import ADMIN_CHAT_ID, BOT_TOKEN, TARGET_GROUP_ID
from database import Database
from texts import (
    APPROVE_BUTTON,
    BACK_BUTTON,
    CANCELLED_MSG,
    COMMAND_START_DESC,
    COMPLETE_BUTTON,
    OPTION_COUCHSURFING,
    OPTION_INVITED,
    OPTION_OTHER,
    PENDING_REQUEST_MSG,
    QUESTION_COUCHSURFING,
    QUESTION_INVITED,
    QUESTION_OTHER,
    REJECT_BUTTON,
    REQUEST_NOT_FOUND,
    SUBMITTED_MSG,
    USER_APPROVED_DM,
    USER_DECLINED_DM,
    WELCOME_TEXT,
    admin_approved_added,
    admin_approved_link_sent,
    complete_prompt,
    user_approved_with_link,
)

# Conversation states
WAITING_FOR_EXPLANATION, WAITING_FOR_ANSWER = range(2)

# Initialize database
db = Database()


class TelegramBot:
    def __init__(self):
        # Configure HTTP client with higher timeouts to avoid startup TimedOut
        http_request = HTTPXRequest(
            connect_timeout=20.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=10.0,
        )
        self.application = (
            Application.builder().token(BOT_TOKEN).request(http_request).build()
        )
        self.setup_handlers()

    def setup_handlers(self):
        """Setup all bot handlers"""
        # Start command handler
        start_handler = CommandHandler("start", self.start_command)

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
        self.application.add_handler(main_conversation)
        self.application.add_handler(approve_handler)
        self.application.add_handler(decline_handler)

        # Set bot commands
        self.application.post_init = self.set_bot_commands

    async def set_bot_commands(self, application):
        """Set bot commands menu"""
        commands = [BotCommand("start", COMMAND_START_DESC)]
        try:
            await application.bot.set_my_commands(commands)
        except Exception:
            pass

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
        """Send the welcome message with three options"""
        welcome_text = WELCOME_TEXT

        keyboard = [
            [
                InlineKeyboardButton(
                    OPTION_COUCHSURFING, callback_data="option_couchsurfing"
                )
            ],
            [InlineKeyboardButton(OPTION_INVITED, callback_data="option_invited")],
            [InlineKeyboardButton(OPTION_OTHER, callback_data="option_other")],
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

        # Store the selected option
        context.user_data["selected_option"] = option

        # Ask the appropriate follow-up question
        if option == "couchsurfing":
            question_text = QUESTION_COUCHSURFING
        elif option == "invited":
            question_text = QUESTION_INVITED
        else:  # other
            question_text = QUESTION_OTHER

        keyboard = [[InlineKeyboardButton(BACK_BUTTON, callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=question_text, reply_markup=reply_markup)

        return WAITING_FOR_ANSWER

    async def handle_back_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle when user clicks the Back button"""
        query = update.callback_query
        await query.answer()

        # Return to welcome message
        await self.send_welcome_message(update, context)
        return WAITING_FOR_EXPLANATION

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

        await update.message.reply_text(text=complete_text, reply_markup=reply_markup)

        return WAITING_FOR_ANSWER

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

    async def approve_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin approval"""
        query = update.callback_query
        await query.answer()

        request_id = int(query.data.split("_")[1])

        request = db.get_request_by_id(request_id)
        if not request:
            await query.edit_message_text(REQUEST_NOT_FOUND)
            return

        try:
            # Try to approve the chat join request first
            try:
                await context.bot.approve_chat_join_request(
                    chat_id=TARGET_GROUP_ID, user_id=request["user_id"]
                )

                # Update request status
                db.update_request_status(
                    request_id, "approved", query.message.message_id
                )

                # Delete the admin message and send confirmation
                await query.delete_message()
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_approved_added(request["first_name"]),
                    parse_mode="Markdown",
                )

                # Notify user
                try:
                    await context.bot.send_message(
                        chat_id=request["user_id"],
                        text=USER_APPROVED_DM,
                    )
                except Exception:
                    pass
                return

            except TelegramError as e:
                # If no join request exists, generate one-time invite link and DM it
                if "Hide_requester_missing" in str(
                    e
                ) or "CHAT_JOIN_REQUEST_NOT_FOUND" in str(e):
                    try:
                        invite = await context.bot.create_chat_invite_link(
                            chat_id=TARGET_GROUP_ID,
                            name=f"Approval for {request['first_name'] or request['user_id']}",
                            member_limit=1,
                            creates_join_request=False,
                        )
                        invite_link = (
                            getattr(invite, "invite_link", None)
                            or invite["invite_link"]
                        )

                        # Update request status
                        db.update_request_status(
                            request_id, "approved", query.message.message_id
                        )

                        # Delete admin message and announce
                        await query.delete_message()
                        await context.bot.send_message(
                            chat_id=ADMIN_CHAT_ID,
                            text=admin_approved_link_sent(request["first_name"]),
                            parse_mode="Markdown",
                        )

                        # DM the user the invite link
                        await context.bot.send_message(
                            chat_id=request["user_id"],
                            text=user_approved_with_link(invite_link),
                        )
                        return

                    except TelegramError as gen_err:
                        await context.bot.send_message(
                            chat_id=ADMIN_CHAT_ID,
                            text=f"❌ Failed to send invite link to user {request['user_id']}: {gen_err}",
                        )
                        return
                else:
                    # Unknown error
                    raise e

        except TelegramError as e:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ Failed to approve user {request['user_id']}: {e}",
            )

    async def decline_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin rejection"""
        query = update.callback_query
        await query.answer()

        request_id = int(query.data.split("_")[1])

        request = db.get_request_by_id(request_id)
        if not request:
            await query.edit_message_text(REQUEST_NOT_FOUND)
            return

        try:
            # Try to decline the chat join request first
            try:
                await context.bot.decline_chat_join_request(
                    chat_id=TARGET_GROUP_ID, user_id=request["user_id"]
                )
            except TelegramError as e:
                # If no join request exists, just continue
                if "Hide_requester_missing" in str(
                    e
                ) or "CHAT_JOIN_REQUEST_NOT_FOUND" in str(e):
                    pass
                else:
                    raise e

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
                    text=USER_DECLINED_DM,
                )
            except Exception:
                pass

        except TelegramError as e:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ Failed to decline user {request['user_id']}: {e}",
            )

    async def cancel_application(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Cancel the application process"""
        user = update.effective_user

        await update.message.reply_text(CANCELLED_MSG)
        return ConversationHandler.END

    async def run(self):
        """Run the bot"""
        await self.application.run_polling()


if __name__ == "__main__":
    bot = TelegramBot()
    bot.application.run_polling()
