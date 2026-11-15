from tortoise import Tortoise

from config import Config

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
    # Get Manifest File IDs
    # --------------------------------------------------------

    async def get_manifest_files(
        self,
        manifest_id: int
    ) -> list[int]:
        """
        Return only file message IDs.

        Kept for compatibility with handlers that
        only need the list of file IDs.
        """

        manifest_data = await self.get_manifest(
            manifest_id
        )

        file_ids = manifest_data["file_ids"]

        if not file_ids:
            raise ValueError(
                f"Manifest {manifest_id} contains no files."
            )

        return file_ids
