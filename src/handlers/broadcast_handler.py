import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, PeerFlood, RPCError
from pyrogram.types import Message

from config import Config
from database.models import User
from handlers.keyboards import (
    main_keyboard_for,
    CANCEL_OPERATION_KEYBOARD,
    RESERVED_BUTTONS,
)
from handlers.state import broadcast_states, channel_states, upload_sessions
from utils.admins import admin_filter, is_admin


logger = logging.getLogger(__name__)

# فاصله بین ارسال‌ها برای جلوگیری از محدودیت flood تلگرام
BROADCAST_DELAY_SECONDS = 0.1


def register_broadcast_handler(app: Client):

    async def broadcast_pending_filter(_, __, message: Message):
        return bool(
            message.from_user
            and broadcast_states.get(message.from_user.id)
        )

    # --------------------------------------------------------
    # شروع پیام همگانی
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^📣 پیام همگانی$")
    )
    async def start_broadcast(client, message: Message):
        admin_id = message.from_user.id

        if admin_id in channel_states or admin_id in upload_sessions:
            await message.reply_text(
                "❌ ابتدا عملیات فعلی را لغو یا کامل کن."
            )
            return

        broadcast_states[admin_id] = True

        await message.reply_text(
            "📣 پیام همگانی\n\n"
            "پیام یا فایلی که می‌خواهی برای همه کاربران ارسال شود "
            "را بفرست.",
            reply_markup=CANCEL_OPERATION_KEYBOARD,
        )

    # --------------------------------------------------------
    # دریافت محتوای همگانی و ارسال به همه کاربران
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & ~filters.command("start")
        & ~filters.regex(r"^❌ لغو عملیات$")
        & filters.create(broadcast_pending_filter),
        group=-3,
    )
    async def receive_broadcast_message(client, message: Message):
        admin_id = message.from_user.id

        # دکمه‌های پنل، محتوای همگانی نیستند؛ عبور بده تا
        # هندلر خودشان آن‌ها را پردازش کند.
        if message.text and message.text in RESERVED_BUTTONS:
            return

        broadcast_states.pop(admin_id, None)

        users = await User.all()

        if not users:
            await message.reply_text(
                "❌ هنوز هیچ کاربری ثبت نشده است.",
                reply_markup=main_keyboard_for(admin_id),
            )
            return

        status = await message.reply_text(
            "⏳ در حال ارسال پیام همگانی..."
        )

        delivered = 0
        failed = 0
        skipped = 0
        aborted = False

        for user in users:
            # به خود ادمین‌ها پیام همگانی نفرست
            if await is_admin(user.user_id):
                skipped += 1
                continue

            try:
                await message.copy(chat_id=user.user_id)
                delivered += 1

            except FloodWait as e:
                # تلگرام خواسته کمی صبر کنیم؛ بعد یک تلاش دوباره
                await asyncio.sleep((e.seconds or 5) + 1)

                try:
                    await message.copy(chat_id=user.user_id)
                    delivered += 1

                except Exception:
                    failed += 1

            except PeerFlood:
                # محدودیت سروری تلگرام؛ ادامه دادن ریسک بن دارد
                logger.error(
                    "Broadcast aborted: PeerFlood limit hit."
                )
                aborted = True
                break

            except Exception:
                # کاربر ربات را بلاک کرده، غیرفعال است و...
                # رد شو و سراغ کاربر بعدی برو
                failed += 1

            await asyncio.sleep(BROADCAST_DELAY_SECONDS)

        summary = (
            "📣 ارسال همگانی تمام شد.\n\n"
            f"✅ ارسال‌شده: {delivered}\n"
            f"❌ ناموفق: {failed}\n"
            f"⏭ ردشده: {skipped}"
        )

        if aborted:
            summary += (
                "\n\n⚠️ ارسال به دلیل محدودیت flood تلگرام متوقف شد."
            )

        try:
            await status.edit_text(summary)
        except RPCError:
            await message.reply_text(summary)

        # بازگرداندن کیبورد پنل ادمین
        await message.reply_text(
            "🏠 به پنل مدیریت برگشتی.",
            reply_markup=main_keyboard_for(admin_id),
        )

    logger.info("Broadcast handler registered successfully.")
