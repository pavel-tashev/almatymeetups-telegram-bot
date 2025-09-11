# Almaty Meetups Telegram Bot

A Telegram bot for managing group join requests with an approval workflow. Users can apply to join a group through a direct bot link, answer questions, and admins can approve or decline requests.

## Features

- **Direct Bot Link Flow**: Users start application via bot link (no group join required)
- **Dynamic Options**: Configurable options for how users found the group
- **Admin Approval**: Admins can approve or decline requests with buttons
- **Clickable User Links**: Admins can click user names to start conversations
- **Message Management**: Admin messages are deleted after approval/decline with status notifications
- **Database Storage**: All requests and user explanations are stored in SQLite
- **Clean Architecture**: Modular code structure with separated concerns

## Setup

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Use `/newbot` command and follow the instructions
3. Save the bot token

### 2. Get Required IDs

#### Bot Token

- Provided by BotFather when creating the bot

#### Admin Chat ID

- Add your bot to a private group with admins
- Send a message in the group
- Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
- Find the chat ID in the response (it will be negative for groups)

#### Target Group ID

- The ID of the group where approved users will be added
- Get it the same way as Admin Chat ID

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_admin_chat_id_here
TARGET_GROUP_ID=your_target_group_id_here
DATABASE_URL=sqlite:///data/bot_database.db
```

### 4. Local Development

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the bot:

```bash
python src/bot.py
```

## Deployment on Render

### 1. Prepare Repository

1. Push your code to a GitHub repository
2. Make sure all files are committed

### 2. Deploy on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure the service:
   - **Name**: `almatymeetups-telegram-bot`
   - **Environment**: `Docker`
   - **Dockerfile Path**: `./Dockerfile`
   - **Plan**: Free

### 3. Set Environment Variables

In the Render dashboard, go to your service → Environment tab and add:

- `BOT_TOKEN`: Your bot token from BotFather
- `ADMIN_CHAT_ID`: Your admin chat ID (negative number for groups)
- `TARGET_GROUP_ID`: Your target group ID
- `DATABASE_URL`: `sqlite:///data/bot_database.db`

### 4. Deploy

Click "Deploy" and wait for the deployment to complete.

## Bot Commands

- `/start` - Start the bot and see the join button

## Workflow

1. **User clicks bot link** → Bot shows welcome message with options
2. **User selects option** → Bot asks follow-up question
3. **User provides answer** → Bot shows "Complete Application" button
4. **User completes application** → Bot sends to admin chat with Approve/Decline buttons
5. **Admin approves** → User gets invite link or is added to group, admin message deleted
6. **Admin declines** → User is notified, admin message is deleted

## Customization

### Options Configuration

Edit `src/config/questions.py` to modify the options and questions:

```python
QUESTIONS = {
    "couchsurfing": {
        "button_text": "🏠 Couchsurfing",
        "question": "What's your Couchsurfing profile link or username?",
        "explanation_template": "Found through Couchsurfing. Account: {answer}",
    },
    "invited": {
        "button_text": "👥 Someone invited me",
        "question": "What is the Telegram username of the person who invited you?",
        "explanation_template": "Invited by: {answer}",
    },
    # Add more options...
}
```

### Messages

Edit `src/messages/texts.py` to customize all user-facing messages and admin notifications.

## Project Structure

```
src/
├── bot.py                    # Main bot orchestrator
├── handlers/
│   ├── user_handlers.py      # User application flow
│   └── admin_handlers.py     # Admin approval/rejection
├── config/
│   ├── settings.py           # Bot configuration
│   └── questions.py          # Options configuration
├── database/
│   └── models.py             # Database operations
└── messages/
    └── texts.py              # User-facing messages
```

## Database Schema

### requests table

- `id`: Primary key
- `user_id`: Telegram user ID
- `username`: Telegram username
- `first_name`: User's first name
- `last_name`: User's last name
- `status`: pending/approved/declined
- `created_at`: Request creation timestamp
- `approved_at`: Approval timestamp
- `admin_message_id`: ID of admin message for deletion
- `user_explanation`: User's explanation text

## Troubleshooting

### Bot not responding

- Check if the bot token is correct
- Ensure the bot is added to the admin chat
- Check Render logs for errors

### Can't get chat IDs

- Make sure the bot is added to the group
- Send a message in the group after adding the bot
- Use the getUpdates API endpoint

### Database issues

- The database file is created automatically
- On Render, it's stored in the `/data` directory
- Free tier has limited storage

### Import errors

- Make sure you're running from the project root directory
- Use `python src/bot.py` to run the bot
- Check that all `__init__.py` files are present in the src directories

## Security Notes

- Keep your bot token secret
- Use environment variables for sensitive data
- The bot requires admin permissions in the target group
- Consider rate limiting for production use

## Support

For issues or questions, check the logs in Render dashboard or create an issue in the repository.
