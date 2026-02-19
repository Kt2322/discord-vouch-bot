import discord
import asyncio
import json
import os
import random
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageSequence
from io import BytesIO
from datetime import timedelta, datetime

# ---------------- CONFIG ----------------
PREFIX = "$"
TOKEN = os.getenv("TOKEN")
VOUCH_FILE = "vouches.json"
VOUCH_ROLE_ID = 1473083771963310233
BOT_OWNER_ID = 1320875525409083459
PROTECTED_ROLE_ID = 1473083771963310233
TIMEOUT_DURATION = 7 * 24 * 60 * 60

BG_GIF = "https://i.postimg.cc/rsHjqxkW/image0-3.gif"
BOTTOM_RIGHT_GIF = "https://i.postimg.cc/76xm9q9z/image0-4.gif"
TOP_RIGHT_GIF = "https://i.postimg.cc/5yypcpZX/image0-5.gif"

# --------------- INTENTS ---------------
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)

# --------------- LOAD VOUCHES ---------------
if os.path.exists(VOUCH_FILE):
    with open(VOUCH_FILE, "r") as f:
        vouches = json.load(f)
else:
    vouches = {}

def save_vouches():
    with open(VOUCH_FILE, "w") as f:
        json.dump(vouches, f, indent=4)

# --------------- HELPERS ---------------
async def download_gif(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.read()
                return Image.open(BytesIO(data))
    except:
        return None

async def fetch_avatar_image(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.read()
                return Image.open(BytesIO(data)).convert("RGBA")
    except:
        return None

def stars_emoji(rating_str):
    try:
        num = int(rating_str)
        num = max(1, min(5, num))
        return "⭐" * num
    except:
        return "⭐"

# --------------- ANIMATED VOUCH ---------------
async def create_vouch_image(vouch):

    bg_gif = await download_gif(BG_GIF)
    br_gif = await download_gif(BOTTOM_RIGHT_GIF)
    tr_gif = await download_gif(TOP_RIGHT_GIF)

    if not bg_gif:
        return None

    try:
        font = ImageFont.truetype("bubble.ttf", 32)
    except:
        font = ImageFont.load_default()

    avatar = await fetch_avatar_image(vouch.get("avatar_url", ""))
    if avatar:
        avatar = avatar.resize((90, 90))

    bg_frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(bg_gif)]
    br_frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(br_gif)] if br_gif else []
    tr_frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(tr_gif)] if tr_gif else []

    frames = []
    durations = []

    for i, frame in enumerate(bg_frames[:25]):  # limit frames for Railway safety
        base = frame.resize((700, 350))

        # dark overlay
        overlay = Image.new("RGBA", base.size, (0, 0, 20, 180))
        base = Image.alpha_composite(base, overlay)

        draw = ImageDraw.Draw(base)

        # neon border
        draw.rectangle([(0, 0), (699, 349)], outline=(0, 120, 255), width=6)

        if avatar:
            base.paste(avatar, (30, 120), avatar)

        draw.text((150, 90), f"{vouch['by']}", fill="white", font=font)
        draw.text((150, 140), stars_emoji(vouch['rating']), fill=(255, 215, 0), font=font)
        draw.text((150, 190), f"Item: {vouch['item']}", fill="white", font=font)
        draw.text((150, 240), f"Trusted: {vouch['trusted']}", fill=(0, 255, 150), font=font)

        if br_frames:
            br = br_frames[i % len(br_frames)].resize((80, 80))
            base.paste(br, (600, 250), br)

        if tr_frames:
            tr = tr_frames[i % len(tr_frames)].resize((120, 120))
            base.paste(tr, (550, 10), tr)

        frames.append(base)
        durations.append(bg_gif.info.get("duration", 80))

    buffer = BytesIO()
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2
    )
    buffer.seek(0)
    return buffer

