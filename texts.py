WELCOME_TEXT = (
    "👋 Welcome to our `Almaty Meetups`!\n\n"
    "We are a local community of foreigners and locals based in Almaty, Kazakhstan.\n\n"
    "Our purpose is to meet and connect with travelers and people living in Almaty. We frequently organize gatherings and events to meet new people and make new friends.\n\n"
    "To join our group, please tell us how you found out about us:"
)

# Option buttons
OPTION_COUCHSURFING = "🏠 Couchsurfing"
OPTION_INVITED = "👥 Someone invited me"
OPTION_OTHER = "🔍 Other"

# Follow-up questions
QUESTION_COUCHSURFING = "What's your Couchsurfing profile link or username?"
QUESTION_INVITED = (
    "What is the Telegram username of the person who invited you to the group?"
)
QUESTION_OTHER = "How did you find out about the group? Please provide more details and a link if possible."

BACK_BUTTON = "⬅️ Back"
COMPLETE_BUTTON = "✅ Complete Application"
APPROVE_BUTTON = "✅ Approve"
REJECT_BUTTON = "❌ Reject"
COMMAND_START_DESC = "Start the application process"
REQUEST_NOT_FOUND = "❌ Request not found."
CANCELLED_MSG = "❌ Application cancelled. You can start again anytime with /start"

# Explanation templates
EXPLANATION_COUCHSURFING = "Found through Couchsurfing. Account: {answer}"
EXPLANATION_INVITED = "Invited by: {answer}"
EXPLANATION_OTHER = "Other: {answer}"

# Error messages
ERROR_INVITE_LINK_FAILED = "❌ Failed to send invite link to user {user_id}: {error}"
ERROR_APPROVE_FAILED = "❌ Failed to approve user {user_id}: {error}"
ERROR_DECLINE_FAILED = "❌ Failed to decline user {user_id}: {error}"

# Admin messages
ADMIN_DECLINED_MSG = "❌ **{first_name}** has been **declined**."


def complete_prompt(answer: str) -> str:
    return (
        "✅ Thank you for your answer!\n\n"
        f"Your response: {answer}\n\n"
        "Click the button below to complete your application:"
    )


# Messages to admins
def admin_approved_added(first_name: str) -> str:
    return f"✅ **{first_name}** has been **approved** and added to the group!"


def admin_approved_link_sent(first_name: str) -> str:
    return f"✅ **{first_name}** approved. Single-use invite link has been sent to the user."


def admin_declined(first_name: str) -> str:
    return f"❌ **{first_name}** has been **declined**."


# DM to user
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


# Start/pending messaging
PENDING_REQUEST_MSG = (
    "⏳ You already have a pending request. Please wait for admin approval."
)

# Post-submit message to user
SUBMITTED_MSG = (
    "✅ Your application has been submitted! We'll review it and get back to you soon."
)

# Admin application message


def admin_application_text(
    first_name: str,
    username: str | None,
    user_id: int,
    when: str,
    request_id: int,
    explanation: str,
) -> str:
    handle = f" (@{username})" if username else ""
    return (
        "📝 **New Join Request**\n\n"
        f"👤 **User:** {first_name}{handle}\n"
        f"🆔 **User ID:** `{user_id}`\n"
        f"📅 **Date:** {when}\n\n"
        f"💬 **Explanation:**\n{explanation}\n\n"
        f"⏰ **Request ID:** {request_id}"
    )
