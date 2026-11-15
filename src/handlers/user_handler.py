import asyncio
import logging
import time

from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from database.models import User, ViewReactionChannel
from handlers.helpers import delete_messages_after
from handlers.state import view_gate_sessions
from utils.base62 import decode_base62
from utils.subscription import (
    get_unjoined_channels,
    require_subscription,
    subscription_keyboard,
)


logger = logging.getLogger(__name__)

# کاربر باید این مدت از نمایش پیام شرط صبر کند؛ این زمان فقط
# سنجش داخلی است و هرگز به کاربر نشان داده نمی‌شود.
VIEW_GATE_WAIT_SECONDS = 10

AUTO_DELETE_SECONDS = 60


# ============================================================
# شرط سین/ری‌اکشن
# ============================================================

async def maybe_require_view_reaction(
    client,
    chat_id: int,
    payload: str,
) -> bool:
    """
    در صورت فعال بودن شرط، پیام کانال ریاکشن را نمایش می‌دهد
    و True برمی‌گرداند. صرف‌نظر کردن از شرط فقط زمانی ممکن است
    که کاربر پیش‌تر از طریق دکمه دریافت، منتظرش مانده باشد.
    """

    channel = await ViewReactionChannel.get_or_none(id=1)

    if not channel or not channel.enabled:
        return False

    current_session = view_gate_sessions.get(chat_id)

    if (
        current_session
        and current_session.get("payload") == payload
    ):
        # اگر کاربر قبلاً این شرط را رد کرده، دیگر لازم نیست.
        if time.monotonic() >= current_session["ready_at"]:
            view_gate_sessions.pop(chat_id, None)
            return False

    else:
        view_gate_sessions[chat_id] = {
            "payload": payload,
            "ready_at": time.monotonic() + VIEW_GATE_WAIT_SECONDS,
        }

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📢 ورود به کانال",
                    url=channel.invite_link,
                )
            ],
            [
                InlineKeyboardButton(
                    "📥 دریافت فایل",
                    callback_data=f"vrget:{payload}",
                )
            ],
        ]
    )

    await client.send_message(
        chat_id,
        "🔒 برای دریافت فایل‌ها، ابتدا وارد کانال زیر شو، "
        "پست‌های اخیر رو ببین و به چندتاشون ریاکشن بزن.\n\n"
        "وقتی انجامش دادی، روی دکمه «📥 دریافت فایل» بزن.",
        reply_markup=keyboard,
    )

    return True


# ============================================================
# ارسال فایل‌های منیفست
# ============================================================

async def send_manifest_files(
    client,
    message: Message,
    payload: str,
    skip_gate: bool = False
):
    chat_id = message.chat.id

    try:
        manifest_id = decode_base62(payload)

        manifest_data = await client.db_channel.get_manifest(
            manifest_id
        )

        file_ids = manifest_data["file_ids"]
        view_gate_enabled = manifest_data["view_gate"]
        auto_delete = manifest_data["auto_delete"]

        if not file_ids:
            await client.send_message(
                chat_id,
                "❌ هیچ فایلی در این منیفست وجود ندارد."
            )
            return

        # بررسی شرط کانال ریاکشن
        if (
            view_gate_enabled
            and chat_id not in Config.ADMIN_IDS
            and not skip_gate
        ):
            gated = await maybe_require_view_reaction(
                client,
                chat_id,
                payload
            )

            if gated:
                return

        sent_message_ids = []

        for file_id in file_ids:
            try:
                stored_message = await client.db_channel.get_message(
                    file_id
                )

                if not stored_message:
                    logger.warning(
                        "File message %s was not found.",
                        file_id
                    )
                    continue

                copied_message = await stored_message.copy(
                    chat_id=chat_id
                )

                if copied_message:
                    sent_message_ids.append(copied_message.id)

            except RPCError:
                logger.exception(
                    "Failed to send file %s",
                    file_id
                )

        if not sent_message_ids:
            await client.send_message(
                chat_id,
                "❌ ارسال فایل‌ها ناموفق بود."
            )
            return

        me = await client.get_me()

        download_link = (
            f"https://t.me/{me.username}?start={payload}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📥 دریافت دوباره فایل‌ها",
                    url=download_link
                )
            ]
        ])

        if auto_delete:
            await client.send_message(
                chat_id,
                "⏳ فایل‌های ارسال‌شده ۶۰ ثانیه دیگر "
                "از این گفتگو حذف می‌شوند.\n"
                "برای نگهداری آن‌ها، قبل از پایان زمان ذخیره‌شان کن.",
                reply_markup=keyboard
            )

            # فقط پیام‌های ارسال‌شده به کاربر حذف می‌شوند.
            # نسخه‌های DB Channel دست‌نخورده می‌مانند.
            asyncio.create_task(
                delete_messages_after(
                    client,
                    chat_id,
                    sent_message_ids,
                    AUTO_DELETE_SECONDS,
                )
            )

        else:
            await client.send_message(
                chat_id,
                "✅ همه فایل‌ها با موفقیت ارسال شدند.",
                reply_markup=keyboard
            )

    except Exception:
        logger.exception("Manifest delivery failed")

        await client.send_message(
            chat_id,
            "❌ هنگام دریافت فایل‌ها خطایی رخ داد."
        )


