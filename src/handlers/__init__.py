from .start_handler import register_start_handler


def register_handlers(app):
    register_start_handler(app)
