import logging

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from database.database import DBChannel
from database.models import Admin as AdminModel
from handlers.keyboards import (
    ADMIN_MAIN_KEYBOARD,
    ADMIN_MANAGEMENT_KEYBOARD,
    CANCEL_OPERATION_KEYBOARD,
)
from handlers.state import admin_management_states, admin_filter


logger = logging.getLogger(__name__)


def register_admin_management_handler(app: Client):
    admin_filter_dyn = admin_filter()

    # --------------------------------------------------------
    # ورود به منوی مدیریت ادمین‌ها
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter_dyn
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
        & admin_filter_dyn
        & filters.regex(r"^📋 لیست ادمین‌ها$")
    )
    async def list_admins(client, message: Message):
        admin_management_states.pop(message.from_user.id, None)

        db = DBChannel.__new__(DBChannel)

        lines = ["👥 لیست ادمین‌ها:\n"]

        # مالک‌های .env
        lines.append("👑 مالکان ربات (.env):")
        for owner_id in Config.ADMIN_IDS:
            name = await db.resolve_admin_name(client, owner_id)
            lines.append(f"• {owner_id} — {name}")

        # ادمین‌های دیتابیس
        active_admins = await db.get_active_admins()

        if active_admins:
            lines.append("\n🛡 ادمین‌های فعال (دیتابیس):")
            for admin in active_admins:
                added_by_name = await db.resolve_admin_name(
                    client, admin.added_by
                ) if admin.added_by else "—"
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
        & admin_filter_dyn
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

    @app.on_message(
        filters.private
        & admin_filter_dyn
        & filters.create(
            lambda _, __, m: bool(
                m.from_user
                and admin_management_states.get(m.from_user.id, {}).get("kind")
                == "add"
            )
        ),
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

        if message.forward_from:
            target_user_id = message.forward_from.id
            target_name = (
                (message.forward_from.first_name or "")
                + " "
                + (message.forward_from.last_name or "")
            ).strip() or None
        elif message.forward_from_chat:
            target_user_id = message.forward_from_chat.id
            target_name = message.forward_from_chat.title or None
        else:
            text = (message.text or "").strip()
            if text.lstrip("-").isdigit():
                target_user_id = int(text)
            else:
                await message.reply_text(
                    "❌ لطفاً یک آیدی عددی بفرست یا پیام کاربر را Forward کن."
                )
                return

        if target_user_id in Config.ADMIN_IDS:
            await message.reply_text(
                "⚠️ این کاربر مالک ربات است و قبلاً ادمین است.",
                reply_markup=ADMIN_MANAGEMENT_KEYBOARD,
            )
            admin_management_states.pop(admin_id, None)
            return

        db = DBChannel.__new__(DBChannel)
        await db.add_admin(target_user_id, admin_id, target_name)

        admin_management_states.pop(admin_id, None)

        name = await db.resolve_admin_name(client, target_user_id)

        await message.reply_text(
            f"✅ کاربر به‌عنوان ادمین اضافه شد.\n\n"
            f"آیدی: {target_user_id}\n"
            f"نام: {name or '—'}",
            reply_markup=ADMIN_MANAGEMENT_KEYBOARD,
        )

    # --------------------------------------------------------
    # شروع حذف ادمین
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter_dyn
        & filters.regex(r"^🗑 حذف ادمین$")
    )
    async def start_remove_admin(client, message: Message):
        admin_id = message.from_user.id

        db = DBChannel.__new__(DBChannel)
        active_admins = await db.get_active_admins()

        if not active_admins:
            await message.reply_text(
                "هیچ ادمین اضافی برای حذف وجود ندارد.\n"
                "مالک‌های .env قابل حذف نیستند.",
                reply_markup=ADMIN_MANAGEMENT_KEYBOARD,
            )
            return

        # نمایش لیست دکمه‌های inline برای حذف
        rows = []
        for admin in active_admins:
            rows.append(
                [
                    InlineKeyboardButton(
                        f"🗑 حذف {admin.name or admin.user_id}",
                        callback_data=f"removeadmin:{admin.user_id}",
                    )
                ]
            )

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
        & admin_filter_dyn
    )
    async def confirm_remove_admin(client, callback_query):
        admin_id = callback_query.from_user.id
        target_user_id = int(callback_query.data.split(":", 1)[1])

        if target_user_id in Config.ADMIN_IDS:
            await callback_query.answer(
                "❌ مالک ربات قابل حذف نیست.",
                show_alert=True,
            )
            return

        db = DBChannel.__new__(DBChannel)
        admin_obj = await AdminModel.get_or_none(
            user_id=target_user_id,
            removed_at__is_null=True,
        )

        if not admin_obj:
            await callback_query.answer(
                "❌ این کاربر دیگر ادمین فعال نیست.",
                show_alert=True,
            )
            return

        actor_name = await db.resolve_admin_name(client, admin_id)
        await db.remove_admin(target_user_id, admin_id, admin_obj.name)

        await callback_query.answer("✅ ادمین حذف شد.", show_alert=True)

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
        & admin_filter_dyn
        & filters.regex(r"^📜 تاریخچه تغییرات$")
    )
    async def show_admin_history(client, message: Message):
        admin_management_states.pop(message.from_user.id, None)

        db = DBChannel.__new__(DBChannel)
        logs = await db.get_admin_logs(limit=30)

        if not logs:
            await message.reply_text(
                "هنوز هیچ تغییراتی در لیست ادمین‌ها ثبت نشده است.",
                reply_markup=ADMIN_MANAGEMENT_KEYBOARD,
            )
            return

        lines = ["📜 تاریخچه تغییرات ادمین‌ها:\n"]

        for log in logs:
            actor_name = log.actor_name or await db.resolve_admin_name(
                client, log.actor_user_id
            )
            target_name = log.target_name or str(log.target_user_id)

            action_emoji = "➕" if log.action == "add" else "🗑"

            lines.append(
                f"{action_emoji} {log.action.upper()} | {log.target_user_id}"
                f" ({target_name}) توسط {actor_name}"
                f"\n  زمان: {log.created_at.strftime('%Y/%m/%d %H:%M')}"
            )

        await message.reply_text("\n".join(lines), reply_markup=ADMIN_MANAGEMENT_KEYBOARD)

    logger.info("Admin management handler registered successfully.")
