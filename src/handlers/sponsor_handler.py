import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import RPCError
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from database.models import SponsorChannel
from handlers.helpers import get_forwarded_channel, is_valid_telegram_link
from handlers.keyboards import (
    CANCEL_OPERATION_KEYBOARD,
    CHANNEL_MENU_KEYBOARD,
)
from handlers.state import (
    broadcast_states,
    make_state_filter,
    upload_sessions,
    channel_states,
)
from utils.admins import admin_filter


logger = logging.getLogger(__name__)


def register_sponsor_handler(app: Client):

    sponsor_forward_filter = make_state_filter("sponsor", "forward")
    sponsor_details_filter = make_state_filter("sponsor", "details")

    # --------------------------------------------------------
    # شروع افزودن کانال قفل‌شده
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^➕ افزودن کانال قفل‌شده$")
    )
    async def start_add_sponsor_channel(client, message: Message):
        admin_id = message.from_user.id

        if admin_id in upload_sessions or admin_id in broadcast_states:
            await message.reply_text(
                "❌ ابتدا عملیات فعلی را لغو یا کامل کن."
            )
            return

        channel_states[admin_id] = {
            "kind": "sponsor",
            "step": "forward",
        }

        await message.reply_text(
            "📩 یک پست از کانال موردنظر را فوروارد کن.\n\n"
            "ربات باید در کانال ادمین باشد.",
            reply_markup=CANCEL_OPERATION_KEYBOARD,
        )

    # --------------------------------------------------------
    # دریافت فوروارد کانال قفل‌شده
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & sponsor_forward_filter,
        group=-2,
    )
    async def receive_sponsor_forward(client, message: Message):
        admin_id = message.from_user.id

        channel = get_forwarded_channel(message)

        if not channel:
            await message.reply_text(
                "❌ لطفاً یک پست از خود کانال فوروارد کن."
            )
            return

        if channel.type != ChatType.CHANNEL:
            await message.reply_text(
                "❌ لطفاً یک کانال تلگرامی فوروارد کن."
            )
            return

        try:
            bot = await client.get_me()

            bot_member = await client.get_chat_member(
                channel.id,
                bot.id,
            )

            if bot_member.status not in (
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            ):
                await message.reply_text(
                    "❌ ربات باید در کانال ادمین باشد."
                )
                return

        except Exception:
            logger.exception("Sponsor channel permission check failed")

            await message.reply_text(
                "❌ امکان بررسی دسترسی ربات در کانال وجود ندارد."
            )
            return

        channel_states[admin_id] = {
            "kind": "sponsor",
            "step": "details",
            "channel_id": channel.id,
        }

        await message.reply_text(
            "✅ کانال شناسایی شد.\n\n"
            "حالا نام کانال و لینک عضویت را با این فرمت بفرست:\n\n"
            "`نام کانال | https://t.me/channel`",
            reply_markup=CANCEL_OPERATION_KEYBOARD,
        )

    # --------------------------------------------------------
    # ثبت مشخصات کانال قفل‌شده
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.text
        & sponsor_details_filter,
        group=-2,
    )
    async def receive_sponsor_details(client, message: Message):
        admin_id = message.from_user.id
        state = channel_states.get(admin_id)

        if not state:
            return

        parts = message.text.split("|", 1)

        if len(parts) != 2:
            await message.reply_text(
                "❌ فرمت اشتباه است.\n"
                "مثال:\n"
                "`نام کانال | https://t.me/channel`"
            )
            return

        name = parts[0].strip()
        invite_link = parts[1].strip()

        if not name:
            await message.reply_text("❌ نام کانال را وارد کن.")
            return

        if not is_valid_telegram_link(invite_link):
            await message.reply_text(
                "❌ لینک تلگرام معتبر نیست."
            )
            return

        try:
            await SponsorChannel.update_or_create(
                channel_id=state["channel_id"],
                defaults={
                    "name": name,
                    "invite_link": invite_link,
                },
            )

            channel_states.pop(admin_id, None)

            await message.reply_text(
                f"✅ کانال قفل‌شده ثبت شد.\n\n"
                f"نام: {name}",
                reply_markup=CHANNEL_MENU_KEYBOARD,
            )

        except Exception:
            logger.exception("Sponsor channel registration failed")

            await message.reply_text(
                "❌ ثبت کانال با خطا مواجه شد."
            )

    # --------------------------------------------------------
    # نمایش کانال‌های قفل‌شده
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^📋 لیست کانال‌های قفل‌شده$")
    )
    async def list_sponsor_channels(client, message: Message):
        channels = await SponsorChannel.all().order_by("name")

        if not channels:
            await message.reply_text(
                "هنوز هیچ کانال قفل‌شده‌ای ثبت نشده است.",
                reply_markup=CHANNEL_MENU_KEYBOARD,
            )
            return

        rows = []

        for channel in channels:
            rows.append(
                [
                    InlineKeyboardButton(
                        f"🗑 حذف {channel.name}",
                        callback_data=f"delsponsor:{channel.channel_id}",
                    )
                ]
            )

        await message.reply_text(
            "📋 کانال‌های قفل‌شده ثبت‌شده:",
            reply_markup=InlineKeyboardMarkup(rows),
        )

    # --------------------------------------------------------
    # حذف کانال قفل‌شده
    # --------------------------------------------------------

    @app.on_callback_query(
        filters.regex(r"^delsponsor:-?\d+$")
        & admin_filter
    )
    async def delete_sponsor_channel(client, callback_query):
        try:
            channel_id = int(
                callback_query.data.split(":", 1)[1]
            )

            channel = await SponsorChannel.get_or_none(
                channel_id=channel_id
            )

            if not channel:
                await callback_query.answer(
                    "این کانال قبلاً حذف شده است.",
                    show_alert=True,
                )
                return

            await channel.delete()

            await callback_query.answer(
                "✅ کانال حذف شد.",
                show_alert=True,
            )

            try:
                await callback_query.message.edit_text(
                    f"✅ کانال «{channel.name}» حذف شد."
                )
            except RPCError:
                pass

        except Exception:
            logger.exception("Sponsor channel deletion failed")

            await callback_query.answer(
                "❌ حذف کانال ناموفق بود.",
                show_alert=True,
            )

    logger.info("Sponsor handler registered successfully.")
