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
MEMBER_ROLE_ID = 1473083771963310233  # updated member/fun + ticket + vouch role
BOT_OWNER_ID = 1320875525409083459
PROTECTED_ROLE_ID = 1473083771963310233  # role that can't be pinged
TIMEOUT_DURATION = 60*60*24*7  # 7 days

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

# ----------------- VOUCH IMAGE (SINGLE) -----------------
async def create_vouch_image_single(vouch, author_avatar_url):
    width, height = 600, 250
    img = Image.new('RGB', (width, height), color=(30,30,40))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("comic.ttf", 36)  # bubble/comic font
        font_body = ImageFont.truetype("comic.ttf", 28)
    except:
        font_title = ImageFont.truetype("arialbd.ttf", 28)
        font_body = ImageFont.truetype("arial.ttf", 24)

    # Header
    draw.rectangle([(0,0),(width,60)], fill=(255,105,180))
    draw.text((20,10), "🌟 New Vouch Received 🌟", fill=(255,255,255), font=font_title)

    # Avatar
    avatar_img = await fetch_avatar_image(author_avatar_url)
    if avatar_img:
        avatar_img = avatar_img.resize((80,80))
        img.paste(avatar_img, (20, 70))

    # Shadow text function
    def draw_shadowed_text(pos, text, color, shadow_color=(0,0,0)):
        x, y = pos
        draw.text((x+2, y+2), text, fill=shadow_color, font=font_body)
        draw.text(pos, text, fill=color, font=font_body)

    draw_shadowed_text((120,70), f"By: {vouch['by']}", (255,255,255))
    draw_shadowed_text((120,110), f"⭐ Rating: {vouch['rating']}", (255,215,0))
    draw_shadowed_text((120,150), f"🛒 Item: {vouch['item']}", (0,191,255))
    draw_shadowed_text((120,190), f"✅ Trusted: {vouch['trusted']}", (144,238,144))

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

# ----------------- VOUCH IMAGE BOARD -----------------
async def create_vouch_image_board(vouch_list, per_row=3):
    card_width, card_height = 600, 250
    rows = (len(vouch_list) + per_row - 1) // per_row
    width = card_width * per_row
    height = card_height * rows
    img = Image.new('RGB', (width, height), color=(30,30,40))

    try:
        font = ImageFont.truetype("comic.ttf", 28)
    except:
        font = ImageFont.truetype("arialbd.ttf", 24)

    for idx, vouch in enumerate(vouch_list):
        x = (idx % per_row) * card_width
        y = (idx // per_row) * card_height
        draw = ImageDraw.Draw(img)

        draw.rectangle([(x,y),(x+card_width,y+card_height-10)], fill=(70,70,100))

        avatar_img = await fetch_avatar_image(vouch['avatar_url'])
        if avatar_img:
            avatar_img = avatar_img.resize((70,70))
            img.paste(avatar_img,(x+15,y+60))

        draw.text((x+100,y+20), f"{vouch['by']}", fill=(255,255,255), font=font)
        draw.text((x+100,y+70), f"⭐ {vouch['rating']}", fill=(255,215,0), font=font)
        draw.text((x+100,y+110), f"🛒 {vouch['item']}", fill=(0,191,255), font=font)
        draw.text((x+100,y+150), f"✅ {vouch['trusted']}", fill=(144,238,144), font=font)

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

    guild_id = str(message.guild.id)
    content = message.content.strip()
    user_roles = [role.id for role in message.author.roles]
    has_member_role = MEMBER_ROLE_ID in user_roles
    is_admin = message.author.guild_permissions.administrator
    is_owner = message.author.id == BOT_OWNER_ID

    # ----------------- ANTI ROLE PING -----------------
    protected_ping = f"<@&{PROTECTED_ROLE_ID}>"
    if protected_ping in content and not is_admin:
        try: await message.delete()
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
                f"🚫 {message.author.mention} You cannot ping that role.\nTimed out 7 days.",
                delete_after=5
            )
        except: pass
        return

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
                await message.channel.send("⏰ Vouch timed out. Please try again.")
                return
        for qmsg in question_messages: await qmsg.delete()

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

        img_buffer = await create_vouch_image_single(
            vouches[guild_id][str(target.id)][-1],
            message.author.avatar.url if message.author.avatar else ""
        )
        await message.channel.send(file=discord.File(fp=img_buffer, filename="vouch.png"))

    # ----------------- REVIEWS -----------------
    elif content == f"{PREFIX}reviews" and is_admin:
        if guild_id not in vouches or not vouches[guild_id]:
            await message.channel.send("No vouches yet.")
            return
        vouch_list = [v for uid in vouches[guild_id] for v in vouches[guild_id][uid]]
        img_buffer = await create_vouch_image_board(vouch_list, per_row=3)
        await message.channel.send(file=discord.File(fp=img_buffer, filename="reviews.png"))

    # ----------------- TICKET -----------------
    elif content.startswith(f"{PREFIX}ticket"):
        if has_member_role and content == f"{PREFIX}ticket":
            overwrites = {
                message.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                message.author: discord.PermissionOverwrite(read_messages=True),
                message.guild.get_member(BOT_OWNER_ID): discord.PermissionOverwrite(read_messages=True)
            }
            channel = await message.guild.create_text_channel(f"ticket-{message.author.name}", overwrites=overwrites)
            await channel.send(f"Ticket created by {message.author.mention}")
        elif (is_admin or is_owner) and message.mentions:
            target = message.mentions[0]
            overwrites = {
                message.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                target: discord.PermissionOverwrite(read_messages=True),
                message.author: discord.PermissionOverwrite(read_messages=True)
            }
            channel = await message.guild.create_text_channel(f"ticket-{target.name}", overwrites=overwrites)
            await channel.send(f"Ticket created with {target.mention}")
        else:
            await message.channel.send("❌ You cannot use this command this way.")

    # ----------------- CLOSE TICKET -----------------
    elif content == f"{PREFIX}close" and message.author.id == BOT_OWNER_ID:
        await message.channel.delete()

    # ----------------- ADMIN / MOD -----------------
    elif content == f"{PREFIX}lock" and is_admin:
        overwrite = message.channel.overwrites_for(message.guild.default_role)
        overwrite.send_messages = False
        await message.channel.set_permissions(message.guild.default_role, overwrite=overwrite)
        await message.channel.send("🔒 Channel locked.")

    elif content == f"{PREFIX}unlock" and is_admin:
        overwrite = message.channel.overwrites_for(message.guild.default_role)
        overwrite.send_messages = True
        await message.channel.set_permissions(message.guild.default_role, overwrite=overwrite)
        await message.channel.send("🔓 Channel unlocked.")

    elif content.startswith(f"{PREFIX}kick") and is_admin and message.mentions:
        await message.mentions[0].kick()
        await message.channel.send("👢 User kicked.")

    elif content.startswith(f"{PREFIX}ban") and is_admin and message.mentions:
        await message.mentions[0].ban()
        await message.channel.send("⛔ User banned.")

    elif content.startswith(f"{PREFIX}unban") and is_admin:
        try:
            user_tag = content.split(" ", 1)[1]
            name, discrim = user_tag.split("#")
        except:
            await message.channel.send("❌ Use: $unban username#1234")
            return
        for ban in await message.guild.bans():
            user = ban.user
            if user.name == name and user.discriminator == discrim:
                await message.guild.unban(user)
                await message.channel.send("✅ User unbanned.")
                return

    # ----------------- FUN / UTILITY -----------------
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
