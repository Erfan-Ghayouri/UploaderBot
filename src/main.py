import asyncio

from pyrogram import idle, Client
from tortoise import Tortoise

from config import Config
from database.database import init_database, DBChannel
from handlers import register_handlers


class UploaderBot(Client):

    def __init__(self):
        super().__init__(
            "UploaderBot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN
        )

        self.db_channel = DBChannel(self)

        register_handlers(self)


async def main():

    Config.validate()

    # Initialize database BEFORE starting the bot
    await init_database()

    bot = UploaderBot()
    started = False

    try:
        await bot.start()
        started = True

        print("🚀 UploaderBot is running!")

        await idle()

    finally:
        if started:
            await bot.stop()

        await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())