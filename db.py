import aiosqlite

# Setup the database and create the table if it doesn't exist
async def setup_database():
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS server_settings (
                guild_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL,
                channel_id INTEGER
            );
        """)
        await db.commit()

# Set or update the language for a guild
async def set_language(guild_id, lang_code):
    async with aiosqlite.connect("bot_data.db") as db:
        await db.execute("""
            INSERT INTO server_settings (guild_id, language) 
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET language = ?;
        """, (guild_id, lang_code, lang_code))
        await db.commit()

# Set or update the channel for a guild
async def set_channel(guild_id, channel_id):
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT language FROM server_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            result = await cursor.fetchone()

        if result is None:
            # If no language is set, default to 'en' and insert both language and channel
            await db.execute("""
                INSERT INTO server_settings (guild_id, language, channel_id) 
                VALUES (?, ?, ?);
            """, (guild_id, "en", channel_id))
        else:
            # If a language exists, update the channel
            await db.execute("""
                UPDATE server_settings 
                SET channel_id = ? 
                WHERE guild_id = ?;
            """, (channel_id, guild_id))

        await db.commit()

# Retrieve the language and channel for a guild
async def get_settings(guild_id):
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT language, channel_id FROM server_settings WHERE guild_id = ?", (guild_id,)) as cursor:
            return await cursor.fetchone()
