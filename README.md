# CourtVision — Quick Discord Bot

This is the simplest version:

1. Attach a 2K scoreboard screenshot and type `!add`.
2. Repeat for every screenshot.
3. Type `!analyze`.
4. CourtVision analyzes all saved screenshots as one session, posts rankings,
   MVP, defense, matchups, chemistry, stock up/down, and balanced teams.

## What you need

- A laptop that stays on while the bot is being used.
- Python 3.11 or newer.
- A Discord bot token.
- An OpenAI API key with available API credit.

ChatGPT Plus does **not** automatically include API credit.

## Setup

### 1. Create your Discord bot

Go to the Discord Developer Portal:

1. Create a new application named `CourtVision`.
2. Open **Bot** and create/reset the token.
3. Turn on **Message Content Intent**.
4. Do not share the token with anybody.
5. Under **OAuth2 → URL Generator**, select:
   - `bot`
   - Permissions: View Channels, Send Messages, Read Message History,
     Attach Files, Embed Links
6. Open the generated invite link and add it to your server.

### 2. Put your keys in `.env`

Copy `.env.example` to a new file named `.env`, then fill in:

```env
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
BOT_PREFIX=!
```

Never post or send your `.env` file.

### 3. Install and run

Mac/Linux:

```bash
cd courtvision_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

Windows:

```bat
cd courtvision_bot
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py bot.py
```

Keep that terminal window open while using the bot.

## Discord commands

- Attach screenshot(s) and type `!add`
- `!count`
- `!analyze`
- `!clear`
- `!courtvision`

## Limits in this quick version

- It stores screenshots only until the program stops.
- It supports up to 12 screenshots per session.
- It does not keep permanent season standings yet.
- AI API usage may cost a small amount.
