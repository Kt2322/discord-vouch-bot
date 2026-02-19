import discord
import asyncio
import json
import os
import random
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from datetime import timedelta, datetime

# ----------------- CONFIG -----------------
PREFIX = "$"
TOKEN = os.getenv("TOKEN")
VOUCH_FILE = "vouches.json"
VOUCH_ROLE_ID = 1473083771963310233
BOT_OWNER_ID = 1320875525409083459
PROTECTED_ROLE_ID = 1473083771963310233
TIMEOUT_DURATION = 7 * 24 * 60 * 60  # 7 days

# GIFs
BOTTOM_LEFT_GIF = "https://i.postimg.cc/76xm9q9z/image0-4.gif"
TOP_RIGHT_GIF = "https://i.postimg.cc/5yypcpZX/image0-5.gif"
BACKGROUND_GIF = "https://i.postimg.cc/rsHjqxkW/image0-3.gif"

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

# ----------------- HELPER FUNCTIONS -----------------
async def fetch_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
            return Image.open(BytesIO(data)).convert("RGBA")

def stars_emoji(rating_str):
    try:
        num = int(rating_str)
        if num < 1: num = 1
        if num > 5: num = 5
        return "⭐" * num
    except:
        return rating_str

async def create_vouch_image(vouch):
    width, height = 500, 220
    # Load background GIF frame
    bg_img = await fetch_image(BACKGROUND_GIF)
    img = Image.new("RGBA", (width, height))
    if bg_img:
        bg_img = bg_img.resize((width, height))
        img.paste(bg_img, (0,0))

    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("bubble.ttf", 32)
    except:
        font = ImageFont.load_default()

    # Avatar
    avatar_img = await fetch_image(vouch.get("avatar_url", ""))
    if avatar_img:
        avatar_img = avatar_img.resize((70,70))
        img.paste(avatar_img, (20,60), avatar_img)

    # Text
    draw.text((110, 60), f"{vouch['by']}", fill=(255,255,255), font=font)
    draw.text((110, 100), f"⭐ Rating: {stars_emoji(vouch['rating'])}", fill=(255, 215, 0), font=font)
    draw.text((110, 140), f"🛒 Item: {vouch['item']}", fill=(255, 255, 255), font=font)
    draw.text((110, 180), f"✅ Trusted: {vouch['trusted']}", fill=(144,238,144), font=font)

    # Overlay GIFs
    bottom_left = await fetch_image(BOTTOM_LEFT_GIF)
    if bottom_left:
        bottom_left = bottom_left.resize((50,50))
        img.paste(bottom_left, (10, height-60), bottom_left)

    top_right = await fetch_image(TOP_RIGHT_GIF)
    if top_right:
        top_right = top_right.resize((80,80))
        img.paste(top_right, (width-90,10), top_right)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

