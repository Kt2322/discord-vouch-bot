import discord
import asyncio
import json
import os
import random

# ----------------- CONFIG -----------------
PREFIX = "$"
TOKEN = os.getenv("TOKEN")  # TOKEN MUST BE SET IN ENV VARIABLES
VOUCH_FILE = "vouches.json"
VOUCH_ROLE_ID = 1472071858047422514  # Member role limited to fun + vouch
BOT_OWNER_ID = 1320875525409083459  # Your Discord ID

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
                "$vouch — submit a vouch (essay style)",
                "$ticket — open a private ticket with the bot owner",
                "$ping, $userinfo, $serverinfo, $avatar",
                "$coinflip, $roll, $8ball, $meme"
            ]
        if is_admin:
            commands += [
                "$reviews — view all vouches",
                "$lock/$unlock — lock channel",
                "$kick/$ban/$unban — moderation",
                "$ticket @user — open ticket for someone else"
            ]
        if not commands:
            # regular members without vouch role
            commands += [
                "$ping, $userinfo, $serverinfo, $avatar",
                "$coinflip, $roll, $8ball, $meme"
            ]

        help_text = "**Available Commands:**\n" + "\n".join(commands)
        await message.channel.send(help_text)

    # ----------------- VOUCH -----------------
    elif content.startswith(f"{PREFIX}vouch"):
        if not has_vouch_role:
            await message.channel.send("❌ You are not allowed to vouch.")
            return

        target = message.guild.get_member(BOT_OWNER_ID)
        if not target:
            await message.channel.send("❌ Bot owner not found in this server.")
            return

        essay_template = (
            f"**Vouch Template for {target.mention}**\n"
            "Please answer below in one message in this format:\n\n"
            "1️⃣ Experience Rating:\n"
            "2️⃣ Item Bought:\n"
            "3️⃣ Is this user trusted (yes/no):"
        )
        await message.channel.send(essay_template)

        def check(m):
            return m.author == message.author and m.channel == message.channel

        try:
            reply = await client.wait_for("message", check=check, timeout=300)
        except asyncio.TimeoutError:
            await message.channel.send("⏰ Vouch timed out. Please try again.")
            return

        # Parse answers
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
        vouches.setdefault(str(guild_id), {})
        vouches[str(guild_id)].setdefault(str(BOT_OWNER_ID), [])
        vouches[str(guild_id)][str(BOT_OWNER_ID)].append({
            "by": f"{message.author} ({message.author.id})",
            "rating": answers["rating"],
            "item": answers["item"],
            "trusted": answers["trusted"]
        })
        save_vouches()

        embed = discord.Embed(title=f"Vouch Recorded by {message.author}", color=discord.Color.green())
        embed.add_field(name="Vouched User", value=target.mention, inline=False)
        embed.add_field(name="Experience Rating", value=answers["rating"] or "Not provided", inline=False)
        embed.add_field(name="Item Bought", value=answers["item"] or "Not provided", inline=False)
        embed.add_field(name="Trusted?", value=answers["trusted"] or "Not provided", inline=False)
        await message.channel.send(embed=embed)

    # ----------------- REVIEWS -----------------
    elif content == f"{PREFIX}reviews" and is_admin:
        if str(guild_id) not in vouches or not vouches[str(guild_id)]:
            await message.channel.send("No vouches recorded yet.")
            return

        review_lines = []
        for user_id, user_vouches in vouches[str(guild_id)].items():
            for v in user_vouches:
                review_lines.append(
                    f"Vouched by {v['by']}\n"
                    f"Experience: {v['rating'] or 'Not provided'}\n"
                    f"Item: {v['item'] or 'Not provided'}\n"
                    f"Trusted: {v['trusted'] or 'Not provided'}\n"
                    "---------------------"
                )

        chunk_size = 1900
        msg = ""
        for line in review_lines:
            if len(msg) + len(line) + 1 > chunk_size:
                await message.channel.send(f"```{msg}```")
                msg = line + "\n"
            else:
                msg += line + "\n"
        if msg:
            await message.channel.send(f"```{msg}```")

    # ----------------- TICKET -----------------
    elif content.startswith(f"{PREFIX}ticket"):
        if has_vouch_role and content.strip() == f"{PREFIX}ticket":
            # member opens ticket with owner
            overwrites = {
                message.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                message.author: discord.PermissionOverwrite(read_messages=True),
                message.guild.get_member(BOT_OWNER_ID): discord.PermissionOverwrite(read_messages=True)
            }
            thread_name = f"ticket-{message.author.name}"
            category = message.channel.category
            ticket_channel = await message.guild.create_text_channel(thread_name, overwrites=overwrites, category=category)
            await ticket_channel.send(f"Ticket opened for {message.author.mention}")
        elif is_admin and message.mentions:
            target_user = message.mentions[0]
            overwrites = {
                message.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                target_user: discord.PermissionOverwrite(read_messages=True),
                message.author: discord.PermissionOverwrite(read_messages=True)
            }
            thread_name = f"ticket-{target_user.name}"
            category = message.channel.category
            ticket_channel = await message.guild.create_text_channel(thread_name, overwrites=overwrites, category=category)
            await ticket_channel.send(f"Ticket opened by {message.author.mention} for {target_user.mention}")

    # ----------------- LOCK / UNLOCK -----------------
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
                await message.channel.send("✅ User unbanned")
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