# ============================================================
# ثبت هندلرها
# ============================================================

def register_user_handler(app: Client):

    # --------------------------------------------------------
    # ثبت کاربر هنگام استارت
    # --------------------------------------------------------

    @app.on_message(
        filters.private & filters.command("start"),
        group=-100,
    )
    async def register_user_on_start(client, message: Message):
        if not message.from_user:
            return

        try:
            await User.get_or_create(
                user_id=message.from_user.id
            )
        except Exception:
            logger.exception(
                "Could not register user %s",
                message.from_user.id,
            )

    # --------------------------------------------------------
    # پیام خوش‌آمدگویی
    # --------------------------------------------------------

    async def send_welcome(client, chat_id: int):
        await client.send_message(
            chat_id,
            "سلام 👋\n"
            "به ربات دریافت فایل خوش اومدی.\n\n"
            "برای دریافت فایل، لینک دریافتی رو باز کن.",
        )

    # --------------------------------------------------------
    # استارت کاربران عادی
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & filters.command("start")
        & ~filters.user(Config.ADMIN_IDS)
    )
    @require_subscription
    async def user_start(client, message: Message):
        payload = (
            message.command[1]
            if len(message.command) > 1
            else None
        )

        if payload:
            await send_manifest_files(
                client,
                message,
                payload,
            )
            return

        await send_welcome(
            client,
            message.chat.id,
        )

    # --------------------------------------------------------
    # بررسی عضویت در کانال‌های قفل‌شده
    # --------------------------------------------------------

    @app.on_callback_query(
        filters.regex(r"^subcheck:")
    )
    async def subscription_check_callback(client, callback_query):
        user_id = callback_query.from_user.id

        data = callback_query.data.partition(":")[2]
        payload = None if data == "home" or not data else data

        try:
            unjoined_channels = await get_unjoined_channels(
                client,
                user_id,
            )

            if unjoined_channels:
                await callback_query.answer(
                    "❌ هنوز در همه کانال‌ها عضو نشدی.",
                    show_alert=True,
                )

                keyboard = subscription_keyboard(
                    unjoined_channels,
                    payload,
                )

                try:
                    await callback_query.message.edit_reply_markup(
                        reply_markup=keyboard
                    )
                except RPCError:
                    pass

                return

            await callback_query.answer(
                "✅ عضویت تأیید شد.",
            )

            try:
                await callback_query.message.delete()
            except RPCError:
                pass

            if payload:
                await send_manifest_files(
                    client,
                    callback_query.message,
                    payload,
                )
            else:
                await send_welcome(
                    client,
                    callback_query.message.chat.id,
                )

        except Exception:
            logger.exception("Subscription check failed")

            await callback_query.answer(
                "❌ بررسی عضویت با خطا مواجه شد.",
                show_alert=True,
            )

    # --------------------------------------------------------
    # دکمه دریافت پس از ریاکشن
    # --------------------------------------------------------

    @app.on_callback_query(
        filters.regex(r"^vrget:[A-Za-z0-9]+$")
    )
    async def view_gate_receive_callback(client, callback_query):
        user_id = callback_query.from_user.id
        payload = callback_query.data.split(":", 1)[1]

        session = view_gate_sessions.get(user_id)

        if not session or session.get("payload") != payload:
            await callback_query.answer(
                "❌ این درخواست منقضی شده؛ لینک دریافت فایل را دوباره باز کن.",
                show_alert=True,
            )
            return

        # زمان باقی‌مانده هرگز نمایش داده نمی‌شود؛ کاربر باید
        # حس کند شرط، دیدن پست‌ها و زدن ریاکشن است نه انتظار.
        if time.monotonic() < session["ready_at"]:
            await callback_query.answer(
                "❌ هنوز ریاکشن نزدی!\n"
                "اول وارد کانال شو، پست‌ها رو ببین و ریاکشن بزن، "
                "بعد دوباره این دکمه رو امتحان کن.",
                show_alert=True,
            )
            return

        view_gate_sessions.pop(user_id, None)

        await callback_query.answer(
            "✅ درخواست ثبت شد."
        )

        gate_message = callback_query.message

        # پیام شرط ریاکشن کامل پاک می‌شود
        try:
            await gate_message.delete()
        except RPCError:
            pass

        await send_manifest_files(
            client,
            gate_message,
            payload,
            skip_gate=True,
        )

    logger.info("User handler registered successfully.")