async def create_vouch_board_image(vouch_list, per_row=3):
    if not vouch_list:
        vouch_list = []

    card_width, card_height = 500, 220
    rows = (len(vouch_list) + per_row - 1) // per_row
    width, height = card_width*per_row, card_height*rows
    # Background GIF
    bg_img = await fetch_image(BACKGROUND_GIF)
    img = Image.new("RGBA", (width, height))
    if bg_img:
        bg_img = bg_img.resize((width, height))
        img.paste(bg_img, (0,0))

    try:
        font = ImageFont.truetype("bubble.ttf", 28)
    except:
        font = ImageFont.load_default()

    for idx, vouch in enumerate(vouch_list):
        x, y = (idx % per_row)*card_width, (idx // per_row)*card_height
        draw = ImageDraw.Draw(img)
        draw.rectangle([(x, y), (x+card_width, y+card_height-10)], fill=(20,30,60))

        avatar_img = await fetch_image(vouch.get("avatar_url", ""))
        if avatar_img:
            avatar_img = avatar_img.resize((60,60))
            img.paste(avatar_img,(x+10,y+50), avatar_img)

        draw.text((x+80,y+20), f"{vouch['by']}", fill=(255,255,255), font=font)
        draw.text((x+80,y+60), f"⭐ {stars_emoji(vouch['rating'])}", fill=(255,215,0), font=font)
        draw.text((x+80,y+90), f"🛒 {vouch['item']}", fill=(255,255,255), font=font)
        draw.text((x+80,y+120), f"✅ {vouch['trusted']}", fill=(144,238,144), font=font)

    # Overlay GIFs
    bottom_left = await fetch_image(BOTTOM_LEFT_GIF)
    if bottom_left:
        bottom_left = bottom_left.resize((50,50))
        img.paste(bottom_left, (10, height-60), bottom_left)

    top_right = await fetch_image(TOP_RIGHT_GIF)
    if top_right:
        top_right = top_right.resize((80,80))
        img.paste(top_right, (width-90,10), top_right)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# ----------------- EVENTS -----------------
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # ----------------- ANTI ROLE PING -----------------
    protected_ping = f"<@&{PROTECTED_ROLE_ID}>"
    if protected_ping in message.content:
        if not message.author.guild_permissions.administrator:
            try:
                await message.delete()
            except: pass
            try:
                await message.author.timeout(
                    datetime.utcnow() + timedelta(seconds=TIMEOUT_DURATION),
                    reason="Unauthorized protected role ping"
                )
            except Exception as e:
                print("Timeout failed:", e)
            try:
                await message.channel.send(
                    f"🚫 {message.author.mention} You cannot ping that role.\nYou have been timed out for 7 days.",
                    delete_after=5
                )
            except: pass
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

        target = message.mentions[0]
        questions = [
            "⭐ Rate your experience (1-5):",
            "🛒 What did you buy?",
            "✅ Is this user trusted? (yes/no)"
        ]
        answers = []

        def check(m):
            return m.author == message.author and m.channel == message.channel

        question_messages = []

        for q in questions:
            embed = discord.Embed(description=q, color=0x1E1E90)
            qm = await message.channel.send(embed=embed)
            question_messages.append(qm)
            try:
                msg = await client.wait_for("message", check=check, timeout=120)
                answers.append(msg.content)
                await msg.delete()
            except asyncio.TimeoutError:
                await message.channel.send("⏰ Vouch timed out. Please try again.")
                return

        # Delete all questions
        for qm in question_messages:
            await qm.delete()

        # Save vouch
        vouches.setdefault(guild_id, {})
        vouches[guild_id].setdefault(str(target.id), [])
        vouches[guild_id][str(target.id)].append({
            "by": f"{message.author} ({message.author.id})",
            "rating": answers[0],
            "item": answers[1],
            "trusted": answers[2],
            "avatar_url": message.author.avatar.url if message.author.avatar else ""
        })
        save_vouches()

        # Send embed with vouch image
        img_buffer = await create_vouch_image(vouches[guild_id][str(target.id)][-1])
        file = discord.File(fp=img_buffer, filename="vouch.png")
        embed = discord.Embed(title="New Vouch!", color=0x1E1E90)
        embed.set_image(url="attachment://vouch.png")
        await message.channel.send(file=file, embed=embed)

    # ----------------- REVIEWS -----------------
    elif content == f"{PREFIX}reviews" and is_admin:
        if guild_id not in vouches or not vouches[guild_id]:
            await message.channel.send("No vouches yet.")
            return
        vouch_list = [v for uid in vouches[guild_id] for v in vouches[guild_id][uid]]
        img_buffer = await create_vouch_board_image(vouch_list)
        file = discord.File(fp=img_buffer, filename="reviews.png")
        embed = discord.Embed(title="Vouch Board", color=0x1E1E90)
        embed.set_image(url="attachment://reviews.png")
        await message.channel.send(file=file, embed=embed)

# ----------------- RUN -----------------
if not TOKEN:
    raise RuntimeError("TOKEN environment variable not set")

client.run(TOKEN)
