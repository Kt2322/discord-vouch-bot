import discord
import asyncio
import json
import os
import random
import aiohttp
from io import BytesIO
from datetime import timedelta, datetime
from PIL import Image, ImageDraw, ImageFont, ImageSequence

# ---------------- CONFIG ----------------
PREFIX = "$"
TOKEN = os.getenv("TOKEN")
VOUCH_FILE = "vouches.json"

VOUCH_ROLE_ID = 1473083771963310233
BOT_OWNER_ID = 1320875525409083459
PROTECTED_ROLE_ID = 1473083771963310233
TIMEOUT_DURATION = 7 * 24 * 60 * 60

# GIF LINKS
SNOW_GIF = "https://cdn.discordapp.com/attachments/1472795548917563492/1473875915330027520/image0.gif"
TOP_RIGHT_GIF = "https://cdn.discordapp.com/attachments/1472795548917563492/1473875920711581920/image0.gif"
BOTTOM_RIGHT_GIF = "https://cdn.discordapp.com/attachments/1472795548917563492/1473875905821540444/image0.gif"

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# ---------------- STORAGE ----------------
if os.path.exists(VOUCH_FILE):
    with open(VOUCH_FILE, "r") as f:
        vouches = json.load(f)
else:
    vouches = {}

def save_vouches():
    with open(VOUCH_FILE, "w") as f:
        json.dump(vouches, f, indent=4)

# ---------------- HELPERS ----------------
async def fetch_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()
            return Image.open(BytesIO(data))

def stars_text(rating):
    try:
        r = max(1, min(5, int(rating)))
        return "⭐" * r
    except:
        return "⭐⭐⭐⭐⭐"

async def create_animated_vouch(vouch):
    snow = await fetch_image(SNOW_GIF)
    top = await fetch_image(TOP_RIGHT_GIF)
    bottom = await fetch_image(BOTTOM_RIGHT_GIF)

    frames = []
    width, height = 600, 300

    try:
        font_big = ImageFont.truetype("bubble.ttf", 36)
        font_small = ImageFont.truetype("bubble.ttf", 28)
    except:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    snow_frames = [frame.convert("RGBA").resize((width, height)) for frame in ImageSequence.Iterator(snow)]
    top_frames = [frame.convert("RGBA").resize((120, 120)) for frame in ImageSequence.Iterator(top)]
    bottom_frames = [frame.convert("RGBA").resize((100, 100)) for frame in ImageSequence.Iterator(bottom)]

    max_frames = max(len(snow_frames), len(top_frames), len(bottom_frames))

    for i in range(max_frames):
        base = snow_frames[i % len(snow_frames)].copy()

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 120))
        base = Image.alpha_composite(base, overlay)

        draw = ImageDraw.Draw(base)

        draw.text((30, 40), vouch["by"], font=font_big, fill=(0, 200, 255))
        draw.text((30, 110), stars_text(vouch["rating"]), font=font_big, fill=(255, 255, 0))
        draw.text((30, 170), f"Item: {vouch['item']}", font=font_small, fill=(255, 255, 255))
        draw.text((30, 210), f"Trusted: {vouch['trusted']}", font=font_small, fill=(200, 255, 200))

        base.paste(top_frames[i % len(top_frames)], (width - 130, 10), top_frames[i % len(top_frames)])
        base.paste(bottom_frames[i % len(bottom_frames)], (width - 110, height - 110), bottom_frames[i % len(bottom_frames)])

        frames.append(base)

    buffer = BytesIO()
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0,
        disposal=2
    )
    buffer.seek(0)
    return buffer

