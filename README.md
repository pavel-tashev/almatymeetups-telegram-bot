# Almaty Meetups Telegram Bot

A Telegram bot for managing group join requests with an approval workflow. Users can apply to join a group, answer questions, and admins can approve or decline requests.

## Features

- **Join Request Flow**: Users can request to join the group through a button
- **Question System**: Configurable questions that users must answer
- **Admin Approval**: Admins can approve or decline requests with buttons
- **Auto-timeout**: Requests are automatically rejected after 24 hours
- **Message Management**: Admin messages are deleted after approval/decline with status notifications
- **Database Storage**: All requests and responses are stored in SQLite

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
REQUEST_TIMEOUT_HOURS=24
DATABASE_URL=sqlite:///bot_database.db
```

### 4. Local Development

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the bot:

```bash
python bot.py
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
- `REQUEST_TIMEOUT_HOURS`: `24` (optional, defaults to 24)
- `DATABASE_URL`: `sqlite:///data/bot_database.db`

### 4. Deploy

Click "Deploy" and wait for the deployment to complete.

## Bot Commands

- `/start` - Start the bot and see the join button

## Workflow

1. **User clicks "Join Our Community"** → Bot shows application form
2. **User answers questions** → Bot stores responses in database
3. **Bot sends to admin chat** → Admins see request with Approve/Decline buttons
4. **Admin approves** → User is added to group, admin message is deleted, status notification sent
5. **Admin declines** → User is notified, admin message is deleted, status notification sent
6. **Auto-timeout** → After 24 hours, request is automatically rejected

## Customization

### Questions

Edit `questions.py` to modify the questions users must answer:

```python
QUESTIONS = [
    {
        "id": "name",
        "question": "What's your full name?",
        "required": True
    },
    # Add more questions...
]
```

### Timeout

Change `REQUEST_TIMEOUT_HOURS` in your environment variables to modify the auto-rejection timeout.

## Database Schema

### requests table

- `id`: Primary key
- `user_id`: Telegram user ID
- `username`: Telegram username
- `first_name`: User's first name
- `last_name`: User's last name
- `status`: pending/approved/declined/expired
- `created_at`: Request creation timestamp
- `approved_at`: Approval timestamp
- `admin_message_id`: ID of admin message for deletion

### responses table

- `id`: Primary key
- `request_id`: Foreign key to requests
- `question_id`: Question identifier
- `answer`: User's answer

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

## Security Notes

- Keep your bot token secret
- Use environment variables for sensitive data
- The bot requires admin permissions in the target group
- Consider rate limiting for production use

## Support

For issues or questions, check the logs in Render dashboard or create an issue in the repository.
