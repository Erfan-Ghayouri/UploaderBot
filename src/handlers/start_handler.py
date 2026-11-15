import asyncio
import json

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
from database.database import get_setting, set_setting
from database.models import User
from handlers.keyboards import (
    ADMIN_PANEL_TEXT,
    build_panel_keyboard,
    build_permanent_link_keyboard,
)
from utils.manifest import parse_manifest

USER_WELCOME_TEXT = "سلام 👋\nبرای دریافت فایل‌ها از لینک اختصاصی استفاده کن."
DELIVERY_FAILED_TEXT = "❌ متأسفانه فایل‌ها در دسترس نیستن."
NOTICE_TEXT = (
    "⚠️ این فایل‌ها تا {} ثانیهٔ دیگه به‌صورت خودکار پاک می‌شن!\n"
    "برای دریافت دوباره، هر وقت خواستی از دکمه‌ی زیر استفاده کن 👇"
)


def register_start_handler(app: Client):

    @app.on_message(filters.private & filters.command("start"))
    async def start_handler(client: Client, message: Message):
        payload = message.command[1] if len(message.command) > 1 else None

        if payload and payload.isdigit():
            await deliver_files(client, message, int(payload))
            return

        if message.from_user and message.from_user.id in Config.ADMIN_IDS:
            timer_on = await get_setting("timer_on", "on") == "on"
            view_on = await get_setting("view_on", "on") == "on"

            await message.reply_text(
                ADMIN_PANEL_TEXT,
                reply_markup=build_panel_keyboard(timer_on, view_on),
            )

        else:
            await message.reply_text(USER_WELCOME_TEXT)


async def deliver_files(client: Client, message: Message, manifest_id: int):
    chat_id = message.chat.id

    await User.get_or_create(user_id=chat_id)

    manifest = await client.get_messages(Config.DB_CHANNEL_ID, manifest_id)
    parsed = parse_manifest(manifest.text) if manifest and not manifest.empty else None

    if not parsed or not parsed[2]:
        await message.reply_text(DELIVERY_FAILED_TEXT)
        return

    _, timer_on, file_ids = parsed

    sent_ids = []

    for file_id in file_ids:
        try:
            sent = await client.copy_message(chat_id, Config.DB_CHANNEL_ID, file_id)
            sent_ids.append(sent.id)

        except Exception:
            continue

    if not sent_ids:
        await message.reply_text(DELIVERY_FAILED_TEXT)
        return

    if not timer_on:
        return

    me = await client.get_me()
    permanent_link = f"https://t.me/{me.username}?start={manifest_id}"

    # پیام اطلاع‌رسانی حذف با دکمه شیشه‌ای لینک دائمی؛ حذف نمیشه که لینک بمونه
    notice = await message.reply_text(
        NOTICE_TEXT.format(Config.AUTO_DELETE_SECONDS),
        reply_markup=build_permanent_link_keyboard(permanent_link),
    )

    await set_setting(f"notice:{manifest_id}", json.dumps([notice.id]))

    asyncio.create_task(
        auto_delete_later(client, chat_id, sent_ids, Config.AUTO_DELETE_SECONDS)
    )


async def auto_delete_later(client: Client, chat_id: int, message_ids, delay: int):
    await asyncio.sleep(delay)

    for message_id in message_ids:
        try:
            await client.delete_messages(chat_id, message_id)

        except Exception:
            continue
