import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from config import Config
from database.models import ViewReactionChannel
from handlers.keyboards import (
    ADMIN_MAIN_KEYBOARD,
    CHANNEL_MENU_KEYBOARD,
    VIEW_REACTION_MENU_KEYBOARD,
)
from handlers.state import broadcast_states, channel_states


logger = logging.getLogger(__name__)


def register_admin_handler(app: Client):
    admin_filter = filters.user(Config.ADMIN_IDS)

    # --------------------------------------------------------
    # استارت ادمین
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & filters.command("start")
        & admin_filter
    )
    async def admin_start(client, message: Message):
        payload = (
            message.command[1]
            if len(message.command) > 1
            else None
        )

        if payload:
            # ادمین هم مثل کاربر می‌تواند با لینک فایل بگیرد
            from handlers.user_handler import send_manifest_files

            await send_manifest_files(client, message, payload)
            return

        await message.reply_text(
            "سلام ادمین عزیز 👋\n"
            "به پنل مدیریت خوش اومدی.",
            reply_markup=ADMIN_MAIN_KEYBOARD,
        )

    # --------------------------------------------------------
    # ورود به منوی کانال‌های قفل‌شده
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^🔒 مدیریت کانال‌های قفل‌شده$")
    )
    async def open_sponsor_menu(client, message: Message):
        channel_states.pop(message.from_user.id, None)
        broadcast_states.pop(message.from_user.id, None)

        await message.reply_text(
            "🔒 مدیریت کانال‌های قفل‌شده",
            reply_markup=CHANNEL_MENU_KEYBOARD,
        )

    # --------------------------------------------------------
    # ورود به منوی کانال سین/ری‌اکشن
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^👁️ مدیریت شرط سین/ری‌اکشن$")
    )
    async def open_view_menu(client, message: Message):
        channel_states.pop(message.from_user.id, None)
        broadcast_states.pop(message.from_user.id, None)

        channel = await ViewReactionChannel.get_or_none(id=1)

        if not channel:
            status_text = "وضعیت کانال: ثبت نشده"
        else:
            status = "فعال ✅" if channel.enabled else "غیرفعال ❌"

            status_text = (
                f"نام کانال: {channel.name}\n"
                f"وضعیت شرط: {status}\n"
                f"لینک: {channel.invite_link}"
            )

        await message.reply_text(
            f"👁️ مدیریت شرط سین/ری‌اکشن\n\n{status_text}",
            reply_markup=VIEW_REACTION_MENU_KEYBOARD,
        )

    # --------------------------------------------------------
    # لغو عملیات و بازگشت به پنل
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^❌ لغو عملیات$")
    )
    async def cancel_general_operation(client, message: Message):
        admin_id = message.from_user.id

        channel_states.pop(admin_id, None)
        broadcast_states.pop(admin_id, None)

        await message.reply_text(
            "عملیات لغو شد.",
            reply_markup=ADMIN_MAIN_KEYBOARD,
        )

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^↩️ پنل اصلی$")
    )
    async def back_to_admin_panel(client, message: Message):
        admin_id = message.from_user.id

        channel_states.pop(admin_id, None)
        broadcast_states.pop(admin_id, None)

        await message.reply_text(
            "🏠 پنل اصلی مدیریت",
            reply_markup=ADMIN_MAIN_KEYBOARD,
        )

    logger.info("Admin handler registered successfully.")
