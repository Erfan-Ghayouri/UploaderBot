import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from config import Config
from database.models import ViewReactionChannel
from handlers.helpers import get_forwarded_channel, is_valid_telegram_link
from handlers.keyboards import (
    CANCEL_OPERATION_KEYBOARD,
    VIEW_REACTION_MENU_KEYBOARD,
)
from handlers.state import (
    broadcast_states,
    channel_states,
    make_state_filter,
    upload_sessions,
)


logger = logging.getLogger(__name__)


def register_view_channel_handler(app: Client):
    admin_filter = filters.user(Config.ADMIN_IDS)

    view_forward_filter = make_state_filter("view", "forward")
    view_details_filter = make_state_filter("view", "details")

    # --------------------------------------------------------
    # شروع افزودن یا جایگزینی کانال ریاکشن
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^➕ افزودن/جایگزینی کانال$")
    )
    async def start_add_view_channel(client, message: Message):
        admin_id = message.from_user.id

        if admin_id in upload_sessions or admin_id in broadcast_states:
            await message.reply_text(
                "❌ ابتدا عملیات فعلی را لغو یا کامل کن."
            )
            return

        channel_states[admin_id] = {
            "kind": "view",
            "step": "forward",
        }

        await message.reply_text(
            "📩 یک پست از کانالی که می‌خواهی برای شرط سین/ری‌اکشن "
            "استفاده شود فوروارد کن.\n\n"
            "با ثبت کانال جدید، کانال قبلی جایگزین می‌شود.",
            reply_markup=CANCEL_OPERATION_KEYBOARD,
        )

    # --------------------------------------------------------
    # دریافت پست فورواردشده کانال ریاکشن
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & view_forward_filter,
        group=-2,
    )
    async def receive_view_channel_forward(client, message: Message):
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

        # برای این قابلیت نیازی به بررسی عضویت یا ادمین بودن
        # ربات در کانال نیست؛ چون بازدید و ریاکشن بررسی نمی‌شود.
        channel_states[admin_id] = {
            "kind": "view",
            "step": "details",
            "channel_id": channel.id,
        }

        await message.reply_text(
            "✅ کانال شناسایی شد.\n\n"
            "حالا نام کانال و لینک آن را با این فرمت بفرست:\n\n"
            "`نام کانال | https://t.me/channel`",
            reply_markup=CANCEL_OPERATION_KEYBOARD,
        )

    # --------------------------------------------------------
    # ثبت نام و لینک کانال ریاکشن
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.text
        & view_details_filter,
        group=-2,
    )
    async def receive_view_channel_details(client, message: Message):
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
            await message.reply_text(
                "❌ نام کانال را وارد کن."
            )
            return

        if not is_valid_telegram_link(invite_link):
            await message.reply_text(
                "❌ لینک تلگرام معتبر نیست."
            )
            return

        try:
            # همیشه id=1 است؛ بنابراین کانال جدید جایگزین قبلی می‌شود.
            await ViewReactionChannel.update_or_create(
                id=1,
                defaults={
                    "channel_id": state["channel_id"],
                    "name": name,
                    "invite_link": invite_link,
                    "enabled": True,
                },
            )

            channel_states.pop(admin_id, None)

            await message.reply_text(
                f"✅ کانال سین/ری‌اکشن ثبت شد.\n\n"
                f"نام: {name}\n"
                f"وضعیت: فعال ✅",
                reply_markup=VIEW_REACTION_MENU_KEYBOARD,
            )

        except Exception:
            logger.exception("View channel registration failed")

            await message.reply_text(
                "❌ ثبت کانال ریاکشن با خطا مواجه شد."
            )

    # --------------------------------------------------------
    # فعال یا غیرفعال کردن کانال ریاکشن
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^🔄 فعال/غیرفعال کردن شرط$")
    )
    async def toggle_view_channel(client, message: Message):
        channel = await ViewReactionChannel.get_or_none(id=1)

        if not channel:
            await message.reply_text(
                "❌ هنوز کانال ریاکشن ثبت نشده است.",
                reply_markup=VIEW_REACTION_MENU_KEYBOARD,
            )
            return

        channel.enabled = not channel.enabled
        await channel.save()

        status = "فعال ✅" if channel.enabled else "غیرفعال ❌"

        await message.reply_text(
            f"وضعیت شرط سین/ری‌اکشن تغییر کرد.\n\n"
            f"کانال: {channel.name}\n"
            f"وضعیت جدید: {status}",
            reply_markup=VIEW_REACTION_MENU_KEYBOARD,
        )

    # --------------------------------------------------------
    # حذف کانال ریاکشن
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^🗑 حذف کانال ریاکشن$")
    )
    async def delete_view_channel(client, message: Message):
        channel = await ViewReactionChannel.get_or_none(id=1)

        if not channel:
            await message.reply_text(
                "❌ کانالی برای حذف وجود ندارد.",
                reply_markup=VIEW_REACTION_MENU_KEYBOARD,
            )
            return

        await channel.delete()

        await message.reply_text(
            "✅ کانال ریاکشن حذف شد و شرط آن غیرفعال شد.",
            reply_markup=VIEW_REACTION_MENU_KEYBOARD,
        )

    logger.info("View channel handler registered successfully.")
