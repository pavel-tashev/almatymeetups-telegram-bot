# =============================================================================
# BOT CONFIGURATION
# =============================================================================

COMMAND_START_DESC = "Start the application process"
COMMAND_HELP_DESC = "Show available commands"

# =============================================================================
# USER FLOW MESSAGES
# =============================================================================

# Welcome and initial messages
WELCOME_TEXT = (
    "👋 Welcome to `Almaty Meetups`!\n\n"
    "We are a local community of foreigners and locals based in Almaty, Kazakhstan.\n\n"
    "Our purpose is to meet and connect with travelers and people living in Almaty. We frequently organize gatherings and events to meet new people and make new friends.\n\n"
    "To join our group, please tell us how you found out about us:"
)

PENDING_REQUEST_MSG = (
    "⏳ You already have a pending request. Please wait for admin approval."
)

CANCELLED_MSG = "❌ Application cancelled. You can start again anytime with /start"

SUBMITTED_MSG = (
    "✅ Your application has been submitted! We'll review it and get back to you soon."
)

# User approval/decline messages
USER_APPROVED_DM = (
    "🎉 Congratulations! Your application has been approved. Welcome to our community!"
)

USER_DECLINED_DM = "❌ Unfortunately, your application has been declined. Thank you for your interest in our community."


def user_approved_with_link(invite_link: str) -> str:
    return (
        "🎉 You have been approved!\n\n"
        "Tap this one-time invite link to join the group:\n"
        f"{invite_link}\n\n"
        "Note: This link works once and expires after first use."
    )


# =============================================================================
# BUTTON LABELS
# =============================================================================

BACK_BUTTON = "⬅️ Back"
COMPLETE_BUTTON = "✅ Complete Application"
APPROVE_BUTTON = "✅ Approve"
REJECT_BUTTON = "❌ Reject"

# =============================================================================
# APPLICATION FLOW FUNCTIONS
# =============================================================================

FALLBACK_QUESTION = "Please provide more details:"


def complete_prompt(answer: str) -> str:
    return (
        "✅ Thank you for your answer!\n\n"
        f"Your response: {answer}\n\n"
        "Click the button below to complete your application:"
    )


def unknown_option_explanation(selected_option: str, answer: str) -> str:
    return f"Unknown option '{selected_option}': {answer}"


# =============================================================================
# ADMIN MESSAGES
# =============================================================================


def admin_application_text(
    first_name: str,
    username: str | None,
    user_id: int,
    when: str,
    explanation: str,
) -> str:
    handle = f" (@{username})" if username else ""
    user_link = f"tg://user?id={user_id}"
    return (
        "📝 **New Join Request**\n\n"
        f"👤 **User:** [{first_name}{handle}]({user_link})\n"
        f"📅 **Date:** {when}\n\n"
        f"💬 **User's Answer:**\n{explanation}"
    )


def admin_approved_added(first_name: str) -> str:
    return f"✅ **{first_name}** has been **approved** and added to the group!"


def admin_approved_link_sent(first_name: str) -> str:
    return f"✅ **{first_name}** approved. Single-use invite link has been sent to the user."


ADMIN_DECLINED_MSG = "❌ **{first_name}** has been **declined**."

# =============================================================================
# ADMIN COMMAND MESSAGES
# =============================================================================

ADMIN_ONLY_COMMAND = "❌ This command is only available to admins."

BROADCAST_NO_MESSAGE = (
    "❌ Please provide a message to broadcast.\n" "Usage: /broadcast Your message here"
)

BROADCAST_NO_USERS = "❌ No approved users found."


def broadcast_summary(
    successful_sends: int, failed_sends: int, total_users: int
) -> str:
    return (
        f"📢 **Broadcast Complete**\n\n"
        f"✅ Successfully sent: {successful_sends}\n"
        f"❌ Failed to send: {failed_sends}\n"
        f"👥 Total users: {total_users}"
    )


# =============================================================================
# STATS MESSAGES
# =============================================================================

STATS_NO_USERS = "📊 **User Statistics**\n\n❌ No approved users found."


def user_stats_text(
    total_users: int, users_with_username: int, users_contacted: int, recent_users: int
) -> str:
    return (
        f"📊 **User Statistics**\n\n"
        f"👥 **Total Approved Users:** {total_users}\n"
        f"📱 **Users with Username:** {users_with_username}\n"
        f"📞 **Users Contacted:** {users_contacted}\n"
        f"🆕 **Approved This Week:** {recent_users}"
    )


# =============================================================================
# ADMIN PANEL MESSAGES
# =============================================================================

ADMIN_PANEL_MESSAGE = (
    "🔧 **Admin Panel**\n\n"
    "You're logged in as an admin! Here are your available commands:\n\n"
    "📊 `/stats` - View user statistics\n"
    "📢 `/broadcast <message>` - Send message to all approved users\n"
    "❓ `/help` - Show detailed help"
)

# =============================================================================
# HELP MESSAGES
# =============================================================================

ADMIN_HELP_TEXT = (
    "🔧 **Admin Commands**\n\n"
    "📊 `/stats` - View user statistics\n"
    "📢 `/broadcast <message>` - Send message to all approved users\n"
    "❓ `/help` - Show this help message"
)

USER_HELP_TEXT = (
    "🤖 **Available Commands**\n\n"
    "🚀 `/start` - Start the application process to join our community\n"
    "➕ `/add` - Add yourself to our community database\n"
    "❓ `/help` - Show this help message\n\n"
    "💡 **Welcome to Almaty Meetups!** We're a local community of foreigners and locals in Almaty, Kazakhstan."
)

# =============================================================================
# ADD COMMAND MESSAGES
# =============================================================================

ADD_COMMAND_ALREADY_EXISTS = "✅ **You're already registered in our user database.**"

ADD_COMMAND_SUCCESS = (
    "🎉 **Welcome to our community! 🇰🇿**\n\n"
    "You've been successfully added to our user database. "
    "One of the most important benefit of being part of our database is that we can broadcast you critical information related to Almaty Meetups."
)

ADD_COMMAND_ERROR = (
    "❌ **Something went wrong**\n\n"
    "We couldn't add you to our community database right now. "
    "Please try again later or contact an admin for assistance."
)

# =============================================================================
# ERROR MESSAGES
# =============================================================================

REQUEST_NOT_FOUND = "❌ Request not found."
ACTION_NOT_AVAILABLE = "This action is not available right now."
TEMPORARY_ERROR_MSG = (
    "Sorry, there was a temporary issue. Please try again in a moment."
)
ERROR_INVITE_LINK_FAILED = "❌ Failed to send invite link to user {user_id}: {error}"
ERROR_APPROVE_FAILED = "❌ Failed to approve user {user_id}: {error}"
ERROR_DECLINE_FAILED = "❌ Failed to decline user {user_id}: {error}"
