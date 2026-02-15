import discord
from discord import app_commands
import asyncio
import json
import os
import random
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# ----------------- CONFIG -----------------
TOKEN = os.getenv("TOKEN")
VOUCH_FILE = "vouches.json"
VOUCH_ROLE_ID = 1472071858047422514
BOT_OWNER_ID = 1320875525409083459

# ----------------- INTENTS -----------------
intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ----------------- LOAD VOUCHES -----------------
if os.path.exists(VOUCH_FILE):
    with open(VOUCH_FILE, "r") as f:
        vouches = json.load(f)
else:
    vouches = {}

def save_vouches():
    with open(VOUCH_FILE, "w") as f:
        json.dump(vouches, f, indent=4)

# ----------------- IMAGE HELPERS -----------------
async def fetch_avatar(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            return Image.open(BytesIO(await r.read())).convert("RGBA")

async def create_vouch_image(vouch):
    img = Image.new("RGB", (500, 220), (40, 42, 54))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
    except:
        font = ImageFont.load_default()

    draw.rectangle((0, 0, 500, 40), fill=(95, 158, 160))
    draw.text((15, 10), "VOUCH RECEIPT", fill="white", font=font)

    avatar = await fetch_avatar(vouch["avatar_url"])
    avatar = avatar.resize((64, 64))
    img.paste(avatar, (15, 60))

    draw.text((100, 60), f"By: {vouch['by']}", fill="white", font=font)
    draw.text((100, 95), f"⭐ Rating: {vouch['rating']}", fill="gold", font=font)
    draw.text((100, 125), f"🛒 Item: {vouch['item']}", fill="lightblue", font=font)
    draw.text((100, 155), f"✅ Trusted: {vouch['trusted']}", fill="lightgreen", font=font)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ----------------- READY -----------------
@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {client.user}")

# ----------------- /VOUCH -----------------
@tree.command(name="vouch", description="Leave a vouch (members only)")
@app_commands.describe(user="User to vouch for")
async def vouch(interaction: discord.Interaction, user: discord.User):
    if user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ You can only vouch for the owner.", ephemeral=True)
        return

    role_ids = [r.id for r in interaction.user.roles]
    if VOUCH_ROLE_ID not in role_ids:
        await interaction.response.send_message("❌ You cannot vouch.", ephemeral=True)
        return

    await interaction.response.send_message("⭐ Check your DMs to complete the vouch.", ephemeral=True)

    dm = await interaction.user.create_dm()
    answers = []

    questions = [
        "⭐ Rate your experience (1–5):",
        "🛒 What did you buy?",
        "✅ Is this user trusted? (yes/no)"
    ]

    def check(m): return m.author == interaction.user and m.channel == dm

    for q in questions:
        await dm.send(q)
        msg = await client.wait_for("message", check=check)
        answers.append(msg.content)

    guild_id = str(interaction.guild.id)
    vouches.setdefault(guild_id, {})
    vouches[guild_id].setdefault(str(user.id), [])

    data = {
        "by": str(interaction.user),
        "rating": answers[0],
        "item": answers[1],
        "trusted": answers[2],
        "avatar_url": interaction.user.avatar.url
    }

    vouches[guild_id][str(user.id)].append(data)
    save_vouches()

    img = await create_vouch_image(data)
    await interaction.followup.send(file=discord.File(img, "vouch.png"))

# ----------------- /REVIEWS -----------------
@tree.command(name="reviews", description="View all vouches")
async def reviews(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Admins only.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    all_vouches = [v for u in vouches.get(guild_id, {}) for v in vouches[guild_id][u]]

    if not all_vouches:
        await interaction.response.send_message("No reviews yet.", ephemeral=True)
        return

    images = [await create_vouch_image(v) for v in all_vouches]
    await interaction.response.send_message(files=[discord.File(i, f"review{i}.png") for i in images])

# ----------------- /TICKET -----------------
@tree.command(name="ticket", description="Open a private ticket")
@app_commands.describe(user="User (admin only)")
async def ticket(interaction: discord.Interaction, user: discord.User = None):
    guild = interaction.guild

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True),
        guild.get_member(BOT_OWNER_ID): discord.PermissionOverwrite(read_messages=True)
    }

    channel = await guild.create_text_channel(
        f"ticket-{interaction.user.name}",
        overwrites=overwrites
    )

    await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

# ----------------- /CLOSE -----------------
@tree.command(name="close", description="Close this ticket")
async def close(interaction: discord.Interaction):
    if interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌ Owner only.", ephemeral=True)
        return
    await interaction.channel.delete()

# ----------------- FUN COMMANDS -----------------
@tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 {round(client.latency*1000)}ms")

@tree.command(name="coinflip")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice(["🪙 Heads", "🪙 Tails"]))

@tree.command(name="roll")
async def roll(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎲 {random.randint(1,6)}")

@tree.command(name="meme")
async def meme(interaction: discord.Interaction):
    memes = [
        "https://i.redd.it/abcd1.jpg",
        "https://i.redd.it/abcd2.jpg",
        "https://i.redd.it/abcd3.jpg"
    ]
    await interaction.response.send_message(random.choice(memes))

# ----------------- RUN -----------------
if not TOKEN:
    raise RuntimeError("TOKEN not set")

client.run(TOKEN)
