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
TOKEN = os.getenv("TOKEN")  # Make sure your token is in environment variables
VOUCH_FILE = "vouches.json"
MEMBER_ROLE_ID = 1473083771963310233  # updated member role (fun + vouch + ticket)
BOT_OWNER_ID = 1320875525409083459

# 🔥 PROTECTED ROLE
PROTECTED_ROLE_ID = 1473083771963310233  # role they cannot ping
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

async def create_vouch_image_single(vouch, author_avatar_url):
    width, height = 500, 220
    img = Image.new('RGB', (width, height), color=(40, 42, 54))
    draw = ImageDraw.Draw(img)

    # Use bubble font if available, else fallback
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 28)
        font_body = ImageFont.truetype("arial.ttf", 20)
    except:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    draw.rectangle([(0,0),(width,45)], fill=(95, 158, 160))
    draw.text((20,5), "New Vouch Received", fill=(255,255,255), font=font_title)

    avatar_img = await fetch_avatar_image(author_avatar_url)
    if avatar_img:
        avatar_img = avatar_img.resize((70,70))
        img.paste(avatar_img, (20, 70))

    draw.text((110, 70), f"By: {vouch['by']}", fill=(255,255,255), font=font_body)
    draw.text((110, 100), f"⭐ Rating: {vouch['rating']}", fill=(255,215,0), font=font_body)
    draw.text((110, 130), f"🛒 Item: {vouch['item']}", fill=(173,216,230), font=font_body)
    draw.text((110, 160), f"✅ Trusted: {vouch['trusted']}", fill=(144,238,144), font=font_body)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

async def create_vouch_image_board(vouch_list, per_row=3):
    card_width, card_height = 500, 220
    rows = (len(vouch_list) + per_row - 1) // per_row
    width = card_width * per_row
    height = card_height * rows
    img = Image.new('RGB', (width, height), color=(40, 42, 54))

    try:
        font = ImageFont.truetype("arialbd.ttf", 20)
    except:
        font = ImageFont.load_default()

    for idx, vouch in enumerate(vouch_list):
        x = (idx % per_row) * card_width
        y = (idx // per_row) * card_height
        draw = ImageDraw.Draw(img)

        draw.rectangle([(x,y),(x+card_width,y+card_height-10)], fill=(60,63,80))

        avatar_img = await fetch_avatar_image(vouch['avatar_url'])
        if avatar_img:
            avatar_img = avatar_img.resize((60,60))
            img.paste(avatar_img,(x+10,y+50))

        draw.text((x+80,y+20), f"{vouch['by']}", fill=(255,255,255), font=font)
        draw.text((x+80,y+60), f"⭐ {vouch['rating']}", fill=(255,215,0), font=font)
        draw.text((x+80,y+90), f"🛒 {vouch['item']}", fill=(173,216,230), font=font)
        draw.text((x+80,y+120), f"✅ {vouch['trusted']}", fill=(144,238,144), font=font)

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

    # 🔥 PROTECTED ROLE ANTI-PING
    if f"<@&{PROTECTED_ROLE_ID}>" in message.content:
        if not message.author.guild_permissions.administrator:
            try:
                await message.delete()
            except: pass
            try:
                await message.author.timeout(
                    discord.utils.utcnow() + timedelta(seconds=TIMEOUT_DURATION),
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
    has_member_role = MEMBER_ROLE_ID in user_roles
    is_admin = message.author.guild_permissions.administrator
    is_owner = message.author.id == BOT_OWNER_ID

    # ----------------- HELP -----------------
    if content == f"{PREFIX}help":
        commands = []
        if has_member_role:
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
        if not has_member_role:
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
                await message.channel.send("⏰ Vouch timed out.")
                return

        for qmsg in question_messages:
            await qmsg.delete()

        avatar_url = message.author.display_avatar.url
        vouches.setdefault(guild_id, {})
        vouches[guild_id].setdefault(str(target.id), [])
        vouches[guild_id][str(target.id)].append({
            "by": f"{message.author} ({message.author.id})",
            "rating": answers[0],
            "item": answers[1],
            "trusted": answers[2],
            "avatar_url": avatar_url
        })
        save_vouches()

        try:
            img_buffer = await create_vouch_image_single(vouches[guild_id][str(target.id)][-1], avatar_url)
            await message.channel.send(file=discord.File(fp=img_buffer, filename="vouch.png"))
        except Exception as e:
            await message.channel.send(f"❌ Failed to create vouch image: {e}")

    # ----------------- REVIEWS -----------------
    elif content == f"{PREFIX}reviews" and is_admin:
        if guild_id not in vouches or not vouches[guild_id]:
            await message.channel.send("No vouches yet.")
            return
        vouch_list = []
        for user_vouches in vouches[guild_id].values():
            vouch_list.extend(user_vouches)

        if not vouch_list:
            await message.channel.send("No vouches to display.")
            return

        try:
            img_buffer = await create_vouch_image_board(vouch_list, per_row=3)
            await message.channel.send(file=discord.File(fp=img_buffer, filename="reviews.png"))
        except Exception as e:
            await message.channel.send(f"❌ Failed to create vouch board: {e}")

    # ----------------- OTHER COMMANDS -----------------
    elif content == f"{PREFIX}ping":
        await message.channel.send(f"🏓 Pong! {round(client.latency*1000)}ms")

    elif content.startswith(f"{PREFIX}userinfo"):
        target = message.mentions[0] if message.mentions else message.author
        roles = ", ".join([r.name for r in target.roles if r != message.guild.default_role])
        await message.channel.send(
            f"**User Info:**\nName: {target}\nID: {target.id}\nRoles: {roles}\nJoined: {target.joined_at}"
        )

    elif content == f"{PREFIX}serverinfo":
        await message.channel.send(
            f"**Server Info:**\nName: {message.guild.name}\nID: {message.guild.id}\nMembers: {message.guild.member_count}\nChannels: {len(message.guild.channels)}"
        )

    elif content.startswith(f"{PREFIX}avatar"):
        target = message.mentions[0] if message.mentions else message.author
        await message.channel.send(target.display_avatar.url)

    elif content == f"{PREFIX}coinflip":
        await message.channel.send(random.choice(["🪙 Heads", "🪙 Tails"]))

    elif content == f"{PREFIX}roll":
        await message.channel.send(f"🎲 {random.randint(1,6)}")

    elif content.startswith(f"{PREFIX}8ball"):
        responses = [
            "It is certain.", "Without a doubt.", "Yes.", "Ask again later.",
            "No.", "Very doubtful."
        ]
        await message.channel.send(random.choice(responses))

    elif content == f"{PREFIX}meme":
        memes = [
            "https://i.redd.it/abcd1.jpg",
            "https://i.redd.it/abcd2.jpg",
            "https://i.redd.it/abcd3.jpg"
        ]
        await message.channel.send(random.choice(memes))

# ----------------- RUN -----------------
if not TOKEN:
    raise RuntimeError("TOKEN environment variable not set")

client.run(TOKEN)
