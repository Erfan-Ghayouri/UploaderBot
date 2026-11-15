from .admin_handler import register_admin_handlers
from .start_handler import register_start_handler


def register_handlers(app):
    register_start_handler(app)
    register_admin_handlers(app)
