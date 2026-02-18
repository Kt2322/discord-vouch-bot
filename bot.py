import discord
import asyncio
import json
import os
import random
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import timedelta

# ----------------- CONFIG -----------------
PREFIX = "$"
TOKEN = os.getenv("TOKEN")
VOUCH_FILE = "vouches.json"
VOUCH_ROLE_ID = 1472071858047422514
BOT_OWNER_ID = 1320875525409083459

PROTECTED_ROLE_ID = 1473083771963310233
TIMEOUT_DURATION = 60 * 60 * 24 * 7  # 7 days

# ----------------- INTENTS -----------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

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

# ----------------- HELPER: FETCH AVATAR -----------------
async def fetch_avatar_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
            return Image.open(BytesIO(data)).convert("RGBA")

# ----------------- COLORFUL VOUCH CARD -----------------
async def create_vouch_image_single(vouch, avatar_url):
    width, height = 650, 300
    img = Image.new("RGB", (width, height), (25, 26, 36))
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
        body_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
    except:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    # Gradient header
    draw.rectangle([(0, 0), (width, 70)], fill=(255, 105, 180))

    # Avatar
    avatar = await fetch_avatar_image(avatar_url)
    if avatar:
        avatar = avatar.resize((100, 100))
        img.paste(avatar, (30, 100))

    draw.text((150, 15), "⭐ NEW REVIEW", fill=(255,255,255), font=title_font)

    draw.text((150, 100), f"By: {vouch['by']}", fill=(0,255,255), font=body_font)
    draw.text((150, 140), f"Rating: {vouch['rating']}", fill=(255,215,0), font=body_font)
    draw.text((150, 180), f"Item: {vouch['item']}", fill=(173,216,230), font=body_font)
    draw.text((150, 220), f"Trusted: {vouch['trusted']}", fill=(144,238,144), font=body_font)

    buffer = BytesIO()
    img.save(buffer, "PNG")
    buffer.seek(0)
    return buffer

# ----------------- COLORFUL REVIEW BOARD -----------------
async def create_vouch_image_board(vouch_list):
    per_row = 2
    card_w, card_h = 650, 300
    rows = (len(vouch_list) + per_row - 1) // per_row

    board = Image.new("RGB", (card_w * per_row, card_h * rows), (18,18,28))

    for index, vouch in enumerate(vouch_list):
        card = await create_vouch_image_single(vouch, vouch["avatar_url"])
        card_img = Image.open(card)
        x = (index % per_row) * card_w
        y = (index // per_row) * card_h
        board.paste(card_img, (x, y))

    buffer = BytesIO()
    board.save(buffer, "PNG")
    buffer.seek(0)
    return buffer

# ----------------- READY -----------------
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

# ----------------- MESSAGE HANDLER -----------------
@client.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # -------- STRICT ROLE PING BLOCK --------
    if f"<@&{PROTECTED_ROLE_ID}>" in message.content:
        if not message.author.guild_permissions.administrator:
            try:
                await message.delete()
            except:
                pass

            try:
                await message.author.timeout(
                    discord.utils.utcnow() + timedelta(seconds=TIMEOUT_DURATION),
                    reason="Unauthorized protected role ping"
                )
            except Exception as e:
                print("Timeout failed:", e)

            await message.channel.send(
                f"🚫 {message.author.mention} You cannot ping that role.\n"
                f"You have been timed out for 7 days.",
                delete_after=5
            )
            return

    content = message.content.strip()
    guild_id = str(message.guild.id)

    user_roles = [role.id for role in message.author.roles]
    has_vouch_role = VOUCH_ROLE_ID in user_roles
    is_admin = message.author.guild_permissions.administrator
    is_owner = message.author.id == BOT_OWNER_ID

    # ----------------- VOUCH -----------------
    if content.startswith(f"{PREFIX}vouch"):
        if not has_vouch_role:
            await message.channel.send("❌ You are not allowed to vouch.")
            return

        if not message.mentions or message.mentions[0].id != BOT_OWNER_ID:
            await message.channel.send(f"❌ You can only vouch for <@{BOT_OWNER_ID}>.")
            return

        questions = [
            "Rate 1-5:",
            "What did you buy?",
            "Trusted? (yes/no)"
        ]

        answers = []

        def check(m):
            return m.author == message.author and m.channel == message.channel

        prompts = []
        for q in questions:
            prompt = await message.channel.send(q)
            prompts.append(prompt)

            try:
                reply = await client.wait_for("message", check=check, timeout=120)
                answers.append(reply.content)
                await reply.delete()
            except asyncio.TimeoutError:
                await message.channel.send("Timed out.")
                return

        for p in prompts:
            await p.delete()

        vouches.setdefault(guild_id, {})
        vouches[guild_id].setdefault(str(BOT_OWNER_ID), [])
        vouches[guild_id][str(BOT_OWNER_ID)].append({
            "by": f"{message.author}",
            "rating": answers[0],
            "item": answers[1],
            "trusted": answers[2],
            "avatar_url": message.author.avatar.url
        })
        save_vouches()

        img = await create_vouch_image_single(
            vouches[guild_id][str(BOT_OWNER_ID)][-1],
            message.author.avatar.url
        )

        await message.channel.send(file=discord.File(img, "vouch.png"))

    # ----------------- REVIEWS -----------------
    elif content == f"{PREFIX}reviews" and is_admin:
        if guild_id not in vouches or str(BOT_OWNER_ID) not in vouches[guild_id]:
            await message.channel.send("No vouches yet.")
            return

        img = await create_vouch_image_board(
            vouches[guild_id][str(BOT_OWNER_ID)]
        )
        await message.channel.send(file=discord.File(img, "reviews.png"))

# ----------------- RUN -----------------
if not TOKEN:
    raise RuntimeError("TOKEN not set")

client.run(TOKEN)
