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
async def load_gif(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()
    return Image.open(BytesIO(data))

def stars_emoji(rating):
    try:
        num = max(1, min(5, int(rating)))
        return "⭐" * num
    except:
        return "⭐"

# ----------------- CREATE ANIMATED VOUCH -----------------
async def create_vouch_image(vouch):
    width, height = 800, 400
    snow = await load_gif(SNOW_URL)
    top = await load_gif(TOP_RIGHT_URL)
    bottom = await load_gif(BOTTOM_RIGHT_URL)

    frames = []
    font = ImageFont.truetype("bubble.ttf", 40)

    for frame in ImageSequence.Iterator(snow):
        base = frame.convert("RGBA").resize((width, height))

        # paste decorations
        t = top.copy().convert("RGBA").resize((160,160))
        b = bottom.copy().convert("RGBA").resize((180,180))

        base.paste(t, (width-170, 10), t)
        base.paste(b, (width-190, height-190), b)

        draw = ImageDraw.Draw(base)

        draw.text((50, 40), "NEW VOUCH", fill="white", font=font)
        draw.text((50, 130), stars_emoji(vouch["rating"]), fill="gold", font=font)
        draw.text((50, 210), f"Item: {vouch['item']}", fill="white", font=font)
        draw.text((50, 280), f"Trusted: {vouch['trusted']}", fill="white", font=font)

        frames.append(base)

    buffer = BytesIO()
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0
    )
    buffer.seek(0)
    return buffer

# ----------------- CREATE REVIEW BOARD -----------------
async def create_vouch_board_image(vouch_list):
    width = 1000
    height = 500 + (len(vouch_list) * 120)

    snow = await load_gif(SNOW_URL)
    frames = []
    font = ImageFont.truetype("bubble.ttf", 30)

    for frame in ImageSequence.Iterator(snow):
        base = frame.convert("RGBA").resize((width, height))
        draw = ImageDraw.Draw(base)

        y = 100
        for v in vouch_list:
            draw.text((100, y), f"{stars_emoji(v['rating'])} | {v['item']} | {v['trusted']}", fill="white", font=font)
            y += 100

        frames.append(base)

    buffer = BytesIO()
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
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

    # ----------------- HELP -----------------
    if content == f"{PREFIX}help":
        await message.channel.send("Commands: $vouch @user, $reviews, $ping, $coinflip, $roll")

    # ----------------- VOUCH -----------------
    elif content.startswith(f"{PREFIX}vouch"):
        if not message.mentions:
            return await message.channel.send("Mention the owner.")

        questions = [
            "⭐ Rate 1-5",
            "🛒 What item?",
            "✅ Trusted? yes/no"
        ]

        prompts = []
        answers = []

        def check(m):
            return m.author == message.author and m.channel == message.channel

        for q in questions:
            msg = await message.channel.send(q)
            prompts.append(msg)
            try:
                reply = await client.wait_for("message", timeout=120, check=check)
                answers.append(reply)
            except asyncio.TimeoutError:
                return await message.channel.send("Timed out.")

        # delete questions + answers
        for m in prompts + answers:
            try:
                await m.delete()
            except:
                pass

        vouches.setdefault(guild_id, [])
        vouches[guild_id].append({
            "rating": answers[0].content,
            "item": answers[1].content,
            "trusted": answers[2].content
        })
        save_vouches()

        img = await create_vouch_image(vouches[guild_id][-1])
        file = discord.File(img, filename="vouch.gif")
        embed = discord.Embed(color=0x0b1c2d)
        embed.set_image(url="attachment://vouch.gif")
        await message.channel.send(file=file, embed=embed)

    # ----------------- REVIEWS -----------------
    elif content == f"{PREFIX}reviews":
        if guild_id not in vouches or not vouches[guild_id]:
            return await message.channel.send("No vouches yet.")

        img = await create_vouch_board_image(vouches[guild_id])
        file = discord.File(img, filename="reviews.gif")
        embed = discord.Embed(color=0x0b1c2d)
        embed.set_image(url="attachment://reviews.gif")
        await message.channel.send(file=file, embed=embed)

    # ----------------- FUN COMMANDS -----------------
    elif content == f"{PREFIX}ping":
        await message.channel.send(f"Pong {round(client.latency*1000)}ms")

    elif content == f"{PREFIX}coinflip":
        await message.channel.send(random.choice(["Heads","Tails"]))

    elif content == f"{PREFIX}roll":
        await message.channel.send(str(random.randint(1,6)))

# ----------------- RUN -----------------
if not TOKEN:
    raise RuntimeError("TOKEN not set")

client.run(TOKEN)
