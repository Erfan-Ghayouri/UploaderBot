import logging

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from handlers.helpers import get_forwarded_channel, get_forwarded_user
from handlers.keyboards import (
    ADMIN_MANAGEMENT_KEYBOARD,
    CANCEL_OPERATION_KEYBOARD,
)
from handlers.state import admin_management_states
from utils.admins import (
    add_admin,
    get_active_admin,
    get_active_admins,
    get_admin_logs,
    get_owner_ids,
    is_owner,
    owner_filter,
    remove_admin,
    resolve_admin_name,
)


logger = logging.getLogger(__name__)

# کل مدیریت ادمین‌ها فقط برای مالک‌های .env است؛
# ادمین‌های اضافه‌شده به این منو دسترسی ندارند.
# فیلتر پویا است و در زمان اجرا ارزیابی می‌شود (بعد از validate).


def register_admin_management_handler(app: Client):

    # --------------------------------------------------------
    # ورود به منوی مدیریت ادمین‌ها
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & owner_filter
        & filters.regex(r"^👥 مدیریت ادمین‌ها$")
    )
    async def open_admin_management(client, message: Message):
        admin_management_states.pop(message.from_user.id, None)

        await message.reply_text(
            "👥 مدیریت ادمین‌ها\n\n"
            "از منوی زیر انتخاب کن:",
            reply_markup=ADMIN_MANAGEMENT_KEYBOARD,
        )

    # --------------------------------------------------------
    # لیست ادمین‌ها
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & owner_filter
        & filters.regex(r"^📋 لیست ادمین‌ها$")
    )
    async def list_admins(client, message: Message):
        admin_management_states.pop(message.from_user.id, None)

        lines = ["👥 لیست ادمین‌ها:\n"]

        # مالک‌های .env
        lines.append("👑 مالکان ربات (.env):")
        for owner_id in get_owner_ids():
            name = await resolve_admin_name(client, owner_id)
            lines.append(f"• {owner_id} — {name}")

        # ادمین‌های دیتابیس
        active_admins = await get_active_admins()

        if active_admins:
            lines.append("\n🛡 ادمین‌های فعال (دیتابیس):")
            for admin in active_admins:
                added_by_name = (
                    await resolve_admin_name(client, admin.added_by)
                    if admin.added_by
                    else "—"
                )
                lines.append(
                    f"• {admin.user_id} — {admin.name or 'بدون نام'}"
                    f"\n  اضافه‌شده توسط: {added_by_name}"
                )
        else:
            lines.append("\nهیچ ادمین اضافی در دیتابیس ثبت نشده است.")

        await message.reply_text("\n".join(lines))

    # --------------------------------------------------------
    # شروع افزودن ادمین
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & owner_filter
        & filters.regex(r"^➕ افزودن ادمین$")
    )
    async def start_add_admin(client, message: Message):
        admin_id = message.from_user.id

        admin_management_states[admin_id] = {"kind": "add"}

        await message.reply_text(
            "➕ افزودن ادمین جدید\n\n"
            "آیدی عددی کاربر را بفرست، یا یک پیام از او را Forward کن.\n\n"
            "آیدی عددی باید عدد باشد (مثلاً 123456789).",
            reply_markup=CANCEL_OPERATION_KEYBOARD,
        )

    # --------------------------------------------------------
    # دریافت آیدی برای افزودن ادمین
    # --------------------------------------------------------

    async def _add_pending_filter(_, __, m: Message):
        if not m.from_user:
            return False

        state = admin_management_states.get(m.from_user.id)

        return bool(state and state.get("kind") == "add")

    @app.on_message(
        filters.private
        & owner_filter
        & filters.create(_add_pending_filter),
        group=-2,
    )
    async def receive_add_admin_id(client, message: Message):
        admin_id = message.from_user.id
        state = admin_management_states.get(admin_id)

        if not state or state.get("kind") != "add":
            return

        # استخراج آیدی از فوروارد یا متن
        target_user_id = None
        target_name = None

        sender_user = get_forwarded_user(message)

        if sender_user:
            # فوروارد از یک کاربر
            target_user_id = sender_user.id
            target_name = (
                (sender_user.first_name or "")
                + " "
                + (sender_user.last_name or "")
            ).strip() or None
        else:
            forwarded_chat = get_forwarded_channel(message)

            if forwarded_chat:
                # فوروارد از یک کانال/گروه
                target_user_id = forwarded_chat.id
                target_name = forwarded_chat.title or None
            else:
                text = (message.text or "").strip()

                if text.lstrip("-").isdigit():
                    target_user_id = int(text)
                else:
                    await message.reply_text(
                        "❌ لطفاً یک آیدی عددی بفرست "
                        "یا پیام کاربر را Forward کن."
                    )
                    return

        if await is_owner(target_user_id):
            await message.reply_text(
                "⚠️ این کاربر مالک ربات است و قبلاً ادمین است.",
                reply_markup=ADMIN_MANAGEMENT_KEYBOARD,
            )
            admin_management_states.pop(admin_id, None)
            return

        await add_admin(target_user_id, admin_id, target_name)

        admin_management_states.pop(admin_id, None)

        name = await resolve_admin_name(client, target_user_id)

        await message.reply_text(
            f"✅ کاربر به‌عنوان ادمین اضافه شد.\n\n"
            f"آیدی: {target_user_id}\n"
            f"نام: {name or target_name or '—'}",
            reply_markup=ADMIN_MANAGEMENT_KEYBOARD,
        )

    # --------------------------------------------------------
    # شروع حذف ادمین
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & owner_filter
        & filters.regex(r"^🗑 حذف ادمین$")
    )
    async def start_remove_admin(client, message: Message):
        active_admins = await get_active_admins()

        if not active_admins:
            await message.reply_text(
                "هیچ ادمین اضافی برای حذف وجود ندارد.\n"
                "مالک‌های .env قابل حذف نیستند.",
                reply_markup=ADMIN_MANAGEMENT_KEYBOARD,
            )
            return

        # نمایش لیست دکمه‌های inline برای حذف
        rows = [
            [
                InlineKeyboardButton(
                    f"🗑 حذف {admin.name or admin.user_id}",
                    callback_data=f"removeadmin:{admin.user_id}",
                )
            ]
            for admin in active_admins
        ]

        await message.reply_text(
            "🗑 حذف ادمین\n\n"
            "این ادمین‌ها قابل حذفند (مالک‌های .env قابل حذف نیستند):",
            reply_markup=InlineKeyboardMarkup(rows),
        )

    # --------------------------------------------------------
    # حذف ادمین از طریق دکمه inline
    # --------------------------------------------------------

    @app.on_callback_query(
        filters.regex(r"^removeadmin:-?\d+$")
        & owner_filter
    )
    async def confirm_remove_admin(client, callback_query):
        actor_id = callback_query.from_user.id
        target_user_id = int(callback_query.data.split(":", 1)[1])

        if await is_owner(target_user_id):
            await callback_query.answer(
                "❌ مالک ربات قابل حذف نیست.",
                show_alert=True,
            )
            return

        admin_obj = await get_active_admin(target_user_id)

        if not admin_obj:
            await callback_query.answer(
                "❌ این کاربر دیگر ادمین فعال نیست.",
                show_alert=True,
            )
            return

        await remove_admin(target_user_id, actor_id, admin_obj.name)

        await callback_query.answer(
            "✅ ادمین حذف شد.",
            show_alert=True,
        )

        try:
            await callback_query.message.edit_text(
                f"✅ کاربر {target_user_id} از لیست ادمین‌ها حذف شد."
            )
        except Exception:
            pass

    # --------------------------------------------------------
    # تاریخچه تغییرات ادمین
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & owner_filter
        & filters.regex(r"^📜 تاریخچه تغییرات$")
    )
    async def show_admin_history(client, message: Message):
        admin_management_states.pop(message.from_user.id, None)

        logs = await get_admin_logs(limit=30)

        if not logs:
            await message.reply_text(
                "هنوز هیچ تغییراتی در لیست ادمین‌ها ثبت نشده است.",
                reply_markup=ADMIN_MANAGEMENT_KEYBOARD,
            )
            return

        lines = ["📜 تاریخچه تغییرات ادمین‌ها:\n"]

        for log in logs:
            actor_name = log.actor_name or await resolve_admin_name(
                client, log.actor_user_id
            )
            target_name = log.target_name or str(log.target_user_id)

            action_emoji = "➕" if log.action == "add" else "🗑"

            lines.append(
                f"{action_emoji} {log.action.upper()} | {log.target_user_id}"
                f" ({target_name}) توسط {actor_name}"
                f"\n  زمان: {log.created_at.strftime('%Y/%m/%d %H:%M')}"
            )

        await message.reply_text(
            "\n".join(lines),
            reply_markup=ADMIN_MANAGEMENT_KEYBOARD,
        )

    logger.info("Admin management handler registered successfully.")
