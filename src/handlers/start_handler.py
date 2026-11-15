
import asyncio
import logging
import math
import re
import time
from urllib.parse import urlparse

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import RPCError
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from config import Config

from database.models import (
    User,
    SponsorChannel,
    ViewReactionChannel,
)

from utils.base62 import encode_base62, decode_base62
from utils.subscription import (
    require_subscription,
    get_unjoined_channels,
)


logger = logging.getLogger(__name__)


# ============================================================
# کیبوردها
# ============================================================

ADMIN_MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📤 آپلود فایل")],
        [KeyboardButton("🔒 مدیریت کانال‌های قفل‌شده")],
        [KeyboardButton("👁️ مدیریت شرط سین/ری‌اکشن")],
    ],
    resize_keyboard=True,
)

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


# ============================================================
# توابع کمکی
# ============================================================

def get_forwarded_channel(message: Message):
    """
    استخراج کانالی که پیام از آن فوروارد شده است.
    هم فرمت جدید Pyrogram و هم فرمت قدیمی را پشتیبانی می‌کند.
    """

    forward_origin = getattr(message, "forward_origin", None)

    if forward_origin:
        channel = getattr(forward_origin, "chat", None)

        if channel:
            return channel

    old_forward = getattr(message, "forward_from_chat", None)

    if old_forward:
        return old_forward

    return None


def is_valid_telegram_link(link: str) -> bool:
    """بررسی اولیه لینک تلگرام."""

    try:
        parsed = urlparse(link.strip())

        return (
            parsed.scheme == "https"
            and parsed.netloc.lower() in {
                "t.me",
                "www.t.me",
                "telegram.me",
                "www.telegram.me",
            }
        )
    except Exception:
        return False


async def delete_messages_after(
    client,
    chat_id: int,
    message_ids: list[int],
    delay: int = 60,
):
    """
    حذف پیام‌ها بعد از مدت مشخص.

    این تابع نسخه‌های ارسال‌شده به کاربر یا پیام اصلی
    ادمین را حذف می‌کند؛ پیام‌های کانال دیتابیس حذف نمی‌شوند.
    """

    await asyncio.sleep(delay)

    if not message_ids:
        return

    # برای جلوگیری از عبور از محدودیت تعداد پیام در هر درخواست
    for index in range(0, len(message_ids), 100):
        chunk = message_ids[index:index + 100]

        try:
            await client.delete_messages(
                chat_id=chat_id,
                message_ids=chunk,
            )
        except RPCError:
            logger.exception(
                "Could not delete messages from chat %s",
                chat_id,
            )


# ============================================================
# فرمت منیفست
# ============================================================

MANIFEST_HEADER = "UPLOADERBOT_MANIFEST_V1"


def build_manifest_text(
    file_ids: list[int],
    view_gate_enabled: bool,
    auto_delete_enabled: bool,
) -> str:
    """
    ساخت منیفست سه‌خطی:

    خط اول: نسخه منیفست
    خط دوم: وضعیت شرط ویو چنل
    خط سوم: وضعیت حذف خودکار
    خطوط بعدی: آیدی پیام‌های فایل
    """

    lines = [
        MANIFEST_HEADER,
        f"VIEW_GATE={1 if view_gate_enabled else 0}",
        f"AUTO_DELETE={1 if auto_delete_enabled else 0}",
    ]

    lines.extend(str(file_id) for file_id in file_ids)

    return "\n".join(lines)


def parse_manifest_text(text: str) -> dict:
    """خواندن منیفست جدید و پشتیبانی از منیفست‌های قدیمی."""

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    # پشتیبانی از منیفست‌های قدیمی
    if not lines or lines[0] != MANIFEST_HEADER:
        old_file_ids = []

        for line in lines:
            if re.fullmatch(r"\d+", line):
                old_file_ids.append(int(line))

        return {
            "view_gate": False,
            "auto_delete": False,
            "file_ids": old_file_ids,
        }

    if len(lines) < 3:
        return {
            "view_gate": False,
            "auto_delete": False,
            "file_ids": [],
        }

    view_gate_enabled = lines[1] == "VIEW_GATE=1"
    auto_delete_enabled = lines[2] == "AUTO_DELETE=1"

    file_ids = []

    for line in lines[3:]:
        if re.fullmatch(r"\d+", line):
            file_ids.append(int(line))

    return {
        "view_gate": view_gate_enabled,
        "auto_delete": auto_delete_enabled,
        "file_ids": file_ids,
    }


# ============================================================
# ثبت هندلرها
# ============================================================