# --------------- ANIMATED BOARD ---------------
async def create_vouch_board_image(vouch_list):

    bg_gif = await download_gif(BG_GIF)
    if not bg_gif:
        return None

    try:
        font = ImageFont.truetype("bubble.ttf", 24)
    except:
        font = ImageFont.load_default()

    bg_frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(bg_gif)]
    frames = []
    durations = []

    for frame in bg_frames[:20]:
        base = frame.resize((900, 500))
        overlay = Image.new("RGBA", base.size, (0, 0, 20, 200))
        base = Image.alpha_composite(base, overlay)

        draw = ImageDraw.Draw(base)
        draw.rectangle([(0, 0), (899, 499)], outline=(0, 120, 255), width=6)

        y = 40
        for v in vouch_list:
            draw.text((50, y),
                      f"{v['by']} | {stars_emoji(v['rating'])} | {v['item']} | {v['trusted']}",
                      fill="white",
                      font=font)
            y += 45

        frames.append(base)
        durations.append(bg_gif.info.get("duration", 80))

    buffer = BytesIO()
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2
    )
    buffer.seek(0)
    return buffer

# --------------- EVENTS ---------------
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    content = message.content.strip()
    guild_id = str(message.guild.id)
    user_roles = [r.id for r in message.author.roles]
    has_vouch_role = VOUCH_ROLE_ID in user_roles
    is_admin = message.author.guild_permissions.administrator

    # -------- VOUCH --------
    if content.startswith(f"{PREFIX}vouch"):

        if not has_vouch_role:
            return await message.channel.send("❌ You cannot vouch.")

        if not message.mentions:
            return await message.channel.send("❌ Mention a user.")

        target = message.mentions[0]
        questions = [
            "⭐ Rate your experience (1-5):",
            "🛒 What did you buy?",
            "✅ Is this user trusted? (yes/no)"
        ]

        answers = []
        question_msgs = []
        answer_msgs = []

        def check(m):
            return m.author == message.author and m.channel == message.channel

        for q in questions:
            q_embed = discord.Embed(description=q, color=0x001f3f)
            qm = await message.channel.send(embed=q_embed)
            question_msgs.append(qm)

            try:
                msg = await client.wait_for("message", check=check, timeout=120)
                answers.append(msg.content)
                answer_msgs.append(msg)
            except asyncio.TimeoutError:
                return await message.channel.send("⏰ Timed out.")

        # DELETE questions + answers
        for m in question_msgs + answer_msgs:
            try:
                await m.delete()
            except:
                pass

        vouches.setdefault(guild_id, {})
        vouches[guild_id].setdefault(str(target.id), [])
        vouches[guild_id][str(target.id)].append({
            "by": str(message.author),
            "rating": answers[0],
            "item": answers[1],
            "trusted": answers[2],
            "avatar_url": message.author.avatar.url if message.author.avatar else ""
        })
        save_vouches()

        img_buffer = await create_vouch_image(
            vouches[guild_id][str(target.id)][-1]
        )

        if not img_buffer:
            return await message.channel.send("Image failed.")

        file = discord.File(img_buffer, filename="vouch.gif")
        embed = discord.Embed(title="New Vouch", color=0x001f3f)
        embed.set_image(url="attachment://vouch.gif")
        await message.channel.send(file=file, embed=embed)

    # -------- REVIEWS --------
    elif content == f"{PREFIX}reviews" and is_admin:

        if guild_id not in vouches or not vouches[guild_id]:
            return await message.channel.send("No vouches yet.")

        vouch_list = [v for uid in vouches[guild_id] for v in vouches[guild_id][uid]]

        img_buffer = await create_vouch_board_image(vouch_list)
        if not img_buffer:
            return await message.channel.send("Image failed.")

        file = discord.File(img_buffer, filename="board.gif")
        embed = discord.Embed(title="Vouch Board", color=0x001f3f)
        embed.set_image(url="attachment://board.gif")
        await message.channel.send(file=file, embed=embed)

# --------------- RUN ---------------
if not TOKEN:
    raise RuntimeError("TOKEN not set")

client.run(TOKEN)
