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
VOUCH_ROLE_ID = 1473083771963310233  # Updated role for fun, utility, ticket
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

# ----------------- HELPER: CREATE VOUCH IMAGE -----------------
async def fetch_avatar_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
            return Image.open(BytesIO(data)).convert("RGBA")

def load_bubble_font(size):
    try:
        return ImageFont.truetype("BubbleFont.ttf", size)
    except:
        return ImageFont.truetype("arialbd.ttf", size)

async def create_vouch_image_single(vouch):
    width, height = 500, 220
    img = Image.new('RGB', (width, height), color=(173,216,230))  # baby blue background
    draw = ImageDraw.Draw(img)

    header_font = load_bubble_font(28)
    body_font = load_bubble_font(22)

    # Draw pink header bar
    draw.rectangle([(0,0),(width,50)], fill=(255,105,180))
    draw.text((20, 10), "New Vouch Received!", fill=(255,255,255), font=header_font)

    # Avatar
    avatar_img = await fetch_avatar_image(vouch['avatar_url'])
    if avatar_img:
        avatar_img = avatar_img.resize((70,70))
        img.paste(avatar_img, (20, 70))

    # Vouch info
    draw.text((110, 70), f"By: {vouch['by']}", fill=(255,255,255), font=body_font)
    draw.text((110, 110), f"⭐ Rating: {vouch['rating']}", fill=(255,215,0), font=body_font)
    draw.text((110, 150), f"🛒 Item: {vouch['item']}", fill=(255,182,193), font=body_font)
    draw.text((110, 190), f"✅ Trusted: {vouch['trusted']}", fill=(144,238,144), font=body_font)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

async def create_vouch_image_board(vouch_list, per_row=3):
    card_width, card_height = 500, 220
    rows = (len(vouch_list) + per_row - 1) // per_row
    width = card_width * per_row
    height = card_height * rows
    img = Image.new('RGB', (width, height), color=(173,216,230))  # baby blue background

    for idx, vouch in enumerate(vouch_list):
        x = (idx % per_row) * card_width
        y = (idx // per_row) * card_height
        draw = ImageDraw.Draw(img)

        header_font = load_bubble_font(24)
        body_font = load_bubble_font(20)

        # Draw card background
        draw.rectangle([(x, y),(x+card_width,y+card_height-10)], fill=(255,105,180))  # pink header band

        # Avatar
        avatar_img = await fetch_avatar_image(vouch['avatar_url'])
        if avatar_img:
            avatar_img = avatar_img.resize((60,60))
            img.paste(avatar_img,(x+10,y+50))

        # Text
        draw.text((x+80,y+10), f"{vouch['by']}", fill=(255,255,255), font=header_font)
        draw.text((x+80,y+60), f"⭐ {vouch['rating']}", fill=(255,215,0), font=body_font)
        draw.text((x+80,y+100), f"🛒 {vouch['item']}", fill=(255,182,193), font=body_font)
        draw.text((x+80,y+140), f"✅ {vouch['trusted']}", fill=(144,238,144), font=body_font)

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

    # ----------------- ANTI ROLE PING -----------------
    protected_ping = f"<@&{PROTECTED_ROLE_ID}>"
    if protected_ping in message.content and not message.author.guild_permissions.administrator:
        try:
            await message.delete()
        except:
            pass
        try:
            await message.author.timeout(
                datetime.utcnow() + timedelta(seconds=TIMEOUT_DURATION),
                reason="Unauthorized protected role ping"
            )
        except Exception as e:
            print("Timeout failed:", e)
        return

    content = message.content.strip()
    guild_id = str(message.guild.id)

    user_roles = [role.id for role in message.author.roles]
    has_vouch_role = VOUCH_ROLE_ID in user_roles
    is_admin = message.author.guild_permissions.administrator
    is_owner = message.author.id == BOT_OWNER_ID

    # ----------------- HELP -----------------
    if content == f"{PREFIX}help":
        commands = []
        if has_vouch_role:
            commands += [
                "$vouch @user — submit a vouch",
                "$ticket — create a ticket with bot owner",
                "$ping, $userinfo @user, $serverinfo, $avatar @user",
                "$coinflip, $roll, $8ball question, $meme"
            ]
        if is_admin:
            commands += [
                "$reviews — see all vouches",
                "$ticket @user — create ticket with user",
                "$lock/$unlock — lock channel",
                "$kick/$ban/$unban — moderation"
            ]
        if is_owner:
            commands += ["$close — close your ticket"]
        if not commands:
            commands += [
                "$ping, $userinfo @user, $serverinfo, $avatar @user",
                "$coinflip, $roll, $8ball question, $meme"
            ]
        await message.channel.send("**Available Commands:**\n" + "\n".join(commands))

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

        question_messages = []
        for q in questions:
            msg = await message.channel.send(q)
            question_messages.append(msg)
            try:
                answer = await client.wait_for("message", check=check, timeout=120)
                answers.append(answer.content)
                await answer.delete()
            except asyncio.TimeoutError:
                await message.channel.send("⏰ Vouch timed out. Please try again.")
                return

        # Delete question prompts
        for qmsg in question_messages:
            await qmsg.delete()

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

        img_buffer = await create_vouch_image_single(vouches[guild_id][str(target.id)][-1])
        await message.channel.send(file=discord.File(fp=img_buffer, filename="vouch.png"))

    # ----------------- REVIEWS -----------------
    elif content == f"{PREFIX}reviews" and is_admin:
        if guild_id not in vouches or not vouches[guild_id]:
            await message.channel.send("No vouches yet.")
            return
        vouch_list = [v for uid in vouches[guild_id] for v in vouches[guild_id][uid]]
        img_buffer = await create_vouch_image_board(vouch_list, per_row=3)
        await message.channel.send(file=discord.File(fp=img_buffer, filename="reviews.png"))

    # ----------------- OTHER COMMANDS -----------------
    elif content == f"{PREFIX}ping":
        await message.channel.send(f"🏓 Pong! {round(client.latency*1000)}ms")
    elif content.startswith(f"{PREFIX}userinfo"):
        target = message.mentions[0] if message.mentions else message.author
        roles = ", ".join([r.name for r in target.roles if r != message.guild.default_role])
        await message.channel.send(f"**User Info:**\nName: {target}\nID: {target.id}\nRoles: {roles}\nJoined: {target.joined_at}")
    elif content == f"{PREFIX}serverinfo":
        await message.channel.send(f"**Server Info:**\nName: {message.guild.name}\nID: {message.guild.id}\nMembers: {message.guild.member_count}\nChannels: {len(message.guild.channels)}")
    elif content.startswith(f"{PREFIX}avatar"):
        target = message.mentions[0] if message.mentions else message.author
        await message.channel.send(target.avatar.url)
    elif content == f"{PREFIX}coinflip":
        await message.channel.send(random.choice(["🪙 Heads", "🪙 Tails"]))
    elif content == f"{PREFIX}roll":
        await message.channel.send(f"🎲 {random.randint(1,6)}")
    elif content.startswith(f"{PREFIX}8ball"):
        responses = ["It is certain.", "Without a doubt.", "Yes.", "Ask again later.","No.", "Very doubtful."]
        await message.channel.send(random.choice(responses))
    elif content == f"{PREFIX}meme":
        memes = ["https://i.redd.it/abcd1.jpg","https://i.redd.it/abcd2.jpg","https://i.redd.it/abcd3.jpg"]
        await message.channel.send(random.choice(memes))

# ----------------- RUN -----------------
if not TOKEN:
    raise RuntimeError("TOKEN environment variable not set")
client.run(TOKEN)
