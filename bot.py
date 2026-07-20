import asyncio
import base64
import logging
import os
from collections import defaultdict
from typing import Dict, List

import discord
from discord.ext import commands
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN in .env")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY in .env")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("courtvision")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Stores screenshots by Discord channel.
sessions: Dict[int, List[bytes]] = defaultdict(list)

SYSTEM_PROMPT = """
You are CourtVision, an NBA 2K 3v3 postgame analyst.

Analyze every supplied scoreboard screenshot as one complete session.

Always include:
1. Overall player rankings from best to worst, with a short explanation.
2. MVP.
3. Defensive player of the session.
4. Battles of the night.
5. Best chemistry or teammate pairings.
6. Stock up and stock down.
7. Fairest possible next 3v3 teams.
8. One short final takeaway.

Rules:
- Use only information visible in the screenshots.
- Never invent statistics, matchups, or events.
- Do not judge only by points; consider efficiency, assists, rebounds, steals,
  blocks, turnovers, teammate impact, and winning when visible.
- If something cannot be determined from the screenshots, say so.
- Keep the report clear, competitive, and easy to read in Discord.
"""

def image_to_data_url(data: bytes, content_type: str = "image/jpeg") -> str:
    encoded = base64.b64encode(data).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"

async def analyze_images(images: List[bytes]) -> str:
    content = [
        {
            "type": "input_text",
            "text": (
                f"Analyze these {len(images)} NBA 2K scoreboard screenshot(s) "
                "as one session. Produce the full CourtVision report."
            ),
        }
    ]

    for image in images:
        content.append(
            {
                "type": "input_image",
                "image_url": image_to_data_url(image),
            }
        )

    response = await client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
        input=[{"role": "user", "content": content}],
        max_output_tokens=1800,
    )
    return response.output_text.strip()

async def send_long(ctx: commands.Context, text: str) -> None:
    # Discord messages have a 2,000-character limit.
    chunks = []
    while text:
        if len(text) <= 1900:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, 1900)
        if split_at == -1:
            split_at = 1900
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()

    for chunk in chunks:
        await ctx.send(chunk)

@bot.event
async def on_ready():
    log.info("Logged in as %s", bot.user)

@bot.command(name="add")
async def add_scoreboard(ctx: commands.Context):
    """
    Attach one or more screenshots and type !add.
    The bot stores them without analyzing yet.
    """
    valid = [
        a for a in ctx.message.attachments
        if (a.content_type or "").startswith("image/")
    ]

    if not valid:
        await ctx.reply("Attach a scoreboard screenshot and type `!add`.")
        return

    added = 0
    for attachment in valid:
        try:
            data = await attachment.read()
            sessions[ctx.channel.id].append(data)
            added += 1
        except discord.HTTPException:
            await ctx.reply(f"I could not read `{attachment.filename}`.")

    total = len(sessions[ctx.channel.id])
    await ctx.reply(
        f"Saved {added} screenshot(s). Session total: **{total}**. "
        "Send more with `!add`, then type `!analyze`."
    )

@bot.command(name="analyze")
@commands.cooldown(1, 30, commands.BucketType.channel)
async def analyze(ctx: commands.Context):
    """
    Analyze every saved screenshot in this channel as one session.
    """
    images = sessions.get(ctx.channel.id, [])
    if not images:
        await ctx.reply("No screenshots saved. Attach one and type `!add` first.")
        return

    if len(images) > 12:
        await ctx.reply(
            "This quick version handles up to 12 screenshots per session. "
            "Use `!clear`, then upload a smaller batch."
        )
        return

    async with ctx.typing():
        try:
            report = await analyze_images(images)
        except Exception as exc:
            log.exception("Analysis failed")
            await ctx.reply(
                "The analysis failed. Check the bot console and confirm your "
                "OpenAI API key has available credit."
            )
            return

    await send_long(ctx, report)
    sessions[ctx.channel.id].clear()
    await ctx.send("Session cleared. Upload the next game's screenshots with `!add`.")

@analyze.error
async def analyze_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"Wait {error.retry_after:.0f} seconds before analyzing again.")
    else:
        raise error

@bot.command(name="count")
async def count(ctx: commands.Context):
    total = len(sessions.get(ctx.channel.id, []))
    await ctx.reply(f"This channel currently has **{total}** saved screenshot(s).")

@bot.command(name="clear")
async def clear(ctx: commands.Context):
    sessions[ctx.channel.id].clear()
    await ctx.reply("Saved screenshots cleared.")

@bot.command(name="courtvision")
async def help_command(ctx: commands.Context):
    await ctx.send(
        "**CourtVision commands**\n"
        "• Attach screenshot(s) + `!add` — save them\n"
        "• `!count` — see how many are saved\n"
        "• `!analyze` — analyze all saved screenshots together\n"
        "• `!clear` — erase the current session"
    )

bot.run(DISCORD_TOKEN)
