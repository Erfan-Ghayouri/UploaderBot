from datetime import datetime

from tortoise import Tortoise

from config import Config

from database.models import Admin, AdminLog

from pyrogram import Client
from pyrogram.types import Message


# ============================================================
# Database Initialization
# ============================================================

async def init_database():
    """
    Initialize Tortoise ORM and create missing tables.
    """

    database_type = str(Config.DATABASE).lower().strip()

    if database_type == "sqlite":
        db_url = "sqlite://db.sqlite3"

    else:
        db_url = Config.DATABASE_URL

        if not db_url:
            raise ValueError(
                "DATABASE_URL is not configured."
            )

    await Tortoise.init(
        config={
            "connections": {
                "default": db_url
            },

            "apps": {
                "models": {
                    "models": [
                        "database.models"
                    ],

                    "default_connection": "default"
                }
            }
        }
    )

    # Create tables that do not exist yet.
    await Tortoise.generate_schemas(safe=True)

    print("✅ Database initialized successfully.")
    print("✅ Database tables checked and created.")


# ============================================================
# Close Database
# ============================================================

async def close_database():
    """
    Close all Tortoise database connections.
    """

    await Tortoise.close_connections()

    print("✅ Database connections closed.")


# ============================================================
# Manifest Configuration
# ============================================================

MANIFEST_HEADER = "UPLOADERBOT_MANIFEST_V1"


def build_manifest_text(
    file_ids: list[int],
    view_gate_enabled: bool = False,
    auto_delete_enabled: bool = False
) -> str:
    """
    Build manifest text.

    Format:

    UPLOADERBOT_MANIFEST_V1
    VIEW_GATE=1
    AUTO_DELETE=1
    12345
    12346
    12347
    """

    if not file_ids:
        raise ValueError(
            "Cannot create a manifest without files."
        )

    lines = [
        MANIFEST_HEADER,

        f"VIEW_GATE={1 if view_gate_enabled else 0}",

        f"AUTO_DELETE={1 if auto_delete_enabled else 0}",
    ]

    for file_id in file_ids:
        lines.append(str(int(file_id)))

    return "\n".join(lines)


def parse_manifest_text(text: str) -> dict:
    """
    Parse manifest text.

    Returns:

    {
        "view_gate": bool,
        "auto_delete": bool,
        "file_ids": list[int]
    }

    Supports both new and old manifest formats.
    """

    if not text:
        raise ValueError("Manifest is empty.")

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        raise ValueError("Manifest is empty.")

    # --------------------------------------------------------
    # New manifest format
    # --------------------------------------------------------

    if lines[0] == MANIFEST_HEADER:

        if len(lines) < 3:
            raise ValueError(
                "Manifest configuration is incomplete."
            )

        if not lines[1].startswith("VIEW_GATE="):
            raise ValueError(
                "Invalid VIEW_GATE configuration."
            )

        if not lines[2].startswith("AUTO_DELETE="):
            raise ValueError(
                "Invalid AUTO_DELETE configuration."
            )

        view_gate_value = lines[1].split("=", 1)[1]
        auto_delete_value = lines[2].split("=", 1)[1]

        if view_gate_value not in ("0", "1"):
            raise ValueError(
                "Invalid VIEW_GATE value."
            )

        if auto_delete_value not in ("0", "1"):
            raise ValueError(
                "Invalid AUTO_DELETE value."
            )

        file_ids = []

        for line in lines[3:]:
            try:
                file_ids.append(int(line))
            except ValueError:
                raise ValueError(
                    f"Invalid file message ID: {line}"
                )

        return {
            "view_gate": view_gate_value == "1",
            "auto_delete": auto_delete_value == "1",
            "file_ids": file_ids
        }

    # --------------------------------------------------------
    # Old manifest format
    #
    # FILE_MANIFEST
    # 12345
    # 12346
    # --------------------------------------------------------

    if lines[0] == "FILE_MANIFEST":

        file_ids = []

        for line in lines[1:]:
            try:
                file_ids.append(int(line))
            except ValueError:
                raise ValueError(
                    f"Invalid file message ID: {line}"
                )

        return {
            "view_gate": False,
            "auto_delete": False,
            "file_ids": file_ids
        }

    raise ValueError(
        "Unknown manifest format."
    )


# ============================================================
# DB Channel
# ============================================================

