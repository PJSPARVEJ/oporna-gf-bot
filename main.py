import discord
from groq import Groq
from discord.ext import commands
from gtts import gTTS
import sqlite3
import json
import os
import yt_dlp as youtube_dl
import asyncio
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- কনফিগারেশন ---
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY') # .env তে যোগ করুন

OWNER_IDS = [906758055167950869, 1028589017861718076, 729726728523743343] 
ALLOWED_CHANNEL_ID = 1477737431100035344, 1478325241670275153
CHANNEL_ID = ['YOUR_YOUTUBE_CHANNEL_ID'] # তোমার ইউটিউব চ্যানেলের আইডি
DISCORD_CHANNEL_ID = [1474106188843974659]  # যে ডিসকর্ড চ্যানেলে লিঙ্ক যাবে তার আইডি
# গালি এবং হার্ড মোড লিস্ট
BANNED_WORDS = ['khisti', 'khanki', 'magi', 'sala', 'saala', 'gasti', 'bal', 'baal', 'chod', 'choda', 
    'gaali', 'harami', 'bokachoda', 'madarchod', 'bejonma', 'suorer', 'kuttr', 'cudbo', '12vatari',
    'কুত্তা', 'শুয়োর', 'হারামি', 'বাল', 'খানকি', 'মাগি', 'শালা', 'চোদ', 'বোকাসোদা', 'খানকি', '১২ ভাতারি মাগি', 'চুদব',
    'sex', 'sexy', 'chuda', 'nude', 'hot', 'pussy', 'dick', 'bitch', 'slvt'
]

# YTDL Configuration
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

client = Groq(api_key=GROQ_API_KEY)
user_spam_counter = {}

# --- ডাটাবেস ফাংশন ---
def init_db():
    conn = sqlite3.connect('chat_memory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS memory (user_id TEXT PRIMARY KEY, history TEXT, last_update REAL)''')
    conn.commit()
    conn.close()

def get_memory(user_id):
    try:
        conn = sqlite3.connect('chat_memory.db')
        c = conn.cursor()
        c.execute("SELECT history, last_update FROM memory WHERE user_id=?", (str(user_id),))
        row = c.fetchone()
        conn.close()
        if row and (time.time() - row[1] < 1800):
            return json.loads(row[0])
        return []
    except: return []

