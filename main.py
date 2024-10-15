import os
import random
import requests
import discord
from discord.ext import tasks
import aiosqlite
from db import setup_database, set_language, set_channel, get_settings
from reminders import reminders
from datetime import datetime

intents = discord.Intents.all()
intents.message_content = True

# Initialize the bot with CommandTree for slash commands
class DeenBot(discord.Client):
    def __init__(self, intents):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

bot = DeenBot(intents=intents)
supported_languages = {
    "en": "en.asad",
    "ar": "ar.alafasy",
    "fr": "fr.hamidullah"
}

@bot.event
async def on_ready():
    """Event that runs when the bot is ready."""
    await setup_database()
    post_hourly_verse.start()
    send_reminders.start()
    await bot.tree.sync()  # Sync slash commands with Discord
    print(f'Logged in as {bot.user}')

@bot.tree.command(name="help", description="Displays instructions and available commands for the bot.")
async def help(interaction: discord.Interaction):
    """Displays instructions and available commands for the bot."""

    # Explanation message for slash commands
    help_message = (
        "✨ **Hello! Here's how you can interact with me!** ✨\n\n"
        "I respond to **slash commands**. Simply type `/` in the text bar and you'll see a list of available commands.\n\n"
        "**Example commands:**\n"
        "`/salam` - Sends a greeting in Arabic. 🌟\n"
        "`/prayer <city>` - Provides prayer times for the specified city. 🕌\n"
        "`/verse` - Displays a random verse from the Quran in the selected language. 📖\n"
        "`/surat <number>` - Displays the specified Surah. 📜\n"
        "`/language` - Sets the language for Quran verses and reminders. 🌍\n"
        "`/channel` - Sets the channel for receiving Quran verses and prayer times. 💌\n\n"
        "Try these commands now by typing `/` and selecting a command! 😊"
    )

    # Send the message in response to the slash command
    await interaction.response.send_message(help_message)

# Slash command for greeting
@bot.tree.command(name="salam", description="Sends a greeting in Arabic.")
async def salam(interaction: discord.Interaction):
    await interaction.response.send_message(f"Wa ʿalaykumu s-salam {interaction.user}! ❤️")

# Slash command to set language
@bot.tree.command(name="language", description="Sets the language for Quran verses and reminders.")
async def language(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT language FROM server_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            result = await cursor.fetchone()

    current_language = result[0] if result else None

    if current_language:
        await interaction.response.send_message(
            f"The current language is **{current_language.upper()}**. Would you like to change it? (Type `fr`, `en`, or `ar` to change.) 💬")
    else:
        await interaction.response.send_message(
            "Please select a language for Quran verses and reminders:\n"
            "`en` for English\n"
            "`ar` for Arabic\n"
            "`fr` for French ❤️"
        )

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.content.lower() in supported_languages

    try:
        message = await bot.wait_for('message', check=check, timeout=60.0)
        selected_language = message.content.lower()
        await set_language(interaction.guild.id, selected_language)
        await interaction.followup.send(f"Language has been set to {selected_language}. 📚")
    except TimeoutError:
        await interaction.followup.send("You took too long to respond! Please try the command again. ⏳")

# Slash command to set channel
@bot.tree.command(name="channel", description="Sets the channel for receiving Quran verses and prayer times.")
async def channel(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT channel_id FROM server_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            result = await cursor.fetchone()

    current_channel_id = result[0] if result else None
    current_channel = bot.get_channel(current_channel_id) if current_channel_id else None

    if current_channel:
        await interaction.response.send_message(f"The current channel for notifications is {current_channel.mention}. Would you like to change it? Please mention the new channel. 💌")
    else:
        await interaction.response.send_message("Please mention the channel where you'd like to receive Quran verses and prayer times. 🕌")

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.content.startswith("<#")

    try:
        message = await bot.wait_for('message', check=check, timeout=60.0)
        channel_id = int(message.content[2:-1])
        channel = bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            await set_channel(interaction.guild.id, channel_id)
            await interaction.followup.send(f"Quran verses and prayer times will be sent to {channel.mention}. 🌙")
    except TimeoutError:
        await interaction.followup.send("You took too long to respond! Please try the command again. ⏳")

# Slash command to fetch a random verse
@bot.tree.command(name="verse", description="Fetches a random verse from the Quran in the selected language.")
async def verse(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT language FROM server_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            result = await cursor.fetchone()

    lang_code = result[0] if result else "en"
    verse_text = get_random_verse(lang_code)
    await interaction.response.send_message(verse_text)

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

@bot.tree.command(name="prayer", description="Fetches prayer times for the specified city, country, and today's date.")
async def prayer(interaction: discord.Interaction, city: str, country: str = "FR"):
    """Fetches prayer times for the specified city, country, and today's date."""
    
    # Get today's date in the format YYYY-MM-DD
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Use the date in the API request
    api_url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country={country}&method=2&date={today}"
    response = requests.get(api_url)

    if response.status_code == 200:
        data = response.json()
        if data['code'] == 200:
            timings = data['data']['timings']
            prayer_times = (
                f"**Prayer times for {city.capitalize()}, {country.upper()} on {today}**:\n"
                f"Fajr: {timings['Fajr']}\n"
                f"Dhuhr: {timings['Dhuhr']}\n"
                f"Asr: {timings['Asr']}\n"
                f"Maghrib: {timings['Maghrib']}\n"
                f"Isha: {timings['Isha']}\n"
                f"🕋 May Allah bless your prayers! ❤️"
            )
            await interaction.response.send_message(prayer_times)
        else:
            await interaction.response.send_message("Could not fetch prayer times. Please check the city name and try again. 🙁")
    else:
        await interaction.response.send_message("Sorry, I couldn't fetch prayer times at the moment. 😔")

def fetch_surat(surah_number, language="en"):
    api_url = f"http://api.alquran.cloud/v1/surah/{surah_number}/{language}"
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()["data"]["ayahs"]
    else:
        return None
    
@bot.tree.command(name="surat", description="Fetches a specific Surah from the Quran.")
async def surat(interaction: discord.Interaction, surah_number: int):
    await interaction.response.defer()  # Acknowledge the interaction immediately

    guild_id = interaction.guild.id
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT language FROM server_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            result = await cursor.fetchone()

    language = result[0] if result else "en"
    surah_content = fetch_surat(surah_number, supported_languages.get(language, "en"))

    if surah_content:
        verses = "\n".join([f"{ayah['numberInSurah']}: {ayah['text']}" for ayah in surah_content])
        
        # Split verses into manageable chunks
        chunk_size = 1900
        chunks = [verses[i:i + chunk_size] for i in range(0, len(verses), chunk_size)]

        for idx, chunk in enumerate(chunks):
            await interaction.followup.send(f"**Surah {surah_number} ({language.upper()}) - Part {idx + 1}:**\n{chunk}")
    else:
        await interaction.followup.send(f"Sorry, I couldn't fetch Surah {surah_number} at the moment. 😔")

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

@tasks.loop(hours=3)
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

# Start the bot
token = os.getenv('TOKEN_BOT')
bot.run(token)