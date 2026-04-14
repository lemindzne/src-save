import os
import json
import random
import re
import asyncio
import discord
import sqlite3 # Thêm thư viện database
from discord.ext import commands
from discord import app_commands
from groq import Groq
from dotenv import load_dotenv
from collections import defaultdict, deque

# =====================
# LOAD CONFIG
# =====================
load_dotenv() 
TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY") # Đảm bảo biến này khớp với .env
DB_PATH = os.getenv("DB_PATH", "mahiru.db") # Đường dẫn lưu file database

client = Groq(api_key=GROQ_KEY)

# ID user đặc biệt
SPECIAL_USER_ID = 695215402187489350
lover_nickname = "anh"

# =====================
# SQLITE SETUP (Hệ thống ghi nhớ)
# =====================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS affinity 
                 (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

def get_affinity(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT points FROM affinity WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

def add_affinity(user_id, amount=1):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO affinity (user_id, points) VALUES (?, 0)", (user_id,))
    c.execute("UPDATE affinity SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# Khởi tạo database ngay khi chạy bot
init_db()

# =====================
# BOT SETUP
# =====================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

server_channels = {}
processing_lock = asyncio.Lock()
conversation_history = defaultdict(lambda: deque(maxlen=6))

# =====================
# AI FUNCTIONS (Giữ nguyên của bạn)
# =====================
async def get_ai_response(system_prompt, user_message):
    try:
        chat_completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=1.0,
            presence_penalty=0.4,  
            frequency_penalty=0.6,
            top_p=0.9,
            max_tokens=150
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Lỗi Groq API: {e}")
        return None

def split_sentences(text: str):
    if text is None: return []
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]

def limit_exact_sentences(text: str, is_special_user: bool = False):
    sentences = split_sentences(text)
    target_count = random.choice([4, 6]) if is_special_user else random.choice([2, 3])
    return " ".join(sentences[:target_count]) if len(sentences) >= target_count else " ".join(sentences)

# =====================
# ON MESSAGE (Logic chính)
# =====================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return

    if bot.user in message.mentions:
        user_id = message.author.id
        
        # 1. Quản lý kênh chat (Giữ logic cũ của bạn)
        target_channel_id = server_channels.get(message.guild.id)
        if target_channel_id and message.channel.id != target_channel_id:
            return

        # 2. Xử lý độ thân mật
        add_affinity(user_id, 1) # Mỗi lần tag bot là +1 điểm
        points = get_affinity(user_id)

        user_message = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if not user_message: user_message = "Em ơi!"

        history = conversation_history[user_id]
        history_text = "\n".join([f"{'Anh' if h['role']=='user' else 'Em'}: {h['content']}" for h in history])

        # 3. Thiết lập Prompt dựa trên độ thân mật
        if user_id == SPECIAL_USER_ID:
            is_special = True
            system_prompt = (
                f"Bạn là Mahiru, người yêu nũng nịu của {lover_nickname}. "
                f"Gọi người yêu là {lover_nickname}. Dùng kaomoji đáng yêu. "
                f"Lịch sử:\n{history_text}"
            )
        else:
            is_special = False
            # Phân bậc cảm xúc cho người thường
            if points < 30:
                feeling = "Bạn là Mahiru lạnh lùng, chỉ coi họ là bạn học xa lạ. Trả lời cực kỳ ngắn gọn, không cảm xúc."
            elif points < 150:
                feeling = "Bạn bắt đầu quen với người bạn học này, lịch sự hơn nhưng vẫn giữ khoảng cách."
            else:
                feeling = "Bạn coi người này là bạn rất thân. Dịu dàng hơn và bắt đầu dùng vài kaomoji (｡•‿•｡)."

            system_prompt = (
                f"{feeling} "
                f"QUY TẮC: Không dùng emoji vàng. "
                f"Lịch sử hội thoại:\n{history_text}"
            )

        async with processing_lock:
            ai_reply = await get_ai_response(system_prompt, user_message)
            if ai_reply:
                ai_reply = limit_exact_sentences(ai_reply, is_special)
                history.append({"role": "user", "content": user_message})
                history.append({"role": "assistant", "content": ai_reply})
                await message.reply(ai_reply)
            else:
                await message.reply("Hic, em đang hơi chóng mặt...")

    await bot.process_commands(message)

# =====================
# COMMANDS (Giữ cũ + Thêm mới)
# =====================
@bot.tree.command(name="check_affinity", description="Xem độ thân mật của bạn với Mahiru")
async def check_affinity(interaction: discord.Interaction):
    points = get_affinity(interaction.user.id)
    await interaction.response.send_message(f"💖 Độ thân mật hiện tại: **{points}** điểm.")

@bot.tree.command(name="setlovername", description="Đổi nickname đặc biệt cho người yêu 💕")
async def set_lover_name(interaction: discord.Interaction, name: str):
    global lover_nickname
    if interaction.user.id == SPECIAL_USER_ID:
        lover_nickname = name
        await interaction.response.send_message(f"**Mahiru từ giờ sẽ gọi anh là: {lover_nickname}**")
    else:
        await interaction.response.send_message("m đéo có quyền đâu con")

@bot.tree.command(name="setchannel", description="Chọn kênh để bot chat khi được tag")
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    global server_channels
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("❌ Bạn không có quyền dùng lệnh này.", ephemeral=False)
    
    # Lưu ID kênh cho server hiện tại
    server_channels[interaction.guild.id] = channel.id
    
    await interaction.response.send_message(f"✅ em sẽ chỉ chat trong kênh: {channel.mention} :3")
    
@bot.tree.command(name="clearchannel", description="Cho phép bot chat mọi kênh ở server này")
async def clearchannel(interaction: discord.Interaction):
    global server_channels
    if interaction.guild_id in server_channels:
        del server_channels[interaction.guild_id]
        await interaction.response.send_message(" Đã reset! Giờ em sẽ chat ở bất cứ kênh nào anh tag em.")
    else:
        await interaction.response.send_message("Server này vốn ko có gì để lưu r ạ :3!", ephemeral=False)

@bot.tree.command(name="resetmemory", description="Xoá lịch sử hội thoại của bạn với bot")
async def resetmemory(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in conversation_history:
        conversation_history[user_id].clear()
        await interaction.response.send_message("🧹 Lịch sử hội thoại của bạn đã được xoá sạch!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Bạn chưa có lịch sử hội thoại nào để xoá.", ephemeral=True)

@bot.tree.command(name="resetallmemory", description="Xoá toàn bộ lịch sử hội thoại (admin)")
async def resetallmemory(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Chỉ admin mới có thể dùng lệnh này.", ephemeral=True)
    conversation_history.clear()
    await interaction.response.send_message("🧹 Toàn bộ lịch sử hội thoại đã được xoá sạch!", ephemeral=True)
# ... Các lệnh setchannel, clearchannel, resetmemory giữ nguyên như code cũ của bạn ...

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot {bot.user} đã sẵn sàng!")

bot.run(TOKEN)
