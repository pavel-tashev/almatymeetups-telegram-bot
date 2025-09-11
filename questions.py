# Options configuration - easily extensible
QUESTIONS = {
    "couchsurfing": {
        "button_text": "🏠 Couchsurfing",
        "question": "What's your Couchsurfing profile link or username?",
        "explanation_template": "Found through Couchsurfing. Account: {answer}",
    },
    "invited": {
        "button_text": "👥 Someone invited me",
        "question": "What is the Telegram username of the person who invited you to the group?",
        "explanation_template": "Invited by: {answer}",
    },
    "other": {
        "button_text": "🔍 Other",
        "question": "How did you find out about the group? Please provide more details and a link if possible.",
        "explanation_template": "Other: {answer}",
    },
}
