import os
import random
import requests
import discord
from discord.ext import commands, tasks
import aiosqlite
from db import setup_database, set_language, set_channel, get_settings
from reminders import reminders

intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

supported_languages = {
    "en": "en.asad",
    "ar": "ar.alafasy",
    "fr": "fr.hamidullah"
}

@bot.command()
async def salam(ctx):
    """Sends a greeting in Arabic."""
    await ctx.send(f"Wa ʿalaykumu s-salam {ctx.author}! ❤️")

@bot.command()
async def language(ctx):
    """Sets the language for Quran verses and reminders."""
    guild_id = ctx.guild.id
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT language FROM server_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            result = await cursor.fetchone()

    current_language = result[0] if result else None

    if current_language:
        await ctx.send(f"The current language is **{current_language.upper()}**. Would you like to change it? (Type `fr`, `en`, or `ar` to change.) 💬")
    else:
        await ctx.send(
            "Please select a language for Quran verses and reminders:\n"
            "`en` for English\n"
            "`ar` for Arabic\n"
            "`fr` for French ❤️"
        )

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in supported_languages

    try:
        message = await bot.wait_for('message', check=check, timeout=60.0)
        selected_language = message.content.lower()
        await set_language(ctx.guild.id, selected_language)
        await ctx.send(f"Language has been set to {selected_language}. 📚")
    except TimeoutError:
        await ctx.send("You took too long to respond! Please try the command again. ⏳")

@bot.command()
async def channel(ctx):
    """Sets the channel for receiving Quran verses and prayer times."""
    guild_id = ctx.guild.id
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT channel_id FROM server_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            result = await cursor.fetchone()

    current_channel_id = result[0] if result else None
    current_channel = bot.get_channel(current_channel_id) if current_channel_id else None

    if current_channel:
        await ctx.send(f"The current channel for notifications is {current_channel.mention}. Would you like to change it? Please mention the new channel. 💌")
    else:
        await ctx.send("Please mention the channel where you'd like to receive Quran verses and prayer times. 🕌")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.startswith("<#")

    try:
        message = await bot.wait_for('message', check=check, timeout=60.0)
        channel_id = int(message.content[2:-1])
        channel = bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            await set_channel(ctx.guild.id, channel_id)
            await ctx.send(f"Quran verses and prayer times will be sent to {channel.mention}. 🌙")
    except TimeoutError:
        await ctx.send("You took too long to respond! Please try the command again. ⏳")

@bot.command()
async def verse(ctx):
    """Fetches a random verse from the Quran in the selected language."""
    guild_id = ctx.guild.id
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT language FROM server_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            result = await cursor.fetchone()

    lang_code = result[0] if result else "en"
    verse_text = get_random_verse(lang_code)
    await ctx.send(verse_text)

def get_random_verse(lang_code):
    """Fetches a random verse from the Quran API."""
    surah_num = random.randint(1, 114)
    response = requests.get(f"http://api.alquran.cloud/v1/surah/{surah_num}")

    if response.status_code == 200:
        surah_data = response.json()["data"]
        verse_num = random.randint(1, surah_data["numberOfAyahs"])
        verse_response = requests.get(f"http://api.alquran.cloud/v1/ayah/{surah_num}:{verse_num}/{supported_languages[lang_code]}")

        if verse_response.status_code == 200:
            verse_data = verse_response.json()["data"]
            verse_text = verse_data["text"]
            surah_name = surah_data["englishName"] if lang_code == "en" else surah_data["name"]
            return f"**Surah {surah_name} ({surah_num}:{verse_num})**\n{verse_text} 📖"

    return "Sorry, I couldn't fetch a verse at the moment. 😔"

@bot.command()
async def prayer(ctx, city: str, country: str = "FR"):
    """Fetches prayer times for the specified city and country."""
    api_url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country={country}&method=2"
    response = requests.get(api_url)

    if response.status_code == 200:
        data = response.json()
        if data['code'] == 200:
            timings = data['data']['timings']
            prayer_times = (
                f"**Prayer times for {city.capitalize()}, {country.upper()}**:\n"
                f"Fajr: {timings['Fajr']}\n"
                f"Dhuhr: {timings['Dhuhr']}\n"
                f"Asr: {timings['Asr']}\n"
                f"Maghrib: {timings['Maghrib']}\n"
                f"Isha: {timings['Isha']}\n"
                f"🕋 May Allah bless your prayers! ❤️"
            )
            await ctx.send(prayer_times)
        else:
            await ctx.send("Could not fetch prayer times. Please check the city name and try again. 🙁")
    else:
        await ctx.send("Sorry, I couldn't fetch prayer times at the moment. 😔")

def fetch_surat(surat_number, language="en"):
    api_url = f"http://api.alquran.cloud/v1/surah/{surat_number}/{language}"
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()["data"]["ayahs"]
    else:
        return None

@bot.command()
async def surat(ctx, surah_number: int):
    guild_id = ctx.guild.id
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT language FROM server_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            result = await cursor.fetchone()

    language = result[0] if result else "en"
    surah_content = fetch_surat(surah_number, supported_languages.get(language, "en"))

    if surah_content:
        verses = "\n".join([f"{ayah['numberInSurah']}: {ayah['text']}" for ayah in surah_content])
        
        chunk_size = 1900
        chunks = [verses[i:i+chunk_size] for i in range(0, len(verses), chunk_size)]
        
        for idx, chunk in enumerate(chunks):
            await ctx.send(f"**Surah {surah_number} ({language.upper()}) - Part {idx + 1}:**\n{chunk}")
    else:
        await ctx.send(f"Sorry, I couldn't fetch Surah {surah_number} at the moment. 😔")
    