# ---------------- EVENTS ----------------
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    content = message.content.strip()
    guild_id = str(message.guild.id)

    user_roles = [role.id for role in message.author.roles]
    has_vouch_role = VOUCH_ROLE_ID in user_roles
    is_admin = message.author.guild_permissions.administrator
    is_owner = message.author.id == BOT_OWNER_ID

    # -------- ANTI ROLE PING --------
    if f"<@&{PROTECTED_ROLE_ID}>" in content and not is_admin:
        await message.delete()
        await message.author.timeout(
            datetime.utcnow() + timedelta(seconds=TIMEOUT_DURATION),
            reason="Unauthorized protected role ping"
        )
        await message.channel.send(
            f"{message.author.mention} You cannot ping that role. Timed out 7 days.",
            delete_after=5
        )
        return

    # -------- HELP --------
    if content == f"{PREFIX}help":
        cmds = ["$vouch @owner"]
        if has_vouch_role:
            cmds += ["$ping", "$coinflip", "$roll", "$8ball", "$meme", "$userinfo", "$serverinfo", "$avatar"]
        if is_admin:
            cmds += ["$reviews", "$kick", "$ban", "$unban", "$lock", "$unlock"]
        await message.channel.send("Available Commands:\n" + "\n".join(cmds))
        return

    # -------- VOUCH --------
    if content.startswith(f"{PREFIX}vouch"):
        if not message.mentions or message.mentions[0].id != BOT_OWNER_ID:
            await message.channel.send("You can only vouch the bot owner.")
            return

        questions = [
            "Rate 1-5:",
            "What did you buy?",
            "Is this user trusted? (yes/no)"
        ]

        prompts = []
        answers = []

        def check(m):
            return m.author == message.author and m.channel == message.channel

        for q in questions:
            msg = await message.channel.send(q)
            prompts.append(msg)
            reply = await client.wait_for("message", check=check)
            answers.append(reply)
        
        for m in prompts + answers:
            try:
                await m.delete()
            except:
                pass

        vouches.setdefault(guild_id, [])
        new_vouch = {
            "by": str(message.author),
            "rating": answers[0].content,
            "item": answers[1].content,
            "trusted": answers[2].content
        }

        vouches[guild_id].append(new_vouch)
        save_vouches()

        gif = await create_animated_vouch(new_vouch)
        file = discord.File(gif, filename="vouch.gif")
        embed = discord.Embed(title="New Vouch", color=0x000080)
        embed.set_image(url="attachment://vouch.gif")
        await message.channel.send(file=file, embed=embed)
        return

    # -------- REVIEWS --------
    if content == f"{PREFIX}reviews" and is_admin:
        if guild_id not in vouches or not vouches[guild_id]:
            await message.channel.send("No vouches yet.")
            return

        for v in vouches[guild_id]:
            gif = await create_animated_vouch(v)
            file = discord.File(gif, filename="review.gif")
            embed = discord.Embed(title="Vouch Review", color=0x000080)
            embed.set_image(url="attachment://review.gif")
            await message.channel.send(file=file, embed=embed)
        return

    # -------- FUN / UTILITY --------
    if has_vouch_role:
        if content == f"{PREFIX}ping":
            await message.channel.send(f"Pong! {round(client.latency*1000)}ms")
        elif content == f"{PREFIX}coinflip":
            await message.channel.send(random.choice(["Heads", "Tails"]))
        elif content == f"{PREFIX}roll":
            await message.channel.send(str(random.randint(1,6)))
        elif content.startswith(f"{PREFIX}8ball"):
            await message.channel.send(random.choice(["Yes", "No", "Maybe"]))
        elif content == f"{PREFIX}meme":
            await message.channel.send("https://i.imgur.com/abcd.jpg")
        elif content.startswith(f"{PREFIX}userinfo"):
            target = message.mentions[0] if message.mentions else message.author
            await message.channel.send(f"{target} | ID: {target.id}")
        elif content == f"{PREFIX}serverinfo":
            await message.channel.send(f"{message.guild.name} | Members: {message.guild.member_count}")
        elif content.startswith(f"{PREFIX}avatar"):
            target = message.mentions[0] if message.mentions else message.author
            await message.channel.send(target.avatar.url)
        return

    # -------- MOD --------
    if is_admin:
        if content.startswith(f"{PREFIX}kick"):
            await message.mentions[0].kick()
        elif content.startswith(f"{PREFIX}ban"):
            await message.mentions[0].ban()
        elif content.startswith(f"{PREFIX}unban"):
            pass
        elif content == f"{PREFIX}lock":
            await message.channel.set_permissions(message.guild.default_role, send_messages=False)
        elif content == f"{PREFIX}unlock":
            await message.channel.set_permissions(message.guild.default_role, send_messages=True)
        return

if not TOKEN:
    raise RuntimeError("TOKEN not set")

client.run(TOKEN)