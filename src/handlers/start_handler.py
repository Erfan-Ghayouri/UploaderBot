from pyrogram import Client, filters


def register_start_handler(app: Client):

    @app.on_message(filters.command("start"))
    async def start_handler(client, message):
        await message.reply_text(
            "سلام 👋 به UploaderBot خوش اومدی!"
        )