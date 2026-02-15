import discord
import asyncio
import json
import os

# ----------------- CONFIG -----------------
PREFIX = "$"
TOKEN = os.getenv("TOKEN") # TOKEN MUST BE SET IN ENV VARIABLES
VOUCH_FILE = "vouches.json"
VOUCH_ROLE_ID = 1472071858047422514

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

# ----------------- READY -----------------
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")

# ----------------- MESSAGE HANDLER -----------------
@client.event
async def on_message(message):
    if message.author.bot:
        return

    if not message.guild:
        return

    content = message.content.strip()
    guild_id = str(message.guild.id)

    user_roles = [role.id for role in message.author.roles]
    has_vouch_role = VOUCH_ROLE_ID in user_roles
    is_admin = message.author.guild_permissions.administrator

    # ----------------- HELP -----------------
    if content == f"{PREFIX}help":
        await message.channel.send(
            "**Commands:**\n"
            "$vouch @user — submit a vouch\n"
            "$vouches — download vouch backup\n"
            "$lock / $unlock — lock channel (admin)\n"
            "$kick / $ban / $unban — moderation (admin)"
        )

    # ----------------- VOUCH -----------------
    elif content.startswith(f"{PREFIX}vouch"):
        if not has_vouch_role:
            await message.channel.send("❌ You are not allowed to vouch.")
            return

        if not message.mentions:
            await message.channel.send("❌ Mention a user to vouch for.")
            return

        target = message.mentions[0]

        questions = [
            "⭐ Rate your experience:",
            "🛒 What did you buy?",
            "✅ Is this user trusted? (yes/no)"
        ]

        answers = []

        def check(m):
            return m.author == message.author and m.channel == message.channel

        try:
            for q in questions:
                await message.channel.send(q)
                msg = await client.wait_for("message", check=check, timeout=120)
                answers.append(msg.content)
        except asyncio.TimeoutError:
            await message.channel.send("⏰ Vouch timed out.")
            return

        vouches.setdefault(guild_id, {})
        vouches[guild_id].setdefault(str(target.id), [])

        vouches[guild_id][str(target.id)].append({
            "by": f"{message.author} ({message.author.id})",
            "rating": answers[0],
            "item": answers[1],
            "trusted": answers[2]
        })

        save_vouches()
        await message.channel.send(f"✅ **Vouch submitted for {target.mention}!**")

    # ----------------- BACKUP -----------------
    elif content == f"{PREFIX}vouches":
        if not is_admin:
            await message.channel.send("❌ Admins only.")
            return

        if guild_id not in vouches:
            await message.channel.send("No vouches yet.")
            return

        file_name = f"vouches_{guild_id}.json"
        with open(file_name, "w") as f:
            json.dump(vouches[guild_id], f, indent=4)

        await message.channel.send(file=discord.File(file_name))
        os.remove(file_name)

    # ----------------- LOCK / UNLOCK -----------------
    elif content == f"{PREFIX}lock":
        if not is_admin:
            return
        overwrite = message.channel.overwrites_for(message.guild.default_role)
        overwrite.send_messages = False
        await message.channel.set_permissions(message.guild.default_role, overwrite=overwrite)
        await message.channel.send("🔒 Channel locked.")

    elif content == f"{PREFIX}unlock":
        if not is_admin:
            return
        overwrite = message.channel.overwrites_for(message.guild.default_role)
        overwrite.send_messages = True
        await message.channel.set_permissions(message.guild.default_role, overwrite=overwrite)
        await message.channel.send("🔓 Channel unlocked.")

    # ----------------- MODERATION -----------------
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

# ----------------- RUN -----------------
if not TOKEN:
    raise RuntimeError("TOKEN environment variable not set")

client.run(TOKEN)
