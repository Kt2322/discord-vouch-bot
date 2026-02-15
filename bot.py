import discord
import asyncio
import json
import os
import random

# ----------------- CONFIG -----------------
PREFIX = "$"
TOKEN = os.getenv("TOKEN")  # TOKEN MUST BE SET IN ENV VARIABLES
VOUCH_ROLE_ID = 1472071858047422514  # Member role limited to fun + vouch

# ----------------- INTENTS -----------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

client = discord.Client(intents=intents)

# ----------------- LOAD VOUCHES -----------------
vouches = {}

def save_vouches():
    with open("vouches.json", "w") as f:
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
                "$vouch @user — submit a vouch (essay style)",
                "$ping, $userinfo @user, $serverinfo, $avatar @user",
                "$coinflip, $roll, $8ball question, $meme"
            ]
        if is_admin:
            commands += [
                "$vouches — show all vouches",
                "$lock/$unlock — lock channel",
                "$kick/$ban/$unban — moderation"
            ]
        if not commands:
            # regular members without vouch role
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

        # Parse user answers
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

    # ----------------- SHOW VOUCHES -----------------
    elif content == f"{PREFIX}vouches" and is_admin:
        if guild_id not in vouches or not vouches[guild_id]:
            await message.channel.send("No vouches recorded yet in this server.")
            return

        embed = discord.Embed(
            title=f"All Vouches in {message.guild.name}",
            color=discord.Color.blue()
        )

        for user_id, vouch_list in vouches[guild_id].items():
            user = message.guild.get_member(int(user_id))
            user_name = user.display_name if user else f"User ID {user_id}"
            vouch_texts = []
            for v in vouch_list:
                vouch_texts.append(
                    f"**By:** {v['by']}\n⭐ {v['rating']}\n🛒 {v['item']}\n✅ {v['trusted']}"
                )
            embed.add_field(
                name=user_name,
                value="\n\n".join(vouch_texts[:3]),
                inline=False
            )

        await message.channel.send(embed=embed)

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
