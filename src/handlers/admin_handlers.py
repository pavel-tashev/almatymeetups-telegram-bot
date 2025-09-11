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

                # Add user to approved users table
                db.add_approved_user(
                    user_id=request["user_id"],
                    username=request["username"],
                    first_name=request["first_name"],
                    last_name=request["last_name"],
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

                        # Add user to approved users table
                        db.add_approved_user(
                            user_id=request["user_id"],
                            username=request["username"],
                            first_name=request["first_name"],
                            last_name=request["last_name"],
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

    async def broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast a message to all approved users (admin only)"""
        from config.settings import ADMIN_CHAT_ID
        
        # Check if user is admin
        if update.effective_user.id != int(ADMIN_CHAT_ID.replace("-", "")):
            await update.message.reply_text("❌ This command is only available to admins.")
            return

        # Get the message text (everything after /broadcast)
        message_text = update.message.text.replace("/broadcast", "").strip()
        
        if not message_text:
            await update.message.reply_text(
                "❌ Please provide a message to broadcast.\n"
                "Usage: /broadcast Your message here"
            )
            return

        # Get all active users
        users = db.get_all_active_users()
        
        if not users:
            await update.message.reply_text("❌ No approved users found.")
            return

        # Send message to each user
        successful_sends = 0
        failed_sends = 0
        
        for user in users:
            try:
                await context.bot.send_message(
                    chat_id=user["user_id"],
                    text=message_text
                )
                successful_sends += 1
                # Update last contacted timestamp
                db.update_last_contacted(user["user_id"])
            except Exception as e:
                failed_sends += 1
                # If user blocked the bot, deactivate them
                if "Forbidden" in str(e) or "blocked" in str(e).lower():
                    db.deactivate_user(user["user_id"])

        # Send summary to admin
        summary = (
            f"📢 **Broadcast Complete**\n\n"
            f"✅ Successfully sent: {successful_sends}\n"
            f"❌ Failed to send: {failed_sends}\n"
            f"👥 Total users: {len(users)}"
        )
        
        await update.message.reply_text(summary, parse_mode="Markdown")

    async def user_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user statistics (admin only)"""
        from config.settings import ADMIN_CHAT_ID
        
        # Check if user is admin
        if update.effective_user.id != int(ADMIN_CHAT_ID.replace("-", "")):
            await update.message.reply_text("❌ This command is only available to admins.")
            return

        # Get all active users
        users = db.get_all_active_users()
        
        if not users:
            await update.message.reply_text("📊 **User Statistics**\n\n❌ No approved users found.")
            return

        # Calculate statistics
        total_users = len(users)
        users_with_username = len([u for u in users if u["username"]])
        users_contacted = len([u for u in users if u["last_contacted_at"]])
        
        # Get recent approvals (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.now() - timedelta(days=7)
        recent_users = len([
            u for u in users 
            if u["approved_at"] and datetime.fromisoformat(u["approved_at"]) > week_ago
        ])

        stats_text = (
            f"📊 **User Statistics**\n\n"
            f"👥 **Total Approved Users:** {total_users}\n"
            f"📱 **Users with Username:** {users_with_username}\n"
            f"📞 **Users Contacted:** {users_contacted}\n"
            f"🆕 **Approved This Week:** {recent_users}\n\n"
            f"💡 Use `/broadcast <message>` to message all users"
        )
        
        await update.message.reply_text(stats_text, parse_mode="Markdown")
