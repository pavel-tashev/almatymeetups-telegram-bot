from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import pytz
from telegram import Update
from telegram.error import Forbidden, NetworkError, TelegramError, TimedOut
from telegram.ext import ContextTypes

from config.settings import (
    ADMIN_CHAT_ID,
    CALLBACK_APPROVE_PREFIX,
    CALLBACK_DECLINE_PREFIX,
    REQUEST_STATUS_APPROVED,
    REQUEST_STATUS_DECLINED,
    STATS_RECENT_DAYS,
    TARGET_GROUP_ID,
    TIMEZONE,
)
from database.model import Model
from messages.texts import (
    ADMIN_DECLINED_MSG,
    ADMIN_HELP_TEXT,
    ADMIN_ONLY_COMMAND,
    BROADCAST_NO_MESSAGE,
    BROADCAST_NO_USERS,
    ERROR_APPROVE_FAILED,
    ERROR_DECLINE_FAILED,
    ERROR_INVITE_LINK_FAILED,
    REQUEST_NOT_FOUND,
    STATS_NO_USERS,
    USER_APPROVED_DM,
    USER_DECLINED_DM,
    USER_HELP_TEXT,
    admin_approved_added,
    admin_approved_link_sent,
    broadcast_summary,
    user_approved_with_link,
    user_stats_text,
)

# Initialize database
db = Model()


async def is_admin_user(bot, user_id: int) -> bool:
    """
    Check if a user is an admin of the admin group.

    Args:
        bot: The bot instance.
        user_id (int): The user ID to check.

    Returns:
        bool: True if the user is an admin (administrator or creator), False otherwise.

    Note:
        If the user is not in the group or there's an error checking, returns False.
    """
    try:
        chat_member = await bot.get_chat_member(ADMIN_CHAT_ID, user_id)
        return chat_member.status in ["administrator", "creator"]
    except Exception:
        # If we can't check (e.g., user not in group), return False
        return False