def save_memory(user_id, history):
    conn = sqlite3.connect('chat_memory.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO memory VALUES (?, ?, ?)", (str(user_id), json.dumps(history[-15:]), time.time()))
    conn.commit()
    conn.close()

init_db()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True 
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# --- পার্সোনালিটি প্রম্পট ---
OWNER_PROMPT = {
    "role": "system", 
    "content": "Your name is Orpona. You are a Bengali girl and the user's GIRLFRIEND. Rule 1: ALWAYS speak in Banglish. Rule 2: Be very romantic, call him 'Jan' or 'Babu'. Rule 3: Keep replies short. Use emojis ❤️, 😊."
}
OTHERS_PROMPT = {
    "role": "system", 
    "content": "Your name is Orpona. You are a friendly Bengali girl. Rule 1: ALWAYS speak in Banglish. Rule 2: Be polite and friendly, NOT romantic. Rule 3: Talk like a normal friend."
}

# FFmpeg Global Options
FFMPEG_OPTIONS = {
    'options': '-vn'
}

# --- ১. বাংলা ভয়েস ওয়েলকাম (Final Stable Version) ---

# --- ২. হার্ড সিকিউরিটি ---
@bot.event
async def on_message(message):
    if message.author == bot.user: return

    # Anti-Link
    if ("http" in message.content.lower() or "www." in message.content.lower()) and message.author.id not in OWNER_IDS:
        await message.delete()
        return await message.channel.send(f"🚫 {message.author.mention}, Security Hard Mode এ লিঙ্ক নিষেধ!", delete_after=5)

    # Anti-Spam
    u_id = message.author.id
    now = time.time()
    user_spam_counter[u_id] = [t for t in user_spam_counter.get(u_id, []) if now - t < 5]
    user_spam_counter[u_id].append(now)
    if len(user_spam_counter[u_id]) > 3:
        try:
            await message.author.timeout(timedelta(minutes=5), reason="Spamming")
            await message.channel.send(f"⚠️ {message.author.mention} কে স্প্যামিং এর জন্য ৫ মিনিট মিউট করা হয়েছে।")
            return
        except: pass

    # গালি ফিল্টার
    if any(word in message.content.lower() for word in BANNED_WORDS):
        try:
            await message.delete()
            await message.author.timeout(timedelta(minutes=5), reason="Bad language")
            await message.channel.send(f"🚫 {message.author.mention}, গালি দেওয়ার জন্য তুমি **৫ মিনিট** মিউট!", delete_after=10)
            return
        except: pass
# --- ইউটিউব ডাটা ফেচ ফাংশন --


        
    # --- ৩. AI চ্যাট লজিক ---
    is_allowed_channel = message.channel.id in ALLOWED_CHANNEL_ID  # ID do seu canal
    is_dm = isinstance(message.channel, discord.DMChannel)
    if is_allowed_channel or is_dm:
        user_input = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        
        if user_input or not is_dm:
            if not user_input:
                user_input = "Hi"

            history = get_memory(message.author.id)
            
            if message.author.id in OWNER_IDS:
                selected_prompt = OWNER_PROMPT
                temp = 0.9
            else:
                selected_prompt = OTHERS_PROMPT
                temp = 0.7

            messages = [selected_prompt] + history + [{"role": "user", "content": user_input}]

            async with message.channel.typing():
                try:
                    completion = client.chat.completions.create(
                        model="llama-3.3-70b-versatile", 
                        messages=messages,
                        temperature=temp,
                        max_tokens=500,
                    )

                    response_text = completion.choices[0].message.content
                    
                    history.append({"role": "user", "content": user_input})
                    history.append({"role": "assistant", "content": response_text})
                    save_memory(message.author.id, history)
                    
                    await message.reply(response_text)
                except Exception as e:
                    print(f"AI Error: {e}")
                    err_msg = "জান, একটু সমস্যা হচ্ছে।" if message.author.id in OWNER_IDS else "একটু টেকনিক্যাল সমস্যা হচ্ছে।"
                    await message.reply(err_msg)

    await bot.process_commands(message)


# --- ৪. কমান্ডস ---
@bot.command()
async def imagine(ctx, *, prompt: str):
    if ctx.author.id not in OWNER_IDS:
        return await ctx.reply("সরি বাবু, এটা শুধু মালিকের জন্য! 🌸")
    img_url = f"https://pollinations.ai/p/{prompt.replace(' ', '%20')}?width=1024&height=1024"
    embed = discord.Embed(title=f"🎨 {prompt}", color=0xff69b4)
    embed.set_image(url=img_url)
    await ctx.send(embed=embed)
    # --- ৩. অন রেডি ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name='my love RedOx/Hxb/Rabbi ❤️'))

@bot.command(name='play', help='Plays a song from YouTube')
async def play(ctx, *, search: str):
    if not ctx.voice_client:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
        else:
            await ctx.send("আগে একটা ভয়েস চ্যানেলে জয়েন করো বাবু! 🌸")
            return

    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
            
            if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                ctx.voice_client.stop()
                await asyncio.sleep(1) # FFmpeg-ke terminate hote ১ সেকেন্ড সময় দিন

            # Space/Indentation gulo niche thik kora holo
            ctx.voice_client.play(
                player, 
                after=lambda *args: print(f'Player error: {args[0]}') if args and args[0] else None
            )

            await ctx.send(f'🎶 এখন বাজছে: **{player.title}**')

        except Exception as e:
            print(f"Play Error: {e}")
            await ctx.send(f"গানটা প্লে করতে পারলাম না। Error: {e}")
        
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🌸 অর্পণা বট মেনু", description="Security: **HARD MODE ✅**", color=0xff69b4)
    embed.add_field(name="🎙️ Voice Welcome", value="ভয়েস চ্যানেলে জয়েন করলে আমি বাংলায় কথা বলবো।", inline=False)
    embed.add_field(name="🛡️ Hard Security", value="Anti-Link, Anti-Spam, 5m Mute active.", inline=False)
    embed.add_field(name="🎨 Image", value="`!imagine [prompt]` (Owner Only)", inline=True)
    embed.add_field(name="🎵 Music", value="`!play`, `!stop` (FFmpeg needed)", inline=True)
    embed.set_footer(text="Developed for RedOx/Hxb")
    await ctx.send(embed=embed)

bot.run(DISCORD_TOKEN)
