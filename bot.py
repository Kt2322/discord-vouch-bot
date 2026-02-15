import discord
import asyncio
import json
import os
import random
from PIL import Image, ImageDraw, ImageFont
import io

# ----------------- CONFIG -----------------
PREFIX = "$"
TOKEN = os.getenv("TOKEN")  # TOKEN MUST BE SET IN ENV VARIABLES
VOUCH_FILE = "vouches.json"
VOUCH_ROLE_ID = 1472071858047422514  # Member role limited to fun + vouch
BOT_OWNER_ID = 1320875525409083459  # Only this user can be vouched for

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

# ----------------- ACTIVE TICKETS -----------------
active_tickets = {}  # {channel_id: user_id}

# ----------------- READY -----------------
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

# ----------------- MESSAGE HANDLER -----------------
@client.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    content = message.content.strip()
    guild_id = str(message.guild.id)

    user_roles = [role.id for role in message.author.roles]
    has_vouch_role = VOUCH_ROLE_ID in user_roles
    is_admin = message.author.guild_permissions.administrator

    # ----------------- HELP -----------------
    if content == f"{PREFIX}help":
        commands = []
        if has_vouch_role:
            commands += [
                "$vouch @user — submit a vouch (essay style)",
                "$ping, $userinfo @user, $serverinfo, $avatar @user",
                "$coinflip, $roll, $8ball question, $meme",
                "$ticket — open a private ticket with bot owner"
            ]
        if is_admin:
            commands += [
                "$reviews — show all vouches as an image",
                "$lock/$unlock — lock channel",
                "$kick/$ban/$unban — moderation",
                "$ticket @user — open ticket with specific user",
                "$close — close ticket in this channel"
            ]
        if not commands:
            # Regular members without vouch role
            commands += [
                "$ping, $userinfo @user, $serverinfo, $avatar @user",
                "$coinflip, $roll, $8ball question, $meme"
            ]

        help_text = "**Available Commands:**\n" + "\n".join(commands)
        await message.channel.send(help_text)

    # ----------------- VOUCH -----------------
    elif content.startswith(f"{PREFIX}vouch"):
        if not has_vouch_role:
            await message.channel.send("❌ You are not allowed to vouch.")
            return
        if not message.mentions:
            await message.channel.send("❌ Mention a user to vouch for.")
            return

        target = message.mentions[0]
        if target.id != BOT_OWNER_ID:
            await message.channel.send("❌ You can only vouch for the bot owner.")
            return

        essay_template = (
            f"**Vouch Template for {target.mention}**\n"
            "Fill in your answers below in this format:\n\n"
            "1️⃣ Experience Rating:\n"
            "2️⃣ Item Bought:\n"
            "3️⃣ Is this user trusted (yes/no):\n\n"
            "Please reply with your answers in one message."
        )
        await message.channel.send(essay_template)

        def check(m):
            return m.author == message.author and m.channel == message.channel

        try:
            reply = await client.wait_for("message", check=check, timeout=300)
        except asyncio.TimeoutError:
            await message.channel.send("⏰ Vouch timed out. Please try again.")
            return

        # Parse user answers from lines
        lines = reply.content.splitlines()
        answers = {"rating": "", "item": "", "trusted": ""}
        for line in lines:
            if "1️⃣" in line:
                answers["rating"] = line.split(":", 1)[-1].strip()
            elif "2️⃣" in line:
                answers["item"] = line.split(":", 1)[-1].strip()
            elif "3️⃣" in line:
                answers["trusted"] = line.split(":", 1)[-1].strip()

        # Save vouch
        vouches.setdefault(guild_id, {})
        vouches[guild_id].setdefault(str(target.id), [])
        vouches[guild_id][str(target.id)].append({
            "by": f"{message.author} ({message.author.id})",
            "rating": answers["rating"],
            "item": answers["item"],
            "trusted": answers["trusted"]
        })
        save_vouches()

        # Send summary embed
        embed = discord.Embed(title=f"Vouch Recorded by {message.author}", color=discord.Color.green())
        embed.add_field(name="Vouched User", value=target.mention, inline=False)
        embed.add_field(name="Experience Rating", value=answers["rating"] or "Not provided", inline=False)
        embed.add_field(name="Item Bought", value=answers["item"] or "Not provided", inline=False)
        embed.add_field(name="Trusted?", value=answers["trusted"] or "Not provided", inline=False)
        await message.channel.send(embed=embed)

    # ----------------- REVIEWS IMAGE -----------------
    elif content == f"{PREFIX}reviews" and is_admin:
        if guild_id not in vouches or not vouches[guild_id]:
            await message.channel.send("No vouches recorded yet.")
            return

        # Image settings
        width = 800
        card_height = 120
        padding = 20
        font_path = "arial.ttf"  # Make sure this font is available
        font_title = ImageFont.truetype(font_path, 24)
        font_text = ImageFont.truetype(font_path, 20)

        vouch_list = []
        for user_id, user_vouches in vouches[guild_id].items():
            for v in user_vouches:
                vouch_list.append(v)

        total_height = padding + len(vouch_list) * (card_height + padding)
        img = Image.new("RGB", (width, total_height), color=(30, 30, 30))
        draw = ImageDraw.Draw(img)

        y_offset = padding
        for idx, v in enumerate(vouch_list, start=1):
            draw.rectangle(
                [padding, y_offset, width - padding, y_offset + card_height],
                fill=(50, 50, 50),
                outline=(255, 255, 255)
            )
            draw.text((padding + 10, y_offset + 10), f"Vouch #{idx} by {v['by']}", font=font_title, fill=(255, 255, 255))
            draw.text((padding + 10, y_offset + 50), f"Experience: {v['rating']}", font=font_text, fill=(200, 200, 200))
            draw.text((padding + 10, y_offset + 75), f"Item: {v['item']}", font=font_text, fill=(200, 200, 200))
            draw.text((padding + 400, y_offset + 75), f"Trusted: {v['trusted']}", font=font_text, fill=(200, 200, 200))
            y_offset += card_height + padding

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        await message.channel.send(file=discord.File(fp=buffer, filename="vouch_board.png"))

    # ----------------- TICKETS -----------------
    elif content == f"{PREFIX}ticket" and has_vouch_role:
        if message.channel.id in active_tickets:
            await message.channel.send("❌ You already have an active ticket here.")
            return
        overwrites = {
            message.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            message.author: discord.PermissionOverwrite(read_messages=True),
            message.guild.get_member(BOT_OWNER_ID): discord.PermissionOverwrite(read_messages=True)
        }
        ticket_channel = await message.guild.create_text_channel(f"ticket-{message.author.name}", overwrites=overwrites)
        active_tickets[ticket_channel.id] = message.author.id
        await ticket_channel.send(f"Ticket created! {message.author.mention} and bot owner can chat here.")

    elif content.startswith(f"{PREFIX}ticket") and is_admin:
        mentions = message.mentions
        if mentions:
            target = mentions[0]
            overwrites = {
                message.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                target: discord.PermissionOverwrite(read_messages=True),
                message.author: discord.PermissionOverwrite(read_messages=True)
            }
            ticket_channel = await message.guild.create_text_channel(f"ticket-{target.name}", overwrites=overwrites)
            active_tickets[ticket_channel.id] = target.id
            await ticket_channel.send(f"Ticket created! {target.mention} and {message.author.mention} can chat here.")

    elif content == f"{PREFIX}close" and is_admin:
        if message.channel.id in active_tickets:
            await message.channel.send("Ticket closed. Deleting channel...")
            del active_tickets[message.channel.id]
            await message.channel.delete()
        else:
            await message.channel.send("❌ No ticket to close in this channel.")

    # ----------------- ADMIN COMMANDS -----------------
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