class AdminHandlers:
    """
    Handles admin approval/rejection actions and administrative commands.

    This class manages all admin-specific functionality including user approval,
    rejection, broadcast messaging, user statistics, and help commands. It provides
    centralized error handling and permission checking for all admin operations.
    """

    async def _check_admin_permission(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        """
        Check if user is admin and send error message if not.

        Args:
            update (Update): The incoming update.
            context (ContextTypes.DEFAULT_TYPE): The context object.

        Returns:
            bool: True if the user is an admin, False otherwise.

        If the user is not an admin, sends an error message and returns False.
        """
        if not await is_admin_user(context.bot, update.effective_user.id):
            await update.message.reply_text(ADMIN_ONLY_COMMAND)
            return False
        return True

    async def _handle_telegram_errors(
        self, operation: Callable, *args: Any, **kwargs: Any
    ) -> Optional[Any]:
        """
        Centralized Telegram error handling for all admin operations.

        Args:
            operation (Callable): The async operation to execute.
            *args: Positional arguments for the operation.
            **kwargs: Keyword arguments for the operation.

        Returns:
            Optional[Any]: The result of the operation if successful, None if
                an error occurred.

        This method handles common Telegram errors like timeouts, network issues,
        and forbidden operations gracefully, and re-raises TelegramError for
        specific handling by calling methods.
        """
        try:
            return await operation(*args, **kwargs)
        except (TimedOut, NetworkError) as e:
            # Handle network issues - these are usually temporary
            return None
        except Forbidden as e:
            # Handle blocked users or permission issues
            return None
        except TelegramError as e:
            # Handle other Telegram-specific errors
            raise e
        except Exception as e:
            # Handle unexpected errors
            raise e

    async def _safe_send_message(
        self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs: Any
    ) -> Optional[Any]:
        """
        Safely send a message with error handling.

        Args:
            context (ContextTypes.DEFAULT_TYPE): The context object.
            chat_id (int): The chat ID to send the message to.
            text (str): The text content of the message.
            **kwargs: Additional keyword arguments for send_message.

        Returns:
            Optional[Any]: The sent message if successful, None if an error occurred.
        """
        return await self._handle_telegram_errors(
            context.bot.send_message, chat_id=chat_id, text=text, **kwargs
        )

    async def _complete_approval(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        request: Dict[str, Any],
        request_id: int,
        query: Any,
    ) -> None:
        """
        Complete the approval process by updating database and notifying users.

        Args:
            context (ContextTypes.DEFAULT_TYPE): The context object.
            request (Dict[str, Any]): The request data from the database.
            request_id (int): The ID of the request being approved.
            query (Any): The callback query from the admin button press.

        This method updates the request status, adds the user to the approved users
        table, deletes the admin message, and notifies both admin and user.
        """
        # Update request status
        db.requests.update_status(
            request_id, REQUEST_STATUS_APPROVED, query.message.message_id
        )

        # Add user to approved users table (upsert operation)
        db.users.upsert(
            user_id=request["user_id"],
            username=request["username"],
            first_name=request["first_name"],
            last_name=request["last_name"],
        )

        # Delete the admin message and send confirmation
        await query.delete_message()
        await self._safe_send_message(
            context,
            chat_id=ADMIN_CHAT_ID,
            text=admin_approved_added(request["first_name"]),
            parse_mode="Markdown",
        )

        # Notify user
        await self._safe_send_message(
            context,
            chat_id=request["user_id"],
            text=USER_APPROVED_DM,
        )

    async def _handle_direct_approval(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        request: Dict[str, Any],
        request_id: int,
        query: Any,
    ) -> None:
        """Handle direct chat join request approval"""
        await context.bot.approve_chat_join_request(
            chat_id=TARGET_GROUP_ID, user_id=request["user_id"]
        )
        await self._complete_approval(context, request, request_id, query)

    async def _handle_invite_link_approval(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        request: Dict[str, Any],
        request_id: int,
        query: Any,
    ) -> None:
        """Handle approval via invite link generation"""
        invite = await context.bot.create_chat_invite_link(
            chat_id=TARGET_GROUP_ID,
            name=f"Approval for {request['first_name'] or request['user_id']}",
            member_limit=1,
            creates_join_request=False,
        )
        invite_link = getattr(invite, "invite_link", None) or invite["invite_link"]

        # Update request status
        db.requests.update_status(
            request_id, REQUEST_STATUS_APPROVED, query.message.message_id
        )

        # Add user to approved users table (upsert operation)
        db.users.upsert(
            user_id=request["user_id"],
            username=request["username"],
            first_name=request["first_name"],
            last_name=request["last_name"],
        )

        # Delete admin message and announce
        await query.delete_message()
        await self._safe_send_message(
            context,
            chat_id=ADMIN_CHAT_ID,
            text=admin_approved_link_sent(request["first_name"]),
            parse_mode="Markdown",
        )

        # DM the user the invite link
        await self._safe_send_message(
            context,
            chat_id=request["user_id"],
            text=user_approved_with_link(invite_link),
        )

    async def approve_request(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle admin approval of a user request.

        Args:
            update (Update): The incoming update containing the approval callback.
            context (ContextTypes.DEFAULT_TYPE): The context object.

        This method attempts to approve the user by first trying to approve a chat
        join request directly. If that fails (no join request exists), it generates
        a one-time invite link and sends it to the user via DM.
        """
        query = update.callback_query
        await query.answer()

        request_id = int(query.data.split("_")[1])

        request = db.requests.get_by_id(request_id)
        if not request:
            await query.edit_message_text(REQUEST_NOT_FOUND)
            return

        try:
            # Try to approve the chat join request first
            try:
                await self._handle_direct_approval(context, request, request_id, query)
                return

            except TelegramError as e:
                # If no join request exists, generate one-time invite link and DM it
                if "Hide_requester_missing" in str(
                    e
                ) or "CHAT_JOIN_REQUEST_NOT_FOUND" in str(e):
                    try:
                        await self._handle_invite_link_approval(
                            context, request, request_id, query
                        )
                        return

                    except TelegramError as gen_err:
                        await self._safe_send_message(
                            context,
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
            await self._safe_send_message(
                context,
                chat_id=ADMIN_CHAT_ID,
                text=ERROR_APPROVE_FAILED.format(user_id=request["user_id"], error=e),
            )

    async def decline_request(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle admin rejection"""
        query = update.callback_query
        await query.answer()

        request_id = int(query.data.split("_")[1])

        request = db.requests.get_by_id(request_id)
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
            db.requests.update_status(
                request_id, REQUEST_STATUS_DECLINED, query.message.message_id
            )

            # Delete the admin message and send confirmation
            await query.delete_message()
            await self._safe_send_message(
                context,
                chat_id=ADMIN_CHAT_ID,
                text=ADMIN_DECLINED_MSG.format(first_name=request["first_name"]),
                parse_mode="Markdown",
            )

            # Notify user
            await self._safe_send_message(
                context,
                chat_id=request["user_id"],
                text=USER_DECLINED_DM,
            )

        except TelegramError as e:
            await self._safe_send_message(
                context,
                chat_id=ADMIN_CHAT_ID,
                text=ERROR_DECLINE_FAILED.format(user_id=request["user_id"], error=e),
            )

    async def broadcast_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Broadcast a message to all approved users (admin only).

        Args:
            update (Update): The incoming update containing the broadcast command.
            context (ContextTypes.DEFAULT_TYPE): The context object.

        This method sends a message to all active users in the database and provides
        a summary of successful and failed sends. Users who have blocked the bot
        are automatically deactivated.
        """
        # Check if user is admin
        if not await self._check_admin_permission(update, context):
            return

        # Get the message text (everything after /broadcast)
        message_text = update.message.text.replace("/broadcast", "").strip()

        if not message_text:
            await update.message.reply_text(BROADCAST_NO_MESSAGE)
            return

        # Get all active users
        users = db.users.get_all_active()

        if not users:
            await update.message.reply_text(BROADCAST_NO_USERS)
            return

        # Send message to each user
        successful_sends = 0
        failed_sends = 0

        for user in users:
            result = await self._safe_send_message(
                context, chat_id=user["user_id"], text=message_text
            )
            if result is not None:
                successful_sends += 1
                # Update last contacted timestamp
                db.users.update_last_contacted(user["user_id"])
            else:
                failed_sends += 1
                # If user blocked the bot, deactivate them
                db.users.deactivate(user["user_id"])

        # Send summary to admin
        summary = broadcast_summary(successful_sends, failed_sends, len(users))
        await update.message.reply_text(summary, parse_mode="Markdown")

    async def user_stats(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Get user statistics (admin only).

        Args:
            update (Update): The incoming update containing the stats command.
            context (ContextTypes.DEFAULT_TYPE): The context object.

        This method provides comprehensive statistics about approved users including
        total users, users with usernames, contacted users, and recent approvals.
        """
        # Check if user is admin
        if not await self._check_admin_permission(update, context):
            return

        # Get all active users
        users = db.users.get_all_active()

        if not users:
            await update.message.reply_text(STATS_NO_USERS)
            return

        # Calculate statistics
        total_users = len(users)
        users_with_username = len([u for u in users if u["username"]])
        users_contacted = len([u for u in users if u["last_contacted_at"]])

        # Get recent approvals (last N days)
        # Use configured timezone for consistent date calculations
        almaty_tz = pytz.timezone(TIMEZONE)
        week_ago = datetime.now(almaty_tz) - timedelta(days=STATS_RECENT_DAYS)
        recent_users = len(
            [
                u
                for u in users
                if u["approved_at"]
                and datetime.fromisoformat(u["approved_at"]) > week_ago
            ]
        )

        stats_text = user_stats_text(
            total_users, users_with_username, users_contacted, recent_users
        )
        await update.message.reply_text(stats_text, parse_mode="Markdown")

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Show help message with available commands.

        Args:
            update (Update): The incoming update containing the help command.
            context (ContextTypes.DEFAULT_TYPE): The context object.

        This method displays different help messages based on whether the user
        is an admin or a regular user, showing appropriate commands for each role.
        """
        user_id = update.effective_user.id
        is_admin = await is_admin_user(context.bot, user_id)

        if is_admin:
            help_text = ADMIN_HELP_TEXT
        else:
            help_text = USER_HELP_TEXT

        await update.message.reply_text(help_text, parse_mode="Markdown")
