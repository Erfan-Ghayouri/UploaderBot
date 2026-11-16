from config import Config
from pyrogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# ============================================================
# کیبوردهای ادمین
# ============================================================

ADMIN_MAIN_KEYBOARD_OWNER = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📤 آپلود فایل")],
        [KeyboardButton("🔒 مدیریت کانال‌های قفل‌شده")],
        [KeyboardButton("👁️ مدیریت شرط سین/ری‌اکشن")],
        [KeyboardButton("📣 پیام همگانی")],
        [KeyboardButton("👥 مدیریت ادمین‌ها")],
    ],
    resize_keyboard=True,
)

# برای ادمین‌های اضافه‌شده (غیرمالک): دکمه مدیریت ادمین‌ها نمایش داده نمی‌شود
ADMIN_MAIN_KEYBOARD_LIMITED = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📤 آپلود فایل")],
        [KeyboardButton("🔒 مدیریت کانال‌های قفل‌شده")],
        [KeyboardButton("👁️ مدیریت شرط سین/ری‌اکشن")],
        [KeyboardButton("📣 پیام همگانی")],
    ],
    resize_keyboard=True,
)


def _is_owner(user_id: int) -> bool:
    """بررسی مالک بودن از .env؛ قبل از validate هم امن است."""

    ids = Config.OWNER_IDS

    if isinstance(ids, (list, tuple, set)):
        return user_id in ids

    return False


def main_keyboard_for(user_id: int) -> ReplyKeyboardMarkup:
    """
    کیبورد پنل اصلی متناسب با کاربر:
    مالک .env دکمه مدیریت ادمین‌ها را می‌بیند؛ ادمین اضافه‌شده نه.
    """

    if _is_owner(user_id):
        return ADMIN_MAIN_KEYBOARD_OWNER

    return ADMIN_MAIN_KEYBOARD_LIMITED

CHANNEL_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ افزودن کانال قفل‌شده")],
        [KeyboardButton("📋 لیست کانال‌های قفل‌شده")],
        [KeyboardButton("↩️ پنل اصلی")],
    ],
    resize_keyboard=True,
)

VIEW_REACTION_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("➕ افزودن/جایگزینی کانال")],
        [KeyboardButton("🔄 فعال/غیرفعال کردن شرط")],
        [KeyboardButton("🗑 حذف کانال ریاکشن")],
        [KeyboardButton("↩️ پنل اصلی")],
    ],
    resize_keyboard=True,
)

ADMIN_MANAGEMENT_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📋 لیست ادمین‌ها")],
        [KeyboardButton("➕ افزودن ادمین"), KeyboardButton("🗑 حذف ادمین")],
        [KeyboardButton("📜 تاریخچه تغییرات")],
        [KeyboardButton("↩️ پنل اصلی")],
    ],
    resize_keyboard=True,
)

CANCEL_OPERATION_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("❌ لغو عملیات")],
    ],
    resize_keyboard=True,
)


def upload_keyboard(auto_delete: bool) -> ReplyKeyboardMarkup:
    """ساخت کیبورد آپلود با توجه به وضعیت حذف خودکار."""

    delete_status = "روشن" if auto_delete else "خاموش"

    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(f"🗑 حذف خودکار: {delete_status}")],
            [
                KeyboardButton("✅ اتمام آپلود"),
                KeyboardButton("❌ لغو آپلود"),
            ],
        ],
        resize_keyboard=True,
    )


# متن دکمه‌های پنل؛ این پیام‌ها هرگز به‌عنوان محتوای همگانی یا
# آپلود تفسیر نمی‌شوند و هندلر مخصوص خودشان آن‌ها را می‌گیرد.

RESERVED_BUTTONS = {
    "📤 آپلود فایل",
    "🔒 مدیریت کانال‌های قفل‌شده",
    "👁️ مدیریت شرط سین/ری‌اکشن",
    "📣 پیام همگانی",
    "👥 مدیریت ادمین‌ها",
    "➕ افزودن کانال قفل‌شده",
    "📋 لیست کانال‌های قفل‌شده",
    "➕ افزودن/جایگزینی کانال",
    "🔄 فعال/غیرفعال کردن شرط",
    "🗑 حذف کانال ریاکشن",
    "↩️ پنل اصلی",
    "✅ اتمام آپلود",
    "❌ لغو آپلود",
    "❌ لغو عملیات",
    "🗑 حذف خودکار: روشن",
    "🗑 حذف خودکار: خاموش",
    "📋 لیست ادمین‌ها",
    "➕ افزودن ادمین",
    "🗑 حذف ادمین",
    "📜 تاریخچه تغییرات",
}
