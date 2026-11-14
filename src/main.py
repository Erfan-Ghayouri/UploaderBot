from pyrogram import Client, filters
from config import Config
from handlers import register_handlers

class UploaderBot(Client):
    """
    This is the main class of the UploaderBot for initializing and running the bot.
    """
    __version__ = "0.1"

    def __init__(self, api_id, api_hash, bot_token, admin_ids):
        self.admin_ids = admin_ids
        super().__init__("UploaderBot", api_id, api_hash, bot_token=bot_token)

        register_handlers(self)


    def start_bot(self):
        self.run()


    def __str__(self):
        return f"The UploaderBot's status is: {super().is_connected}"


if __name__ == '__main__':
    Config.validate()

    bot = UploaderBot(
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        admin_ids=Config.ADMIN_IDS
    )

    bot.start_bot()