"""
Admin handlers - separated for better organization
"""

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config.settings import ADMIN_CHAT_ID, TARGET_GROUP_ID
from database.models import Database
from messages.texts import (
    ADMIN_DECLINED_MSG,
    ERROR_APPROVE_FAILED,
    ERROR_DECLINE_FAILED,
    ERROR_INVITE_LINK_FAILED,
    REQUEST_NOT_FOUND,
    USER_APPROVED_DM,
    USER_DECLINED_DM,
    admin_approved_added,
    admin_approved_link_sent,
    user_approved_with_link,
)

# Initialize database
db = Database()


class AdminHandlers:
    """Handles admin approval/rejection actions"""

    async def approve_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin approval"""
        query = update.callback_query
        
        # Answer the callback query with error handling
        try:
            await query.answer()
        except Exception as e:
            # If answering fails, log but continue processing
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to answer callback query: {e}")

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
                            text=ERROR_INVITE_LINK_FAILED.format(
                                user_id=request["user_id"], error=gen_err
                            ),
                        )
                        return
                else:
                    # Unknown error
                    raise e

        except TelegramError as e:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=ERROR_APPROVE_FAILED.format(user_id=request["user_id"], error=e),
            )

    async def decline_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin rejection"""
        query = update.callback_query
        
        # Answer the callback query with error handling
        try:
            await query.answer()
        except Exception as e:
            # If answering fails, log but continue processing
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to answer callback query: {e}")

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
                text=ADMIN_DECLINED_MSG.format(first_name=request["first_name"]),
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
                text=ERROR_DECLINE_FAILED.format(user_id=request["user_id"], error=e),
            )
