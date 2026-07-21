import logging
import os
from collections import defaultdict
from typing import Dict, List

import discord
from discord.ext import commands
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")

if not DISCORD_TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("courtvision")
client = genai.Client(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

sessions: Dict[int, List[dict]] = defaultdict(list)
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}

SYSTEM_PROMPT = """
You are Court Vision, an NBA 2K postgame analyst for Rec, Pro-Am, Park, and 3v3 games.
Analyze every supplied scoreboard screenshot as one complete session.

Always include:
1. Overall player rankings from best to worst, with a short explanation.
2. Session MVP.
3. Defensive player of the session.
4. Battles of the night.
5. Best chemistry or teammate pairings.
6. Stock up and stock down.
7. Fairest possible next 3v3 teams.
8. One short final takeaway.

Rules:
- Use only information visible in the screenshots.
- Never invent statistics, matchups, winners, or events.
- Do not judge only by points. Consider efficiency, assists, rebounds, steals,
  blocks, turnovers, teammate impact, and winning when visible.
- Do not claim who guarded whom unless the screenshots clearly prove it.
- If something cannot be determined, say so.
- Keep the report clear, competitive, natural, and easy to read in Discord.
"""

def split_message(text: str, limit: int = 1900) -> List[str]:
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return chunks

async def save_attachments(attachments: List[discord.Attachment]) -> List[dict]:
    saved: List[dict] = []
    for attachment in attachments:
        content_type = (attachment.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            continue
        try:
            image_bytes = await attachment.read()
        except discord.HTTPException:
            continue
        saved.append({"filename": attachment.filename, "mime_type": content_type, "data": image_bytes})
    return saved

async def analyze_images(images: List[dict]) -> str:
    contents = [types.Part.from_text(text=f"{SYSTEM_PROMPT}\n\nAnalyze these {len(images)} NBA 2K scoreboard screenshot(s) as one complete session.")]
    for image in images:
        contents.append(types.Part.from_bytes(data=image["data"], mime_type=image["mime_type"]))
print(f"GEMINI_MODEL = {repr(GEMINI_MODEL)}")
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(temperature=0.35, max_output_tokens=3500),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")
    return response.text.strip()

@bot.event
async def on_ready():
    log.info("Logged in as %s", bot.user)
    await bot.change_presence(activity=discord.Game(name="analyzing 2K runs"))

@bot.command(name="add")
async def add_scoreboard(ctx: commands.Context):
    if not ctx.message.attachments:
        await ctx.reply("Attach one or more 2K scoreboard screenshots and type `!add`.", mention_author=False)
        return
    new_images = await save_attachments(ctx.message.attachments)
    if not new_images:
        await ctx.reply("I couldn't find a supported image. Use PNG, JPG, JPEG, or WEBP.", mention_author=False)
        return
    sessions[ctx.channel.id].extend(new_images)
    total = len(sessions[ctx.channel.id])
    await ctx.reply(f"Saved **{len(new_images)}** screenshot(s). Session total: **{total}**. Send more with `!add`, then type `!analyze`.", mention_author=False)

@bot.command(name="analyze")
@commands.cooldown(1, 30, commands.BucketType.channel)
async def analyze(ctx: commands.Context):
    images = sessions.get(ctx.channel.id, [])
    if not images:
        await ctx.reply("No screenshots are saved. Attach one and type `!add` first.", mention_author=False)
        return
    if len(images) > 12:
        await ctx.reply("This version handles up to 12 screenshots per session. Use `!clear`, then upload a smaller batch.", mention_author=False)
        return
    async with ctx.typing():
        try:
            report = await analyze_images(images)
        except Exception as exc:
            log.exception("Gemini analysis failed: %s", exc)
            await ctx.reply("The analysis failed. Check Railway's newest deploy logs for the exact Gemini error.", mention_author=False)
            return
    for chunk in split_message(report):
        await ctx.send(chunk)
    sessions[ctx.channel.id].clear()
    await ctx.send("Session cleared. Upload the next game's screenshots with `!add`.")

@analyze.error
async def analyze_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(f"Wait {error.retry_after:.0f} seconds before analyzing again.", mention_author=False)
        return
    raise error

@bot.command(name="quick")
async def quick(ctx: commands.Context):
    if not ctx.message.attachments:
        await ctx.reply("Attach one or more screenshots and type `!quick`.", mention_author=False)
        return
    images = await save_attachments(ctx.message.attachments)
    if not images:
        await ctx.reply("I couldn't find a supported image. Use PNG, JPG, JPEG, or WEBP.", mention_author=False)
        return
    async with ctx.typing():
        try:
            report = await analyze_images(images)
        except Exception as exc:
            log.exception("Gemini quick analysis failed: %s", exc)
            await ctx.reply("The quick analysis failed. Check Railway's newest logs.", mention_author=False)
            return
    for chunk in split_message(report):
        await ctx.send(chunk)

@bot.command(name="count")
async def count(ctx: commands.Context):
    total = len(sessions.get(ctx.channel.id, []))
    await ctx.reply(f"This channel currently has **{total}** saved screenshot(s).", mention_author=False)

@bot.command(name="clear")
async def clear(ctx: commands.Context):
    removed = len(sessions.get(ctx.channel.id, []))
    sessions[ctx.channel.id].clear()
    await ctx.reply(f"Cleared **{removed}** saved screenshot(s).", mention_author=False)

@bot.command(name="help", aliases=["courtvision"])

async def help_command(ctx: commands.Context):
    await ctx.send(
        "**🏀 Court Vision Commands**\n"
        "• Attach screenshot(s) + `!add` — save them\n"
        "• `!count` — see how many are saved\n"
        "• `!analyze` — analyze all saved screenshots together\n"
        "• Attach screenshot(s) + `!quick` — analyze immediately\n"
        "• `!clear` — erase the current session\n"
        "• `!help` — show this menu"
    )

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    log.exception("Command error: %s", error)
    await ctx.reply("Something went wrong while running that command.", mention_author=False)

bot.run(DISCORD_TOKEN)
