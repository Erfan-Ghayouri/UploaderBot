import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from database.models import ViewReactionChannel
from handlers.keyboards import (
    main_keyboard_for,
    upload_keyboard,
)
from handlers.helpers import delete_messages_after
from handlers.state import (
    auto_delete_enabled,
    broadcast_states,
    channel_states,
    upload_sessions,
)
from utils.base62 import encode_base62
from utils.admins import admin_filter


logger = logging.getLogger(__name__)

# مدت حذف خودکار پیام اصلی فایل ادمین
ADMIN_FILE_DELETE_SECONDS = 60


def register_upload_handler(app: Client):

    # --------------------------------------------------------
    # شروع آپلود
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^📤 آپلود فایل$")
    )
    async def begin_upload(client, message: Message):
        admin_id = message.from_user.id

        if (
            admin_id in channel_states
            or admin_id in broadcast_states
        ):
            await message.reply_text(
                "❌ ابتدا عملیات فعلی را لغو یا کامل کن."
            )
            return

        if admin_id in upload_sessions:
            await message.reply_text(
                "⚠️ یک آپلود در حال انجام داری.",
                reply_markup=upload_keyboard(
                    auto_delete_enabled.get(admin_id, False)
                ),
            )
            return

        upload_sessions[admin_id] = []
        auto_delete_enabled[admin_id] = False

        await message.reply_text(
            "📤 حالت آپلود فعال شد.\n\n"
            "فایل‌ها را یکی‌یکی یا پشت‌سرهم ارسال کن.\n"
            "بعد از ارسال همه فایل‌ها، «اتمام آپلود» را بزن.\n\n"
            "با روشن کردن حذف خودکار، پیام اصلی فایل‌هایی که می‌فرستی "
            "بعد از ۶۰ ثانیه از چت ربات حذف می‌شوند. "
            "نسخه ذخیره‌شده در کانال دیتابیس حذف نمی‌شود.",
            reply_markup=upload_keyboard(False),
        )

    # --------------------------------------------------------
    # روشن و خاموش کردن حذف خودکار
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^🗑 حذف خودکار: (روشن|خاموش)$")
    )
    async def toggle_auto_delete(client, message: Message):
        admin_id = message.from_user.id

        if admin_id not in upload_sessions:
            await message.reply_text(
                "❌ ابتدا آپلود را شروع کن.",
                reply_markup=main_keyboard_for(admin_id),
            )
            return

        current_status = auto_delete_enabled.get(
            admin_id,
            False,
        )

        new_status = not current_status
        auto_delete_enabled[admin_id] = new_status

        status_text = "روشن ✅" if new_status else "خاموش ❌"

        await message.reply_text(
            f"وضعیت حذف خودکار: {status_text}\n\n"
            "در صورت روشن بودن، پیام اصلی فایل ارسالی "
            "پس از ۶۰ ثانیه حذف می‌شود.",
            reply_markup=upload_keyboard(new_status),
        )

    # --------------------------------------------------------
    # دریافت فایل‌های ادمین
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.media
    )
    async def receive_upload_file(client, message: Message):
        admin_id = message.from_user.id

        # اگر در حال افزودن کانال یا پیام همگانی هستیم،
        # پیام را آپلود نکن.
        if admin_id in channel_states or admin_id in broadcast_states:
            return

        # اگر آپلود شروع نشده، هیچ پیامی نده.
        # این موضوع از تداخل با ثبت نام و لینک کانال جلوگیری می‌کند.
        if admin_id not in upload_sessions:
            return

        try:
            # ابتدا فایل در کانال دیتابیس ذخیره می‌شود.
            stored_message = await client.db_channel.save_file(
                message
            )

            if not stored_message:
                await message.reply_text(
                    "❌ ذخیره فایل در کانال دیتابیس ناموفق بود."
                )
                return

            upload_sessions[admin_id].append(
                stored_message.id
            )

            # حذف پیام اصلی ادمین، نه کپی داخل کانال دیتابیس
            if auto_delete_enabled.get(admin_id, False):
                asyncio.create_task(
                    delete_messages_after(
                        client,
                        message.chat.id,
                        [message.id],
                        ADMIN_FILE_DELETE_SECONDS,
                    )
                )

            count = len(upload_sessions[admin_id])

            await message.reply_text(
                f"✅ فایل ذخیره شد.\n"
                f"تعداد فایل‌های آپلودشده: {count}",
                reply_markup=upload_keyboard(
                    auto_delete_enabled.get(admin_id, False)
                ),
            )

        except Exception:
            logger.exception("File upload failed")

            await message.reply_text(
                "❌ هنگام ذخیره فایل خطایی رخ داد."
            )

    # --------------------------------------------------------
    # اتمام آپلود و ساخت لینک
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^✅ اتمام آپلود$")
    )
    async def finish_upload(client, message: Message):
        admin_id = message.from_user.id

        file_ids = upload_sessions.get(admin_id)

        if file_ids is None:
            await message.reply_text(
                "❌ ابتدا آپلود را شروع کن.",
                reply_markup=main_keyboard_for(admin_id),
            )
            return

        if not file_ids:
            await message.reply_text(
                "❌ هنوز هیچ فایلی ارسال نکرده‌ای.",
                reply_markup=upload_keyboard(
                    auto_delete_enabled.get(admin_id, False)
                ),
            )
            return

        auto_delete = auto_delete_enabled.get(
            admin_id,
            False,
        )

        try:
            # وضعیت فعلی کانال ریاکشن در منیفست ثبت می‌شود.
            view_channel = await ViewReactionChannel.get_or_none(
                id=1
            )

            view_gate_enabled = bool(
                view_channel and view_channel.enabled
            )

            manifest = await client.db_channel.create_manifest(
                file_ids=file_ids,
                view_gate_enabled=view_gate_enabled,
                auto_delete_enabled=auto_delete,
            )

            payload = encode_base62(manifest.id)

            me = await client.get_me()

            download_link = (
                f"https://t.me/{me.username}?start={payload}"
            )

            download_keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📥 دریافت فایل",
                            url=download_link,
                        )
                    ]
                ]
            )

            file_count = len(file_ids)

            # پاک کردن سشن پس از ساخت موفق منیفست
            upload_sessions.pop(admin_id, None)
            auto_delete_enabled.pop(admin_id, None)

            # پیام اول: لینک با دکمه شیشه‌ای
            await message.reply_text(
                "✅ آپلود با موفقیت به پایان رسید.\n\n"
                f"📁 تعداد فایل‌ها: {file_count}\n"
                f"🗑 حذف خودکار پیام‌های اصلی: "
                f"{'روشن' if auto_delete else 'خاموش'}\n"
                f"👁️ شرط سین/ری‌اکشن: "
                f"{'فعال' if view_gate_enabled else 'غیرفعال'}\n\n"
                "لینک دریافت فایل:",
                reply_markup=download_keyboard,
            )

            # پیام دوم: بازگرداندن کیبورد اصلی ادمین
            await message.reply_text(
                "🏠 به پنل مدیریت برگشتی.",
                reply_markup=main_keyboard_for(admin_id),
            )

        except Exception:
            logger.exception("Finishing upload failed")

            await message.reply_text(
                "❌ هنگام ساخت منیفست یا لینک خطایی رخ داد.\n"
                "فایل‌های آپلودشده از سشن حذف نشده‌اند؛ "
                "می‌توانی دوباره اتمام آپلود را امتحان کنی.",
                reply_markup=upload_keyboard(
                    auto_delete_enabled.get(admin_id, False)
                ),
            )

    # --------------------------------------------------------
    # لغو آپلود
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^❌ لغو آپلود$")
    )
    async def cancel_upload(client, message: Message):
        admin_id = message.from_user.id

        upload_sessions.pop(admin_id, None)
        auto_delete_enabled.pop(admin_id, None)

        await message.reply_text(
            "❌ آپلود لغو شد.\n"
            "فایل‌هایی که قبلاً در کانال دیتابیس ذخیره شده‌اند "
            "حذف نمی‌شوند.",
            reply_markup=main_keyboard_for(admin_id),
        )

    logger.info("Upload handler registered successfully.")