def register_start_handler(app: Client):

    admin_filter = filters.user(Config.ADMIN_IDS)

    # سشن‌های موقت
    upload_sessions: dict[int, list[int]] = {}
    auto_delete_enabled: dict[int, bool] = {}

    channel_states: dict[int, dict] = {}

    # اطلاعات موقت انتظار ۱۰ ثانیه‌ای
    view_gate_sessions: dict[int, dict] = {}

    # --------------------------------------------------------
    # فیلتر وضعیت‌های مربوط به افزودن کانال
    # --------------------------------------------------------

    def make_state_filter(kind: str, step: str):
        async def state_filter(_, __, message: Message):
            if not message.from_user:
                return False

            state = channel_states.get(message.from_user.id)

            return bool(
                state
                and state.get("kind") == kind
                and state.get("step") == step
            )

        return filters.create(state_filter)

    sponsor_forward_filter = make_state_filter(
        "sponsor",
        "forward",
    )

    sponsor_details_filter = make_state_filter(
        "sponsor",
        "details",
    )

    view_forward_filter = make_state_filter(
        "view",
        "forward",
    )

    view_details_filter = make_state_filter(
        "view",
        "details",
    )

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
    # ساخت کیبورد عضویت در کانال‌های قفل‌شده
    # --------------------------------------------------------

    def make_subscription_keyboard(
        unjoined_channels,
        payload: str
    ):
        buttons = []

        for channel in unjoined_channels:

            # پشتیبانی از خروجی‌های قدیمی که ممکن است
            # کانال را داخل یک tuple یا list قرار داده باشند.
            if isinstance(channel, (list, tuple)):
                channel = next(
                    (
                        item for item in channel
                        if hasattr(item, "name")
                        and hasattr(item, "invite_link")
                    ),
                    None
                )

            if channel is None:
                continue

            buttons.append([
                InlineKeyboardButton(
                    f"📢 {channel.name}",
                    url=channel.invite_link
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                "🔄 بررسی عضویت",
                callback_data=f"subcheck:{payload}"
            )
        ])

        return InlineKeyboardMarkup(buttons)

    # --------------------------------------------------------
    # شرط سین/ری‌اکشن
    # --------------------------------------------------------

    async def maybe_require_view_reaction(
        client,
        chat_id: int,
        payload: str,
    ) -> bool:
        """
        این شرط عضویت یا واکنش را بررسی نمی‌کند.
        فقط ۱۰ ثانیه از زمان نمایش پیام می‌گذرد.
        """

        channel = await ViewReactionChannel.get_or_none(id=1)

        if not channel or not channel.enabled:
            return False

        user_id = chat_id
        now = time.monotonic()

        current_session = view_gate_sessions.get(user_id)

        if (
            current_session
            and current_session.get("payload") == payload
        ):
            ready_at = current_session["ready_at"]

            # اگر قبلاً ۱۰ ثانیه گذشته باشد، دیگر شرط لازم نیست.
            if now >= ready_at:
                view_gate_sessions.pop(user_id, None)
                return False

        else:
            ready_at = now + 10

            view_gate_sessions[user_id] = {
                "payload": payload,
                "ready_at": ready_at,
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
            "🔒 برای دریافت فایل، وارد کانال زیر شو و پست‌ها رو ببین "
            "یا واکنش بزن.\n\n"
            "بعد از ۱۰ ثانیه روی دکمه «دریافت فایل» بزن.\n"
            "توجه: ربات انجام بازدید یا واکنش رو بررسی نمی‌کنه.",
            reply_markup=keyboard,
        )

        return True

    # --------------------------------------------------------
    # ارسال فایل‌های منیفست
    # --------------------------------------------------------

    async def send_manifest_files(
        client,
        message,
        payload: str,
        skip_gate: bool = False
    ):
        chat_id = message.chat.id

        try:
            manifest_id = decode_base62(payload)

            # دریافت اطلاعات کامل منیفست
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

            # ارسال فایل‌ها
            for file_id in file_ids:

                try:
                    stored_message = await client.db_channel.get_message(
                        file_id
                    )

                    if not stored_message:
                        logging.warning(
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
                    logging.exception(
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
                    (
                        "✅ همه فایل‌ها ارسال شدند.\n\n"
                        "⏳ فایل‌های ارسال‌شده ۶۰ ثانیه دیگر "
                        "از این گفتگو حذف می‌شوند.\n"
                        "برای نگهداری آن‌ها، قبل از پایان زمان ذخیره‌شان کن."
                    ),
                    reply_markup=keyboard
                )

                # فقط پیام‌های ارسال‌شده به کاربر حذف می‌شوند.
                # نسخه‌های DB Channel دست‌نخورده می‌مانند.
                asyncio.create_task(
                    delete_messages_after(
                        client,
                        chat_id,
                        sent_message_ids,
                        60
                    )
                )

            else:

                await client.send_message(
                    chat_id,
                    "✅ همه فایل‌ها با موفقیت ارسال شدند.",
                    reply_markup=keyboard
                )

        except Exception:
            logging.exception("Manifest delivery failed")

            await client.send_message(
                chat_id,
                "❌ هنگام دریافت فایل‌ها خطایی رخ داد."
            )
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
            await send_manifest_files(
                client,
                message,
                payload,
            )
            return

        await message.reply_text(
            "سلام ادمین عزیز 👋\n"
            "به پنل مدیریت خوش اومدی.",
            reply_markup=ADMIN_MAIN_KEYBOARD,
        )

    # --------------------------------------------------------
    # استارت کاربران عادی
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & filters.command("start")
        & ~admin_filter
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

                keyboard = make_subscription_keyboard(
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
    # دکمه دریافت پس از ۱۰ ثانیه
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

        remaining = session["ready_at"] - time.monotonic()

        if remaining > 0:
            await callback_query.answer(
                f"⏳ لطفاً {math.ceil(remaining)} ثانیه دیگر صبر کن.",
                show_alert=True,
            )
            return

        view_gate_sessions.pop(user_id, None)

        await callback_query.answer(
            "✅ حالا می‌توانی فایل‌ها را دریافت کنی."
        )

        try:
            await callback_query.message.edit_reply_markup(
                reply_markup=None
            )
        except RPCError:
            pass

        await send_manifest_files(
            client,
            callback_query.message,
            payload,
            skip_gate=True,
        )

    # ========================================================
    # مدیریت کانال‌های قفل‌شده
    # ========================================================

    # --------------------------------------------------------
    # شروع افزودن کانال قفل‌شده
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^🔒 مدیریت کانال‌های قفل‌شده$")
    )
    async def open_sponsor_menu(client, message: Message):
        channel_states.pop(message.from_user.id, None)

        await message.reply_text(
            "🔒 مدیریت کانال‌های قفل‌شده",
            reply_markup=CHANNEL_MENU_KEYBOARD,
        )

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^➕ افزودن کانال قفل‌شده$")
    )
    async def start_add_sponsor_channel(client, message: Message):
        admin_id = message.from_user.id

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

    # ========================================================
    # مدیریت کانال سین/ری‌اکشن
    # ========================================================

    # --------------------------------------------------------
    # ورود به منوی کانال ریاکشن
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^👁️ مدیریت شرط سین/ری‌اکشن$")
    )
    async def open_view_menu(client, message: Message):
        channel_states.pop(message.from_user.id, None)

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
    # شروع افزودن یا جایگزینی کانال ریاکشن
    # --------------------------------------------------------

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^➕ افزودن/جایگزینی کانال$")
    )
    async def start_add_view_channel(client, message: Message):
        admin_id = message.from_user.id

        channel_states[admin_id] = {
            "kind": "view",
            "step": "forward",
        }

        await message.reply_text(
            "📩 یک پست از کانالی که می‌خواهی برای شرط سین/ری‌اکشن استفاده شود فوروارد کن.\n\n"
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

    # ========================================================
    # لغو عملیات و بازگشت به پنل
    # ========================================================

    @app.on_message(
        filters.private
        & admin_filter
        & filters.regex(r"^❌ لغو عملیات$")
    )
    async def cancel_general_operation(client, message: Message):
        admin_id = message.from_user.id

        channel_states.pop(admin_id, None)

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

        await message.reply_text(
            "🏠 پنل اصلی مدیریت",
            reply_markup=ADMIN_MAIN_KEYBOARD,
        )

    # ========================================================
    # آپلود فایل
    # ========================================================

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

        if admin_id in channel_states:
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
                reply_markup=ADMIN_MAIN_KEYBOARD,
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

        # اگر در حال افزودن کانال هستیم، پیام را آپلود نکن.
        if admin_id in channel_states:
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
                        60,
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
                reply_markup=ADMIN_MAIN_KEYBOARD,
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

            # این متد باید در کلاس db_channel به‌روز شده باشد.
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
                reply_markup=ADMIN_MAIN_KEYBOARD,
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
            reply_markup=ADMIN_MAIN_KEYBOARD,
        )

    logger.info("Start handler registered successfully.")
