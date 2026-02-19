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
TOKEN = os.getenv("TOKEN")  # your bot token in env variable
VOUCH_FILE = "vouches.json"
VOUCH_ROLE_ID = 1473083771963310233  # updated role ID for members allowed to vouch
BOT_OWNER_ID = 1320875525409083459
PROTECTED_ROLE_ID = 1473083771963310233  # role that cannot be pinged
TIMEOUT_DURATION = 7 * 24 * 60 * 60  # 7 days in seconds

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

# ----------------- GIF CONFIG -----------------
BOTTOM_RIGHT_GIF = "https://i.postimg.cc/grMzTcFM"
TOP_RIGHT_GIF = "https://i.postimg.cc/jDnSfp1c"
SNOW_BG_GIF = "https://i.postimg.cc/c611hgjn"

# ----------------- HELPER FUNCTIONS -----------------
async def fetch_avatar_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
            return Image.open(BytesIO(data)).convert("RGBA")

async def fetch_gif(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
            return Image.open(BytesIO(data))

def stars_emoji_glow(rating_str):
    try:
        num = int(rating_str)
        if num < 1: num = 1
        if num > 5: num = 5
        return "⭐" * num
    except:
        return rating_str

# ----------------- VOUCH IMAGE -----------------
async def create_vouch_image(vouch):
    bg_gif = await fetch_gif(SNOW_BG_GIF)
    bottom_gif = await fetch_gif(BOTTOM_RIGHT_GIF)
    top_gif = await fetch_gif(TOP_RIGHT_GIF)
    
    avatar_img = await fetch_avatar_image(vouch.get("avatar_url", ""))
    if avatar_img:
        avatar_img = avatar_img.resize((70, 70))
    
    try:
        font = ImageFont.truetype("bubble.ttf", 32)
    except:
        font = ImageFont.load_default()
    
    frames = []
    for frame in ImageSequence.Iterator(bg_gif):
        frame = frame.convert("RGBA")
        draw = ImageDraw.Draw(frame)
        
        if avatar_img:
            frame.paste(avatar_img, (20, 60), avatar_img)
        
        draw.text((110, 60), f"{vouch['by']}", fill=(255,255,255), font=font)
        draw.text((110, 100), f"⭐ {stars_emoji_glow(vouch['rating'])}", fill=(0, 255, 255), font=font)
        draw.text((110, 140), f"🛒 {vouch['item']}", fill=(255,255,255), font=font)
        draw.text((110, 180), f"✅ {vouch['trusted']}", fill=(144,238,144), font=font)
        
        if top_gif:
            top_frame = next(ImageSequence.Iterator(top_gif)).convert("RGBA").resize((80, 80))
            frame.paste(top_frame, (frame.width - 90, 10), top_frame)
        if bottom_gif:
            bottom_frame = next(ImageSequence.Iterator(bottom_gif)).convert("RGBA").resize((50, 50))
            frame.paste(bottom_frame, (frame.width - 60, frame.height - 60), bottom_frame)
        
        frames.append(frame)
    
    buffer = BytesIO()
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:], loop=0, duration=100, disposal=2)
    buffer.seek(0)
    return buffer

# ----------------- VOUCH BOARD IMAGE -----------------
async def create_vouch_board_image(vouch_list, per_row=3):
    card_width, card_height = 500, 220
    rows = (len(vouch_list) + per_row - 1) // per_row
    width, height = card_width * per_row, card_height * rows
    
    bg_gif = await fetch_gif(SNOW_BG_GIF)
    bottom_gif = await fetch_gif(BOTTOM_RIGHT_GIF)
    top_gif = await fetch_gif(TOP_RIGHT_GIF)
    
    try:
        font = ImageFont.truetype("bubble.ttf", 28)
    except:
        font = ImageFont.load_default()
    
    frames = []
    for frame in ImageSequence.Iterator(bg_gif):
        frame = frame.convert("RGBA").resize((width, height))
        draw = ImageDraw.Draw(frame)
        
        for idx, vouch in enumerate(vouch_list):
            x, y = (idx % per_row) * card_width, (idx // per_row) * card_height
            draw.rectangle([(x, y), (x + card_width, y + card_height - 10)], fill=(10, 10, 40, 200))  # navy
            
            avatar_img = await fetch_avatar_image(vouch.get("avatar_url", ""))
            if avatar_img:
                avatar_img = avatar_img.resize((60, 60))
                frame.paste(avatar_img, (x + 10, y + 50), avatar_img)
            
            draw.text((x + 80, y + 20), f"{vouch['by']}", fill=(255,255,255), font=font)
            draw.text((x + 80, y + 60), f"⭐ {stars_emoji_glow(vouch['rating'])}", fill=(0, 255, 255), font=font)
            draw.text((x + 80, y + 90), f"🛒 {vouch['item']}", fill=(255,255,255), font=font)
            draw.text((x + 80, y + 120), f"✅ {vouch['trusted']}", fill=(144,238,144), font=font)
        
        if top_gif:
            top_frame = next(ImageSequence.Iterator(top_gif)).convert("RGBA").resize((80, 80))
            frame.paste(top_frame, (frame.width - 90, 10), top_frame)
        if bottom_gif:
            bottom_frame = next(ImageSequence.Iterator(bottom_gif)).convert("RGBA").resize((50, 50))
            frame.paste(bottom_frame, (frame.width - 60, frame.height - 60), bottom_frame)
        
        frames.append(frame)
    
    buffer = BytesIO()
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:], loop=0, duration=100, disposal=2)
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

        for q in questions:
            embed = discord.Embed(description=q, color=0x87CEFA)  # baby blue
            await message.channel.send(embed=embed)
            try:
                msg = await client.wait_for("message", check=check, timeout=120)
                answers.append(msg.content)
                await msg.delete()
            except asyncio.TimeoutError:
                await message.channel.send("⏰ Vouch timed out. Please try again.")
                return

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

        img_buffer = await create_vouch_image(vouches[guild_id][str(target.id)][-1])
        file = discord.File(fp=img_buffer, filename="vouch.gif")
        embed = discord.Embed(title="New Vouch!", color=0x1E1E3F)
        embed.set_image(url="attachment://vouch.gif")
        await message.channel.send(file=file, embed=embed)

    # ----------------- REVIEWS -----------------
    elif content == f"{PREFIX}reviews" and is_admin:
        if guild_id not in vouches or not vouches[guild_id]:
            await message.channel.send("No vouches yet.")
            return
        vouch_list = [v for uid in vouches[guild_id] for v in vouches[guild_id][uid]]
        img_buffer = await create_vouch_board_image(vouch_list)
        file = discord.File(fp=img_buffer, filename="reviews.gif")
        embed = discord.Embed(title="Vouch Board", color=0x1E1E3F)
        embed.set_image(url="attachment://reviews.gif")
        await message.channel.send(file=file, embed=embed)

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
        await message.channel.send(target.avatar.url)

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