@tasks.loop(hours=2)
async def post_hourly_verse():
    """Posts a random verse every hour in the specified channel."""
    for guild in bot.guilds:
        settings = await get_settings(guild.id)
        if settings:
            lang_code, channel_id = settings
            channel = bot.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                verse_text = get_random_verse(lang_code)
                await channel.send(verse_text + " 🌟")

@tasks.loop(hours=5)
async def send_reminders():
    """Sends reminders five times a day in the selected channel."""
    for guild in bot.guilds:
        settings = await get_settings(guild.id)
        if settings:
            lang_code, channel_id = settings
            channel = bot.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                reminder_message = random.choice(reminders)
                await channel.send(reminder_message)

@bot.command()
async def commands(ctx):
    """Displays a list of commands and their descriptions."""
    help_message = (
        "**I am a Discord bot coded by 0xhajar.** 🥰\n"
        "I aim to help you improve your faith and stay connected with your spirituality! 💖\n\n"
        "**Bot Commands:**\n"
        "`!salam` - Sends a greeting in Arabic. ✨\n"
        "`!channel` - Sets the channel for receiving Quran verses and prayer times. Mention the channel when prompted. 🕌\n"
        "`!language` - Sets the language for Quran verses and reminders. Choose between English (`en`), Arabic (`ar`), or French (`fr`). 📚\n"
        "`!verse` - Fetches a random verse from the Quran in the selected language. 📖\n"
        "`!prayer <city>` - Fetches the prayer times for the specified city for the current day. 🕋\n"
        "`!surat <number>` - Fetches the specified Surah from the Quran. 📜\n"
        "\n**Usage Instructions:**\n"
        "1. Use `!language` to set your preferred language.\n"
        "2. Use `!channel` to set the channel for notifications.\n"
        "3. Use `!prayer <city>` to get the prayer times.\n"
        "4. Use `!verse` to get a random verse in your selected language. 🌟\n"
        "5. Use `!surat <number>` to get the specified Surah from the Quran. 📜"
    )
    await ctx.send(help_message)

@bot.event
async def on_guild_join(guild):
    """Event triggered when the bot joins a new server (guild)."""
    # Log the join event
    user = await bot.fetch_user(1250032893955280909)
    await user.send(f"{guild.name} ({guild.id}) added me. Total servers: {len(bot.guilds)}")

    # Determine the channel to send the help message
    if guild.system_channel: 
        channel = guild.system_channel
    else:
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                channel = ch
                break
        else:
            return  # No suitable channel found

    help_message = (
        "**I am a Discord bot coded by 0xhajar.** 🥰\n"
        "I aim to help you improve your faith and stay connected with your spirituality! 💖\n\n"
        "**Bot Commands:**\n"
        "`!salam` - Sends a greeting in Arabic. ✨\n"
        "`!channel` - Sets the channel for receiving Quran verses and prayer times. Mention the channel when prompted. 🕌\n"
        "`!language` - Sets the language for Quran verses and reminders. Choose between English (`en`), Arabic (`ar`), or French (`fr`). 📚\n"
        "`!verse` - Fetches a random verse from the Quran in the selected language. 📖\n"
        "`!prayer <city>` - Fetches the prayer times for the specified city for the current day. 🕋\n"
        "`!surat <number>` - Fetches the specified Surah from the Quran. 📜\n"
        "\n**Usage Instructions:**\n"
        "1. Use `!language` to set your preferred language.\n"
        "2. Use `!channel` to set the channel for notifications.\n"
        "3. Use `!prayer <city>` to get the prayer times.\n"
        "4. Use `!verse` to get a random verse in your selected language. 🌟\n"
        "5. Use `!surat <number>` to get the specified Surah from the Quran. 📜"
    )
    
    await channel.send(help_message)

@bot.event
async def on_message(message):
    """Handles messages sent to the bot."""
    if message.author == bot.user:
        return
    
    if isinstance(message.channel, discord.DMChannel):
        user = message.author
        log_user_id = 1250032893955280909
        user_to_log = await bot.fetch_user(log_user_id)
        await user_to_log.send(f"DM from {user.name}: {message.content}")

    else:
        guild = message.guild
        user = message.author
        log_user_id = 1250032893955280909
        user_to_log = await bot.fetch_user(log_user_id)
        await user_to_log.send(f"Message from {user.name} in {guild.name}: {message.content}")

    await bot.process_commands(message)
    
@bot.event
async def on_guild_remove(guild):
  user = await bot.fetch_user(1250032893955280909)
  await user.send(guild.name + ' ' + str(guild.id) +
                  ' removed me number of servers ' + str(len(bot.guilds)))

@bot.event
async def on_ready():
    """Event that runs when the bot is ready."""
    await setup_database()
    post_hourly_verse.start()
    send_reminders.start()
    print(f'Logged in as {bot.user}')

print(os.environ)
token = os.getenv('TOKEN_BOT')
bot.run(token)
