"""
ادمین‌های ربات = مالک‌های اصلی از .env (همیشه فعال و غیرقابل حذف)
+ ادمین‌های داینامیک از جدول admins دیتابیس.

حذف ادمین‌ها soft-delete است (removed_at ثبت می‌شود) تا تاریخچه‌ی
افزودن/حذف در جدول admin_logs قابل نمایش بماند.
"""

import logging

from datetime import datetime

from pyrogram import filters

from config import Config
from database.models import Admin, AdminLog


logger = logging.getLogger(__name__)


def get_owner_ids() -> set[int]:
    """مالک‌های اصلی از .env؛ قبل از validate هم امن است."""

    ids = Config.ADMIN_IDS

    if isinstance(ids, (list, tuple, set)):
        return set(ids)

    return set()


async def get_admin_ids() -> set[int]:
    """همه‌ی ادمین‌های فعال: مالک‌های .env + رکوردهای فعال جدول admins."""

    admin_ids = get_owner_ids()

    admin_ids.update(
        admin.user_id
        for admin in await Admin.filter(removed_at__isnull=True)
    )

    return admin_ids


async def is_admin(user_id: int) -> bool:
    if user_id in get_owner_ids():
        return True

    return await Admin.filter(
        user_id=user_id,
        removed_at__isnull=True,
    ).exists()


async def get_active_admins():
    """ادمین‌های فعال دیتابیس (بدون مالک‌های .env)."""

    return await Admin.filter(
        removed_at__isnull=True
    ).order_by("added_at")


async def get_active_admin(user_id: int):
    """یک ادمین فعال دیتابیس؛ اگر فعال نبود None."""

    return await Admin.get_or_none(
        user_id=user_id,
        removed_at__isnull=True,
    )


async def add_admin(
    user_id: int,
    actor_id: int = None,
    name: str = None,
):
    """
    ثبت یا فعال‌سازی مجدد ادمین + ثبت در لاگ.
    اگر از قبل فعال باشد، همان رکورد بدون تغییر برمی‌گردد.
    """

    admin = await Admin.get_or_none(user_id=user_id)

    if admin and admin.removed_at is None:
        return admin

    await Admin.update_or_create(
        user_id=user_id,
        defaults={
            "name": name,
            "added_by": actor_id,
            "removed_at": None,
            "removed_by": None,
        },
    )

    await AdminLog.create(
        action="add",
        target_user_id=user_id,
        target_name=name,
        actor_user_id=actor_id,
    )

    return await Admin.get(user_id=user_id)


async def remove_admin(
    user_id: int,
    actor_id: int = None,
    name: str = None,
):
    """
    حذف نرم ادمین (removed_at ثبت می‌شود) + ثبت در لاگ.
    مالک‌های .env جدول ندارند و قابل حذف نیستند → None برمی‌گردد.
    """

    if user_id in get_owner_ids():
        return None

    admin = await get_active_admin(user_id)

    if not admin:
        return None

    admin.removed_at = datetime.now()
    admin.removed_by = actor_id
    await admin.save()

    await AdminLog.create(
        action="remove",
        target_user_id=user_id,
        target_name=name or admin.name,
        actor_user_id=actor_id,
    )

    return admin


async def get_admin_logs(limit: int = 50):
    """آخرین رکوردهای تاریخچه‌ی افزودن/حذف ادمین‌ها."""

    return await AdminLog.all().order_by("-created_at").limit(limit)


async def resolve_admin_name(client, user_id: int) -> str:
    """حل نام نمایشی کاربر از تلگرام؛ در خطا خود آیدی برمی‌گردد."""

    try:
        user = await client.get_users(user_id)

        first = getattr(user, "first_name", "") or ""
        last = getattr(user, "last_name", "") or ""

        full = (first + " " + last).strip()

        if full:
            return full

        username = getattr(user, "username", "")

        return f"@{username}" if username else str(user_id)

    except Exception:
        return str(user_id)


async def _admin_filter_func(_, __, update):
    # هم برای Message و هم CallbackQuery کار می‌کند
    user = getattr(update, "from_user", None)

    if not user:
        return False

    return await is_admin(user.id)


admin_filter = filters.create(_admin_filter_func)
