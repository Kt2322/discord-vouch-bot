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
VOUCH_ROLE_ID = 1473083771963310233
BOT_OWNER_ID = 1320875525409083459
PROTECTED_ROLE_ID = 1473083771963310233
TIMEOUT_DURATION = 7 * 24 * 60 * 60  # 7 days

# GIF LINKS
GIF_SNOW = "https://cdn.discordapp.com/attachments/1472795548917563492/1473875915330027520/image0.gif"
GIF_TOP_RIGHT = "https://cdn.discordapp.com/attachments/1472795548917563492/1473875920711581920/image0.gif"
GIF_BOTTOM_RIGHT = "https://cdn.discordapp.com/attachments/1472795548917563492/1473875905821540444/image0.gif"

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

# ----------------- HELPER FUNCTIONS -----------------
async def fetch_image(url):
    """Fetch image from URL as RGBA"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.read()
            return Image.open(BytesIO(data)).convert("RGBA")

def stars_emoji(rating_str):
    try:
        num = int(rating_str)
        num = max(1, min(5, num))
        return "⭐" * num
    except:
        return rating_str

async def create_vouch_image(vouch):
    # Load GIF frames
    snow_gif = await fetch_image(GIF_SNOW)
    top_gif = await fetch_image(GIF_TOP_RIGHT)
    bottom_gif = await fetch_image(GIF_BOTTOM_RIGHT)
    
    # If snow GIF exists, use frames
    frames = []
    if snow_gif and getattr(snow_gif, "is_animated", False):
        for frame in ImageSequence.Iterator(snow_gif):
            frames.append(frame.convert("RGBA"))
    else:
        frames = [Image.new("RGBA", (500, 220), (30, 30, 50, 255))]

    # Load font
    try:
        font = ImageFont.truetype("bubble.ttf", 28)
    except:
        font = ImageFont.load_default()

    final_frames = []
    for base in frames:
        img = base.copy()
        draw = ImageDraw.Draw(img)

        # Slight transparent overlay for navy/dark theme
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 40))
        img = Image.alpha_composite(img, overlay)

        # Draw card
        draw.rectangle([(0,0),(500,220)], fill=(20,30,60,180))
        draw.rectangle([(0,0),(500,50)], fill=(15,40,80,200))  # header

        # Avatar
        avatar = await fetch_image(vouch.get("avatar_url",""))
        if avatar:
            avatar = avatar.resize((70,70))
            img.paste(avatar, (20,60), avatar)

        # Text
        draw.text((110, 60), f"{vouch['by']}", fill=(255,255,255), font=font)
        draw.text((110, 100), f"⭐ {stars_emoji(vouch['rating'])}", fill=(255,215,0), font=font)
        draw.text((110, 140), f"🛒 {vouch['item']}", fill=(255,255,255), font=font)
        draw.text((110, 180), f"✅ {vouch['trusted']}", fill=(144,238,144), font=font)

        # Top-right GIF
        if top_gif:
            top_frame = top_gif.resize((50,50))
            img.paste(top_frame, (430, 0), top_frame)
        # Bottom-right GIF
        if bottom_gif:
            bottom_frame = bottom_gif.resize((50,50))
            img.paste(bottom_frame, (430, 170), bottom_frame)

        final_frames.append(img)

    buffer = BytesIO()
    final_frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=final_frames[1:],
        loop=0,
        duration=100,
        disposal=2,
        transparency=0
    )
    buffer.seek(0)
    return buffer

async def create_vouch_board_image(vouch_list, per_row=3):
    # Auto scaling board
    card_w, card_h = 500, 220
    rows = (len(vouch_list)+per_row-1)//per_row
    width, height = card_w*per_row, card_h*rows

    snow_gif = await fetch_image(GIF_SNOW)
    top_gif = await fetch_image(GIF_TOP_RIGHT)
    bottom_gif = await fetch_image(GIF_BOTTOM_RIGHT)

    frames = []
    if snow_gif and getattr(snow_gif,"is_animated",False):
        for f in ImageSequence.Iterator(snow_gif):
            frames.append(f.convert("RGBA").resize((width,height)))
    else:
        frames = [Image.new("RGBA",(width,height),(30,30,50,255))]

    try:
        font = ImageFont.truetype("bubble.ttf",24)
    except:
        font = ImageFont.load_default()

    final_frames = []
    for base in frames:
        img = base.copy()
        draw = ImageDraw.Draw(img)
        overlay = Image.new("RGBA", img.size, (0,0,0,40))
        img = Image.alpha_composite(img, overlay)

        for idx, v in enumerate(vouch_list):
            x, y = (idx%per_row)*card_w, (idx//per_row)*card_h
            draw.rectangle([(x,y),(x+card_w,y+card_h-10)], fill=(20,30,60,200))
            draw.rectangle([(x,y),(x+card_w,y+50)], fill=(15,40,80,200))
            
            # Avatar
            avatar = await fetch_image(v.get("avatar_url",""))
            if avatar:
                avatar = avatar.resize((60,60))
                img.paste(avatar,(x+10,y+50),avatar)

            # Text
            draw.text((x+80,y+20), f"{v['by']}", fill=(255,255,255), font=font)
            draw.text((x+80,y+60), f"⭐ {stars_emoji(v['rating'])}", fill=(255,215,0), font=font)
            draw.text((x+80,y+90), f"🛒 {v['item']}", fill=(255,255,255), font=font)
            draw.text((x+80,y+120), f"✅ {v['trusted']}", fill=(144,238,144), font=font)

            # Top-right GIF
            if top_gif:
                top_frame = top_gif.resize((50,50))
                img.paste(top_frame,(x+430,y),top_frame)
            # Bottom-right GIF
            if bottom_gif:
                bottom_frame = bottom_gif.resize((50,50))
                img.paste(bottom_frame,(x+430,y+170),bottom_frame)

        final_frames.append(img)

    buffer = BytesIO()
    final_frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=final_frames[1:],
        loop=0,
        duration=100,
        disposal=2,
        transparency=0
    )
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
            try: await message.delete()
            except: pass
            try:
                await message.author.timeout(datetime.utcnow()+timedelta(seconds=TIMEOUT_DURATION), reason="Unauthorized role ping")
            except: pass
            try:
                await message.channel.send(f"🚫 {message.author.mention} You cannot ping that role.\nTimed out 7 days",delete_after=5)
            except: pass
            return

    content = message.content.strip()
    guild_id = str(message.guild.id)
    user_roles = [r.id for r in message.author.roles]
    has_vouch_role = VOUCH_ROLE_ID in user_roles
    is_admin = message.author.guild_permissions.administrator
    is_owner = message.author.id == BOT_OWNER_ID

    # ----------------- HELP -----------------
    if content==f"{PREFIX}help":
        commands=[]
        if has_vouch_role:
            commands += ["$vouch @user — submit a vouch","$ticket — create a ticket with bot owner","$ping, $userinfo @user, $serverinfo, $avatar @user","$coinflip, $roll, $8ball question, $meme"]
        if is_admin:
            commands += ["$reviews — see all vouches","$ticket @user — create ticket with user","$lock/$unlock — lock channel","$kick/$ban/$unban — moderation"]
        if is_owner:
            commands += ["$close — close your ticket"]
        if not commands:
            commands += ["$ping, $userinfo @user, $serverinfo, $avatar @user","$coinflip, $roll, $8ball question, $meme"]
        await message.channel.send("**Available Commands:**\n"+"\n".join(commands))

    # ----------------- VOUCH -----------------
    elif content.startswith(f"{PREFIX}vouch"):
        if not has_vouch_role:
            await message.channel.send("❌ Not allowed to vouch."); return
        if not message.mentions or message.mentions[0].id!=BOT_OWNER_ID:
            await message.channel.send(f"❌ You can only vouch for <@{BOT_OWNER_ID}>."); return

        target=message.mentions[0]
        questions=["⭐ Rate your experience (1-5):","🛒 What did you buy?","✅ Is this user trusted? (yes/no)"]
        answers=[]
        msgs_to_delete=[]

        def check(m): return m.author==message.author and m.channel==message.channel

        for q in questions:
            embed=discord.Embed(description=q,color=0x1e1e2d)
            sent = await message.channel.send(embed=embed)
            msgs_to_delete.append(sent)
            try:
                msg = await client.wait_for("message", check=check, timeout=120)
                answers.append(msg.content)
                msgs_to_delete.append(msg)
            except asyncio.TimeoutError:
                await message.channel.send("⏰ Vouch timed out. Try again.")
                return

        # Delete all Q&A
        try: await message.channel.delete_messages(msgs_to_delete)
        except: pass

        vouches.setdefault(guild_id,{})
        vouches[guild_id].setdefault(str(target.id),[])
        vouches[guild_id][str(target.id)].append({
            "by": f"{message.author} ({message.author.id})",
            "rating": answers[0],
            "item": answers[1],
            "trusted": answers[2],
            "avatar_url": message.author.avatar.url if message.author.avatar else ""
        })
        save_vouches()

        # Create embed image
        img_buffer = await create_vouch_image(vouches[guild_id][str(target.id)][-1])
        file = discord.File(fp=img_buffer, filename="vouch.gif")
        embed = discord.Embed(title="New Vouch!", color=0x1e1e2d)
        embed.set_image(url="attachment://vouch.gif")
        await message.channel.send(file=file, embed=embed)

    # ----------------- REVIEWS -----------------
    elif content==f"{PREFIX}reviews" and is_admin:
        if guild_id not in vouches or not vouches[guild_id]:
            await message.channel.send("No vouches yet."); return
        vouch_list=[v for uid in vouches[guild_id] for v in vouches[guild_id][uid]]
        img_buffer = await create_vouch_board_image(vouch_list)
        file = discord.File(fp=img_buffer, filename="reviews.gif")
        embed = discord.Embed(title="Vouch Board", color=0x1e1e2d)
        embed.set_image(url="attachment://reviews.gif")
        await message.channel.send(file=file, embed=embed)

    # ----------------- OTHER COMMANDS -----------------
    elif content==f"{PREFIX}ping":
        await message.channel.send(f"🏓 Pong! {round(client.latency*1000)}ms")
    elif content.startswith(f"{PREFIX}userinfo"):
        target = message.mentions[0] if message.mentions else message.author
        roles=", ".join([r.name for r in target.roles if r!=message.guild.default_role])
        await message.channel.send(f"**User Info:**\nName: {target}\nID: {target.id}\nRoles: {roles}\nJoined: {target.joined_at}")
    elif content==f"{PREFIX}serverinfo":
        await message.channel.send(f"**Server Info:**\nName: {message.guild.name}\nID: {message.guild.id}\nMembers: {message.guild.member_count}\nChannels: {len(message.guild.channels)}")
    elif content.startswith(f"{PREFIX}avatar"):
        target = message.mentions[0] if message.mentions else message.author
        await message.channel.send(target.avatar.url)
    elif content==f"{PREFIX}coinflip":
        await message.channel.send(random.choice(["🪙 Heads","🪙 Tails"]))
    elif content==f"{PREFIX}roll":
        await message.channel.send(f"🎲 {random.randint(1,6)}")
    elif content.startswith(f"{PREFIX}8ball"):
        responses = ["It is certain.","Without a doubt.","Yes.","Ask again later.","No.","Very doubtful."]
        await message.channel.send(random.choice(responses))
    elif content==f"{PREFIX}meme":
        memes=["https://i.redd.it/abcd1.jpg","https://i.redd.it/abcd2.jpg","https://i.redd.it/abcd3.jpg"]
        await message.channel.send(random.choice(memes))

# ----------------- RUN -----------------
if not TOKEN:
    raise RuntimeError("TOKEN environment variable not set")
client.run(TOKEN)
