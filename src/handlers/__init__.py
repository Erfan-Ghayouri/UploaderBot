from .admin_handler import register_admin_handler
from .admin_management_handler import register_admin_management_handler
from .broadcast_handler import register_broadcast_handler
from .sponsor_handler import register_sponsor_handler
from .upload_handler import register_upload_handler
from .user_handler import register_user_handler
from .view_channel_handler import register_view_channel_handler


def register_handlers(app):
    register_user_handler(app)
    register_admin_handler(app)
    register_admin_management_handler(app)
    register_sponsor_handler(app)
    register_view_channel_handler(app)
    register_upload_handler(app)
    register_broadcast_handler(app)
