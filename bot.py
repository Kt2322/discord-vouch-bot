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

# 🔥 PROTECTED ROLE (cannot be pinged)
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
    if not url:
        return None
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
            return Image.open(BytesIO(data)).convert("RGBA")

# ----------------- UPDATED VOUCH CARD -----------------
async def create_vouch_image_single(vouch, avatar_url):
    width, height = 520, 240
    img = Image.new("RGB", (width, height), (28, 28, 38))
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
        body_font = ImageFont.truetype("DejaVuSans.ttf", 18)
    except:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    # Header
    draw.rectangle([(0, 0), (width, 50)], fill=(70, 130, 180))
    draw.text((20, 12), "⭐ New Vouch", fill="white", font=title_font)

    # Avatar
    avatar = await fetch_avatar_image(avatar_url)
    if avatar:
        avatar = avatar.resize((70, 70))
        img.paste(avatar, (20, 80))

    # Text
    draw.text((110, 80), f"By: {vouch['by']}", fill="white", font=body_font)
    draw.text((110, 110), f"Rating: {vouch['rating']}/5", fill=(255, 215, 0), font=body_font)
    draw.text((110, 140), f"Item: {vouch['item']}", fill=(173, 216, 230), font=body_font)
    draw.text((110, 170), f"Trusted: {vouch['trusted']}", fill=(144, 238, 144), font=body_font)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# ----------------- UPDATED VOUCH BOARD -----------------
async def create_vouch_image_board(vouch_list, per_row=3):
    card_w, card_h = 520, 240
    rows = (len(vouch_list) + per_row - 1) // per_row
    img = Image.new("RGB", (card_w * per_row, card_h * rows), (28, 28, 38))

    for i, vouch in enumerate(vouch_list):
        x = (i % per_row) * card_w
        y = (i // per_row) * card_h
        draw = ImageDraw.Draw(img)

        draw.rectangle([(x, y), (x + card_w - 10, y + card_h - 10)], fill=(45, 45, 60))

        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
        except:
            font = ImageFont.load_default()

        avatar = await fetch_avatar_image(vouch["avatar_url"])
        if avatar:
            avatar = avatar.resize((60, 60))
            img.paste(avatar, (x + 15, y + 60))

        draw.text((x + 90, y + 20), vouch["by"], fill="white", font=font)
        draw.text((x + 90, y + 70), f"⭐ {vouch['rating']}/5", fill=(255, 215, 0), font=font)
        draw.text((x + 90, y + 100), f"🛒 {vouch['item']}", fill=(173, 216, 230), font=font)
        draw.text((x + 90, y + 130), f"✅ {vouch['trusted']}", fill=(144, 238, 144), font=font)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
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

    # 🔥 STRICT ROLE PING PROTECTION
    protected_ping = f"<@&{PROTECTED_ROLE_ID}>"
    if protected_ping in message.content:
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
            except:
                pass

            try:
                await message.channel.send(
                    f"🚫 {message.author.mention} You cannot ping that role.\nTimed out for 7 days.",
                    delete_after=5
                )
            except:
                pass
            return

    content = message.content.strip()
    guild_id = str(message.guild.id)

    user_roles = [role.id for role in message.author.roles]
    has_vouch_role = VOUCH_ROLE_ID in user_roles
    is_admin = message.author.guild_permissions.administrator
    is_owner = message.author.id == BOT_OWNER_ID

    # ----------------- HELP -----------------
    if content == f"{PREFIX}help":
        await message.channel.send("Bot is active ✅")

    # ----------------- VOUCH -----------------
    elif content.startswith(f"{PREFIX}vouch"):
        if not has_vouch_role:
            await message.channel.send("❌ You are not allowed to vouch.")
            return
        if not message.mentions or message.mentions[0].id != BOT_OWNER_ID:
            await message.channel.send(f"❌ You can only vouch for <@{BOT_OWNER_ID}>.")
            return

        target = message.mentions[0]
        questions = [
            "⭐ Rate your experience (1-5):",
            "🛒 What did you buy?",
            "✅ Is this user trusted? (yes/no)"
        ]
        answers = []

        def check(m):
            return m.author == message.author and m.channel == message.channel

        for q in questions:
            await message.channel.send(q)
            try:
                msg = await client.wait_for("message", check=check, timeout=120)
                answers.append(msg.content)
                await msg.delete()
            except asyncio.TimeoutError:
                await message.channel.send("⏰ Vouch timed out.")
                return

        vouches.setdefault(guild_id, {})
        vouches[guild_id].setdefault(str(target.id), [])
        vouches[guild_id][str(target.id)].append({
            "by": f"{message.author}",
            "rating": answers[0],
            "item": answers[1],
            "trusted": answers[2],
            "avatar_url": message.author.avatar.url if message.author.avatar else ""
        })
        save_vouches()

        img = await create_vouch_image_single(
            vouches[guild_id][str(target.id)][-1],
            message.author.avatar.url if message.author.avatar else ""
        )
        await message.channel.send(file=discord.File(img, "vouch.png"))

    # ----------------- REVIEWS -----------------
    elif content == f"{PREFIX}reviews" and is_admin:
        if guild_id not in vouches or not vouches[guild_id]:
            await message.channel.send("No vouches yet.")
            return

        vouch_list = [v for uid in vouches[guild_id] for v in vouches[guild_id][uid]]
        img = await create_vouch_image_board(vouch_list)
        await message.channel.send(file=discord.File(img, "reviews.png"))

    # ----------------- REST OF YOUR ORIGINAL COMMANDS -----------------
    elif content == f"{PREFIX}ping":
        await message.channel.send(f"🏓 Pong! {round(client.latency*1000)}ms")

    elif content == f"{PREFIX}coinflip":
        await message.channel.send(random.choice(["🪙 Heads", "🪙 Tails"]))

    elif content == f"{PREFIX}roll":
        await message.channel.send(f"🎲 {random.randint(1,6)}")

    elif content.startswith(f"{PREFIX}8ball"):
        await message.channel.send(random.choice([
            "It is certain.", "Without a doubt.", "Yes.",
            "Ask again later.", "No.", "Very doubtful."
        ]))

# ----------------- RUN -----------------
if not TOKEN:
    raise RuntimeError("TOKEN environment variable not set")

client.run(TOKEN)
