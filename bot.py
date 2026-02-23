import discord
import asyncio
import json
import os
import random
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageSequence
from io import BytesIO
from datetime import timedelta, datetime

# ----------------- CONFIG -----------------
PREFIX = "$"
TOKEN = os.getenv("TOKEN")
VOUCH_FILE = "vouches.json"
VOUCH_ROLE_ID = 1473083771963310233
BOT_OWNER_ID = 1320875525409083459
PROTECTED_ROLE_ID = 1473083771963310233
TIMEOUT_DURATION = 7 * 24 * 60 * 60

SNOW_URL = "https://cdn.discordapp.com/attachments/1472795548917563492/1473875915330027520/image0.gif"
TOP_RIGHT_URL = "https://cdn.discordapp.com/attachments/1472795548917563492/1473875920711581920/image0.gif"
BOTTOM_RIGHT_URL = "https://cdn.discordapp.com/attachments/1472795548917563492/1473875905821540444/image0.gif"

# ----------------- INTENTS -----------------
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
client = discord.Client(intents=intents)

# ----------------- LOAD VOUCHES -----------------
if os.path.exists(VOUCH_FILE):
    with open(VOUCH_FILE, "r") as f:
        vouches = json.load(f)
else:
    vouches = {}

def save_vouches():
    with open(VOUCH_FILE, "w") as f:
        json.dump(vouches, f, indent=4)

# ----------------- IMAGE HELPERS -----------------
async def fetch_gif_frames(url, size):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()

    gif = Image.open(BytesIO(data))
    frames = []
    for frame in ImageSequence.Iterator(gif):
        frame = frame.convert("RGBA").resize(size)
        frames.append(frame.copy())
    return frames

def stars_text(rating):
    try:
        r = max(1, min(5, int(rating)))
        return "★" * r
    except:
        return "★"

# ----------------- CREATE VOUCH IMAGE -----------------
async def create_vouch_image(vouch):
    width, height = 800, 450

    snow_frames = await fetch_gif_frames(SNOW_URL, (width, height))
    top_frames = await fetch_gif_frames(TOP_RIGHT_URL, (180, 180))
    bottom_frames = await fetch_gif_frames(BOTTOM_RIGHT_URL, (200, 200))

    final_frames = []

    for i in range(len(snow_frames)):
        base = snow_frames[i].copy()  # FULL snow no transparency

        top = top_frames[i % len(top_frames)]
        bottom = bottom_frames[i % len(bottom_frames)]

        base.paste(top, (width - 190, 10), top)
        base.paste(bottom, (width - 220, height - 210), bottom)

        draw = ImageDraw.Draw(base)

        try:
            font_big = ImageFont.truetype("bubble.ttf", 50)
            font_small = ImageFont.truetype("bubble.ttf", 32)
        except:
            font_big = ImageFont.load_default()
            font_small = ImageFont.load_default()

        draw.text((40, 40), "NEW VOUCH", font=font_big, fill="white")
        draw.text((40, 120), stars_text(vouch["rating"]), font=font_big, fill="gold")
        draw.text((40, 200), f"Item: {vouch['item']}", font=font_small, fill="white")
        draw.text((40, 260), f"Trusted: {vouch['trusted']}", font=font_small, fill="white")
        draw.text((40, 320), f"By: {vouch['by']}", font=font_small, fill="white")

        final_frames.append(base)

    buffer = BytesIO()
    final_frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=final_frames[1:],
        duration=80,
        loop=0
    )
    buffer.seek(0)
    return buffer

# ----------------- CREATE REVIEWS BOARD -----------------
async def create_vouch_board_image(vouch_list):
    width = 1000
    height = 600

    snow_frames = await fetch_gif_frames(SNOW_URL, (width, height))
    final_frames = []

    for i in range(len(snow_frames)):
        base = snow_frames[i].copy()
        draw = ImageDraw.Draw(base)

        try:
            font = ImageFont.truetype("bubble.ttf", 28)
        except:
            font = ImageFont.load_default()

        y_offset = 40
        for v in vouch_list[-10:]:
            text = f"{v['by']} | {stars_text(v['rating'])} | {v['item']}"
            draw.text((40, y_offset), text, font=font, fill="white")
            y_offset += 50

        final_frames.append(base)

    buffer = BytesIO()
    final_frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=final_frames[1:],
        duration=80,
        loop=0
    )
    buffer.seek(0)
    return buffer

# ----------------- EVENTS -----------------
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    content = message.content.strip()
    guild_id = str(message.guild.id)

    if content.startswith(f"{PREFIX}vouch"):
        if not message.mentions or message.mentions[0].id != BOT_OWNER_ID:
            await message.channel.send(f"❌ You can only vouch for <@{BOT_OWNER_ID}>.")
            return

        target = message.mentions[0]
        questions = [
            "⭐ Rate 1-5:",
            "🛒 What did you buy?",
            "✅ Trusted? yes/no"
        ]

        answers = []
        question_msgs = []

        def check(m):
            return m.author == message.author and m.channel == message.channel

        for q in questions:
            q_msg = await message.channel.send(q)
            question_msgs.append(q_msg)

            try:
                msg = await client.wait_for("message", check=check, timeout=120)
                answers.append(msg.content)
                await msg.delete()
            except asyncio.TimeoutError:
                return await message.channel.send("Timed out.")

        for q in question_msgs:
            await q.delete()

        vouches.setdefault(guild_id, {})
        vouches[guild_id].setdefault(str(target.id), [])
        vouches[guild_id][str(target.id)].append({
            "by": str(message.author),
            "rating": answers[0],
            "item": answers[1],
            "trusted": answers[2]
        })
        save_vouches()

        img_buffer = await create_vouch_image(vouches[guild_id][str(target.id)][-1])
        file = discord.File(img_buffer, filename="vouch.gif")
        embed = discord.Embed(color=0x000000)
        embed.set_image(url="attachment://vouch.gif")
        await message.channel.send(embed=embed, file=file)

    elif content == f"{PREFIX}reviews":
        if guild_id not in vouches:
            return await message.channel.send("No vouches yet.")

        vouch_list = [v for uid in vouches[guild_id] for v in vouches[guild_id][uid]]
        if not vouch_list:
            return await message.channel.send("No vouches yet.")

        img_buffer = await create_vouch_board_image(vouch_list)
        file = discord.File(img_buffer, filename="reviews.gif")
        embed = discord.Embed(color=0x000000)
        embed.set_image(url="attachment://reviews.gif")
        await message.channel.send(embed=embed, file=file)

client.run(TOKEN)
