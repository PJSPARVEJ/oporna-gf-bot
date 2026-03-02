import discord
from groq import Groq
from discord.ext import commands
from gtts import gTTS
import sqlite3
import json
import os
import asyncio
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- কনফিগারেশন ---
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

OWNER_IDS = [906758055167950869, 1028589017861718076] 
ALLOWED_CHANNEL_ID = 1477737431100035344 

# গালি এবং হার্ড মোড লিস্ট
BANNED_WORDS = ['khisti', 'khanki', 'magi', 'sala', 'saala', 'gasti', 'bal', 'baal', 'chod', 'choda', 
    'gaali', 'harami', 'bokachoda', 'madarchod', 'bejonma', 'suorer', 'kuttr', 'cudbo', '12vatari',
    
    # কমন গালি (Bengali Script)
    'কুত্তা', 'শুয়োর', 'হারামি', 'বাল', 'খানকি', 'মাগি', 'শালা', 'চোদ', 'বোকাসোদা', 'খানকি', '১২ ভাতারি মাগি', 'চুদব',
    
    # ১৮+ বা অশালীন শব্দ
    'sex', 'sexy', 'chuda', 'nude', 'hot', 'pussy', 'dick', 'bitch', 'slvt'
]


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

# --- ১. বাংলা ভয়েস ওয়েলকাম (FFmpeg Required) ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id or (before.channel == after.channel):
        return

    if after.channel is not None:
        try:
            # আগের কোনো কানেকশন থাকলে ডিসকানেক্ট করা
            existing_vc = discord.utils.get(bot.voice_clients, guild=member.guild)
            if existing_vc: await existing_vc.disconnect()

            vc = await after.channel.connect()

            if member.id in OWNER_IDS:
                txt = f"স্বাগতম বাবু! জান, তুমি কেমন আছো?"
            else:
                txt = f"হ্যালো {member.display_name}, আমাদের ভয়েস চ্যানেলে স্বাগতম।"

            tts = gTTS(text=txt, lang='bn')
            filename = f"welcome_{member.id}.mp3"
            tts.save(filename)

            # FFmpeg দিয়ে প্লে করা
            vc.play(discord.FFmpegPCMAudio(filename))

            while vc.is_playing():
                await asyncio.sleep(1)
            
            await vc.disconnect()
            if os.path.exists(filename): os.remove(filename)
        except Exception as e:
            print(f"Voice Error: {e}")

# --- ২. হার্ড সিকিউরিটি (Anti-Link, Anti-Spam, Mute) ---
@bot.event
async def on_message(message):
    if message.author == bot.user: return

    # Anti-Link
    if ("http" in message.content.lower() or "www." in message.content.lower()) and message.author.id not in OWNER_IDS:
        await message.delete()
        return await message.channel.send(f"🚫 {message.author.mention}, Security Hard Mode এ লিঙ্ক নিষেধ!", delete_after=5)

    # Anti-Spam (5s এ ৩টি মেসেজ)
    u_id = message.author.id
    now = time.time()
    user_spam_counter[u_id] = [t for t in user_spam_counter.get(u_id, []) if now - t < 5]
    user_spam_counter[u_id].append(now)
    if len(user_spam_counter[u_id]) > 3:
        try:
            await message.author.timeout(timedelta(minutes=5), reason="Spamming")
            await message.channel.send(f"⚠️ {message.author.mention} কে স্প্যামিং এর জন্য ৫ মিনিট মিউট করা হয়েছে।")
            return
        except: pass

    # গালি ফিল্টার (৫ মিনিট মিউট)
    if any(word in message.content.lower() for word in BANNED_WORDS):
        try:
            await message.delete()
            await message.author.timeout(timedelta(minutes=5), reason="Bad language")
            await message.channel.send(f"🚫 {message.author.mention}, গালি দেওয়ার জন্য তুমি **৫ মিনিট** মিউট!", delete_after=10)
            return
        except: pass

    # --- ৩. AI চ্যাট লজিক ---
    if (message.channel.id == ALLOWED_CHANNEL_ID or isinstance(message.channel, discord.DMChannel)) and not message.content.startswith('!'):
        history = get_memory(message.author.id)
        prompt = {"role": "system", "content": "Your name is Orpona. Use Banglish. Romantic with owners, friendly with others."}
        
        async with message.channel.typing():
            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[prompt] + history + [{"role": "user", "content": message.content}]
                )
                res = completion.choices[0].message.content
                history.append({"role": "user", "content": message.content})
                history.append({"role": "assistant", "content": res})
                save_memory(message.author.id, history)
                await message.reply(res)
            except: pass

    await bot.process_commands(message)

# --- ৪. ইমেজ এবং অন্যান্য কমান্ডস ---
@bot.command()
async def imagine(ctx, *, prompt: str):
    if ctx.author.id not in OWNER_IDS:
        return await ctx.reply("সরি বাবু, এটা শুধু মালিকের জন্য! 🌸")
    img_url = f"https://pollinations.ai/p/{prompt.replace(' ', '%20')}?width=1024&height=1024"
    embed = discord.Embed(title=f"🎨 {prompt}", color=0xff69b4)
    embed.set_image(url=img_url)
    await ctx.send(embed=embed)

@bot.command()
async def play(ctx, *, search: str):
    if not ctx.author.voice: return await ctx.send("আগে ভয়েস চ্যানেলে ঢুকো জান! ❤️")
    await ctx.send(f"🎵 **{search}** গানটি খোঁজা হচ্ছে... (FFmpeg active)")

@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🌸 অর্পণা বট মেনু", description="Security: **HARD MODE ✅**", color=0xff69b4)
    embed.add_field(name="🎙️ Voice Welcome", value="ভয়েস চ্যানেলে জয়েন করলে আমি বাংলায় কথা বলবো।", inline=False)
    embed.add_field(name="🛡️ Hard Security", value="Anti-Link, Anti-Spam, 5m Mute active.", inline=False)
    embed.add_field(name="🎨 Image", value="`!imagine [prompt]` (Owner Only)", inline=True)
    embed.add_field(name="🎵 Music", value="`!play`, `!stop` (FFmpeg needed)", inline=True)
    embed.set_footer(text="Developed for RedOx/Hxb")
    await ctx.send(embed=embed)

bot.run(DISCORD_TOKEN)
