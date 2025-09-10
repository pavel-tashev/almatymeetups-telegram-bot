# Predefined questions for the join request form
QUESTIONS = [
    {
        "id": "cs",
        "question": "What's your Couch Surfing account? (Type 'No' if you don't have one)",
        "required": False,
    },
    {
        "id": "inviter",
        "question": "What is the username of the person who invited you to the group? (Type 'No' if you don't have an inviter)",
        "required": False,
    },
    {
        "id": "how_found",
        "question": "How you found out about the group, please let us know your name? (Type 'No' if you don't know how you found out about the group)",
        "required": False,
    },
]


def get_question_by_id(question_id):
    """Get a question by its ID"""
    for question in QUESTIONS:
        if question["id"] == question_id:
            return question
    return None


def get_all_questions():
    """Get all questions"""
    return QUESTIONS


def get_required_questions():
    """Get only required questions"""
    return [q for q in QUESTIONS if q["required"]]