class DBChannel:
    """
    Telegram DB Channel manager.

    Files and manifests are stored inside Telegram.

    PostgreSQL/SQLite is not used to store file message IDs.
    """

    def __init__(self, app: Client):
        self.app = app
        self.channel_id = Config.DB_CHANNEL_ID

    # --------------------------------------------------------
    # Save File
    # --------------------------------------------------------

    async def save_file(self, message: Message) -> Message:
        """
        Copy a file message into the DB Channel.

        Returns:
            The copied message inside the DB Channel.
        """

        if not self.channel_id:
            raise ValueError(
                "DB_CHANNEL_ID is not configured."
            )

        saved_message = await message.copy(
            chat_id=self.channel_id
        )

        if not saved_message:
            raise RuntimeError(
                "Failed to save file in DB Channel."
            )

        return saved_message

    # --------------------------------------------------------
    # Get Message
    # --------------------------------------------------------

    async def get_message(
        self,
        message_id: int
    ) -> Message | None:
        """
        Retrieve a message from the DB Channel.
        """

        message = await self.app.get_messages(
            chat_id=self.channel_id,
            message_ids=int(message_id)
        )

        if not message:
            return None

        if getattr(message, "empty", False):
            return None

        return message

    # --------------------------------------------------------
    # Create Manifest
    # --------------------------------------------------------

    async def create_manifest(
        self,
        file_ids: list[int],
        view_gate_enabled: bool = False,
        auto_delete_enabled: bool = False
    ) -> Message:
        """
        Create a manifest message in the DB Channel.

        Stores:
            1. Manifest version
            2. View/reaction gate status
            3. Auto-delete status
            4. File message IDs
        """

        manifest_text = build_manifest_text(
            file_ids=file_ids,
            view_gate_enabled=view_gate_enabled,
            auto_delete_enabled=auto_delete_enabled
        )

        manifest_message = await self.app.send_message(
            chat_id=self.channel_id,
            text=manifest_text
        )

        if not manifest_message:
            raise RuntimeError(
                "Failed to create manifest."
            )

        return manifest_message

    # --------------------------------------------------------
    # Get Manifest
    # --------------------------------------------------------

    async def get_manifest(
        self,
        manifest_id: int
    ) -> dict:
        """
        Retrieve and parse a manifest.

        Returns:

        {
            "view_gate": bool,
            "auto_delete": bool,
            "file_ids": list[int]
        }
        """

        manifest = await self.get_message(
            manifest_id
        )

        if not manifest:
            raise ValueError(
                f"Manifest not found: {manifest_id}"
            )

        manifest_text = (
            manifest.text
            or manifest.caption
            or ""
        )

        if not manifest_text:
            raise ValueError(
                f"Manifest {manifest_id} has no text."
            )

        return parse_manifest_text(
            manifest_text
        )

    # --------------------------------------------------------
    # Admin Management
    # --------------------------------------------------------

    async def is_admin(self, user_id: int) -> bool:
        """
        Checks if a user is an admin.

        Owners from .env (ADMIN_IDS) are always admins.
        Database admins with no removed_at are also admins.
        """

        if user_id in Config.ADMIN_IDS:
            return True

        admin = await Admin.get_or_none(
            user_id=user_id,
            removed_at__isnull=True,
        )

        return admin is not None

    async def get_active_admins(self):
        """Return all active (not removed) database admins."""

        return await Admin.filter(
            removed_at__isnull=True
        ).order_by("added_at")

    async def add_admin(self, user_id: int, actor_id: int, name: str = None):
        """
        Add a user as admin.

        Returns the Admin instance. If already active, returns it unchanged.
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
            actor_name=None,
        )

        return await Admin.get(user_id=user_id)

    async def remove_admin(self, user_id: int, actor_id: int, name: str = None):
        """
        Soft-remove an admin (marks removed_at).

        Returns the Admin instance, or None if not active.
        Owners from .env cannot be removed.
        """

        if user_id in Config.ADMIN_IDS:
            return None

        admin = await Admin.get_or_none(
            user_id=user_id,
            removed_at__isnull=True,
        )

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
            actor_name=None,
        )

        return admin

    async def get_admin_logs(self, limit: int = 50):
        """Return the most recent admin change log entries."""

        return await AdminLog.all().limit(limit)

    async def resolve_admin_name(self, client: Client, user_id: int) -> str:
        """Try to resolve a Telegram user's display name."""

        try:
            user = await client.get_users(user_id)

            first = getattr(user, "first_name", "") or ""
            last = getattr(user, "last_name", "") or ""

            full = (first + " " + last).strip()

            return full or f"@{getattr(user, 'username', '') or user_id}"

        except Exception:
            return str(user_id)
